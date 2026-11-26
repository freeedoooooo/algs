# 指标 / 规则 / 框架计算层设计稿（全路径可回溯 · 审计可信）

> 状态：**设计稿，未施工**（2026-11-26）。目标：在既有结构化平台之上，用最小施工量增加「指标 → 规则 → 框架」三层计算，并把计算结果与入库业务表、源文件逐格血缘完整串联，形成可演示的全路径追溯闭环。
> 阅读前提：本稿只描述方案与取舍，不含任何产品代码改动。施工须在用户确认开工单后按分期推进，每期先汇报验证结果再进入下一期。

---

## 1. 结论摘要

现有平台已经具备完整血缘底座，新增计算层不需要重做血缘，只需**挂接**：

1. **业务表行**已写入 `file_id + record_id` 两个溯源列（`store/loader.py` 的 `TRACE_COLS`，`service.run_load` 的 `extra_values`）；
2. **暂存层**已有逐格血缘 `c1_staging_lineage`（页码 / 表下标 / `cell_bbox` / `raw_text`），并有 `/api/staging/locate/{record_id}` 反查接口；
3. **数据看板**已实现「点业务表单元格 → 反查 `record_id` → 高亮原图格子」的单元格级双向血缘（`web/dashboard.js`）。

因此本方案的核心只有一句话：**让每一层计算结果携带输入锚点（input refs），锚点最终落到 `record_id`，从而复用既有反查链路直达源文件格子**。指标结果锚定业务表行，规则结果继承指标结果的锚点，框架结果继承规则结果的锚点——血缘沿计算链逐层传递，任意结果都能一键钻取到源文件。

三个模块的定位（最简抽象）：

| 模块 | 输入 | 运算 | 输出 | 血缘锚点 |
|---|---|---|---|---|
| 指标 | 数据库表（列 + 聚合） | SUM / COUNT / AVG / MIN / MAX / COUNT_DISTINCT | 指标值 | 参与计算的行：`(file_id, record_id, 原始值)` 列表 |
| 规则 | 已计算的指标 | 结构化条件比较（不用表达式解析器） | 通过 / 不通过 + 值 | 依赖的指标结果 ID → 间接继承行锚点 |
| 框架 | 已计算的规则 | 加权求和 / 全通过 / 任一通过 / 一票否决 | 得分 + 结论 | 依赖的规则结果 ID → 逐层继承到行锚点 |

---

## 2. 现状事实与可复用锚点（已核对代码）

| 事实 | 代码锚点 | 对本设计的意义 |
|---|---|---|
| 12 张 `c1_*` 表，DB 唯一事实源，无外键，人工建表 | `store/migrations/001_file_baseline.sql` | 新表沿用同风格：`IF NOT EXISTS`、应用层维护引用完整性、单独迁移脚本 |
| 业务表溯源代码两列 `file_id + record_id` | `store/loader.py:111 TRACE_COLS`、`:224 write_record(extra_values)` | **指标读取业务表时把这两列一起 SELECT**，即可拿到行锚点 |
| 只读查询已有白名单 + 参数化 + 按 `file_id` 过滤 | `store/loader.py:257 query_rows` | 指标计算复用 `connect_datasource` / `list_tables` / `list_columns`，不新写 SQL 拼接 |
| 逐格血缘可查 | `c1_staging_lineage`；`app.py:899 /api/staging/locate/{record_id}` | 结果钻取链路终点现成，无需改造 |
| 看板单元格级双向血缘已可用 | `web/dashboard.js:124` 起 | 追溯视图可复用同一交互与面板样式 |
| 数据源/映射/列元数据 API 齐备 | `app.py:525-612`（`/api/load/datasources|tables|columns|rows`） | 指标配置页的「选库 → 选表 → 选列」直接消费现有接口 |
| 抽取规则有版本快照机制 | `c1_extract_rule_version` 三段 JSON 不可变；`app.py:464-518` | 指标/规则/框架的版本快照沿用同一范式，审计口径一致 |
| 入库回执幂等唯一键 | `c1_load_log` `uk_load_receipt` | 计算结果表同样用「定义版本 + 输入哈希」做幂等键 |
| 平台运行必须 Python 3.10 | `D:/miniforge3/envs/paddle/python.exe` | 施工验证沿用该解释器；8765 常服不动 |

