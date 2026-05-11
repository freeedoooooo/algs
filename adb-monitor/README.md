# adb-monitor

这个目录里有两个 PowerShell 脚本。

## 脚本用途

### `ldplayer-inspect.ps1`

一次性巡检，用来查看模拟器当前到底停在哪个状态。

### `ldplayer-monitor.ps1`

健康数量监控，只关心当前有多少台模拟器处于健康运行状态。

它会检查这些内容：

- `adb` 是否能发现设备
- 设备状态是不是 `device`
- `sys.boot_completed` 是否为 `1`

输出文件：

- `ldplayer-monitor.md`

## 常用命令

### 运行一次健康数量监控

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once
```

### 持续轮询监控

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -PollSeconds 30
```

### 手动传入 adb 路径

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -Once
```

## 说明

- 健康运行数会直接写入终端和 `ldplayer-monitor.md`
- 如果没有发现设备，脚本会按异常退出
- 如果有设备但未通过健康检查，脚本也会按异常退出
