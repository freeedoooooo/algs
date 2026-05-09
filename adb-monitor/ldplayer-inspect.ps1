param(
    [string]$AdbPath = "D:\leidian\LDPlayer9\adb.exe",
    [string]$LdConsolePath = "D:\leidian\LDPlayer9\ldconsole.exe",
    [string]$ReportPath = ".\ldplayer-inspect.json"
)

$ErrorActionPreference = "Stop"

function Require-Path {
    param(
        [string]$PathValue,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "$Label was not found: $PathValue"
    }
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

function Get-FocusInfo {
    param(
        [string]$Adb,
        [string]$Serial
    )

    $window = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("dumpsys", "window", "windows")
    $activity = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("dumpsys", "activity", "activities")

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

    $psResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("ps")
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

    $pmResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("pm", "list", "packages", "-3")
    return @($pmResult.Output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

Require-Path -PathValue $AdbPath -Label "adb.exe"
Require-Path -PathValue $LdConsolePath -Label "ldconsole.exe"

$devices = @(Get-Devices -Adb $AdbPath)
$console = Invoke-External -FilePath $LdConsolePath -ArgumentList @("list2")

$inspected = @(
    foreach ($device in $devices) {
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

$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

Write-Host "LDPlayer instances:"
Write-Host $console.StdOut
Write-Host ""

foreach ($device in $inspected) {
    Write-Host "[$($device.Serial)] state=$($device.State)"
    Write-Host "  current focus: $($device.CurrentFocus)"
    Write-Host "  resumed activity: $($device.ResumedActivity)"
    Write-Host "  interesting processes:"
    if ($device.InterestingProcess.Count -eq 0) {
        Write-Host "    (none)"
    } else {
        foreach ($line in $device.InterestingProcess) {
            Write-Host "    $line"
        }
    }

    Write-Host "  third-party packages:"
    if ($device.UserPackages.Count -eq 0) {
        Write-Host "    (none)"
    } else {
        foreach ($pkg in $device.UserPackages) {
            Write-Host "    $pkg"
        }
    }

    Write-Host ""
}
