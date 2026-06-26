param(
    [string]$ConfigPath = "..\monitor.config",
    [string]$AdbPath = "",
    [string]$LdPlayerPath = ""
)

$ErrorActionPreference = "Stop"
$script:MonitorLogFilePath = ""
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptRoot "common.ps1")

function Write-Step {
    param([string]$Message)
    Write-MonitorLine -Message "[STEP] $Message" -ForegroundColor Cyan
}

function Write-WarnLog {
    param([string]$Message)
    Write-MonitorLine -Message "[WARN] $Message" -ForegroundColor Yellow
}

function Write-MonitorLine {
    param(
        [AllowEmptyString()][string]$Message,
        [string]$ForegroundColor = ""
    )

    if ([string]::IsNullOrWhiteSpace($Message)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($ForegroundColor)) {
        Write-Host $Message
    } else {
        Write-Host $Message -ForegroundColor $ForegroundColor
    }

    if (-not [string]::IsNullOrWhiteSpace($script:MonitorLogFilePath)) {
        Add-Content -LiteralPath $script:MonitorLogFilePath -Value $Message -Encoding UTF8
    }
}

function Write-MonitorBlankLine {
    Write-BlankLogLine -LogPath $script:MonitorLogFilePath
}

function Get-MonitorLineColor {
    param([string]$Message)

    if ($Message -match '\[ERROR\]') {
        return "Red"
    }
    if ($Message -match '\[WARN\]') {
        return "Yellow"
    }
    if ($Message -match '\[STEP\]') {
        return "Cyan"
    }

    return ""
}

function ConvertTo-ArgumentString {
    param([string[]]$ArgumentList)

    $escaped = foreach ($arg in $ArgumentList) {
        if ($null -eq $arg) {
            '""'
            continue
        }

        if ($arg -notmatch '[\s"]') {
            $arg
            continue
        }

        '"' + (($arg -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
    }

    return ($escaped -join ' ')
}

function Normalize-MailAddress {
    param([string]$Address)

    $value = $Address.Trim()
    if ([string]::IsNullOrWhiteSpace($value)) {
        return ""
    }

    if ($value -notmatch '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$') {
        return ""
    }

    return $value
}

function Get-CommonLdPlayerDirs {
    return @($script:CommonLdPlayerDirs)
}

function Test-LDPlayerInstallDir {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }

    return (Test-Path -LiteralPath (Join-Path $Path "adb.exe"))
}

function Get-LDPlayerInstallDirsFromRegistry {
    $roots = @($script:RegistryRoots)
    $valueNames = @($script:RegistryValueNames)
    $dirs = New-Object System.Collections.Generic.List[string]

    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        $items = @(Get-Item -LiteralPath $root -ErrorAction SilentlyContinue)
        $items += @(Get-ChildItem -LiteralPath $root -Recurse -ErrorAction SilentlyContinue)

        foreach ($item in $items) {
            try {
                $props = Get-ItemProperty -LiteralPath $item.PSPath -ErrorAction SilentlyContinue
                foreach ($name in $valueNames) {
                    $value = $props.$name
                    if (-not [string]::IsNullOrWhiteSpace($value) -and (Test-Path -LiteralPath $value)) {
                        $dirs.Add((Resolve-Path -LiteralPath $value).Path)
                    }
                }
            } catch {
            }
        }
    }

    return @($dirs | Select-Object -Unique)
}

function Resolve-LDPlayerPath {
    param(
        [string]$Hint,
        [string]$ResolvedAdbPath
    )

    if (Test-LDPlayerInstallDir -Path $Hint) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    if ($ResolvedAdbPath -and (Test-Path -LiteralPath $ResolvedAdbPath)) {
        $adbDir = Split-Path -Parent $ResolvedAdbPath
        if (Test-LDPlayerInstallDir -Path $adbDir) {
            return $adbDir
        }
    }

    $dirs = New-Object System.Collections.Generic.List[string]
    foreach ($dir in Get-CommonLdPlayerDirs) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add((Resolve-Path -LiteralPath $dir).Path)
        }
    }
    foreach ($dir in Get-LDPlayerInstallDirsFromRegistry) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add($dir)
        }
    }

    $firstDir = @($dirs | Select-Object -Unique | Select-Object -First 1)
    if ($firstDir.Count -gt 0) {
        return $firstDir[0]
    }

    return ""
}

