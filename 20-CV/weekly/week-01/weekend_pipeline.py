"""
第1周 · 周末任务：把 PDF/图片 → 结构化文本 串成一个小 pipeline。

这是你第一个"能拿出手的小工具"。本文件给了骨架，标了 TODO 的地方自己动手补全。
（这属于"用工具"范畴，不是深度学习核心，所以给骨架让你专注串联逻辑。）

用法：
    python weekend_pipeline.py input.pdf
"""
import sys
import os
import json
import pdfplumber
import pymupdf                     # PyMuPDF 新导入名（`import fitz` 已弃用）
from paddleocr import PaddleOCR

# 默认输入：不带参数直接跑这张
DEFAULT_PDF = os.path.join('input', 'test3.pdf')

# PaddleOCR 3.x：显式指定模型（免联网下载 v6）
# 用移动端模型：server 大模型在 CPU 上极慢（实测单张 104s vs mobile 3.8s）
ocr = PaddleOCR(
    text_detection_model_name='PP-OCRv4_mobile_det',
    text_recognition_model_name='PP-OCRv4_mobile_rec',
    use_textline_orientation=True,   # 替代已废弃的 use_angle_cls
    lang='ch',
)


def ocr_image(path):
    """对单张图片跑 OCR，返回识别到的文字列表。"""
    # 3.x 用 predict()，返回 list[OCRResult]（dict 结构）
    result = ocr.predict(path)
    return [t for res in result for t in res['rec_texts']]


def pdf_pages_to_images(pdf_path, dpi=200, out_dir="output"):
    """把 PDF 每页转成图片，返回图片路径列表。产物统一放 output/。"""
    os.makedirs(out_dir, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    paths = []
    try:
        for i, page in enumerate(doc):
            out = os.path.join(out_dir, f"_tmp_page_{i}.png")
            page.get_pixmap(dpi=dpi).save(out)
            paths.append(out)
    finally:
        doc.close()
    return paths


def run(pdf_path):
    # TODO 1: 用 pdfplumber 判断有没有文本层（参考 c_pdf_text_layer.py 的 has_text_layer）
    #         有 → 直接 extract_text 抽字，返回结果
    #         无 → 转图片（pdf_pages_to_images），逐页 ocr_image，汇总文字
    raise NotImplementedError("把 c_pdf_text_layer.py 和 b_ocr_image.py 的逻辑串起来")

    # TODO 2: 把结果存成 json（{"source": pdf_path, "text": ...}）写到 output/output.json
    # TODO 3: （进阶）遇到表格区域时调用 d_table_ocr.py 的逻辑


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF
    if not os.path.exists(pdf_path):
        sys.exit(f"找不到 PDF：{os.path.abspath(pdf_path)}（默认找 input/test3.pdf）")
    text = run(pdf_path)
    print(text)
