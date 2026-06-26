# 文档查看指令

> 查看当前功能的各类文档和状态信息。按需使用。

---

## `SHOW REQ`

显示当前功能的需求文档。

**AI 执行动作**：读取并展示 `requirements.md` 完整内容。

---

## `SHOW DESIGN`

显示当前功能的技术设计文档。

**AI 执行动作**：读取并展示 `design.md` 完整内容。

---

## `SHOW TASKS`

显示任务清单及当前进度。

**AI 执行动作**：读取 `tasks.md`，以可视化格式展示任务状态。

输出示例：
```
📋 任务清单：0003-data-qe-yoy-change-rate

✅ 1. 创建脚本文件
✅ 2. 实现主函数 calc(...)
🔄 3. 实现 buildSql 方法  ← 当前
⬜ 4. 验证

进度：2/4（50%）
```

---

## `SHOW FILES`

显示本次功能涉及的所有文件。

**AI 执行动作**：读取 `design.md` 的"影响范围"章节，列出所有新增和修改的文件。

输出示例：
```
📁 涉及文件：0003-data-qe-yoy-change-rate

新增：
  + src/main/resources/indexFunc/qualityEvaluation/QeYoyChangeRate.groovy

修改：
  ~ （无）
```

---

## `SHOW MODULE`

显示当前会话已加载的模块和宪法信息。

**AI 执行动作**：输出当前模块状态。

输出示例：
```
🎯 当前模块：data（dib-agent-service-data，端口 30003）
📋 已加载宪法：
   - constitutions/constitution.md（公共基础宪法）
   - constitutions/constitution-data.md（专属宪法）
```
