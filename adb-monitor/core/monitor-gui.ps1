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
    param([string]$LogFilePath, [int]$TailLines = 300)
    if ([string]::IsNullOrWhiteSpace($LogFilePath) -or -not (Test-Path -LiteralPath $LogFilePath)) {
        return "暂无日志。"
    }
    try {
        $lines = Get-Content -LiteralPath $LogFilePath -Tail $TailLines -Encoding UTF8 -ErrorAction Stop
        if (-not $lines) { return "日志文件为空。" }
        return ($lines -join [Environment]::NewLine)
    } catch {
        return "读取日志失败：$($_.Exception.Message)"
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
        $pid = 0
        if ([int]::TryParse($pidText.Trim(), [ref]$pid)) {
            if (Get-Process -Id $pid -ErrorAction SilentlyContinue) {
                return [pscustomobject]@{ Running = $true; Pid = $pid; Source = "PID 文件" }
            }
        }
    }

    $proc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -match [regex]::Escape($runnerScript) -and
        $_.CommandLine -match [regex]::Escape($ConfigFullPath)
    } | Select-Object -First 1

    if ($proc) {
        return [pscustomobject]@{ Running = $true; Pid = $proc.ProcessId; Source = "进程匹配" }
    }

    return [pscustomobject]@{ Running = $false; Pid = ""; Source = "" }
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
        $pid = 0
        if ([int]::TryParse($pidText.Trim(), [ref]$pid)) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
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

function Save-ConfigText {
    param([string]$Path, [string]$Text)
    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path -LiteralPath $directory)) {
        [void](New-Item -Path $directory -ItemType Directory -Force)
    }
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($true))
}

$configFullPath = Resolve-PathFromBase -BaseDirectory $projectRoot -Value $ConfigPath
$configDir = Split-Path -Parent $configFullPath

$form = New-Object System.Windows.Forms.Form
$form.Text = "adb-monitor 小工具"
$form.StartPosition = "CenterScreen"
$form.Width = 1400
$form.Height = 900
$form.MinimumSize = New-Object System.Drawing.Size(1200, 760)
$form.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 10)

$top = New-Object System.Windows.Forms.Panel
$top.Dock = "Top"
$top.Height = 56
$top.Padding = New-Object System.Windows.Forms.Padding(10)
$form.Controls.Add($top)

function New-Button($text, $left) {
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $text
    $btn.Width = 92
    $btn.Left = $left
    $btn.Top = 12
    return $btn
}

$btnStart = New-Button "启动监控" 10
$btnStop = New-Button "停止监控" 110
$btnRefresh = New-Button "刷新日志" 210
$btnSave = New-Button "保存配置" 310
$btnOpenConfig = New-Button "打开配置" 410
$btnOpenLog = New-Button "打开日志" 510
$top.Controls.AddRange(@($btnStart, $btnStop, $btnRefresh, $btnSave, $btnOpenConfig, $btnOpenLog))

$lblState = New-Object System.Windows.Forms.Label
$lblState.AutoSize = $true
$lblState.Left = 630
$lblState.Top = 16
$lblState.Text = "状态：未知"
$top.Controls.Add($lblState)

$lblLog = New-Object System.Windows.Forms.Label
$lblLog.AutoSize = $true
$lblLog.Left = 630
$lblLog.Top = 34
$lblLog.Text = "日志：-"
$top.Controls.Add($lblLog)

$split = New-Object System.Windows.Forms.SplitContainer
$split.Dock = "Fill"
$split.SplitterDistance = 480
$form.Controls.Add($split)

$leftPanel = New-Object System.Windows.Forms.Panel
$leftPanel.Dock = "Fill"
$leftPanel.Padding = New-Object System.Windows.Forms.Padding(10, 0, 5, 10)
$split.Panel1.Controls.Add($leftPanel)

