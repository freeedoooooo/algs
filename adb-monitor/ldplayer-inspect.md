# 雷电模拟器巡检报告

- 生成时间: 2026-05-09T22:38:18.1597488+08:00
- adb 路径: D:\leidian\LDPlayer9\adb.exe
- ldconsole 路径: D:\leidian\LDPlayer9\ldconsole.exe
- 设备数量: 1

## 雷电多开列表

| 索引 | 名称 | Android已启动 | 主进程PID | VBoxPID | 分辨率 | DPI |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 雷电模拟器 | 否 | -1 | -1 | 1920x1080 | 280 |

## 设备详情

### emulator-5554

- 状态: device
- 当前焦点: mCurrentFocus=Window{bdf5c95 u0 com.android.launcher3/com.android.launcher3.Launcher}
- 恢复中的 Activity: mResumedActivity: ActivityRecord{263cdcf u0 com.android.launcher3/.Launcher t4}

### 关键进程
- u0_a33        2408  1433 3252808 118128 0                   0 S com.android.launcher3
- u0_a50        4031  1433 3292284  83996 0                   0 S com.google.android.gms.unstable
- u0_a17        4204  1433 3913380 106616 0                   0 S com.android.flysilkworm
- u0_a17        4254  1433 3546568  49416 0                   0 S com.android.flysilkworm:filedownloader
- u0_a56        6313  1434 1051128  54684 0                   0 S com.android.chrome
- u0_a53        6594  1433 3296256 117724 0                   0 S com.android.vending
- u0_a53        6773  1433 3186508  85308 0                   0 S com.android.vending:instant_app_installer
- u0_a50        7615  1433 3271932 137176 0                   0 S com.google.android.gms

### 第三方安装包
- package:com.google.android.ext.services
- package:org.telegram.messenger
- package:com.google.ar.core
- package:com.android.vending
- package:com.instagram.android
- package:com.google.android.syncadapters.contacts
- package:com.android.chrome
- package:com.google.android.gms
- package:com.google.android.gsf
- package:com.ldboost.app
- package:com.google.android.play.games

## 附注：原始 JSON

```json
{
    "Timestamp":  "2026-05-09T22:38:18.1597488+08:00",
    "AdbPath":  "D:\\leidian\\LDPlayer9\\adb.exe",
    "LdConsolePath":  "D:\\leidian\\LDPlayer9\\ldconsole.exe",
    "LdConsoleList2":  "0,雷电模拟器,0,0,0,-1,-1,1920,1080,280",
    "Devices":  [
                    {
                        "Serial":  "emulator-5554",
                        "State":  "device",
                        "RawDeviceLine":  "emulator-5554          device product:NX809J model:NX809J device:star2qltechn transport_id:1",
                        "CurrentFocus":  "mCurrentFocus=Window{bdf5c95 u0 com.android.launcher3/com.android.launcher3.Launcher}",
                        "ResumedActivity":  "mResumedActivity: ActivityRecord{263cdcf u0 com.android.launcher3/.Launcher t4}",
                        "InterestingProcess":  [
                                                   "u0_a33        2408  1433 3252808 118128 0                   0 S com.android.launcher3",
                                                   "u0_a50        4031  1433 3292284  83996 0                   0 S com.google.android.gms.unstable",
                                                   "u0_a17        4204  1433 3913380 106616 0                   0 S com.android.flysilkworm",
                                                   "u0_a17        4254  1433 3546568  49416 0                   0 S com.android.flysilkworm:filedownloader",
                                                   "u0_a56        6313  1434 1051128  54684 0                   0 S com.android.chrome",
                                                   "u0_a53        6594  1433 3296256 117724 0                   0 S com.android.vending",
                                                   "u0_a53        6773  1433 3186508  85308 0                   0 S com.android.vending:instant_app_installer",
                                                   "u0_a50        7615  1433 3271932 137176 0                   0 S com.google.android.gms"
                                               ],
                        "UserPackages":  [
                                             "package:com.google.android.ext.services",
                                             "package:org.telegram.messenger",
                                             "package:com.google.ar.core",
                                             "package:com.android.vending",
                                             "package:com.instagram.android",
                                             "package:com.google.android.syncadapters.contacts",
                                             "package:com.android.chrome",
                                             "package:com.google.android.gms",
                                             "package:com.google.android.gsf",
                                             "package:com.ldboost.app",
                                             "package:com.google.android.play.games"
                                         ]
                    }
                ]
}
```
