# 雷电模拟器本地巡检

这组脚本用于在 Windows 电脑上本地查看雷电模拟器状态，适合先做单机验证。

## 文件说明

- `ldplayer-monitor.ps1`
  用 `adb` 轮询已连接的模拟器，检查启动状态，并可选检查目标 App 是否还在运行。
- `ldplayer-inspect.ps1`
  复现我们刚才手工做的巡检动作，输出当前模拟器、前台界面、关键进程和已安装第三方包。

## `adb` 是什么

`adb` 是 Android Debug Bridge，中文一般叫“安卓调试桥”。它是电脑和安卓设备、安卓模拟器之间的命令通道。

对雷电模拟器来说，`adb` 可以用来：

- 查看在线实例
- 在指定模拟器里执行命令
- 查看当前前台页面
- 检查某个 App 是否在运行
- 安装、卸载、启动、停止应用
- 抓日志和排查异常

常见命令：

```powershell
adb devices -l
adb -s emulator-5554 shell getprop sys.boot_completed
adb -s emulator-5554 shell pidof com.example.app
adb -s emulator-5554 shell dumpsys activity activities
```

## 本地巡检

运行一次巡检：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1
```

如果 `adb.exe` 不在 `PATH`，可以手动指定雷电安装目录：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -LdConsolePath "D:\leidian\LDPlayer9\ldconsole.exe"
```

## 本地监控

运行一次监控：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -Once
```

检查某个 App：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -Once -Packages com.android.flysilkworm
```

持续轮询：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -PollSeconds 30 -Packages com.android.flysilkworm
```

## 输出文件

- `ldplayer-monitor.ps1` 会写入 `ldplayer-monitor.json`
- `ldplayer-inspect.ps1` 会写入 `ldplayer-inspect.json`

