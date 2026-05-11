param(
    [string]$ConfigPath = "..\monitor.config",
    [string]$AdbPath = "",
    [string]$LdPlayerPath = ""
)

$ErrorActionPreference = "Stop"
$script:MonitorLogFilePath = ""

function Write-Step {
    param([string]$Message)
    Write-MonitorLine -Message "[STEP] $Message" -ForegroundColor Cyan
}

function Write-WarnLog {
    param([string]$Message)
    Write-MonitorLine -Message "[WARN] $Message" -ForegroundColor Yellow
}

function Write-MonitorLine {
    param(
        [AllowEmptyString()][string]$Message,
        [string]$ForegroundColor = ""
    )

    if ([string]::IsNullOrWhiteSpace($Message)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($ForegroundColor)) {
        Write-Host $Message
    } else {
        Write-Host $Message -ForegroundColor $ForegroundColor
    }

    if (-not [string]::IsNullOrWhiteSpace($script:MonitorLogFilePath)) {
        Add-Content -LiteralPath $script:MonitorLogFilePath -Value $Message -Encoding UTF8
    }
}

function Write-MonitorBlankLine {
    Write-Host ""

    if (-not [string]::IsNullOrWhiteSpace($script:MonitorLogFilePath)) {
        Add-Content -LiteralPath $script:MonitorLogFilePath -Value "" -Encoding UTF8
    }
}

function Get-LogBaseName {
    param([string]$FileName)

    $name = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    if ([string]::IsNullOrWhiteSpace($name)) {
        return "monitor"
    }

    return $name
}

function Get-DatedLogFilePath {
    param(
        [string]$DirectoryPath,
        [string]$BaseFileName,
        [datetime]$Date = (Get-Date)
    )

    $baseName = Get-LogBaseName -FileName $BaseFileName
    $dateSuffix = $Date.ToString("yyyyMMdd")
    return Join-Path $DirectoryPath ("{0}-{1}.log" -f $baseName, $dateSuffix)
}

function Get-MonitorLineColor {
    param([string]$Message)

    if ($Message -match '\[ERROR\]') {
        return "Red"
    }
    if ($Message -match '\[WARN\]') {
        return "Yellow"
    }
    if ($Message -match '\[STEP\]') {
        return "Cyan"
    }

    return ""
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

function Get-ConfigList {
    param(
        [hashtable]$Config,
        [string]$Key
    )

    $rawValue = Get-ConfigValue -Config $Config -Key $Key
    if ([string]::IsNullOrWhiteSpace($rawValue)) {
        return @()
    }

    return @(
        $rawValue.Split(";") |
            ForEach-Object { $_.Trim() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
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

function Get-CommonLdPlayerDirs {
    return @($script:CommonLdPlayerDirs)
}

function Test-LDPlayerInstallDir {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    return (Test-Path -LiteralPath (Join-Path $Path "adb.exe"))
}

function Get-LDPlayerInstallDirsFromRegistry {
    $roots = @($script:RegistryRoots)
    $valueNames = @($script:RegistryValueNames)
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

function Resolve-LDPlayerPath {
    param(
        [string]$Hint,
        [string]$ResolvedAdbPath
    )

    if (Test-LDPlayerInstallDir -Path $Hint) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    if ($ResolvedAdbPath -and (Test-Path -LiteralPath $ResolvedAdbPath)) {
        $adbDir = Split-Path -Parent $ResolvedAdbPath
        if (Test-LDPlayerInstallDir -Path $adbDir) {
            return $adbDir
        }
    }

    $dirs = New-Object System.Collections.Generic.List[string]
    foreach ($dir in Get-CommonLdPlayerDirs) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add((Resolve-Path -LiteralPath $dir).Path)
        }
    }
    foreach ($dir in Get-LDPlayerInstallDirsFromRegistry) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add($dir)
        }
    }

    $firstDir = @($dirs | Select-Object -Unique | Select-Object -First 1)
    if ($firstDir.Count -gt 0) {
        return $firstDir[0]
    }

    return ""
}

function Resolve-AdbPath {
    param([string]$Hint)

    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    $dirs = New-Object System.Collections.Generic.List[string]
    foreach ($dir in Get-CommonLdPlayerDirs) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add((Resolve-Path -LiteralPath $dir).Path)
        }
    }
    foreach ($dir in Get-LDPlayerInstallDirsFromRegistry) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add($dir)
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
        [int]$TimeoutSeconds = $script:ExternalCommandTimeoutSeconds
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
    $result = Invoke-External -FilePath $Adb -ArgumentList $deviceArgs -TimeoutSeconds $script:AdbDevicesTimeoutSeconds
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
        $result = Invoke-External -FilePath $Adb -ArgumentList @("devices") -TimeoutSeconds $script:AdbDevicesTimeoutSeconds
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

    return Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $ShellArgs) -TimeoutSeconds $script:AdbShellTimeoutSeconds
}

