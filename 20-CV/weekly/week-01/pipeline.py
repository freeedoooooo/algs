"""
第1周 · 周末任务：把 PDF/图片 → 结构化文本 串成一个小 pipeline。

这是你第一个"能拿出手的小工具"。本文件给了骨架，标了 TODO 的地方自己动手补全。
（这属于"用工具"范畴，不是深度学习核心，所以给骨架让你专注串联逻辑。）

用法：
    python pipeline.py input.pdf
"""
import sys
import json
import pdfplumber
import fitz
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='ch')


def ocr_image(path):
    """对单张图片跑 OCR，返回识别到的文字列表。"""
    result = ocr.ocr(path, cls=True)
    return [line[1][0] for line in (result[0] or [])]


def pdf_pages_to_images(pdf_path, dpi=200):
    """把 PDF 每页转成图片，返回图片路径列表。"""
    doc = fitz.open(pdf_path)
    paths = []
    for i, page in enumerate(doc):
        out = f"_tmp_page_{i}.png"
        page.get_pixmap(dpi=dpi).save(out)
        paths.append(out)
    return paths


def run(pdf_path):
    # TODO 1: 用 pdfplumber 判断有没有文本层（参考 pdf_extract.py 的 has_text_layer）
    #         有 → 直接 extract_text 抽字，返回结果
    #         无 → 转图片（pdf_pages_to_images），逐页 ocr_image，汇总文字
    raise NotImplementedError("把 pdf_extract.py 和 ocr_image.py 的逻辑串起来")

    # TODO 2: 把结果存成 json（{"source": pdf_path, "text": ...}）写到 output.json
    # TODO 3: （进阶）遇到表格区域时调用 table_ocr.py 的逻辑


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python pipeline.py input.pdf")
        sys.exit(1)
    text = run(sys.argv[1])
    print(text)
