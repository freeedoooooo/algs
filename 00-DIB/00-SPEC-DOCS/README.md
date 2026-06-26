# DIB Agent AI-DOCS

> DIB Agent 微服务体系的规范驱动开发框架，基于 Spec-Kit 工作流。

---

## 项目简介

本目录提供一套**规范驱动开发（Spec-Driven Development）**方案，约束 AI 助手在 DIB Agent 各微服务中的行为，实现：

- **模块感知**：每次开始前确认所属服务模块，加载对应宪法
- **需求先行**：先写清楚要做什么，再动手
- **质量内置**：通过"宪法"强制代码规范
- **流程标准化**：需求 → 设计 → 任务 → 实现 → 验收
- **进度可追溯**：任务状态实时更新，支持会话恢复

---

## 目录结构

```
00 AI-DOCS/
├── SDD/                              # 规范驱动开发核心目录
│   ├── constitutions/                # 所有宪法文档
│   │   ├── constitution.md           # 公共基础宪法（所有模块必读）
│   │   ├── constitution-agent-parent.md  # parent 模块专属宪法
│   │   ├── constitution-auth-server.md   # auth-server 模块专属宪法
│   │   ├── constitution-gateway.md       # gateway 模块专属宪法
│   │   ├── constitution-auth-resource.md # auth-resource 模块专属宪法
│   │   ├── constitution-mdm.md           # mdm 模块专属宪法
│   │   ├── constitution-extract.md       # extract 模块专属宪法
│   │   ├── constitution-report.md        # report 模块专属宪法
│   │   ├── constitution-data.md          # data 模块专属宪法
│   │   ├── constitution-rule.md          # rule 模块专属宪法
│   │   └── constitution-data-dg.md       # dg 模块专属宪法
│   ├── templates/                    # 文档模板
│   │   ├── requirements-template.md  # 需求文档模板
│   │   ├── design-template.md        # 技术设计模板
│   │   ├── tasks-template.md         # 任务清单模板
│   │   ├── checklist-template.md     # 宪法自检清单
│   │   ├── debug-template.md         # 调试记录模板
│   │   └── sql-migration-template.md # 数据库迁移脚本模板
│   ├── commands/                     # 指令体系（按职责拆分）
│   │   ├── reference.md              # 全量速查表 + 典型流程
│   │   ├── session.md                # 会话指令（START/MODULE/RESUME/STATUS）
│   │   ├── workflow.md               # 开发流程指令（NEW/需求确认/设计确认/任务确认/验收）
│   │   ├── tasks.md                  # 任务执行指令（DO/SKIP/REDO）
│   │   ├── show.md                   # 文档查看指令（SHOW 系列）
│   │   └── tools.md                  # 辅助工具指令（DEBUG/SQL/CHECK/SAVE/SYNC）
│   ├── commands.md                   # 指令入口（指向 commands/ 目录）
│   ├── workflow.md                   # AI 标准工作流程
│   └── branch-management.md          # 分支管理规范
│
├── specs/                            # 需求规格目录
│   └── {模块}-{序号}-{功能名}/          # 每个功能一个文件夹
│       ├── requirements.md           # 需求文档
│       ├── design.md                 # 技术设计
│       ├── tasks.md                  # 任务清单
│       ├── output/                   # 输出文件（代码、脚本等）
│       ├── scripts/                  # 数据库脚本
│       │   └── V{版本号}__{描述}.sql
│       └── debug/                    # 调试和分析文件
│
└── README.md                         # 本文件
```

---

## 服务模块一览

| 模块标识 | 服务名 | 端口 | 专属宪法 |
|---------|--------|------|---------|
| `parent` | dib-agent-parent | - | `constitution-agent-parent.md` |
| `auth-server` | data-cloud-auth-server | 9090 | `constitution-auth-server.md` |
| `gateway` | data-cloud-gateway | 20000 | `constitution-gateway.md` |
| `auth-resource` | data-cloud-auth-resource | 20001 | `constitution-auth-resource.md` |
| `mdm` | data-cloud-mdm | 20002 | `constitution-mdm.md` |
| `extract` | dib-agent-service-extract | 30001 | `constitution-extract.md` |
| `report` | dib-agent-service-report | 30002 | `constitution-report.md` |
| `data` | dib-agent-service-data | 30003 | `constitution-data.md` |
| `rule` | dib-agent-service-rule | 30004 | `constitution-rule.md` |
| `dg` | dib-agent-data-dg | 30005 | `constitution-data-dg.md` |


---

## 快速开始

### 激活工作流

每次新会话输入：

