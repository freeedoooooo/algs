# result.json 字段解读与冗余分析

> 对象：`mvp/output/<批次_文件名>/result.json`（每个 case 一份，由 `pipeline/runner.py:197` 写出）
> 样本：`20261119104813_108_resplit`（图片 + 人工列边界重切，**417,592 字节**，下文简称 108）
> 对照：107（矫正图扫描件）、21（文本层 PDF）、verify（CSV）
> 结论先行：**冗余确实很多，但大部分是「升级过渡期」有意保留的，不是 bug。** 真正可立刻无 regret 清掉的有两块：① `indent=2` 缩进空白（占磁盘 72%）；② `parsing` 里若干**代码从不读取**的死字段（最大单块 `table_ocr_pred` 22,957 字节）。

---

## 0. 一张图看懂数据流

```
PPStructureV3 单次推理 res
        │
        ├─ _plain(res) 原样 ───────────────► rec['parsing']   （官方全量 JSON · 存档 · 报告层不读）
        ├─ parsing_res_list 改名投影 ──────► rec['layout']    （报告文档 tab 读）
        ├─ overall_ocr_res 投影 ───────────► rec['texts'/'scores'/'boxes']  （报告文字 tab / 回溯读）
        └─ table_res_list → _TableParser ──► rec['tables']（raw 中间态）
                                                  │ structure_all()
                                                  ▼
                                          rec['structured_tables']  （报告表格 tab / 文档 tab 读）
```

关键事实（已 grep 验证）：

- **报告层 `report/` 从不读 `rec['parsing']`**（`grep parsing report/` → 0 命中）。它只读 `structured_tables`、`layout`、`texts/scores/boxes`、`elapsed` 与少量元信息。
- `parsing` 当前是**纯存档**：作为「官方唯一事实源」原样落盘，但下游还没接它。这正是 [engine-upgrade.md](./engine-upgrade.md) §4 说的「薄投影待文字 tab 直读 parsing/layout 后可退役」的过渡状态。
- 于是同一份信息被存了多遍：官方全量里一遍、投影里一遍、表格中间态里一遍、结构化结果里一遍。

---

## 1. 逐字段解读（108 实测字节，紧凑序列化口径）

> 字节数 = `len(json.dumps(v, ensure_ascii=False))`，不含缩进。磁盘实际 417,592，紧凑仅 116,880（差额见 §3）。

### 1.1 应用信封 / 元信息（小，必要）

| 字段 | 字节 | 含义 | 谁读 |
|---|---|---|---|
| `file` / `case` | 32 / 28 | 原始文件名 / case 相对目录 | 报告导航、`file_url` |
| `kind` | 7 | `image` / `pdf` / `csv` 载体分流 | runner 分支 |
| `source` / `rectified` | 12 / 4 | 左图文件名 / 矫正图文件名（off 时为 null） | 报告图片区 |
| `image_size` / `rectified_size` | 11 / 4 | 原图 / 矫正图宽高 | SVG viewBox、`--ar` |
| `boxes_png` | 11 | 带框 PNG 文件名 | 报告（可选） |
| `pages` / `page` | 1 / 1 | 总页数 / 本次处理页 | 报告页头 |
| `text_layer` / `cropbox_limited` | 5 / 5 | PDF 是否有文本层 / 是否 CropBox 裁剪 | 路线判定 |
| `encoding` / `plain_text` | 2 / 2 | 纯文本解码 / 全文（图片路线恒空） | 文本原文弹窗 |
| `text_space` | 8 | `source` / `rectified`，文字框坐标空间 | 回溯切视图 |
| `table_route` | 10 | `ppstruct` / `text_layer` / `skipped` | 报告标签 |
| `notes` | 109 | 人类可读诊断备注 | 报告诊断 |
| `params_snapshot` | 201 | 本次生效调试参数 | 报告参数快照 |
| `elapsed` | 5 | 推理耗时 | 报告页头 |

### 1.2 文字薄投影（报告文字 tab / 回溯在用 · 可退役）

| 字段 | 字节 | 含义 | 冗余关系 |
|---|---|---|---|
| `texts` | 2,807 | 226 行识别文字 | **== `parsing.overall_ocr_res.rec_texts`（完全相等）** |
| `scores` | 1,705 | 226 行置信度（round 4 位） | **== `round(rec_scores, 4)`**；rec_scores 是全精度 4,483 |
| `boxes` | 11,278 | 226 个四点框 | **== `dt_polys` == `rec_polys`（三者完全相等）** |
| `lines` | 3 | 行数 | **== `len(texts)`，可推导** |
| `avg_score` | 6 | 平均置信度 | 可由 scores 推导 |
| `low_score_lines` | 1 | 低置信行数 | 可由 scores + 阈值推导 |

