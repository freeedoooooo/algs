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

function Get-NextStartBoundary {
    param([string]$TimeText)

    if ($TimeText -notmatch '^\d{2}:\d{2}:\d{2}$') {
        throw "schedule_start_time must use HH:mm:ss format."
    }

    $parts = $TimeText.Split(":")
    $hour = [int]$parts[0]
    $minute = [int]$parts[1]
    $second = [int]$parts[2]
    if ($hour -gt 23 -or $minute -gt 59 -or $second -gt 59) {
        throw "schedule_start_time must be a valid 24-hour time."
    }

    $now = Get-Date
    $start = Get-Date -Year $now.Year -Month $now.Month -Day $now.Day -Hour $hour -Minute $minute -Second $second
    if ($start -le $now) {
        $start = $start.AddDays(1)
    }

    return $start
}

function Get-RunnerProcesses {
    param([string]$RunnerScriptPath)

    $escapedPath = [System.Management.Automation.WildcardPattern]::Escape($RunnerScriptPath)
    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -like "*$escapedPath*"
    })
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$taskName = Get-ConfigValue -Config $config -Key "task_name" -DefaultValue "LDPlayerHealthMonitor"
$intervalSeconds = [int](Get-ConfigValue -Config $config -Key "schedule_interval_seconds" -DefaultValue "10")
$startTimeText = Get-ConfigValue -Config $config -Key "schedule_start_time" -DefaultValue "00:00:00"
$taskDescription = Get-ConfigValue -Config $config -Key "task_description" -DefaultValue "LDPlayer health monitor task"

if ($intervalSeconds -lt 1) {
    throw "schedule_interval_seconds must be >= 1."
}

$runnerScriptPath = Join-Path $scriptRoot "monitor-runner.ps1"
if (-not (Test-Path -LiteralPath $runnerScriptPath)) {
    throw "Runner script not found: $runnerScriptPath"
}

$startBoundary = Get-NextStartBoundary -TimeText $startTimeText
$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$actionArguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$runnerScriptPath`"",
    "-ConfigPath", "`"$configFullPath`""
) -join " "

$action = New-ScheduledTaskAction -Execute $powershellPath -Argument $actionArguments -WorkingDirectory $configDirectory
$trigger = New-ScheduledTaskTrigger -Once -At $startBoundary
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $taskDescription | Out-Null
$runningProcesses = @(Get-RunnerProcesses -RunnerScriptPath $runnerScriptPath)
if ($runningProcesses.Count -eq 0) {
    Start-ScheduledTask -TaskName $taskName
} else {
    Write-Host "Runner already running. Skip immediate start."
}

Write-Host "Task registered: $taskName"
Write-Host "Next schedule start: $($startBoundary.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Interval seconds: $intervalSeconds"
