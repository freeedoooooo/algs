param(
    [string]$AdbPath = "D:\leidian\LDPlayer9\adb.exe",
    [string]$LdConsolePath = "D:\leidian\LDPlayer9\ldconsole.exe",
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

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "未找到 ${Label}: $PathValue"
    }
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutSeconds = 20
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

Write-Step "校验 adb.exe 和 ldconsole.exe 路径"
Require-Path -PathValue $AdbPath -Label "adb.exe"
Require-Path -PathValue $LdConsolePath -Label "ldconsole.exe"

Write-Step "开始巡检雷电模拟器"
$devices = @(Get-Devices -Adb $AdbPath)

Write-Step "读取雷电多开列表"
$console = Invoke-External -FilePath $LdConsolePath -ArgumentList @("list2") -TimeoutSeconds 10

$inspected = @(
    foreach ($device in $devices) {
        Write-Step "开始巡检设备 $($device.Serial)"
        $focus = Get-FocusInfo -Adb $AdbPath -Serial $device.Serial
        $processes = Get-InterestingProcesses -Adb $AdbPath -Serial $device.Serial
        $packages = Get-UserPackages -Adb $AdbPath -Serial $device.Serial

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
    AdbPath        = $AdbPath
    LdConsolePath  = $LdConsolePath
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
