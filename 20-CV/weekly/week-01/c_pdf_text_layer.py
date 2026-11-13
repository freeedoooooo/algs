"""
第1周 · 模块C：PDF 文本层判断 + 扫描件转图（可直接运行）

核心思想（工程思维）：能直接抽字的 PDF 根本不用 OCR。先判断，省一大半事。

用法（在 week-01 目录下）：
    conda activate paddle
    python c_pdf_text_layer.py                    # 用配置区 INPUT_PDF 指定的文件
    python c_pdf_text_layer.py input/你的.pdf      # 命令行临时指定（优先级高于 INPUT_PDF）

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。

【产物】两层隔离 + 中间产物单独一层：
    output/c_pdf_text_layer/<输入文件名去后缀>/
        <文件名>_text.txt    有文本层时抽出的全文
        pages/               无文本层时转出的页图（中间产物，单独放，不混在结果里）
            c_page_0.png …
换一个 PDF 跑，结果自动进另一个目录，不会覆盖上一次的。

两个库的分工：
    pdfplumber → 判断/抽取 PDF 的【文本层】（有字就直接读，又快又准）
    pymupdf    → 把 PDF 每页【渲染成图片】（扫描件没文本层，转图后再走 b 的 OCR）

版本说明（pymupdf 1.24+）：
    官方已弃用 `import fitz`，改用 `import pymupdf`（本文件已改用新写法）。
    老写法在新版本会报 DeprecationWarning，未来会被移除。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_PDF = 'input/test3_image.pdf'         # 输入 PDF
# ↓ 产物隔离规则：output/<脚本名>/<输入文件名>/
#   OUT_DIR 是本脚本专属目录，和 b / d / weekend_pipeline 的产物互不干扰；
#   PAGES_SUBDIR 是「转出的页图」单独待的子目录，避免中间产物和正式结果混在一起。
OUT_DIR = 'output/c_pdf_text_layer'         # 本脚本的产物总目录
PAGES_SUBDIR = 'pages'                      # 页图（中间产物）的子目录名
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
    """
    前几页能抽到足够文字 = 有文本层，不用 OCR。

    返回三个值（元组）：(是否有文本层, 前 200 字预览, 总页数)。
    调用处写 ok, preview, page_count = has_text_layer(...) 分别接住。
    """
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        text = ''.join((p.extract_text() or '') for p in pdf.pages[:sample_pages])
    return len(text.strip()) > MIN_CHARS, text[:200], page_count


def extract_text(pdf_path):
    """
    有文本层：直接抽全文（逐页拼接）。

    顺便返回每页的字符数列表，让「为什么判成有/无文本层」看得见：
    如果某几页是 0、另一些页很多字，就是混合型 PDF（部分页有文本层、
    部分是扫描图），整份文件给一个结论会漏字。
    """
    with pdfplumber.open(pdf_path) as pdf:
        parts = [(p.extract_text() or '') for p in pdf.pages]
    return '\n'.join(parts), [len(s.strip()) for s in parts]


def show(path):
    """日志专用：把 Windows 的反斜杠显示成 /，实际读写路径不变。"""
    return str(path).replace(os.sep, '/') if path else path


def case_dir(input_path):
    """
    按输入文件名算出专属产物目录：OUT_DIR/<输入文件名去后缀>/。

    os.path.basename 去掉前面的目录只留文件名，splitext 再去掉后缀。
    这样 test3.pdf 和 test3_image.pdf 的结果各进各的目录，不会互相覆盖。
    """
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(OUT_DIR, stem)


def pdf_to_images(pdf_path, dpi=None, out_dir=None):
    """
    扫描件：每页转成图片，再走 PaddleOCR（见 b_ocr_image.py）。

    注意默认参数写成 None、进函数再读配置区，而不是直接写 `dpi=DPI, out_dir=OUT_DIR`：
    Python 的默认参数值在「函数定义那一刻」就被算好并固定，之后就算改了配置区
    （或在别的文件里 import 后改），也不会生效。写成 None 才是运行时读配置。

    main() 会传入 <case 目录>/pages/，让页图这类中间产物单独待一层，
    不和抽取的文本混在一起。
    """
    dpi = DPI if dpi is None else dpi
    out_dir = OUT_DIR if out_dir is None else out_dir
    os.makedirs(out_dir, exist_ok=True)
    out_paths = []
    doc = pymupdf.open(pdf_path)          # 新 API：pymupdf.open 等价于老的 fitz.open
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)  # dpi 越高越清晰但越慢；200 够 OCR 用
            out = os.path.join(out_dir, f'c_page_{i}.png')
            pix.save(out)
            out_paths.append(out)
            print(f'已保存 {show(out)}')
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

    # ---- 0.5) 产物目录：脚本名 + 输入文件名两层隔离 ----
    case_out = case_dir(pdf_path)
    pages_dir = os.path.join(case_out, PAGES_SUBDIR)   # 转出的页图单独放这一层
    os.makedirs(case_out, exist_ok=True)
    print(f'>> 产物目录：{show(case_out)}')

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
        text, per_page = extract_text(pdf_path)
        t2 = time.perf_counter()

        # 打印每页字符数：一眼看出判断依据，也能发现「部分页是扫描图」的混合型 PDF
        head = per_page[:8]
        tail = ' …' if len(per_page) > 8 else ''
        print(f'>> 逐页字符数：{head}{tail}（共 {len(per_page)} 页，阈值 {MIN_CHARS}）')
        if per_page and min(per_page) < MIN_CHARS // 10 < max(per_page):
            print('>> 注意：各页字数差异很大，可能是混合型 PDF（有的页是扫描图）。'
                  '本脚本按整份文件只给一个结论，这些页的文字会被漏掉。')

        # 抽出的全文放进这个 case 自己的目录，不堆在 output/ 根目录
        stem = os.path.splitext(os.path.basename(pdf_path))[0]
        out_txt = os.path.join(case_out, f'{stem}_text.txt')
        with open(out_txt, 'w', encoding='utf-8') as f:
            f.write(text)

        print(f'>> 抽取耗时：{t2 - t1:.2f}s；共 {len(text)} 个字符')
        print(f'>> 全文已保存：{show(out_txt)}')
        print('>> 前 200 字预览：')
        # 预览里的换行会刷屏并打乱日志，先压成空格
        print(' '.join(preview.split()) if preview.strip() else '(空)')
        print(f'>> 总耗时：{t2 - t0:.2f}s')
    else:
        print('>> 扫描件/图片型（无文本层）→ 需要 OCR，正在转图片…')
        imgs = pdf_to_images(pdf_path, out_dir=pages_dir)
        t2 = time.perf_counter()
        print(f'>> 转图耗时：{t2 - t1:.2f}s；共生成 {len(imgs)} 张')
        print(f'>> 总耗时：{t2 - t0:.2f}s')
        print(f'>> 页图（中间产物）单独放在：{show(pages_dir)}')
        print(f'>> 下一步：对 {show(pages_dir)}/ 下每张 c_page_*.png 跑 b_ocr_image.py，例如')
        print(f'   python b_ocr_image.py {show(imgs[0])}' if imgs else '   （没有页面可转）')


if __name__ == '__main__':
    main()
