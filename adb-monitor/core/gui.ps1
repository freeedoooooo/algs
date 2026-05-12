[CmdletBinding()]
param(
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
}
$OutputEncoding = [Console]::OutputEncoding

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $projectRoot "monitor.config"
}

function Resolve-PathFromBase {
    param([string]$BaseDirectory, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
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

function Get-LogBaseName {
    param([string]$FileName)
    $name = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    if ([string]::IsNullOrWhiteSpace($name)) { return "monitor" }
    return $name
}

function Get-LatestLogFile {
    param([string]$LogDirectory, [string]$LogFileName)
    if (-not (Test-Path -LiteralPath $LogDirectory)) { return $null }
    $baseName = Get-LogBaseName -FileName $LogFileName
    Get-ChildItem -LiteralPath $LogDirectory -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "$baseName-*.log" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

function Read-LogTail {
    param([string]$LogFilePath, [int]$TailLines = 400)
    if ([string]::IsNullOrWhiteSpace($LogFilePath) -or -not (Test-Path -LiteralPath $LogFilePath)) {
        return @()
    }

    try {
        $lines = Get-Content -LiteralPath $LogFilePath -Tail $TailLines -Encoding UTF8 -ErrorAction Stop
        return @($lines)
    } catch {
        return @("读取日志失败：$($_.Exception.Message)")
    }
}

function Get-RunnerState {
    param([string]$ConfigFullPath)

    $config = Get-ConfigMap -Path $ConfigFullPath
    $configDir = Split-Path -Parent $ConfigFullPath
    $runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDir -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")
    $runnerScript = Join-Path $scriptRoot "runner.ps1"

    if (Test-Path -LiteralPath $runnerPidFile) {
        $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
        $runnerPid = 0
        if ([int]::TryParse($pidText.Trim(), [ref]$runnerPid)) {
            if (Get-Process -Id $runnerPid -ErrorAction SilentlyContinue) {
                return [pscustomobject]@{ Running = $true; Pid = $runnerPid }
            }
        }
    }

    $proc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -match [regex]::Escape($runnerScript) -and
        $_.CommandLine -match [regex]::Escape($ConfigFullPath)
    } | Select-Object -First 1

    if ($proc) {
        return [pscustomobject]@{ Running = $true; Pid = $proc.ProcessId }
    }

    return [pscustomobject]@{ Running = $false; Pid = "" }
}

function Start-Backend {
    param([string]$ConfigFullPath)

    $state = Get-RunnerState -ConfigFullPath $ConfigFullPath
    if ($state.Running) {
        return $state.Pid
    }

    $runnerScript = Join-Path $scriptRoot "runner.ps1"
    $powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
    $process = Start-Process -FilePath $powershellPath -WindowStyle Hidden -PassThru -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $runnerScript,
        "-ConfigPath", $ConfigFullPath
    )

    return $process.Id
}

function Stop-Backend {
    param([string]$ConfigFullPath)

    $config = Get-ConfigMap -Path $ConfigFullPath
    $configDir = Split-Path -Parent $ConfigFullPath
    $runnerPidFile = Resolve-PathFromBase -BaseDirectory $configDir -Value (Get-ConfigValue -Config $config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")
    $runnerScript = Join-Path $scriptRoot "runner.ps1"
    $stopped = $false

    if (Test-Path -LiteralPath $runnerPidFile) {
        $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
        $runnerPid = 0
        if ([int]::TryParse($pidText.Trim(), [ref]$runnerPid)) {
            Stop-Process -Id $runnerPid -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
        Remove-Item -LiteralPath $runnerPidFile -Force -ErrorAction SilentlyContinue
    }

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -match [regex]::Escape($runnerScript) -and
        $_.CommandLine -match [regex]::Escape($ConfigFullPath)
    } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }

    return $stopped
}

function Get-AlertStatePath {
    param([string]$ConfigFullPath)

    $config = Get-ConfigMap -Path $ConfigFullPath
    $configDir = Split-Path -Parent $ConfigFullPath
    return Resolve-PathFromBase -BaseDirectory $configDir -Value (Get-ConfigValue -Config $config -Key "alert_state_file" -DefaultValue ".\runtime\alert.state.json")
}

function Get-CooldownInfo {
    param([string]$ConfigFullPath)

    $config = Get-ConfigMap -Path $ConfigFullPath
    $cooldownMinutes = [int](Get-ConfigValue -Config $config -Key "alert_cooldown_minutes" -DefaultValue "30")
    $statePath = Get-AlertStatePath -ConfigFullPath $ConfigFullPath

    if ($cooldownMinutes -le 0) {
        return [pscustomobject]@{
            Text = "邮件冷却：未启用"
            RemainingSeconds = 0
            LastAlertAt = ""
            StatePath = $statePath
        }
    }

    if (-not (Test-Path -LiteralPath $statePath)) {
        return [pscustomobject]@{
            Text = "邮件冷却：无"
            RemainingSeconds = 0
            LastAlertAt = ""
            StatePath = $statePath
        }
    }

    try {
        $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        return [pscustomobject]@{
            Text = "邮件冷却：状态异常"
            RemainingSeconds = 0
            LastAlertAt = ""
            StatePath = $statePath
        }
    }

    if ([string]::IsNullOrWhiteSpace($state.LastAlertAt)) {
        return [pscustomobject]@{
            Text = "邮件冷却：无"
            RemainingSeconds = 0
            LastAlertAt = ""
            StatePath = $statePath
        }
    }

    try {
        $lastAlertAt = [datetime]$state.LastAlertAt
    } catch {
        return [pscustomobject]@{
            Text = "邮件冷却：状态异常"
            RemainingSeconds = 0
            LastAlertAt = ""
            StatePath = $statePath
        }
    }

    $remaining = [TimeSpan]::FromMinutes($cooldownMinutes) - (New-TimeSpan -Start $lastAlertAt -End (Get-Date))
    $remainingSeconds = [int][Math]::Ceiling([Math]::Max($remaining.TotalSeconds, 0))

    if ($remainingSeconds -le 0) {
        return [pscustomobject]@{
            Text = "邮件冷却：已结束"
            RemainingSeconds = 0
            LastAlertAt = $lastAlertAt.ToString("yyyy-MM-dd HH:mm:ss")
            StatePath = $statePath
        }
    }

    return [pscustomobject]@{
        Text = "邮件冷却：剩余 $(Format-Seconds -TotalSeconds $remainingSeconds)"
        RemainingSeconds = $remainingSeconds
        LastAlertAt = $lastAlertAt.ToString("yyyy-MM-dd HH:mm:ss")
        StatePath = $statePath
    }
}

function Clear-CooldownState {
    param([string]$ConfigFullPath)

    $statePath = Get-AlertStatePath -ConfigFullPath $ConfigFullPath
    if (Test-Path -LiteralPath $statePath) {
        Remove-Item -LiteralPath $statePath -Force -ErrorAction SilentlyContinue
    }
}

function Format-Seconds {
    param([int]$TotalSeconds)

    $seconds = [Math]::Max($TotalSeconds, 0)
    $hours = [int]($seconds / 3600)
    $minutes = [int](($seconds % 3600) / 60)
    $remain = [int]($seconds % 60)
    if ($hours -gt 0) {
        return "{0:D2}:{1:D2}:{2:D2}" -f $hours, $minutes, $remain
    }
    return "{0:D2}:{1:D2}" -f $minutes, $remain
}

function Get-LogLineColor {
    param([string]$Line)

    if ($Line -match '\[ERROR\]') { return [System.Drawing.Color]::Firebrick }
    if ($Line -match '\[WARN\]') { return [System.Drawing.Color]::DarkOrange }
    if ($Line -match '\[STEP\]') { return [System.Drawing.Color]::Teal }
    if ($Line -match '\[INFO\]') { return [System.Drawing.Color]::DimGray }
    return [System.Drawing.Color]::Black
}

function Render-LogLines {
    param(
        [System.Windows.Forms.RichTextBox]$Box,
        [string[]]$Lines
    )

    $Box.Clear()
    if (-not $Lines -or $Lines.Count -eq 0) {
        $Box.SelectionColor = [System.Drawing.Color]::Gray
        $Box.AppendText("暂无日志。" + [Environment]::NewLine)
        return
    }

    foreach ($line in $Lines) {
        $Box.SelectionStart = $Box.TextLength
        $Box.SelectionLength = 0
        $Box.SelectionColor = Get-LogLineColor -Line $line
        $Box.AppendText($line + [Environment]::NewLine)
    }

    $Box.SelectionColor = $Box.ForeColor
    $Box.ScrollToCaret()
}

function Refresh-View {
    $config = Get-ConfigMap -Path $configFullPath
    $logDirectory = Resolve-PathFromBase -BaseDirectory $configDir -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
    $logFileName = Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log"
    $latestLog = Get-LatestLogFile -LogDirectory $logDirectory -LogFileName $logFileName

    if ($latestLog) {
        $logLines = Read-LogTail -LogFilePath $latestLog.FullName -TailLines 500
        Render-LogLines -Box $txtLog -Lines $logLines
    } else {
        Render-LogLines -Box $txtLog -Lines @()
    }

    $state = Get-RunnerState -ConfigFullPath $configFullPath
    if ($state.Running) {
        $lblState.Text = "状态：运行中，PID=$($state.Pid)"
        $lblState.ForeColor = [System.Drawing.Color]::ForestGreen
    } else {
        $lblState.Text = "状态：未运行"
        $lblState.ForeColor = [System.Drawing.Color]::Crimson
    }

    $cooldown = Get-CooldownInfo -ConfigFullPath $configFullPath
    $lblCooldown.Text = $cooldown.Text
    if ($cooldown.RemainingSeconds -gt 0) {
        $lblCooldown.ForeColor = [System.Drawing.Color]::DarkOrange
    } else {
        $lblCooldown.ForeColor = [System.Drawing.Color]::ForestGreen
    }

    $statusLabel.Text = "最后刷新：$((Get-Date).ToString('HH:mm:ss'))"
}

$configFullPath = Resolve-PathFromBase -BaseDirectory $projectRoot -Value $ConfigPath
$configDir = Split-Path -Parent $configFullPath

$form = New-Object System.Windows.Forms.Form
$form.Text = "adb-monitor"
$form.StartPosition = "CenterScreen"
$form.Width = 1400
$form.Height = 900
$form.MinimumSize = New-Object System.Drawing.Size(1200, 760)
$form.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)

