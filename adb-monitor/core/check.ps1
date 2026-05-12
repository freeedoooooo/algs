param(
    [string]$ConfigPath = "..\monitor.config",
    [string]$AdbPath = "",
    [string]$LdPlayerPath = ""
)

$ErrorActionPreference = "Stop"
$script:MonitorLogFilePath = ""

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
    Write-Host ""

    if (-not [string]::IsNullOrWhiteSpace($script:MonitorLogFilePath)) {
        Add-Content -LiteralPath $script:MonitorLogFilePath -Value "" -Encoding UTF8
    }
}

function Get-LogBaseName {
    param([string]$FileName)

    $name = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    if ([string]::IsNullOrWhiteSpace($name)) {
        return "monitor"
    }

    return $name
}

function Get-DatedLogFilePath {
    param(
        [string]$DirectoryPath,
        [string]$BaseFileName,
        [datetime]$Date = (Get-Date)
    )

    $baseName = Get-LogBaseName -FileName $BaseFileName
    $dateSuffix = $Date.ToString("yyyyMMdd")
    return Join-Path $DirectoryPath ("{0}-{1}.log" -f $baseName, $dateSuffix)
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

function Get-ConfigList {
    param(
        [hashtable]$Config,
        [string]$Key
    )

    $rawValue = Get-ConfigValue -Config $Config -Key $Key
    if ([string]::IsNullOrWhiteSpace($rawValue)) {
        return @()
    }

    return @(
        $rawValue.Split(";") |
            ForEach-Object { $_.Trim() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    )
}

function Resolve-PathFromBase {
    param(
        [string]$BaseDirectory,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $Value))
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

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        [void](New-Item -Path $Path -ItemType Directory -Force)
    }
}

function Reset-LogIfOversized {
    param(
        [string]$LogFilePath,
        [int]$MaxSizeMb
    )

    if (-not (Test-Path -LiteralPath $LogFilePath)) {
        return
    }

    $maxBytes = $MaxSizeMb * 1MB
    if ($maxBytes -lt 1MB) {
        $maxBytes = 1MB
    }

    $logFile = Get-Item -LiteralPath $LogFilePath
    if ($logFile.Length -lt $maxBytes) {
        return
    }

    Remove-Item -LiteralPath $LogFilePath -Force
}

function Remove-StaleLogs {
    param(
        [string]$DirectoryPath,
        [string]$BaseFileName,
        [string]$CurrentLogFileName,
        [int]$RetentionDays
    )

    $cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
    $baseName = Get-LogBaseName -FileName $BaseFileName
    Get-ChildItem -LiteralPath $DirectoryPath -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "$baseName*.log" -and
            $_.Name -ne $CurrentLogFileName -and
            $_.LastWriteTime -lt $cutoff
        } |
        Remove-Item -Force -ErrorAction SilentlyContinue
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
        [datetime]$LastAlertAt
    )

    $directory = Split-Path -Parent $StatePath
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        Ensure-Directory -Path $directory
    }

    $payload = [pscustomobject]@{
        LastAlertAt = $LastAlertAt.ToString("o")
    }

    $payload | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Clear-AlertState {
    param([string]$StatePath)

    if (Test-Path -LiteralPath $StatePath) {
        Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
    }
}

