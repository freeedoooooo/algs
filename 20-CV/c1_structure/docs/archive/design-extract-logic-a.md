# A 期：抽取逻辑引擎详细设计 + 任务清单（可施工版）

> 状态：待施工（承接 `design-rule-evolution.md` §1，用户确认抽取为最高优先级后展开）。
> 日期 2026-11-23。目标：把"选列映射"升级为"算子管道＋记录切分＋声明式校验"，
> 保持零 DB 迁移、零解析改动、血缘不退化、8765 常服不动。

## 0. 设计红线（贯穿全部任务）

1. **三段 JSON 不变**：`schema_json` / `mapping_json` / `transform_json` 仍是 `c1_extract_rule_version` 的三列，且每列必须是 dict（`rules._tpl_payload` 硬约束）。新规范塞进 `mapping_json.spec_version=2`，不新增列、不改表。
2. **向后兼容**：`spec_version` 缺省或 1 → `collect.build` 原样走 `passthrough` / `apply_mapping`；只有 =2 走新引擎。存量规则、存量任务、正在跑的 8765 全部零影响。
3. **抽取永远纯函数**：新引擎吃 `doc`（c1-structure/1 信封），吐 records，无 DB、无模型、无 I/O；毫秒级。
4. **血缘不退化**：records 结构仍是 `{index, values, original, lineage, review}`；`lineage[field]` 仍是 `{page, table_index, table_scope, space, cell_bbox, raw_text}` 数组，直接喂现有 `content_db.save_records` 和 `c1_staging_lineage`，预览血缘查看器零改动。
5. **transform 语义隔离**：`loader.apply_transform`（入库期）保持不动，继续只吃 `transform_json`；新引擎的算子在抽取期算，两者不许互相调用。
6. **算子实现形态**：A 期采用代码内注册表 + 单文件模块化（`collect_logic/ops/<op>.py` 一算子一文件、一测试文件、`registry.py` 自动发现），**不建外部脚本插件、不建算子逻辑配置表、不用 DB 存代码串 exec**。理由：①纯函数的可测性来自"纯"而非物理位置，外部脚本不降低单测难度；②审计场景要求规则版本快照完整可复现——算子若独立发版，旧 `rule_version_id` 重跑时算子已变，血缘不可复现；③插件的版本治理（算子包版本随规则快照记录）成本 > A 期收益。若将来算子数多、跨角色扩展、需独立发版，再演进为插件包，届时必须把算子包版本写进规则版本快照。
6. **校验规则只标记不改值**：validate 算子产出 `review.reason`/标记，绝不自动改 `values`；人工改值仍是 `patch_record` 唯一入口。

---

## 1. 新规范全文（`spec_version=2`）

### 1.1 顶层结构（放在 `mapping_json` 里）

```
mapping_json = {
  "spec_version": 2,
  "tables": [                          # 表选择器，可多张；替代旧的单 table
    {"ref": "main", "index": 0},       # index 优先
    {"ref": "sum",  "header_contains": "合计"},
    {"ref": "all",  "scope": "all"}    # scope: all|page|stitched
  ],
  "records": {                         # 记录切分策略
    "strategy": "row",                 # row | key_value | group_by | one_per_page
    "source": "main",                  # 主表 ref
    "group_by": ["字段名"],             # strategy=group_by 时必填
    "header_rows": 1                   # 数据起始行（跳过表头），默认 1
  },
  "fields": [
    {
      "target": "交易金额",             # 目标字段名（唯一，入库映射按它对齐）
      "type": "string",                 # string | number | date | bool（仅声明，不强制转换）
      "pipeline": [                     # 算子管道，顺序执行
        {"op": "cell", "source": "main",
         "column": {"header_contains": "金额"}, "row": "current"},
        {"op": "regex", "pattern": "[\\d,]+\\.\\d{2}"},
        {"op": "number", "strip": ","}
      ],
      "validate": [                     # 声明式校验，只标记不改值
        {"op": "required"},
        {"op": "range", "min": 0}
      ],
      "on_fail": "flag"                 # flag | reject（review 状态提示，不自动改值）
    }
  ]
}
```