---

## 3. 术语裁决（必须先定，否则 demo 会混乱）

平台里已有「抽取规则」和「入库映射」，用户新提的「规则」是业务侧概念。设计稿统一采用下表术语，UI 与 API 均按此口径：

| 本稿用词 | 含义 | 与既有概念的关系 | API 前缀 |
|---|---|---|---|
| **指标**（metric） | 对业务表列做聚合得到的数值 | 与抽取规则无关；读取的是**已入库**的业务表 | `/api/metrics` |
| **业务规则**（rule） | 对一个/多个指标做比较判断 | **不是**抽取规则；后者保留 `/api/extract-rules` 不动 | `/api/biz-rules` |
| **框架**（framework） | 关联多个业务规则，组合出总结论 | 全新概念，无同名冲突 | `/api/frameworks` |
| **计算结果**（eval result） | 上述三者每次运行的产物 | 复用「回执」语义，区别于暂存记录 | `/api/eval` |

前端页面新增 1 项导航「计算审计」→ `/compute`，单页三 Tab + 一个「全链路追溯」视图；不新增 3 个页面，避免导航膨胀。

---

## 4. 目标模型与全链路血缘

### 4.1 正向链路（计算方向）

```
源文件(BLOB) → parse.json(逐格 bbox) → 暂存记录(record_id + lineage)
      → 业务表行(file_id + record_id 溯源列) → 指标结果 → 规则结果 → 框架结果
```

### 4.2 反向链路（审计追溯方向，demo 主亮点）

```
框架结果 ──rule_result_ids──▶ 规则结果 ──metric_result_ids──▶ 指标结果
        ──input_rows_json──▶ 业务表行(file_id, record_id, 原始值)
        ──/api/staging/locate──▶ 暂存记录 ──lineage──▶ 原图第 N 页 [x0,y0,x1,y1] 高亮
```

一次点击即可从框架结论下钻到「是哪张源文件的哪个格子的值，经过哪次聚合、哪条比较、哪套权重，得出这个结论」。反向还可选做「影响分析」：给定源文件格子，列出受影响的指标/规则/框架结果（demo 可只做正向钻取，反向留 P2）。

### 4.3 审计可信的三条硬约束

1. **定义不可变**：每次保存定义生成新版本行（version 递增），旧版本只读；结果绑定 `def_id + def_version`，历史结果永远能按当时的定义解释。
2. **输入可复现**：结果保存输入快照（参与行锚点 + 原始值 + 过滤条件）与 `result_hash = sha256(定义快照 + 输入快照)`；提供 `/api/eval/{id}/replay` 重算并比对 hash，一致即证明结果未被篡改且可复算。
3. **口径不漂移**：聚合规则、比较算子、组合算子都是固定枚举，不接受用户自由 SQL 或表达式字符串；表名/列名走现有白名单校验，杜绝注入与「同定义不同结果」。

---

## 5. 数据模型（6 张表，DDL 草案）

设计取舍：采用「定义 3 张 + 结果 3 张」而非「统一结果表」。理由是三模块结果各有独立字段（指标=值+行锚点，规则=条件明细，框架=权重明细），显式列比一个 JSON 大杂烩更易读、更易在 demo 中展示；代价是多 3 张表，但结构与现有 12 表同构，施工量可控。备选方案见 §12。

### 5.1 定义表（版本行同表，天然不可变）

