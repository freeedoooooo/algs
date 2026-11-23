# 抽取规则 → 抽取逻辑 → 模板解耦：三步演进设计稿

> 状态：讨论稿（未立项、未改代码）。日期 2026-11-23。
> 缘起：用户四个问题——①规则从映射升级为抽取逻辑的方案；②人工改值回流成规则建议的设计；
> ③文档类型模板与项目完全解耦的沉淀方案；④业内是否有成熟工具。
> 本文只给设计，不动代码；任何一期落地前需用户拍板。

## 0. 现状锚点与硬约束（方案必须贴合）

| 事实 | 代码位置 | 对设计的约束 |
|---|---|---|
| 抽取＝parse.json 纯投影，无模型、毫秒级 | `collect.build` / `service.run_extract:289` | 抽取逻辑升级必须保持"纯函数、无模型"，否则解耦红利全丢 |
| 规则＝三段 JSON（schema/mapping/transform）不可变版本快照 | `c1_extract_rule_version`、`rules.py:76` `_tpl_payload` | 三段必须是 dict；新规范要么塞进现有三段，要么加字段（需迁移），优先前者零迁移 |
| 现在 mapping 只有"单表选择＋列选择/改名" | `collect.apply_mapping:110` | 这是要被替换的"薄映射器"，但 passthrough 必须继续可用 |
| transform 只在入库时消费，暂存值永不改 | `loader.apply_transform:140` | 抽取逻辑内的"计算值"是抽取期产出，与入库 transform 是两回事，别混 |
| 血缘逐格落库：page/table/bbox/raw_text | `c1_staging_lineage`、`content_db.save_records:229` | 升级后的每个算子都必须能产出锚点，血缘不能退化 |
| 改值只动 values_json/field.value_text；original_json、original_text、lineage.raw_text 永不覆盖 | `content_db.patch_record:250` | **这是回流设计的金矿**：original vs values 的差＝人工信号，且原文锚点仍在 |
| 三段 JSON 目前由手写前端拼装 | `web/extract.js:376` savebtn | 规范升级必须同步给编辑器，否则规则写不出来 |
| 项目概念原则上不进平台（只认裸 id） | 记忆 2026-11-23、progress-handoff | 模板解耦方案必须让项目只持 task_id/task_file_id，不放 projectId 进平台库 |

---

## 1. 问题二：规则从"映射"升级为"抽取逻辑"

### 1.1 核心思路：三段 JSON 不变，引入 `spec` 方言 + 算子注册表

不新增 DB 列（零迁移）。做法是在 `mapping_json` 里加一个 `spec_version`，向后兼容：

```
mapping_json = {
  "spec_version": 2,              # 缺省/1 = 老映射（走 apply_mapping）；2 = 走新引擎
  "tables": [...],                # 表选择器（可多张，替代单表 table）
  "records": {...},               # 记录切分策略（一行一条 / 分组 / 键值对）
  "fields": [                     # 目标字段，每个字段是一条算子管道
    {
      "target": "金额",
      "type": "number",
      "pipeline": [
        {"op": "cell", "column": {"header_contains": "金额"}, "row": "current"},
        {"op": "regex", "pattern": "[\\d,.]+"},
        {"op": "number", "strip": ","}
      ],
      "validate": [{"op": "required"}, {"op": "range", "min": 0}],
      "on_fail": "flag"           # flag | reject | default
    }
  ]
}
```

- `spec_version` 缺省或 1 → `collect.build` 仍走 `apply_mapping` / `passthrough`，**存量规则与任务零影响**。
- `spec_version=2` → 走新引擎 `collect_logic.py`，纯函数、吃同一个 doc 信封、吐同样的 records 结构（index/values/original/lineage/review）。

### 1.2 算子（operator）分层——这是"领域壁垒"的载体

算子设计成**小而正交的纯函数**，`op` 名 + 参数 JSON，注册在一张表里（如 `collect_logic.OPS`）。分四族：

| 族 | 算子示例 | 输入→输出 | 锚点行为 |
|---|---|---|---|
| 取值（source） | `cell` / `row` / `block` / `page_text` | doc 上下文 → 字符串 | 带出 cell_bbox/page/raw_text |
| 变换（transform） | `trim` / `regex` / `number` / `date` / `replace` / `split` / `cut` | 字符串 → 字符串/数 | 透传上游锚点，标记 `derived` |
| 组合（compose） | `concat` / `template` / `lookup`(字典) / `join` / `coalesce` | 多字段/常量 → 字符串 | 合并多源锚点（多段血缘） |
| 逻辑/聚合（logic） | `if`/`switch` / `sum` / `count` / `group_by` / `pivot` / `dedupe` | 行集 → 行集/值 | 行级算子产出多锚点，记录级聚合标注来源行 |

