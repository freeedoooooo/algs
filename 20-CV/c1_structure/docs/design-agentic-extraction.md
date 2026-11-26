# Agent 化智能抽取：设计文档与技术实现方案

> 状态：**设计稿（未施工）**。日期 2026-11-26。
> 用户拍板（2026-11-26）：一期 = 规则生成 Agent；目标档位 = L3（自动执行 + 人工只审异常）；回流闭环暂缓。
> 后续追加诉求（2026-11-26 讨论）：① 生成阶段能否像 WorkBuddy 一样自主规划直到解决 → §4.6；
> ② 利用中间层已确认记录作为标准答案 → §6.7；③ 前端不只是加按钮 → §6.8；
> ④ 对话式助手深度交互 → §7（分期待定）。
> 本文只给设计与可施工技术方案，任何一期落地前需再次确认开工单。本文不修改产品代码。

---

## 0. 一句话结论

**不重写成通用 AI 抽取平台；在既有确定性骨架上加一层 Agent 编排，坚持「AI 只做选 / 生成 / 判断，值必须回锚，人只审异常」。**

生成 Agent 的输出是 **规则（`spec_version=2` 的 `mapping_json`）**，不是把 LLM 抽出的值直接写进暂存。规则可版本化、可审阅、可重放复现；直接写值会架空逐格血缘与审计留痕——那是本项目相对市面产品的护城河。

---

## 1. 现状锚点（方案必须贴合的代码事实）

| 事实 | 代码位置 | 对 Agent 方案的约束 |
|---|---|---|
| LLM 通道已跑通：OpenAI 兼容 `/chat/completions`，`urllib.request` 无第三方依赖，凭据只走环境变量 | `smart_extract.py::77 _call_llm`；`config.py:50-57` `LLM_*` / `SMART_STUB` | 直接复用并抽成公共 client，不引入 SDK / 框架 |
| 抽取三分流：`spec_version=3` → `smart_extract.build_smart`，其余 → `collect.build` | `service.py:333-336` | 生成 Agent **不改变分流**，产物仍是 v2/v3 规则 |
| v2 引擎是纯函数：吃 `parse.json` 信封、吐 records，无 DB / 无 I/O / 毫秒级 | `collect_logic/engine.py::219 build_logic`；`collect.py:148 build` | Agent 可做**干跑验证**：生成规则后立刻在参考文件上试跑 |
| 算子注册表 17 个算子，代码定义能力、JSON 只描述用法 | `collect_logic/registry.py:7 OPS`；`ops/{source,transform,compose,logic,aggregate,kv}.py` | LLM 的**输出词表就是这 17 个 op**，封闭集合，天然可校验 |
| 规则版本＝三段 JSON 不可变快照，三段必须是 dict | `store/catalog/rules.py::76 _tpl_payload`、`::132 create_version` | 零迁移：生成元数据塞进 `mapping_json`，不加 DB 列 |
| 规则版本 API 已完整（CRUD + versions + create_version） | `app.py:464-518` | 生成 Agent **不写库**，只产出草稿填进编辑器，保存复用既有 API |
| 参考文件 / 参考业务表已是公共配置项，随规则版本存进 `mapping_json.refs` | `web/extract.html:67-86`；`web/extract.js:469 collectRefs`、`:796` | 生成 Agent 的上下文输入**现成可用**，无需新增采集入口 |
| 复杂模式已有「场景模板 → 生成配置」骨架（`table`/`kv`/`page` 三类） | `web/extract.html:97-112`；`extract.js::genJson` | AI 生成是这条链路的升级版，前端结构已有落点 |
| 逐格血缘锚点形态固定：`{page,table_index,table_scope,space,cell_bbox,raw_text}` | `collect.py::25 _anchor`；`collect_logic/_common.py` | 生成规则必须让每个字段管道走到 source 算子产出锚点 |
| 声明式 `validate` 只写 `review.reason`、不改值 | `design-extract-logic-a.md` §1.3；engine `apply_pipeline` issues | 校验 Agent 沿用该约束，绝不自动改值 |
| 环境红线：Python `D:/miniforge3/envs/paddle/python.exe`；8765 常服不启停；8799/8797 临时 | `MEMORY.md`；`docs/progress-handoff.md` | 一切验证在 8799 + 合成资料上做，8765 不动 |
| `smart_extract.SMART_STUB` 默认 `1`（占位），真实调用需 `C1_SMART_STUB=0` | `config.py:55-57` | Agent 同样提供 Stub 开关，供前端/API 联调不烧 token |

---

## 2. 设计目标与非目标

### 2.1 目标（可度量）

1. **消灭手写 JSON**：用户选参考文件 + 填目标列名 → 一键生成可执行的 v2 规则草稿，人工只做确认/微调。
2. **消灭选规则 / 调参数**：解析后自动归类、自动推荐规则版本与解析参数（P1）。
3. **消灭逐条校验**：低置信字段自动确认、高风险进异常队列（P2，L3 目标态）。
4. **策略自优化**：人工改值回流成规则建议（P3，本期暂缓但预留数据结构）。