### 1.2 四族算子（注册在 `collect_logic.OPS`，纯函数）

统一签名：`fn(ctx: dict, args: dict, value, anchors: list) -> (value, anchors, meta)`
- `ctx` = 当前行/表/页上下文（含 `row`、`table`、`page`、`doc`）
- `anchors` = 上游继承的锚点数组
- `meta` = `{'derived': bool, 'issues': [...]}`（issues 供校验用）

| 族 | op | 参数 | 行为 | 锚点 |
|---|---|---|---|---|
| 取值 | `cell` | source/column/row | 按列选择器取值，row=current\|index\|label | 新增该格锚点 |
| 取值 | `kv` | source/label/value | 非表格文档：按标签文本＋空间关系取值（见 1.6） | 值 box 为主＋标签 box 为辅，双锚点 |
| 取值 | `row` | source/index | 取整行（供 compose） | 行内全部格 |
| 取值 | `block` | role(role=title/text/table) | 取版面块文本 | block bbox 锚点 |
| 取值 | `page_text` | page | 取整页 plain_text | page 锚点（无 bbox） |
| 变换 | `trim` / `cut` / `replace` | begin/end, pattern/repl | 字符串处理 | 透传 |
| 变换 | `regex` | pattern, group | 正则提取 | 透传 + derived |
| 变换 | `number` | strip | 转数值（只做一次，别和入库 transform 重复） | 透传 + derived |
| 变换 | `date` | format | 日期归一化 | 透传 + derived |
| 组合 | `concat` / `template` | fields/pattern, sep | 多字段拼接 | 合并多源锚点 |
| 组合 | `lookup` | dict / dict_ref | 字典映射（别名/代码表） | 透传 + derived |
| 组合 | `coalesce` | fields | 取第一个非空 | 合并命中源锚点 |
| 逻辑 | `if` / `switch` | when, then, else | 条件分支（子管道） | 合并 |
| 逻辑 | `sum` / `count` | source/column/where | 跨行聚合 | 汇总参与行锚点 |
| 逻辑 | `join` / `link` | left/right, on | 多表关联（审计：明细＋汇总） | 合并两侧锚点 |

列选择器（复用于 `cell`/`row`/聚合）：`{"name": "表头原文"}` / `{"index": n}` / `{"header_contains": "金额"}` / `{"header_regex": "^金"}`；与现有 `_pick_column`（extract.js `keysOf`）同序同规则，前端复用 `candidates()`。

### 1.3 校验算子（`validate`，只标记不改值）

| op | 参数 | 失败时 |
|---|---|---|
| `required` | — | issues += '空值' |
| `regex` | pattern | issues += '格式不符' |
| `enum` | values | issues += '不在枚举内' |
| `range` | min/max | issues += '越界' |
| `cross_field` | other, op(=,>,<=) | issues += '字段关系不符' |
| `unique` | scope=file\|task | issues += '重复' |

失败汇总写入该 record 的 `review.reason`（数组），`review.state` 仍 `pending`；`/review` 壳页将来可据此做置信度路由。**不阻断抽取、不改值。**

### 1.4 记录切分（records.strategy）

- `row`（默认＝现状）：主表数据行，一行一条，与原 `passthrough` 等价。
- `key_value`：左列字段名、右列值 → 拼一条记录（audit 附表常见）。
- `group_by`：按 `group_by` 字段分组，组内多行 → 一条记录，组内其他字段成数组（对标 WPS 365 的 group 字段）。
- `one_per_page`：每页一条，`page_text` 填正文。

### 1.5 锚点传播（血缘不褪化的硬规则）

- 每个算子的 `anchors` 必须来自 `_anchor()` 产出的同款 dict（page/table_index/table_scope/space/cell_bbox/raw_text）。
- 变换类算子透传上游 anchors、置 `derived=true`；组合/逻辑类合并去重后按 `region_seq` 递增。
- 管道结束后，`lineage[target] = dedupe(anchors)`；无锚点（如 `lookup` 常量）留空数组，前端显示"无源"。
- `original[target]` = 管道第一个取值算子的原始值；`values[target]` = 管道末值。**保留 original 是回流归因的前提。**

