# 指标 / 规则 / 框架计算层设计稿（简化版 · 全路径可回溯）

> 状态：**已实施完成（2026-11-26）**。本稿为简化口径，取代此前带版本/哈希/快照的设计。
> 变更依据：用户裁决（2026-11-26）——去掉版本、哈希、配置快照副本；前端页签去内部命名并优化体验。
> 旧稿 `design-metric-rule-framework.md` 与 002 迁移脚本的版本化设计已作废，以本稿和 `003_simplify_value.sql` 为准。

---

## 1. 一句话结论

在入库业务表之上做三层计算：**指标（选表做聚合）→ 规则（用指标做比较）→ 框架（关联规则出结论）**。每一层结果只保留两类信息：**结果本身** 与 **指向下一层的血缘锚点**。因此任意结果都能一路下钻到源文件单据的具体格子。设计追求简单、可演示，不做版本与哈希的复杂审计机制。

---

## 2. 命名口径

| 概念 | 前缀 | 定义表 | 结果表 | API 前缀 | 页面用语 |
|---|---|---|---|---|---|
| 指标 | `index` | `c1_index_info` | `c1_index_value` | `/api/index` | 指标 |
| 规则 | `rule` | `c1_rule_info` | `c1_rule_value` | `/api/rule` | 规则 |
| 框架 | `frame` | `c1_frame_info` | `c1_frame_value` | `/api/frame` | 框架 |

- 前缀 `index/rule/frame` 只用于代码与 API，**页面一律显示中文「指标/规则/框架」**。
- 「规则」专指计算层业务规则，与既有「抽取规则」`/api/extract-rules` 完全隔离。
- 定义表后缀 `_info`，结果表后缀 `_value`。

---

## 3. 简化后的数据模型

### 3.1 定义表（同名唯一，无版本、无哈希）

```sql
c1_index_info(id, name UNIQUE, datasource_id, source_table, source_column,
              aggregate, filter_json, created_at, updated_at)
c1_rule_info (id, name UNIQUE, index_refs_json, conditions_json,
              combine, created_at, updated_at)
c1_frame_info(id, name UNIQUE, rule_refs_json, combine, threshold,
              created_at, updated_at)
```

- 同名保存即**覆盖更新**，不生成新版本。
- `index_refs_json`：`[{index_id, alias}]`；`rule_refs_json`：`[{rule_id, weight, veto}]`。

### 3.2 结果表（只存结果与血缘锚点）

```sql
c1_index_value(id, index_id, value_text, input_rows_json, computed_at)
c1_rule_value (id, rule_id, index_value_ids_json, outcome, detail_json, computed_at)
c1_frame_value(id, frame_id, rule_value_ids_json, outcome, score_text, detail_json, computed_at)
```

**明确去掉的字段**：
- `*_version`：结果不绑定版本，定义更新后旧结果按当前定义复核。
- `result_hash` / `spec_hash`：不做哈希防篡改。
- 配置副本：`input_rows_json` 不再复制 `datasource_id/table/column/aggregate/filter`，只保留：
  ```json
  {"rows":[{"file_id":1,"record_id":121,"value":"10.00"}],
   "matched_rows":24,"truncated":false}
  ```
- `detail_json` 不再复制阈值/权重/比较符，只留实际值与结论：
  - 规则：`[{alias, actual, passed}]`
  - 框架：`[{rule_value_id, outcome, contribution}]`

每次运行**新增一行**，不做幂等去重。

---

## 4. 全路径可回溯

```
框架结果(rule_value_ids_json) → 规则结果(index_value_ids_json) → 指标结果(input_rows_json)
    → 业务表行(file_id + record_id 溯源列) → /api/staging/locate/{record_id}
    → 暂存逐格血缘(c1_staging_lineage) → 原图具体格子
```

- 核心接口 `GET /api/{scope}/value/{value_id}/lineage` 递归展开为 `chain` + `source_files`。
- 每行锚点带 `locate` 链接；源文件带 `open` 预览链接。
- 这一层血缘底座是平台既有能力（业务表双溯源列 + staging lineage），本次计算层只是把结果挂上去。

---

## 5. 复核（replay，降级）

- `GET /api/{scope}/value/{value_id}/replay`：用**当前定义**重算一次结果，与存储值逐字段比对（值/结论/得分/明细）。
- 不比对哈希、不绑定历史版本——因此只能发现「当前定义或数据变化导致的不一致」，不能证明历史结果当时的口径。
- 返回 `consistent` 为各项比对的合取，并附 `note` 说明降级性质。

---

## 6. API 清单（24 个路由）

| 类别 | 路由 |
|---|---|
| 定义 | `GET/POST /api/index|rule|frame`；`GET/DELETE /api/index|rule|frame/{id}` |
| 运行 | `POST /api/index|rule|frame/{id}/run` |
| 结果 | `GET /api/index|rule|frame/{id}/values` |
| 追溯 | `GET /api/index|rule|frame/value/{value_id}/lineage` |
| 复核 | `GET /api/index|rule|frame/value/{value_id}/replay` |

定义保存请求体带 `id` 即为更新，不带则为新建（同名覆盖）。

---

## 7. 计算语义（固定算子）

- **指标**：`sum/count/avg/min/max/count_distinct` + 简单过滤（eq/ne/gt/gte/lt/lte）。表名/列名走白名单与反引号转义，值参数化；行锚点上限 500 行。
- **规则**：`gt/gte/lt/lte/eq/ne/between` 比较，Decimal 精度，`all/any` 组合。
- **框架**：`weighted/all_pass/any_pass/veto`，加权得分 = Σ(权重×通过) / Σ(权重)，veto 优先。

不接受自由 SQL 或表达式字符串。

---

## 8. 文件与迁移

- 建表：`store/migrations/003_simplify_value.sql`（重建 6 表，清空旧演示数据）。
- 引擎：`compute/engine.py`；编排/血缘/复核：`compute/orchestrate.py`。
- 存储：`store/{index,rule,frame}_repo.py`、`store/value_common.py`。
- API/页面：`app.py`、`web/compute.{html,js,css}`。
- 演示：`docs/demo-script-index-rule-frame.md`。

---

## 9. 取舍与边界

| 取舍 | 说明 |
|---|---|
| 去版本 | 大幅简化配置与结果模型；代价是无法按历史口径解释旧结果 |
| 去哈希 | 去掉防篡改证据；复核能力降级为「当前定义重算比对」 |
| 去配置副本 | 结果表更轻；追溯时才回查定义，定义变更后展示以当前定义为准 |
| 保留血缘锚点 | 全路径回溯的核心，不可去掉 |
| 每次运行新增结果 | 不做幂等；结果列表按 ID 倒序取最近一次 |

本设计适合 demo 展示与中小规模审计追溯场景；如需严格的历史口径复现与防篡改，需重新引入版本与哈希机制。
