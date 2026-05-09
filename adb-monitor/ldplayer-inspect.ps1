param(
    [string]$AdbPath = "",
    [string]$LdConsolePath = "",
    [string]$ReportPath = ".\ldplayer-inspect.md"
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

    Write-Step "读取 adb 设备列表"
    $deviceArgs = @("devices", "-l")
    $result = Invoke-External -FilePath $Adb -ArgumentList $deviceArgs -TimeoutSeconds 10
    $fallbackReasons = New-Object System.Collections.Generic.List[string]

    if ($result.ExitCode -ne 0) {
        $fallbackReasons.Add("退出码=$($result.ExitCode)")
    }

    if ($result.StdOut -match "^Usage:\s+adb devices \[-l\]") {
        $fallbackReasons.Add("当前 adb 不接受 -l 参数")
    }

    $nonHeaderLines = @(
        $result.Output |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_) -and
                $_ -notlike "List of devices attached*"
            }
    )

    if ($nonHeaderLines.Count -eq 0) {
        $fallbackReasons.Add("devices -l 未返回任何设备行")
    }

    if ($fallbackReasons.Count -gt 0) {
        Write-DebugLog "adb devices -l 不可用或结果为空，原因: $($fallbackReasons -join '；')"
        Write-DebugLog "回退执行 adb devices"
        $deviceArgs = @("devices")
        $result = Invoke-External -FilePath $Adb -ArgumentList $deviceArgs -TimeoutSeconds 10
        if ($result.ExitCode -ne 0) {
            throw "执行 adb devices 失败: $($result.StdOut)"
        }
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
            Source = ($deviceArgs -join " ")
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

    Write-DebugLog "执行 adb shell, 设备: $Serial, 参数: $($ShellArgs -join ' ')"
    return Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $ShellArgs) -TimeoutSeconds 15
}

function Get-FocusInfo {
    param(
        [string]$Adb,
        [string]$Serial
    )

    Write-Step "读取设备 $Serial 的前台界面信息"
    $focusLine = $null
    $resumedLine = $null

    try {
        $focusResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("sh", "-c", "dumpsys window windows | grep mCurrentFocus")
        $focusLine = $focusResult.Output | Select-Object -First 1
    } catch {
        Write-DebugLog "轻量读取当前焦点失败，回退到完整 dumpsys window。"
    }

    if (-not $focusLine) {
        $window = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("dumpsys", "window", "windows")
        $focusLine = $window.Output | Where-Object { $_ -match "mCurrentFocus=" } | Select-Object -First 1
    }

    try {
        $resumedResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("sh", "-c", "dumpsys activity activities | grep mResumedActivity")
        $resumedLine = $resumedResult.Output | Select-Object -First 1
    } catch {
        Write-DebugLog "轻量读取恢复中的 Activity 失败，回退到完整 dumpsys activity。"
    }

    if (-not $resumedLine) {
        $activity = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("dumpsys", "activity", "activities")
        $resumedLine = $activity.Output | Where-Object { $_ -match "mResumedActivity:" } | Select-Object -First 1
    }

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

    Write-Step "读取设备 $Serial 的第三方安装包"
    $pmResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("pm", "list", "packages", "-3")
    return @($pmResult.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Convert-LdConsoleList2ToObjects {
    param([string]$Text)

    $items = @()
    foreach ($line in ($Text -split "`r?`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line.Split(",")
        if ($parts.Count -lt 10) {
            $items += [pscustomobject]@{
                Raw = $line.Trim()
            }
            continue
        }

        $items += [pscustomobject]@{
            Index            = $parts[0]
            Name             = $parts[1]
            TopWindowHandle  = $parts[2]
            BindWindowHandle = $parts[3]
            AndroidStarted   = ($parts[4] -eq "1")
            PlayerPid        = $parts[5]
            VBoxPid          = $parts[6]
            Width            = $parts[7]
            Height           = $parts[8]
            Dpi              = $parts[9]
            Raw              = $line.Trim()
        }
    }

    return @($items)
}

function Add-MarkdownBulletSection {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Title,
        [string[]]$Items,
        [string]$EmptyText = "无"
    )

    $Lines.Add("### $Title")
    if (-not $Items -or $Items.Count -eq 0) {
        $Lines.Add("- $EmptyText")
        return
    }

    foreach ($item in $Items) {
        $Lines.Add("- $item")
    }
}

function Convert-InspectReportToMarkdown {
    param(
        [pscustomobject]$Report,
        [object[]]$LdConsoleItems
    )

    $jsonText = $Report | ConvertTo-Json -Depth 6
    $lines = New-Object System.Collections.Generic.List[string]

    $lines.Add("# 雷电模拟器巡检报告")
    $lines.Add("")
    $lines.Add("- 生成时间: $($Report.Timestamp)")
    $lines.Add("- adb 路径: $($Report.AdbPath)")
    $lines.Add("- ldconsole 路径: $($Report.LdConsolePath)")
    $lines.Add("- 设备数量: $($Report.Devices.Count)")
    $lines.Add("")

    $lines.Add("## 雷电多开列表")
    $lines.Add("")
    if (-not $LdConsoleItems -or $LdConsoleItems.Count -eq 0) {
        $lines.Add("- 未读取到实例列表")
    } else {
        $lines.Add("| 索引 | 名称 | Android已启动 | 主进程PID | VBoxPID | 分辨率 | DPI |")
        $lines.Add("| --- | --- | --- | --- | --- | --- | --- |")
        foreach ($item in $LdConsoleItems) {
            if ($item.PSObject.Properties.Name -contains "Index") {
                $started = if ($item.AndroidStarted) { "是" } else { "否" }
                $resolution = "$($item.Width)x$($item.Height)"
                $lines.Add("| $($item.Index) | $($item.Name) | $started | $($item.PlayerPid) | $($item.VBoxPid) | $resolution | $($item.Dpi) |")
            } else {
                $lines.Add("- 原始数据: $($item.Raw)")
            }
        }
    }
    $lines.Add("")

    $lines.Add("## 设备详情")
    $lines.Add("")
    foreach ($device in $Report.Devices) {
        $lines.Add("### $($device.Serial)")
        $lines.Add("")
        $lines.Add("- 状态: $($device.State)")
        $lines.Add("- 当前焦点: $($device.CurrentFocus)")
        $lines.Add("- 恢复中的 Activity: $($device.ResumedActivity)")
        $lines.Add("")
        Add-MarkdownBulletSection -Lines $lines -Title "关键进程" -Items $device.InterestingProcess
        $lines.Add("")
        Add-MarkdownBulletSection -Lines $lines -Title "第三方安装包" -Items $device.UserPackages
        $lines.Add("")
    }

    $lines.Add("## 附注：原始 JSON")
    $lines.Add("")
    $lines.Add('```json')
    foreach ($line in ($jsonText -split "`r?`n")) {
        $lines.Add($line)
    }
    $lines.Add('```')

    return (($lines.ToArray()) -join [Environment]::NewLine)
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
$ldConsoleItems = Convert-LdConsoleList2ToObjects -Text $console.StdOut
$markdownReport = Convert-InspectReportToMarkdown -Report $report -LdConsoleItems $ldConsoleItems
$markdownReport | Set-Content -LiteralPath $ReportPath -Encoding UTF8

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
