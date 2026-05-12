# LD-Monitor

轻量脚本版模拟器健康监控工具。

## 根目录里你主要会用到的文件

- `start.cmd`
  双击启动监控，适合日常使用
- `stop.cmd`
  双击停止监控，适合日常使用
- `start.ps1`
  PowerShell 启动入口，适合调试
- `stop.ps1`
  PowerShell 停止入口，适合调试
- `monitor.config`
  外部配置文件，路径、检查频率、邮件告警都在这里改

## 其他目录

- `core/`
  内部脚本
  `check.ps1` 负责单次检查
  `runner.ps1` 负责循环调度
  `common.ps1` 负责公共函数
- `runtime/`
  运行状态文件目录
- `log/`
  日志目录

## 最常用的方式

日常使用：

1. 双击 `start.cmd`
2. 需要停止时双击 `stop.cmd`
3. 需要改配置时编辑 `monitor.config`

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
