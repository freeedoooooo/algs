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
  统一配置 `adb` 路径、模拟器路径、发现策略、健康检查参数、日志策略、定时策略。
- `log/`
  监控日志目录。平时只追加一个主日志文件，达到轮转条件后再归档。

## 健康定义

监控脚本只检查这两件事：

- 设备状态必须是 `device`
- `sys.boot_completed` 必须等于 `1`

## 配置项

`config.txt` 采用 `key=value` 格式。

- `adb_path`
  可留空。留空时脚本会自动查找 `adb.exe`。
- `ldplayer_path`
  可留空。留空时脚本会优先用 `adb.exe` 所在目录推断模拟器安装目录。
- `common_ldplayer_dirs`
  常见雷电安装目录列表，使用分号分隔。
- `log_directory`
  日志目录，默认是 `.\log`。
- `log_file_name`
  当前正在写入的主日志文件名。
- `registry_roots`
  自动发现雷电安装目录时会扫描的注册表根路径，使用分号分隔。
- `registry_value_names`
  从注册表里读取安装目录时使用的值名列表，使用分号分隔。
- `external_command_timeout_seconds`
  外部命令默认超时时间。
- `adb_devices_timeout_seconds`
  `adb devices` 超时时间。
- `adb_shell_timeout_seconds`
  `adb shell` 超时时间。
- `boot_check_attempts`
  `sys.boot_completed` 检查重试次数。
- `boot_check_delay_seconds`
  启动完成检查失败后的重试间隔秒数。
- `task_name`
  计划任务名称。
- `task_description`
  Windows 计划任务描述。
- `schedule_interval_minutes`
  定时执行间隔，单位分钟。
- `schedule_start_time`
  每日首次触发时间，格式必须是 `HH:mm`。
- `schedule_repetition_days`
  计划任务重复调度持续天数。
- `log_rotate_size_mb`
  主日志达到多少 MB 后自动轮转，默认 `10`。
- `log_retention_hours`
  轮转后的旧日志最多保留多少小时，默认 `72`。

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

- 监控日志默认写入 `.\log\ldplayer-monitor.log`
- 每次执行都会把结果追加到同一个 `.log` 文件，而不是一轮一个文件
- 主日志达到 `log_rotate_size_mb` 后，会轮转成带时间戳的归档日志
- 每次运行后会自动清理 72 小时以前的归档日志
- 日志里会记录配置文件路径、`adb` 路径、模拟器安装目录、连接设备数和异常原因
