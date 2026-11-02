"""
第1周 · 模块C：PDF 文本层判断 + 扫描件转图（可直接运行）

核心思想（工程思维）：能直接抽字的 PDF 根本不用 OCR。先判断，省一大半事。

用法（在 week-01 目录下）：
    python c_pdf_text_layer.py                    # 用配置区 INPUT_PDF 指定的文件
    python c_pdf_text_layer.py input/你的.pdf      # 命令行临时指定（优先级高于 INPUT_PDF）

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。

两个库的分工：
    pdfplumber → 判断/抽取 PDF 的【文本层】（有字就直接读，又快又准）
    pymupdf    → 把 PDF 每页【渲染成图片】（扫描件没文本层，转图后再走 b 的 OCR）

版本说明（pymupdf 1.24+）：
    官方已弃用 `import fitz`，改用 `import pymupdf`（本文件已改用新写法）。
    老写法在新版本会报 DeprecationWarning，未来会被移除。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_PDF = 'input/test3_image.pdf'         # 输入 PDF
OUT_DIR = 'output'                          # 产物目录（抽取的文本 / 转出的图片都放这里）
DPI = 200                                   # 转图清晰度：越高越清晰但越慢，OCR 用 200 够
MIN_CHARS = 50                              # 前几页抽到的字符数超过它 → 判定为"有文本层"
SAMPLE_PAGES = 3                            # 只检查前几页，避免大 PDF 判断太慢
# ==========================================================================

import os
import sys
import time

import pdfplumber
import pymupdf  # PyMuPDF 新导入名（不再用已弃用的 fitz）


def has_text_layer(pdf_path, sample_pages=SAMPLE_PAGES):
    """前几页能抽到足够文字 = 有文本层，不用 OCR。返回 (bool, 预览文本)。"""
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        text = ''.join((p.extract_text() or '') for p in pdf.pages[:sample_pages])
    return len(text.strip()) > MIN_CHARS, text[:200], page_count


def extract_text(pdf_path):
    """有文本层：直接抽全文（逐页拼接）。"""
    with pdfplumber.open(pdf_path) as pdf:
        return '\n'.join((p.extract_text() or '') for p in pdf.pages)


def pdf_to_images(pdf_path, dpi=DPI, out_dir=OUT_DIR):
    """扫描件：每页转成图片，再走 PaddleOCR（见 b_ocr_image.py）。产物统一放 output/。"""
    os.makedirs(out_dir, exist_ok=True)
    out_paths = []
    doc = pymupdf.open(pdf_path)          # 新 API：pymupdf.open 等价于老的 fitz.open
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)  # dpi 越高越清晰但越慢；200 够 OCR 用
            out = os.path.join(out_dir, f'c_page_{i}.png')
            pix.save(out)
            out_paths.append(out)
            print(f'已保存 {out}')
    finally:
        doc.close()
    return out_paths


def main():
    # ---- 0) 取路径：命令行指定 > 配置区 INPUT_PDF ----
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else INPUT_PDF

    if not os.path.exists(pdf_path):
        print(f'找不到 PDF：{os.path.abspath(pdf_path)}')
        # 顺手把 input/ 下可用的 PDF 列出来，省得你猜
        pdfs = [f for f in os.listdir('input') if f.lower().endswith('.pdf')] if os.path.isdir('input') else []
        if pdfs:
            print('input/ 下现有 PDF：')
            for f in pdfs:
                print(f'   python c_pdf_text_layer.py input/{f}')
        else:
            print('请把 PDF 放到 week-01/input/ 下，或改文件顶部的 INPUT_PDF。')
        sys.exit(1)

    print(f'>> 目标文件：{pdf_path}')

    # ---- 1) 判断有没有文本层 ----
    t0 = time.perf_counter()
    try:
        ok, preview, page_count = has_text_layer(pdf_path)
    except Exception as e:
        sys.exit(f'>> 打开 PDF 失败：{e}\n（文件可能损坏或加密，试试用阅读器另存一份再跑）')
    t1 = time.perf_counter()
    print(f'>> 共 {page_count} 页；文本层判断耗时：{t1 - t0:.2f}s')

    # ---- 2) 分流 ----
    if ok:
        print('>> 有文本层 → 直接抽字即可（不用 OCR，又快又准）')
        text = extract_text(pdf_path)
        t2 = time.perf_counter()

        # 产物落盘，符合"产物放 output/"的约定
        os.makedirs(OUT_DIR, exist_ok=True)
        stem = os.path.splitext(os.path.basename(pdf_path))[0]
        out_txt = os.path.join(OUT_DIR, f'c_{stem}_text.txt')
        with open(out_txt, 'w', encoding='utf-8') as f:
            f.write(text)

        print(f'>> 抽取耗时：{t2 - t1:.2f}s；共 {len(text)} 个字符')
        print(f'>> 全文已保存：{out_txt}')
        print('>> 前 200 字预览：')
        print(preview if preview.strip() else '(空)')
        print(f'>> 总耗时：{t2 - t0:.2f}s')
    else:
        print('>> 扫描件/图片型（无文本层）→ 需要 OCR，正在转图片…')
        imgs = pdf_to_images(pdf_path)
        t2 = time.perf_counter()
        print(f'>> 转图耗时：{t2 - t1:.2f}s；共生成 {len(imgs)} 张')
        print(f'>> 总耗时：{t2 - t0:.2f}s')
        print(f'>> 下一步：对 {OUT_DIR}/ 下每张 page_*.png 跑 b_ocr_image.py，例如')
        print(f'   python b_ocr_image.py {imgs[0]}' if imgs else '   （没有页面可转）')


if __name__ == '__main__':
    main()
