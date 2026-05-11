[CmdletBinding()]
param(
    [string]$ConfigPath = ".\monitor.config"
)

$ErrorActionPreference = "Stop"

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

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $Value))
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
    return Join-Path $DirectoryPath ("{0}-{1}.log" -f $baseName, $Date.ToString("yyyyMMdd"))
}

function Reset-LogIfOversized {
    param(
        [string]$LogFilePath,
        [int]$MaxSizeMb
    )

    if (-not (Test-Path -LiteralPath $LogFilePath)) {
        return
    }

    $maxBytes = [Math]::Max($MaxSizeMb, 1) * 1MB
    if ((Get-Item -LiteralPath $LogFilePath).Length -ge $maxBytes) {
        Remove-Item -LiteralPath $LogFilePath -Force
    }
}

function Remove-StaleLogs {
    param(
        [string]$DirectoryPath,
        [string]$BaseFileName,
        [string]$CurrentLogFileName,
        [int]$RetentionDays
    )

    $cutoff = (Get-Date).AddDays(-1 * [Math]::Max($RetentionDays, 1))
    $baseName = Get-LogBaseName -FileName $BaseFileName
    Get-ChildItem -LiteralPath $DirectoryPath -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "$baseName*.log" -and
            $_.Name -ne $CurrentLogFileName -and
            $_.LastWriteTime -lt $cutoff
        } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Get-MonitorLogPath {
    param(
        [string]$ConfigDirectory,
        [hashtable]$Config
    )

    $logDirectory = Resolve-PathFromBase -BaseDirectory $ConfigDirectory -Value (Get-ConfigValue -Config $Config -Key "log_directory" -DefaultValue ".\log")
    $logFileName = Get-ConfigValue -Config $Config -Key "log_file_name" -DefaultValue "monitor.log"
    if (-not (Test-Path -LiteralPath $logDirectory)) {
        [void](New-Item -Path $logDirectory -ItemType Directory -Force)
    }

    return (Get-DatedLogFilePath -DirectoryPath $logDirectory -BaseFileName $logFileName)
}

function Write-LogLine {
    param(
        [string]$LogPath,
        [string]$Message,
        [string]$Level = "INFO"
    )

    if ([string]::IsNullOrWhiteSpace($Message)) {
        return
    }

    $timestamp = (Get-Date).ToString("o")
    $line = "[{0}] [{1}] {2}" -f $timestamp, $Level, $Message
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Get-RunnerProcess {
    param(
        [string]$RunnerScriptPath,
        [string]$ConfigPath
    )

    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -match [regex]::Escape($RunnerScriptPath) -and
        $_.CommandLine -match [regex]::Escape($ConfigPath)
    } | Select-Object -First 1
}

function Get-RunnerProcessById {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return $null
    }

    return Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath
$logPath = Get-MonitorLogPath -ConfigDirectory $configDirectory -Config $config

$intervalSeconds = [int](Get-ConfigValue -Config $config -Key "schedule_interval_seconds" -DefaultValue "10")
$logMaxSizeMb = [int](Get-ConfigValue -Config $config -Key "log_max_size_mb" -DefaultValue "50")
$logRetentionDays = [int](Get-ConfigValue -Config $config -Key "log_retention_days" -DefaultValue "7")
$runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")
if ($intervalSeconds -lt 1) {
    throw "schedule_interval_seconds must be >= 1."
}
if ($logMaxSizeMb -lt 1) {
    throw "log_max_size_mb must be >= 1."
}
if ($logRetentionDays -lt 1) {
    throw "log_retention_days must be >= 1."
}

$runnerScriptPath = Join-Path $scriptRoot "core\runner.ps1"
if (-not (Test-Path -LiteralPath $runnerScriptPath)) {
    throw "Runner script not found: $runnerScriptPath"
}

Reset-LogIfOversized -LogFilePath $logPath -MaxSizeMb $logMaxSizeMb

$existingRunnerId = 0
if (Test-Path -LiteralPath $runnerPidFile) {
    $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
    if ([int]::TryParse($pidText.Trim(), [ref]$existingRunnerId)) {
        $pidProcess = Get-RunnerProcessById -ProcessId $existingRunnerId
        if ($pidProcess) {
            Write-LogLine -LogPath $logPath -Message "监控已启动，PID=$($process.Id)，间隔=${intervalSeconds}秒"
            exit 0
        }
    }

    Remove-Item -LiteralPath $runnerPidFile -Force -ErrorAction SilentlyContinue
}

$existingRunner = Get-RunnerProcess -RunnerScriptPath $runnerScriptPath -ConfigPath $configFullPath
if ($existingRunner) {
    Set-Content -LiteralPath $runnerPidFile -Value $existingRunner.ProcessId -Encoding ASCII
    Write-LogLine -LogPath $logPath -Message "监控已启动，PID=$($process.Id)，间隔=${intervalSeconds}秒"
    exit 0
}

$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$process = Start-Process -FilePath $powershellPath -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $runnerScriptPath,
    "-ConfigPath", $configFullPath
) -WorkingDirectory $configDirectory -PassThru

Set-Content -LiteralPath $runnerPidFile -Value $process.Id -Encoding ASCII
Write-LogLine -LogPath $logPath -Message "监控已启动，PID=$($process.Id)，间隔=${intervalSeconds}秒"

