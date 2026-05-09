# adb-monitor

这个目录里有两个 PowerShell 脚本，都是给本机上的雷电模拟器做巡检和监控用的。

## 两个脚本分别做什么

### `ldplayer-inspect.ps1`

用途：做一次性的现场巡检，适合排查“当前这台模拟器到底是什么状态”。

它会输出这些信息：

- 当前实际使用的 `adb.exe` 路径
- 当前实际使用的 `ldconsole.exe` 路径
- 雷电多开实例列表
- 已连接设备列表
- 当前焦点窗口
- 当前恢复中的 Activity
- 关键进程
- 第三方安装包

输出文件：

- `ldplayer-inspect.md`

报告特点：

- 以 Markdown 为主，方便直接看
- 最后附带原始 JSON，方便程序处理或进一步排查

### `ldplayer-monitor.ps1`

用途：做设备状态监控，适合检查“模拟器是不是正常启动了”“指定 App 还在不在运行”。

它会检查这些内容：

- `adb` 是否能发现设备
- 设备状态是不是 `device`
- `sys.boot_completed` 是否为 `1`
- 指定包名是否还在运行

输出文件：

- `ldplayer-monitor.md`

报告特点：

- 以 Markdown 为主，方便直接看
- 最后附带原始 JSON，方便程序处理或进一步排查

## 路径处理方式

脚本默认会自动查找雷电安装路径，不需要在脚本里写死：

- 优先使用命令行传入的路径
- 再尝试注册表中的安装目录
- 再尝试常见安装目录
- 最后尝试 `PATH` 中的 `adb`

## 常用命令

### 运行一次巡检

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1
```

### 运行一次监控

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once
```

### 监控指定应用是否还在运行

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -Once -Packages com.android.flysilkworm
```

### 持续轮询监控

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -PollSeconds 30 -Packages com.android.flysilkworm
```

## 手动传入路径

如果自动查找失败，可以手工传：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-inspect.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -LdConsolePath "D:\leidian\LDPlayer9\ldconsole.exe"
```

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ldplayer-monitor.ps1 -AdbPath "D:\leidian\LDPlayer9\adb.exe" -Once
```

## 适合什么时候用

- 想看当前模拟器到底停在哪个界面，用 `ldplayer-inspect.ps1`
- 想确认模拟器是否启动完成，用 `ldplayer-monitor.ps1`
- 想确认某个 App 是否掉了，用 `ldplayer-monitor.ps1 -Packages <包名>`
- 想导出一份便于阅读的现场报告，用这两个脚本都可以
