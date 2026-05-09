param(
    [string]$AdbPath = "",
    [string]$LdConsolePath = "",
    [string]$ReportPath = ".\ldplayer-inspect.json"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[步骤] $Message" -ForegroundColor Cyan
}

function Write-DebugLog {
    param([string]$Message)
    Write-Host "[日志] $Message" -ForegroundColor DarkGray
}

function ConvertTo-ArgumentString {
    param([string[]]$ArgumentList)

    # 将参数数组安全拼接成命令行字符串，兼容 Windows PowerShell 5.1。
    $escaped = foreach ($arg in $ArgumentList) {
        if ($null -eq $arg) {
            '""'
            continue
        }

        if ($arg -notmatch '[\s"]') {
            $arg
            continue
        }

        '"' + (($arg -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
    }

    return ($escaped -join ' ')
}

function Require-Path {
    param(
        [string]$PathValue,
        [string]$Label
    )

    if (-not $PathValue -or -not (Test-Path -LiteralPath $PathValue)) {
        throw "未找到 ${Label}: $PathValue"
    }
}

function Get-ExistingPath {
    param([string[]]$Candidates)

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Get-LDPlayerInstallDirsFromRegistry {
    $roots = @(
        "HKCU:\Software\leidian",
        "HKLM:\Software\leidian",
        "HKLM:\Software\WOW6432Node\leidian",
        "HKCU:\Software\ChangZhi2",
        "HKLM:\Software\ChangZhi2",
        "HKLM:\Software\WOW6432Node\ChangZhi2"
    )
    $valueNames = @("InstallDir", "InstallPath", "Path", "Dir", "LdPlayerPath")
    $dirs = New-Object System.Collections.Generic.List[string]

    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        $items = @(Get-Item -LiteralPath $root -ErrorAction SilentlyContinue)
        $items += @(Get-ChildItem -LiteralPath $root -Recurse -ErrorAction SilentlyContinue)

        foreach ($item in $items) {
            try {
                $props = Get-ItemProperty -LiteralPath $item.PSPath -ErrorAction SilentlyContinue
                foreach ($name in $valueNames) {
                    $value = $props.$name
                    if (-not [string]::IsNullOrWhiteSpace($value) -and (Test-Path -LiteralPath $value)) {
                        $dirs.Add((Resolve-Path -LiteralPath $value).Path)
                    }
                }
            } catch {
            }
        }
    }

    return @($dirs | Select-Object -Unique)
}

function Get-LDPlayerInstallDirs {
    $dirs = New-Object System.Collections.Generic.List[string]

    foreach ($dir in Get-LDPlayerInstallDirsFromRegistry) {
        $dirs.Add($dir)
    }

    $commonDirs = @(
        "D:\leidian\LDPlayer9",
        "D:\leidian",
        "C:\leidian\LDPlayer9",
        "C:\leidian",
        "C:\Program Files\LDPlayer\LDPlayer9",
        "C:\Program Files\LDPlayer",
        "C:\Program Files\dnplayerext2",
        "D:\LDPlayer",
        "C:\LDPlayer"
    )

    foreach ($dir in $commonDirs) {
        if (Test-Path -LiteralPath $dir) {
            $dirs.Add((Resolve-Path -LiteralPath $dir).Path)
        }
    }

    return @($dirs | Select-Object -Unique)
}

function Resolve-AdbPath {
    param([string]$Hint)

    # 优先使用手工传入的 adb 路径，其次从注册表、常见目录和 PATH 自动查找。
    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($dir in Get-LDPlayerInstallDirs) {
        $candidates.Add((Join-Path $dir "adb.exe"))
    }

    $candidates.Add((Join-Path $env:ProgramFiles "Android\platform-tools\adb.exe"))
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Android\platform-tools\adb.exe"))
    }

    $resolved = Get-ExistingPath -Candidates @($candidates)
    if ($resolved) {
        return $resolved
    }

    $command = Get-Command adb -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return $null
}

function Resolve-LdConsolePath {
    param(
        [string]$Hint,
        [string]$ResolvedAdbPath
    )

    # 优先使用手工传入的 ldconsole 路径，其次根据 adb 所在目录和常见安装目录自动推导。
    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    $candidates = New-Object System.Collections.Generic.List[string]

    if ($ResolvedAdbPath) {
        $adbDir = Split-Path -Parent $ResolvedAdbPath
        $candidates.Add((Join-Path $adbDir "ldconsole.exe"))
    }

    foreach ($dir in Get-LDPlayerInstallDirs) {
        $candidates.Add((Join-Path $dir "ldconsole.exe"))
    }

    return Get-ExistingPath -Candidates @($candidates)
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutSeconds = 20,
        [System.Text.Encoding]$OutputEncoding = $null
    )

    # 统一通过独立进程调用外部程序，并增加超时保护。
    Write-DebugLog "执行外部命令: $FilePath $($ArgumentList -join ' ')"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.Arguments = ConvertTo-ArgumentString -ArgumentList $ArgumentList
    if ($OutputEncoding) {
        $psi.StandardOutputEncoding = $OutputEncoding
        $psi.StandardErrorEncoding = $OutputEncoding
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    [void]$process.Start()

    # 并行读取标准输出和标准错误，避免大输出时缓冲区写满导致子进程假死。
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill()
            $process.WaitForExit()
        } catch {
        }

        throw "命令执行超时(${TimeoutSeconds}秒): $FilePath $($ArgumentList -join ' ')"
    }

    $stdoutTask.Wait()
    $stderrTask.Wait()

    $stdoutText = $stdoutTask.Result
    $stderrText = $stderrTask.Result
    $combinedText = (@($stdoutText, $stderrText) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join [Environment]::NewLine
    $output = @($combinedText -split "`r?`n" | Where-Object { $_ -ne "" })

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output   = $output
        StdOut   = (($output -join [Environment]::NewLine).Trim())
    }
}

