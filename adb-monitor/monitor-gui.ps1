[CmdletBinding()]
param(
    [string]$ConfigPath = ".\monitor.config"
)

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch {
}
$OutputEncoding = [Console]::OutputEncoding

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

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

function Get-ConfigMap {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "配置文件不存在：$Path"
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
    return Join-Path $DirectoryPath ("{0}-{1}.log" -f $baseName, $Date.ToString("yyyyMMdd"))
}

function Get-LatestLogFile {
    param(
        [string]$LogDirectory,
        [string]$LogFileName
    )

    if (-not (Test-Path -LiteralPath $LogDirectory)) {
        return $null
    }

    $baseName = Get-LogBaseName -FileName $LogFileName
    return Get-ChildItem -LiteralPath $LogDirectory -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "$baseName-*.log" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

function Read-LogTail {
    param(
        [string]$LogFilePath,
        [int]$TailLines = 300
    )

    if ([string]::IsNullOrWhiteSpace($LogFilePath) -or -not (Test-Path -LiteralPath $LogFilePath)) {
        return "暂无日志。"
    }

    try {
        $lines = Get-Content -LiteralPath $LogFilePath -Tail $TailLines -Encoding UTF8 -ErrorAction Stop
        if (-not $lines) {
            return "日志文件为空。"
        }

        return ($lines -join [Environment]::NewLine)
    } catch {
        return "读取日志失败：$($_.Exception.Message)"
    }
}

function Get-RunnerState {
    param(
        [string]$ConfigDirectory,
        [string]$ConfigFullPath,
        [hashtable]$Config
    )

    $runnerPidFile = Resolve-PathFromBase -BaseDirectory $ConfigDirectory -Value (Get-ConfigValue -Config $Config -Key "runner_pid_file" -DefaultValue ".\runtime\runner.pid")
    $runnerScriptPath = Join-Path $scriptRoot "core\runner.ps1"
    $pid = $null
    $source = ""
    if (Test-Path -LiteralPath $runnerPidFile) {
        $pidText = Get-Content -LiteralPath $runnerPidFile -Raw -ErrorAction SilentlyContinue
        $parsedId = 0
        if ([int]::TryParse($pidText.Trim(), [ref]$parsedId)) {
            $proc = Get-Process -Id $parsedId -ErrorAction SilentlyContinue
            if ($proc) {
                $pid = $parsedId
                $source = "PID 文件"
            }
        }
    }

    if (-not $pid) {
        $proc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -ieq "powershell.exe" -and
            $_.CommandLine -match [regex]::Escape($runnerScriptPath) -and
            $_.CommandLine -match [regex]::Escape($ConfigFullPath)
        } | Select-Object -First 1
        if ($proc) {
            $pid = $proc.ProcessId
            $source = "进程匹配"
        }
    }

    if ($pid) {
        return [pscustomobject]@{
            Running = $true
            Pid     = $pid
            Source  = $source
        }
    }

    return [pscustomobject]@{
        Running = $false
        Pid     = ""
        Source  = ""
    }
}

function Invoke-MonitorScript {
    param(
        [string]$ScriptPath,
        [string]$ConfigFullPath
    )

    $powershellPath = (Get-Command powershell.exe -ErrorAction Stop).Source
    $argumentString = @(
        "-NoProfile"
        "-ExecutionPolicy", "Bypass"
        "-File", ('"' + $ScriptPath + '"')
        "-ConfigPath", ('"' + $ConfigFullPath + '"')
    ) -join ' '

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $powershellPath
    $psi.Arguments = $argumentString
    $psi.WorkingDirectory = $scriptRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::Start($psi)
    $stdOut = $process.StandardOutput.ReadToEnd()
    $stdErr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        StdOut   = $stdOut
        StdErr   = $stdErr
    }
}

function Save-ConfigText {
    param(
        [string]$Path,
        [string]$Text
    )

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path -LiteralPath $directory)) {
        [void](New-Item -Path $directory -ItemType Directory -Force)
    }

    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($true))
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFullPath = Resolve-PathFromBase -BaseDirectory $scriptRoot -Value $ConfigPath
$configDirectory = Split-Path -Parent $configFullPath
$configText = ""

if (-not (Test-Path -LiteralPath $configFullPath)) {
    throw "配置文件不存在：$configFullPath"
}

$configText = Get-Content -LiteralPath $configFullPath -Raw -Encoding UTF8

$form = New-Object System.Windows.Forms.Form
$form.Text = "adb-monitor 小工具"
$form.StartPosition = "CenterScreen"
$form.Width = 1440
$form.Height = 920
$form.MinimumSize = New-Object System.Drawing.Size(1200, 760)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

$topPanel = New-Object System.Windows.Forms.Panel
$topPanel.Dock = "Top"
$topPanel.Height = 64
$topPanel.Padding = New-Object System.Windows.Forms.Padding(12, 12, 12, 8)
$form.Controls.Add($topPanel)