```sql
-- 指标定义：一行 = 一个版本；同名取 MAX(version) 为当前版
CREATE TABLE IF NOT EXISTS `c1_metric_def` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '指标名',
  `version` int NOT NULL COMMENT '版本号（同名内递增）',
  `datasource_id` bigint NOT NULL COMMENT '业务库 ID（引用 c1_load_datasource.id）',
  `source_table` varchar(128) NOT NULL COMMENT '业务表名（白名单校验）',
  `source_column` varchar(128) NOT NULL COMMENT '聚合列（可为空=COUNT(*)）',
  `aggregate` varchar(24) NOT NULL COMMENT 'sum/count/avg/min/max/count_distinct',
  `filter_json` json DEFAULT NULL COMMENT '可选简单过滤：[{column,op,value}]，op 限 eq/ne/gt/gte/lt/lte',
  `spec_hash` char(64) NOT NULL COMMENT '定义快照哈希',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `uk_metric_name_ver` (`name`,`version`)
) COMMENT='业务指标定义：每个版本一行，旧版本只读';

-- 业务规则定义
CREATE TABLE IF NOT EXISTS `c1_rule_def` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `version` int NOT NULL,
  `metric_refs_json` json NOT NULL COMMENT '引用指标：[{metric_id,version,alias}]，version=0 表示取当前版',
  `conditions_json` json NOT NULL COMMENT '条件：[{alias,op,threshold}]，op=gt/gte/lt/lte/eq/ne/between',
  `combine` varchar(16) NOT NULL DEFAULT 'all' COMMENT 'all/any：多条件同时满足/任一满足',
  `spec_hash` char(64) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `uk_rule_name_ver` (`name`,`version`)
) COMMENT='业务规则定义：指标比较条件，结构化 JSON 不用表达式';

-- 框架定义
CREATE TABLE IF NOT EXISTS `c1_framework_def` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `version` int NOT NULL,
  `rule_refs_json` json NOT NULL COMMENT '引用规则：[{rule_id,version,weight,veto}]',
  `combine` varchar(24) NOT NULL DEFAULT 'weighted' COMMENT 'weighted/all_pass/any_pass/veto',
  `threshold` decimal(12,4) DEFAULT NULL COMMENT 'weighted 模式的通过阈值',
  `spec_hash` char(64) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `uk_fw_name_ver` (`name`,`version`)
) COMMENT='评估框架定义：规则组合口径';
```

### 5.2 结果表（每次运行一行，带完整血缘锚点）

```sql
CREATE TABLE IF NOT EXISTS `c1_metric_result` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `metric_id` bigint NOT NULL,
  `metric_version` int NOT NULL,
  `value_text` varchar(64) NOT NULL COMMENT '指标值（保真文本，避免 DECIMAL 精度争议）',
  `input_rows_json` json NOT NULL COMMENT '输入锚点：{datasource_id,table,column,filter,rows:[{file_id,record_id,value}],truncated}',
  `result_hash` char(64) NOT NULL COMMENT 'sha256(def spec + input snapshot)',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_metric_result_def` (`metric_id`,`metric_version`),
  UNIQUE KEY `uk_metric_result_hash` (`metric_id`,`metric_version`,`result_hash`)
) COMMENT='指标结果：携带参与计算的行锚点';