### 1.6 字段定位模型：表格 / 非表格两条路径（补非表格缺口）

"定位"分三层，逐层收窄：**选文件/页 → 选容器（表/文本区）→ 选字段值**。A 期必须两条路径都覆盖，否则营业执照、合同、证明这类无法抽。

**路径 A · 表格类（现有设计已覆盖，这里显式写出来）**

```
tables[{"ref":"main","index":0}, ...]     ← L1+L2：选表，ref 供字段引用
  → fields[].pipeline[0] = {"op":"cell",   ← L3：选字段
       "source":"main",                    ← 引用上面的 ref
       "column":{"header_contains":"金额"},← 列选择器（name/index/header_contains/header_regex）
       "row":"current"}                    ← 行：current|index|label
  → 锚点 = 该单元格 bbox（表格 cells 网格坐标）
```

表定位支持：`index`（第几张）、`header_contains`（表头含某词，取第一张命中）、`scope=all|page|stitched`（全部/当页/跨页合并），复用 `_candidate_tables` 的迭代序。

**路径 B · 非表格类（营业执照信用代码，新增 `kv` 算子）**

营业执照的"统一社会信用代码"通常**不在表格里**，而是"标签+值"的版式文本行。解析信封的 `page.texts[] = [{text, score, box}]`（四点 polygon，带坐标，见 `adapter/base.py:10`）和 `page.blocks[] = [{role, bbox, text}]` 已经提供了定位素材——**不需要表格识别也能抽**。

`kv` 算子 = 先按标签文本找到"锚点行"，再按空间关系取它旁边的值：

```
{"op": "kv",
 "source": "texts",                  # texts | blocks（页内文本行 / 版面块）
 "label": {"text": "统一社会信用代码", "match": "contains"},  # contains|exact|regex
 "value": {"direction": "right",     # right(同行右侧) | below(下方行) | inline(同一行冒号后)
           "max_gap": 300,           # 最大像素距离，超出视为无关行（可选）
           "regex": "[0-9A-Z]{18}"}, # 值上再做提取（可选）
 "page": 1}                          # 限定页（可选，缺省全页搜索）
```

执行逻辑（纯函数）：
1. 在 `texts`/`blocks` 里按 `label.match` 找到标签项 → 记下它的 `box`；
2. 按 `direction` 筛候选：同行右侧 / 正下方 / 同一行内标签之后，`max_gap` 过滤过远项；
3. 候选值过 `regex`（信用代码 18 位字母数字，天然排除地址/名称误取）；
4. 返回 `(value, [value_box, label_box])` —— 双锚点：值所在行 + 标签所在行，**血缘能证明"这个值是从哪个标签旁边抽的"**。

完整例子：营业执照抽信用代码（非表格，一条记录）：

```
mapping_json = {
  "spec_version": 2,
  "tables": [],                              # 没有表，走路径 B
  "records": {"strategy": "one_per_page"},   # 一页一条记录
  "fields": [{
    "target": "统一社会信用代码",
    "pipeline": [
      {"op": "kv", "source": "texts",
       "label": {"text": "统一社会信用代码", "match": "contains"},
       "value": {"direction": "right", "regex": "[0-9A-Z]{18}"}}
    ],
    "validate": [{"op": "regex", "pattern": "^[0-9A-Z]{18}$"}]
  }]
}
```

覆盖范围与兜底：
- `direction=inline` 处理"统一社会信用代码：9131..." 同一行（中文全角冒号也支持）；
- `direction=below` 处理"标签在上、值在下一行"的竖排；
- 标签 OCR 偶有错字时 `match=regex` 用容错模式，如 `信用.*代号|信用代码`；
- 值 regex 是**最后一道保险**：18 位模式不匹配就留空并在 `review.reason` 标记，宁可漏抽不可错抽。

**为什么不用表格路径硬套营业执照**：PPStructureV3 对证照类文档可能把字段识别成一张 2 列伪表，但列切分不稳定（标签/值粘连、跨行）；`kv` 直接走带坐标的文本行，不依赖表格模型，稳定性更高，且双锚点血缘更可解释。