$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = "启动监控"
$btnStart.Width = 96
$btnStart.Height = 32
$btnStart.Left = 12
$btnStart.Top = 14
$topPanel.Controls.Add($btnStart)

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = "停止监控"
$btnStop.Width = 96
$btnStop.Height = 32
$btnStop.Left = 118
$btnStop.Top = 14
$topPanel.Controls.Add($btnStop)

$btnRefresh = New-Object System.Windows.Forms.Button
$btnRefresh.Text = "刷新日志"
$btnRefresh.Width = 96
$btnRefresh.Height = 32
$btnRefresh.Left = 224
$btnRefresh.Top = 14
$topPanel.Controls.Add($btnRefresh)

$btnOpenLog = New-Object System.Windows.Forms.Button
$btnOpenLog.Text = "打开日志目录"
$btnOpenLog.Width = 108
$btnOpenLog.Height = 32
$btnOpenLog.Left = 330
$btnOpenLog.Top = 14
$topPanel.Controls.Add($btnOpenLog)

$lblState = New-Object System.Windows.Forms.Label
$lblState.AutoSize = $true
$lblState.Left = 460
$lblState.Top = 20
$lblState.Text = "状态：未知"
$topPanel.Controls.Add($lblState)

$lblLogPath = New-Object System.Windows.Forms.Label
$lblLogPath.AutoSize = $true
$lblLogPath.Left = 460
$lblLogPath.Top = 38
$lblLogPath.Text = "日志：-"
$topPanel.Controls.Add($lblLogPath)

$mainSplit = New-Object System.Windows.Forms.SplitContainer
$mainSplit.Dock = "Fill"
$mainSplit.Orientation = "Vertical"
$mainSplit.SplitterDistance = 520
$form.Controls.Add($mainSplit)

$leftPanel = New-Object System.Windows.Forms.Panel
$leftPanel.Dock = "Fill"
$leftPanel.Padding = New-Object System.Windows.Forms.Padding(12, 0, 6, 12)
$mainSplit.Panel1.Controls.Add($leftPanel)

$rightPanel = New-Object System.Windows.Forms.Panel
$rightPanel.Dock = "Fill"
$rightPanel.Padding = New-Object System.Windows.Forms.Padding(6, 0, 12, 12)
$mainSplit.Panel2.Controls.Add($rightPanel)

$configButtons = New-Object System.Windows.Forms.Panel
$configButtons.Dock = "Top"
$configButtons.Height = 44
$configButtons.Padding = New-Object System.Windows.Forms.Padding(0, 6, 0, 6)
$leftPanel.Controls.Add($configButtons)

$btnReloadConfig = New-Object System.Windows.Forms.Button
$btnReloadConfig.Text = "重新载入"
$btnReloadConfig.Width = 96
$btnReloadConfig.Height = 28
$btnReloadConfig.Left = 0
$btnReloadConfig.Top = 8
$configButtons.Controls.Add($btnReloadConfig)

$btnSaveConfig = New-Object System.Windows.Forms.Button
$btnSaveConfig.Text = "保存配置"
$btnSaveConfig.Width = 96
$btnSaveConfig.Height = 28
$btnSaveConfig.Left = 106
$btnSaveConfig.Top = 8
$configButtons.Controls.Add($btnSaveConfig)

$btnOpenConfig = New-Object System.Windows.Forms.Button
$btnOpenConfig.Text = "打开配置文件"
$btnOpenConfig.Width = 108
$btnOpenConfig.Height = 28
$btnOpenConfig.Left = 212
$btnOpenConfig.Top = 8
$configButtons.Controls.Add($btnOpenConfig)

$txtConfig = New-Object System.Windows.Forms.TextBox
$txtConfig.Multiline = $true
$txtConfig.ScrollBars = "Both"
$txtConfig.WordWrap = $false
$txtConfig.Font = New-Object System.Drawing.Font("Consolas", 10)
$txtConfig.Dock = "Fill"
$leftPanel.Controls.Add($txtConfig)

$logPanel = New-Object System.Windows.Forms.Panel
$logPanel.Dock = "Fill"
$rightPanel.Controls.Add($logPanel)

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ReadOnly = $true
$txtLog.ScrollBars = "Both"
$txtLog.WordWrap = $false
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 10)
$txtLog.Dock = "Fill"
$logPanel.Controls.Add($txtLog)

$txtResult = New-Object System.Windows.Forms.TextBox
$txtResult.Multiline = $true
$txtResult.ReadOnly = $true
$txtResult.Height = 72
$txtResult.Dock = "Bottom"
$txtResult.ScrollBars = "Vertical"
$txtResult.Font = New-Object System.Drawing.Font("Consolas", 9)
$rightPanel.Controls.Add($txtResult)