function Resolve-AdbPath {
    param([string]$Hint)

    if ($Hint -and (Test-Path -LiteralPath $Hint)) {
        return (Resolve-Path -LiteralPath $Hint).Path
    }

    $dirs = New-Object System.Collections.Generic.List[string]
    foreach ($dir in Get-CommonLdPlayerDirs) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add((Resolve-Path -LiteralPath $dir).Path)
        }
    }
    foreach ($dir in Get-LDPlayerInstallDirsFromRegistry) {
        if (Test-LDPlayerInstallDir -Path $dir) {
            $dirs.Add($dir)
        }
    }

    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($dir in @($dirs | Select-Object -Unique)) {
        $candidates.Add((Join-Path $dir "adb.exe"))
    }

    $candidates.Add((Join-Path $env:ProgramFiles "Android\platform-tools\adb.exe"))
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Android\platform-tools\adb.exe"))
    }

    foreach ($candidate in $candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $command = Get-Command adb -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    return $null
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutSeconds = $script:ExternalCommandTimeoutSeconds
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $psi.Arguments = ConvertTo-ArgumentString -ArgumentList $ArgumentList

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi

    [void]$process.Start()

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try {
            $process.Kill()
            $process.WaitForExit()
        } catch {
        }

        throw "Command timed out (${TimeoutSeconds}s): $FilePath $($ArgumentList -join ' ')"
    }

    $stdoutTask.Wait()
    $stderrTask.Wait()

    $stdoutText = $stdoutTask.Result
    $stderrText = $stderrTask.Result
    $combinedText = (@($stdoutText, $stderrText) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join [Environment]::NewLine
    $output = @($combinedText -split "`r?`n" | Where-Object { $_ -ne "" })

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output   = $output
        StdOut   = $stdoutText.Trim()
        StdErr   = $stderrText.Trim()
    }
}

function Get-Devices {
    param([string]$Adb)

    $deviceArgs = @("devices", "-l")
    $result = Invoke-External -FilePath $Adb -ArgumentList $deviceArgs -TimeoutSeconds $script:AdbDevicesTimeoutSeconds
    $fallbackReasons = New-Object System.Collections.Generic.List[string]

    if ($result.ExitCode -ne 0) {
        $fallbackReasons.Add("exit_code=$($result.ExitCode)")
    }

    if ($result.StdOut -match "^Usage:\s+adb devices \[-l\]") {
        $fallbackReasons.Add("adb does not accept -l")
    }

    $nonHeaderLines = @(
        $result.Output |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_) -and
                $_ -notlike "List of devices attached*"
            }
    )

    if ($nonHeaderLines.Count -eq 0) {
        $fallbackReasons.Add("devices -l returned no device lines")
    }

    if ($fallbackReasons.Count -gt 0) {
        $result = Invoke-External -FilePath $Adb -ArgumentList @("devices") -TimeoutSeconds $script:AdbDevicesTimeoutSeconds
        if ($result.ExitCode -ne 0) {
            throw "Failed to run adb devices: $($result.StdOut) $($result.StdErr)".Trim()
        }
    }

    $devices = @()
    foreach ($line in $result.Output) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line -like "List of devices attached*") {
            continue
        }

        $parts = ($line -split "\s+") | Where-Object { $_ }
        if ($parts.Count -lt 2) {
            continue
        }

        $devices += [pscustomobject]@{
            Serial = $parts[0]
            State  = $parts[1]
        }
    }

    return @($devices)
}

function Invoke-AdbShell {
    param(
        [string]$Adb,
        [string]$Serial,
        [string[]]$ShellArgs
    )

    return Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $ShellArgs) -TimeoutSeconds $script:AdbShellTimeoutSeconds
}

function Test-BootCompleted {
    param(
        [string]$Adb,
        [string]$Serial
    )

    $attempts = $script:BootCheckAttempts
    $delaySeconds = $script:BootCheckDelaySeconds
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        $boot = Invoke-AdbShell -Adb $Adb -Serial $Serial -ShellArgs @("getprop", "sys.boot_completed")
        $bootCompleted = @(
            (($boot.StdOut | Out-String) -split "`r?`n") |
                Where-Object { $_.Trim() -eq "1" }
        ).Count -gt 0

        if ($bootCompleted) {
            return $true
        }

        if ($attempt -lt $attempts) {
            Start-Sleep -Seconds $delaySeconds
        }
    }

    return $false
}

function Get-LDConsolePath {
    param([string]$LdPlayerPath)

    if ([string]::IsNullOrWhiteSpace($LdPlayerPath)) {
        return ""
    }

    foreach ($fileName in @("ldconsole.exe", "dnconsole.exe")) {
        $candidate = Join-Path $LdPlayerPath $fileName
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return ""
}

function Get-LDPlayerInstances {
    param([string]$LdPlayerPath)

    $ldConsolePath = Get-LDConsolePath -LdPlayerPath $LdPlayerPath
    if ([string]::IsNullOrWhiteSpace($ldConsolePath)) {
        return @()
    }

    try {
        $result = Invoke-External -FilePath $ldConsolePath -ArgumentList @("list2")
        if ($result.ExitCode -ne 0) {
            return @()
        }

        $instances = @()
        foreach ($line in $result.Output) {
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }

            $parts = $line -split ",", 7
            if ($parts.Count -lt 2) {
                continue
            }

            $index = 0
            if (-not [int]::TryParse($parts[0], [ref]$index)) {
                continue
            }

            $instances += [pscustomobject]@{
                Index = $index
                Name  = $parts[1].Trim()
            }
        }

        return @($instances)
    } catch {
        return @()
    }
}