$topPanel = New-Object System.Windows.Forms.Panel
$topPanel.Dock = "Top"
$topPanel.Height = 92
$topPanel.Padding = New-Object System.Windows.Forms.Padding(10)
$form.Controls.Add($topPanel)

function New-TopButton {
    param([string]$Text, [int]$Left)
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $Text
    $btn.Width = 92
    $btn.Left = $Left
    $btn.Top = 12
    return $btn
}

$btnStart = New-TopButton -Text "启动监控" -Left 10
$btnStop = New-TopButton -Text "停止监控" -Left 110
$btnRefresh = New-TopButton -Text "刷新日志" -Left 210
$btnOpenConfig = New-TopButton -Text "打开配置" -Left 310
$btnClearCooldown = New-TopButton -Text "清空冷却" -Left 410
$topPanel.Controls.AddRange(@($btnStart, $btnStop, $btnRefresh, $btnOpenConfig, $btnClearCooldown))

$lblState = New-Object System.Windows.Forms.Label
$lblState.AutoSize = $true
$lblState.Left = 10
$lblState.Top = 55
$lblState.Text = "状态：未知"
$topPanel.Controls.Add($lblState)

$lblCooldown = New-Object System.Windows.Forms.Label
$lblCooldown.AutoSize = $true
$lblCooldown.Left = 360
$lblCooldown.Top = 55
$lblCooldown.Text = "邮件冷却：未知"
$topPanel.Controls.Add($lblCooldown)

