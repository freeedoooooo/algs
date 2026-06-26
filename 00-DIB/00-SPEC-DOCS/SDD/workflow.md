# DIB Agent 微服务项目 AI 工作流程

> 本文档定义了 AI 助手在 DIB Agent 所有微服务项目中的标准工作流程，遵循规范驱动开发模式。
> 适用服务：parent / auth-server / gateway / auth-resource / mdm / extract / report / data / rule / dg

---

## 流程概览

```
用户提出需求
     ↓
[前置] 模块确认 → 加载公共宪法 + 专属宪法
     ↓
[阶段1] 需求澄清 → 生成 requirements.md
     ↓
[阶段2] 技术设计 → 生成 design.md
     ↓
[阶段3] 任务拆解 → 生成 tasks.md
     ↓
[阶段4] 逐步实现 → 按 tasks.md 顺序执行
     ↓
[阶段5] 验收检查 → 确认符合规范
```

---

## 前置步骤：模块确认与宪法加载（强制）

**每次开始新需求，AI 必须先执行此步骤，不得跳过。**

### 步骤 1：询问模块

AI 必须向用户提问：

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

### 步骤 2：加载宪法

用户确认模块后，AI 必须加载：

1. `docs-c1/00 AI-DOCS/SDD/constitutions/constitution.md`（公共基础宪法，**必须加载**）
2. 对应的专属宪法（根据模块选择）：

| 模块 | 专属宪法文件 |
|------|------------|
| `parent` | `constitutions/constitution-agent-parent.md` |
| `auth-server` | `constitutions/constitution-auth-server.md` |
| `gateway` | `constitutions/constitution-gateway.md` |
| `auth-resource` | `constitutions/constitution-auth-resource.md` |
| `mdm` | `constitutions/constitution-mdm.md` |
| `extract` | `constitutions/constitution-extract.md` |
| `report` | `constitutions/constitution-report.md` |
| `data` | `constitutions/constitution-data.md` |
| `rule` | `constitutions/constitution-rule.md` |
| `dg` | `constitutions/constitution-data-dg.md` |


### 步骤 3：确认加载完成

AI 输出确认信息：

```
✅ 模块已确认：{模块标识}（{服务名}）
📋 已加载宪法：constitution.md + constitution-{模块}.md
🎯 当前模式：规范驱动开发
```

---

## 文件组织规范

### 目录结构
```
docs-c1/00 AI-DOCS/specs/{编号}-{模块}-{功能名}/
├── requirements.md     # 需求文档
├── design.md           # 技术设计
├── tasks.md            # 任务清单
├── output/             # 不直接放入工程的输出文件（如生成的 Groovy 脚本、配置片段等）
├── test/               # 单元测试产物（测试用例、测试数据等，可选）
├── scripts/            # 数据库脚本（如有数据库变更）
│   └── V{版本号}__{描述}.sql
└── debug/              # 调试和分析文件（可选）
```

功能目录命名规范：`{编号}-{模块标识}-{功能描述-kebab-case}`
- 编号：4 位数字序号（内部需求）或 issue 编号（外部 ticket）
- 示例：`0001-data-qe-industry-deviation`
- 示例：`0002-rule-frame-calc-optimize`
- 示例：`0003-report-word-render-fix`
- 示例：`0004-extract-etl-sync-feature`
- 示例：`9087-report-contract-effective-date-optimization`（ticket 编号）

### 目录说明

| 目录/文件 | 说明 | 是否必须 |
|----------|------|---------|
| `requirements.md` | 需求文档 | ✅ 必须 |
| `design.md` | 技术设计 | ✅ 必须 |
| `tasks.md` | 任务清单 | ✅ 必须 |
| `output/` | 不直接放入工程的输出文件（如 Groovy 脚本、SQL 查询结果等） | 按需创建 |
| `test/` | 单元测试产物（测试用例、测试数据、测试报告等） | 按需创建 |
| `scripts/` | 数据库迁移脚本 | 有 DB 变更时创建 |
| `debug/` | 调试记录和分析文件 | 按需创建 |

### 禁止事项
- ❌ 禁止在功能目录根目录创建主文件以外的文档
- ❌ 禁止创建 `summary.md`、`guide.md` 等非标准文件
- ✅ 调试或分析信息统一放入 `debug/` 目录
- ✅ 需要直接放入工程的代码，直接修改工程文件，不经过 `output/`

---

## 阶段 1：需求澄清（Specify）

**触发条件**：模块确认完成后，用户提出新功能需求（输入 `NEW {编号} {功能描述}`）

**AI 必须做的事**：

1. 理解用户的原始需求
2. 识别功能类型（参考专属宪法中的业务域）
3. 主动追问模糊点
4. 确认边界条件和异常情况
5. 使用 `docs-c1/00 AI-DOCS/SDD/templates/requirements-template.md` 生成 `requirements.md`

**阶段 1 完成标志**：`requirements.md` 生成后，AI **必须主动向用户发起确认**，格式如下：

