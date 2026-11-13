# 第 2 周笔记（P0 收尾 · 真实图片 + bad case 库）

## 我压测了哪些场景，效果如何

> 首轮基线由 `a_batch_ocr.py` 代跑：22 张样本，`PP-OCRv4_mobile_det/rec`，
> 关闭文档预处理，总 37.16s（含模型加载 2.62s）。
> 逐行结果见 `output/batch_ocr_results.json`，**看图对照见 `output/vis/index.html`**。
> 格式：`检出行数 / 平均置信度`。

> ⚠️ **下面这张表是 11-12 首轮基线的历史记录，用的是当时的旧编号**，数据如实保留、没有改写。
> 11-13 把输入重排成「01~18 合成样本 + `real_*` 真实 case」，旧名 → 新名对照：
>
> | 旧名 | 新名 |
> |---|---|
> | `17_heavy_blur.png` | `15_heavy_blur.png` |
> | `18_glare_wipe.png` | `16_glare_wipe.png` |
> | `19_dark_shadow.png` | `17_dark_shadow.png` |
> | `20_faint.png` | `18_faint.png` |
> | `15_real_terminal.jpg` | `real_terminal_screenshot.jpg` |
> | `16_real_doc.jpg` | `real_clear_doc.jpg` |
> | `21_real_scan_p1.jpg` | `real_scan_page1.jpg` |
> | `22_real_scan_p2.jpg` | `real_scan_page2.jpg` |
>
> 重跑后的新结果一律以 `output/batch_ocr_results.json` / `output/vis/index.html` 为准。

| 场景 | 代表样本 | 效果 | 备注 |
|---|---|---|---|
| 清晰印刷体（对照） | `01_clear.png` 12 / 0.99、`16_real_doc.jpg` 21 / 0.94 | 好 | 识别框与文字完全对齐，作为基准 |
| 模糊 / 低质 | `02_blur` 12 / 0.96、`03_lowres` 13 / **0.38**、`11_noise` 13 / 0.64、`17_heavy_blur` **4 / 0.07** | 轻度几乎无影响，降采样与重度模糊才崩 | `17` 应有 12 行只检出 4 行，是典型漏检 |
| 倾斜 / 透视 | `04_skew` 12 / 0.99、`05_perspective` 12 / 0.99、`13_rot180` 12 / 0.98 | 好 | 8° 倾斜、梯形透视、整页倒置都正常；`use_textline_orientation` 起作用了 |
| 反光 / 光照 | `06~08` 12 / 0.99、`18_glare_wipe` **8** / 0.95、`19_dark_shadow` 12 / 0.99、`20_faint` 12 / 0.99 | 全局变暗变淡不影响；局部过曝漏 4 行 | `19` / `20` 压到 10% 亮度、13% 对比度仍全对 |
| 密集小字 / 多栏 | `09_dense_small` 35 / 0.96（标准答案 28 行）、`22_real_scan_p2` 58 / 0.85 | 行数膨胀、部分低置信 | 疑似一行被拆成多块，需看带框图确认 |
| 手写（只观察） | `12_handwriting` 4 / 0.99 | 基本能认 | ⚠️ 用的是**行楷印刷字体，不是真手写**，样本不具代表性；建议自己手写一张拍照替换，本计划仍不攻手写 |
| 真实复杂文档 | `21_real_scan_p1` 76 / 0.60（35 行低置信）、`15_real_terminal` 4 / **0.17** | 最差 | 真实扫描件的噪点 + 印章 + 版面是复合退化，比任何单因素合成图都难 |

## 本次实测的三个关键观察

1. **模型对"全局"退化异常鲁棒，怕的是"信息被物理抹除"。**
   模糊 2.4、倾斜 8°、透视、倒置 180°、亮度压到 10%、对比度压到 13%，
   全都稳定在 0.96~0.99；真正让它崩的是降采样（细节永久丢失）、
   强反光过曝（文字像素洗成纯白）、重度模糊（笔画糊成色块）。
2. **置信度筛不出漏检。** `18_glare_wipe.png` 漏了 4 行，但留下的 8 行平均 0.95，
   只看 JSON 的 `avg_score` 会完全错过它。必须看带框图：**原图有字、没有框**才是漏检。