### 2.2 非目标（明确不做）

- 不做通用文档 AI / 自由问答；不做 LLM 直接写暂存值（v3 仅作无规则兜底通道）。
- 不改解析层（Paddle / 几何路线不动，有文本层 PDF 不需要 VLM——已有技术结论）。
- 不引入向量库、不引入 Agent 框架、不改 DB 表结构（零迁移）。
- 不追求 L4 免审：审计场景必须保留人工审批关卡与完整留痕。

---

## 3. 总体架构

```
交互层     一键智能处理  /  异常复核队列  /  对话式助手（本期只设计）
   │
Agent 编排层   归类 ─ 生成 ─ 路由 ─ 校验 ─ 回流（P0 只实现「生成」）
   │              生成 Agent：P0 一次性生成；P0.5 可选受限 ReAct 自迭代（见 §4.6）
确定性执行层   v1/v2 算子引擎（纯函数）│ v3 智能抽取（证据回锚）│ validate │ 入库映射
   │
资产与知识层   文档模板 + 字段契约 │ 不可变规则版本快照 │ 人工更正样本池
   │
唯一事实源     parse.json 文件信封 + 逐格 lineage —— 所有 AI 产出必须回锚到此
```

**分层铁律**：紫色智能层可以出错、可以被替换；灰色确定性底座不可被 AI 绕过。任何 AI 产物在进入执行层之前，必须通过确定性校验器。

---

## 4. Agent 技术栈（重点）

### 4.1 选型总表

| 层 | 选型 | 理由 | 明确不选 |
|---|---|---|---|
| LLM 传输 | `urllib.request` + OpenAI 兼容 `/chat/completions`，复用并抽出 `smart_extract._call_llm` 为公共 client | 零新依赖；端点已在本项目跑通；内网可指向自建；凭据只走环境变量 | 不选 `openai` SDK / `requests`：多依赖且版本漂移，与 `requirements.txt` 锁版本风格冲突 |
| 编排方式 | **P0 有限状态机**（固定 1~2 次调用）；**P0.5 可选受限 ReAct**（封闭工具白名单 + 确定性终止 + 预算上限，见 §4.6） | 决策路径可枚举、可回放、可单测；受限迭代兼顾"自主到解决"与审计可复现 | 不选 LangChain / LangGraph / AutoGPT 式**无界** ReAct：路径不可枚举、重试不可控、依赖重 |
| 结构化输出 | Prompt 内嵌 JSON Schema + `json.loads` 严格解析 + **定点修复重试 ≤2 次** | 兼容所有 OpenAI 兼容端点 | 不把 function calling / tool_use 当唯一约束（兼容端点未必支持） |
| 上下文构造 | 从 `parse.json` 确定性压缩：候选表 headers + 前 N 行样例 + 页码/scope + token 预算 | `parse.json` 是唯一事实源，不重新 OCR、不重复存储 | 不把整份信封无脑塞进 prompt |
| 输出校验 | 静态 schema 校验（op 名 / 必填参数 / 类型）+ **干跑验证**（在参考 doc 上试跑，算命中率） | 把"幻觉"变成可测的确定性失败 | 不采信 LLM 自报置信度 |
| 资产 / 记忆 | 既有 `c1_extract_rule_version` 不可变快照 + `mapping_json._agent_meta` | 零迁移、可回滚、旧规则引用隔离 | 一期不建向量库（规模不值当） |
| 可观测 | `tasklog.emit` + `logs/file_<id>.log`（沿用既有结构化日志） | 决策可追溯 | 不新建日志系统 |

**选型的核心逻辑**：这是一个**受约束的规则生成问题**，不是开放域 Agent 问题。封闭的算子词表（17 个 op）+ 确定的输入（`parse.json`）+ 可执行的验证器（v2 引擎）三者叠加，使"LLM 生成 → 机器验证 → 人工确认"成为可靠闭环；引入自由编排框架只会削弱这三者的确定性。

### 4.2 公共模块划分（新增 `agent/` 包）