function Get-InstanceIndexFromSerial {
    param([string]$Serial)

    if ($Serial -match '^emulator-(\d+)$') {
        $port = [int]$matches[1]
        if ($port -ge 5554 -and (($port - 5554) % 2 -eq 0)) {
            return [int](($port - 5554) / 2)
        }
    }

    return $null
}

function Get-DeviceInstanceInfo {
    param(
        [string]$Serial,
        [object[]]$LdPlayerInstances = @()
    )

    $instanceIndex = Get-InstanceIndexFromSerial -Serial $Serial
    $instanceName = ""
    $displayName = $Serial

    if ($null -ne $instanceIndex) {
        $matchedInstance = @($LdPlayerInstances | Where-Object { $_.Index -eq $instanceIndex } | Select-Object -First 1)
        if ($matchedInstance.Count -gt 0) {
            $instanceName = $matchedInstance[0].Name
        }

        if ([string]::IsNullOrWhiteSpace($instanceName)) {
            $displayName = "模拟器$instanceIndex"
        } else {
            $displayName = "模拟器$instanceIndex（$instanceName）"
        }
    }

    return [pscustomobject]@{
        InstanceIndex = $instanceIndex
        InstanceName  = $instanceName
        DisplayName   = $displayName
    }
}

function Test-DeviceHealth {
    param(
        [string]$Adb,
        [object]$Device,
        [object[]]$LdPlayerInstances = @()
    )

    $instanceInfo = Get-DeviceInstanceInfo -Serial $Device.Serial -LdPlayerInstances $LdPlayerInstances

    if ($Device.State -ne "device") {
        return [pscustomobject]@{
            Serial        = $Device.Serial
            State         = $Device.State
            Healthy       = $false
            Reason        = "state=$($Device.State)"
            InstanceIndex = $instanceInfo.InstanceIndex
            InstanceName  = $instanceInfo.InstanceName
            DisplayName   = $instanceInfo.DisplayName
        }
    }

    $bootCompleted = Test-BootCompleted -Adb $Adb -Serial $Device.Serial
    if (-not $bootCompleted) {
        return [pscustomobject]@{
            Serial        = $Device.Serial
            State         = $Device.State
            Healthy       = $false
            Reason        = "boot_not_completed"
            InstanceIndex = $instanceInfo.InstanceIndex
            InstanceName  = $instanceInfo.InstanceName
            DisplayName   = $instanceInfo.DisplayName
        }
    }

    return [pscustomobject]@{
        Serial        = $Device.Serial
        State         = $Device.State
        Healthy       = $true
        Reason        = ""
        InstanceIndex = $instanceInfo.InstanceIndex
        InstanceName  = $instanceInfo.InstanceName
        DisplayName   = $instanceInfo.DisplayName
    }
}

function Get-AlertStatePath {
    param(
        [string]$ConfigDirectory,
        [hashtable]$Config
    )

    return Resolve-PathFromBase -BaseDirectory $ConfigDirectory -Value (Get-ConfigValue -Config $Config -Key "alert_state_file" -DefaultValue ".\runtime\alert.state.json")
}

function Get-AlertState {
    param([string]$StatePath)

    if (-not (Test-Path -LiteralPath $StatePath)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $StatePath -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json -ErrorAction Stop
    } catch {
        return $null
    }
}

function Set-AlertState {
    param(
        [string]$StatePath,
        [pscustomobject]$State
    )

    $directory = Split-Path -Parent $StatePath
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        Ensure-Directory -Path $directory
    }

    $State | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Clear-AlertState {
    param([string]$StatePath)

    if (Test-Path -LiteralPath $StatePath) {
        Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
    }
}

function Get-ObservedStatus {
    param([pscustomobject]$Summary)

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        return "error"
    }

    if ($Summary.HealthyCount -lt $Summary.ExpectedHealthy) {
        return "unhealthy"
    }

    return "healthy"
}

function Get-StatusDisplayText {
    param([string]$Status)

    switch ($Status) {
        "healthy" { return "正常" }
        "unhealthy" { return "异常" }
        "error" { return "错误" }
        default { return $Status }
    }
}

