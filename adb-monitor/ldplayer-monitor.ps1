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
        [string[]]$ArgumentList = @()
    )

    $output = & $FilePath @ArgumentList 2>&1 | ForEach-Object { $_.ToString() }
    $exitCode = $LASTEXITCODE

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output   = @($output)
        StdOut   = (($output -join [Environment]::NewLine).Trim())
    }
}

function Get-Devices {
    param([string]$Adb)

    $result = Invoke-External -FilePath $Adb -ArgumentList @("devices", "-l")
    if ($result.ExitCode -ne 0) {
        throw "adb devices failed: $($result.StdOut)"
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
        [string[]]$Args
    )

    return Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $Args)
}

function Test-BootCompleted {
    param(
        [string]$Adb,
        [string]$Serial,
        [int]$Attempts = 3,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        $boot = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("getprop", "sys.boot_completed")
        $bootCompleted = @(
            (($boot.StdOut | Out-String) -split "\r?\n") |
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
        $check = Invoke-AdbShell -Adb $Adb -Serial $Device.Serial -Args @("pidof", $pkg)
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
    throw "adb.exe was not found. Pass -AdbPath or add adb to PATH."
}

if ($PollSeconds -lt 1) {
    throw "-PollSeconds must be greater than or equal to 1."
}

Write-Host "Using adb: $adb"

do {
    $devices = @(Get-Devices -Adb $adb)
    if ($devices.Count -eq 0) {
        Write-Host "No connected emulator/device found." -ForegroundColor Yellow
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

    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

    foreach ($item in $checks) {
        if ($item.Issues.Count -gt 0) {
            Write-Host "[WARN] $($item.Serial) $($item.Issues -join ', ')" -ForegroundColor Yellow
        } else {
            Write-Host "[OK]   $($item.Serial)" -ForegroundColor Green
        }
    }

    $hasIssues = @($checks | Where-Object { $_.Issues.Count -gt 0 }).Count -gt 0
    if ($hasIssues) {
        exit 1
    }

    if (-not $Once) {
        Start-Sleep -Seconds $PollSeconds
    }
} while (-not $Once)
