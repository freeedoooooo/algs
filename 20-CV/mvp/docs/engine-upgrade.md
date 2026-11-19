# mvp 引擎升级方案对比：升级前 vs 升级后

> 配套流程图：[`engine-upgrade.drawio`](./engine-upgrade.drawio)（两页，可在 draw.io 继续编辑）
> 导出图：[升级前](./engine-upgrade-before.drawio.png) · [升级后](./engine-upgrade-after.drawio.png)

---

## 0. 先纠正一个前提（重要）

讨论初期我们以为「旧方案 = OCR + 表格模型，升级 = 引入 PP-StructureV3」。
**读代码后发现这个前提是错的**：PP-StructureV3 **现在就已经在用**，只是只取了它的表格输出。

证据（以下为**升级前**代码位置；升级后 `table_model.py` 已删除，见 §4）：

- `mvp/pipeline/engines.py:32` `structure()` 构造的就是 `PPStructureV3(...)`，按 `use_unwarp` 缓存两个槽位。
- `mvp/pipeline/table_model.py:178`（已删）表格路线调用的正是 `engines.structure(use_unwarp).predict(...)`。
- 但旧 `table_model.py` 只从结果里取 **表格 HTML + `cell_box_list` + 矫正图**，把 `parsing_res_list`（版面语义）和 `overall_ocr_res`（整页 OCR）**直接丢弃**。
- 整页文字另走一条独立推理：`mvp/pipeline/ocr.py:43` `recognize()` 用 `engines.py:17` 的独立 `PaddleOCR` 单例再跑一遍。

所以**升级的真实含义**不是「换引擎」，而是：

1. **把已经在跑的 PP-StructureV3 用全**——不再丢弃它的版面语义与整页 OCR；
2. **把两次推理合并成一次**——整页文字直接取 PP-StructureV3 内部的 `overall_ocr_res`，不再单独跑 PaddleOCR；
3. **以官方 JSON 为唯一事实源**，不自己制定私有标准；现有 `rec` 字段降级为「薄投影」，验证后可彻底清理。

---

## 1. 升级前（现状）：两次推理 · 语义丢弃

![升级前流程图](./engine-upgrade-before.drawio.png)

两条并行推理路径，同一张图被推理两遍：

| 路径 | 引擎 | 取用什么 | 丢弃什么 |
|---|---|---|---|
| 表格路线 | PP-StructureV3 推理①（先过长直线网格预筛 `grid_score`） | 表格 HTML、`cell_box_list`、矫正图 | `parsing_res_list`（版面语义）、`overall_ocr_res` |
| 文字路线 | 独立 PaddleOCR 推理②（整页） | `texts / boxes / scores`（source 空间） | —（但它本可由推理①顺带产出） |

下游：表格走 `resplit`（人工列边界，可选）→ `structure.py`（表头切分/对齐）→ `structured_tables`；
两路汇进**私有格式 `rec`** → `result.json` → 报告前端。
文档 tab 只能**按 y 坐标把文字行拼成文档流**——没有语义、没有真实标题。

**痛点**：冗余推理（②可省）、语义被丢（文档 tab 无标题/无角色）、私有格式（与官方不一致）。

---

## 2. 升级后（ppstruct 路线）：单次推理 · 官方 JSON 为源

![升级后流程图](./engine-upgrade-after.drawio.png)

一次 PP-StructureV3 推理，扇出五路、全部利用：

| 输出 | 去向 | 性质 |
|---|---|---|
| 官方 JSON（裁死字段） | `rec['parsing']` | **唯一事实源**（蓝） |
| `parsing_res_list` | 渲染期派生 `layout`：角色块 + 官方阅读顺序 | **新增语义**（绿） |
| `overall_ocr_res` | 渲染期派生 `texts/boxes/scores` | 薄投影，**已退役为派生视图**（灰） |
| `table_res_list` | `_TableParser`（复用）→ `resplit` → `structure.py` → `structured_tables` | 领域资产，**零改动**（绿） |
| `doc_preprocessor output_img` | `rectified.png` | 现有逻辑（灰） |

汇成 `rec = 应用信封 + parsing + structured_tables` → `result.json`（紧凑）→ 报告前端。
投影 / layout **不落盘**，由 `viewmodel.hydrate()` 渲染期从 parsing 现算（详见 [result-json-anatomy.md](./result-json-anatomy.md)）。
文档 tab **直读派生 `layout`**：真实标题、官方阅读顺序、块级坐标回溯。

**收益**：省掉一次整页推理；文档 tab 从「y 排序拼行」升级为「语义块流」；格式与官方对齐。