```
agent/
├── __init__.py
├── llm.py            call_json(prompt, schema, *, llm=None, max_repair=2) -> (dict, meta)
│                     · 从 config 读 base_url/key/model/temperature/timeout
│                     · 缺配置显式抛错，绝不静默降级
│                     · 类型化异常：LLMUnconfigured / LLMTimeout / LLMBadJSON / LLMSchemaFail
├── context.py        doc_to_context(doc, budget=12000) -> {tables, text_hint, doc_shape}
│                     · 候选表用 collect._candidate_tables 的同一迭代序（不另造一套）
│                     · 每表保留 headers + 前 N 行样例 + index / scope / page
├── validate.py       validate_spec(spec) -> issues[]；dry_run(spec, doc) -> diagnostics{}
│                     · 静态校验：spec_version=2、op 在 OPS 词表内、参数类型、target 唯一
│                     · 干跑：调 collect.build_logic，统计字段非空率 / 命中锚点数
├── prompts/
│   ├── rule_author_v1.py   PROMPT_VERSION='v1'；render(ctx) -> str
│   └── _schema.py          生成目标 JSON Schema（供 prompt 与 validate 共用）
├── rule_author.py    P0 主体：generate_rule(doc, fields, refs, *, llm=None) -> GenerationResult
├── classifier.py     P1：识别单据类型（本期只留接口）
├── router.py         P1：选规则版本 / 解析参数（本期只留接口）
├── validator_agent.py P2：置信度分流（本期只留接口）
└── orchestrator.py   P2：一键流程状态机（本期只留接口）
```

**依赖 Inject 约定**：所有入口都接受 `llm=None` 可注入函数（与 `build_smart(doc, tpl, llm=None)` 同构），生产走真实端点，单测走 fake LLM——这是让 Agent 逻辑可测的关键。

### 4.3 一次 Agent 调用的标准生命周期（六步）

```
① 构造上下文（确定性）  doc_to_context → 表清单 + 样例行 + token 预算截断
② 渲染提示词（版本化）  PROMPT_VERSION 写进 meta，改提示词即换版本
③ LLM 调用（temperature=0，超时 config.LLM_TIMEOUT）
④ 严格解析             json.loads；失败 → 把报错回喂模型定点修复（≤2 次）
⑤ 静态校验             op 名必须在 OPS 词表；参数类型/target 唯一性
⑥ 干跑验证             collect.build_logic(spec, doc) 试跑：字段非空率、锚点命中数
                       → 产出 GenerationResult{spec, meta, diagnostics, confidence}
```

**置信度不是 LLM 自报，而是确定性信号合成**：

| 信号 | 计算方式 | 权重方向 |
|---|---|---|
| 列选择器命中率 | 生成的 `header_contains`/`name` 是否真能在参考 doc 表头命中 | 越高越可信 |
| 字段非空率 | 干跑后各字段 `values` 非空占比 | 越高越可信 |
| 锚点覆盖率 | 有 `lineage` 的字段数 / 字段总数 | 低于阈值直接标红（无血缘＝不可审计） |
| 样例覆盖数 | 参与上下文的样例行数 | 太少（<2 行）标低置信 |

`confidence` 只用于**分流**（进人工确认 vs 允许后续自动放行），不用于自动改值。

### 4.4 可复现性设计

生成元数据写进 `mapping_json._agent_meta`（仍是 dict，零迁移）：

```json
"_agent_meta": {
  "generator": "rule_author",
  "prompt_version": "v1",
  "model": "gpt-4o-mini",
  "input_sha256": "<doc+fields+refs 规范化后的摘要>",
  "temperature": 0,
  "tool_version": "<OPS 注册表版本号>",
  "created_at": "2026-11-26T09:xx:xx"
}
```

作用：任何历史规则版本都能回答"是哪版提示词、哪个模型、哪份输入生成的"；模型或算子升级后，旧版本仍可重放验证。

### 4.5 失败与降级策略（红线）

- 未配置 LLM → 显式报错（`LLMUnconfigured`），前端提示设 `C1_LLM_*`，**回退手动模式**；绝不静默走 passthrough（那会让人误以为规则已生效）。
- 超时 / 非法 JSON / schema 失败 / 干跑全空 → 返回诊断信息，**不落库、不建规则版本**。
- 干跑锚点覆盖率为 0 → 标记 `warning`，禁止"一键确认"，须人工逐字段检查。
- Agent 永远不写 `staging`、不改 `values`、不碰 `original` / `lineage` 事实源。

### 4.6 从"一次性生成"到"自主迭代到达标"（受限 ReAct）

用户诉求：一两次调用没解决时，能否像 WorkBuddy 一样自己规划分析，直到解决？
**结论：能，但只放在生成阶段，且必须是"受限 ReAct"，不是无界自由循环。**

#### 4.6.1 为什么能放在生成阶段

生成阶段的操作对象是**规则**，规则可版本化、可审阅、可回滚，风险低；而执行/入库阶段操作的是**证据值与审计回执**，让 LLM 自由迭代会断掉血缘链。因此分层结论如下：

| 层 | 能否迭代到解决 | 原因 |
|---|---|---|
| 规则生成 | **能**（受限 ReAct，本节设计） | 操作对象是规则，可版本化、可回滚、可审阅 |
| v3 智能抽取 | **有限重试**：证据匹配不到时换证据重试 1~2 次 | 值必须回锚，匹配不到仍留空，不能无中生有 |
| v2 执行抽取 | **不需要** | 纯函数，规则对就必出结果，毫秒级，没有"没解决"这回事 |
| 校验 / 入库 | **绝不开放** | 校验只标记不改值；入库是审计回执，必须确定性 |

