# result.json 字段解读与冗余清理（已执行）

> 对象：`mvp/output/<批次_文件名>/result.json`（每个 case 一份，由 `pipeline/runner.py` 写出）
> 状态：**冗余清理已于 2026-11-19 一次性执行完毕**。本文先讲清理后的终态 schema，再回溯当初冗余在哪、怎么清的、实测收益。
> 配套：[engine-upgrade.md](./engine-upgrade.md)（引擎升级）· 纯函数桥 `mvp/viewmodel.py`

---

## 0. 一句话结论

result.json 现在**只存三样东西**：官方 `parsing`（裁掉死字段）+ `structured_tables`（领域加工后的表）+ 应用元信息。
文字投影 `texts/scores/boxes`、版面 `layout`、行数/均值等**不再落盘**，改由 `viewmodel.hydrate()` 在**渲染期从 parsing 现算**；raw 表中间态删除；落盘改紧凑序列化。

实测收益（同一份输入、同一套参数重跑）：

| case | 路线 | 清理前磁盘 | 清理后磁盘 | 降幅 |
|---|---|---|---|---|
| 108_resplit | 图片 + 人工列边界 | 417,592 | **47,858** | **-88.5%** |
| 107_scan | 图片矫正 | 113,587 | **15,112** | **-86.7%** |
| 21_two_tables | 文本层 PDF | 31,832 | **7,730** | **-75.7%** |
| verify | CSV | 2,225 | **1,118** | **-49.8%** |

**正确性零退化**：hydrate 派生的投影与清理前存储的投影**逐元素完全相等**（`texts/scores/boxes/layout/lines/avg_score/low_score_lines` 全等，三 case 验证 True）；四路线行数/表数/回溯/文档标题全部一致。

---

## 1. 清理后的数据流

```
PPStructureV3 单次推理 res
        │
        ├─ _slim_parsing(_plain(res)) ─────► rec['parsing']   官方语义源（裁死字段）· 落盘
        └─ table_res_list → _TableParser ──► raw（中间态，不落盘）
                                                  │ resplit（人工列边界，可选）→ structure_all()
                                                  ▼
                                          rec['structured_tables']  领域加工终态 · 落盘

渲染期（builder.build / runner 返回前）：
        viewmodel.hydrate(rec)
            parsing.overall_ocr_res.{rec_texts,rec_scores,dt_polys} ─► texts/scores/boxes/lines/avg_score/low_score_lines
            parsing.parsing_res_list                                ─► layout[{label,content,bbox}]
        （这些是内存视图，喂给报告；disk_view() 落盘时剥掉，不重复存储）
```

两条存储原则：

- **官方 JSON 为唯一事实源**：`parsing` 保留官方字段名与语义，只删代码从不读取的死 weight（见 §3）。
- **派生视图不落盘**：投影/layout 是 parsing 的纯函数视图，渲染期现算（`hydrate`），落盘形态（`disk_view`）剥掉它们。**这不是兼容 shim**——没有「旧字段保留以兼容旧代码」，而是彻底改为「单一源 + 渲染期派生」。

> 文本层 PDF / CSV 路线**没有 parsing**（不跑 PPStructureV3）。它们的 OCR 投影是唯一文字记录，**直接存储**（hydrate 对无 parsing 的 rec 原样返回）。所以这两条路线的 result.json 仍含 `texts/scores/boxes`，但**不构成冗余**（没有另一份 parsing 与之重复）。

---

## 2. 清理后逐字段解读

### 2.1 ppstruct 路线（图片 / 扫描件）· 以 108 为例（紧凑 46,944 字节）

| 字段 | 字节 | 含义 | 备注 |
|---|---|---|---|
| `parsing` | 38,064 | 官方语义源（裁死字段后） | 唯一事实源，详见 §2.3 |
| `structured_tables` | 8,112 | 领域加工后的表：headers/rows/cells/n_rows/n_cols/fill_ratio/csv_file/coord | resplit + structure 的产物，**与 parsing 原始表不同**（108 经重切 25黏连格→23×7） |
| 元信息信封 | ~770 | file/case/kind/source/rectified/image_size/rectified_size/boxes_png/pages/page/text_layer/cropbox_limited/encoding/plain_text/text_space/table_route/notes/params_snapshot/elapsed | 报告导航/图片/参数快照/诊断 |

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
| 元信息信封 | 同上 | — |

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

## 4. viewmodel.py：派生视图的纯函数桥

`mvp/viewmodel.py`（与 config 同级，**仅依赖 config，不触发 pipeline 重 import**）：

- `hydrate(rec)`：有 parsing → 从 `overall_ocr_res` 现算 texts/scores/boxes/lines/avg_score/low_score_lines，从 `parsing_res_list` 现算 layout；无 parsing → 原样返回。**幂等**。
- `disk_view(rec)`：ppstruct 路线剥掉 `DERIVED` 键（texts/scores/boxes/layout/lines/avg_score/low_score_lines）；其余原样。
- `DERIVED`：派生键清单，落盘剥掉、渲染补回。

调用点：
- `runner.extract_one`：提取后 `hydrate(rec)`（供 boxes_png 绘制 + 日志 + 返回给 app），落盘写 `disk_view(rec)` 紧凑。
- `builder.build`：开头对每条 record `hydrate`（磁盘 slim parsing → 渲染视图）。
- `cards.json_section`：展示 `disk_view(rec)`（pretty），**与下载的 result.json 内容一致**。

报告层 `cards.py` 的文字/文档/回溯逻辑**零改动**——它读的 `texts/boxes/layout` 由 hydrate 在渲染前补齐，与清理前完全一致（§0 逐元素相等验证）。

---

## 5. 验证清单（2026-11-19 全部通过）

- [x] 四路线重跑：108(off, column_lines=496) / 107(on) / 21(文本层) / CSV，行数/表数与清理前一致（226/1、58/1、53/2、0/1）。
- [x] **hydrate 派生投影 == 清理前存储投影**（texts/scores/boxes/layout/lines/avg_score/low_score_lines 逐元素相等，三 case True）。
- [x] 新 result.json：ppstruct 无 DERIVED 键、无 raw tables、parsing 无 input_path/table_ocr_pred/rec_polys/rec_boxes/layout_det_res。
- [x] 报告渲染：108 文字 226 行/226 框、107 文档 tab 2 个标题（mdhead）、21 两表、CSV 无图。
- [x] 交互回溯：108 悬停文字行→框高亮、单元格点击→钉住；107 切矫正图→mdline 点击钉住+框高亮、双「隐藏叠加框」同步。
- [x] JSON tab == 下载（均 disk_view 形态：有 parsing、无 texts/raw）；控制台无报错。
- [x] 体量：108 -88.5% / 107 -86.7% / 21 -75.7% / CSV -49.8%。

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

> 历史 case 的旧格式 result.json 仍在 output/ 下（未删，供对比）；新上传/重跑一律产出清理后格式。旧格式文件若用新 builder 渲染，hydrate 会因 parsing 含死字段而正常派生（投影键已存在则被覆盖为同源值），但建议重跑以享受瘦身。