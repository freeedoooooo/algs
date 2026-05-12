[CmdletBinding()]
param(
    [string]$ConfigPath = "..\monitor.config"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot "common.ps1")

$script:LastConsoleClearAt = Get-Date

function Clear-ConsoleIfNeeded {
    param([int]$IntervalSeconds)

    if ($IntervalSeconds -lt 1) {
        return
    }

    $now = Get-Date
    if ((New-TimeSpan -Start $script:LastConsoleClearAt -End $now).TotalSeconds -lt $IntervalSeconds) {
        return
    }

    Clear-Host
    $script:LastConsoleClearAt = $now
}

function Write-RunnerPidFile {
    param([string]$PidFilePath)

    if ([string]::IsNullOrWhiteSpace($PidFilePath)) {
        return
    }

    $pidDirectory = Split-Path -Parent $PidFilePath
    Ensure-Directory -Path $pidDirectory
    Set-Content -LiteralPath $PidFilePath -Value $PID -Encoding ASCII
}

function Remove-RunnerPidFile {
    param([string]$PidFilePath)

    if ([string]::IsNullOrWhiteSpace($PidFilePath)) {
        return
    }

    if (Test-Path -LiteralPath $PidFilePath) {
        Remove-Item -LiteralPath $PidFilePath -Force -ErrorAction SilentlyContinue
    }
}

$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$intervalSeconds = [int](Get-ConfigValue -Config $config -Key "schedule_interval_seconds" -DefaultValue "10")
$clearIntervalSeconds = [int](Get-ConfigValue -Config $config -Key "window_clear_interval_seconds" -DefaultValue "3600")
$runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")

if ($intervalSeconds -lt 1) {
    throw "schedule_interval_seconds must be >= 1."
}
if ($clearIntervalSeconds -lt 1) {
    throw "window_clear_interval_seconds must be >= 1."
}

$monitorScriptPath = Join-Path $scriptRoot "check.ps1"
if (-not (Test-Path -LiteralPath $monitorScriptPath)) {
    throw "Monitor script not found: $monitorScriptPath"
}

$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$argumentList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $monitorScriptPath,
    "-ConfigPath", $configFullPath
)

Write-RunnerPidFile -PidFilePath $runnerPidFile
try {
    while ($true) {
        Clear-ConsoleIfNeeded -IntervalSeconds $clearIntervalSeconds
        & $powershellPath @argumentList
        Start-Sleep -Seconds $intervalSeconds
    }
} finally {
    Remove-RunnerPidFile -PidFilePath $runnerPidFile
}