$rightPanel = New-Object System.Windows.Forms.Panel
$rightPanel.Dock = "Fill"
$rightPanel.Padding = New-Object System.Windows.Forms.Padding(5, 0, 10, 10)
$split.Panel2.Controls.Add($rightPanel)

$txtConfig = New-Object System.Windows.Forms.TextBox
$txtConfig.Multiline = $true
$txtConfig.ScrollBars = "Both"
$txtConfig.WordWrap = $false
$txtConfig.Font = New-Object System.Drawing.Font("Consolas", 10)
$txtConfig.Dock = "Fill"
$txtConfig.Text = Get-Content -LiteralPath $configFullPath -Raw -Encoding UTF8
$leftPanel.Controls.Add($txtConfig)

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ScrollBars = "Both"
$txtLog.WordWrap = $false
$txtLog.ReadOnly = $true
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 10)
$txtLog.Dock = "Fill"
$rightPanel.Controls.Add($txtLog)

$status = New-Object System.Windows.Forms.StatusStrip
$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = "就绪"
[void]$status.Items.Add($statusLabel)
$form.Controls.Add($status)

function Refresh-View {
    $config = Get-ConfigMap -Path $configFullPath
    $logDirectory = Resolve-PathFromBase -BaseDirectory $configDir -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
    $logFileName = Get-ConfigValue -Config $config -Key "log_file_name" -DefaultValue "monitor.log"
    $latestLog = Get-LatestLogFile -LogDirectory $logDirectory -LogFileName $logFileName

    if ($latestLog) {
        $lblLog.Text = "日志：$($latestLog.FullName)"
        $txtLog.Text = Read-LogTail -LogFilePath $latestLog.FullName -TailLines 400
    } else {
        $lblLog.Text = "日志：暂无"
        $txtLog.Text = "暂无日志。"
    }

    $state = Get-RunnerState -ConfigFullPath $configFullPath
    if ($state.Running) {
        $lblState.Text = "状态：运行中，PID=$($state.Pid)"
        $lblState.ForeColor = [System.Drawing.Color]::ForestGreen
    } else {
        $lblState.Text = "状态：未运行"
        $lblState.ForeColor = [System.Drawing.Color]::Crimson
    }
    $statusLabel.Text = "最后刷新：$((Get-Date).ToString('HH:mm:ss'))"
}

$btnStart.Add_Click({
    try {
        $pid = Start-Backend -ConfigFullPath $configFullPath
        $statusLabel.Text = "已启动监控，PID=$pid"
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

$btnRefresh.Add_Click({ Refresh-View })

$btnSave.Add_Click({
    try {
        Save-ConfigText -Path $configFullPath -Text $txtConfig.Text
        $statusLabel.Text = "配置已保存"
        Refresh-View
    } catch {
        [System.Windows.Forms.MessageBox]::Show("保存失败：$($_.Exception.Message)", "错误") | Out-Null
    }
})

$btnOpenConfig.Add_Click({ Invoke-Item -LiteralPath $configFullPath })
$btnOpenLog.Add_Click({
    $config = Get-ConfigMap -Path $configFullPath
    $logDirectory = Resolve-PathFromBase -BaseDirectory $configDir -Value (Get-ConfigValue -Config $config -Key "log_directory" -DefaultValue ".\log")
    if (-not (Test-Path -LiteralPath $logDirectory)) {
        [void](New-Item -Path $logDirectory -ItemType Directory -Force)
    }
    Invoke-Item -LiteralPath $logDirectory
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.Add_Tick({ Refresh-View })
$timer.Start()

$form.Add_Shown({
    try {
        $null = Start-Backend -ConfigFullPath $configFullPath
    } catch {
    }
    Refresh-View
})

$form.Add_FormClosing({
    $null = Stop-Backend -ConfigFullPath $configFullPath
})

[void][System.Windows.Forms.Application]::EnableVisualStyles()
[void][System.Windows.Forms.Application]::Run($form)