#### 4.6.2 受限 ReAct 的三个约束

```
目标：生成一份干跑全字段命中的 v2 规则
① 工具集封闭：inspect_tables / validate_spec / dry_run / revise_spec 四个工具，
   LLM 只能从中选；不得执行 SQL、不得改暂存值、不得碰入库——越界在代码层拒绝，不靠提示词
② 终止由确定性验证器判定：达标 = 字段命中率 + 锚点覆盖率 + issues 全部过阈值；
   LLM 自评"我觉得好了"不算数；最多 6 轮，耗尽预算带诊断交人工
③ 每轮留痕：工具调用与诊断写 tasklog；最终产物仍是规则草稿，仍需人工确认
```

生命周期：`LLM 观察+规划 → 选工具 → 读结果 → 再规划 → … → 达标 → 规则草稿 → 人工确认存版本`。

#### 4.6.3 代价（必须诚实）

- **成本与延迟**：从 1 次调用涨到 3~6 次，单条规则生成由秒级到十几秒级。
- **可复现性下降**：同输入路径可能不同；靠 `_agent_meta` 记录每轮工具调用与诊断补偿，但弱于一次性生成。
- **复杂度上升**：需工具调度器、轮次状态机、预算控制、诊断回喂 prompt，P0 工作量约翻倍。

**分期建议**：P0 先交付一次性生成 + 干跑验证（快、稳、可复现）；把受限 ReAct 作为 **P0.5 增强项**——等真实文件跑出"一次生成命中率不够"的样本再决定。没有实测数据就上 ReAct，是在为未证实的问题付复杂度成本。

### 4.7 验证信号来源：中间层已确认记录作为标准答案

用户指出：抽取数据落在中间层，可否用它让 Agent 自己规划生成直到可用规则并保存？
**结论：可以，且它把"规则可用"从 LLM 自评升级为精确对拍。**

#### 4.7.1 中间层提供的三样信号

| 中间层字段 | 作用 |
|---|---|
| `values_json`（人工确认/改后的值） | **标准答案**：规则跑出来该长什么样 |
| `original_json`（抽取原值） | 反推需要的变换（trim / number / replace …） |
| `c1_staging_lineage`（逐格锚点） | 验证生成的规则血缘不退化 |

`review_state` 语义边界：**只有 `confirmed` 和 `edited` 能当标准答案**；`pending` 未背书、`rejected` 是明确否定，均不得用于训练/验证。

#### 4.7.2 闭环步骤（关键：内存重跑，不落库）

```
① 取该资料中间层 confirmed/edited 记录 → targets
② 取同一 file_id 的 parse.json → doc（唯一事实源）
③ LLM 生成 v2 spec（可叠加 §4.6 的受限 ReAct 迭代）
④ 用 collect.build_logic(spec, doc) 在内存里重跑   ← 关键：不落库
⑤ 逐字段与 targets 对拍：命中率 / 锚点覆盖 / issues
   守卫：records 数量与 targets 不一致 → 直接判不达标并提示"样例不完整"，不靠 LLM 硬凑
⑥ 达标 → 保存规则新版本；不达标 → 带 diff 诊断回喂，再迭代
```

**第 ④ 步是核心红线**：`content_db.save_records` 是 `_purge` 先删后插的覆盖语义（`store/content_db.py:182,191`），验证绝不能调 `POST /extract`，只能在内存里跑纯函数引擎对拍，中间层人工成果全程不被碰。

**第 ⑥ 步的"保存"复用既有 `create_version`**（`app.py:512`）：不可变快照、当前版本前移、旧资料引用旧版本不受影响，零新增链路、零迁移；`_agent_meta` 记录来源 file_id 与提示词版本。

这不等于用户先前拍板"暂缓"的回流闭环：回流是持续归因 + 自动建议 + 审批发版；这里只是一次性从已校验资料提炼规则，用中间层当验收标准，共用数据、互不冲突，且不需要新表。

---

## 5. 五个 Agent 的职责与实现路径

| Agent | 消灭的手工动作 | 输入 | 输出 | LLM 次数 | 分期 |
|---|---|---|---|---|---|
| **生成** `rule_author` | 手写 `mapping_json` / 字段说明 / 提示词 | 参考 doc + 目标列名 + 业务表列（+ 中间层已确认记录作标准答案） | v2 spec 草稿 + diagnostics | P0：1（+≤2 修复）；P0.5：受限 ReAct ≤6 轮 | **P0 本期** |
| **归类** `classifier` | 上传后选单据类型 / 选规则 | `doc_to_context` 的形状特征 | 单据类型 + 候选模板 id | 1 | P1 |
| **路由** `router` | 选 v1/v2/v3、调解析参数 | 归类结果 + doc 形状 + 规则资产清单 | `rule_version_id` + 参数建议 | 0~1（多数可规则判定） | P1 |
| **校验** `validator_agent` | 逐条人工找错 | `validate` issues + 置信度信号 | 自动确认集 + 异常队列 | 0~1（仅高风险字段） | P2 |
| **回流** `feedback` | 人工改规则、凭经验调策略 | `original` vs `values` 差异 + 锚点 | 规则补丁建议（人工审批） | 1（离线批量） | P3 暂缓 |

