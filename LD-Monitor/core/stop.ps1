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
$logMaxSizeMb = [int](Get-ConfigValue -Config $config -Key "log_max_size_mb" -DefaultValue "50")
$logRetentionDays = [int](Get-ConfigValue -Config $config -Key "log_retention_days" -DefaultValue "7")
$runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")

if ($logMaxSizeMb -lt 1) {
    throw "log_max_size_mb must be >= 1."
}
if ($logRetentionDays -lt 1) {
    throw "log_retention_days must be >= 1."
}

Reset-LogIfOversized -LogFilePath $logPath -MaxSizeMb $logMaxSizeMb

$stopped = $false
if (Test-Path -LiteralPath $runnerPidFile) {
    $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
    $runnerId = 0
    if ([int]::TryParse($pidText.Trim(), [ref]$runnerId)) {
        $proc = Get-RunnerProcessById -ProcessId $runnerId
        if ($proc) {
            Stop-Process -Id $runnerId -Force -ErrorAction SilentlyContinue
            Write-LogLine -LogPath $logPath -Message "监控已停止，PID=$runnerId"
            $stopped = $true
        }
    }

    Remove-Item -LiteralPath $runnerPidFile -Force -ErrorAction SilentlyContinue
}

$runnerScriptPath = Join-Path $scriptRoot "runner.ps1"
$runnerProcesses = @(Get-RunnerProcessByCommandLine -RunnerScriptPath $runnerScriptPath -ConfigPath $configFullPath)
foreach ($process in $runnerProcesses) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Write-LogLine -LogPath $logPath -Message "监控已停止，PID=$($process.ProcessId)"
    $stopped = $true
}

$checkScriptPath = Join-Path $scriptRoot "check.ps1"
$checkProcesses = @(Get-CheckProcessByCommandLine -CheckScriptPath $checkScriptPath -ConfigPath $configFullPath)
foreach ($process in $checkProcesses) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    Write-LogLine -LogPath $logPath -Message "已清理残留检查进程，PID=$($process.ProcessId)"
    $stopped = $true
}

if (-not $stopped) {
    Write-LogLine -LogPath $logPath -Message "未发现正在运行的监控"
}

Remove-StaleLogs -DirectoryPath (Split-Path -Parent $logPath) -BaseFileName (Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log") -CurrentLogFileName (Split-Path -Leaf $logPath) -RetentionDays $logRetentionDays