### 1.3 版面语义（报告文档 tab 在用）

| 字段 | 字节 | 含义 | 冗余关系 |
|---|---|---|---|
| `layout` | 3,874 | 5 个角色块 `{label, content, bbox}` | **是 `parsing.parsing_res_list`（4,138）的改名投影**：`label←block_label`、`content←block_content`、`bbox←block_bbox`，丢弃 `block_id`/`block_order` |

### 1.4 表格（报告表格 tab / 文档 tab 在用）

| 字段 | 字节 | 含义 | 冗余关系 |
|---|---|---|---|
| `tables`（raw） | 8,223 | 中间态：`rows`（格文字）+ `cell_grid`（格框）+ coord | 由 `parsing.table_res_list` 解析而来；**报告层不读 raw，只读 structured** |
| `structured_tables` | 8,112 | 终态：`headers`/`rows`/`cells`/`n_rows`/`n_cols`/`fill_ratio`/`csv_file`/coord | 由 raw 经 `structure_all()` 推导；格文字/格框与 raw、与 `table_res_list` 重复 |

### 1.5 官方全量 `parsing`（存档 · 报告层不读 · 冗余重灾区，79,998 字节）

| 子字段 | 字节 | 含义 | 代码引用 | 冗余 / 死字段 |
|---|---|---|---|---|
| `overall_ocr_res.dt_polys` | 11,278 | 检测四点框 | 投影来源 | **== rec['boxes'] == rec_polys** |
| `overall_ocr_res.rec_polys` | 11,278 | 识别四点框 | 投影来源 | **== dt_polys（parsing 内部自我重复）** |
| `overall_ocr_res.rec_texts` | 2,807 | 识别文字 | 投影来源 | **== rec['texts']** |
| `overall_ocr_res.rec_scores` | 4,483 | 全精度置信度 | 投影来源 | rec['scores'] 是它的 round 版 |
| `overall_ocr_res.rec_boxes` | 4,961 | 轴对齐外接矩形 | **0 引用** | 可由 polys 推导，**死字段** |
| `overall_ocr_res.textline_orientation_angles` | 678 | 每行方向角 | **0 引用** | 平整扫描件全 0，**死字段** |
| `overall_ocr_res.text_det_params` / `model_settings` 等 | ~200 | 参数回显 | 0 引用 | 与 params_snapshot 部分重叠 |
| `table_res_list[0].table_ocr_pred` | **22,957** | 逐格 OCR（rec_polys/texts/scores/boxes，220 条） | **0 引用** | **最大单块死字段**，格文字已进 pred_html→rows |
| `table_res_list[0].cell_box_list` | 11,667 | 150 个格框 | raw 来源 | → raw.cell_grid → structured.cells（多遍） |
| `table_res_list[0].pred_html` | 3,478 | 表格 HTML | raw 来源 | → raw.rows → structured.rows/headers（多遍） |
| `parsing_res_list` | 4,138 | 5 个版面块（含 id/order） | layout 来源 | **≈ rec['layout']** |
| `layout_det_res` | 965 | 版面检测原始框（label+score+bbox） | **0 引用** | 与 parsing_res_list.block_bbox 重叠，**死字段** |
| `model_settings` | 336 | 引擎开关回显 | **0 引用** | 配置回显 |
| `doc_preprocessor_res` | 140 | 矫正 angle 等 | 1 引用（取 angle） | 大部分子字段无用 |
| `input_path` | 105 | **上传临时文件绝对路径** | **0 引用** | 泄漏本机路径，下游无用，**死字段** |
| `width` / `height` | ~7 | 图宽高 | — | **== rec['image_size']** |
| `page_index` / `page_count` | 8 | 恒 null | 0 引用 | 单页路线无意义 |

---

## 2. 冗余地图：同一信息存了几遍（108 实测相等关系）

下列等式均用脚本**逐元素比对验证为 True**（见 §6 附录）：

