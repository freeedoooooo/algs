param(
    [string]$AdbPath = "",
    [int]$PollSeconds = 30,
    [switch]$Once,
    [string]$ReportPath = ".\ldplayer-monitor.md"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

function Write-DebugLog {
    param([string]$Message)
    Write-Host "[LOG] $Message" -ForegroundColor DarkGray
}

function ConvertTo-ArgumentString {
    param([string[]]$ArgumentList)

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

    Write-DebugLog "Execute: $FilePath $($ArgumentList -join ' ')"

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

        throw "Command timed out (${TimeoutSeconds}s): $FilePath $($ArgumentList -join ' ')"
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

    Write-Step "Read adb device list"
    $deviceArgs = @("devices", "-l")
    $result = Invoke-External -FilePath $Adb -ArgumentList $deviceArgs -TimeoutSeconds 10
    $fallbackReasons = New-Object System.Collections.Generic.List[string]

    if ($result.ExitCode -ne 0) {
        $fallbackReasons.Add("exit_code=$($result.ExitCode)")
    }

    if ($result.StdOut -match "^Usage:\s+adb devices \[-l\]") {
        $fallbackReasons.Add("adb does not accept -l")
    }

    $nonHeaderLines = @(
        $result.Output |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_) -and
                $_ -notlike "List of devices attached*"
            }
    )

    if ($nonHeaderLines.Count -eq 0) {
        $fallbackReasons.Add("devices -l returned no device lines")
    }

    if ($fallbackReasons.Count -gt 0) {
        Write-DebugLog "Fallback to adb devices because: $($fallbackReasons -join '; ')"
        $deviceArgs = @("devices")
        $result = Invoke-External -FilePath $Adb -ArgumentList $deviceArgs -TimeoutSeconds 10
        if ($result.ExitCode -ne 0) {
            throw "Failed to run adb devices: $($result.StdOut)"
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

    Write-DebugLog "adb shell: $Serial $($ShellArgs -join ' ')"
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
        Write-Step "Check boot completion for $Serial, attempt $attempt"
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

function Test-DeviceHealth {
    param(
        [string]$Adb,
        [object]$Device
    )

    Write-Step "Check device $($Device.Serial)"

    if ($Device.State -ne "device") {
        return [pscustomobject]@{
            Serial  = $Device.Serial
            State   = $Device.State
            Healthy = $false
            Reason  = "state=$($Device.State)"
        }
    }

    $bootCompleted = Test-BootCompleted -Adb $Adb -Serial $Device.Serial
    if (-not $bootCompleted) {
        return [pscustomobject]@{
            Serial  = $Device.Serial
            State   = $Device.State
            Healthy = $false
            Reason  = "boot_not_completed"
        }
    }

    return [pscustomobject]@{
        Serial  = $Device.Serial
        State   = $Device.State
        Healthy = $true
        Reason  = ""
    }
}

function Convert-MonitorReportToMarkdown {
    param(
        [pscustomobject]$Summary,
        [int]$PollSeconds,
        [bool]$OnceMode
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $modeText = if ($OnceMode) { "once" } else { "polling" }

    $lines.Add("# LDPlayer health count report")
    $lines.Add("")
    $lines.Add("- timestamp: $($Summary.Timestamp)")
    $lines.Add("- mode: $modeText")
    $lines.Add("- poll seconds: $PollSeconds")
    $lines.Add("- adb path: $($Summary.AdbPath)")
    $lines.Add("- connected devices: $($Summary.TotalCount)")
    $lines.Add("- healthy devices: $($Summary.HealthyCount)")
    $lines.Add("- unhealthy devices: $($Summary.UnhealthyCount)")
    $lines.Add("")

    if ($Summary.HealthyDevices.Count -gt 0) {
        $lines.Add("## Healthy devices")
        $lines.Add("")
        foreach ($device in $Summary.HealthyDevices) {
            $lines.Add("- $device")
        }
        $lines.Add("")
    }

    if ($Summary.UnhealthyDevices.Count -gt 0) {
        $lines.Add("## Unhealthy devices")
        $lines.Add("")
        $lines.Add("| device | reason |")
        $lines.Add("| --- | --- |")
        foreach ($device in $Summary.UnhealthyDevices) {
            $lines.Add("| $($device.Serial) | $($device.Reason) |")
        }
        $lines.Add("")
    }

    if ($Summary.TotalCount -eq 0) {
        $lines.Add("## Current result")
        $lines.Add("")
        $lines.Add("- no connected emulator or device found")
        $lines.Add("")
    }

    return (($lines.ToArray()) -join [Environment]::NewLine)
}

$adb = Resolve-AdbPath -Hint $AdbPath
if (-not $adb) {
    throw "adb.exe not found. Pass -AdbPath or add adb to PATH."
}

if ($PollSeconds -lt 1) {
    throw "-PollSeconds must be >= 1."
}

Write-Step "Resolved adb.exe: $adb"

do {
    Write-Step "Start monitoring round"
    $devices = @(Get-Devices -Adb $adb)
    $checks = @(
        foreach ($device in $devices) {
            Test-DeviceHealth -Adb $adb -Device $device
        }
    )

    $healthyDevices = @($checks | Where-Object { $_.Healthy })
    $unhealthyDevices = @($checks | Where-Object { -not $_.Healthy })
    if ($checks.Count -eq 0) {
        $unhealthyDevices = @(
            [pscustomobject]@{
                Serial  = "(none)"
                State   = "missing"
                Healthy = $false
                Reason  = "no_devices_found"
            }
        )
    }

    $summary = [pscustomobject]@{
        Timestamp       = (Get-Date).ToString("o")
        AdbPath         = $adb
        TotalCount      = $checks.Count
        HealthyCount    = $healthyDevices.Count
        UnhealthyCount   = $unhealthyDevices.Count
        HealthyDevices  = @($healthyDevices | ForEach-Object { $_.Serial })
        UnhealthyDevices = @($unhealthyDevices)
    }

    Write-Step "Write report to $ReportPath"
    $markdownReport = Convert-MonitorReportToMarkdown -Summary $summary -PollSeconds $PollSeconds -OnceMode ([bool]$Once)
    $markdownReport | Set-Content -LiteralPath $ReportPath -Encoding UTF8

    Write-Host "[RESULT] healthy emulators: $($summary.HealthyCount) / $($summary.TotalCount)" -ForegroundColor Green
    foreach ($item in $unhealthyDevices) {
        Write-Host "[WARN] $($item.Serial) $($item.Reason)" -ForegroundColor Yellow
    }

    if ($unhealthyDevices.Count -gt 0) {
        Write-Step "Unhealthy devices found; exiting with code 1"
        exit 1
    }

    if (-not $Once) {
        Write-Step "Round complete; sleeping $PollSeconds seconds"
        Start-Sleep -Seconds $PollSeconds
    }
} while (-not $Once)

Write-Step "Monitoring complete"
