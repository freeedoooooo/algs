# 指令参考手册

> 所有指令的速查、用法示例和典型流程。日常使用查本文件即可。
> 需要了解 AI 详细执行逻辑时，查对应的详情文件。

---

## 会话与模块

| 指令 | 说明 | 详情 |
|------|------|------|
| `START` | 激活工作流，引导选择模块 | [session.md](session.md) |
| `MODULE {模块}` | 直接切换到指定模块 | [session.md](session.md) |
| `RESUME {功能名}` | 恢复已有功能的进度 | [session.md](session.md) |
| `STATUS` | 查看所有功能的进度总览 | [session.md](session.md) |

```
# 示例
MODULE data
MODULE auth-resource
RESUME 0003-data-qe-yoy-change-rate
STATUS
```

---

## 开发流程

| 指令 | 触发时机 | 详情 |
|------|---------|------|
| `NEW {编号} {功能描述}` | 启动新功能，编号必须由用户提供 | [workflow.md](workflow.md) |
| `需求确认` | requirements.md 审阅完毕 | [workflow.md](workflow.md) |
| `设计确认` | design.md 审阅完毕 | [workflow.md](workflow.md) |
| `任务确认` | tasks.md 审阅完毕 | [workflow.md](workflow.md) |
| `验收` | 所有任务完成后 | [workflow.md](workflow.md) |

```
# 示例
NEW 0005 开发同比变动率算子
NEW 9101 修复银行账号长度校验问题
```

---

## 任务执行

| 指令 | 说明 | 详情 |
|------|------|------|
| `DO {N}` | 执行指定任务，如 `DO 3`、`DO 2.1` | [tasks.md](tasks.md) |
| `DO NEXT` | 执行下一个未完成任务 | [tasks.md](tasks.md) |
| `DO ALL` | 自动执行所有剩余任务 | [tasks.md](tasks.md) |
| `SKIP {N}` | 跳过任务 N | [tasks.md](tasks.md) |
| `REDO {N}` | 重置并重新执行任务 N | [tasks.md](tasks.md) |

```
# 示例
DO 3
DO NEXT
DO ALL
SKIP 2
REDO 3
```

---

## 文档查看

| 指令 | 说明 | 详情 |
|------|------|------|
| `SHOW REQ` | 显示需求文档 | [show.md](show.md) |
| `SHOW DESIGN` | 显示技术设计文档 | [show.md](show.md) |
| `SHOW TASKS` | 显示任务清单及进度 | [show.md](show.md) |
| `SHOW FILES` | 显示涉及的文件列表 | [show.md](show.md) |
| `SHOW MODULE` | 显示当前模块和已加载宪法 | [show.md](show.md) |

```
# 示例
SHOW TASKS     # 查看当前进度
SHOW MODULE    # 确认当前加载的模块
SHOW FILES     # 查看本次涉及哪些文件
```

---

## 辅助工具

| 指令 | 说明 | 详情 |
|------|------|------|
| `DEBUG {描述}` | 在 `debug/` 创建调试记录 | [tools.md](tools.md) |
| `SQL` | 在 `scripts/` 创建数据库迁移脚本 | [tools.md](tools.md) |
| `CHECK` | 执行宪法自检，输出不符合项 | [tools.md](tools.md) |
| `SAVE` | 确认并输出当前进度快照 | [tools.md](tools.md) |
| `SYNC` | 重新读取文档，修正状态不一致项 | [tools.md](tools.md) |

```
# 示例
DEBUG 分析变量计算结果异常
SQL
CHECK
```

---

## 典型场景

### 开始一个新功能
```
MODULE data
NEW 0005 开发同比变动率算子
→ [需求讨论]
需求确认
→ [设计讨论]
设计确认
任务确认
DO ALL
验收
```

### 恢复中断的工作
```
RESUME 0003-data-qe-yoy-change-rate
SHOW TASKS        # 确认当前进度
DO NEXT           # 继续执行
```

### 单步调试执行
```
DO 3              # 执行单个任务
CHECK             # 自检
DO 4
验收
```

### 处理问题任务
```
SKIP 2            # 跳过有问题的任务
DEBUG 任务2执行异常  # 记录问题
REDO 2            # 问题解决后重做
```
