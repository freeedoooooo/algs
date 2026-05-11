# adb-monitor

这个目录现在只保留雷电模拟器健康监控链路。

## 文件说明

- `ldplayer-monitor.ps1`
  单次执行监控。每次运行都会检查当前连接设备里有多少台是健康的。
- `start-monitor.ps1`
  按 `config.txt` 注册并启动 Windows 计划任务。
- `stop-monitor.ps1`
  停止并删除计划任务。
- `config.txt`
  统一配置 `adb` 路径、日志目录、定时策略、日志保留时长。
- `log/`
  监控日志目录。日志名会自动带时间戳。

## 健康定义

监控脚本只检查这两件事：

- 设备状态必须是 `device`
- `sys.boot_completed` 必须等于 `1`

## 配置项

`config.txt` 采用 `key=value` 格式。

- `adb_path`
  可留空。留空时脚本会自动查找 `adb.exe`。
- `log_directory`
  日志目录，默认是 `.\log`。
- `task_name`
  计划任务名称。
- `schedule_interval_minutes`
  定时执行间隔，单位分钟。
- `schedule_start_time`
  每日首次触发时间，格式必须是 `HH:mm`。
- `log_retention_hours`
  日志最多保留多少小时，默认 `72`。

## 使用方式

先修改 [config.txt](./config.txt)。

手动运行一次监控：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1
```

启动定时监控：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-monitor.ps1
```

停止定时监控：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\stop-monitor.ps1
```

## 日志规则

- 监控日志写入 `.\log`
- 日志文件名格式为 `ldplayer-monitor-YYYYMMDD-HHMMSS.md`
- 每次运行后会自动清理 72 小时以前的日志