function Test-AlertCooldownPassed {
    param(
        [string]$StatePath,
        [int]$CooldownMinutes
    )

    if ($CooldownMinutes -lt 1) {
        return $true
    }

    $state = Get-AlertState -StatePath $StatePath
    if (-not $state -or [string]::IsNullOrWhiteSpace($state.LastAlertAt)) {
        return $true
    }

    try {
        $lastAlertAt = [datetime]$state.LastAlertAt
    } catch {
        return $true
    }

    $elapsedMinutes = (New-TimeSpan -Start $lastAlertAt -End (Get-Date)).TotalMinutes
    return ($elapsedMinutes -ge $CooldownMinutes)
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
        [string]$StatePath,
        [int]$CooldownMinutes
    )

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($Summary.AlertMessage)) {
        Clear-AlertState -StatePath $StatePath
        return
    }

    $mailEnabled = (Get-ConfigValue -Config $Config -Key "mail_enabled" -DefaultValue "true").ToLowerInvariant()
    if ($mailEnabled -ne "true") {
        Write-MonitorLine -Message ("[{0}] [INFO] 邮件通知未开启" -f (Get-Date).ToString("o"))
        return
    }

    if (-not (Test-AlertCooldownPassed -StatePath $StatePath -CooldownMinutes $CooldownMinutes)) {
        Write-MonitorLine -Message ("[{0}] [INFO] 告警邮件处于冷却期，本次跳过发送" -f (Get-Date).ToString("o"))
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
        Write-MonitorLine -Message ("[{0}] [ERROR] 邮件配置不完整或邮箱格式不正确" -f (Get-Date).ToString("o")) -ForegroundColor Red
        return
    }

    $subject = "{0} 模拟器告警 {1}/{2}" -f $subjectPrefix, $Summary.HealthyCount, $Summary.ExpectedHealthy
    $statusText = Get-SummaryStatusText -Status $Summary.Status
    $bodyLines = New-Object System.Collections.Generic.List[string]
    $bodyLines.Add("时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    $bodyLines.Add("状态：$statusText")
    $bodyLines.Add("健康数量：$($Summary.HealthyCount)/$($Summary.ExpectedHealthy)")
    $bodyLines.Add("总数：$($Summary.TotalCount)")
    $bodyLines.Add("模拟器路径：$($Summary.LdPlayerPath)")
    $bodyLines.Add("ADB路径：$($Summary.AdbPath)")
    $bodyLines.Add("设备明细：")
    foreach ($device in @($Summary.UnhealthyDevices)) {
        $displayName = if ([string]::IsNullOrWhiteSpace($device.DisplayName)) { $device.Serial } else { $device.DisplayName }
        $bodyLines.Add(" - $displayName $(Format-DeviceReason -Reason $device.Reason)")
    }
    $bodyLines.Add("")
    $bodyLines.Add("告警信息：$($Summary.AlertMessage)")

    $message = $null
    $client = $null
    try {
        Set-AlertState -StatePath $StatePath -LastAlertAt (Get-Date)

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

        Write-MonitorLine -Message ("[{0}] [INFO] 告警邮件已发送，主题={1}，收件人={2}" -f (Get-Date).ToString("o"), $subject, ($mailTo -join ";")) -ForegroundColor Cyan
    } catch {
        Write-MonitorLine -Message ("[{0}] [ERROR] 告警邮件发送失败：{1}" -f (Get-Date).ToString("o"), $_.Exception.Message) -ForegroundColor Red
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
        [string]$ConfigFilePath,
        [string]$LogFilePath,
        [string]$ResolvedAdbPath,
        [string]$ResolvedLdPlayerPath,
        [int]$ExpectedHealthyDevices,
        [object[]]$Checks,
        [string]$ErrorMessage
    )

    $healthyDevices = @()
    $unhealthyDevices = @()

    if ($Checks) {
        $healthyDevices = @($Checks | Where-Object { $_.Healthy } | ForEach-Object { $_.DisplayName })
        $unhealthyDevices = @($Checks | Where-Object { -not $_.Healthy })
    }

    if ($Checks.Count -eq 0 -and [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $unhealthyDevices = @(
            [pscustomobject]@{
                Serial        = "(none)"
                State         = "missing"
                Healthy       = $false
                Reason        = "no_devices_found"
                DisplayName   = "未发现设备"
            }
        )
    }

    $status = "healthy"
    if ($unhealthyDevices.Count -gt 0) {
        $status = "unhealthy"
    }
    if (-not [string]::IsNullOrWhiteSpace($ErrorMessage)) {
        $status = "error"
    }

    $alertMessage = ""
    if ($ExpectedHealthyDevices -gt 0 -and $healthyDevices.Count -lt $ExpectedHealthyDevices) {
        $alertMessage = "健康设备数量低于预期，预期=$ExpectedHealthyDevices，当前=$($healthyDevices.Count)"
    }

    return [pscustomobject]@{
        Timestamp        = $RunTime.ToString("o")
        ConfigFilePath   = $ConfigFilePath
        LogFilePath      = $LogFilePath
        AdbPath          = $ResolvedAdbPath
        LdPlayerPath     = $ResolvedLdPlayerPath
        ExpectedHealthy  = $ExpectedHealthyDevices
        Status           = $status
        TotalCount       = $Checks.Count
        HealthyCount     = $healthyDevices.Count
        UnhealthyCount   = $unhealthyDevices.Count
        HealthyDevices   = $healthyDevices
        UnhealthyDevices = $unhealthyDevices
        AlertMessage     = $alertMessage
        ErrorMessage     = $ErrorMessage
    }
}

function Convert-SummaryToLogLines {
    param([pscustomobject]$Summary)

    $prefix = "[{0}]" -f $Summary.Timestamp
    $lines = New-Object System.Collections.Generic.List[string]

    $resultLevel = if ($Summary.Status -eq "healthy") { "INFO" } elseif (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage) -or -not [string]::IsNullOrWhiteSpace($Summary.AlertMessage)) { "ERROR" } else { "WARN" }

    $statusText = switch ($Summary.Status) {
        "healthy" { "正常" }
        "unhealthy" { "异常" }
        "error" { "错误" }
        default { $Summary.Status }
    }

    $lines.Add("$prefix [INFO] 监控开始")
    $lines.Add("$prefix [INFO] 配置文件=$($Summary.ConfigFilePath)")
    $lines.Add("$prefix [INFO] 雷电路径=$($Summary.LdPlayerPath)")
    $lines.Add("$prefix [INFO] ADB路径=$($Summary.AdbPath)")
    $lines.Add("$prefix [$resultLevel] 状态=$statusText 总数=$($Summary.TotalCount) 健康=$($Summary.HealthyCount) 异常=$($Summary.UnhealthyCount) 预期=$($Summary.ExpectedHealthy)")

    foreach ($device in $Summary.UnhealthyDevices) {
        $displayName = if ([string]::IsNullOrWhiteSpace($device.DisplayName)) { $device.Serial } else { $device.DisplayName }
        $lines.Add("$prefix [WARN] 模拟器 $displayName $(Format-DeviceReason -Reason $device.Reason)")
    }

    if (-not [string]::IsNullOrWhiteSpace($Summary.ErrorMessage)) {
        $lines.Add("$prefix [ERROR] $($Summary.ErrorMessage)")
    }

    if (-not [string]::IsNullOrWhiteSpace($Summary.AlertMessage)) {
        $lines.Add("$prefix [ERROR] $($Summary.AlertMessage)")
    }

    $lines.Add("$prefix [INFO] 日志=$($Summary.LogFilePath)")
    $lines.Add("$prefix [INFO] 监控结束")
    $lines.Add("")
    return $lines
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$config = Get-ConfigMap -Path $configFullPath

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
$alertCooldownMinutes = [int](Get-ConfigValue -Config $config -Key "alert_cooldown_minutes" -DefaultValue "30")
$alertStatePath = Get-AlertStatePath -ConfigDirectory $configDirectory -Config $config

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
if ($alertCooldownMinutes -lt 0) {
    throw "alert_cooldown_minutes must be >= 0."
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

$summary = New-RunSummary -RunTime $runTime -ConfigFilePath $configFullPath -LogFilePath $logFilePath -ResolvedAdbPath $resolvedAdb -ResolvedLdPlayerPath $resolvedLdPlayerPath -ExpectedHealthyDevices $expectedHealthyDevices -Checks $checks -ErrorMessage $errorMessage
$logLines = Convert-SummaryToLogLines -Summary $summary
Write-LogLines -Lines $logLines
Send-AlertMail -Summary $summary -Config $config -StatePath $alertStatePath -CooldownMinutes $alertCooldownMinutes
Remove-StaleLogs -DirectoryPath $logDirectory -BaseFileName $logFileName -CurrentLogFileName (Split-Path -Leaf $logFilePath) -RetentionDays $retentionDays
exit $exitCode

