# LDPlayer local monitor

This folder contains two PowerShell scripts for checking local LDPlayer / adb state on Windows.

## Files

- `ldplayer-inspect.ps1`
  Collects a one-time snapshot of connected emulator state, foreground activity, selected processes, and third-party packages.
- `ldplayer-monitor.ps1`
  Polls connected emulators through `adb`, checks boot status, and can optionally verify whether target app packages are running.

## What is `adb`

`adb` is Android Debug Bridge. It is the command-line bridge between your PC and Android devices or emulators.

Common commands:

```powershell
adb devices -l
adb -s emulator-5554 shell getprop sys.boot_completed
adb -s emulator-5554 shell pidof com.example.app
adb -s emulator-5554 shell dumpsys activity activities
```

## Run inspect

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1
```

If `adb.exe` or `ldconsole.exe` is not in the default path:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -LdConsolePath "D:\leidian\LDPlayer9\ldconsole.exe"
```

## Run monitor

Run once:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once
```

Check a package:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once -Packages com.android.flysilkworm
```

Keep polling:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -PollSeconds 30 -Packages com.android.flysilkworm
```

## Output files

- `ldplayer-inspect.ps1` writes `ldplayer-inspect.json`
- `ldplayer-monitor.ps1` writes `ldplayer-monitor.json`