3. **坐标基准有个 3.7.0 的坑。** 默认的「整页方向分类 + UVDoc 去扭曲」会让
   `rec_polys` 基于矫正后的图像，画回原图整体错位（实测标题框 y=27~66，
   墨迹实际 y=66~98）。关闭后完全吻合。代价是 `15_real_terminal.jpg` 从
   6 行 / 0.90 掉到 4 行 / 0.17 —— 预处理对某些图确实有用。
   配置区 `USE_DOC_PREPROCESS` 可切换，取文字与取坐标是两种取舍。

## 调参数救回了哪个 bad case，调了什么
- （Day 3 自己填。建议拿 `18_glare_wipe.png` 或 `03_lowres.jpg` 跑 `c_try_params.py`，
  对比默认阈值 0.3/0.6 与调低后的 0.2/0.4，看是"救回漏检"还是"多了误检"。）
- 已知结果：`18_glare_wipe.png` 两组都是 8 行 / 0.95、**0 差异**。
  这不代表"没有漏检"，而是过曝区的文字像素已不存在，调阈值无能为力。
  这正是「参数不是万能的」的第一个实例，值得记下来。

## 看完 3B1B 4 集，我对"神经网络怎么学"的理解
- 

## P0 收尾自评（L1 会用达成了吗）
- 

## 11-13 · 输入重排 + 让文本层 PDF 进对比预览

**需求**：把 week-01 的样例搬进 week-02/input 并排在最后；所有真实 case 也排最后；
真实 case 统一 `real_` 前缀、名字一眼看懂、去掉重复；重跑结果；
再把第1周「有文本层 PDF 的表格直读」搬到第2周，好用对比预览看提取效果。

**输入整理**
- 18 张合成样本改成连续编号 `01~18`（原 17~20 → 15~18）。
- 真实 case 统一 `real_` 前缀：`real_terminal_screenshot.jpg`、`real_clear_doc.jpg`、
  `real_bank_statement_textlayer.pdf`、`real_certificates_scan.pdf`、
  `real_transactions_gbk.csv`、`real_scan_page1.jpg`、`real_scan_page2.jpg`。
  字母 r 的字典序在数字之后，`sorted()` 时天然全部排在最后。
- **去重**：MD5 核对发现两对字节级相同的副本（`test1.jpg` / `test2.jpg` 各存了两份），
  删掉副本只留正本（旧名都在 git 里，可恢复）。`real_scan_page1/2` 是 PDF 渲染页
  缩放出来的 JPEG，与 PDF 原件内容不同，保留为独立的扫描 bad case。
- `make_samples.py` 把原来三段清单合并成一张 `REAL_CASES`（copy / scan 两种来源），
  重跑不会再生成重复文件；manifest 新增 `group` 字段区分合成 / 真实。

**文本层 PDF 接入**（新模块 `text_layer_extract.py`）
- 移植第1周的策略回退：线型诊断 → `TABLE_STRATEGIES` → 人工列边界模板 → 清洗 + 填充率。
  `real_bank_statement_textlayer.pdf` 配 9 条竖线，抽出 105×8、8 列表头正确。
- `a_batch_ocr.py` 按后缀分三路：图片 OCR / PDF 首页渲染成图后 OCR + 文本层直读 /
  CSV 纯文本解析（不跑模型）。PDF 渲染必须 `set_cropbox(mediabox)`，否则只出
  910×218 的顶部一条（整页 910×1287）—— 第1周裁剪陷阱的又一次体现。
- `vis_ocr_result.py` 每张 PDF/CSV 卡片下方新增「直读结果」区：抽出的表格、
  策略 / 行列数 / 填充率、抽取诊断、CSV 原文；顶部汇总加「直读表格」「真实 case」统计。
  表格按原始抽取顺序平铺，**不假设第 1 行是表头**（这文件第 1 行其实是页眉）。

**验证**（不加载模型）：5 个脚本 `py_compile` 通过；`extract_case()` 对两个 PDF + 一个
CSV 结果正确；构造 3 类 record 生成报告，10 项 HTML 检查全通过。完整批量重跑结果见
`output/batch_ocr_results.json` 与 `output/vis/index.html`。