**P0 只实现「生成」**；其余四个本期只留接口与数据结构占位，不接 LLM、不进主链路，避免未验证的自动决策污染现有流程。

---

## 6. P0 规则生成 Agent：可施工技术方案

### 6.1 用户故事

> 用户在抽取规则页点「新建规则」，选一份参考文件（已解析）、从参考业务表勾选/填写目标列名，点「AI 生成规则」；系统在数秒后把一份可执行的 `spec_version=2` 配置填入「复杂抽取」编辑器，并标出低置信字段；用户审阅微调后按原有方式保存，生成一个不可变规则版本。

### 6.2 新增 API

```
POST /api/agent/generate-rule
Body: {
  "file_id": 8,                      // 参考文件（必填，须已解析出 parse.json）
  "fields": [                        // 目标列名 + 说明（来自业务表列 / 手填）
    {"target": "交易金额", "description": "借方发生额，含千分位"},
    {"target": "交易日期", "description": "YYYY-MM-DD"}
  ],
  "datasource_id": 1,                // 可选，参考业务表
  "table": "biz_test_1"              // 可选
}
Resp 200: {
  "spec": { "spec_version":2, "tables":[...], "records":{...}, "fields":[...], "_agent_meta":{...} },
  "schema": { "fields":[{"name":"交易金额","type":"text"}, ...] },
  "confidence": 0.82,
  "diagnostics": {
     "field_hits": {"交易金额": 24, "交易日期": 24},
     "anchor_coverage": 1.0,
     "issues": [],
     "warning": null
  }
}
```

**路由命名注意**：必须避开现有 `GET /api/extract-rules/{rule_id}`（path param 是 int）。用独立前缀 `/api/agent/...`，不要挂在 `/api/extract-rules/generate` 下，否则 `generate` 会被 int 转换器拒绝（422）或触发路由歧义。

新增端点必须：走 `run_in_threadpool`（LLM 是阻塞 I/O，不占事件循环）；复用 `_json_body` / 类型化业务异常；写 `tasklog.emit`；缺配置返回明确的 `BadRequest` / `503`。

### 6.3 提示词与输出契约

提示词（`prompts/rule_author_v1.py`）输入三段：

1. **系统约束**：只允许使用给定的 17 个 op；每个字段的 pipeline 第一个算子必须是 source 类（`cell`/`kv`/`row`/`block`/`page_text`），以保证产出锚点；不知道就留空 pipeline，不要编造列名。
2. **上下文**：候选表（index / headers / 前 3 行样例 / 页码 scope），文本行概要（非表格文档走 `kv`）。
3. **目标**：返回严格 JSON，字段为 `{spec_version:2, tables, records:{strategy}, fields:[{target,type,pipeline,validate?}]}`；附 JSON Schema 文本。

输出契约由 `prompts/_schema.py` 定义，并被 `validate.validate_spec` 复用——**同一份 schema 既约束生成、又校验生成**，杜绝两边漂移（沿用项目 `params.py` 单一 schema 源的既有经验）。

### 6.4 前端交互（改动最小）

- 在 `web/extract.html` 的参考文件 / 参考业务表配置下方、规则模式上方，新增一个「AI 生成规则」按钮（与既有「生成配置」并列，但语义不同：后者是场景模板，前者调 LLM）。
- `web/extract.js`：点击后 POST `/api/agent/generate-rule`，成功后：
  - `setMode('json')`，把 `spec` 序列化进 `#jsonspec`；
  - `schema` 回填到隐藏变量，保存时与既有 json 模式一致（不新增保存链路）；
  - diagnostics 以 banner 展示：命中率 / 锚点覆盖 / issues；低置信字段在 JSON 里以注释性提示列出（不破坏 JSON 合法性）。
- 失败时沿用 `#emsg` 展示错误文案，编辑器保持原状。
- 不改动 `savebtn.onclick` 的既有三段 JSON 组装与 `create_version` 调用；`_agent_meta` 随 `mapping` 一起被保存。
- **完整交互不止一个按钮**——按钮只是触发点，四段式面板与三个落点见 §6.8。

### 6.5 干跑验证闭环（本方案的关键创新）

生成后**不等用户确认就先自我验证**，这是把 LLM 幻觉挡在门外的确定性关卡：

