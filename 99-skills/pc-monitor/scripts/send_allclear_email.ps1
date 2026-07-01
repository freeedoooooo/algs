#Requires -Version 5.1
$smtpHost = "smtp.qq.com"
$smtpPort = 587
$smtpUser = "2504601121@qq.com"
$smtpPass = "tibskdiwwcvoecge"
$mailTo = @("195836303@qq.com", "3198127828@qq.com")
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$subject = "[PC-Monitor] All Clear - 31 PCs Online"

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("<html><body style='font-family:Microsoft YaHei,sans-serif;color:#333;line-height:1.6;'>")
[void]$sb.AppendLine("<h2 style='color:#28a745;margin-bottom:4px;'>PC Online Report (All Clear)</h2>")
[void]$sb.AppendLine("<p style='color:#666;'>Time: $timestamp</p>")
[void]$sb.AppendLine("<p style='color:#28a745;font-weight:bold;'>All 31 PCs are online and healthy.</p>")
[void]$sb.AppendLine("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-size:14px;'>")
[void]$sb.AppendLine("<tr style='background:#343a40;color:#fff;'><th>Group</th><th>Name</th><th>IP</th><th>Status</th><th>Detail</th></tr>")

$data = @(
"group1|1|192.168.1.11|ONLINE|[OK/OK]",
"group1|2|192.168.1.22|ONLINE|[OK/OK]",
"group1|3|192.168.1.33|ONLINE|[OK/OK]",
"group1|4|192.168.1.44|ONLINE|[OK/OK]",
"group1|5|192.168.1.55|ONLINE|[OK/OK]",
"group1|6|192.168.1.66|ONLINE|[OK/OK]",
"group1|7|192.168.1.77|ONLINE|[OK/OK]",
"group1|8|192.168.1.88|ONLINE|[OK/OK]",
"group1|9|192.168.1.119|ONLINE|[OK/OK]",
"group1|10|192.168.1.100|ONLINE|[OK/OK]",
"group2|11|192.168.1.101|ONLINE|[NO-ICMP/OK]",
"group2|12|192.168.1.102|ONLINE|[OK/OK]",
"group2|13|192.168.1.103|ONLINE|[NO-ICMP/OK]",
"group2|14|192.168.1.104|ONLINE|[OK/OK]",
"group2|15|192.168.1.105|ONLINE|[NO-ICMP/OK]",
"group2|16|192.168.1.106|ONLINE|[OK/OK]",
"group2|17|192.168.1.107|ONLINE|[OK/OK]",
"group2|18|192.168.1.108|ONLINE|[OK/OK]",
"group2|19|192.168.1.109|ONLINE|[OK/OK]",
"group2|20|192.168.1.200|ONLINE|[NO-ICMP/OK]",
"group3|21|192.168.1.211|ONLINE|[OK/OK]",
"group3|22|192.168.1.222|ONLINE|[OK/OK]",
"group3|23|192.168.1.203|ONLINE|[OK/OK]",
"group3|24|192.168.1.204|ONLINE|[OK/OK]",
"group3|25|192.168.1.205|ONLINE|[OK/OK]",
"group3|26|192.168.1.206|ONLINE|[OK/OK]",
"group3|27|192.168.1.207|ONLINE|[OK/OK]",
"group3|28|192.168.1.208|ONLINE|[OK/OK]",
"group3|29|192.168.1.129|ONLINE|[OK/OK]",
"group3|30|192.168.1.130|ONLINE|[OK/OK]",
"group3|31|192.168.1.131|ONLINE|[OK/OK]"
)

$idx = 0
foreach ($d in $data) {
    $parts = $d.Split("|")
    $bg = if ($idx % 2 -eq 0) { "#ffffff" } else { "#f8f9fa" }
    [void]$sb.AppendLine("<tr style='background:$bg;'><td>$($parts[0])</td><td>$($parts[1])</td><td>$($parts[2])</td><td style='color:#28a745;font-weight:bold;'>$($parts[3])</td><td>$($parts[4])</td></tr>")
    $idx++
}

[void]$sb.AppendLine("</table>")
[void]$sb.AppendLine("<p style='margin-top:16px;padding:10px;background:#f8f9fa;border-radius:4px;'>Summary: ONLINE 31 | HALF 0 | OFFLINE 0 | TOTAL 31</p>")
[void]$sb.AppendLine("</body></html>")

$body = $sb.ToString()

try {
    $smtpClient = New-Object System.Net.Mail.SmtpClient($smtpHost, $smtpPort)
    $smtpClient.EnableSsl = $true
    $smtpClient.Credentials = New-Object System.Net.NetworkCredential($smtpUser, $smtpPass)
    $mail = New-Object System.Net.Mail.MailMessage
    $mail.From = $smtpUser
    foreach ($addr in $mailTo) { $mail.To.Add($addr) }
    $mail.Subject = $subject
    $mail.Body = $body
    $mail.BodyEncoding = [System.Text.Encoding]::UTF8
    $mail.SubjectEncoding = [System.Text.Encoding]::UTF8
    $mail.IsBodyHtml = $true
    $smtpClient.Send($mail)
    $mail.Dispose()
    $smtpClient.Dispose()
    Write-Host "Email sent OK"
} catch {
    Write-Host "Email failed: $($_.Exception.Message)"
}