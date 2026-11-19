# result.json 字段解读与冗余清理（已执行）

> 对象：`mvp/output/<批次_文件名>/result.json`（每个文件一份，由 `pipeline/runner.py` 写出）
> 状态：**冗余清理已于 2026-11-19 一次性执行完毕**；同日升级为**多页文件信封** schema（`pages:[pageRec…]` + `stitched_tables`）。本文先讲当前终态 schema（信封 + 逐页三样），再回溯当初冗余在哪、怎么清的、实测收益。
> 配套：[engine-upgrade.md](./engine-upgrade.md)（引擎升级）· 纯函数桥 `mvp/viewmodel.py`

---

## 0. 一句话结论

result.json 现在是**文件信封**：顶层 `file/case/kind/encoding/params_snapshot/page_count` + `pages:[pageRec…]` + `stitched_tables`。**单页文件也是 `pages:[1]`**——没有「单页扁平 / 多页信封」双形态，没有兼容 shim。

每个 `pageRec`（一页）**只存三样东西**：官方 `parsing`（裁掉死字段）+ `structured_tables`（领域加工后的表）+ 该页元信息。
文字投影 `texts/scores/boxes`、版面 `layout`、行数/均值等**不再落盘**，改由 `viewmodel.hydrate()` 在**渲染期逐页从 parsing 现算**；raw 表中间态删除；落盘改紧凑序列化。
跨页续表由 `structure.stitch_tables()` 合并进文件级 `stitched_tables`（每格带 `page/space`）。

> §3 / §6 的瘦身实测字节数是**信封化之前的单页扁平格式**（历史参考）；清理原则（官方源 + 派生不落盘 + 紧凑序列化）在信封里**逐页继承**，收益不变。

实测收益（同一份输入、同一套参数重跑）：

| case | 路线 | 清理前磁盘 | 清理后磁盘 | 降幅 |
|---|---|---|---|---|
| 108_resplit | 图片 + 人工列边界 | 417,592 | **47,858** | **-88.5%** |
| 107_scan | 图片矫正 | 113,587 | **15,112** | **-86.7%** |
| 21_two_tables | 文本层 PDF | 31,832 | **7,730** | **-75.7%** |
| verify | CSV | 2,225 | **1,118** | **-49.8%** |

**正确性零退化**：hydrate 派生的投影与清理前存储的投影**逐元素完全相等**（`texts/scores/boxes/layout/lines/avg_score/low_score_lines` 全等，三 case 验证 True）；四路线行数/表数/回溯/文档标题全部一致。

---

## 1. 当前数据流（文件信封 + 逐页派生）

```
extract_one(src) ── 按 page 参数决定 page_list（all → 全部页；页码 → 单页）
        │
        ├─ 逐页 _extract_page_*() ──► pageRec（每页一份）
        │       PPStructureV3 单次推理 res
        │         ├─ _slim_parsing(_plain(res)) ─► page['parsing']   官方语义源（裁死字段）· 落盘
        │         └─ table_res_list → _TableParser → raw（中间态，不落盘）
        │                 │ resplit（人工列边界，可选）→ structure_all()
        │                 ▼
        │           page['structured_tables']  领域加工终态 · 落盘
        │
        ├─ file_rec['pages'] = [pageRec…]
        ├─ viewmodel.hydrate(file_rec)  逐页派生 + 注入文件上下文（case/file/kind）
        ├─ structure.stitch_tables(pages) ─► file_rec['stitched_tables']  跨页续表 · 落盘
        └─ json.dump(viewmodel.disk_view(file_rec))  紧凑落盘（逐页剥派生 + 上下文）

渲染期（builder.build）：
        viewmodel.hydrate(rec)  对每条 record 的每页：
            parsing.overall_ocr_res.{rec_texts,rec_scores,dt_polys} ─► texts/scores/boxes/lines/avg_score/low_score_lines
            parsing.parsing_res_list                                ─► layout[{label,content,bbox}]
        （内存视图，喂给报告；disk_view() 落盘时逐页剥掉，不重复存储）
```

两条存储原则（逐页继承）：

