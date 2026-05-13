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

function Merge-ConfigMap {
    param(
        [hashtable]$BaseConfig,
        [hashtable]$OverrideConfig
    )

    $merged = @{}

    if ($BaseConfig) {
        foreach ($key in $BaseConfig.Keys) {
            $merged[$key] = $BaseConfig[$key]
        }
    }

    if ($OverrideConfig) {
        foreach ($key in $OverrideConfig.Keys) {
            $merged[$key] = $OverrideConfig[$key]
        }
    }

    return $merged
}

function Get-MergedConfigMap {
    param(
        [string]$DefaultConfigPath,
        [string]$OverrideConfigPath
    )

    $defaultConfig = @{}
    if (-not [string]::IsNullOrWhiteSpace($DefaultConfigPath) -and (Test-Path -LiteralPath $DefaultConfigPath)) {
        $defaultConfig = Get-ConfigMap -Path $DefaultConfigPath
    }

    $overrideConfig = @{}
    if (-not [string]::IsNullOrWhiteSpace($OverrideConfigPath)) {
        $overrideConfig = Get-ConfigMap -Path $OverrideConfigPath
    }

    return Merge-ConfigMap -BaseConfig $defaultConfig -OverrideConfig $overrideConfig
}

function Get-DefaultConfigPath {
    param([string]$ScriptRoot)

    return Join-Path $ScriptRoot "default.config"
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

function Ensure-Directory {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        [void](New-Item -Path $Path -ItemType Directory -Force)
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
    return Join-Path $DirectoryPath ("{0}-{1}.log" -f $baseName, $Date.ToString("yyyyMMdd"))
}

function Get-LogTimestamp {
    param([datetime]$Date = (Get-Date))

    return $Date.ToString("yyyy-MM-dd HH:mm:ss")
}

function Reset-LogIfOversized {
    param(
        [string]$LogFilePath,
        [int]$MaxSizeMb
    )

    if (-not (Test-Path -LiteralPath $LogFilePath)) {
        return
    }

    $maxBytes = [Math]::Max($MaxSizeMb, 1) * 1MB
    if ((Get-Item -LiteralPath $LogFilePath).Length -ge $maxBytes) {
        Remove-Item -LiteralPath $LogFilePath -Force
    }
}

function Remove-StaleLogs {
    param(
        [string]$DirectoryPath,
        [string]$BaseFileName,
        [string]$CurrentLogFileName,
        [int]$RetentionDays
    )

    $cutoff = (Get-Date).AddDays(-1 * [Math]::Max($RetentionDays, 1))
    $baseName = Get-LogBaseName -FileName $BaseFileName
    Get-ChildItem -LiteralPath $DirectoryPath -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "$baseName*.log" -and
            $_.Name -ne $CurrentLogFileName -and
            $_.LastWriteTime -lt $cutoff
        } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Get-MonitorLogPath {
    param(
        [string]$ConfigDirectory,
        [hashtable]$Config
    )

    $logDirectory = Resolve-PathFromBase -BaseDirectory $ConfigDirectory -Value (Get-ConfigValue -Config $Config -Key "log_directory" -DefaultValue ".\log")
    $logFileName = Get-ConfigValue -Config $Config -Key "log_file_name" -DefaultValue "monitor.log"
    Ensure-Directory -Path $logDirectory
    return Get-DatedLogFilePath -DirectoryPath $logDirectory -BaseFileName $logFileName
}

function Write-LogLine {
    param(
        [string]$LogPath,
        [string]$Message,
        [string]$Level = "INFO"
    )

    if ([string]::IsNullOrWhiteSpace($Message)) {
        return
    }

    $timestamp = Get-LogTimestamp
    $line = "[{0}] [{1}] {2}" -f $timestamp, $Level, $Message
    Write-Host $line

    if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
        Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    }
}

function Write-BlankLogLine {
    param([string]$LogPath = "")

    Write-Host ""
    if (-not [string]::IsNullOrWhiteSpace($LogPath)) {
        Add-Content -LiteralPath $LogPath -Value "" -Encoding UTF8
    }
}

function Get-RunnerProcessByCommandLine {
    param(
        [string]$RunnerScriptPath,
        [string]$ConfigPath
    )

    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -match [regex]::Escape($RunnerScriptPath) -and
        $_.CommandLine -match [regex]::Escape($ConfigPath)
    })
}

function Get-RunnerProcessById {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return $null
    }

    return Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
}

function Get-CheckProcessByCommandLine {
    param(
        [string]$CheckScriptPath,
        [string]$ConfigPath
    )

    return @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -ieq "powershell.exe" -and
        $_.CommandLine -match [regex]::Escape($CheckScriptPath) -and
        $_.CommandLine -match [regex]::Escape($ConfigPath)
    })
}

function Get-SafeWorkingDirectory {
    param([string]$MonitorRoot)

    if ([string]::IsNullOrWhiteSpace($MonitorRoot)) {
        return [System.IO.Path]::GetTempPath()
    }

    $parent = Split-Path -Parent $MonitorRoot
    if (-not [string]::IsNullOrWhiteSpace($parent) -and (Test-Path -LiteralPath $parent)) {
        return $parent
    }

    return $MonitorRoot
}
