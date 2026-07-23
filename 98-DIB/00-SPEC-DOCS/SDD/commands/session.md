# 会话指令

> 工作流激活、模块切换、进度恢复、状态查询。
> 每次新会话必须执行 `START` 或 `MODULE` 来激活工作流。

---

## `START`

激活工作流，引导用户选择模块。

**AI 执行动作**：
1. 加载 `constitutions/constitution.md`（公共基础宪法）
2. 加载 `workflow.md`（工作流规则）
3. 加载 `commands/reference.md`（指令索引）
4. 询问用户确认所属模块：

   > 请确认本次需求属于哪个模块？
   >
   > 基础设施：
   > - `parent` — 父 POM 和基础库（dib-agent-parent）
   >
   > Data Cloud 平台服务：
   > - `auth-server` — 认证服务（data-cloud-auth-server，端口 9090）
   > - `gateway` — API 网关（data-cloud-gateway，端口 20000）
   > - `auth-resource` — 权限资源服务（data-cloud-auth-resource，端口 20001）
   > - `mdm` — 主数据服务（data-cloud-mdm，端口 20002）
   >
   > DIB Agent 业务服务：
   > - `extract` — 资料提取服务（dib-agent-service-extract，端口 30001）
   > - `report` — 报告生成服务（dib-agent-service-report，端口 30002）
   > - `data` — 数据资源服务（dib-agent-service-data，端口 30003）
   > - `rule` — 规则引擎服务（dib-agent-service-rule，端口 30004）
   > - `dg` — 数据治理服务（dib-agent-data-dg，端口 30005）

5. 用户确认模块后，加载对应专属宪法 `constitutions/constitution-{模块}.md`
6. 输出确认信息：
   ```
   ✅ 工作流已激活
   📋 已加载：constitution.md + constitution-{模块}.md + workflow.md
   🎯 当前模块：{模块标识}（{服务名}）

   可用指令：NEW / RESUME / STATUS
   ```

---

## `MODULE {模块标识}`

直接切换到指定模块，跳过 START 的交互引导。

**示例**：`MODULE data` / `MODULE mdm` / `MODULE gateway`

**AI 执行动作**：
1. 加载 `constitutions/constitution.md`（公共基础宪法）
2. 加载 `constitutions/constitution-{模块}.md`（专属宪法）
3. 输出确认信息：
   ```
   ✅ 模块已确认：{模块标识}（{服务名}）
   📋 已加载：constitution.md + constitution-{模块}.md
   ```

> 适合已熟悉流程、想快速进入工作状态时使用。

---

## `RESUME {功能名}`

恢复已有功能的进度，从中断处继续。

**示例**：`RESUME 0003-data-qe-yoy-change-rate`

**AI 执行动作**：
1. 读取 `docs-c1/00 AI-DOCS/specs/{功能名}/` 下所有文档
2. 从目录名中识别模块标识，自动加载对应宪法
3. 分析当前进度（根据 tasks.md 的勾选状态）
4. 输出进度报告：
   ```
   📂 功能：{功能名}
   🎯 模块：{模块标识}
   📋 当前阶段：{阶段名}
   ✅ 已完成任务：{N}/{总数}
   ⏳ 下一步：{下一个未完成任务}
   ```
5. 等待用户指令

---

## `STATUS`

查看所有功能的进度总览。

**AI 执行动作**：
1. 扫描 `docs-c1/00 AI-DOCS/specs/` 目录
2. 按模块分组列出所有功能及其状态：
   ```
   📊 功能进度总览

   [data]
   - 0001-data-qe-industry-deviation       ✅ 已完成
   - 0003-data-qe-yoy-change-rate      🔄 实现中（7/10）

   [rule]
   - 0002-rule-frame-optimize          📝 设计阶段

   [report]
   - 9087-report-contract-effective    🔄 实现中（3/6）
   ```