function Get-Devices {
    param([string]$Adb)

    # 读取 adb 当前识别到的设备列表。
    Write-Step "读取 adb 设备列表"
    $result = Invoke-External -FilePath $Adb -ArgumentList @("devices", "-l") -TimeoutSeconds 10
    if ($result.ExitCode -ne 0) {
        throw "执行 adb devices 失败: $($result.StdOut)"
    }

    $devices = @()
    foreach ($line in $result.Output) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -like "List of devices attached*") {
            continue
        }

        $parts = ($line -split "\s+") | Where-Object { $_ }
        if ($parts.Count -lt 2) {
            continue
        }

        $devices += [pscustomobject]@{
            Serial = $parts[0]
            State  = $parts[1]
            Raw    = $line.Trim()
        }
    }

    return @($devices)
}

function Invoke-AdbShell {
    param(
        [string]$Adb,
        [string]$Serial,
        [string[]]$ShellArgs
    )

    # 在指定设备上执行 adb shell 命令。
    Write-DebugLog "执行 adb shell, 设备: $Serial, 参数: $($ShellArgs -join ' ')"
    return Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $ShellArgs) -TimeoutSeconds 15
}

function Get-FocusInfo {
    param(
        [string]$Adb,
        [string]$Serial
    )

    # 读取当前前台窗口和恢复中的 Activity，方便定位当前界面。
    Write-Step "读取设备 $Serial 的前台界面信息"
    $window = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("dumpsys", "window", "windows")
    $activity = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("dumpsys", "activity", "activities")

    $focusLine = $window.Output | Where-Object { $_ -match "mCurrentFocus=" } | Select-Object -First 1
    $resumedLine = $activity.Output | Where-Object { $_ -match "mResumedActivity:" } | Select-Object -First 1

    return [pscustomobject]@{
        CurrentFocus    = [string]($focusLine | ForEach-Object { $_.Trim() })
        ResumedActivity = [string]($resumedLine | ForEach-Object { $_.Trim() })
    }
}

