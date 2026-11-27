# 指标 / 规则 / 框架计算层设计稿（极简版）

> 状态：**已实施完成（2026-11-26）**。本稿为极简口径，取代此前所有版本化/血缘锚点设计。
> 变更依据：用户裁决（2026-11-26）——结果表只需「定义 ID + 结果值」；输入值、依赖 ID、行锚点全部去掉；关联对象从定义表推导；结果字段统一为 `index_value/rule_value/frame_value`。
> 旧稿 `archive/design-metric-rule-framework.md` 与 002/003 迁移脚本的设计已作废，以本稿和 `004_result_value_only.sql` 为准。

---

## 1. 一句话结论

在入库业务表之上做三层计算：**指标（选表做聚合）→ 规则（用指标做比较）→ 框架（关联规则出结论）**。定义表存配置（含 1 对多的关联数组），结果表只存「算出来是什么值」。要追溯时用结果的定义 ID 找到配置，逐级展开参与计算的定义——这就是"参与计算的元数据"。

---

## 2. 命名口径

| 概念 | 前缀 | 定义表 | 结果表 | 结果字段 | API 前缀 | 页面用语 |
|---|---|---|---|---|---|---|
| 指标 | `index` | `c1_index_info` | `c1_index_value` | `index_value` | `/api/index` | 指标 |
| 规则 | `rule` | `c1_rule_info` | `c1_rule_value` | `rule_value` | `/api/rule` | 规则 |
| 框架 | `frame` | `c1_frame_info` | `c1_frame_value` | `frame_value` | `/api/frame` | 框架 |

- 前缀只用于代码与 API；页面一律中文，导航项「计算」。
- 「规则」专指计算层规则，与抽取规则 `/api/extract-rules` 隔离。

---

## 3. 数据模型

### 3.1 定义表（存配置，同名唯一）

```sql
c1_index_info(id, name UK, datasource_id, source_table, source_column,
              aggregate, filter_json, created_at, updated_at)
c1_rule_info (id, name UK, index_refs_json, conditions_json, combine,
              created_at, updated_at)
c1_frame_info(id, name UK, rule_refs_json, combine, threshold,
              created_at, updated_at)
```

- `index_refs_json`：`[{index_id, alias}]`——规则关联多个指标（1 对多数组）。
- `rule_refs_json`：`[{rule_id, weight, veto}]`——框架关联多个规则（1 对多数组）。
- 关联关系只存定义表，结果表不再重复。

### 3.2 结果表（只存定义 ID + 结果值 + 时间）

```sql
c1_index_value(id, index_id, index_value varchar(64), computed_at)
c1_rule_value (id, rule_id,  rule_value  varchar(64), computed_at)
c1_frame_value(id, frame_id, frame_value varchar(64), computed_at)
```

**明确不存**：行锚点、依赖结果 ID、输入值、命中行数、明细、结论拆分、得分拆分、版本、哈希、配置副本。每次运行新增一行。

结果值约定：
- `index_value`：聚合值文本（如 `24`）。
- `rule_value`：`pass` / `fail`。
- `frame_value`：结论文本（如 `pass（1）` 或 `fail（一票否决）`）。

---

## 4. 运行逻辑

run 请求**不带参数**，后端从定义推导依赖：

- **指标 run**：读定义 → 查业务表聚合 → 写 `index_value`。
- **规则 run**：读 `rule_info.index_refs_json` → 取各指标最新 `index_value` 按 alias 组装 → 比较 → 写 `rule_value`。
- **框架 run**：读 `frame_info.rule_refs_json` → 取各规则最新 `rule_value` → 组合 → 写 `frame_value`。

因此必须先运行下级、再运行上级；否则后端返回明确错误。

---

## 5. 依据链（lineage）

`GET /api/{scope}/value/{id}/lineage` 返回参与计算的**元数据链**：

```
{scope, result:{id,def_id,结果值}, definition:{
    scope, id, name, config:{...},      // 本级定义配置
    refs:[ {下级定义...}, ... ]          // 1 对多数组，递归展开
}}
```

框架 → 规则 → 指标，逐层展开配置（表/列/运算/筛选、条件/组合、规则引用/权重）。不再有行锚点、源文件下钻。

---

## 6. 复核（replay）

`GET /api/{scope}/value/{id}/replay`：用当前定义 + 最新下级结果重算一次，比对结果值，返回 `{checks:{index_value|rule_value|frame_value:{stored,recomputed,match}}, consistent, note}`。

这是极简复核：可发现配置或数据变化，不提供历史口径复现或防篡改证据。

---

## 7. API 清单（24 路由）

定义 `GET/POST /api/index|rule|frame`、`GET/DELETE /{id}`；运行 `POST /{id}/run`（无 body）；结果 `GET /{id}/values`；依据 `GET /value/{vid}/lineage`；复核 `GET /value/{vid}/replay`。

定义保存带 `id` 即更新，不带即新建（同名覆盖）。

---

## 8. 计算算子（固定枚举）

- 指标：`sum/count/avg/min/max/count_distinct` + 过滤（eq/ne/gt/gte/lt/lte），白名单 + 参数化。
- 规则：`gt/gte/lt/lte/eq/ne/between`，Decimal 精度，`all/any`。
- 框架：`weighted/all_pass/any_pass/veto`。

---

## 9. 文件与迁移

- 迁移：`store/migrations/004_result_value_only.sql`（重建 3 张结果表；定义表与 001 基线不动）。
- 引擎 `compute/engine.py`（compute_index/compute_rule/compute_frame）；编排 `compute/orchestrate.py`。
- 存储 `store/{index,rule,frame}_repo.py`；API `app.py`；页面 `web/compute.{html,js,css}`。

---

## 10. 取舍

| 取舍 | 说明 |
|---|---|
| 结果表极简 | 存储最轻、结构最清晰；代价是无法下钻到源文件、无法按历史口径复现 |
| 依赖从定义推导 | 不在结果表重复关联关系；代价是重算下级后旧结果可能与新输入不一致（复核会提示） |
| 保留定义表关联数组 | 1 对多关系完整保留，配置层面可追溯 |
| 无哈希/版本 | 不做防篡改与历史口径，定位为轻量计算与元数据显示 |

适合 demo 展示与轻量计算场景；如需严格审计追溯，需另行引入锚点与版本机制。