---

## 2. 可落地任务清单（A 期，按依赖顺序）

> 约定：每完成一项跑 `compileall` + 8799 冒烟；8765 全程不动；不写新表。
> 测试用合成 task，跑完清理（沿用 `tmp/clean_*` 套路与独占窗口规则）。

### A1 规范定义与占位分发（0.5 天）
- [ ] `collect.py`：`build(doc, tpl)` 加 `spec_version` 判断——缺省/1 走原分支（一行不改），=2 调 `collect_logic.build_logic(doc, tpl)`；`collect_logic.py` 先放空壳。
- [ ] 单测：`spec_version` 缺失/1/2 三条分发正确；老规则输出与改动前逐字段相等（golden 对比）。
- [ ] 验收：`compileall`；`check_env.py`；8799 `/api/extract-rules` 200。

### A2 算子注册表 + 取值/变换族（1.5~2 天，含 kv）
- [ ] 新建 `collect_logic.py`：`OPS` 注册表、`_anchor` 复用 `collect._anchor`、`apply_pipeline`、`build_logic` 骨架。
- [ ] 实现 `cell`/`row`/`block`/`page_text` + `trim`/`cut`/`replace`/`regex`/`number`/`date`，每算子纯函数、带锚点返回。
- [ ] **实现 `kv`**（非表格定位，见 1.6）：从 `page.texts`/`blocks` 按 label 匹配 + direction(right/below/inline) + max_gap 筛候选 + regex 提取；返回双锚点（值 box + 标签 box），坐标走 `texts[].box`（四点 polygon）；label 匹配支持 contains/exact/regex，全角冒号归一。
- [ ] 单测：单字段单算子/多算子链，锚点从 cell 一路传到 lineage；derived 标记正确；**合成 texts 测 kv 三种 direction + regex 过滤 + 双锚点**。
- [ ] 验收：合成 doc 跑 `build_logic`，`lineage[target][0].raw_text` == 源格原文；**合成营业执照 texts 抽 18 位信用代码，值正确且 lineage 含标签行与值行两个锚点**。

### A3 组合/逻辑族 + 多表选择器（1~1.5 天）
- [ ] 实现 `concat`/`template`/`lookup`/`coalesce`/`if`/`switch`。
- [ ] 实现 `tables` 多选择器（`_candidate_tables` 复用，加 `ref` 与 `scope=all`），`cell.source` 按 ref 解析。
- [ ] 实现 `sum`/`count`/`join`/`link`（先支持同页与 stitched，跨页 join 留 A3.1）。
- [ ] 单测：两表 join 产出组合记录、锚点合并去重、region_seq 递增。
- [ ] 验收：合成双表 doc，join 字段 lineage 含两表锚点。

### A4 记录切分策略（0.5~1 天）
- [ ] 实现 `row`/`key_value`/`group_by`/`one_per_page`，输出统一 records 信封。
- [ ] 单测：`row` 与旧 `passthrough` 输出逐字段相等（保证默认行为不变）；`group_by` 组内数组正确。
- [ ] 验收：records 信封 schema 与 `content_db.save_records` 契约一致（index/values/original/lineage/review 齐全）。

### A5 声明式校验（0.5 天）
- [ ] 实现 6 个 validate 算子，issues 写 `review.reason`（数组），不改 values、不阻断抽取。
- [ ] 单测：required/range/cross_field/unique 各自触发；确认값仍 pending。
- [ ] 验收：`get_records` 往返一致契约不破（不能把 reason 塞进 values 键）。

### A6 规则校验器（0.5 天）
- [ ] 新建 `extract_spec/validate.py`（或放 `collect_logic.validate_spec`）：校验 `spec_version=2` 的 mapping_json——未知 op、缺参、类型错、重复 target、未知 source ref、validate 参数非法。风格参照 `params.normalize`（非法回退＋警告 → 这里改为 BadRequest 拒绝）。
- [ ] 接入 `rules.create_rule` / `rules.create_version`（在 `_tpl_payload` 之后），非法规范 400、不入库。
- [ ] 单测：合法 spec 放行；未知 op/重复 target 被拒；**老三段 JSON（无 spec_version）不受校验影响**。
- [ ] 验收：8799 POST `/api/extract-rules` 注入合法/非法两例，400/200 正确。