关键约束（保证血缘不退化）：
1. 每个算子的返回统一为 `{value, anchors:[...], derived:bool}`；`anchors` 是 `_anchor()` 已产出的那种 dict 列表。
2. 管道末尾把各字段 anchors 汇总进 `lineage[target]`，`region_seq` 按序递增——现有 `c1_staging_lineage` 表和预览血缘查看器**完全不用改**。
3. 纯函数、无 I/O、无模型；复杂算子（如 LLM 分类）若未来要加，走独立"标注服务"预计算写回 doc，不塞进抽取引擎。

### 1.3 记录切分与多表

- `records.strategy`: `row`（默认，一行一条＝现状）/ `key_value`（左列字段名右列值，拼一条）/ `group_by`（按某列分组，组内多行）/ `one_per_page`。
- `tables` 支持多张表选择器（`index`/`header_contains`/`scope=page|stitched`），字段来源用 `table_ref` 指定；`stitched` 表照旧带 page 逐格。
- 跨表 join：`link` 算子按 key 字段把两张表的行关联，产生组合记录（审计常见：明细表＋汇总表）。

### 1.4 校验规则也进规范（为问题三铺路）

`validate` 数组是**声明式校验算子**（`required`/`regex`/`enum`/`range`/`cross_field`/`unique`），抽取期只评估并写 `review_state`/标记（不自动改值）。这样 `/review` 壳页将来可据此做"自动预检＋人工只复核高风险项"——把校验从纯人工变成置信度路由。

### 1.5 规范可验证性

`spec_version=2` 时提交规则，后端用 JSON Schema 校验 `mapping_json`（可用 `jsonschema` 或手写校验器，参照 `params.normalize` 的"非法回退＋警告"风格），拒绝未知 op、缺参、类型错，避免存进库却跑不起来。

---

## 2. 问题三：人工改值回流成规则建议

### 2.1 思路：不改值本身，改"改值的归因"

现状已有完整信号链：`original_text`（抽取原值）→ `values_json`（人工改后）→ `lineage.raw_text`（原文锚点）。回流不碰这些事实源，而是**新增旁路表**记录"差异事件"，由离线归因器生成"建议"，人审批后才生成新规则版本。

设计原则（对标 Rossum 的经验，见问题五）：
- **只用人工更正做信号，不用系统预测做信号**（避免自我强化的反馈回路）。
- **建议不自动生效**，必须人审批 → 新版本；旧任务引用旧快照，天然隔离。
- 建议必须带**证据**（样本数、命中率、原文锚点），可点回原件。

### 2.2 新表（旁路、可重建、不进主链路）

```
c1_correction（差异事件，append-only）
  id, task_file_id, record_id, field_name,
  rule_version_id,          -- 当时用的规则版本（关键：归因到具体版本）
  original_value, corrected_value,
  page, cell_bbox, raw_text, -- 当时 lineage 快照，便于回溯
  created_at, reviewer

c1_rule_suggestion（归因建议）
  id, rule_id, base_version_id,
  kind,                      -- column_remap|transform|enum_add|record_strategy|...
  payload_json,              -- 对 mapping_json 的补丁（JSON Merge Patch）
  evidence_count, confidence, status(pending|accepted|rejected|ignored),
  created_at, decided_at, decided_by
```

写入点：`content_db.patch_record` 事务内，比较 `vals[k]` 与 `original[k]`，不同则插一条 `c1_correction`（不阻断主流程，失败记日志）。

### 2.3 归因器（离线任务，纯函数）

按 `(rule_version_id, field_name)` 聚合 corrections，做模式识别：

| 观察到的差异模式 | 建议 kind | 生成的补丁示例 |
|---|---|---|
| 多数记录的某字段 original 来自 A 列、corrected 等于 B 列原文 | `column_remap` | 把该字段 `column` 选择器改成 B 列 |
| corrected 恒为 original 去空格/去逗号/截前后缀 | `transform` | pipeline 追加 `trim` / `number` |
| original 多种值都收敛到同一 corrected（同义词/简称） | `enum_map` | 加 `lookup` 字典算子 |
| corrected 总是 original 的某个子串（正则可描述） | `regex` | pipeline 加 `regex` 算子 |
| 多条记录被人工合并/拆分 | `record_strategy` | 建议改 `records.strategy` 或 `group_by` |
| 某字段几乎每次都被改 | `field_low_quality` | 提示该字段抽取质量差，建议专人复核规则 |

- `confidence = f(样本数, 一致率, 跨文件数)`，样本 < N（如 5）不出建议，只累计。
- 建议的 payload 是**对 mapping_json 的 Merge Patch**，人工接受时叠加到 base_version 生成新版本（`rules.create_version`），复用现有版本机制，零新链路。

