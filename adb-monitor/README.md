# adb-monitor

目录里只保留最直白的 4 个脚本：

- `check.ps1`
  单次健康检查。
- `runner.ps1`
  定时循环执行检查，并定时清屏。
- `start.ps1`
  启动监控窗口。
- `stop.ps1`
  停止监控窗口。

其余关键文件：

- `monitor.config`
  所有配置都放这里。
- `runner.pid`
  当前运行中的 runner 进程 ID。
- `log/`
  日志目录。

## 规则

- 每天一个日志文件
- 日志名形如 `monitor-YYYYMMDD.log`
- 只保留最近 7 天
- 单文件超过 50MB 就直接删掉重写
- 黑窗口输出和日志内容保持一致

## 配置

- `ldplayer_path`
  LDPlayer 安装目录，脚本会自动取其中的 `adb.exe`
- `schedule_interval_seconds`
  定时执行间隔
- `window_clear_interval_seconds`
  清屏间隔，默认 3600 秒
- `log_directory`
  日志目录
- `log_file_name`
  日志基础名，默认 `monitor.log`
- `log_max_size_mb`
  单文件最大值
- `log_retention_days`
  日志保留天数

## 使用

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\check.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1
```