CREATE TABLE IF NOT EXISTS `c1_rule_result` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `rule_id` bigint NOT NULL,
  `rule_version` int NOT NULL,
  `metric_result_ids_json` json NOT NULL COMMENT '依赖的指标结果 ID 列表（血缘上溯）',
  `outcome` varchar(8) NOT NULL COMMENT 'pass/fail',
  `detail_json` json NOT NULL COMMENT '逐条件：{alias,op,threshold,actual,passed}',
  `result_hash` char(64) NOT NULL,
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_rule_result_def` (`rule_id`,`rule_version`),
  UNIQUE KEY `uk_rule_result_hash` (`rule_id`,`rule_version`,`result_hash`)
) COMMENT='业务规则结果：继承指标结果血缘';

CREATE TABLE IF NOT EXISTS `c1_framework_result` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `framework_id` bigint NOT NULL,
  `framework_version` int NOT NULL,
  `rule_result_ids_json` json NOT NULL COMMENT '依赖的规则结果 ID 列表（血缘上溯）',
  `outcome` varchar(8) NOT NULL COMMENT 'pass/fail',
  `score_text` varchar(64) DEFAULT NULL COMMENT '综合得分（weighted 模式）',
  `detail_json` json NOT NULL COMMENT '逐规则：{rule_result_id,outcome,weight,veto,contribution}',
  `result_hash` char(64) NOT NULL,
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_fw_result_def` (`framework_id`,`framework_version`),
  UNIQUE KEY `uk_fw_result_hash` (`framework_id`,`framework_version`,`result_hash`)
) COMMENT='框架结果：继承规则结果血缘，追溯链顶点';
```

**input_rows_json 示例（demo 关键数据）**：

```json
{
  "datasource_id": 1,
  "table": "t_bank_txn",
  "column": "amount",
  "filter": [{"column": "file_id", "op": "eq", "value": 12}],
  "rows": [
    {"file_id": 12, "record_id": 101, "value": "1250.00"},
    {"file_id": 12, "record_id": 102, "value": "830.00"}
  ],
  "row_count": 2,
  "truncated": false
}
```

行锚点上限（如 500 行）由配置控制；超出置 `truncated=true`，demo 演示数据远低于该阈值。

---

## 6. 计算语义（最小算子集）

### 6.1 指标

- 从定义取 `datasource_id / source_table / source_column / aggregate / filter_json`。
- SQL 构造复用 `store.loader` 的白名单：`list_tables` / `list_columns` 校验表名列名；列名一律 `_ident()` 转义；值参数化。
- **两条查询**：① 聚合查询得到指标值；② 明细查询 `SELECT file_id, record_id, <column> ...` 得到参与行锚点（与聚合使用同一 filter）。两条查询放在同一只读连接内，避免中间数据变动。
- 聚合结果以字符串保存，避免 float/DECIMAL 精度争议；前端展示原样。

### 6.2 业务规则

- 解析 `metric_refs_json` 得到指标结果 ID（由运行请求显式传入，或按定义版本取最新一次结果）。
- 按 `conditions_json` 逐条比较：`actual` 来自指标结果的 `value_text`（转 Decimal 比较），`op` 为固定枚举；`between` 用二元阈值数组。
- `combine=all` 全部条件成立为 pass，`any` 任一成立为 pass。
- 结果 `detail_json` 保存每条条件的实际值与通过标记——这是审计时「为什么通过」的直接证据。

### 6.3 框架

- 解析 `rule_refs_json` 得到规则结果 ID 及权重/否决标记。
- `weighted`：各规则 pass 记 1、fail 记 0，得分 `Σ(weight × outcome) / Σ(weight)`，`score >= threshold` 为 pass；`veto=true` 的规则 fail 直接否决。
- `all_pass` / `any_pass` / `veto`：布尔组合，语义与名称一致。
- 结果 `detail_json` 保存每条规则的贡献值，便于在追溯视图中解释结论构成。

---

## 7. API 清单

定义 CRUD 三套，运行一套，追溯一套。沿用现有 `/api/extract-rules` 的版本风格与 `StoreError` 异常映射。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/metrics`、`/api/biz-rules`、`/api/frameworks` | 定义列表（含当前版本）/ 新建版本 |
| GET | `/api/metrics/{id}` 等 | 定义详情（可带 `?version=` 取历史版） |
| POST | `/api/metrics/{id}/run`、`/api/biz-rules/{id}/run`、`/api/frameworks/{id}/run` | 执行计算，写结果行，返回结果 ID |
| GET | `/api/eval/results?scope=metric\|rule\|framework&def_id=` | 结果列表（追溯视图入口） |
| GET | `/api/eval/{result_id}` | 结果详情（定义快照 + 输入快照 + 依赖 ID） |
| **GET** | **`/api/eval/{result_id}/lineage`** | **核心接口**：递归展开完整血缘包（见下） |
| GET | `/api/eval/{result_id}/replay` | 用结果自带输入快照重算，比对 hash，返回一致/不一致 |

