#Requires -Version 5.1
param(
    [Parameter(Mandatory=$true)]
    [string]$ConfigPath,

    [Parameter(Mandatory=$false)]
    [string]$Group,

    [Parameter(Mandatory=$false)]
    [string]$MachineName,

    [Parameter(Mandatory=$false)]
    [int]$Timeout = 1000,

    [Parameter(Mandatory=$false)]
    [switch]$Notify
)

function Parse-MachineConfig {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Error "Config file not found: $Path"
        exit 1
    }
    [xml]$xml = Get-Content $Path -Encoding UTF8
    $machines = @()
    foreach ($groupNode in $xml.root.Group) {
        foreach ($machine in $groupNode.Machine) {
            $machines += [PSCustomObject]@{
                GroupName = $groupNode.Name
                Name      = $machine.Name
                IP        = $machine.IP
                Port      = $machine.Port
                UserName  = $machine.UserName
                Mac       = $machine.Mac
            }
        }
    }
    return $machines
}

function Test-Ping {
    param([string]$IP, [int]$TimeoutMs)
    try {
        $null = Test-Connection -ComputerName $IP -Count 1 -TimeoutMs $TimeoutMs -ErrorAction Stop
        return $true
    }
    catch { return $false }
}

function Test-Port {
    param([string]$IP, [int]$Port, [int]$TimeoutMs)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $connect = $tcp.BeginConnect($IP, $Port, $null, $null)
        $wait = $connect.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if ($wait) {
            try { $tcp.EndConnect($connect); $tcp.Close(); return $true }
            catch { $tcp.Close(); return $false }
        }
        else { $tcp.Close(); return $false }
    }
    catch { return $false }
}

function Send-AlertEmail {
    param(
        [string[]]$To,
        [string]$Subject,
        [string]$Body
    )

    $smtpHost = "smtp.qq.com"
    $smtpPort = 587
    $smtpUser = "2504601121@qq.com"
    $smtpPass = "tibskdiwwcvoecge"

    try {
        $smtpClient = New-Object System.Net.Mail.SmtpClient($smtpHost, $smtpPort)
        $smtpClient.EnableSsl = $true
        $smtpClient.Credentials = New-Object System.Net.NetworkCredential($smtpUser, $smtpPass)

        $mail = New-Object System.Net.Mail.MailMessage
        $mail.From = $smtpUser
        foreach ($addr in $To) {
            $mail.To.Add($addr)
        }
        $mail.Subject = $Subject
        $mail.Body = $Body
        $mail.BodyEncoding = [System.Text.Encoding]::UTF8
        $mail.SubjectEncoding = [System.Text.Encoding]::UTF8
        $mail.IsBodyHtml = $true

        $smtpClient.Send($mail)
        $mail.Dispose()
        $smtpClient.Dispose()
        return $true
    }
    catch {
        Write-Warning "Email send failed: $($_.Exception.Message)"
        return $false
    }
}

# --- Main ---

$machines = Parse-MachineConfig -Path $ConfigPath
if ($Group) { $machines = $machines | Where-Object { $_.GroupName -eq $Group } }
if ($MachineName) { $machines = $machines | Where-Object { $_.Name -eq $MachineName } }
if ($machines.Count -eq 0) {
    Write-Host "[WARN] No matching machines found."
    exit 0
}

$onlineCount = 0; $halfCount = 0; $offlineCount = 0
$results = @()
$offlineList = @()

foreach ($pc in $machines) {
    $pingOk = Test-Ping -IP $pc.IP -TimeoutMs $Timeout
    $portOk = Test-Port -IP $pc.IP -Port $pc.Port -TimeoutMs $Timeout

    if ($pingOk -and $portOk) {
        $status = "[ONLINE]"; $flag = "[OK/OK]"; $color = "Green"; $onlineCount++
    }
    elseif ($pingOk) {
        $status = "[HALF]"; $flag = "[OK/FAIL]"; $color = "Yellow"; $halfCount++
        $offlineList += $pc
    }
    else {
        $status = "[OFFLINE]"; $flag = "[FAIL/-]"; $color = "Red"; $offlineCount++
        $offlineList += $pc
    }

    $results += [PSCustomObject]@{
        Group = $pc.GroupName
        Name  = $pc.Name
        IP    = $pc.IP
        Port  = $pc.Port
        Status = $status
        Detail = $flag
        Color  = $color
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PC Status Report" -ForegroundColor Cyan
Write-Host "  Config: $ConfigPath" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
$results | Format-Table -Property Group, Name, IP, Port, Status, Detail -AutoSize
Write-Host ""
Write-Host "Summary: ONLINE=$onlineCount | HALF=$halfCount | OFFLINE=$offlineCount | TOTAL=$($machines.Count)" -ForegroundColor Cyan
Write-Host ""

# Send email notification when offline machines detected
if ($Notify -and $offlineList.Count -gt 0) {
    $mailTo = @("195836303@qq.com", "3198127828@qq.com")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    $offlineNum = $offlineList.Count
    $totalNum = $machines.Count

    $subject = "[PC-Monitor] $offlineNum offline out of $totalNum"

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine("<html><body style='font-family:Microsoft YaHei,sans-serif;color:#333;line-height:1.6;'>")
    [void]$sb.AppendLine("<h2 style='color:#dc3545;margin-bottom:4px;'>PC Offline Alert</h2>")
    [void]$sb.AppendLine("<p style='color:#666;'>Time: $timestamp</p>")
    [void]$sb.AppendLine("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-size:14px;width:auto;'>")
    [void]$sb.AppendLine("<tr style='background:#343a40;color:#fff;'><th>Group</th><th>Name</th><th>IP</th><th>Status</th><th>Detail</th></tr>")

    $rowIdx = 0
    foreach ($pc in $offlineList) {
        $r = $results | Where-Object { $_.IP -eq $pc.IP }
        $bg = if ($rowIdx % 2 -eq 0) { "#ffffff" } else { "#f8f9fa" }

        if ($r.Status -eq "[OFFLINE]") {
            $sColor = "#dc3545"; $sText = "OFFLINE"
        }
        else {
            $sColor = "#f0ad4e"; $sText = "HALF"
        }

        if ($r.Detail -eq "[OK/FAIL]") {
            $dText = "Ping OK / Port FAIL"
        }
        else {
            $dText = "Ping FAIL / Port FAIL"
        }

        [void]$sb.AppendLine("<tr style='background:$bg;'><td>$($r.Group)</td><td>$($r.Name)</td><td>$($r.IP):$($r.Port)</td><td style='color:$sColor;font-weight:bold;'>$sText</td><td>$dText</td></tr>")
        $rowIdx++
    }

    [void]$sb.AppendLine("</table>")
    [void]$sb.AppendLine("<p style='margin-top:16px;padding:10px;background:#f8f9fa;border-radius:4px;'>Summary: ONLINE $onlineCount | HALF $halfCount | OFFLINE $offlineCount | TOTAL $totalNum</p>")
    [void]$sb.AppendLine("</body></html>")

    $body = $sb.ToString()

    $emailOk = Send-AlertEmail -To $mailTo -Subject $subject -Body $body
    if ($emailOk) {
        Write-Host "[OK] Alert email sent to: $($mailTo -join ', ')" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] Alert email could not be sent." -ForegroundColor Red
    }
}

$json = $results | Select-Object Group, Name, IP, Port, Status, Detail | ConvertTo-Json -Compress
Write-Output $json
