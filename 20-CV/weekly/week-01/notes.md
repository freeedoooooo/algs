# 第 1 周笔记（P0 · 环境 + PaddleOCR）

> 边学边记。卡住的点、试出来的经验、对 OCR 的新认识，都写这里。
>
> 📌 2026-11-02 的问答与实测已完整整理到 → [学习记录-2026-11-02.md](学习记录-2026-11-02.md)
> （含：本机环境与版本锁定、paddle/paddlex/paddleocr 三层架构、性能对比、
> 3.x API 的 4 个坑、PDF 的 MediaBox/CropBox 专题、bad case 素材）

## 我跑通了什么
- ✅ `b_ocr_image.py`：test2.jpg 识别 20 行，置信度 0.88~1.00（换 mobile 模型后 5.8~12.4s）
- ✅ `c_pdf_text_layer.py`：test3.pdf 0.34s 抽出 2054 字符；转图分支可用
- ✅ `d_table_ocr.py`：test2.jpg → 4 个内容块 + 表格 HTML（乱码已修）
- ⬜ `weekend_pipeline.py`：骨架已修正，TODO 待补

## bad case 观察（同步记到 ../week-02/bad_cases/notes.md）
- 

## 卡住的点 & 怎么解决的
- 

## 对"OCR = 检测 + 识别"的初步理解
- 

## 疑问（留着后面阶段解答）
- 
