param(
    [string]$XmlPath = (Join-Path $PSScriptRoot 'Machine.xml'),
    [string]$SettingsPath = (Join-Path $PSScriptRoot 'monitor-settings.json'),
    [switch]$SkipPing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Merge-Settings {
    param(
        [hashtable]$Defaults,
        [string]$Path
    )

    $merged = @{}
    foreach ($key in $Defaults.Keys) {
        $merged[$key] = $Defaults[$key]
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        return $merged
    }

    $fileSettings = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($property in $fileSettings.PSObject.Properties) {
        $merged[$property.Name] = $property.Value
    }

    return $merged
}

function Resolve-ConfigPath {
    param(
        [string]$Path,
        [string]$BaseDirectory
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path $BaseDirectory $Path
}

function Ensure-ParentDirectory {
    param([string]$Path)

    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

function Write-Log {
    param(
        [string]$Message,
        [string]$LogFile
    )

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[{0}] {1}" -f $timestamp, $Message
    Write-Host $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Load-MachinesFromXml {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Machine.xml not found: $Path"
    }

    $xml = New-Object System.Xml.XmlDocument
    $xml.Load($Path)

    $machines = New-Object System.Collections.Generic.List[object]

    foreach ($group in $xml.root.Group) {
        $groupName = $group.GetAttribute('Name')
        foreach ($machine in $group.Machine) {
            $name = $machine.GetAttribute('Name')
            $ip = $machine.GetAttribute('IP')
            $port = $machine.GetAttribute('Port')

            if ([string]::IsNullOrWhiteSpace($ip) -or [string]::IsNullOrWhiteSpace($port)) {
                continue
            }

            $machines.Add([pscustomobject]@{
                    Group    = $groupName
                    Name     = $name
                    IP       = $ip
                    Port     = [int]$port
                    UserName = $machine.GetAttribute('UserName')
                    Mac      = $machine.GetAttribute('Mac')
                })
        }
    }

    return $machines
}

function Test-TcpPort {
    param(
        [string]$IP,
        [int]$Port,
        [int]$TimeoutMs
    )

    $client = [System.Net.Sockets.TcpClient]::new()

    try {
        $asyncResult = $client.BeginConnect($IP, $Port, $null, $null)
        $completed = $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMs, $false)

        if (-not $completed) {
            return [pscustomobject]@{
                Reachable = $false
                Error     = "TCP timeout after $TimeoutMs ms"
            }
        }

        $client.EndConnect($asyncResult)
        return [pscustomobject]@{
            Reachable = $true
            Error     = $null
        }
    }
    catch {
        $baseException = $_.Exception.GetBaseException()
        return [pscustomobject]@{
            Reachable = $false
            Error     = $baseException.Message
        }
    }
    finally {
        $client.Close()
        $client.Dispose()
    }
}

function Test-PingStatus {
    param(
        [string]$IP,
        [int]$TimeoutMs
    )

    $ping = [System.Net.NetworkInformation.Ping]::new()

    try {
        $reply = $ping.Send($IP, $TimeoutMs)
        return [pscustomobject]@{
            Reachable = ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success)
            Status    = [string]$reply.Status
            LatencyMs = $reply.RoundtripTime
        }
    }
    catch {
        return [pscustomobject]@{
            Reachable = $false
            Status    = $_.Exception.Message
            LatencyMs = $null
        }
    }
    finally {
        $ping.Dispose()
    }
}

function Get-MachineStatus {
    param(
        [object]$Machine,
        [bool]$TcpReachable,
        [string]$TcpError,
        [bool]$ShouldPing,
        [int]$PingTimeoutMs
    )

    if ($TcpReachable) {
        return [pscustomobject]@{
            Group         = $Machine.Group
            Name          = $Machine.Name
            IP            = $Machine.IP
            Port          = $Machine.Port
            UserName      = $Machine.UserName
            Mac           = $Machine.Mac
            Status        = 'UP'
            TcpReachable  = $true
            PingReachable = $null
            LatencyMs     = $null
            Note          = 'TCP connected'
        }
    }

    $pingReachable = $null
    $latencyMs = $null
    $note = $TcpError
    $status = 'DOWN'

    if ($ShouldPing) {
        $ping = Test-PingStatus -IP $Machine.IP -TimeoutMs $PingTimeoutMs
        $pingReachable = $ping.Reachable
        $latencyMs = $ping.LatencyMs

        if ($ping.Reachable) {
            $status = 'HOST_UP_PORT_DOWN'
            $note = "Ping ok, port closed or filtered; $TcpError"
        }
        else {
            $note = "Ping failed ($($ping.Status)); $TcpError"
        }
    }

    return [pscustomobject]@{
        Group         = $Machine.Group
        Name          = $Machine.Name
        IP            = $Machine.IP
        Port          = $Machine.Port
        UserName      = $Machine.UserName
        Mac           = $Machine.Mac
        Status        = $status
        TcpReachable  = $false
        PingReachable = $pingReachable
        LatencyMs     = $latencyMs
        Note          = $note
    }
}

$defaultSettings = @{
    TimeoutMs            = 1500
    PingTimeoutMs        = 800
    TestPingWhenTcpFails = $true
    OnlyShowOffline      = $false
    ReportPath           = 'output/last-report.json'
    SummaryPath          = 'output/last-summary.json'
    LogDirectory         = 'output/logs'
}

$settings = Merge-Settings -Defaults $defaultSettings -Path $SettingsPath
$baseDirectory = Split-Path -Path $SettingsPath -Parent
if ([string]::IsNullOrWhiteSpace($baseDirectory)) {
    $baseDirectory = $PSScriptRoot
}

$reportPath = Resolve-ConfigPath -Path $settings.ReportPath -BaseDirectory $baseDirectory
$summaryPath = Resolve-ConfigPath -Path $settings.SummaryPath -BaseDirectory $baseDirectory
$logDirectory = Resolve-ConfigPath -Path $settings.LogDirectory -BaseDirectory $baseDirectory

if (-not (Test-Path -LiteralPath $logDirectory)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

Ensure-ParentDirectory -Path $reportPath
Ensure-ParentDirectory -Path $summaryPath

$logFile = Join-Path $logDirectory ("monitor-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$checkedAt = Get-Date

Write-Log -Message "Loading machine list from $XmlPath" -LogFile $logFile
$machines = Load-MachinesFromXml -Path $XmlPath

if ($machines.Count -eq 0) {
    Write-Log -Message 'No machines found in Machine.xml.' -LogFile $logFile
    exit 1
}

$groupCount = ($machines.Group | Sort-Object -Unique).Count
Write-Log -Message "Loaded $($machines.Count) machines from $groupCount groups." -LogFile $logFile

$shouldPing = (-not $SkipPing.IsPresent) -and [bool]$settings.TestPingWhenTcpFails

$report = @(
foreach ($machine in $machines) {
    $tcpResult = Test-TcpPort -IP $machine.IP -Port $machine.Port -TimeoutMs ([int]$settings.TimeoutMs)
    Get-MachineStatus `
        -Machine $machine `
        -TcpReachable $tcpResult.Reachable `
        -TcpError $tcpResult.Error `
        -ShouldPing $shouldPing `
        -PingTimeoutMs ([int]$settings.PingTimeoutMs)
}
)

$reportItems = @($report)
$onlineItems = @($reportItems | Where-Object Status -eq 'UP')
$hostUpPortDownItems = @($reportItems | Where-Object Status -eq 'HOST_UP_PORT_DOWN')
$downItems = @($reportItems | Where-Object Status -eq 'DOWN')
$failureItems = @($reportItems | Where-Object Status -ne 'UP')

$summary = [pscustomobject]@{
    CheckedAt           = $checkedAt.ToString('s')
    MachineCount        = $reportItems.Count
    GroupCount          = $groupCount
    OnlineCount         = $onlineItems.Count
    HostUpPortDownCount = $hostUpPortDownItems.Count
    DownCount           = $downItems.Count
    HasFailures         = ($failureItems.Count -gt 0)
}

$reportPayload = [pscustomobject]@{
    CheckedAt = $checkedAt.ToString('s')
    Summary   = $summary
    Machines  = $report
}

$reportPayload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
$summary | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$displayRows = $reportItems
if ([bool]$settings.OnlyShowOffline) {
    $displayRows = @($reportItems | Where-Object Status -ne 'UP')
}

Write-Host ''
$displayRows |
Sort-Object Group, @{ Expression = { [int]$_.Name } }, IP |
Format-Table Group, Name, IP, Port, Status, Note -AutoSize

Write-Host ''
Write-Host ("Checked at: {0}" -f $summary.CheckedAt)
Write-Host ("Online: {0}, HostUpPortDown: {1}, Down: {2}" -f $summary.OnlineCount, $summary.HostUpPortDownCount, $summary.DownCount)
Write-Host ("Detailed report: {0}" -f $reportPath)
Write-Host ("Summary report:  {0}" -f $summaryPath)

Write-Log -Message ("Finished check. Online={0}, HostUpPortDown={1}, Down={2}" -f $summary.OnlineCount, $summary.HostUpPortDownCount, $summary.DownCount) -LogFile $logFile

if ($summary.HasFailures) {
    exit 2
}

exit 0
