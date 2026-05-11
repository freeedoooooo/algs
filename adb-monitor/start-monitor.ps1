[CmdletBinding()]
param(
    [string]$ConfigPath = ".\config.txt"
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

    if ($TimeText -notmatch '^\d{2}:\d{2}$') {
        throw "schedule_start_time must use HH:mm format."
    }

    $parts = $TimeText.Split(":")
    $hour = [int]$parts[0]
    $minute = [int]$parts[1]
    if ($hour -gt 23 -or $minute -gt 59) {
        throw "schedule_start_time must be a valid 24-hour time."
    }

    $now = Get-Date
    $start = Get-Date -Year $now.Year -Month $now.Month -Day $now.Day -Hour $hour -Minute $minute -Second 0
    if ($start -le $now) {
        $start = $start.AddDays(1)
    }

    return $start
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$taskName = Get-ConfigValue -Config $config -Key "task_name" -DefaultValue "LDPlayerHealthMonitor"
$intervalMinutes = [int](Get-ConfigValue -Config $config -Key "schedule_interval_minutes" -DefaultValue "30")
$startTimeText = Get-ConfigValue -Config $config -Key "schedule_start_time" -DefaultValue "00:00"
$taskDescription = Get-ConfigValue -Config $config -Key "task_description" -DefaultValue "LDPlayer health monitor task"
$repetitionDays = [int](Get-ConfigValue -Config $config -Key "schedule_repetition_days" -DefaultValue "3650")

if ($intervalMinutes -lt 1) {
    throw "schedule_interval_minutes must be >= 1."
}
if ($repetitionDays -lt 1) {
    throw "schedule_repetition_days must be >= 1."
}

$monitorScriptPath = Join-Path $scriptRoot "ldplayer-monitor.ps1"
if (-not (Test-Path -LiteralPath $monitorScriptPath)) {
    throw "Monitor script not found: $monitorScriptPath"
}

$startBoundary = Get-NextStartBoundary -TimeText $startTimeText
$powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
$actionArguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$monitorScriptPath`"",
    "-ConfigPath", "`"$configFullPath`""
) -join " "

$action = New-ScheduledTaskAction -Execute $powershellPath -Argument $actionArguments -WorkingDirectory $configDirectory
$trigger = New-ScheduledTaskTrigger -Once -At $startBoundary -RepetitionInterval (New-TimeSpan -Minutes $intervalMinutes) -RepetitionDuration ([TimeSpan]::FromDays($repetitionDays))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description $taskDescription | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "Task registered: $taskName"
Write-Host "Next schedule start: $($startBoundary.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Interval minutes: $intervalMinutes"
