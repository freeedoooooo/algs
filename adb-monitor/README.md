# 雷电模拟器本地巡检与监控脚本

这个目录里放了 2 个 PowerShell 脚本，用来在 Windows 本地检查雷电模拟器和 `adb` 的运行状态。

默认情况下，脚本会先自动查找雷电模拟器安装目录，再定位 `adb.exe` 和 `ldconsole.exe`。如果自动查找失败，也可以通过参数手工传入路径。

适用场景：

- 快速确认当前连上了哪些模拟器
- 检查某台模拟器是否已经启动完成
- 检查指定 App 是否还在运行
- 导出一次当前模拟器巡检信息，方便排查问题

## 文件说明

- `ldplayer-inspect.ps1`
  执行一次性的巡检，输出当前模拟器列表、前台界面、关键进程、第三方安装包等信息。

- `ldplayer-monitor.ps1`
  定时轮询 `adb`，检查模拟器启动状态，并可选检查指定 App 是否在运行。

## 自动找路径的规则

脚本默认按下面顺序寻找雷电相关路径：

1. 先使用命令行参数里手工传入的路径
2. 再尝试读取注册表中的雷电安装目录
3. 再尝试常见安装目录
4. 最后尝试 `PATH` 中的 `adb`

当前脚本涉及的自动定位：

- `ldplayer-inspect.ps1`
  会自动定位 `adb.exe` 和 `ldconsole.exe`

- `ldplayer-monitor.ps1`
  会自动定位 `adb.exe`

执行时你会看到类似日志：

```text
[步骤] 自动定位到 adb.exe: D:\leidian\LDPlayer9\adb.exe
[步骤] 自动定位到 ldconsole.exe: D:\leidian\LDPlayer9\ldconsole.exe
```

## adb 是什么

`adb` 是 Android Debug Bridge，也就是安卓调试桥。

它是电脑和安卓设备、安卓模拟器之间的命令通道。通过它可以：

- 查看当前在线设备
- 对某台模拟器执行 shell 命令
- 查询系统属性
- 查看前台 Activity
- 检查某个 App 是否在运行
- 导出日志和辅助排查异常

常见命令示例：

```powershell
adb devices -l
adb -s emulator-5554 shell getprop sys.boot_completed
adb -s emulator-5554 shell pidof com.example.app
adb -s emulator-5554 shell dumpsys activity activities
```

## 如何执行巡检脚本

推荐执行方式：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1
```

如果自动查找失败，可以手动传入：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -LdConsolePath "D:\leidian\LDPlayer9\ldconsole.exe"
```

## 如何执行监控脚本

执行一次：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once
```

检查指定包名是否在运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once -Packages com.android.flysilkworm
```

持续轮询，每 30 秒检查一次：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -PollSeconds 30 -Packages com.android.flysilkworm
```

## inspect 做了哪些优化

为了减少输出量和超时风险，`ldplayer-inspect.ps1` 读取前台界面时会优先执行轻量命令：

```powershell
dumpsys window windows | grep mCurrentFocus
dumpsys activity activities | grep mResumedActivity
```

也就是说，脚本优先只抓取真正有用的焦点行，而不是每次都读取整份 `dumpsys`。

如果轻量命令失败，脚本才会自动回退到完整 `dumpsys`，保证兼容性。

## ldconsole list2 说明

`ldplayer-inspect.ps1` 会调用：

```powershell
ldconsole.exe list2
```

这个命令返回的是一行逗号分隔的数据。脚本现在已经按 `GBK(cp936)` 正确解码，所以实例名中的中文不会再乱码。

示例：

```text
0,雷电模拟器,4654752,526278,1,14276,12448,1920,1080,280
0,雷电模拟器,0,0,0,-1,-1,1920,1080,280
```

按顺序可理解为：

1. 模拟器索引
2. 模拟器名称
3. 顶层窗口句柄
4. 绑定窗口句柄
5. Android 是否已启动，`1` 表示已启动，`0` 表示未启动
6. 模拟器主进程 PID
7. 虚拟机相关进程 PID
8. 宽
9. 高
10. DPI

两种常见状态的区别：

- `4654752,526278,1,14276,12448,...`
  说明实例正在运行，窗口和进程都存在

- `0,0,0,-1,-1,...`
  说明实例当前没有真正运行起来，或已经关闭

## 输出文件

- `ldplayer-inspect.ps1` 会生成 `ldplayer-inspect.json`
- `ldplayer-monitor.ps1` 会生成 `ldplayer-monitor.json`

`ldplayer-inspect.json` 里的主要字段：

- `AdbPath`
  本次巡检实际使用的 `adb.exe` 路径

- `LdConsolePath`
  本次巡检实际使用的 `ldconsole.exe` 路径

- `LdConsoleList2`
  `ldconsole list2` 的原始输出，已做正确中文解码

- `CurrentFocus`
  当前焦点窗口行

- `ResumedActivity`
  当前恢复中的 Activity 行

- `InterestingProcess`
  关键进程列表

- `UserPackages`
  第三方安装包列表

## 当前脚本已做的保护

为了避免脚本卡住不结束，现在已经加了这些保护：

- 每次调用 `adb` 和 `ldconsole` 都有超时控制
- 命令超时后会直接报错退出，不会一直挂住
- 执行过程中会打印中文日志，方便看到卡在第几步
- 默认会自动查找雷电安装目录，不再依赖写死路径
- `ldconsole list2` 已单独按 `GBK` 解码，避免中文乱码
- `inspect` 优先走轻量焦点采集，减少整份 `dumpsys` 带来的压力

## 直接执行 .ps1 时的注意事项

如果你这样执行：

```powershell
.\ldplayer-inspect.ps1
```

有些电脑会因为 PowerShell 执行策略限制而被拦截。可以先在当前会话临时放开：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\ldplayer-inspect.ps1
```

更推荐的仍然是使用 `powershell.exe -ExecutionPolicy Bypass -File ...` 的方式。

## 建议排查顺序

如果脚本运行不符合预期，建议按下面顺序看：

1. 先确认 `adb devices -l` 能否正常执行
2. 运行 `ldplayer-inspect.ps1` 看自动定位到的路径和巡检输出
3. 检查 `LdConsoleList2` 是否显示出正确的实例状态
4. 如果巡检正常，再运行 `ldplayer-monitor.ps1 -Once`
5. 最后查看生成的 `json` 文件确认采集结果
