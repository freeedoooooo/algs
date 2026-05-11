param(
    [string]$ConfigPath = ".\config.txt",
    [string]$AdbPath = ""
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message" -ForegroundColor Cyan
}

function Write-WarnLog {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
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

function Get-ConfigMap {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Config file not found: $Path"
    }

    $config = @{}
    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line.StartsWith("#") -or $line.StartsWith(";")) {
            continue
        }

        $separatorIndex = $line.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $key = $line.Substring(0, $separatorIndex).Trim().ToLowerInvariant()
        $value = $line.Substring($separatorIndex + 1).Trim()
        $config[$key] = $value
    }

    return $config
}

function Get-ConfigValue {
    param(
        [hashtable]$Config,
        [string]$Key,
        [string]$DefaultValue = ""
    )

    $lookupKey = $Key.ToLowerInvariant()
    if ($Config.ContainsKey($lookupKey) -and -not [string]::IsNullOrWhiteSpace($Config[$lookupKey])) {
        return $Config[$lookupKey]
    }

    return $DefaultValue
}

function Resolve-PathFromBase {
    param(
        [string]$BaseDirectory,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $Value))
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
        StdOut   = $stdoutText.Trim()
        StdErr   = $stderrText.Trim()
    }
}

function Get-Devices {
    param([string]$Adb)

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
        $result = Invoke-External -FilePath $Adb -ArgumentList @("devices") -TimeoutSeconds 10
        if ($result.ExitCode -ne 0) {
            throw "Failed to run adb devices: $($result.StdOut) $($result.StdErr)".Trim()
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

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        [void](New-Item -Path $Path -ItemType Directory -Force)
    }
}

function Remove-StaleLogs {
    param(
        [string]$DirectoryPath,
        [int]$RetentionHours
    )

    $cutoff = (Get-Date).AddHours(-1 * $RetentionHours)
    Get-ChildItem -LiteralPath $DirectoryPath -Filter "ldplayer-monitor-*.md" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function New-RunSummary {
    param(
        [datetime]$RunTime,
        [string]$Adb,
        [object[]]$Checks,
        [string]$ErrorMessage
    )

    $healthyDevices = @()
    $unhealthyDevices = @()

    if ($Checks) {
        $healthyDevices = @($Checks | Where-Object { $_.Healthy } | ForEach-Object { $_.Serial })
        $unhealthyDevices = @($Checks | Where-Object { -not $_.Healthy })
    }

    if ($Checks.Count -eq 0 -and [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $unhealthyDevices = @(
            [pscustomobject]@{
                Serial  = "(none)"
                State   = "missing"
                Healthy = $false
                Reason  = "no_devices_found"
            }
        )
    }

    $status = "healthy"
    if ($unhealthyDevices.Count -gt 0) {
        $status = "unhealthy"
    }
    if (-not [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $status = "error"
    }

    return [pscustomobject]@{
        Timestamp        = $RunTime.ToString("o")
        AdbPath          = $Adb
        Status           = $status
        TotalCount       = $Checks.Count
        HealthyCount     = $healthyDevices.Count
        UnhealthyCount   = $unhealthyDevices.Count
        HealthyDevices   = $healthyDevices
        UnhealthyDevices = $unhealthyDevices
        ErrorMessage     = $ErrorMessage
    }
}

function Convert-SummaryToMarkdown {
    param(
        [pscustomobject]$Summary,
        [string]$ConfigFilePath
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# LDPlayer health monitor log")
    $lines.Add("")
    $lines.Add("- timestamp: $($Summary.Timestamp)")
    $lines.Add("- status: $($Summary.Status)")
    $lines.Add("- config: $ConfigFilePath")
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

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        $lines.Add("## Error")
        $lines.Add("")
        $lines.Add('```text')
        $lines.Add($Summary.ErrorMessage)
        $lines.Add('```')
        $lines.Add("")
    }

    return ($lines -join [Environment]::NewLine)
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$adbHint = $AdbPath
if ([string]::IsNullOrWhiteSpace($adbHint)) {
    $adbHint = Get-ConfigValue -Config $config -Key "adb_path"
}
if (-not [string]::IsNullOrWhiteSpace($adbHint)) {
    $adbHint = Resolve-PathFromBase -BaseDirectory $configDirectory -Value $adbHint
}

$logDirectory = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
$retentionHours = [int](Get-ConfigValue -Config $config -Key "log_retention_hours" -DefaultValue "72")
if ($retentionHours -lt 1) {
    throw "log_retention_hours must be >= 1."
}

Ensure-Directory -Path $logDirectory
$runTime = Get-Date
$logFileName = "ldplayer-monitor-{0}.md" -f $runTime.ToString("yyyyMMdd-HHmmss")
$logFilePath = Join-Path $logDirectory $logFileName

$resolvedAdb = ""
$checks = @()
$errorMessage = ""
$exitCode = 0

try {
    Write-Step "Load config from $configFullPath"
    $resolvedAdb = Resolve-AdbPath -Hint $adbHint
    if (-not $resolvedAdb) {
        throw "adb.exe not found. Configure adb_path in config.txt or add adb to PATH."
    }

    Write-Step "Use adb at $resolvedAdb"
    $devices = @(Get-Devices -Adb $resolvedAdb)
    foreach ($device in $devices) {
        $checks += Test-DeviceHealth -Adb $resolvedAdb -Device $device
    }

    if (@($checks | Where-Object { -not $_.Healthy }).Count -gt 0 -or $checks.Count -eq 0) {
        $exitCode = 1
    }
} catch {
    $errorMessage = $_.Exception.Message
    $exitCode = 1
}

$summary = New-RunSummary -RunTime $runTime -Adb $resolvedAdb -Checks $checks -ErrorMessage $errorMessage
$markdown = Convert-SummaryToMarkdown -Summary $summary -ConfigFilePath $configFullPath
$markdown | Set-Content -LiteralPath $logFilePath -Encoding UTF8
Remove-StaleLogs -DirectoryPath $logDirectory -RetentionHours $retentionHours

if ($summary.Status -eq "healthy") {
    Write-Host "[RESULT] healthy emulators: $($summary.HealthyCount) / $($summary.TotalCount)" -ForegroundColor Green
} else {
    Write-WarnLog "healthy emulators: $($summary.HealthyCount) / $($summary.TotalCount)"
}

foreach ($item in $summary.UnhealthyDevices) {
    Write-WarnLog "$($item.Serial) $($item.Reason)"
}

if (-not [string]::IsNullOrWhiteSpace($summary.ErrorMessage)) {
    Write-WarnLog $summary.ErrorMessage
}

Write-Host "[LOG] $logFilePath"
exit $exitCode