```python
# agent/rule_author.py 核心伪码
def generate_rule(doc, fields, refs, *, llm=None):
    ctx = context.doc_to_context(doc)                  # ① 确定性压缩
    prompt = prompts.rule_author_v1.render(ctx, fields, refs)  # ② 版本化提示词
    raw, meta = llm_module.call_json(prompt, schema, llm=llm)  # ③④ 调用+严格解析
    issues = validate.validate_spec(raw)               # ⑤ 静态校验
    if issues:
        raise LLMSchemaFail(issues)                    # 不落库
    diag = validate.dry_run(raw, doc)                  # ⑥ 干跑：调 collect.build_logic
    conf = confidence.from_diagnostics(diag)
    raw['_agent_meta'] = {**meta, 'input_sha256': sha256_of(doc, fields, refs)}
    return GenerationResult(raw, schema_of(raw), conf, diag)
```

`dry_run` 只用 `collect.build_logic`（纯函数、毫秒级），不写 DB、不发模型调用；因此生成一次规则的额外成本 = 1 次 LLM + 几十毫秒。

### 6.6 验收口径

| 项 | 口径 |
|---|---|
| 正确性（golden） | 用 ≥3 份真实参考文件生成规则，跑出的 records 与**中间层已确认记录逐字段相等**（含 lineage 锚点）；无已确认记录时退回与人工手写规则逐字段相等 |
| 结构合法性 | 生成 spec 100% 通过 `validate_spec`（未知 op / 缺参 / 类型错 / target 重复一律拒绝） |
| 血缘 | 干跑后 `anchor_coverage == 1.0`（每字段都有锚点）；否则标 warning 且禁止一键确认 |
| 失败语义 | 未配置 LLM / 超时 / 非法 JSON → 显式错误，不落库、不建版本、不回退 passthrough |
| 兼容性 | 既有 v1/v2/v3 规则输出逐字段不变；30+ 既有单测全绿；`compileall` 通过 |
| 环境 | 8799 临时服务验 UI + API（Stub 模式不烧 token），验完即停；8765 不动 |
| 中间层保护 | 生成/对拍前后断言：目标资料 `c1_staging_record` 行数与 `values_json` 摘要不变（守 `_purge` 红线） |
| 样例守卫 | targets 记录数与内存重跑记录数一致；不一致报"样例不完整"，不出规则 |

### 6.7 生成闭环：从中间层标准答案到达标保存

把 §4.7 的信号来源落成前端可见的四步闭环（与 §6.5 干跑验证同一条链路，增加对拍环节）：

```
选已校验资料作为样板（confirmed/edited）
  → 生成 spec（§6.5，可叠加 §4.6 迭代）
  → 内存重跑 collect.build_logic，与中间层 targets 对拍（§4.7）
  → 展示字段一致率 / 锚点覆盖 / 差异明细
  → 达标：保存为新规则版本（create_version）；未达标：带 diff 再迭代或交人工
```

**双动作分离**："保存为新版本"只改规则资产，不碰当前资料的暂存；"应用到当前资料"需在资料处理页显式点「执行抽取」。两者绝不在一次点击里合并。

### 6.8 前端交互：四段式面板与三个落点

用户明确：前端交互不只是加按钮。按钮只是触发点，完整交互是四段式面板。

#### 6.8.1 四段式面板

| 段 | 用户看到什么 | 为什么必须有 |
|---|---|---|
| ① 输入 | 目标列名 chip、参考文件 / 业务表来源 | 复用抽取页已做的公共参考配置，不让用户重填 |
| ② 过程 | 每轮迭代做了什么、命中率变化 | "自主规划直到解决"的可见性；不展示过程，用户视其为黑盒不敢信 |
| ③ 对拍 | 与中间层已确认记录的字段一致率、锚点覆盖、差异明细 | 把"规则可用"变成用户能亲自核对的证据，不是系统自说自话 |
| ④ 确认 | 保存为新版本 / 返回修改 / 应用到当前资料 | 放行权在人手里；明确区分"存规则"与"抽数据" |

#### 6.8.2 三个落点分工

1. **抽取规则页（配规则时）**：新建/编辑抽屉里加「AI 生成规则」，结果进 JSON 编辑器——**规则生产**入口。
2. **资料处理工作台（用规则时）**：抽取节点加「AI 生成并应用」——针对当前资料生成→对拍→存版本→绑定→执行。这是用户要的"少交互"主入口（分期见 §7）。
3. **校验页 / 数据预览（P2 目标态）**：校验路由的异常队列视图；本期不做，先留位。

每个落点嵌在现有页面结构里：规则页用现成 `.drawer wide`，处理台用现成 `.proc-ruledetail`（`web/process.js:217`），过程日志复用运行日志面板样式（`STEP/OK/WARN` 分级）。

#### 6.8.3 前端改动清单（供开工单估算）

- `web/extract.html/js/css`：抽屉内加生成触发 + 四段式结果面板。
- `web/process.js`：抽取节点加"生成并应用"分支 + 状态轮询。
- 新增 `web/agent.css`（面板样式）与少量 JS 模块；**不新建页面**，全部嵌在现有页面里。
- 关键约束：生成结果是**草稿**，保存走既有 `create_version`，前端不新增保存逻辑。

#### 6.8.4 明确不做