| 信息 | 存储位置 | 遍数 | 浪费（紧凑字节） |
|---|---|---|---|
| 文字行四点框 | `boxes` = `dt_polys` = `rec_polys` | **3×** | 22,556 |
| 文字行文字 | `texts` = `rec_texts` | 2× | 2,807 |
| 文字行置信度 | `scores`(round) ⊂ `rec_scores`(全精度) | 2× | ~1,705 |
| 版面块 | `layout` ≈ `parsing_res_list` | 2× | ~3,874 |
| 单元格框 | `cell_box_list` → `raw.cell_grid` → `structured.cells`（+ `table_ocr_pred.rec_boxes/rec_polys`） | **4×** | 上万 |
| 单元格文字 | `pred_html` + `table_ocr_pred.rec_texts` → `raw.rows` → `structured.rows/headers` | **4×** | 上万 |
| 图宽高 | `image_size` = `[parsing.width, height]` | 2× | 极小 |
| 行数/均值/低置信数 | `lines`/`avg_score`/`low_score_lines` 可由 texts/scores 推导 | 派生 | 极小 |

**量化结论（108，紧凑 116,880 字节口径）：**

- 报告层真正需要的载荷 ≈ `structured_tables`(8,112) + `layout`(3,874) + 投影(15,790) + 元信息(~800) ≈ **28,576 字节（24%）**。
- `parsing`(79,998) + raw `tables`(8,223) = **88,221 字节（75%）** 是报告层不读的存档 / 中间态。
- `parsing` 内部**代码 0 引用的死字段**合计 ≈ `table_ocr_pred`22,957 + `rec_boxes`4,961 + `rec_polys`重复11,278 + `layout_det_res`965 + `textline_orientation_angles`678 + `model_settings`~400 + `input_path`105 ≈ **41,300 字节**（占紧凑总量 35%）。

---

## 3. 最大的「假冗余」：indent=2 缩进空白（占磁盘 72%）

| 口径 | 字节 |
|---|---|
| 磁盘实际（`indent=2`） | 417,592 |
| 紧凑序列化（无缩进） | 116,880 |
| **纯缩进空白** | **300,712（72%）** |

原因：`boxes`/`dt_polys`/`rec_polys`/`cell_box_list` 都是「数组套数组套数字」，`indent=2` 把每个数字单独成行并加大量空格，深层嵌套被指数级放大。

**关键点：报告 JSON tab 不受影响。** `report/cards.py:519` 是 `json.dumps(rec, indent=2)` **在生成报告时重新美化**，与磁盘怎么存无关。所以：

> 把 `runner.py:199` 的落盘改成紧凑（`indent=None` 或 `separators=(',',':')`），**108 立刻从 417KB → 117KB（-72%）**，报告 JSON tab 依旧漂亮可读。唯一代价：直接用文本编辑器打开裸 `result.json` 时不再自动换行缩进（但可用任何 JSON 工具一键美化）。

这是**零风险、零设计争议**的第一刀。

---

## 4. 为什么会这么冗余（不是 bug，是过渡期设计）

[engine-upgrade.md](./engine-upgrade.md) 定的原则是「**官方 JSON 为唯一事实源 + 现有 rec 字段降级为薄投影，验证后可彻底清理**」。当前正处在「验证已通过、清理尚未做」的中间态：

- `parsing` 原样保留 = 忠实官方事实源（原则要求）。
- 投影 `texts/scores/boxes` 保留 = 文字 tab 还在读它（尚未迁移到直读 parsing/layout）。
- raw `tables` 保留 = resplit 的输入/输出记录 + structure 的中间态。
- `parsing` 里那些 0 引用死字段 = `_plain(inner)` **无差别原样搬运**官方 JSON 的副产品——官方给什么就存什么，没做裁剪。

所以冗余分两种性质：
1. **有意保留的过渡冗余**（投影 ↔ parsing、raw ↔ structured）：要等下游迁移后才能退役，符合「先验证后清理、不留 shim」。
2. **无意的死重量**（parsing 内 0 引用子字段、indent 空白、input_path 路径泄漏）：与原则无关，随时可清。

---

## 5. 分级清理建议（含预估收益与取舍）

> 遵循「设计先行」：本文只做分析，**不改代码**。下面按风险/收益排序，待你拍板再动手。

### 第 1 梯队 · 无 regret，立刻可做

| 动作 | 改动点 | 108 收益 | 风险 |
|---|---|---|---|
| 落盘改紧凑 | `runner.py:199` `indent=2`→`separators=(',',':')` | **-300,712（-72%）** | 裸文件可读性↓（报告 tab 不受影响） |
| 删 `input_path` | `ppstruct.py::_plain` 过滤键 | -105 + **消除本机路径泄漏** | 无（0 引用） |