`/api/eval/{result_id}/lineage` 返回结构（一次性给前端，避免多次往返）：

```json
{
  "ok": true,
  "scope": "framework", "result": { "...": "框架结果" },
  "definition": { "name": "...", "version": 2, "spec_hash": "..." },
  "chain": [
    {"scope": "rule", "result_id": 8, "outcome": "fail", "detail": { "...": "..." }},
    {"scope": "metric", "result_id": 3, "value": "2080.00",
     "rows": [{"file_id": 12, "record_id": 101, "value": "1250.00",
               "locate": "/api/staging/locate/101?key=amount"}]}
  ],
  "source_files": [{"file_id": 12, "name": "招行流水.pdf",
                    "open": "/preview?file=12&index=0"}]
}
```

前端拿到 `chain[].rows[].locate` 即可复用现有血缘面板，在原图高亮对应格子。

---

## 8. 前端 Demo 方案

单页 `/compute`（web/compute.html + compute.js + compute.css），沿用现有 shell / 样式体系（`table.list`、`badge`、抽屉、分页组件）。

- **Tab 1 指标**：左侧定义表单（选业务库 → 表 → 列 → 聚合 → 可选过滤），右侧结果列表；「运行」按钮调用 `/api/metrics/{id}/run`。
- **Tab 2 业务规则**：选择指标（可多选，带 alias）→ 配置条件行（alias / 比较符 / 阈值）→ 组合方式；结果列表展示通过/不通过徽标与条件明细。
- **Tab 3 框架**：勾选规则结果 → 设权重/否决 → 组合方式与阈值；结果列表展示得分与结论。
- **「全链路追溯」抽屉**：从任意结果行点开，展示 §7 的链路：框架结论 → 规则条件明细 → 指标值 + 参与行 → 源文件 → 原图格子高亮。复用 `dashboard.js` 的 `openLineage` 面板组件与 `/preview?embed=1&file=` 嵌入视图。
- **「复现校验」按钮**：对结果调 `/replay`，展示「定义哈希 / 输入哈希 / 重算一致」三行证据。

导航改动：在 8 个 HTML 的 nav 中增加 1 项 `/compute`（与历史「校验规则 → 校验」那次一致的批量改法），home 首页卡片加一个入口。

---

## 9. 分期施工计划（每期单独汇报验证后再进下一期）

| 期 | 内容 | 涉及文件 | 验证 |
|---|---|---|---|
| P0 | 定义表 + 结果表迁移脚本（6 表，IF NOT EXISTS）；store 层 repo（`store/eval/`） | `store/migrations/002_metric_rule_framework.sql`、`store/eval/*.py` | 迁移脚本幂等重跑；repo 增删改查单测 |
| P1 | 计算引擎：指标聚合 + 行锚点采集；规则比较；框架组合 | `compute/engine.py`（新包） | 单测：三种聚合 × 六种比较 × 四种组合；锚点非空 |
| P2 | API：定义 CRUD + run + results + lineage + replay | `app.py`（新增路由段）、`service.py`（薄封装） | 8799 临时服务端到端；结果 hash 复现一致 |
| P3 | 前端 `/compute` 三 Tab + 追溯抽屉 + 导航入口 | `web/compute.*` + 8 个 HTML nav | `node --check`；8799 冒烟全页面 200；追溯点击链路通 |
| P4 | demo 演示数据 + 文档收尾 | `docs/demo-script-mrf.md`（新）、`README.md` 增量 | 按 §10 脚本完整走通一遍并录屏/截图 |

施工边界：8765 常服不启停；临时验证一律 8799，验完即停；所有 Python 用 `D:/miniforge3/envs/paddle/python.exe`。

---

## 10. Demo 演示脚本（建议 3 分钟）