- **官方 JSON 为唯一事实源**：每页 `parsing` 保留官方字段名与语义，只删代码从不读取的死 weight（见 §3）。
- **派生视图不落盘**：投影/layout 是 parsing 的纯函数视图，渲染期现算（`hydrate`），落盘形态（`disk_view`）逐页剥掉它们。**这不是兼容 shim**——没有「旧字段保留以兼容旧代码」，而是彻底改为「单一源 + 渲染期派生」。

> 文本层 PDF / CSV 路线**没有 parsing**（不跑 PPStructureV3）。它们的 OCR 投影是唯一文字记录，**直接存储**（hydrate 对无 parsing 的页只注入上下文、不派生）。所以这两条路线的 pageRec 仍含 `texts/scores/boxes`，但**不构成冗余**（没有另一份 parsing 与之重复）。

### 1.1 文件信封顶层字段

| 字段 | 含义 |
|---|---|
| `file` / `case` / `kind` | 文件名 / 输出目录名 / 载体（image·pdf·csv） |
| `encoding` | 纯文本解码（csv/txt 路线），其余空 |
| `params_snapshot` | 本批生效参数（去掉 `_` 前缀内部键），文件级一份 |
| `page_count` | PDF 实际总页数（图片/CSV 恒 1） |
| `pages` | `pageRec` 数组，单页文件长度 1 |
| `stitched_tables` | 跨页合并表数组（无续表则 `[]`） |

### 1.2 多页产物命名与跨页拼接

- **逐页产物加 `p{n}` 前缀**（仅多页 PDF）：`pages/p{n}.png`（渲染图）、`pages/p{n}_rectified.png`（矫正图）、`pages/p{n}_boxes.png`（带框图）、`p{n}_table_{i}.csv`（**仅未被合并的表**）。单页保持 `source.png` / `pages/rectified.png` / `boxes.png` / `table_{i}.csv`。
- **拼接判据（保守，宁可不拼不误拼）**：只合并**相邻页**（p 末表 ↔ p+1 首表），且同时满足 ① 列数相同且非零 ② 坐标空间相同（`coord.space`）③ 来源精确（`coord.exact`）④ 列 x 边界对齐（≥2 对有效列、容差 12px）⑤ 表头空白归一化后相同（重复表头丢弃、行连续）。`used` 集防止重复起链，**一个文件可有多条独立跨页链**。
- 合并表 `stitched_tables[i]`：`headers/rows/row_pages/cells/n_rows/n_cols/source_pages/parts/csv_file=stitched_{i}.csv`，`coord={mixed:true, space:'per-cell', exact:true}`；**每格 `cells[r][c]={bbox,page,space}`** 保留来源页与空间，报告据此做页感知回溯（悬停自动切页 + 高亮）。
- **下载归一 + 碎片不落盘**：被并入合并表的逐页表（`parts` 里的 `(page,tbl)`），提取层**跳过其碎片 CSV 导出**，磁盘只留 `stitched_{i}.csv`；报告里这些表的下载按钮直接给完整合并表（带「跨页合并」徽标），未合并的表保持各自 `table_{i}.csv`。
- **报告呈现**：合并表收进**每个页卡片的「跨页合并」tab**（非独立底部面板），多链以子页签区分；**整份信封 JSON 以默认收起的折叠区同放该 tab**，文件底部不再单列占版面。页签为**仅数字的小圆点**、悬浮**源图 stage 右缘**；页头为**单一文件级紧凑整合头**（主行=标题+标签+右置文件级汇总，副行=链接+当前页片段，切页时由 `<template>` 注入 `.pagehead-slot` 更新），切页保留激活 tab 与合并表子页签。`stitched_tables` 仍是文件信封的落盘字段（数据模型不变），只是 UI 不再单列面板。

---

## 2. 逐页 pageRec 字段解读

> 下列字段都在 `pages[i]` 里（每页一份）；文件级顶层字段见 §1.1。字节数为信封化前单页实测（历史参考），结构关系不变。

### 2.1 ppstruct 路线（图片 / 扫描件）· 以 108 为例（紧凑 46,944 字节）

| 字段 | 字节 | 含义 | 备注 |
|---|---|---|---|
| `parsing` | 38,064 | 官方语义源（裁死字段后） | 唯一事实源，详见 §2.3 |
| `structured_tables` | 8,112 | 领域加工后的表：headers/rows/cells/n_rows/n_cols/fill_ratio/csv_file/coord | resplit + structure 的产物，**与 parsing 原始表不同**（108 经重切 25黏连格→23×7） |
| 页元信息 | ~770 | page/source/rectified/image_size/rectified_size/boxes_png/text_layer/cropbox_limited/plain_text/text_space/table_route/notes/elapsed | 该页导航/图片/诊断（file/case/kind/encoding/params_snapshot 在文件信封顶层） |

