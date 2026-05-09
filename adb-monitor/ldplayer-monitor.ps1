param(
    [string]$AdbPath = "",
    [int]$PollSeconds = 30,
    [switch]$Once,
    [string[]]$Packages = @(),
    [string]$ReportPath = ".\ldplayer-monitor.md"
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

function Resolve-AdbPath {
    param([string]$Hint)

    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

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

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($dir in @($dirs | Select-Object -Unique)) {
        $candidates.Add((Join-Path $dir "adb.exe"))
    }

    $candidates.Add((Join-Path $env:ProgramFiles "Android\platform-tools\adb.exe"))
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Android\platform-tools\adb.exe"))
    }

    foreach ($candidate in $candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command adb -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return $null
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutSeconds = 20
    )

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

    Write-DebugLog "执行 adb shell, 设备: $Serial, 参数: $($ShellArgs -join ' ')"
    return Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $ShellArgs) -TimeoutSeconds 15
}

function Test-BootCompleted {
    param(
        [string]$Adb,
        [string]$Serial,
        [int]$Attempts = 3,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        Write-Step "检查设备 $Serial 的启动完成状态，第 $attempt 次尝试"
        $boot = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("getprop", "sys.boot_completed")
        $bootCompleted = @(
            (($boot.StdOut | Out-String) -split "`r?`n") |
                Where-Object { $_.Trim() -eq "1" }
        ).Count -gt 0

        if ($bootCompleted) {
            return $true
        }

        if ($attempt -lt $Attempts) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    return $false
}

function Test-Device {
    param(
        [string]$Adb,
        [object]$Device,
        [string[]]$Packages
    )

    Write-Step "开始检查设备 $($Device.Serial)"
    $issues = New-Object System.Collections.Generic.List[string]

    if ($Device.State -ne "device") {
        $issues.Add("state=$($Device.State)")
        return [pscustomobject]@{
            Serial = $Device.Serial
            State  = $Device.State
            Booted = $false
            Apps   = @()
            Issues = [string[]]$issues
        }
    }

    $bootCompleted = Test-BootCompleted -Adb $Adb -Serial $Device.Serial
    if (-not $bootCompleted) {
        $issues.Add("boot_not_completed")
    }

    $apps = @()
    foreach ($pkg in $Packages) {
        Write-Step "检查设备 $($Device.Serial) 上的应用是否运行: $pkg"
        $check = Invoke-AdbShell -Adb $Adb -Serial $Device.Serial -ShellArgs @("pidof", $pkg)
        $running = -not [string]::IsNullOrWhiteSpace($check.StdOut)
        if (-not $running) {
            $issues.Add("app_missing:$pkg")
        }

        $apps += [pscustomobject]@{
            Package = $pkg
            Running = $running
            Pid     = $check.StdOut
        }
    }

    return [pscustomobject]@{
        Serial = $Device.Serial
        State  = $Device.State
        Booted = $bootCompleted
        Apps   = @($apps)
        Issues = [string[]]$issues
    }
}

function Convert-MonitorReportToMarkdown {
    param(
        [pscustomobject]$Summary,
        [int]$PollSeconds,
        [bool]$OnceMode,
        [string[]]$Packages
    )

    $jsonText = $Summary | ConvertTo-Json -Depth 6
    $lines = New-Object System.Collections.Generic.List[string]
    $modeText = if ($OnceMode) { "单次执行" } else { "持续轮询" }
    $packageText = if ($Packages -and $Packages.Count -gt 0) { $Packages -join ", " } else { "未指定" }
    $hasIssues = @($Summary.Devices | Where-Object { $_.Issues.Count -gt 0 }).Count -gt 0
    $overallStatus = if ($hasIssues) { "有异常" } else { "正常" }

    $lines.Add("# 雷电模拟器监控报告")
    $lines.Add("")
    $lines.Add("- 生成时间: $($Summary.Timestamp)")
    $lines.Add("- 执行模式: $modeText")
    $lines.Add("- 轮询间隔(秒): $PollSeconds")
    $lines.Add("- adb 路径: $($Summary.AdbPath)")
    $lines.Add("- 检查包名: $packageText")
    $lines.Add("- 总体状态: $overallStatus")
    $lines.Add("")

    $lines.Add("## 设备概览")
    $lines.Add("")
    if (-not $Summary.Devices -or $Summary.Devices.Count -eq 0) {
        $lines.Add("- 未发现已连接的模拟器或设备")
    } else {
        $lines.Add("| 设备 | 连接状态 | 启动完成 | 异常 |")
        $lines.Add("| --- | --- | --- | --- |")
        foreach ($device in $Summary.Devices) {
            $bootedText = if ($device.Booted) { "是" } else { "否" }
            $issuesText = if ($device.Issues.Count -gt 0) { $device.Issues -join ", " } else { "无" }
            $lines.Add("| $($device.Serial) | $($device.State) | $bootedText | $issuesText |")
        }
    }
    $lines.Add("")

    foreach ($device in $Summary.Devices) {
        $lines.Add("## $($device.Serial)")
        $lines.Add("")
        $lines.Add("- 连接状态: $($device.State)")
        $lines.Add("- 启动完成: $(if ($device.Booted) { '是' } else { '否' })")
        $lines.Add("- 异常: $(if ($device.Issues.Count -gt 0) { $device.Issues -join ', ' } else { '无' })")
        $lines.Add("")
        $lines.Add("### 应用检查")
        if (-not $device.Apps -or $device.Apps.Count -eq 0) {
            $lines.Add("- 本次未指定需要检查的应用包名")
        } else {
            $lines.Add("")
            $lines.Add("| 包名 | 是否运行 | PID |")
            $lines.Add("| --- | --- | --- |")
            foreach ($app in $device.Apps) {
                $runningText = if ($app.Running) { "是" } else { "否" }
                $pidText = if ([string]::IsNullOrWhiteSpace($app.Pid)) { "-" } else { $app.Pid }
                $lines.Add("| $($app.Package) | $runningText | $pidText |")
            }
        }
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

$adb = Resolve-AdbPath -Hint $AdbPath
if (-not $adb) {
    throw "未找到 adb.exe，请通过 -AdbPath 传入，或者先把 adb 加入 PATH。"
}

if ($PollSeconds -lt 1) {
    throw "-PollSeconds 必须大于等于 1。"
}

Write-Step "自动定位到 adb.exe: $adb"

do {
    Write-Step "开始新一轮监控"
    $devices = @(Get-Devices -Adb $adb)
    if ($devices.Count -eq 0) {
        Write-Host "未发现已连接的模拟器或设备。" -ForegroundColor Yellow
    }

    $checks = @(
        foreach ($device in $devices) {
            Test-Device -Adb $adb -Device $device -Packages $Packages
        }
    )

    $summary = [pscustomobject]@{
        Timestamp = (Get-Date).ToString("o")
        AdbPath   = $adb
        Devices   = @($checks)
    }

    Write-Step "写入监控结果到 $ReportPath"
    $markdownReport = Convert-MonitorReportToMarkdown -Summary $summary -PollSeconds $PollSeconds -OnceMode ([bool]$Once) -Packages $Packages
    $markdownReport | Set-Content -LiteralPath $ReportPath -Encoding UTF8

    foreach ($item in $checks) {
        if ($item.Issues.Count -gt 0) {
            Write-Host "[告警] $($item.Serial) $($item.Issues -join ', ')" -ForegroundColor Yellow
        } else {
            Write-Host "[正常] $($item.Serial)" -ForegroundColor Green
        }
    }

    $hasIssues = @($checks | Where-Object { $_.Issues.Count -gt 0 }).Count -gt 0
    if ($hasIssues) {
        Write-Step "本轮监控发现异常，脚本将以退出码 1 结束"
        exit 1
    }

    if (-not $Once) {
        Write-Step "本轮监控完成，等待 $PollSeconds 秒后进入下一轮"
        Start-Sleep -Seconds $PollSeconds
    }
} while (-not $Once)

Write-Step "监控执行完成"