### A7 前端编辑器（1~1.5 天，工作量最大）
- [ ] `web/extract.html`：加"规则模式"切换（v1 简单映射 / v2 逻辑管道），v2 显示管道编辑器区块（字段行展开：source→算子列表→validate 列表）。
- [ ] `web/extract.js`：openEditor 按 `mapping.spec_version` 分流；v2 保存时组装 spec（复用 `candidates()`/`keysOf()` 做源列下拉）；保留旧分支不动。
- [ ] 交互底线：v2 编辑器和 v1 一样能"选参考文件→选表选列→自动填字段"，否则规则写不出来。
- [ ] 验收：8799 冒烟 extract 页 200；手测新建 v2 规则→保存→版本历史→回读三段 JSON 一致。

### A8 端到端 + 回归（0.5 天）
- [ ] 从任务详情/数据预览页选 v2 规则执行抽取 → staging 三表落库 → 预览血缘点击定位到正确 cell。
- [ ] 回归：老规则（原始透传 + 一个 v1 映射规则）跑同一文件，输出与 A1 golden 完全一致。
- [ ] 验证：`compileall` + `check_env` 全绿；8799 全链冒烟；8799/8797 free、8765 未动、tmp 空、无合成残留。
- [ ] 文档：`docs/progress-handoff.md` 产品结构段补一句 spec_version=2；本设计稿状态改"已落地 A 期"。

### A9（可选，A 期之后）回流闭环 B 期接入点
- [ ] `content_db.patch_record` 事务内插 `c1_correction`（A 期不做，但 `original[target]` 已在 A2 保留，B 期可直接接）。
- [ ] 归因器 `c1_rule_suggestion` 的补丁目标就是本规范的 `fields[].pipeline` / `validate` / `records.strategy`。

---

## 3. 依赖关系与工期

```
A1 分发 ─┬─ A2 算子(取值/变换) ─┬─ A3 组合/逻辑/多表 ─┬─ A4 切分 ─┬─ A5 校验 ─┬─ A8 端到端
         │                      │                     │           │           │
         └────────────────────── A6 校验器（可并行，依赖算子表）
                                                          A7 前端（依赖 A2~A5 定型）
```

- A1→A2→A3→A4→A5 串行（后者吃前者接口）；A6 可在 A2 后并行；A7 在 A5 后开工；A8 收尾。
- 总计约 5~7 个工作日（按人天，不含 B 期回流）。

## 4. 风险与对策

| 风险 | 对策 |
|---|---|
| 前端 v2 编辑器做不出来，规则写不进系统 | A7 底线：保留"参考文件选表选列自动填字段"，复杂算子先支持 JSON 高级编辑框（文本框粘贴 spec）兜底 |
| 算子设计过度膨胀成 DSL | 每个算子必须小而正交、纯函数；新算子加进注册表即可，不碰引擎；A 期只做表中 16 个（含 `kv`） |
| 非表格文档（营业执照）抽不出字段 | A2 必须实现 `kv`，走 `page.texts` 带坐标文本行，不依赖表格识别；验收合成样例抽 18 位信用代码 |
| 血缘在多算子后错位 | A2/A3 每步单测锚点；A8 端到端核对 cell 定位；anchors 统一走 `collect._anchor` |
| 改了老规则行为 | A1/A4 golden 对比逐字段相等；`spec_version` 缺省分支一行不改 |
| validate 误塞进 values 破坏往返契约 | A5 单测明确写入 `review.reason`，`get_records` 往返一致断言 |

## 5. 待拍板

1. A 期是否包含 A7 前端？若想先验证引擎，可先做 A1~A6 + JSON 高级编辑框，前端 UI 放 A7.1。
2. `lookup` 字典是内联在规则 JSON 里，还是单独建字典表？A 期默认内联（零迁移），B 期再考虑字典表。
3. 校验失败 `reject` 的语义：是阻断入库门禁，还是仅标记？A 期默认仅标记（不改门禁计数）。