function New-AlertState {
    param([string]$ConfirmedStatus = "unknown")

    return [pscustomobject]@{
        ConfirmedStatus          = $ConfirmedStatus
        ConsecutiveHealthyCount  = 0
        ConsecutiveUnhealthyCount = 0
        LastObservedStatus       = ""
        LastNotifiedAt           = ""
    }
}

function Normalize-AlertState {
    param([object]$State)

    if (-not $State) {
        return New-AlertState
    }

    return [pscustomobject]@{
        ConfirmedStatus           = if ([string]::IsNullOrWhiteSpace($State.ConfirmedStatus)) { "unknown" } else { [string]$State.ConfirmedStatus }
        ConsecutiveHealthyCount   = if ($null -eq $State.ConsecutiveHealthyCount) { 0 } else { [int]$State.ConsecutiveHealthyCount }
        ConsecutiveUnhealthyCount = if ($null -eq $State.ConsecutiveUnhealthyCount) { 0 } else { [int]$State.ConsecutiveUnhealthyCount }
        LastObservedStatus        = if ($null -eq $State.LastObservedStatus) { "" } else { [string]$State.LastObservedStatus }
        LastNotifiedAt            = if ($null -eq $State.LastNotifiedAt) { "" } else { [string]$State.LastNotifiedAt }
    }
}

function Reset-AlertCounters {
    param([pscustomobject]$State)

    $State.ConsecutiveHealthyCount = 0
    $State.ConsecutiveUnhealthyCount = 0
    $State.LastObservedStatus = ""
}

function Get-AlertDecision {
    param(
        [pscustomobject]$Summary,
        [string]$StatePath,
        [int]$ConsecutiveCount
    )

    $now = Get-Date
    $observedStatus = Get-ObservedStatus -Summary $Summary
    $state = Normalize-AlertState -State (Get-AlertState -StatePath $StatePath)
    $requiredCount = [Math]::Max($ConsecutiveCount, 1)

    if ($observedStatus -eq "healthy") {
        $state.ConsecutiveHealthyCount += 1
        $state.ConsecutiveUnhealthyCount = 0
    } elseif ($observedStatus -eq "unhealthy") {
        $state.ConsecutiveUnhealthyCount += 1
        $state.ConsecutiveHealthyCount = 0
    } else {
        Reset-AlertCounters -State $state
        Set-AlertState -StatePath $StatePath -State $state
        return [pscustomobject]@{
            State        = $state
            Observed     = $observedStatus
            ShouldNotify = $false
            LogMessage   = "本轮检测异常，不参与状态确认"
            MailSubject  = ""
            MailBodyTag  = ""
        }
    }

    $state.LastObservedStatus = $observedStatus
    $currentCount = if ($observedStatus -eq "healthy") { $state.ConsecutiveHealthyCount } else { $state.ConsecutiveUnhealthyCount }
    $progressText = "$currentCount/$requiredCount"

    if ($state.ConfirmedStatus -eq "unknown") {
        if ($observedStatus -eq "healthy" -and $currentCount -eq 1) {
            $state.ConfirmedStatus = "healthy"
            $state.LastNotifiedAt = ""
            Set-AlertState -StatePath $StatePath -State $state
            return [pscustomobject]@{
                State        = $state
                Observed     = $observedStatus
                ShouldNotify = $false
                LogMessage   = "首次记录状态：正常"
                MailSubject  = ""
                MailBodyTag  = ""
            }
        }

        if ($currentCount -lt $requiredCount) {
            Set-AlertState -StatePath $StatePath -State $state
            return [pscustomobject]@{
                State        = $state
                Observed     = $observedStatus
                ShouldNotify = $false
                LogMessage   = "首次状态确认中：$((Get-StatusDisplayText -Status $observedStatus))，连续次数=$progressText"
                MailSubject  = ""
                MailBodyTag  = ""
            }
        }

        $state.ConfirmedStatus = $observedStatus
        $state.LastNotifiedAt = $now.ToString("o")
        Set-AlertState -StatePath $StatePath -State $state
        return [pscustomobject]@{
            State        = $state
            Observed     = $observedStatus
            ShouldNotify = $true
            LogMessage   = "首次异常状态已确认：$((Get-StatusDisplayText -Status $observedStatus))"
            MailSubject  = "初始 -> $((Get-StatusDisplayText -Status $observedStatus))"
            MailBodyTag  = "状态异常"
        }
    }

    if ($observedStatus -eq $state.ConfirmedStatus) {
        Set-AlertState -StatePath $StatePath -State $state
        return [pscustomobject]@{
            State        = $state
            Observed     = $observedStatus
            ShouldNotify = $false
            LogMessage   = ""
            MailSubject  = ""
            MailBodyTag  = ""
        }
    }

    if ($currentCount -lt $requiredCount) {
        Set-AlertState -StatePath $StatePath -State $state
        return [pscustomobject]@{
            State        = $state
            Observed     = $observedStatus
            ShouldNotify = $false
            LogMessage   = "状态切换确认中：$((Get-StatusDisplayText -Status $state.ConfirmedStatus)) -> $((Get-StatusDisplayText -Status $observedStatus))，连续次数=$progressText"
            MailSubject  = ""
            MailBodyTag  = ""
        }
    }

    $previousStatus = $state.ConfirmedStatus
    $state.ConfirmedStatus = $observedStatus
    $state.LastNotifiedAt = $now.ToString("o")
    Set-AlertState -StatePath $StatePath -State $state

    $mailBodyTag = if ($observedStatus -eq "healthy") { "已恢复正常" } else { "状态异常" }
    $mailSubject = "{0} -> {1}" -f (Get-StatusDisplayText -Status $previousStatus), (Get-StatusDisplayText -Status $observedStatus)

    return [pscustomobject]@{
        State        = $state
        Observed     = $observedStatus
        ShouldNotify = $true
        LogMessage   = "状态变化已确认：$mailSubject"
        MailSubject  = $mailSubject
        MailBodyTag  = $mailBodyTag
    }
}

