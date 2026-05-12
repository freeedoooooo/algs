# BB-Monitor

轻量脚本版模拟器健康监控工具。

## 目录

- `start.ps1`：启动监控
- `stop.ps1`：停止监控
- `monitor.config`：外部配置
- `core/check.ps1`：单次检查
- `core/runner.ps1`：循环调度
- `core/common.ps1`：公共函数
- `runtime/`：运行状态文件
- `log/`：日志目录

## 常用方式

日常使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1
```

调试单次检查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\core\check.ps1
```

## 监控规则

- 只统计当前 ADB 已连接的健康模拟器数量
- 设备状态必须是 `device`
- `adb shell getprop sys.boot_completed` 必须返回 `1`
- 每轮输出后额外留一空行，方便区分

## 日志规则

- 每天一个日志文件，例如 `monitor-20260512.log`
- 只保留最近 7 天日志
- 单个日志超过 50MB 时直接删除重写
- 黑窗口输出与日志文件内容保持一致
- 黑窗口每 3600 秒清屏一次

## 关键配置

- `ldplayer_path`
  主模拟器目录，优先使用；失效后自动尝试备用目录
- `common_ldplayer_dirs`
  备用目录列表，按顺序尝试
- `schedule_interval_seconds`
  循环检查间隔，单位秒
- `expected_healthy_devices`
  期望健康数量，低于该值会输出错误日志并触发告警逻辑
- `alert_cooldown_minutes`
  告警冷却时间，冷却期内不重复发同类邮件
- `mail_to`
  收件邮箱列表，分号分隔
- `runner_pid_file`
  runner 进程 PID 文件
- `alert_state_file`
  邮件冷却状态文件
