# 第 1 周笔记（P0 · 环境 + PaddleOCR）

> 边学边记。卡住的点、试出来的经验、对 OCR 的新认识，都写这里。
>
> 📌 2026-11-02 的问答与实测已完整整理到 → [学习记录-2026-11-02.md](学习记录-2026-11-02.md)
> （含：本机环境与版本锁定、paddle/paddlex/paddleocr 三层架构、性能对比、
> 3.x API 的 4 个坑、PDF 的 MediaBox/CropBox 专题、bad case 素材）
> 📌 2026-11-09 补：`weekend_pipeline.py` 三个 TODO 已完成，并补了面向初学者的详细注释。

## 我跑通了什么
- ✅ 环境：miniforge 环境名 `paddle`（`conda activate paddle`），Python 3.10.9，`requirements.txt` 全锁版本
- ✅ `b_ocr_image.py`：test2.jpg 识别 20 行，置信度 0.88~1.00（换 mobile 模型后 5.8~12.4s）
- ✅ `c_pdf_text_layer.py`：test3.pdf 0.34s 抽出 2054 字符；转图分支可用
- ✅ `d_table_ocr.py`：test2.jpg → 4 个内容块 + 表格 HTML（乱码已修）
- ✅ `weekend_pipeline.py`：三个 TODO 补全；默认 `test3.pdf` 跑通 →
  `mode=text_layer`、1 页、2054 字符、0.53s，输出 `output/output.json` + `pipeline_result.txt`
- ⬜ `test3_image.pdf`（5 页扫描件）的 OCR 分支还没在 pipeline 里实跑
- ⬜ `b`、`d` 还没改成 `main()` + 主程序守卫
- ⬜ 3B1B 第 1 集：笔记里没记录，需自评

## bad case 观察（同步记到 ../week-02/bad_cases/notes.md）
- `test1.jpg`：深色背景终端截图（亮字暗底）→ 第1周当时用默认模型实测识别全乱码、置信度约 0.2。猜测：训练数据几乎都是暗字亮底。可试反色预处理。
  - 2026-11-12 复测（week-02 `a_batch_ocr.py`，v4 mobile + 文本行方向分类）：识别出 6 行、平均置信度 0.90。与第1周结论不同，说明**模型与预处理开关会显著改变结果**；这条样本仍值得收进 bad case 库，但归因笔记要写成两次实测的对比，而不是「必然失败」。
- `test3.pdf` 的 CropBox 裁剪：同一文件 4 种工具读出 143 / 144 / 145 / 2054 四种结果，差异来自「读内容流」还是「读可见区」。
- 有文本层却走 OCR：只拿到约 8% 内容，且 `15:47` 被认成 `15：47`（半角→全角）；密集小字整行漏检。

## 卡住的点 & 怎么解决的
- **首次跑 b 像卡死**：3.7.0 默认模型变成 `PP-OCRv6_medium`，本地缓存没命中 → 从 HuggingFace 下载卡住。改为显式指定已缓存的 `PP-OCRv4_mobile_*`，并设 `PADDLE_PDX_MODEL_SOURCE=BOS`。
- **一张图要 121s**：加分段耗时日志后定位到「CPU 上跑 server 大模型」（加载 17.3s + 推理 103.8s）。换 mobile 后 5.8~12.4s。
- **API 全报错**：3.x 把 `use_angle_cls` / `.ocr(cls=True)` / `PPStructure` / `import fitz` 全换了，逐项改成 `use_textline_orientation` / `.predict()` / `PPStructureV3` / `import pymupdf`。
- **表格模型下载断线**：365MB 的 `SLANeXt_wired` 从 BOS 断线后回退 HF；用 curl 断点续传下 tar，解压到 `~/.paddlex/official_models/`。
- **HTML 打开是中文乱码**：paddlex `save_to_html()` 输出 UTF-8 但没有 `<meta charset>`，浏览器按 GBK 解码 → 补完整 HTML 骨架 + charset。
- **结果取不到**：`PPStructureV3` 的结果多一层，要 `res.json['res']['parsing_res_list']`。

## 对"OCR = 检测 + 识别"的初步理解
- 检测（det）回答「字在哪」→ `rec_polys` 四点框；识别（rec）回答「是什么字」→ `rec_texts` + `rec_scores`。两步是两个独立模型，串起来才是一行结果，所以「漏检」和「认错」是两类不同的失败。
- 表格不是普通 OCR 能做的：还要版面检测 + 表格分类 + 结构识别 + 单元格检测，所以走 `PPStructureV3` 多模型产线，慢得多。
- OCR 是「像素 → 文字」的有损重建；PDF 有文本层时直接抽字又快又准，所以工程上先分流再决定要不要动用模型。

## 疑问（留着后面阶段解答）
- 为什么亮字暗底会几乎全军覆没？检测阶段到底在看什么特征？（week-02 反色实验 / P4）
- 调低 `text_det_thresh` 为什么能救漏检，又为什么会带来误检？DBNet 的概率图是什么？（week-02 Day3 感受，P4 深入）
- 同一个 PDF 的「全部内容流」和「肉眼可见区」，业务上该取哪个？`weekend_pipeline` 目前取前者并打了 `cropbox_limited` 标记。