> 需求文档已生成，请确认以下内容是否正确：
> 1. 计算流程是否完整准确？
> 2. 输入参数是否齐全？
> 3. 输出字段是否符合预期？
> 4. 边界条件是否覆盖？
>
> 确认无误后请回复"需求确认"，或告知需要修改的地方。
> ➡️ **下一步**：需求确认后，AI 将进入阶段 2 生成技术设计文档。

AI **禁止**在用户明确回复"需求确认"之前自动进入阶段 2。

---

## 阶段 2：技术设计（Plan）

**触发条件**：requirements.md 已被用户确认

**AI 必须做的事**：

1. 阅读 `requirements.md`
2. 阅读已加载的公共宪法 + 专属宪法中的技术规范
3. 参考同类现有代码
4. 使用 `docs-c1/00 AI-DOCS/SDD/templates/design-template.md` 生成 `design.md`

**阶段 2 完成标志**：`design.md` 生成后，AI **必须主动向用户发起确认**：

> 技术设计文档已生成，请确认以下内容是否正确：
> 1. 架构设计和数据流是否合理？
> 2. SQL/核心逻辑是否符合预期？
> 3. 影响范围是否完整？
>
> 确认无误后请回复"设计确认"，或告知需要修改的地方。
> ➡️ **下一步**：设计确认后，AI 将进入阶段 3 生成任务清单。

AI **禁止**在用户明确回复"设计确认"之前自动进入阶段 3。

---

## 阶段 3：任务拆解（Tasks）

**触发条件**：design.md 已被用户确认

**AI 必须做的事**：

1. 阅读 requirements.md 和 design.md
2. 将设计拆解为可执行的小任务（每个任务 30 分钟内可完成）
3. 使用 `docs-c1/00 AI-DOCS/SDD/templates/tasks-template.md` 生成 `tasks.md`

**阶段 3 完成标志**：`tasks.md` 生成后，AI **必须主动向用户发起确认**：

> 任务清单已生成，请确认以下内容是否正确：
> 1. 任务拆解是否合理，粒度是否适当？
> 2. 任务顺序是否正确？
> 3. 是否有遗漏的任务？
>
> 确认无误后请回复"任务确认"或"可以开始实现"，或告知需要修改的地方。
> ➡️ **下一步**：任务确认后，AI 将进入阶段 4 按顺序逐步实现。

AI **禁止**在用户明确回复后才开始阶段 4 实现。

---

## 阶段 4：逐步实现（Implement）

**触发条件**：tasks.md 已被用户确认

**AI 必须做的事**：

1. 按 tasks.md 中的顺序逐个执行任务
2. 每完成一个任务，在 tasks.md 中勾选 `[x]`
3. 遵守公共宪法 + 专属宪法中的所有规范
4. 将输出文件放入 `output/` 目录

**任务状态标记规范**：
- `- [ ]` - 未开始
- `- [-]` - 进行中
- `- [x]` - 已完成

**实现原则**：
- 一次只做一个任务，不跳步
- 不确定的地方先问用户
- 改动现有代码前说明影响范围
- 任务完成后必须立即更新 tasks.md

**每个任务完成后执行宪法自检**（参考 `templates/checklist-template.md`）。

**阶段 4 完成标志**：所有任务勾选完毕后，AI **必须主动提示**：

> 所有任务已完成。
> ➡️ **下一步**：请输入"验收"进入阶段 5 验收检查。

---

## 阶段 5：验收检查（Analyze）

**触发条件**：所有任务完成，用户输入 `验收`

**AI 必须做的事**：

1. 对照 requirements.md 检查所有验收标准是否满足
2. 对照公共宪法 + 专属宪法检查代码是否符合规范
3. 确认输出文件已放入 `output/` 目录

**阶段 5 完成标志**：验收结果输出后，AI **必须主动提示**：

> 验收完成。
> ➡️ **下一步**：可输入 `NEW {编号} {功能描述}` 开始新功能，或 `STATUS` 查看所有功能进度。

---

## 特殊情况处理

### 发现需求有歧义
- 立即暂停，向用户澄清
- 更新 requirements.md 后继续

### 发现设计有缺陷
- 立即暂停，向用户说明
- 回到阶段 2 修改 design.md

### 宪法与需求冲突
- 优先遵守宪法
- 向用户说明冲突点

---

## 快速命令参考

| 指令 | 触发阶段 |
|------|----------|
| `START` | 激活工作流，询问模块 |
| `MODULE {模块}` | 直接指定模块（如 `MODULE data`） |
| `NEW {编号} {功能描述}` | 阶段 1：需求澄清 |
| `需求确认` | 进入阶段 2：技术设计 |
| `设计确认` | 进入阶段 3：任务拆解 |
| `任务确认` | 进入阶段 4：逐步实现 |
| `验收` | 进入阶段 5：验收检查 |
| `STATUS` | 显示所有功能进度 |
| `RESUME {功能名}` | 恢复中断的工作 |

---

**本工作流程适用于 DIB Agent 所有微服务项目的 AI 助手。**