function Test-BootCompleted {
    param(
        [string]$Adb,
        [string]$Serial
    )

    $attempts = $script:BootCheckAttempts
    $delaySeconds = $script:BootCheckDelaySeconds
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        $boot = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("getprop", "sys.boot_completed")
        $bootCompleted = @(
            (($boot.StdOut | Out-String) -split "`r?`n") |
                Where-Object { $_.Trim() -eq "1" }
        ).Count -gt 0

        if ($bootCompleted) {
            return $true
        }

        if ($attempt -lt $attempts) {
            Start-Sleep -Seconds $delaySeconds
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

function Reset-LogIfOversized {
    param(
        [string]$LogFilePath,
        [int]$MaxSizeMb
    )

    if (-not (Test-Path -LiteralPath $LogFilePath)) {
        return
    }

    $maxBytes = $MaxSizeMb * 1MB
    if ($maxBytes -lt 1MB) {
        $maxBytes = 1MB
    }

    $logFile = Get-Item -LiteralPath $LogFilePath
    if ($logFile.Length -lt $maxBytes) {
        return
    }

    Remove-Item -LiteralPath $LogFilePath -Force
}

function Remove-StaleLogs {
    param(
        [string]$DirectoryPath,
        [string]$BaseFileName,
        [string]$CurrentLogFileName,
        [int]$RetentionDays
    )

    $cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
    $baseName = Get-LogBaseName -FileName $BaseFileName
    Get-ChildItem -LiteralPath $DirectoryPath -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "$baseName*.log" -and
            $_.Name -ne $CurrentLogFileName -and
            $_.LastWriteTime -lt $cutoff
        } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Write-LogLines {
    param([string[]]$Lines)

    foreach ($line in $Lines) {
        if ($null -eq $line -or $line -eq "") {
            Write-MonitorBlankLine
            continue
        }

        Write-MonitorLine -Message $line -ForegroundColor (Get-MonitorLineColor -Message $line)
    }
}

function Format-DeviceReason {
    param([string]$Reason)

    switch ($Reason) {
        "boot_not_completed" { return "boot not completed" }
        "no_devices_found" { return "no devices found" }
        default {
            if ($Reason -like "state=*") {
                return $Reason.Substring(6)
            }
            return $Reason
        }
    }
}

function New-RunSummary {
    param(
        [datetime]$RunTime,
        [string]$ConfigFilePath,
        [string]$LogFilePath,
        [string]$ResolvedAdbPath,
        [string]$ResolvedLdPlayerPath,
        [int]$ExpectedHealthyDevices,
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

    $alertMessage = ""
    if ($ExpectedHealthyDevices -gt 0 -and $healthyDevices.Count -lt $ExpectedHealthyDevices) {
        $alertMessage = "healthy devices below expected expected=$ExpectedHealthyDevices actual=$($healthyDevices.Count)"
    }

    return [pscustomobject]@{
        Timestamp        = $RunTime.ToString("o")
        ConfigFilePath   = $ConfigFilePath
        LogFilePath      = $LogFilePath
        AdbPath          = $ResolvedAdbPath
        LdPlayerPath     = $ResolvedLdPlayerPath
        ExpectedHealthy  = $ExpectedHealthyDevices
        Status           = $status
        TotalCount       = $Checks.Count
        HealthyCount     = $healthyDevices.Count
        UnhealthyCount   = $unhealthyDevices.Count
        HealthyDevices   = $healthyDevices
        UnhealthyDevices = $unhealthyDevices
        AlertMessage     = $alertMessage
        ErrorMessage     = $ErrorMessage
    }
}

function Convert-SummaryToLogLines {
    param([pscustomobject]$Summary)

    $prefix = "[{0}]" -f $Summary.Timestamp
    $lines = New-Object System.Collections.Generic.List[string]

    $resultLevel = if ($Summary.Status -eq "healthy") { "INFO" } else { "WARN" }

    $lines.Add("$prefix [INFO] monitor start")
    $lines.Add("$prefix [INFO] config=$($Summary.ConfigFilePath)")
    $lines.Add("$prefix [INFO] ldplayer=$($Summary.LdPlayerPath)")
    $lines.Add("$prefix [INFO] adb=$($Summary.AdbPath)")
    $lines.Add("$prefix [$resultLevel] status=$($Summary.Status) total=$($Summary.TotalCount) healthy=$($Summary.HealthyCount) unhealthy=$($Summary.UnhealthyCount)")

    foreach ($device in $Summary.HealthyDevices) {
        $lines.Add("$prefix [INFO] $device healthy")
    }

    foreach ($device in $Summary.UnhealthyDevices) {
        $lines.Add("$prefix [WARN] $($device.Serial) $(Format-DeviceReason -Reason $device.Reason)")
    }

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        $lines.Add("$prefix [ERROR] $($Summary.ErrorMessage)")
    }

    if (-not [string]::IsNullOrWhiteSpace($Summary.AlertMessage)) {
        $lines.Add("$prefix [ERROR] $($Summary.AlertMessage)")
    }

    $lines.Add("$prefix [INFO] log=$($Summary.LogFilePath)")
    $lines.Add("$prefix [INFO] monitor end")
    $lines.Add("")
    return $lines
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$script:CommonLdPlayerDirs = @(
    foreach ($item in (Get-ConfigList -Config $config -Key "common_ldplayer_dirs")) {
        Resolve-PathFromBase -BaseDirectory $configDirectory -Value $item
    }
)
$script:RegistryRoots = @(Get-ConfigList -Config $config -Key "registry_roots")
$script:RegistryValueNames = @(Get-ConfigList -Config $config -Key "registry_value_names")
$script:ExternalCommandTimeoutSeconds = [int](Get-ConfigValue -Config $config -Key "external_command_timeout_seconds" -DefaultValue "20")
$script:AdbDevicesTimeoutSeconds = [int](Get-ConfigValue -Config $config -Key "adb_devices_timeout_seconds" -DefaultValue "10")
$script:AdbShellTimeoutSeconds = [int](Get-ConfigValue -Config $config -Key "adb_shell_timeout_seconds" -DefaultValue "15")
$script:BootCheckAttempts = [int](Get-ConfigValue -Config $config -Key "boot_check_attempts" -DefaultValue "3")
$script:BootCheckDelaySeconds = [int](Get-ConfigValue -Config $config -Key "boot_check_delay_seconds" -DefaultValue "1")

$ldPlayerHint = $LdPlayerPath
if ([string]::IsNullOrWhiteSpace($ldPlayerHint)) {
    $ldPlayerHint = Get-ConfigValue -Config $config -Key "ldplayer_path"
}
if (-not [string]::IsNullOrWhiteSpace($ldPlayerHint)) {
    $ldPlayerHint = Resolve-PathFromBase -BaseDirectory $configDirectory -Value $ldPlayerHint
}

$logDirectory = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
$logFileName = Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log"
$retentionDays = [int](Get-ConfigValue -Config $config -Key "log_retention_days" -DefaultValue "7")
$maxLogSizeMb = [int](Get-ConfigValue -Config $config -Key "log_max_size_mb" -DefaultValue "50")
$expectedHealthyDevices = [int](Get-ConfigValue -Config $config -Key "expected_healthy_devices" -DefaultValue "27")

if ($script:RegistryRoots.Count -eq 0) {
    throw "registry_roots must not be empty."
}
if ($script:RegistryValueNames.Count -eq 0) {
    throw "registry_value_names must not be empty."
}
if ($script:CommonLdPlayerDirs.Count -eq 0) {
    throw "common_ldplayer_dirs must not be empty."
}
if ($script:ExternalCommandTimeoutSeconds -lt 1) {
    throw "external_command_timeout_seconds must be >= 1."
}
if ($script:AdbDevicesTimeoutSeconds -lt 1) {
    throw "adb_devices_timeout_seconds must be >= 1."
}
if ($script:AdbShellTimeoutSeconds -lt 1) {
    throw "adb_shell_timeout_seconds must be >= 1."
}
if ($script:BootCheckAttempts -lt 1) {
    throw "boot_check_attempts must be >= 1."
}
if ($script:BootCheckDelaySeconds -lt 0) {
    throw "boot_check_delay_seconds must be >= 0."
}
if ($retentionDays -lt 1) {
    throw "log_retention_days must be >= 1."
}
if ($maxLogSizeMb -lt 1) {
    throw "log_max_size_mb must be >= 1."
}
if ($expectedHealthyDevices -lt 1) {
    throw "expected_healthy_devices must be >= 1."
}

Ensure-Directory -Path $logDirectory
$logFilePath = Get-DatedLogFilePath -DirectoryPath $logDirectory -BaseFileName $logFileName
Reset-LogIfOversized -LogFilePath $logFilePath -MaxSizeMb $maxLogSizeMb
$script:MonitorLogFilePath = $logFilePath

$runTime = Get-Date
$resolvedAdb = ""
$resolvedLdPlayerPath = ""
$checks = @()
$errorMessage = ""
$exitCode = 0

try {
    $resolvedLdPlayerPath = Resolve-LDPlayerPath -Hint $ldPlayerHint -ResolvedAdbPath ""
    $adbHint = $AdbPath
    if ([string]::IsNullOrWhiteSpace($adbHint) -and -not [string]::IsNullOrWhiteSpace($resolvedLdPlayerPath)) {
        $adbHint = Join-Path $resolvedLdPlayerPath "adb.exe"
    }

    $resolvedAdb = Resolve-AdbPath -Hint $adbHint
    if (-not $resolvedAdb) {
        throw "adb.exe not found under ldplayer_path or PATH."
    }

    if ([string]::IsNullOrWhiteSpace($resolvedLdPlayerPath)) {
        $resolvedLdPlayerPath = Resolve-LDPlayerPath -Hint $ldPlayerHint -ResolvedAdbPath $resolvedAdb
    }

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

$summary = New-RunSummary -RunTime $runTime -ConfigFilePath $configFullPath -LogFilePath $logFilePath -ResolvedAdbPath $resolvedAdb -ResolvedLdPlayerPath $resolvedLdPlayerPath -ExpectedHealthyDevices $expectedHealthyDevices -Checks $checks -ErrorMessage $errorMessage
$logLines = Convert-SummaryToLogLines -Summary $summary
Write-LogLines -Lines $logLines
Remove-StaleLogs -DirectoryPath $logDirectory -BaseFileName $logFileName -CurrentLogFileName (Split-Path -Leaf $logFilePath) -RetentionDays $retentionDays
exit $exitCode
