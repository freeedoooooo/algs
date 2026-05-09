param(
    [string]$AdbPath = "",
    [int]$PollSeconds = 30,
    [switch]$Once,
    [string[]]$Packages = @(),
    [string]$ReportPath = ".\ldplayer-monitor.json"
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

function Resolve-AdbPath {
    param([string]$Hint)

    # 优先使用手工传入的 adb 路径，其次尝试常见安装位置和 PATH。
    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    $candidates = @(
        "D:\leidian\LDPlayer9\adb.exe",
        (Join-Path $env:ProgramFiles "Android\platform-tools\adb.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Android\platform-tools\adb.exe"),
        "C:\Program Files\LDPlayer\adb.exe",
        "C:\Program Files\LDPlayer\LDPlayer9\adb.exe",
        "C:\Program Files\dnplayerext2\adb.exe"
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
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

    # 对外部命令统一增加超时保护，避免 adb 无响应时脚本一直挂住。
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

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill()
            $process.WaitForExit()
        } catch {
        }

        throw "命令执行超时(${TimeoutSeconds}秒): $FilePath $($ArgumentList -join ' ')"
    }

    $stdoutText = $process.StandardOutput.ReadToEnd()
    $stderrText = $process.StandardError.ReadToEnd()
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

    # 在指定模拟器上执行 adb shell 子命令。
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

    # 有些模拟器刚连上时第一次读取 boot 属性不稳定，这里做短重试。
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

    # 针对单台设备执行完整检查：设备状态、系统启动状态、目标 App 进程状态。
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

$adb = Resolve-AdbPath -Hint $AdbPath
if (-not $adb) {
    throw "未找到 adb.exe，请通过 -AdbPath 传入，或者先把 adb 加入 PATH。"
}

if ($PollSeconds -lt 1) {
    throw "-PollSeconds 必须大于等于 1。"
}

Write-Step "当前使用的 adb 路径: $adb"

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
    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

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