```
START
```

AI 自动加载公共宪法 + workflow + commands，然后询问所属模块。

### 直接指定模块

```
MODULE mdm
```

跳过交互，直接加载对应模块宪法，进入就绪状态。

### 开始新功能

```
NEW 优化框架计算逻辑
```

AI 进入需求澄清阶段，主动追问细节，生成 `requirements.md`。

### 恢复已有功能

```
RESUME rule-002-frame-calc-optimize
```

AI 读取已有文档，分析进度，从中断处继续。

### 查看项目状态

```
STATUS
```

按模块分组列出所有功能及当前阶段。

---

## 核心指令速查

| 指令 | 说明 |
|------|------|
| `START` | 激活工作流，询问模块 |
| `MODULE {模块}` | 直接指定模块（见服务模块一览表） |
| `NEW {功能描述}` | 开始新功能需求 |
| `RESUME {功能名}` | 恢复已有功能进度 |
| `STATUS` | 查看所有功能状态 |
| `需求确认` | 确认需求 → 进入设计阶段 |
| `设计确认` | 确认设计 → 进入任务拆解 |
| `任务确认` | 确认任务 → 进入实现阶段 |
| `DO NEXT` | 执行下一个未完成任务 |
| `DO {N}` | 执行指定任务（如 `DO 3`） |
| `DO ALL` | 自动执行所有剩余任务 |
| `验收` | 触发验收检查 |
| `CHECK` | 执行宪法自检 |
| `SHOW MODULE` | 显示当前已加载的模块和宪法 |

| 文件 | 内容 |
|------|------|
| [SDD/commands/reference.md](SDD/commands/reference.md) | 全量速查表 + 典型流程 |
| [SDD/commands/session.md](SDD/commands/session.md) | START / MODULE / RESUME / STATUS |
| [SDD/commands/workflow.md](SDD/commands/workflow.md) | NEW / 需求确认 / 设计确认 / 任务确认 / 验收 |
| [SDD/commands/tasks.md](SDD/commands/tasks.md) | DO / DO NEXT / DO ALL / SKIP / REDO |
| [SDD/commands/show.md](SDD/commands/show.md) | SHOW REQ / SHOW DESIGN / SHOW TASKS / SHOW FILES / SHOW MODULE |
| [SDD/commands/tools.md](SDD/commands/tools.md) | DEBUG / SQL / CHECK / SAVE / SYNC |

---

## 工作流程

```
用户提出需求
     ↓
[前置] 模块确认 → 加载 constitution.md + constitution-{模块}.md
     ↓
[阶段1] 需求澄清 → 生成 requirements.md
     ↓  (用户输入: 需求确认)
[阶段2] 技术设计 → 生成 design.md
     ↓  (用户输入: 设计确认)
[阶段3] 任务拆解 → 生成 tasks.md
     ↓  (用户输入: 任务确认)
[阶段4] 逐步实现 → 按 tasks.md 顺序执行
     ↓  (用户输入: 验收)
[阶段5] 验收检查 → 对照需求和宪法验收
```

> 详细流程见 [SDD/workflow.md](SDD/workflow.md)

---

## 宪法体系说明

### 双宪法加载机制

每次工作必须同时加载两份宪法：

1. **公共基础宪法** `constitutions/constitution.md` — 所有服务通用规范（技术栈、分层架构、命名规范、数据库规范、编码规范等）
2. **专属宪法** `constitutions/constitution-{模块}.md` — 该服务的特有规范（包结构、特有技术、专属约束等）

专属宪法以公共宪法为基础，只记录差异和扩展，不重复公共内容。

### 宪法文件说明

| 文件 | 内容 |
|------|------|
| `constitution.md` | 服务概览、公共技术栈、分层架构、命名规范、数据库规范、编码规范、AI 约束 |
| `constitution-agent-parent.md` | 依赖版本管理、公共基础类规范、Starter 使用说明、子模块新增规范 |
| `constitution-auth-server.md` | OAuth2 流程、令牌管理、登录日志、MySQL/DM8 双库兼容、密钥安全 |
| `constitution-gateway.md` | WebFlux 编码规范、路由配置、认证白名单、Swagger 聚合 |
| `constitution-auth-resource.md` | 多客户隔离、三员管理、密码策略、Redis 权限缓存 |
| `constitution-mdm.md` | 树形结构防循环、字典两级结构、附件多后端存储、扩展属性 EAV 模式 |
| `constitution-extract.md` | Redis Streams、异步执行器、邮件通知、Nacos 注册、开放接口规范 |
| `constitution-report.md` | Word 渲染、Aviator 表达式、双包结构（report + toubao）、变量计算器体系 |
| `constitution-data.md` | Groovy 脚本规范、指标计算组件、CTE SQL 构建规范 |
| `constitution-rule.md` | DAG 计算、MVEL 表达式、Redis 缓存、定时任务开关规范 |
| `constitution-data-dg.md` | 数据同步幂等性、异步任务异常处理、外部 API 集成规范 |

