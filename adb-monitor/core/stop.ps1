[CmdletBinding()]
param(
    [string]$ConfigPath = "..\monitor.config"
)

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
}
$OutputEncoding = [Console]::OutputEncoding

function Resolve-PathFromBase {
    param([string]$BaseDirectory, [string]$Value)
    if ([System.IO.Path]::IsPathRooted($Value)) { return $Value }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $Value))
}

function Get-ConfigMap {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { throw "配置文件不存在：$Path" }
    $config = @{}
    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or $line.StartsWith(";")) { continue }
        $index = $line.IndexOf("=")
        if ($index -lt 1) { continue }
        $config[$line.Substring(0, $index).Trim().ToLowerInvariant()] = $line.Substring($index + 1).Trim()
    }
    return $config
}

function Get-ConfigValue {
    param([hashtable]$Config, [string]$Key, [string]$DefaultValue = "")
    $lookupKey = $Key.ToLowerInvariant()
    if ($Config.ContainsKey($lookupKey) -and -not [string]::IsNullOrWhiteSpace($Config[$lookupKey])) { return $Config[$lookupKey] }
    return $DefaultValue
}

function Write-LogLine {
    param([string]$LogPath, [string]$Message)
    if ([string]::IsNullOrWhiteSpace($Message)) { return }
    $line = "[{0}] [INFO] {1}" -f (Get-Date).ToString("o"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath
$runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")
$logDirectory = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
$logFileName = Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log"
$logBaseName = [System.IO.Path]::GetFileNameWithoutExtension($logFileName)
$logPath = Join-Path $logDirectory ("{0}-{1}.log" -f $logBaseName, (Get-Date).ToString("yyyyMMdd"))
$stopped = $false

if (-not (Test-Path -LiteralPath $logDirectory)) {
    [void](New-Item -Path $logDirectory -ItemType Directory -Force)
}

if (Test-Path -LiteralPath $runnerPidFile) {
    $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
    $runnerId = 0
    if ([int]::TryParse($pidText.Trim(), [ref]$runnerId)) {
        if (Get-Process -Id $runnerId -ErrorAction SilentlyContinue) {
            Stop-Process -Id $runnerId -Force -ErrorAction SilentlyContinue
            Write-LogLine -LogPath $logPath -Message "监控已停止，PID=$runnerId"
            $stopped = $true
        }
    }
    Remove-Item -LiteralPath $runnerPidFile -Force -ErrorAction SilentlyContinue
}

$runnerScriptPath = Join-Path $scriptRoot "runner.ps1"
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -ieq "powershell.exe" -and
    $_.CommandLine -match [regex]::Escape($runnerScriptPath) -and
    $_.CommandLine -match [regex]::Escape($configFullPath)
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-LogLine -LogPath $logPath -Message "监控已停止，PID=$($_.ProcessId)"
    $stopped = $true
}

if (-not $stopped) {
    Write-LogLine -LogPath $logPath -Message "未发现正在运行的监控"
}