**不再落盘**（渲染期 hydrate 派生）：`texts` `scores` `boxes` `layout` `lines` `avg_score` `low_score_lines`。
**已删除**：raw `tables`（中间态，报告从不读）。

### 2.2 文本层 PDF / CSV 路线 · 以 21 为例（7,730 字节）

| 字段 | 含义 | 备注 |
|---|---|---|
| `parsing` | null | 不跑 PPStructureV3 |
| `texts/scores/boxes/lines/avg_score/low_score_lines` | 独立 OCR（pdfplumber 路线的文字源）/ CSV 为空 | **唯一文字记录，直接存储，非冗余** |
| `layout` | `[]` | 无版面语义 |
| `plain_text` / `encoding` | 文本层全文 / 解码 | 文本原文弹窗 |
| `structured_tables` | pdfplumber 直读 / CSV 直读加工 | 带单元格 bbox |
| 页元信息 | 同 §2.1 | file/case/kind/encoding/params_snapshot 在文件信封顶层 |

### 2.3 `parsing` 内部（裁死字段后保留的官方语义源）

| 子字段 | 108 字节 | 含义 | 谁用 |
|---|---|---|---|
| `overall_ocr_res.dt_polys` | 11,278 | 检测四点框 | hydrate → `boxes`（回溯） |
| `overall_ocr_res.rec_texts` | 2,807 | 识别文字 | hydrate → `texts` |
| `overall_ocr_res.rec_scores` | 4,483 | 全精度置信度 | hydrate → `scores`(round4)/avg/low |
| `parsing_res_list` | 4,138 | 版面块（block_label/content/bbox/id/order） | hydrate → `layout`（文档 tab 标题/顺序） |
| `table_res_list[*].cell_box_list` | 11,667 | 模型原始格框 | raw 表溯源（resplit 前） |
| `table_res_list[*].pred_html` | 3,478 | 模型原始表格 HTML | raw 表溯源 |
| `doc_preprocessor_res.angle` | 13 | 矫正旋转角 | 诊断 |
| `width` / `height` | 7 | 图宽高 | 元信息 |

> `table_res_list` 是**模型原始输出**，`structured_tables` 是**经 resplit/structure 加工后**的终态——两者在有人工列边界时**内容不同**，是「官方源 ↔ 加工资产」的溯源关系，不是重复存储。无重切时二者一致，但 structured 仍是报告唯一读取的表层（领域资产，保留）。

---

## 3. 当初冗余在哪 · 怎么清的（回溯）

> 本节字节数均为**信封化之前的单页扁平 result.json** 实测（历史参考）。三刀清理原则在信封里逐页继承：每页 parsing 同样裁死字段、投影同样渲染期派生、落盘同样紧凑。

清理前 108 磁盘 417,592 字节，紧凑仅 116,880——**72% 是 indent=2 缩进空白**。紧凑部分里又有大量重复。三类问题、三刀清掉：

### 3.1 第一刀 · 缩进空白（-72%）

`boxes/dt_polys/cell_box_list` 都是深层数字数组，`indent=2` 把每个数字单独成行加空格，指数级放大。
**清理**：`runner.py` 落盘改 `json.dump(..., separators=(',',':'))` 紧凑。报告 JSON tab 由 `cards.json_section` 渲染时 `indent=2` 重新美化，**可读性不受影响**。清理后 108 缩进空白仅 914 字节（2%）。

### 3.2 第二刀 · parsing 死字段（代码 0 引用，纯搬运副产品）

`_plain(inner)` 当初无差别原样搬运官方 JSON，带进一堆下游从不读的死 weight。`_slim_parsing()` 删除：

