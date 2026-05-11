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

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

$intervalSeconds = [int](Get-ConfigValue -Config $config -Key "schedule_interval_seconds" -DefaultValue "10")
if ($intervalSeconds -lt 1) {
    throw "schedule_interval_seconds must be >= 1."
}

$monitorScriptPath = Join-Path $scriptRoot "ldplayer-monitor.ps1"
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

while ($true) {
    & $powershellPath @argumentList
    Start-Sleep -Seconds $intervalSeconds
}
