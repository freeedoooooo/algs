# 辅助工具指令

> 调试记录、SQL 脚本生成、宪法自检、进度管理。按需使用。

---

## `DEBUG {描述}`

在 `debug/` 目录创建调试记录文档。

**示例**：`DEBUG 分析变量计算结果异常`

**AI 执行动作**：
1. 在当前功能的 `debug/` 目录下创建文档
2. 文件名：`debug-{描述-kebab-case}.md`
3. 基于 `templates/debug-template.md` 填充内容
4. 记录问题描述、分析过程、根因和解决方案

---

## `SQL`

在 `scripts/` 目录创建数据库迁移脚本。

**AI 执行动作**：
1. 在当前功能的 `scripts/` 目录下创建脚本文件
2. 文件名：`V{版本号}__{描述}.sql`
3. 基于 `templates/sql-migration-template.md` 填充内容
4. 包含必要的注释、BaseEntity 基础字段和索引

---

## `CHECK`

执行宪法自检，输出不符合项报告。

**AI 执行动作**：
1. 读取 `templates/checklist-template.md`
2. 对照当前模块执行通用自检 + 专属自检
3. 输出自检报告

输出示例：
```
🔍 宪法自检报告

通用检查：
✅ 分层架构：符合
✅ 命名规范：符合
⚠️  注解规范：Controller 缺少 @Api(tags)
✅ 数据库操作：符合
✅ 异常处理：符合

[data 专属]：
✅ Groovy 脚本模式：符合
⚠️  日志：使用了 @Slf4j，应改为 LoggerFactory.getLogger(this.class)

需修复：2 项
```

---

## `SAVE`

确认并输出当前进度快照。

**AI 执行动作**：
1. 确认 `tasks.md` 中已完成任务标记为 `[x]`，进行中任务标记为 `[-]`
2. 输出当前进度快照，便于下次 `RESUME` 时快速定位

---

## `SYNC`

重新读取文档，修正状态不一致项。

**AI 执行动作**：
1. 重新读取当前功能目录下所有文档
2. 对比 `tasks.md` 状态与实际代码情况
3. 输出同步报告，提示不一致项并建议修正