| 删除项 | 108 字节 | 为什么死 |
|---|---|---|
| `table_res_list[*].table_ocr_pred` | **22,957** | 逐格 OCR，格文字已进 pred_html→rows；代码 0 引用（最大单块） |
| `overall_ocr_res.rec_polys` | 11,278 | **== dt_polys**（parsing 内部自我重复） |
| `overall_ocr_res.rec_boxes` | 4,961 | 轴对齐外接矩形，可由 polys 推导；0 引用 |
| `layout_det_res` | 965 | 版面检测原始框，与 parsing_res_list.block_bbox 重叠；0 引用 |
| `overall_ocr_res.textline_orientation_angles` | 678 | 每行方向角，平整扫描件全 0；0 引用 |
| `input_path`（顶层 + 各子 res） | 105+ | **上传临时文件绝对路径，泄漏本机路径**；0 引用 |
| `model_settings` / `text_det_params` / `text_type` / `text_rec_score_thresh` / `return_word_box` 等回显 | ~700 | 配置回显，与 params_snapshot 重叠；0 引用 |
| `page_index` / `page_count` | 8 | 单页路线恒 null |

parsing 从 79,998 → **38,064**（-52%）。保留的全是 hydrate / raw 溯源所需的官方语义源（§2.3）。

### 3.3 第三刀 · 退役过渡冗余（投影 / layout / raw）

清理前同一信息存多遍（实测相等关系）：

| 信息 | 清理前存储位置 | 遍数 |
|---|---|---|
| 文字框 | `boxes` == `parsing.dt_polys` == `rec_polys` | 3× |
| 文字 | `texts` == `rec_texts` | 2× |
| 置信度 | `scores`(round) ⊂ `rec_scores`(全精度) | 2× |
| 版面块 | `layout` ≈ `parsing_res_list` | 2× |
| 格框/格文字 | `table_res_list` → raw `tables` → `structured_tables` | 3~4× |

**清理**：
- 投影 `texts/scores/boxes` + 派生指标 `lines/avg_score/low_score_lines` + `layout` **不再落盘**，改 `viewmodel.hydrate()` 渲染期从 parsing 现算（`disk_view()` 落盘剥掉）。
- raw `tables` **删除**（报告只读 structured_tables，raw 是 resplit/structure 的中间态）。
- `structured_tables` 保留（领域加工资产，非纯投影）。

> 这正是 engine-upgrade §4 规划的「薄投影验证后退役」。当初为过渡保留投影 + 官方全量两份；验证通过后彻底改为单一源 + 派生视图，不留兼容 shim。

---

## 4. viewmodel.py：派生视图的纯函数桥（信封逐页）

`mvp/viewmodel.py`（与 config 同级，**仅依赖 config，不触发 pipeline 重 import**）：

- `DERIVED`：派生键清单（texts/scores/boxes/layout/lines/avg_score/low_score_lines），落盘剥掉、渲染补回。
- `CONTEXT`：文件上下文键（case/file/kind），hydrate 时注入每页供报告渲染便利，落盘剥掉（避免每页重复存文件级信息）。
- `hydrate(rec)`：rec 含 `pages` → 逐页 `setdefault` 注入 CONTEXT + `_derive_page`；否则按单页 `_derive_page`。`_derive_page`：有 parsing → 从 `overall_ocr_res` 现算投影、从 `parsing_res_list` 现算 layout；无 parsing → 只注入上下文、投影原样保留。**幂等**。
- `disk_view(rec)`：rec 含 `pages` → 顶层去掉 `pages` 后保留文件级字段，`pages` 逐页 `_disk_page`；否则单页 `_disk_page`。`_disk_page`：剥 CONTEXT，再对有 parsing 的页剥 DERIVED（文本层/CSV 无 parsing，投影保留）。

调用点：
- `runner.extract_one`：组装信封后 `hydrate(file_rec)`（供逐页 boxes_png 绘制 + 日志 + 返回给 app），落盘写 `disk_view(file_rec)` 紧凑。
- `builder.build`：开头对每条 record `hydrate`（磁盘 slim parsing → 逐页渲染视图）。
- `cards.json_section`：单页卡片展示 `disk_view(file_rec)`（文件信封 pretty，与下载 result.json 一致）；多页另给「本页 JSON」展示该页 `disk_view` 形态。

报告层 `cards.py` 的文字/文档/回溯逻辑读的是 hydrate 补齐的 `texts/boxes/layout`，与清理前完全一致（§0 逐元素相等验证）；多页只是把同一套逻辑套在「激活页子卡片」上，拼接表用独立的 `.scell`/`.stitchbox` 页感知通路。

---