$statusStrip = New-Object System.Windows.Forms.StatusStrip
$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = "就绪"
$statusStrip.Items.Add($statusLabel) | Out-Null
$form.Controls.Add($statusStrip)

function Set-ResultText {
    param([string]$Text)

    $txtResult.Text = $Text
}

function Refresh-ConfigView {
    $script:configText = Get-Content -LiteralPath $configFullPath -Raw -Encoding UTF8
    $txtConfig.Text = $script:configText
}

function Refresh-LogView {
    try {
        $configMap = Get-ConfigMap -Path $configFullPath
        $logDirectory = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $configMap -Key "log_directory" -DefaultValue ".\log")
        $logFileName = Get-ConfigValue -Config $configMap -Key "log_file_name" -DefaultValue "monitor.log"
        $latestLog = Get-LatestLogFile -LogDirectory $logDirectory -LogFileName $logFileName

        if ($latestLog) {
            $lblLogPath.Text = "日志：$($latestLog.FullName)"
            $txtLog.Text = Read-LogTail -LogFilePath $latestLog.FullName -TailLines 400
        } else {
            $lblLogPath.Text = "日志：暂无日志文件"
            $txtLog.Text = "暂无日志文件。"
        }

        $state = Get-RunnerState -ConfigDirectory $configDirectory -ConfigFullPath $configFullPath -Config $configMap
        if ($state.Running) {
            $lblState.Text = "状态：运行中，PID=$($state.Pid)，来源=$($state.Source)"
            $lblState.ForeColor = [System.Drawing.Color]::ForestGreen
        } else {
            $lblState.Text = "状态：未运行"
            $lblState.ForeColor = [System.Drawing.Color]::Crimson
        }
    } catch {
        $lblState.Text = "状态：读取失败"
        $lblState.ForeColor = [System.Drawing.Color]::Crimson
        $txtLog.Text = "刷新失败：$($_.Exception.Message)"
    }
}

function Refresh-All {
    Refresh-LogView
    $statusLabel.Text = "最后刷新：$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
}

function Execute-Action {
    param(
        [string]$ScriptName,
        [string]$SuccessMessage
    )

    $scriptPath = Join-Path $scriptRoot $ScriptName
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        Set-ResultText "脚本不存在：$scriptPath"
        return
    }

    try {
        $result = Invoke-MonitorScript -ScriptPath $scriptPath -ConfigFullPath $configFullPath
        if (-not [string]::IsNullOrWhiteSpace($result.StdErr)) {
            Set-ResultText ("{0}`r`n{1}" -f $SuccessMessage, $result.StdErr.Trim())
        } else {
            Set-ResultText $SuccessMessage
        }
    } catch {
        Set-ResultText ("执行失败：{0}" -f $_.Exception.Message)
    }

    Refresh-All
}

$btnStart.Add_Click({
    Execute-Action -ScriptName "start.ps1" -SuccessMessage "已执行启动命令。"
})

$btnStop.Add_Click({
    Execute-Action -ScriptName "stop.ps1" -SuccessMessage "已执行停止命令。"
})

$btnRefresh.Add_Click({
    Refresh-All
})

$btnOpenLog.Add_Click({
    try {
        $configMap = Get-ConfigMap -Path $configFullPath
        $logDirectory = Resolve-PathFromBase -BaseDirectory $configDirectory -Value (Get-ConfigValue -Config $configMap -Key "log_directory" -DefaultValue ".\log")
        if (-not (Test-Path -LiteralPath $logDirectory)) {
            [void](New-Item -Path $logDirectory -ItemType Directory -Force)
        }

        Invoke-Item -LiteralPath $logDirectory
    } catch {
        Set-ResultText ("打开日志目录失败：{0}" -f $_.Exception.Message)
    }
})

$btnReloadConfig.Add_Click({
    try {
        Refresh-ConfigView
        Set-ResultText "配置已重新载入。"
    } catch {
        Set-ResultText ("重新载入配置失败：{0}" -f $_.Exception.Message)
    }
})

$btnSaveConfig.Add_Click({
    try {
        Save-ConfigText -Path $configFullPath -Text $txtConfig.Text
        Set-ResultText "配置已保存。"
        Refresh-All
    } catch {
        Set-ResultText ("保存配置失败：{0}" -f $_.Exception.Message)
    }
})

$btnOpenConfig.Add_Click({
    try {
        Invoke-Item -LiteralPath $configFullPath
    } catch {
        Set-ResultText ("打开配置文件失败：{0}" -f $_.Exception.Message)
    }
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.Add_Tick({
    Refresh-All
})

Refresh-ConfigView
Refresh-All
$timer.Start()

[void][System.Windows.Forms.Application]::EnableVisualStyles()
[void][System.Windows.Forms.Application]::Run($form)