---

## 3. 逐维度对比

| 维度 | 升级前 | 升级后 |
|---|---|---|
| 推理次数 | 2 次（PPStructureV3① + PaddleOCR②） | 1 次（PPStructureV3） |
| 版面语义 | 丢弃 `parsing_res_list` | 保留为 `rec['layout']` |
| 整页文字来源 | 独立 PaddleOCR | PPStructureV3 内部 `overall_ocr_res` |
| 事实源 | 私有 `rec` | 官方 JSON `rec['parsing']` |
| 文档 tab | 按 y 拼行，无标题 | 直读 layout，真实标题/官方顺序 |
| 网格预筛 `grid_score` | 有（启发式门槛） | 新路线移除（语义由模型给） |
| `resplit` / `structure.py` | 在用 | **零改动保留** |
| PDF 文本层 / CSV 路线 | 在用 | **不变** |
| 私有投影字段 | 主体 | 薄投影，验证后清理 |

---

## 4. 保留 vs 清理

**保留（领域资产，与引擎无关）**：
- `resplit.py` 人工列边界重切（仍用独立 OCR 单例做子格 crop 重 OCR，仅 `unwarp=off`）。
- `structure.py` 表头切分 / 网格对齐 / CSV 导出。
- PDF 文本层路线（pdfplumber）、CSV 路线。
- `_TableParser`、`_save_rectified`、坐标空间约定（`coord.space`）。

**清理（已执行 · 2026-11-19 · 不留兼容 shim）**：
- 删除 `table_model.py`（含 `grid_score` 长直线预筛与旧 `tables()`）；表格解析 helper 移入 `ppstruct.py`。
- 删除 `config.GRID_*` 常量与 `params` 的 `grid_min_h / grid_min_v` 两项。
- 图片 / 扫描路线不再调 `ocr.recognize`（整页文字改由单次推理的 `overall_ocr_res` 投影提供）。

**有意保留（非 shim）**：
- `ocr.recognize` 仅作「PDF 文本层」路线的文字源——该路线不跑 PPStructureV3，此处 OCR 不冗余。
- `_doc_blocks_ysort`：仅作无 layout 路线（文本层 PDF / CSV）的回退，升级路线不走它。

> **薄投影已退役（2026-11-19 追加清理）**：`texts/scores/boxes/layout` 不再落盘，改由 `viewmodel.hydrate()` 渲染期从官方 `parsing` 现算；raw `tables` 中间态删除；parsing 裁死字段、紧凑落盘。result.json 体积降 76~89%，派生投影与清理前逐元素相等。详见 [result-json-anatomy.md](./result-json-anatomy.md)。

> 历史 case 的 `result.json` 是旧格式，升级后需**重跑**才能享受新文档 tab。

---

## 5. 三个决策点

1. **坐标空间**：PP-StructureV3 内部 OCR 跑在矫正图上。`unwarp=on` 时文字框在 rectified 空间，
   文档 tab 的文字行回溯需带 `data-space` 并支持原图/矫正图双视图切换（表格已有此机制，可复用）。
   `unwarp=off` 时矫正图与原图逐像素一致，坐标即 source，无需切换。
2. **resplit 不变**：它只治结构不治识别，子格 crop 重 OCR 仍走独立 OCR 单例，与主推理合并无关。
3. **网格预筛移除**：新路线不再用 `grid_score` 决定是否加载模型——语义由版面模型直接给出。

---

## 6. 验证清单（先验证、后清理 · 已于 2026-11-19 全部通过）

- [x] 单次推理产出 `parsing / layout / 投影 / tables / rectified` 五路齐全。
- [x] `unwarp=off`：文字框与表格框同处 source 空间，回溯 1:1 精准（108）。
- [x] `unwarp=on`：文字行回溯自动切矫正图视图，框对齐（107，58 框落在 rect 视图）。
- [x] 文档 tab 标题/段落/表格顺序与官方阅读顺序一致（107 出现 `##` 标题块）。
- [x] `resplit`、`structure.py`、CSV、PDF 文本层路线回归无退化。
- [x] 108 黏连列重切（`column_lines=496`）→ 23×7，余额/摘要分离，与升级前一致。
- [x] 清理已执行：删 `table_model` / grid 预筛 / 图片路线旧推理②；保留项见 §4「有意保留」。

实测摘要：108 单推理 32.3s 出 226 行 + 1 表（旧路线因预筛漏检为 skipped）；
107（unwarp=on）21.4s 出 58 行 + 1 表 + 矫正图；21 文本层 PDF 与 CSV 路线不变。