## 5. 验证清单（2026-11-19 全部通过）

冗余清理（单页扁平时期）：

- [x] 四路线重跑：108(off, column_lines=496) / 107(on) / 21(文本层) / CSV，行数/表数与清理前一致（226/1、58/1、53/2、0/1）。
- [x] **hydrate 派生投影 == 清理前存储投影**（texts/scores/boxes/layout/lines/avg_score/low_score_lines 逐元素相等，三 case True）。
- [x] 新 result.json：ppstruct 无 DERIVED 键、无 raw tables、parsing 无 input_path/table_ocr_pred/rec_polys/rec_boxes/layout_det_res。
- [x] 报告渲染：108 文字 226 行/226 框、107 文档 tab 2 个标题（mdhead）、21 两表、CSV 无图。
- [x] 交互回溯：108 悬停文字行→框高亮、单元格点击→钉住；107 切矫正图→mdline 点击钉住+框高亮、双「隐藏叠加框」同步。
- [x] JSON tab == 下载（均 disk_view 形态：有 parsing、无 texts/raw）；控制台无报错。
- [x] 体量：108 -88.5% / 107 -86.7% / 21 -75.7% / CSV -49.8%。

多页信封 + 拼接（同日升级后）：

- [x] 单页零回归：21(文本层)/107(扫描 on)/CSV 仍 `pages:[1]`，文字行↔框、单元格↔cellbox 回溯、矫正图自动切视图全部正常。
- [x] 多页全量：20_multipage_3pages.pdf `page=all` → 3 页各 6×6 表，逐页 `p{n}.png/p{n}_boxes.png/p{n}_rectified.png` 无碰撞；磁盘信封顶层键正确、无 CONTEXT 泄漏、ppstruct 页 derived 剥净（parsing 在）、文本层/CSV 页投影保留。
- [x] 跨页拼接：3 页续表合并成 `stitched_1.csv` 18 行×6 列、`source_pages=[1,2,3]`、每格带 page/space。
- [x] 页感知回溯：合并表单元格（page3）悬停→自动切到第 3 页 + `.scell.hv`/`.stitchbox.hv` 各 1，离开归 0，点击钉住 1+1；页签切换只显示激活页。
- [x] 扫描多页 A/B：107+108 拼成 2 页 PDF `page=all` `doc_unwarp=on` → 2 页 ppstruct rectified、`p1/p2_rectified.png` 不碰撞；两表版式不同**正确不合并**（stitched=0）。

---

## 6. 附录：清理前冗余实测（历史参考）

清理前 108 验证脚本（全部 True）：

```python
r = json.load(open('20261119104813_108_resplit/result.json', encoding='utf-8'))
p = r['parsing']; o = p['overall_ocr_res']
assert r['boxes'] == o['dt_polys'] == o['rec_polys']          # 文字框三处相等
assert r['texts'] == o['rec_texts']                           # 文字两处相等
assert r['scores'] == [round(x, 4) for x in o['rec_scores']]  # 置信度=全精度round4
assert r['image_size'] == [p['width'], p['height']]
assert r['lines'] == len(r['texts'])
# compact=116880 indent2=383792 disk=417592 whitespace_overhead=300712 (72%)
```

清理前代码 0 引用死字段计数（`grep -rn --include=*.py <kw> pipeline report`）：
`table_ocr_pred:0  rec_boxes:0  layout_det_res:0  textline_orientation_angles:0  model_settings:0  input_path:0`；`parsing` 在 report/ 0 命中（纯存档）。

清理后 parsing 子字段体量（108，紧凑）：

```
parsing=38064  structured_tables=8112
  overall_ocr_res=18613  {dt_polys:11278, rec_texts:2807, rec_scores:4483}
  table_res_list[0]=15181 {cell_box_list:11667, pred_html:3478}
  parsing_res_list=4138   doc_preprocessor_res=13   width/height=7
```

> 历史 case 的旧格式 result.json 仍在 output/ 下（未删，供对比）。注意有两代旧格式：① 清理前的「扁平 + 冗余投影」，② 清理后但信封化前的「扁平单页」。当前 builder/cards 按**文件信封**（`pages`）渲染，这两代旧文件都需**重跑**才能正常显示；新上传/重跑一律产出「信封 + 逐页三样」格式。本节字节数仅作瘦身收益的历史参考。