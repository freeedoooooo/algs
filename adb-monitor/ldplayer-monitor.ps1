param(
    [string]$AdbPath = "",
    [int]$PollSeconds = 30,
    [switch]$Once,
    [string[]]$Packages = @(),
    [string]$ReportPath = ".\ldplayer-monitor.json"
)

$ErrorActionPreference = "Stop"

function Resolve-AdbPath {
    param([string]$Hint)

    # 先优先使用用户手动传入的 adb 路径。
    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    # 再按常见安装位置逐个尝试。
    $candidates = @(
        (Join-Path $env:ProgramFiles "Android\platform-tools\adb.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Android\platform-tools\adb.exe"),
        "C:\Program Files\LDPlayer\adb.exe",
        "C:\Program Files\LDPlayer\LDPlayer9\adb.exe",
        "C:\Program Files\dnplayerext2\adb.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return $null
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [int]$TimeoutSeconds = 20
    )

    # 直接调用外部程序，保持兼容性和简单性。
    $output = & $FilePath @ArgumentList 2>&1 | ForEach-Object { $_.ToString() }
    $exitCode = $LASTEXITCODE

    $stdout = @()
    $stderr = @()
    foreach ($line in $output) {
        if ($line -like "*error:*" -or $line -like "*failed:*") {
            $stderr += $line
        } else {
            $stdout += $line
        }
    }

    [pscustomobject]@{
        ExitCode = $exitCode
        StdOut   = (($stdout -join [Environment]::NewLine).Trim())
        StdErr   = (($stderr -join [Environment]::NewLine).Trim())
    }
}

function Get-Devices {
    param([string]$Adb)

    # 读取已连接的模拟器列表。
    $result = Invoke-External -FilePath $Adb -ArgumentList @("devices", "-l") -TimeoutSeconds 15
    if ($result.ExitCode -ne 0) {
        throw "执行 adb devices 失败：$($result.StdErr)"
    }

    $devices = @()
    foreach ($line in ($result.StdOut -split "`r?`n")) {
        if (-not $line -or $line -like "List of devices attached*") {
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

    return $devices
}

function Invoke-Shell {
    param(
        [string]$Adb,
        [string]$Serial,
        [string[]]$Args,
        [int]$TimeoutSeconds = 20
    )

    # 在指定模拟器里执行 shell 命令。
    Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $Args) -TimeoutSeconds $TimeoutSeconds
}

function Test-Device {
    param(
        [string]$Adb,
        [object]$Device,
        [string[]]$Packages
    )

    # 逐台检查模拟器状态。
    $issues = New-Object System.Collections.Generic.List[string]

    if ($Device.State -ne "device") {
        $issues.Add("state=$($Device.State)")
        return [pscustomobject]@{
            Serial = $Device.Serial
            State  = $Device.State
            Booted = $false
            Apps   = @()
            Issues = $issues
        }
    }

    # 读取系统启动完成状态。
    $boot = Invoke-Shell -Adb $Adb -Serial $Device.Serial -Args @("getprop", "sys.boot_completed") -TimeoutSeconds 15
    $bootCompleted = ($boot.StdOut -match "1")
    if (-not $bootCompleted) {
        $issues.Add("boot_not_completed")
    }

    # 选填：检查指定 App 是否仍在运行。
    $apps = @()
    foreach ($pkg in $Packages) {
        $check = Invoke-Shell -Adb $Adb -Serial $Device.Serial -Args @("pidof", $pkg) -TimeoutSeconds 15
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
        Apps   = $apps
        Issues = $issues
    }
}

$adb = Resolve-AdbPath -Hint $AdbPath
if (-not $adb) {
    throw "未找到 adb.exe，请传入 -AdbPath，或者把 adb 加入 PATH。"
}

Write-Host "正在使用 adb：$adb"

do {
    $devices = Get-Devices -Adb $adb
    if (-not $devices.Count) {
        Write-Host "没有找到已连接的模拟器。"
    }

    $checks = foreach ($device in $devices) {
        Test-Device -Adb $adb -Device $device -Packages $Packages
    }

    $summary = [pscustomobject]@{
        Timestamp = (Get-Date).ToString("o")
        AdbPath   = $adb
        Devices   = $checks
    }

    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

    foreach ($item in $checks) {
        if ($item.Issues.Count -gt 0) {
            Write-Host "[警告] $($item.Serial) $($item.Issues -join ', ')" -ForegroundColor Yellow
        } else {
            Write-Host "[正常] $($item.Serial)" -ForegroundColor Green
        }
    }

    $bad = @($checks | Where-Object { $_.Issues.Count -gt 0 })
    if ($bad.Count -gt 0) {
        exit 1
    }

    if (-not $Once) {
        Start-Sleep -Seconds $PollSeconds
    }
} while (-not $Once)
