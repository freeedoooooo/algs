param(
    [string]$AdbPath = "D:\leidian\LDPlayer9\adb.exe",
    [string]$LdConsolePath = "D:\leidian\LDPlayer9\ldconsole.exe",
    [string]$ReportPath = ".\ldplayer-inspect.json"
)

$ErrorActionPreference = "Stop"

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    # 直接调用外部程序，避免额外封装带来的兼容性问题。
    $output = & $FilePath @ArgumentList 2>&1 | ForEach-Object { $_.ToString() }
    $exitCode = $LASTEXITCODE

    $stdout = @()
    $stderr = @()
    foreach ($line in $output) {
        if ($line -like "*error:*" -or $line -like "*failed:*") {
            $stderr += $line
        } else {
            $stdout += $line
        }
    }

    [pscustomobject]@{
        ExitCode = $exitCode
        StdOut   = (($stdout -join [Environment]::NewLine).Trim())
        StdErr   = (($stderr -join [Environment]::NewLine).Trim())
    }
}

function Require-Path {
    param([string]$PathValue, [string]$Label)

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "未找到 $Label：$PathValue"
    }
}

function Get-Devices {
    param([string]$Adb)

    # 读取当前在线的模拟器设备。
    $result = Invoke-External -FilePath $Adb -ArgumentList @("devices", "-l")
    if ($result.ExitCode -ne 0) {
        throw "执行 adb devices 失败：$($result.StdErr)"
    }

    $devices = @()
    foreach ($line in ($result.StdOut -split "`r?`n")) {
        if (-not $line -or $line -like "List of devices attached*") {
            continue
        }

        $parts = ($line -split "\s+") | Where-Object { $_ }
        if ($parts.Count -lt 2) {
            continue
        }

        $devices += [pscustomobject]@{
            Serial = $parts[0]
            State  = $parts[1]
            Raw    = $line.Trim()
        }
    }

    return $devices
}

function Invoke-AdbShell {
    param(
        [string]$Adb,
        [string]$Serial,
        [string[]]$Args
    )

    # 针对某台模拟器执行 shell 命令。
    Invoke-External -FilePath $Adb -ArgumentList (@("-s", $Serial, "shell") + $Args)
}

function Get-FocusInfo {
    param([string]$Adb, [string]$Serial)

    # 分别从窗口管理器和活动栈里读取当前焦点。
    $window = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("dumpsys", "window", "windows")
    $activity = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("dumpsys", "activity", "activities")

    $focusLine = ($window.StdOut -split "`r?`n" | Where-Object { $_ -match "mCurrentFocus=" } | Select-Object -First 1)
    $resumedLine = ($activity.StdOut -split "`r?`n" | Where-Object { $_ -match "mResumedActivity:" } | Select-Object -First 1)

    [pscustomobject]@{
        CurrentFocus    = [string]($focusLine | ForEach-Object { $_.Trim() })
        ResumedActivity = [string]($resumedLine | ForEach-Object { $_.Trim() })
    }
}

function Get-InterestingProcesses {
    param([string]$Adb, [string]$Serial)

    # 只筛出和当前场景相关的进程。
    $psResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("ps")
    $patterns = @(
        "flysilkworm",
        "telegram",
        "instagram",
        "chrome",
        "vending",
        "gms",
        "launcher3"
    )

    $lines = @()
    foreach ($line in ($psResult.StdOut -split "`r?`n")) {
        foreach ($pattern in $patterns) {
            if ($line -match $pattern) {
                $lines += $line.Trim()
                break
            }
        }
    }

    return [string[]]@($lines)
}

function Get-UserPackages {
    param([string]$Adb, [string]$Serial)

    # 列出用户安装的第三方应用包。
    $pmResult = Invoke-AdbShell -Adb $Adb -Serial $Serial -Args @("pm", "list", "packages", "-3")
    return [string[]]@($pmResult.StdOut -split "`r?`n" | Where-Object { $_ })
}

Require-Path -PathValue $AdbPath -Label "adb.exe"
Require-Path -PathValue $LdConsolePath -Label "ldconsole.exe"

$devices = @(Get-Devices -Adb $AdbPath)
$console = Invoke-External -FilePath $LdConsolePath -ArgumentList @("list2")

$inspected = @(foreach ($device in $devices) {
    $focus = Get-FocusInfo -Adb $AdbPath -Serial $device.Serial
    $processes = Get-InterestingProcesses -Adb $AdbPath -Serial $device.Serial
    $packages = Get-UserPackages -Adb $AdbPath -Serial $device.Serial

    [pscustomobject]@{
        Serial             = $device.Serial
        State              = $device.State
        RawDeviceLine      = $device.Raw
        CurrentFocus       = [string]$focus.CurrentFocus
        ResumedActivity    = [string]$focus.ResumedActivity
        InterestingProcess = [string[]]@($processes)
        UserPackages       = [string[]]@($packages)
    }
})

$report = [pscustomobject]@{
    Timestamp      = (Get-Date).ToString("o")
    AdbPath        = $AdbPath
    LdConsolePath   = $LdConsolePath
    LdConsoleList2  = $console.StdOut
    Devices        = $inspected
}

$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8

Write-Host "雷电多开列表："
Write-Host $console.StdOut
Write-Host ""

foreach ($device in $inspected) {
    Write-Host "[$($device.Serial)] 状态=$($device.State)"
    Write-Host "  当前焦点：$($device.CurrentFocus)"
    Write-Host "  恢复活动：$($device.ResumedActivity)"
    Write-Host "  关键进程："
    foreach ($line in $device.InterestingProcess) {
        Write-Host "    $line"
    }
    Write-Host "  第三方包："
    foreach ($pkg in $device.UserPackages) {
        Write-Host "    $pkg"
    }
    Write-Host ""
}
