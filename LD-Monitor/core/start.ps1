[CmdletBinding()]
param(
    [string]$ConfigPath = "..\monitor.config"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot "common.ps1")

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

$runnerScriptPath = Join-Path $scriptRoot "runner.ps1"
if (-not (Test-Path -LiteralPath $runnerScriptPath)) {
    throw "Runner script not found: $runnerScriptPath"
}

$safeWorkingDirectory = Get-SafeWorkingDirectory -MonitorRoot $configDirectory

Reset-LogIfOversized -LogFilePath $logPath -MaxSizeMb $logMaxSizeMb
Remove-StaleLogs -DirectoryPath (Split-Path -Parent $logPath) -BaseFileName (Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log") -CurrentLogFileName (Split-Path -Leaf $logPath) -RetentionDays $logRetentionDays

$existingRunnerId = 0
if (Test-Path -LiteralPath $runnerPidFile) {
    $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
    if ([int]::TryParse($pidText.Trim(), [ref]$existingRunnerId)) {
        $pidProcess = Get-RunnerProcessById -ProcessId $existingRunnerId
        if ($pidProcess) {
            Write-LogLine -LogPath $logPath -Message "监控已启动，PID=$existingRunnerId，间隔=${intervalSeconds}秒"
            exit 0
        }
    }

    Remove-Item -LiteralPath $runnerPidFile -Force -ErrorAction SilentlyContinue
}

$existingRunner = @(Get-RunnerProcessByCommandLine -RunnerScriptPath $runnerScriptPath -ConfigPath $configFullPath | Select-Object -First 1)
if ($existingRunner.Count -gt 0) {
    Write-LogLine -LogPath $logPath -Message "监控已启动，PID=$($existingRunner[0].ProcessId)，间隔=${intervalSeconds}秒"
    exit 0
}

$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$process = Start-Process -FilePath $powershellPath -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $runnerScriptPath,
    "-ConfigPath", $configFullPath
) -WorkingDirectory $safeWorkingDirectory -PassThru

Start-Sleep -Seconds 1
$startedRunner = Get-RunnerProcessById -ProcessId $process.Id
if (-not $startedRunner) {
    Write-LogLine -LogPath $logPath -Message "监控启动失败，runner 进程已退出" -Level "ERROR"
    exit 1
}

Write-LogLine -LogPath $logPath -Message "监控启动成功，PID=$($process.Id)，间隔=${intervalSeconds}秒"