### 第 2 梯队 · 裁剪 parsing 死字段（保留官方语义，去掉搬运副产品）

在 `_plain(inner)` 落盘前剔除**代码 0 引用且可推导/无意义**的子字段：

- `overall_ocr_res`：`rec_polys`（==dt_polys）、`rec_boxes`（可推导）、`textline_orientation_angles`（全 0 无用）、`text_det_params`/`model_settings` 回显。
- `table_res_list[*]`：`table_ocr_pred`（**22,957，最大块**，格文字已进 pred_html）。
- 顶层：`layout_det_res`（与 parsing_res_list 重叠）、`model_settings`、`page_index`/`page_count`（恒 null）。

预估 108 紧凑再 **-41,000 左右**；叠加第 1 梯队，磁盘 417KB → ~75KB（**-82%**）。

取舍：这会让 `parsing` 不再是「逐字节官方原样」，而是「官方语义子集」。若你坚持「官方原样存档」原则，可改为**把完整 parsing 单独落一份 `parsing_full.json`（紧凑），result.json 里只留瘦身版**——既保事实源可追溯，又给报告减负。两种路线二选一，需你定。

### 第 3 梯队 · 退役过渡冗余（需先迁移下游，符合「先验证后清理」）

- 文字 tab / 回溯改为直读 `parsing.overall_ocr_res`（或 layout），随后删投影 `texts/scores/boxes`（-15,790）。
- 报告确认不读 raw `tables` 后，删 raw（-8,223），只留 `structured_tables`。
- `lines`/`avg_score`/`low_score_lines`/`image_size` 属派生便利字段，极小，**建议保留**（报告页头直接用，删了反而要前端重算）。

这一步是 engine-upgrade §4 早已规划的「薄投影退役」，属结构性改动，应单独设计 + 验证。

### 不建议动

- `structured_tables`、`layout`、`coord`、`params_snapshot`、`notes`：报告核心载荷与领域资产，保留。
- 各路线恒空字段（图片路线的 `plain_text`、文本层路线的 `parsing=null`）：体积极小，是统一信封的代价，删了会让前端到处判空，得不偿失。

---

## 6. 附录：验证脚本与实测等式

```python
import json
r = json.load(open('20261119104813_108_resplit/result.json', encoding='utf-8'))
p = r['parsing']; o = p['overall_ocr_res']
assert r['boxes'] == o['dt_polys'] == o['rec_polys']      # 文字框三处完全相等
assert r['texts'] == o['rec_texts']                       # 文字两处完全相等
assert r['scores'] == [round(x, 4) for x in o['rec_scores']]  # 置信度=全精度round4
assert r['image_size'] == [p['width'], p['height']]       # 宽高相等
assert r['lines'] == len(r['texts'])                      # 行数可推导
# layout 是 parsing_res_list 的改名投影：
b = p['parsing_res_list'][0]; l = r['layout'][0]
assert (l['label'], l['content'], l['bbox']) == (b['block_label'], b['block_content'], b['block_bbox'])
```

实测输出（全部 True）：

```
boxes==dt_polys: True
dt_polys==rec_polys: True
texts==rec_texts: True
scores==round(rec_scores,4): True
image_size==[width,height]: True
lines==len(texts): True
compact=116880 indent2=383792 disk=417592 whitespace_overhead=300712 (72%)
```

代码引用计数（`grep -rn --include=*.py <kw> pipeline report config.py params.py`）：

```
table_ocr_pred:0  rec_boxes:0  layout_det_res:0  textline_orientation_angles:0
model_settings:0  input_path:0  pred_html:0(经 _html_blocks 间接取)
parsing 在 report/:0 命中（纯存档）
```

各 case 体量对照：

| case | 路线 | 磁盘字节 | parsing | 说明 |
|---|---|---|---|---|
| 108_resplit | 图片+重切 | 417,592 | 79,998 | 226 行 + 1 表，冗余最典型 |
| 107_scan | 图片矫正 | 113,587 | 23,655 | 58 行 + 矫正图 |
| 21_two_tables | 文本层 PDF | 31,832 | null | 不跑 PPStructureV3，无 parsing |
| verify | CSV | 2,225 | null | 直读，最精简 |

> 文本层 / CSV 路线没有 `parsing`，冗余主要是 raw↔structured 与 indent；图片/扫描路线才是 parsing 冗余重灾区。