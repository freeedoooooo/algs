# adb-monitor

只保留一套 LDPlayer 健康监控脚本，目标很简单：

- 统计当前连接到 ADB 的模拟器总数
- 判断其中多少台是健康运行
- 用统一的黑窗口和日志持续输出结果

## 文件说明

- `ldplayer-monitor.ps1`
  单次执行一次健康检查。
- `monitor-runner.ps1`
  按配置循环执行监控，并按周期清屏。
- `start-monitor.ps1`
  启动监控窗口。
- `stop-monitor.ps1`
  停止监控窗口。
- `monitor.config`
  所有配置都放在这里。
- `log/`
  日志目录。

## 健康判定

脚本只检查两件事：

- 设备状态必须是 `device`
- `adb shell getprop sys.boot_completed` 必须返回 `1`

只要任意一项不满足，就记为不健康。

## 配置项

`monitor.config` 使用 `key=value` 格式：

- `ldplayer_path`
  LDPlayer 安装目录。脚本会默认使用这个目录下的 `adb.exe`。
- `common_ldplayer_dirs`
  常见 LDPlayer 安装目录，分号分隔，用于兜底发现。
- `registry_roots`
  扫描注册表时使用的根路径，分号分隔。
- `registry_value_names`
  注册表里用于查找安装目录的键名，分号分隔。
- `external_command_timeout_seconds`
  外部命令默认超时。
- `adb_devices_timeout_seconds`
  `adb devices` 超时。
- `adb_shell_timeout_seconds`
  `adb shell` 超时。
- `boot_check_attempts`
  `sys.boot_completed` 重试次数。
- `boot_check_delay_seconds`
  启动完成检查的重试间隔。
- `schedule_interval_seconds`
  定时执行间隔，单位秒。
- `window_clear_interval_seconds`
  黑窗口清屏间隔，单位秒。默认 3600，也就是 1 小时。
- `runner_pid_file`
  监控进程 PID 文件。
- `log_directory`
  日志目录。
- `log_file_name`
  日志基础文件名。实际写入文件会自动带上日期后缀。
- `log_max_size_mb`
  单个日志文件最大大小，超过后直接删除并从新内容开始写。
- `log_retention_days`
  仅保留最近多少天的日志文件。

## 日志规则

- 每天一个日志文件，例如 `log\monitor-20260511.log`
- 黑窗口输出和日志文件内容保持一致
- 每小时清屏一次，避免窗口堆太多内容
- 仅保留最近 7 天日志
- 单个日志文件超过 50MB 时，直接删除当前文件，再继续写入

## 使用方式

手动执行一次监控：

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
