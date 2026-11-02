"""
第1周 · 模块C：PDF 文本层判断 + 扫描件转图（可直接运行）

核心思想（工程思维）：能直接抽字的 PDF 根本不用 OCR。先判断，省一大半事。

用法：
    python pdf_extract.py your.pdf
"""
import sys
import pdfplumber
import fitz  # PyMuPDF


def has_text_layer(pdf_path, sample_pages=3):
    """前几页能抽到足够文字 = 有文本层，不用 OCR。"""
    with pdfplumber.open(pdf_path) as pdf:
        text = "".join((p.extract_text() or "") for p in pdf.pages[:sample_pages])
    return len(text.strip()) > 50, text[:200]


def extract_text(pdf_path):
    """有文本层：直接抽全文。"""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def pdf_to_images(pdf_path, dpi=200, out_prefix="page"):
    """扫描件：每页转成图片，再走 PaddleOCR（见 ocr_image.py）。"""
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)      # dpi 越高越清晰但越慢
        out = f"{out_prefix}_{i}.png"
        pix.save(out)
        print(f"已保存 {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python pdf_extract.py your.pdf")
        sys.exit(1)

    path = sys.argv[1]
    ok, preview = has_text_layer(path)
    if ok:
        print("✅ 有文本层，直接抽字即可（不用 OCR）")
        print("预览：", preview)
        # print(extract_text(path))   # 需要全文时取消注释
    else:
        print("⚠️ 扫描件/图片型，需要 OCR → 正在转图片")
        pdf_to_images(path)
        print("转好了，对每张 page_*.png 跑 ocr_image.py 即可")