function Get-InterestingProcesses {
    param(
        [string]$Adb,
        [string]$Serial
    )

    # 只筛选排查时常关注的关键进程，避免 ps 输出过多。
    Write-Step "读取设备 $Serial 的关键进程"
    $psResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("ps")
    $patterns = @(
        "flysilkworm",
        "telegram",
        "instagram",
        "chrome",
        "vending",
        "gms",
        "launcher3"
    )

    $lines = @()
    foreach ($line in $psResult.Output) {
        foreach ($pattern in $patterns) {
            if ($line -match $pattern) {
                $lines += $line.Trim()
                break
            }
        }
    }

    return @($lines)
}

function Get-UserPackages {
    param(
        [string]$Adb,
        [string]$Serial
    )

    # 读取用户安装的第三方应用，方便确认目标 App 是否已安装。
    Write-Step "读取设备 $Serial 的第三方安装包"
    $pmResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("pm", "list", "packages", "-3")
    return @($pmResult.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

$resolvedAdbPath = Resolve-AdbPath -Hint $AdbPath
$resolvedLdConsolePath = Resolve-LdConsolePath -Hint $LdConsolePath -ResolvedAdbPath $resolvedAdbPath

Write-Step "校验 adb.exe 和 ldconsole.exe 路径"
Require-Path -PathValue $resolvedAdbPath -Label "adb.exe"
Require-Path -PathValue $resolvedLdConsolePath -Label "ldconsole.exe"
Write-Step "自动定位到 adb.exe: $resolvedAdbPath"
Write-Step "自动定位到 ldconsole.exe: $resolvedLdConsolePath"

Write-Step "开始巡检雷电模拟器"
$devices = @(Get-Devices -Adb $resolvedAdbPath)

Write-Step "读取雷电多开列表"
$console = Invoke-External -FilePath $resolvedLdConsolePath -ArgumentList @("list2") -TimeoutSeconds 10 -OutputEncoding ([System.Text.Encoding]::GetEncoding(936))

$inspected = @(
    foreach ($device in $devices) {
        Write-Step "开始巡检设备 $($device.Serial)"
        $focus = Get-FocusInfo -Adb $resolvedAdbPath -Serial $device.Serial
        $processes = Get-InterestingProcesses -Adb $resolvedAdbPath -Serial $device.Serial
        $packages = Get-UserPackages -Adb $resolvedAdbPath -Serial $device.Serial

        [pscustomobject]@{
            Serial             = $device.Serial
            State              = $device.State
            RawDeviceLine      = $device.Raw
            CurrentFocus       = [string]$focus.CurrentFocus
            ResumedActivity    = [string]$focus.ResumedActivity
            InterestingProcess = @($processes)
            UserPackages       = @($packages)
        }
    }
)

$report = [pscustomobject]@{
    Timestamp      = (Get-Date).ToString("o")
    AdbPath        = $resolvedAdbPath
    LdConsolePath  = $resolvedLdConsolePath
    LdConsoleList2 = $console.StdOut
    Devices        = @($inspected)
}

Write-Step "写入巡检结果到 $ReportPath"
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

Write-Host "雷电多开列表:"
Write-Host $console.StdOut
Write-Host ""

foreach ($device in $inspected) {
    Write-Host "[$($device.Serial)] 状态=$($device.State)"
    Write-Host "  当前焦点: $($device.CurrentFocus)"
    Write-Host "  恢复中的 Activity: $($device.ResumedActivity)"
    Write-Host "  关键进程:"
    if ($device.InterestingProcess.Count -eq 0) {
        Write-Host "    (无)"
    } else {
        foreach ($line in $device.InterestingProcess) {
            Write-Host "    $line"
        }
    }

    Write-Host "  第三方安装包:"
    if ($device.UserPackages.Count -eq 0) {
        Write-Host "    (无)"
    } else {
        foreach ($pkg in $device.UserPackages) {
            Write-Host "    $pkg"
        }
    }

    Write-Host ""
}

Write-Step "巡检完成"