### 2.4 闭环流程

```
校验改值 → c1_correction(事实)
        → 归因器(按规则版本×字段聚合)
        → c1_rule_suggestion(建议＋证据)
        → 人工审批(规则页"建议"抽屉)
        → 接受 → create_version(新快照) → current 前移
        → 下次抽取自动用新版本，改值率下降
```

度量：`改值率 = edited 记录数 / 总记录数`，按规则版本统计（staging_record.review_state 已有），作为"规则质量"的量化指标，也是模板沉淀的门槛。

---

## 3. 问题四：文档类型模板与项目解耦

### 3.1 先厘清两个概念（这是解耦的关键）

- **文档类型模板**："一类文档长什么样、怎么抽、抽什么字段"——规则＋字段契约＋校验策略的组合。**与项目、客户、业务系统零关系**。例：`银行流水-通用v2`、`审计凭证-报销单v1`。
- **项目**：业务侧概念，持有"这个项目有哪些 task、这些 task 属于哪一类文档"。

平台侧永远只有：task → rule_version → records。**模板就是"可复用的 rule_version 集合＋元数据"**，项目只在业务侧用 task_id 引用（延续 2026-11-23 的分层结论：业务侧中间表 project↔task，平台只认裸 id）。

### 3.2 模板的建模（建议新建一张轻量目录表，不动三段 JSON）

```
c1_doc_template
  id, code(稳定外部引用), name, description,
  kind_hint,            -- 文档类型关键词/特征（供上传时推荐模板）
  rule_version_ids,     -- JSON 数组：组成该模板的规则版本（可多规则：主表＋附表）
  field_contract_json,  -- 标准输出字段契约（字段名/类型/必填/同义词）——领域资产
  status(draft|active|deprecated),
  current_revision, created_at, updated_at
```

- 模板本身可以版本化（revision），但**核心内容是对不可变 rule_version 的引用**——rule 演进不破坏模板历史。
- `field_contract_json` 是"领域词汇表"：定义 `金额`/`交易日期`/`对手方` 等标准字段及同义词、类型、校验。这是跨项目可复用的真正资产，换项目时字段契约不变。
- 模板不存任何 projectId、客户名、业务表名。

### 3.3 沉淀流程（怎么"长出来"）

```
1. 冷启动：从一个真实项目里选一份样本 → 在抽取规则页建规则 v1
   （现有 extract.js 的"参考文件选表选列"已支持）
2. 批量跑：同项目多份同类型文档用该规则抽取 → 人工校验
3. 回流：改值经问题三的归因器 → 建议 → 审批 → 规则新版本
4. 提纯：改值率降到阈值以下后，把 field_contract + rule_version_ids
   打包成"文档类型模板"，发布为 active
5. 换项目：新项目只做两件事——
   a) 业务侧建 project↔task 中间表（挂 task_id）
   b) 上传时按 kind_hint 推荐/手选模板 → 复用同一 rule_version
   平台侧零改动、零新规则
6. 演进：某项目的改值进入全局归因池，经审批后发规则新版本；
   模板引用可整体指向新版本（或按项目保留旧版本快照）
```

要点：**沉淀是"从项目里提炼、回到平台里复用"**——项目是规则的训练场，模板是提炼出的领域资产。规则质量用改值率度量（问题三），达到门槛才允许发布模板，避免垃圾模板扩散。

### 3.4 与入库映射的关系

模板字段契约里的标准字段名 → 由业务侧的入库映射（`c1_load_table_field.rule_field → target_column`）决定写到哪张表哪个列。**换项目时只改入库映射，抽取规则与模板不动**——这正是"解析提取与项目解耦"的落点。

---

## 4. 问题五：业内是否有成熟工具（调研结论）

### 4.1 有，而且很成熟，但分层

| 层 | 代表 | 特点 | 对你的意义 |
|---|---|---|---|
| 模板/规则驱动 | Docparser、Xtracta、Parseur、ABBYY FlexiCapture/Vantage、IBM Datacap | 可解释、规则可查；版式漂移要重做模板 | 证明"规则资产"路线成立；但模板维护成本随文档族线性上涨 |
| 模型/置信度驱动 | Rossum、Hyperscience、Nanonets、Azure Document Intelligence、Google Document AI、Amazon Textract | 免模板、跨版式泛化；字段级置信度＋人工复核队列 | 置信度路由与四种校验源（Rossum）值得抄 |
| 开源解析 | Docling(TableFormer)、Unstructured、PaddleOCR(-VL)、MinerU | 解析层已商品化 | 别在解析层重复造轮子；你已用 Paddle 路线，方向对 |
| 审计专用 | **WPS 365 智能抽取（审计凭证 single+group 字段、底稿回流）**、合合 TextIn DocFlow、Grater 银行流水、昆山农商"AI 鹰眼" | 国内已有贴场景产品 | 直接对标：抽凭效率提升 50~70% 的量级；你的差异化必须在这些产品没有的地方 |
| 回流载体 | Label Studio（开源）、Rossum/Hyperscience（商业闭环） | 人工更正回流训练 | **开源侧"置信度路由→异常队列→审计留痕→回流"闭环无开箱产品，这是你的机会窗** |