---

## 模板文件说明

| 模板 | 用途 |
|------|------|
| `requirements-template.md` | 需求澄清阶段生成 requirements.md 时使用 |
| `design-template.md` | 技术设计阶段生成 design.md 时使用 |
| `tasks-template.md` | 任务拆解阶段生成 tasks.md 时使用 |
| `checklist-template.md` | 每个任务完成后执行宪法自检（含通用 + 各模块专属检查项） |
| `debug-template.md` | 在 `debug/` 目录记录调试过程时使用 |
| `sql-migration-template.md` | 在 `scripts/` 目录创建数据库迁移脚本时使用 |

---

## 当前功能列表

| 功能目录 | 模块 | 说明 |
|---------|------|------|
| [0001-data-qe-industry-deviation](specs/0001-data-qe-industry-deviation/) | data | 行业算子 |
| [0002-data-ic-adjust-factor](specs/0002-data-ic-adjust-factor/) | data | 内控调整因子算子 |
| [0003-data-qe-yoy-change-rate](specs/0003-data-qe-yoy-change-rate/) | data | 同比变动率算子 |
| [9063-ars-payee-enable-default](specs/9063-ars-payee-enable-default/) | ars | 收款人默认启用 |
| [9065-ars-travel-default-departure](specs/9065-ars-travel-default-departure/) | ars | 出行默认出发地 |
| [9067-ars-internal-adjustment-flow-variables](specs/9067-ars-internal-adjustment-flow-variables/) | ars | 内部调整流程变量 |
| [9072-ars-labor-form-select-payee](specs/9072-ars-labor-form-select-payee/) | ars | 劳务表单选择收款人 |
| [9087-ars-contract-effective-date-optimization](specs/9087-ars-contract-effective-date-optimization/) | ars | 合同生效日期优化 |
| [9095-ars-bank-account-length-fix](specs/9095-ars-bank-account-length-fix/) | ars | 银行账号长度修复 |

---

## 配置 AI 工具

### Kiro（当前已配置）

Kiro 通过根目录 `.kiro/steering/ai-rules.md` 自动注入规范，该文件已配置好，无需手动操作。

规范加载链路：

```
.kiro/steering/ai-rules.md（根目录，Kiro 自动读取）
    └── 引用 → docs-c1/00 AI-DOCS/SDD/constitutions/constitution.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/constitutions/constitution-{模块}.md × 10
    └── 引用 → docs-c1/00 AI-DOCS/SDD/workflow.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/commands/reference.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/commands/session.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/commands/workflow.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/commands/tasks.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/commands/show.md
    └── 引用 → docs-c1/00 AI-DOCS/SDD/commands/tools.md
```

> 注意：只有根目录下的 `.kiro/steering/` 会被 Kiro 自动加载，其他位置的同名目录无效。

### Cursor

创建根目录 `.cursorrules`：

```markdown
请在每次对话开始时，先阅读以下文件并严格遵守：
- docs-c1/00 AI-DOCS/SDD/constitutions/constitution.md（公共基础宪法）
- docs-c1/00 AI-DOCS/SDD/workflow.md（工作流程）
- docs-c1/00 AI-DOCS/SDD/commands.md（快速指令手册）

开始新需求前，必须询问用户确认所属模块（parent/auth-server/gateway/auth-resource/mdm/extract/report/data/rule/dg），
然后加载对应的专属宪法：docs-c1/00 AI-DOCS/SDD/constitutions/constitution-{模块}.md
```

### Windsurf

创建根目录 `.windsurfrules`：

```markdown
请在每次对话开始时，先阅读以下文件并严格遵守：
- docs-c1/00 AI-DOCS/SDD/constitutions/constitution.md（公共基础宪法）
- docs-c1/00 AI-DOCS/SDD/workflow.md（工作流程）
- docs-c1/00 AI-DOCS/SDD/commands.md（快速指令手册）

开始新需求前，必须询问用户确认所属模块（parent/auth-server/gateway/auth-resource/mdm/extract/report/data/rule/dg），
然后加载对应的专属宪法：docs-c1/00 AI-DOCS/SDD/constitutions/constitution-{模块}.md
```
