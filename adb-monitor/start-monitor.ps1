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

function Get-RunnerProcess {
    param([string]$RunnerScriptPath)

    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and $_.CommandLine -like "*monitor-runner.ps1*"
    } | Select-Object -First 1
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$intervalSeconds = [int](Get-ConfigValue -Config $config -Key "schedule_interval_seconds" -DefaultValue "10")
$runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\monitor.pid")
if ($intervalSeconds -lt 1) {
    throw "schedule_interval_seconds must be >= 1."
}

$runnerScriptPath = Join-Path $scriptRoot "monitor-runner.ps1"
if (-not (Test-Path -LiteralPath $runnerScriptPath)) {
    throw "Runner script not found: $runnerScriptPath"
}

$existingRunner = Get-RunnerProcess -RunnerScriptPath $runnerScriptPath
if ($existingRunner) {
    Set-Content -LiteralPath $runnerPidFile -Value $existingRunner.ProcessId -Encoding ASCII
    Write-Host "Runner already running: PID $($existingRunner.ProcessId)"
    Write-Host "PID file: $runnerPidFile"
    exit 0
}

$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$process = Start-Process -FilePath $powershellPath -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $runnerScriptPath,
    "-ConfigPath", $configFullPath
) -WorkingDirectory $configDirectory -PassThru -WindowStyle Hidden

Set-Content -LiteralPath $runnerPidFile -Value $process.Id -Encoding ASCII
Write-Host "Runner started: PID $($process.Id)"
Write-Host "PID file: $runnerPidFile"
Write-Host "Interval seconds: $intervalSeconds"