- 不做聊天式对话界面替代规则配置——审计场景要可审阅证据，不是对话（对话式助手另见 §7，定位不同）。
- 不做独立 Agent 控制台——避免多一个功能入口（`/sources` 仍是唯一入口）。
- 本期不自动放行入库——④ 的确认只存规则，应用仍需显式点执行抽取。

---

## 7. 对话式助手（聊天窗口与系统深度交互）

> 状态：**仅设计、未立项**。用户 2026-11-26 提出"能不能做一个聊天交互窗口，跟系统页面深度交互"。分期归属待拍板。

### 7.1 定位：副驾驶，不是替代品

聊天窗口擅长**编排与问答**（"把 8 号按上次规则抽了""为什么这条金额对不上"），不擅长**精确审阅 24 条记录的表格**。因此它不是新入口取代现有页面，而是**嵌在资料处理页里的侧边抽屉**——聊完一步，卡片上点"查看记录"跳 `/preview` 精看，点"确认入库"仍走既有四步向导。守住 `/sources` 唯一入口约定，不新增导航项。

### 7.2 技术路径选型：API 工具调用型（推荐）

```
前端：处理页侧边抽屉（复用 .drawer）
  ↓ POST /api/agent/chat  {file_id, messages}
后端：会话编排器
  ↓ 用户意图 → 工具调用（工具白名单 = 现有业务 API 包装成 schema）
  ↓ SSE 流式回传：思考 → 工具名+参数 → 执行结果 → 答复
  ↓ 工具执行走 run_in_threadpool，全程 tasklog 留痕
```

| | 路径 A：API 工具调用型（推荐） | 路径 B：浏览器操作型（browser-use / Playwright） |
|---|---|---|
| 操作方式 | 调后端已有业务 API（`/api/sources/{id}/extract` 等） | 真点按钮、填表单、读 DOM |
| 稳定性 | 高：API 契约固定，不随 UI 改版失效 | 低：DOM 一变就崩，选择器维护成本高 |
| 速度 | 秒级 | 慢，每步要渲染、等待、截图 |
| 审计留痕 | 天然：每次工具调用可记入 `tasklog` | 难：需操作层额外埋点 |
| 能力边界 | 只做 API 覆盖的操作 | 理论可操作任何页面 |
| 适配本项目 | **高**：`/api/sources/{id}/...` 已全流程覆盖 | 低：需常驻浏览器进程，与离线内网部署冲突 |

**判断：选 A**。后端 API 已覆盖解析/抽取/校验/入库/查询，"深度交互"无需让模型点按钮。路径 B 留作远期备选——仅当出现"API 未覆盖、必须操作 UI"的场景才值得引入。

### 7.3 工具分级（安全设计核心）

| 级别 | 工具举例 | 策略 |
|---|---|---|
| 只读 | 查资料状态、查暂存记录、查规则版本、查入库回执 | 直接执行 |
| 执行 | 执行抽取、重新解析、生成规则草稿 | 执行前回显"将做什么"，人点确认 |
| 危险 | 入库、删除资料、重放解析（清空暂存）、改规则当前版本 | **对话里永不直接执行**，只生成深链，跳既有页面由人操作 |

第三级是关键：让聊天能编排流程，但不绕过既有门禁、审批与只读守卫。用户说"确认入库"，助手回答"请到入库向导确认"，而不是自己写库。

### 7.4 需额外解决的三个问题

1. **上下文窗口**：不把整份 `parse.json` 塞进去；只注入资料元信息 + 规则摘要 + 中间层统计，细节按需调只读工具取。
2. **多轮状态**：会话须记住"当前资料是谁、刚生成了什么草稿"，否则"按上次规则抽"无法解析；服务端存轻量会话态，不落业务库。
3. **失败语义**：工具调用失败（状态不对、缺 parse.json）必须回显原始错误，不能让模型编"已完成"。

### 7.5 交互效果（草图要点）

- 顶部显示上下文（资料 #8 · 银行流水）；用户输入自然语言指令。
- 助手回显工具执行清单（读状态 → 匹配规则 → 调 `/extract` → 对拍中间层），每步带 ✓。
- 答复给结果卡片（字段一致率、金额合计、日期范围），差异项标"待复核"并可跳详情。
- 输入框支持继续追问，或"确认入库""改规则"等意图。

### 7.6 分期建议（待拍板）

- **一期（先）**：只读问答 + 导航——查状态、查记录、跳页面，验证交互价值，风险最低。
- **二期**：加执行类工具——抽取、生成规则，带确认回显。
- **危险类永远只生成深链**。

本报告建议：不把对话式助手插进 P0，另起独立路线（与 P0 规则生成 Agent 并行评估），待 P0 落地后再定档期。

---

## 8. 从 L2 到 L3 的演进路径（P1 / P2，本期不施工）