$txtLog = New-Object System.Windows.Forms.RichTextBox
$txtLog.Dock = "Fill"
$txtLog.ReadOnly = $true
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 10)
$txtLog.BackColor = [System.Drawing.Color]::White
$txtLog.ForeColor = [System.Drawing.Color]::Black
$txtLog.BorderStyle = "FixedSingle"
$form.Controls.Add($txtLog)

$statusStrip = New-Object System.Windows.Forms.StatusStrip
$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = "就绪"
[void]$statusStrip.Items.Add($statusLabel)
$form.Controls.Add($statusStrip)

$btnStart.Add_Click({
    try {
        $startedPid = Start-Backend -ConfigFullPath $configFullPath
        $statusLabel.Text = "已启动监控，PID=$startedPid"
        Refresh-View
    } catch {
        [System.Windows.Forms.MessageBox]::Show("启动失败：$($_.Exception.Message)", "错误") | Out-Null
    }
})

$btnStop.Add_Click({
    try {
        $null = Stop-Backend -ConfigFullPath $configFullPath
        $statusLabel.Text = "已停止监控"
        Refresh-View
    } catch {
        [System.Windows.Forms.MessageBox]::Show("停止失败：$($_.Exception.Message)", "错误") | Out-Null
    }
})

$btnRefresh.Add_Click({
    Refresh-View
})

$btnOpenConfig.Add_Click({
    Invoke-Item -LiteralPath $configFullPath
})

$btnClearCooldown.Add_Click({
    try {
        Clear-CooldownState -ConfigFullPath $configFullPath
        $statusLabel.Text = "邮件冷却已清空"
        Refresh-View
    } catch {
        [System.Windows.Forms.MessageBox]::Show("清空失败：$($_.Exception.Message)", "错误") | Out-Null
    }
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.Add_Tick({ Refresh-View })
$timer.Start()

$form.Add_Shown({
    try {
        $null = Start-Backend -ConfigFullPath $configFullPath
    } catch {
        [System.Windows.Forms.MessageBox]::Show("启动失败：$($_.Exception.Message)", "错误") | Out-Null
    }
    Refresh-View
})

$form.Add_FormClosing({
    $null = Stop-Backend -ConfigFullPath $configFullPath
})

[void][System.Windows.Forms.Application]::EnableVisualStyles()
[void][System.Windows.Forms.Application]::Run($form)
