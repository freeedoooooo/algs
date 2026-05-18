param(
    [string]$XmlPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'Machine.xml'),
    [string]$SettingsPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'monitor-settings.json'),
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

function ConvertTo-Hashtable {
    param([object]$InputObject)

    if ($null -eq $InputObject) {
        return $null
    }

    $result = @{}
    foreach ($property in $InputObject.PSObject.Properties) {
        $value = $property.Value
        if ($value -is [System.Management.Automation.PSCustomObject]) {
            $result[$property.Name] = ConvertTo-Hashtable -InputObject $value
        }
        elseif ($value -is [System.Array]) {
            $items = @()
            foreach ($item in $value) {
                if ($item -is [System.Management.Automation.PSCustomObject]) {
                    $items += , (ConvertTo-Hashtable -InputObject $item)
                }
                else {
                    $items += , $item
                }
            }
            $result[$property.Name] = $items
        }
        else {
            $result[$property.Name] = $value
        }
    }

    return $result
}

function Load-State {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return @{}
    }

    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @{}
    }

    $stateObject = $raw | ConvertFrom-Json
    return ConvertTo-Hashtable -InputObject $stateObject
}

function Save-State {
    param(
        [hashtable]$State,
        [string]$Path
    )

    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-MachineKey {
    param([object]$Machine)

    return '{0}|{1}|{2}|{3}' -f $Machine.Group, $Machine.Name, $Machine.IP, $Machine.Port
}

function New-StateRecord {
    return @{
        Status                = 'UNKNOWN'
        ConsecutiveFailures   = 0
        ConsecutiveSuccesses  = 0
        FirstFailureAt        = $null
        LastCheckedAt         = $null
        LastStatusChangeAt    = $null
        LastAlertedAt         = $null
        LastRecoveredAt       = $null
        AlertActive           = $false
        LastNote              = $null
    }
}

function Update-StateAndCollectAlerts {
    param(
        [object[]]$Report,
        [hashtable]$State,
        [datetime]$CheckedAt,
        [hashtable]$AlertSettings
    )

    $offlineAlerts = @()
    $recoveryAlerts = @()
    $activeKeys = @{}

    $failureThreshold = [int]$AlertSettings.FailureThreshold
    $recoveryThreshold = [int]$AlertSettings.RecoveryThreshold
    $reminderMinutes = [int]$AlertSettings.ReminderMinutes

    foreach ($machine in $Report) {
        $key = Get-MachineKey -Machine $machine
        $activeKeys[$key] = $true

        if (-not $State.ContainsKey($key) -or $null -eq $State[$key]) {
            $State[$key] = New-StateRecord
        }

        $record = $State[$key]
        $previousStatus = [string]$record.Status
        $isUp = ($machine.Status -eq 'UP')

        if ($isUp) {
            $record.ConsecutiveSuccesses = [int]$record.ConsecutiveSuccesses + 1
            $record.ConsecutiveFailures = 0

            if ($previousStatus -ne 'UP') {
                $record.LastStatusChangeAt = $CheckedAt.ToString('s')
            }

            if ([bool]$record.AlertActive -and [int]$record.ConsecutiveSuccesses -ge $recoveryThreshold) {
                $record.AlertActive = $false
                $record.LastRecoveredAt = $CheckedAt.ToString('s')
                $record.LastAlertedAt = $CheckedAt.ToString('s')
                $recoveryAlerts += [pscustomobject]@{
                    Machine         = $machine
                    FirstFailureAt  = $record.FirstFailureAt
                    LastRecoveredAt = $record.LastRecoveredAt
                }
            }

            $record.FirstFailureAt = $null
        }
        else {
            $record.ConsecutiveFailures = [int]$record.ConsecutiveFailures + 1
            $record.ConsecutiveSuccesses = 0

            if ($previousStatus -eq 'UP' -or [string]::IsNullOrWhiteSpace([string]$record.FirstFailureAt)) {
                $record.FirstFailureAt = $CheckedAt.ToString('s')
                $record.LastStatusChangeAt = $CheckedAt.ToString('s')
            }

            $shouldSendFailureAlert = $false
            if ([int]$record.ConsecutiveFailures -ge $failureThreshold) {
                if (-not [bool]$record.AlertActive) {
                    $shouldSendFailureAlert = $true
                }
                elseif (-not [string]::IsNullOrWhiteSpace([string]$record.LastAlertedAt)) {
                    $lastAlertedAt = [datetime]::Parse($record.LastAlertedAt)
                    if ($reminderMinutes -gt 0 -and $lastAlertedAt.AddMinutes($reminderMinutes) -le $CheckedAt) {
                        $shouldSendFailureAlert = $true
                    }
                }
            }

            if ($shouldSendFailureAlert) {
                $record.AlertActive = $true
                $record.LastAlertedAt = $CheckedAt.ToString('s')
                $offlineAlerts += [pscustomobject]@{
                    Machine             = $machine
                    FirstFailureAt      = $record.FirstFailureAt
                    ConsecutiveFailures = $record.ConsecutiveFailures
                    LastAlertedAt       = $record.LastAlertedAt
                }
            }
        }

        $record.Status = $machine.Status
        $record.LastCheckedAt = $CheckedAt.ToString('s')
        $record.LastNote = $machine.Note
        $State[$key] = $record
    }

    foreach ($stateKey in @($State.Keys)) {
        if (-not $activeKeys.ContainsKey($stateKey)) {
            $State.Remove($stateKey)
        }
    }

    $result = [ordered]@{}
    $result['OfflineAlerts'] = @($offlineAlerts)
    $result['RecoveryAlerts'] = @($recoveryAlerts)
    $result['State'] = $State
    return $result
}

function Send-AlertMail {
    param(
        [hashtable]$AlertSettings,
        [string]$Subject,
        [string]$Body,
        [string]$LogFile
    )

    if (-not [bool]$AlertSettings.Enabled) {
        return
    }

    if ([string]::IsNullOrWhiteSpace([string]$AlertSettings.SmtpHost)) {
        throw 'Alert.SmtpHost is empty.'
    }

    if ([string]::IsNullOrWhiteSpace([string]$AlertSettings.From)) {
        throw 'Alert.From is empty.'
    }

    $recipients = @($AlertSettings.To)
    if ($recipients.Count -eq 0) {
        throw 'Alert.To is empty.'
    }

    $message = [System.Net.Mail.MailMessage]::new()
    $message.From = [System.Net.Mail.MailAddress]::new([string]$AlertSettings.From)
    foreach ($recipient in $recipients) {
        if (-not [string]::IsNullOrWhiteSpace([string]$recipient)) {
            $message.To.Add([string]$recipient)
        }
    }
    $message.Subject = $Subject
    $message.Body = $Body
    $message.BodyEncoding = [System.Text.Encoding]::UTF8
    $message.SubjectEncoding = [System.Text.Encoding]::UTF8

    $smtpClient = [System.Net.Mail.SmtpClient]::new([string]$AlertSettings.SmtpHost, [int]$AlertSettings.SmtpPort)
    $smtpClient.EnableSsl = [bool]$AlertSettings.UseSsl

    if (-not [string]::IsNullOrWhiteSpace([string]$AlertSettings.UserName)) {
        $smtpClient.Credentials = [System.Net.NetworkCredential]::new(
            [string]$AlertSettings.UserName,
            [string]$AlertSettings.Password
        )
    }

    try {
        $smtpClient.Send($message)
        Write-Log -Message "Alert email sent: $Subject" -LogFile $LogFile
    }
    finally {
        $message.Dispose()
        $smtpClient.Dispose()
    }
}

function Build-OfflineAlertBody {
    param(
        [object[]]$Alerts,
        [datetime]$CheckedAt,
        [object]$Summary
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("PC Monitor detected offline machines.")
    $lines.Add("CheckedAt: $($CheckedAt.ToString('yyyy-MM-dd HH:mm:ss'))")
    $lines.Add("Online: $($Summary.OnlineCount), HostUpPortDown: $($Summary.HostUpPortDownCount), Down: $($Summary.DownCount)")
    $lines.Add('')

    foreach ($alert in $Alerts | Sort-Object { $_.Machine.Group }, { [int]$_.Machine.Name }) {
        $machine = $alert.Machine
        $lines.Add(("Group={0}, Name={1}, IP={2}, Port={3}, Status={4}" -f $machine.Group, $machine.Name, $machine.IP, $machine.Port, $machine.Status))
        $lines.Add(("FirstFailureAt={0}, ConsecutiveFailures={1}" -f $alert.FirstFailureAt, $alert.ConsecutiveFailures))
        $lines.Add(("Note={0}" -f $machine.Note))
        $lines.Add('')
    }

    return ($lines -join [Environment]::NewLine)
}

function Build-RecoveryAlertBody {
    param(
        [object[]]$Alerts,
        [datetime]$CheckedAt,
        [object]$Summary
    )

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("PC Monitor detected recovered machines.")
    $lines.Add("CheckedAt: $($CheckedAt.ToString('yyyy-MM-dd HH:mm:ss'))")
    $lines.Add("Online: $($Summary.OnlineCount), HostUpPortDown: $($Summary.HostUpPortDownCount), Down: $($Summary.DownCount)")
    $lines.Add('')

    foreach ($alert in $Alerts | Sort-Object { $_.Machine.Group }, { [int]$_.Machine.Name }) {
        $machine = $alert.Machine
        $lines.Add(("Group={0}, Name={1}, IP={2}, Port={3}, Status={4}" -f $machine.Group, $machine.Name, $machine.IP, $machine.Port, $machine.Status))
        $lines.Add(("FirstFailureAt={0}, RecoveredAt={1}" -f $alert.FirstFailureAt, $alert.LastRecoveredAt))
        $lines.Add(("Note={0}" -f $machine.Note))
        $lines.Add('')
    }

    return ($lines -join [Environment]::NewLine)
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
        [bool]$RequirePingForOnline,
        [int]$PingTimeoutMs
    )

    $pingReachable = $null
    $latencyMs = $null
    $note = $TcpError
    $status = 'DOWN'
    $tcpNote = if ($TcpReachable) { 'TCP connected' } else { $TcpError }

    if ($ShouldPing) {
        $ping = Test-PingStatus -IP $Machine.IP -TimeoutMs $PingTimeoutMs
        $pingReachable = $ping.Reachable
        $latencyMs = $ping.LatencyMs

        if ($TcpReachable -and $RequirePingForOnline) {
            if ($ping.Reachable) {
                $status = 'UP'
                $note = "Ping ok ($latencyMs ms), TCP connected"
            }
            else {
                $note = "Ping failed ($($ping.Status)); TCP connected"
            }
        }
        elseif (-not $TcpReachable) {
            if ($ping.Reachable) {
                $status = 'HOST_UP_PORT_DOWN'
                $note = "Ping ok ($latencyMs ms), port closed or filtered; $TcpError"
            }
            else {
                $note = "Ping failed ($($ping.Status)); $TcpError"
            }
        }
    }
    elseif ($TcpReachable) {
        $status = 'UP'
        $note = $tcpNote
    }

    if ($TcpReachable -and -not $RequirePingForOnline -and $ShouldPing -and $null -eq $pingReachable) {
        $status = 'UP'
        $note = $tcpNote
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
    RequirePingForOnline = $true
    TestPingWhenTcpFails = $true
    OnlyShowOffline      = $false
    ReportPath           = 'output/last-report.json'
    SummaryPath          = 'output/last-summary.json'
    StatePath            = 'output/monitor-state.json'
    LogDirectory         = 'output/logs'
    Alert                = @{
        Enabled          = $false
        FailureThreshold = 3
        RecoveryThreshold = 2
        ReminderMinutes  = 60
        From             = 'monitor@example.com'
        To               = @('admin@example.com')
        SmtpHost         = 'smtp.example.com'
        SmtpPort         = 465
        UseSsl           = $true
        UserName         = 'monitor@example.com'
        Password         = 'replace-with-real-password'
        SubjectPrefix    = '[PC-Monitor]'
    }
}

$settings = Merge-Settings -Defaults $defaultSettings -Path $SettingsPath
$baseDirectory = Split-Path -Path $SettingsPath -Parent
if ([string]::IsNullOrWhiteSpace($baseDirectory)) {
    $baseDirectory = $PSScriptRoot
}

$reportPath = Resolve-ConfigPath -Path $settings.ReportPath -BaseDirectory $baseDirectory
$summaryPath = Resolve-ConfigPath -Path $settings.SummaryPath -BaseDirectory $baseDirectory
$statePath = Resolve-ConfigPath -Path $settings.StatePath -BaseDirectory $baseDirectory
$logDirectory = Resolve-ConfigPath -Path $settings.LogDirectory -BaseDirectory $baseDirectory
if ($settings.Alert -is [System.Management.Automation.PSCustomObject]) {
    $settings.Alert = ConvertTo-Hashtable -InputObject $settings.Alert
}

if (-not (Test-Path -LiteralPath $logDirectory)) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

Ensure-ParentDirectory -Path $reportPath
Ensure-ParentDirectory -Path $summaryPath
Ensure-ParentDirectory -Path $statePath

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

$shouldPing = (-not $SkipPing.IsPresent) -and (
    [bool]$settings.RequirePingForOnline -or
    [bool]$settings.TestPingWhenTcpFails
)
$requirePingForOnline = (-not $SkipPing.IsPresent) -and [bool]$settings.RequirePingForOnline

$report = @(
foreach ($machine in $machines) {
    $tcpResult = Test-TcpPort -IP $machine.IP -Port $machine.Port -TimeoutMs ([int]$settings.TimeoutMs)
    Get-MachineStatus `
        -Machine $machine `
        -TcpReachable $tcpResult.Reachable `
        -TcpError $tcpResult.Error `
        -ShouldPing $shouldPing `
        -RequirePingForOnline $requirePingForOnline `
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

$state = Load-State -Path $statePath
$alertChanges = Update-StateAndCollectAlerts `
    -Report $reportItems `
    -State $state `
    -CheckedAt $checkedAt `
    -AlertSettings $settings.Alert

Save-State -State $alertChanges.State -Path $statePath

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
Write-Host ("State file:      {0}" -f $statePath)

if ([bool]$settings.Alert.Enabled) {
    $subjectPrefix = [string]$settings.Alert.SubjectPrefix

    if ($alertChanges.OfflineAlerts.Count -gt 0) {
        $offlineBody = Build-OfflineAlertBody -Alerts $alertChanges.OfflineAlerts -CheckedAt $checkedAt -Summary $summary
        $offlineSubject = "{0} {1} machine(s) offline" -f $subjectPrefix, $alertChanges.OfflineAlerts.Count
        Send-AlertMail -AlertSettings $settings.Alert -Subject $offlineSubject -Body $offlineBody -LogFile $logFile
    }

    if ($alertChanges.RecoveryAlerts.Count -gt 0) {
        $recoveryBody = Build-RecoveryAlertBody -Alerts $alertChanges.RecoveryAlerts -CheckedAt $checkedAt -Summary $summary
        $recoverySubject = "{0} {1} machine(s) recovered" -f $subjectPrefix, $alertChanges.RecoveryAlerts.Count
        Send-AlertMail -AlertSettings $settings.Alert -Subject $recoverySubject -Body $recoveryBody -LogFile $logFile
    }
}

Write-Log -Message ("Finished check. Online={0}, HostUpPortDown={1}, Down={2}" -f $summary.OnlineCount, $summary.HostUpPortDownCount, $summary.DownCount) -LogFile $logFile

if ($summary.HasFailures) {
    exit 2
}

exit 0