1. 用现有链路上传一份源 PDF → 解析 → 抽取 → 校验 → 入库，得到业务表行（带 `file_id / record_id` 溯源列）。
2. 进 `/compute` → 指标 Tab：选该业务库/表/金额列，聚合 `SUM`，过滤 `file_id = 本次资料 ID` → 运行，得到指标结果（如 2080.00）。
3. 规则 Tab：选该指标，条件「金额合计 > 1000」→ 运行，得到「通过」。
4. 框架 Tab：关联该规则（权重 1.0），阈值 0.8 → 运行，得到「通过，得分 1.00」。
5. **亮点展示**：点框架结果的「全链路追溯」→ 逐级展开到指标结果的两条参与行 → 点其中一行 → 原图对应格子高亮（复用既有血缘面板）。
6. **可信展示**：点「复现校验」→ 展示定义哈希、输入哈希、重算一致。
7. 现场改一次暂存值（可选）→ 重跑指标 → 结果与 hash 变化，旧的框架结果仍绑定旧定义版本与旧输入快照，可继续追溯——证明「结果可解释、历史不篡改」。

---

## 11. 风险与边界（诚实披露）

| 风险/边界 | 处置 |
|---|---|
| 指标读取业务表时数据被并发修改 | 同一只读连接内完成聚合 + 明细两条查询；输入快照固化当时值，hash 可验证一致性；demo 单用户无并发 |
| 行锚点过多导致 JSON 膨胀 | 上限 500 行 + `truncated` 标记；demo 数据量远低于阈值 |
| 定义版本.no 更新后历史结果如何解释 | 结果绑定版本 ID + 定义 spec_hash，历史结果永久按当时口径可解释；不做自动重算（避免"追溯时结果已变"） |
| 规则/框架引用了被删的结果 | 结果行只增不删；定义引用按 ID 固化，删除定义需检查引用（应用层守卫，模仿现有映射守卫 409） |
| 指标计算的性能 | demo 阶段对业务表全表聚合，数据量小；生产化需加索引/预聚合，不在本设计范围 |
| 与既有「抽取规则/入库映射」混淆 | §3 术语裁决 + UI 明确标注「业务规则（计算层）」；API 前缀完全隔离 |

---

## 12. 备选方案与取舍

| 方案 | 优点 | 代价 | 裁决 |
|---|---|---|---|
| A. 6 表（定义 3 + 结果 3）——本稿推荐 | 字段显式、链路清晰、与现有表风格一致、易展示 | 多 3 张表 | **采用** |
| B. 4 表（定义 3 + 统一结果表 1，用 `scope + ref_id + parent_ids_json`） | 表少、血缘遍历逻辑统一 | 结果字段变成大 JSON，demo 展示与审计可读性差 | 备选，若用户要求极简表数可切换 |
| C. 计算层不落库、每次实时算 | 零存储 | 无历史结果、无法复现、追溯链断裂，违背审计亮点 | 不采用 |

---

## 13. 待用户确认的开工单

> 本稿为设计，未改任何产品代码。请逐项确认后我再按分期施工，每期完成后先汇报验证结果与设计取舍：

1. **术语口径**：同意「指标 / 业务规则 / 框架」命名，且 `/api/biz-rules` 与既有 `/api/extract-rules` 并存？
2. **表方案**：采用 §12 方案 A（6 表）？还是切换方案 B（4 表）？
3. **前端形态**：接受「单页 `/compute` + 三 Tab + 追溯抽屉」而非三个独立页面？
4. **追溯深度**：一期只做「结果 → 源文件格子」正向钻取（§4.2），「源文件 → 受影响结果」反向影响分析留 P2？
5. **指标算子**：一期只实现 `sum/count/avg/min/max/count_distinct` + 简单过滤，不做 JOIN / 自定义 SQL？
6. **施工起点**：确认后是否从 P0（建表 + repo）开始，还是希望先出一份可点击的前端静态原型供 demo 评审？

确认以上 6 项后，我将输出逐期的详细执行清单并开始 P0 施工。