function Get-SummaryStatusText {
    param([string]$Status)

    switch ($Status) {
        "healthy" { return "正常" }
        "unhealthy" { return "异常" }
        "error" { return "错误" }
        default { return $Status }
    }
}

function Send-AlertMail {
    param(
        [pscustomobject]$Summary,
        [hashtable]$Config,
        [pscustomobject]$AlertDecision
    )

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        return
    }

    if (-not $AlertDecision.ShouldNotify) {
        return
    }

    $mailEnabled = (Get-ConfigValue -Config $Config -Key "mail_enabled" -DefaultValue "true").ToLowerInvariant()
    if ($mailEnabled -ne "true") {
        Write-MonitorLine -Message ("[{0}] [INFO] 邮件通知未开启" -f (Get-LogTimestamp))
        return
    }

    $smtpHost = Get-ConfigValue -Config $Config -Key "mail_smtp_host" -DefaultValue "smtp.qq.com"
    $smtpPort = [int](Get-ConfigValue -Config $Config -Key "mail_smtp_port" -DefaultValue "587")
    $smtpSsl = (Get-ConfigValue -Config $Config -Key "mail_smtp_ssl" -DefaultValue "true").ToLowerInvariant() -eq "true"
    $mailUser = Normalize-MailAddress -Address (Get-ConfigValue -Config $Config -Key "mail_user")
    $mailPassword = Get-ConfigValue -Config $Config -Key "mail_password"
    $mailTo = @(
        Get-ConfigList -Config $Config -Key "mail_to" |
            ForEach-Object { Normalize-MailAddress -Address $_ } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
    $subjectPrefix = Get-ConfigValue -Config $Config -Key "mail_subject_prefix" -DefaultValue "[adb-monitor]"
    $timeoutSeconds = [int](Get-ConfigValue -Config $Config -Key "mail_timeout_seconds" -DefaultValue "20")

    if ([string]::IsNullOrWhiteSpace($mailUser) -or [string]::IsNullOrWhiteSpace($mailPassword) -or $mailTo.Count -eq 0) {
        Write-MonitorLine -Message ("[{0}] [ERROR] 邮件配置不完整或邮箱格式不正确" -f (Get-LogTimestamp)) -ForegroundColor Red
        return
    }

    $subject = "{0} [{1}] 状态变更：{2}" -f $subjectPrefix, $Summary.ComputerName, $AlertDecision.MailSubject
    $statusText = Get-SummaryStatusText -Status $Summary.Status
    $bodyLines = New-Object System.Collections.Generic.List[string]
    $bodyLines.Add("时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $bodyLines.Add("电脑名称：$($Summary.ComputerName)")
    $bodyLines.Add("通知类型：$($AlertDecision.MailBodyTag)")
    $bodyLines.Add("状态：$statusText")
    $bodyLines.Add("健康数量：$($Summary.HealthyCount)/$($Summary.ExpectedHealthy)")
    $bodyLines.Add("总数：$($Summary.TotalCount)")
    $bodyLines.Add("模拟器路径：$($Summary.LdPlayerPath)")
    $bodyLines.Add("ADB路径：$($Summary.AdbPath)")
    $bodyLines.Add("设备明细：")
    if ($Summary.NoDevicesFound) {
        $bodyLines.Add(" - 当前未发现已连接的模拟器设备")
    }
    foreach ($device in @($Summary.UnhealthyDevices)) {
        $displayName = if ([string]::IsNullOrWhiteSpace($device.DisplayName)) { $device.Serial } else { $device.DisplayName }
        $bodyLines.Add(" - $displayName $(Format-DeviceReason -Reason $device.Reason)")
    }
    $bodyLines.Add("")
    $bodyLines.Add("状态变化：$($AlertDecision.MailSubject)")

    $message = $null
    $client = $null
    try {
        $message = New-Object System.Net.Mail.MailMessage
        $message.From = New-Object System.Net.Mail.MailAddress($mailUser)
        foreach ($recipient in $mailTo) {
            [void]$message.To.Add($recipient)
        }
        $message.Subject = $subject
        $message.Body = ($bodyLines -join [Environment]::NewLine)
        $message.SubjectEncoding = [System.Text.Encoding]::UTF8
        $message.BodyEncoding = [System.Text.Encoding]::UTF8
        $message.IsBodyHtml = $false

        $client = New-Object System.Net.Mail.SmtpClient($smtpHost, $smtpPort)
        $client.EnableSsl = $smtpSsl
        $client.UseDefaultCredentials = $false
        $client.Credentials = New-Object System.Net.NetworkCredential($mailUser, $mailPassword)
        $client.Timeout = [Math]::Max($timeoutSeconds, 1) * 1000
        $client.Send($message)

        Write-MonitorLine -Message ("[{0}] [INFO] 告警邮件已发送，主题={1}，收件人={2}" -f (Get-LogTimestamp), $subject, ($mailTo -join ";")) -ForegroundColor Cyan
    } catch {
        Write-MonitorLine -Message ("[{0}] [ERROR] 告警邮件发送失败：{1}" -f (Get-LogTimestamp), $_.Exception.Message) -ForegroundColor Red
    } finally {
        if ($message) {
            $message.Dispose()
        }
        if ($client) {
            $client.Dispose()
        }
    }
}

function Write-LogLines {
    param([string[]]$Lines)

    foreach ($line in $Lines) {
        if ($null -eq $line -or $line -eq "") {
            Write-MonitorBlankLine
            continue
        }

        Write-MonitorLine -Message $line -ForegroundColor (Get-MonitorLineColor -Message $line)
    }
}

function Format-DeviceReason {
    param([string]$Reason)

    switch ($Reason) {
        "boot_not_completed" { return "启动未完成" }
        "no_devices_found" { return "未发现设备" }
        default {
            if ($Reason -like "state=*") {
                return "状态=$($Reason.Substring(6))"
            }
            return $Reason
        }
    }
}

function New-RunSummary {
    param(
        [datetime]$RunTime,
        [string]$ComputerName,
        [string]$ConfigFilePath,
        [string]$LogFilePath,
        [string]$ResolvedAdbPath,
        [string]$ResolvedLdPlayerPath,
        [int]$ExpectedHealthyDevices,
        [object[]]$Checks,
        [string]$ErrorMessage,
        [string]$EventMessage = ""
    )

    $healthyDevices = @()
    $unhealthyDevices = @()
    $displayTotalCount = 0
    $noDevicesFound = $false

    if ($Checks) {
        $healthyDevices = @($Checks | Where-Object { $_.Healthy } | ForEach-Object { $_.DisplayName })
        $unhealthyDevices = @($Checks | Where-Object { -not $_.Healthy })
    }

    $displayTotalCount = $Checks.Count

    if ($Checks.Count -eq 0 -and [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $noDevicesFound = $true
    }

    $status = "healthy"
    if ($unhealthyDevices.Count -gt 0 -or $noDevicesFound) {
        $status = "unhealthy"
    }
    if (-not [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $status = "error"
    }

    return [pscustomobject]@{
        Timestamp        = Get-LogTimestamp -Date $RunTime
        ComputerName     = $ComputerName
        ConfigFilePath   = $ConfigFilePath
        LogFilePath      = $LogFilePath
        AdbPath          = $ResolvedAdbPath
        LdPlayerPath     = $ResolvedLdPlayerPath
        ExpectedHealthy  = $ExpectedHealthyDevices
        Status           = $status
        TotalCount       = $displayTotalCount
        HealthyCount     = $healthyDevices.Count
        UnhealthyCount   = $unhealthyDevices.Count
        HealthyDevices   = $healthyDevices
        UnhealthyDevices = $unhealthyDevices
        NoDevicesFound   = $noDevicesFound
        EventMessage     = $EventMessage
        ErrorMessage     = $ErrorMessage
    }
}

function Convert-SummaryToLogLines {
    param([pscustomobject]$Summary)

    $prefix = "[{0}]" -f $Summary.Timestamp
    $lines = New-Object System.Collections.Generic.List[string]

    $resultLevel = if ($Summary.Status -eq "healthy") { "INFO" } else { "ERROR" }

    $statusText = switch ($Summary.Status) {
        "healthy" { "正常" }
        "unhealthy" { "异常" }
        "error" { "错误" }
        default { $Summary.Status }
    }

    $lines.Add("$prefix [INFO] -------- 监控开始 --------")
    $lines.Add("$prefix [INFO] 电脑名称=$($Summary.ComputerName)")
    $lines.Add("$prefix [INFO] 配置=$($Summary.ConfigFilePath)")
    $lines.Add("$prefix [INFO] 模拟器路径=$($Summary.LdPlayerPath)")
    $lines.Add("$prefix [INFO] ADB路径=$($Summary.AdbPath)")

    $statusDetail = "状态=$statusText 健康=$($Summary.HealthyCount)/$($Summary.ExpectedHealthy) ADB设备=$($Summary.TotalCount)"
    if ($Summary.UnhealthyCount -gt 0) {
        $statusDetail = "$statusDetail 异常设备=$($Summary.UnhealthyCount)"
    }

    $reason = ""
    if ($Summary.NoDevicesFound) {
        $reason = "未发现已连接的模拟器设备"
    } elseif (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        $reason = "脚本执行异常"
    } elseif ($Summary.Status -eq "unhealthy" -and $Summary.HealthyCount -lt $Summary.ExpectedHealthy) {
        $reason = "健康数量低于期望值"
    } elseif ($Summary.Status -eq "healthy") {
        $reason = "正常"
    }

    if (-not [string]::IsNullOrWhiteSpace($reason)) {
        $statusDetail = "$statusDetail 原因=$reason"
    }

    $lines.Add("$prefix [$resultLevel] $statusDetail")

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        $lines.Add("$prefix [ERROR] $($Summary.ErrorMessage)")
    }

    if (-not [string]::IsNullOrWhiteSpace($Summary.EventMessage)) {
        $lines.Add("$prefix [INFO] $($Summary.EventMessage)")
    }

    return $lines
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$defaultConfigPath = Get-DefaultConfigPath -ScriptRoot $scriptRoot
$config = Get-MergedConfigMap -DefaultConfigPath $defaultConfigPath -OverrideConfigPath $configFullPath

$script:CommonLdPlayerDirs = @(
    foreach ($item in (Get-ConfigList -Config $config -Key "common_ldplayer_dirs")) {
        Resolve-PathFromBase -BaseDirectory $configDirectory -Value $item
    }
)
$script:RegistryRoots = @(Get-ConfigList -Config $config -Key "registry_roots")
$script:RegistryValueNames = @(Get-ConfigList -Config $config -Key "registry_value_names")
$script:ExternalCommandTimeoutSeconds = [int](Get-ConfigValue -Config $config -Key "external_command_timeout_seconds" -DefaultValue "20")
$script:AdbDevicesTimeoutSeconds = [int](Get-ConfigValue -Config $config -Key "adb_devices_timeout_seconds" -DefaultValue "10")
$script:AdbShellTimeoutSeconds = [int](Get-ConfigValue -Config $config -Key "adb_shell_timeout_seconds" -DefaultValue "15")
$script:BootCheckAttempts = [int](Get-ConfigValue -Config $config -Key "boot_check_attempts" -DefaultValue "3")
$script:BootCheckDelaySeconds = [int](Get-ConfigValue -Config $config -Key "boot_check_delay_seconds" -DefaultValue "1")

$ldPlayerHint = $LdPlayerPath
if ([string]::IsNullOrWhiteSpace($ldPlayerHint)) {
    $ldPlayerHint = Get-ConfigValue -Config $config -Key "ldplayer_path"
}
if (-not [string]::IsNullOrWhiteSpace($ldPlayerHint)) {
    $ldPlayerHint = Resolve-PathFromBase -BaseDirectory $configDirectory -Value $ldPlayerHint
}

$logDirectory = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
$logFileName = Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log"
$retentionDays = [int](Get-ConfigValue -Config $config -Key "log_retention_days" -DefaultValue "7")
$maxLogSizeMb = [int](Get-ConfigValue -Config $config -Key "log_max_size_mb" -DefaultValue "50")
$expectedHealthyDevices = [int](Get-ConfigValue -Config $config -Key "expected_healthy_devices" -DefaultValue "27")
$alertConsecutiveCount = [int](Get-ConfigValue -Config $config -Key "alert_consecutive_count" -DefaultValue "20")
$alertStatePath = Get-AlertStatePath -ConfigDirectory $configDirectory -Config $config
$computerName = Get-ConfigValue -Config $config -Key "computer_name" -DefaultValue $env:COMPUTERNAME

if ($script:RegistryRoots.Count -eq 0) {
    throw "registry_roots must not be empty."
}
if ($script:RegistryValueNames.Count -eq 0) {
    throw "registry_value_names must not be empty."
}
if ($script:CommonLdPlayerDirs.Count -eq 0) {
    throw "common_ldplayer_dirs must not be empty."
}
if ($script:ExternalCommandTimeoutSeconds -lt 1) {
    throw "external_command_timeout_seconds must be >= 1."
}
if ($script:AdbDevicesTimeoutSeconds -lt 1) {
    throw "adb_devices_timeout_seconds must be >= 1."
}
if ($script:AdbShellTimeoutSeconds -lt 1) {
    throw "adb_shell_timeout_seconds must be >= 1."
}
if ($script:BootCheckAttempts -lt 1) {
    throw "boot_check_attempts must be >= 1."
}
if ($script:BootCheckDelaySeconds -lt 0) {
    throw "boot_check_delay_seconds must be >= 0."
}
if ($retentionDays -lt 1) {
    throw "log_retention_days must be >= 1."
}
if ($maxLogSizeMb -lt 1) {
    throw "log_max_size_mb must be >= 1."
}
if ($expectedHealthyDevices -lt 1) {
    throw "expected_healthy_devices must be >= 1."
}
if ($alertConsecutiveCount -lt 1) {
    throw "alert_consecutive_count must be >= 1."
}
if ([string]::IsNullOrWhiteSpace($computerName)) {
    throw "computer_name must not be empty."
}

Ensure-Directory -Path $logDirectory
$logFilePath = Get-DatedLogFilePath -DirectoryPath $logDirectory -BaseFileName $logFileName
Reset-LogIfOversized -LogFilePath $logFilePath -MaxSizeMb $maxLogSizeMb
$script:MonitorLogFilePath = $logFilePath

$runTime = Get-Date
$resolvedAdb = ""
$resolvedLdPlayerPath = ""
$ldPlayerInstances = @()
$checks = @()
$errorMessage = ""
$exitCode = 0

try {
    $resolvedLdPlayerPath = Resolve-LDPlayerPath -Hint $ldPlayerHint -ResolvedAdbPath ""
    $adbHint = $AdbPath
    if ([string]::IsNullOrWhiteSpace($adbHint) -and -not [string]::IsNullOrWhiteSpace($resolvedLdPlayerPath)) {
        $adbHint = Join-Path $resolvedLdPlayerPath "adb.exe"
    }

    $resolvedAdb = Resolve-AdbPath -Hint $adbHint
    if (-not $resolvedAdb) {
        throw "adb.exe not found under ldplayer_path or PATH."
    }

    if ([string]::IsNullOrWhiteSpace($resolvedLdPlayerPath)) {
        $resolvedLdPlayerPath = Resolve-LDPlayerPath -Hint $ldPlayerHint -ResolvedAdbPath $resolvedAdb
    }

    $ldPlayerInstances = @(Get-LDPlayerInstances -LdPlayerPath $resolvedLdPlayerPath)
    $devices = @(Get-Devices -Adb $resolvedAdb)
    foreach ($device in $devices) {
        $checks += Test-DeviceHealth -Adb $resolvedAdb -Device $device -LdPlayerInstances $ldPlayerInstances
    }

    if (@($checks | Where-Object { -not $_.Healthy }).Count -gt 0 -or $checks.Count -eq 0) {
        $exitCode = 1
    }
} catch {
    $errorMessage = $_.Exception.Message
    $exitCode = 1
}

$summary = New-RunSummary -RunTime $runTime -ComputerName $computerName -ConfigFilePath $configFullPath -LogFilePath $logFilePath -ResolvedAdbPath $resolvedAdb -ResolvedLdPlayerPath $resolvedLdPlayerPath -ExpectedHealthyDevices $expectedHealthyDevices -Checks $checks -ErrorMessage $errorMessage
$alertDecision = $null
if ([string]::IsNullOrWhiteSpace($summary.ErrorMessage)) {
    $alertDecision = Get-AlertDecision -Summary $summary -StatePath $alertStatePath -ConsecutiveCount $alertConsecutiveCount
    if ($alertDecision -and -not [string]::IsNullOrWhiteSpace($alertDecision.LogMessage)) {
        $summary.EventMessage = $alertDecision.LogMessage
    }
}
$logLines = Convert-SummaryToLogLines -Summary $summary
Write-LogLines -Lines $logLines
if ($alertDecision) {
    Send-AlertMail -Summary $summary -Config $config -AlertDecision $alertDecision
}
Write-MonitorLine -Message ("[{0}] [INFO] -------- 监控结束 --------" -f $summary.Timestamp)
Remove-StaleLogs -DirectoryPath $logDirectory -BaseFileName $logFileName -CurrentLogFileName (Split-Path -Leaf $logFilePath) -RetentionDays $retentionDays
exit $exitCode