市场事实（口径不一，取量级）：全球 IDP 约 CAGR 25%，CR5 约 42%（ABBYY ~16%、Kofax ~10%、OpenText ~6%）；规则驱动仍占 ~34%，说明规则路线没过时。IDC：LLM 38% / OCR 32% / ML 29%，三者协作，OCR 未被取代。

### 4.2 冷静的对标结论（不要妄自菲薄，也不要闭门造车）

1. **解析与通用抽取已经是红海**，且开源免费。你的解析层不是卖点，是入场券。
2. **商业工具普遍与项目/业务系统强绑定**——WPS 365 绑审计底稿、ABBYY 绑 BPM、UiPath 绑 RPA。你说的"模板与项目完全无关、换项目无缝衔接"，恰好是它们**没有**做的（它们的模板是项目内的配置）。这是真实差异化空间。
3. **逐格血缘＋不可变回执＋回流闭环三件套，没有一个现成产品全给**。Rossum 有闭环和校验源但无你要的中文表格逐格血缘；开源有解析和标注但无闭环。**你的组合（血缘×规则资产×项目解耦）在市面产品里有空位**。
4. **可借鉴的机制**（直接拿思路，不抄实现）：
   - Rossum：四种校验源（置信度/数据完整性/历史值/自定义）＋只用人工更正训练（防反馈回路）→ 抄进 §1.4 validate 与 §2.1 原则。
   - WPS 365：`single` 单值字段 + `group` 组字段（一笔多分录拆多行）→ 抄进 §1.3 `records.strategy=group_by`。
   - Docling TableFormer：跨页跨行跨列表格还原 → 作为解析层可替换后端的研究方向（挂起项已有 Docling vs MinerU）。
5. **验证方法**：用 20–100 份最脏的真实文件测**字段级准确率**，分阶段监控（解析→抽取→校验，误差累积），别看厂商 99% 的宣传数字。

### 4.3 一句话战略判断

> 别去和 ABBYY/Rossum 比解析和通用抽取；你的护城河 = **审计级逐格血缘（已有）＋ 可沉淀的领域规则/模板资产（本文 §1/§3）＋ 人工更正回流闭环（本文 §2）＋ 平台与项目零耦合**。这四件事市面上没有一家全做，且都是你的架构已经铺好地基的。

---

## 5. 分期建议与风险（待拍板）

| 期 | 内容 | 依赖 | 风险 |
|---|---|---|---|
| A | 抽取逻辑引擎（`spec_version=2` + 算子注册表 + 校验器），保留 v1 | 无 | 编辑器同步改造是最大工作量；算子设计要小而正交，别做成大一统 DSL |
| B | 回流闭环（c1_correction/suggestion + 归因器 + 建议审批 UI） | A（validate/kind 对齐） | 归因误报会污染规则；样本阈值＋人工审批是必须的安全阀 |
| C | 文档模板（c1_doc_template + field_contract + 发布门槛） | A＋B（质量度量） | 模板引用多规则版本的一致性；版本快照与项目隔离要守住 |

红线（沿用既有教训）：
- 三段 JSON 必须是 dict（`rules._tpl_payload`）；新规范塞进 `mapping_json`，不加列，零迁移。
- 抽取保持纯函数、无模型；血缘每个算子都要产出锚点。
- 回流旁路表可重建，不改 staging 事实源；建议不自动生效。
- 平台库不出现 projectId；项目只在业务侧中间表。
- 8765 常服全程不动；破坏性操作只在合成 task 上做。

## 6. 待用户拍板的口味点

1. `spec_version=2` 塞进 `mapping_json`（零迁移）vs 新增 `spec_json` 列（更清晰但要迁移）？本文默认前者。
2. 回流建议审批的粒度：按"单字段补丁"审批，还是按"整条规则新版本"审批？本文默认前者。
3. 模板发布门槛：改值率阈值定多少、样本量至少多少？建议先按"≥20 条记录、改值率<5%"起步，可调。
4. 归因器是定时任务还是改值时实时触发？建议离线定时（避免拖慢校验交互）。