- **P1 归类 + 路由**：`classifier` 用 doc 形状特征 + 一次 LLM 调用给单据类型；`router` 优先用**确定性规则**（按 `kind_hint` / 表头关键词匹配）判定，只有规则无法判定时才调 LLM。产出候选 `rule_version_id` 与解析参数建议， UI 上以"推荐"形式呈现，人可改选。
- **P2 校验路由 + 异常队列**：把既有 `validate` issues 与 §4.3 的置信度信号合成分流——高置信字段自动确认（`review.state` 仍走既有 `approve` 机制），低置信字段进异常队列；一键处理按钮把解析→生成→抽取→校验串成有限状态机，每步状态写 `tasklog`，可回放。此时才真正达到 L3。
- **P3 回流闭环**（暂缓）：沿用 `design-rule-evolution.md` §2 的 `c1_correction` / `c1_rule_suggestion` 旁路表设计；**只用人工更正做信号**，建议不自动生效，人工审批后发新版本。

---

## 9. 数据模型与迁移

**零迁移**。新增内容全部落在既有 `mapping_json` 字典内部：

- `_agent_meta`：生成溯源（§4.4）。
- `refs`：参考文件 / 参考业务表（前端已在存）。
- 未来 `c1_correction` / `c1_rule_suggestion` 为旁路新表（可重建、不进主链路），P3 再建，本期不动。

三段 JSON（`schema_json` / `mapping_json` / `transform_json`）保持 dict 约束；DB 表结构与迁移脚本不改。

---

## 10. 风险与红线

| 风险 | 缓解 |
|---|---|
| LLM 幻觉出不存在列名 | 干跑验证 + 锚点覆盖率门槛；生成 spec 只在参考 doc 上验证通过才标可用 |
| 模型/提示词升级导致旧规则行为漂移 | `_agent_meta` 记录版本；规则版本快照不可变，旧资料引用旧版本 |
| 自动决策串错规则 | P1 归类/路由保留人工改选入口；P2 分流只针对低风险字段自动确认 |
| LLM 成本 / 延迟 | temperature=0、上下文预算截断、Stub 模式联调、只在生成/归类/高风险校验调用 |
| 凭据泄漏 | 只走环境变量，不入库不打印（沿用 config 约定） |
| 受限 ReAct 成本 / 路径漂移 | P0 先一次性生成，P0.5 才上迭代；预算上限 6 轮；`_agent_meta` 记录每轮工具调用 |
| 对话助手越权操作 | 工具三级分级；危险类只生成深链不执行；`/sources` 仍是唯一入口 |
| 误伤常服 | 8765 不启停；所有验证在 8799 + 合成资料上完成 |

**不可让步的红线**：三段 JSON dict、零迁移；抽取引擎纯函数（模型只在编排层/生成层）；AI 值必须回锚；`validate` 只写 `review.reason` 不改值；平台库不出现 `projectId`；8765 不动。

---

## 11. 分期与开工建议

| 期 | 内容 | 依赖 | 状态 |
|---|---|---|---|
| P0 | 规则生成 Agent（`agent/` 公共模块 + `generate_rule` + API + 四段式面板 + 干跑/对拍验证） | 无 | **待确认开工** |
| P0.5 | 受限 ReAct 自迭代（§4.6）：工具调度器 + 轮次状态机 + 诊断回喂 | P0 实测出现"一次生成命中率不够"的样本 | 条件触发，未立项 |
| P1 | 归类 + 路由 Agent，规则资产推荐 | P0 产出的可信规则 | 待办 |
| P2 | 校验路由 + 异常队列 + 一键流程（L3 成型） | P1 | 待办 |
| P3 | 回流闭环（旁路表 + 归因器 + 审批） | P2 的质量度量 | 暂缓 |
| 独立线 | 对话式助手（§7）：API 工具调用 + 三级权限 + SSE | 分期待拍板 | 仅设计，未立项 |

P0 建议拆成 3 个可独立验收的任务：① `agent/` 公共层（llm/context/validate/prompts，含单测）；② `generate_rule` + API + 干跑/对拍；③ 前端四段式面板与诊断展示。每个任务完成后汇报验证结果与设计取舍，确认后再进下一个。

---

## 12. 待确认事项

1. 生成入口放在**抽取规则页**（本文默认：改动最小、参考配置现成），还是资料处理工作台？
2. P0 是否需要"生成即保存为新规则版本"的快捷路径，还是必须先经编辑器人工确认？（本文默认后者，L3 再放开自动保存）
3. `_agent_meta` 是否接受写进 `mapping_json`（零迁移方案），还是希望新增独立 DB 列（更清晰但要迁移）？本文默认前者。
4. P0.5 受限 ReAct 是否立项？本文默认等 P0 实测样本再定，不 preemptive 上复杂度。
5. 对话式助手（§7）分期归属：插在 P0 之后，还是另起独立路线与 P0 并行评估？本文默认后者。
6. 对话助手一期范围：先只读问答 + 导航（本文默认），还是直接含执行类工具？
