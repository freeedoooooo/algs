"""
第1周 · 周末任务：把 PDF/图片 → 结构化文本 串成一个小 pipeline。

三个 TODO 已补全：
    TODO 1 判断有无文本层 → 有则 pdfplumber 直接抽字，无则转图逐页 OCR
    TODO 2 结果写成 output/output.json（另存一份纯文本方便看全文）
    TODO 3 进阶表格识别：文本层用 pdfplumber，扫描件用 PP-StructureV3

run(pdf_path) 返回一个 dict（mode / text / pages / elapsed / tables ...），
同时把结果落盘。main() 只负责取路径、打印摘要和预览。

用法：
    python weekend_pipeline.py                  # 用配置区 INPUT_PDF 指定的文件
    python weekend_pipeline.py input/你的.pdf     # 命令行临时指定（优先级高于 INPUT_PDF）

调试要改的路径都在文件顶部的【配置区】，不用往下翻代码。
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_PDF = 'input/test3_image.pdf'                   # 输入 PDF
OUT_DIR = 'output'                              # 产物目录（转出的中间图、最终结果）
OUT_JSON = 'output/output.json'                 # 结构化结果（含模式、页数、耗时、表格）
OUT_TXT = 'output/pipeline_result.txt'          # 纯文本结果，方便直接打开看全文
DPI = 200                                       # 转图清晰度
MIN_CHARS = 50                                  # 前几页抽到超过这么多字 → 判定「有文本层」
SAMPLE_PAGES = 3                                # 只检查前几页，避免大 PDF 判断太慢
ENABLE_TABLE = True                             # 表格识别开关（OCR 分支每页约 +20s，嫌慢改 False）
# ==========================================================================

import sys
import os
import json
import re
import time

# 必须在任何 paddleocr / paddlex import 之前设置（见 d_table_ocr.py 的说明）
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

import pdfplumber
import pymupdf                     # PyMuPDF 新导入名（`import fitz` 已弃用）

# 两个重量级模型都改成懒加载：走文本层分支时完全不碰 paddle，启动秒开
_ocr = None
_table_engine = None


def get_ocr():
    """首次调用时才加载 PaddleOCR，之后同进程复用。"""
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        t0 = time.perf_counter()
        _ocr = PaddleOCR(
            text_detection_model_name='PP-OCRv4_mobile_det',
            text_recognition_model_name='PP-OCRv4_mobile_rec',
            use_textline_orientation=True,   # 替代已废弃的 use_angle_cls
            lang='ch',
        )
        print(f'>> OCR 模型加载耗时 {time.perf_counter() - t0:.2f}s')
    return _ocr


def get_table_engine():
    """首次调用时才加载 PP-StructureV3（表格识别流水线）。"""
    global _table_engine
    if _table_engine is None:
        from paddleocr import PPStructureV3
        t0 = time.perf_counter()
        _table_engine = PPStructureV3(
            use_formula_recognition=False,   # 关掉不需要的子模型，少下载、少耗时
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_region_detection=False,
            use_table_recognition=True,
            text_detection_model_name='PP-OCRv4_mobile_det',
            text_recognition_model_name='PP-OCRv4_mobile_rec',
        )
        print(f'>> 表格流水线加载耗时 {time.perf_counter() - t0:.2f}s')
    return _table_engine


def ocr_image(path):
    """对单张图片跑 OCR，返回识别到的文字列表。"""
    # 3.x 用 predict()，返回 list[OCRResult]（dict 结构）
    result = get_ocr().predict(path)
    return [t for res in result for t in res['rec_texts']]


def pdf_pages_to_images(pdf_path, dpi=DPI, out_dir=OUT_DIR):
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


# ---------------------------------------------------------------- TODO 1 --
def has_text_layer(pdf_path):
    """前 SAMPLE_PAGES 页能抽到足够文字 = 有文本层。返回 (bool, 总页数)。"""
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)
        sample = ''.join((p.extract_text() or '') for p in pdf.pages[:SAMPLE_PAGES])
    return len(sample.strip()) > MIN_CHARS, pages


def extract_text_layer(pdf_path):
    """有文本层：逐页抽取全文。读的是全部内容流，不受 CropBox 限制。"""
    with pdfplumber.open(pdf_path) as pdf:
        return '\n'.join((p.extract_text() or '') for p in pdf.pages)


def cropbox_is_limited(pdf_path):
    """CropBox 是否比 MediaBox 小（学习记录 6.3 的「裁剪陷阱」）。"""
    doc = pymupdf.open(pdf_path)
    try:
        return any(page.cropbox != page.mediabox for page in doc)
    finally:
        doc.close()


# ---------------------------------------------------------------- TODO 3 --
def extract_tables_text_layer(pdf_path):
    """有文本层时直接用 pdfplumber 抽表格，快且不需要模型。"""
    found = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                tables = page.extract_tables() or []
            except Exception as e:
                print(f'>> 第 {i + 1} 页表格抽取失败，已跳过：{e}')
                continue
            for table in tables:
                found.append({'page': i, 'source': 'pdfplumber', 'rows': table})
    return found


def ensure_readable_html(path):
    """给 paddlex save_to_html 的片段补 <meta charset="utf-8">，否则中文乱码。"""
    with open(path, encoding='utf-8') as f:
        frag = f.read()
    if re.search(r'<meta[^>]+charset', frag, flags=re.I):
        return
    inner = re.sub(r'^\s*<html[^>]*>|</html>\s*$', '', frag, flags=re.I)
    inner = re.sub(r'^\s*<body[^>]*>|</body>\s*$', '', inner, flags=re.I)
    doc = (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '  <meta charset="utf-8">\n  <title>表格识别结果</title>\n'
        '  <style>body{font-family:"Microsoft YaHei",sans-serif;margin:24px}'
        'table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #999;padding:6px 10px}</style>\n'
        '</head>\n<body>\n' + inner + '\n</body>\n</html>\n'
    )
    with open(path, 'w', encoding='utf-8') as f:
        f.write(doc)


def table_ocr_page(image_path, page_index):
    """
    对一页图跑 PP-StructureV3，挑出表格内容块并导出 HTML。

    注意：不能直接 `import d_table_ocr` —— 那个文件是脚本式写法，
    输入检查和推理都在模块顶层，import 会立刻把整份表格识别跑一遍。
    所以这里复用它的参数和 3.x API，在本文件内重新实现一遍。
    """
    result = get_table_engine().predict(image_path)
    blocks = []
    for res in result:
        data = res.json if hasattr(res, 'json') else res
        # 3.x 的 res.json 是 {'res': {...}} 嵌套结构，真正字段在里面
        if isinstance(data, dict) and isinstance(data.get('res'), dict):
            data = data['res']
        if isinstance(data, dict):
            for b in data.get('parsing_res_list', []):
                blocks.append({
                    'label': b.get('block_label', '?'),
                    'content': str(b.get('block_content', '')),
                })
    tables = [b for b in blocks if 'table' in b['label'].lower()]
    html_path = None
    if tables and result:
        html_path = os.path.join(OUT_DIR, f'pipeline_table_p{page_index}.html')
        result[0].save_to_html(html_path)
        ensure_readable_html(html_path)
    return {
        'page': page_index,
        'source': 'PPStructureV3',
        'table_count': len(tables),
        'blocks': tables,
        'html': html_path,
    }


# ---------------------------------------------------------------- TODO 2 --
def save_result(result):
    """结构化结果写 OUT_JSON，纯文本另存一份方便直接看。"""
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if OUT_TXT:
        with open(OUT_TXT, 'w', encoding='utf-8') as f:
            f.write(result['text'])
    return OUT_JSON


def run(pdf_path):
    """PDF → 结构化 dict；同时把结果落盘到 OUT_JSON / OUT_TXT。"""
    t0 = time.perf_counter()
    limited = cropbox_is_limited(pdf_path)
    ok, pages = has_text_layer(pdf_path)
    tables = []

    if ok:
        # TODO 1：有文本层 → 直接抽字，不碰 OCR（又快又准）
        print('>> 有文本层 → 直接抽字（跳过 OCR）')
        text = extract_text_layer(pdf_path)
        mode, scope = 'text_layer', 'all_content_stream'
        if limited:
            print('>> 注意：该 PDF 有 CropBox 裁剪，抽到的是全部内容流，'
                  '可能包含打开时看不到的文字')
        # TODO 3：文本层分支用 pdfplumber 抽表格，不需要模型
        if ENABLE_TABLE:
            tables = extract_tables_text_layer(pdf_path)
            print(f'>> 表格抽取：{len(tables)} 个表格（pdfplumber）')
    else:
        # TODO 1：无文本层 → 转图，逐页 OCR 后汇总
        print('>> 无文本层（扫描件）→ 转图后逐页 OCR')
        images = pdf_pages_to_images(pdf_path)
        chunks = []
        for i, img in enumerate(images):
            t1 = time.perf_counter()
            lines = ocr_image(img)
            chunks.append(f'--- 第 {i + 1} 页 ---')
            chunks.extend(lines)
            print(f'>> 第 {i + 1}/{len(images)} 页 OCR 完成：{len(lines)} 行，'
                  f'{time.perf_counter() - t1:.2f}s')
            # TODO 3：扫描件分支用 PP-StructureV3 还原表格结构
            if ENABLE_TABLE:
                info = table_ocr_page(img, i)
                tables.append(info)
                print(f'   表格识别：{info["table_count"]} 个表格块'
                      + (f'，HTML → {info["html"]}' if info['html'] else ''))
        text = '\n'.join(chunks)
        mode, scope = 'ocr', 'visible_cropbox'

    result = {
        'source': pdf_path,
        'mode': mode,
        'text': text,
        'chars': len(text),
        'pages': pages,
        'text_scope': scope,
        'cropbox_limited': limited,
        'elapsed': round(time.perf_counter() - t0, 2),
        'tables': tables,
    }

    # TODO 2：落盘（ensure_ascii=False 保证中文不变成 \uXXXX）
    out_json = save_result(result)
    print(f'>> 已保存 {out_json}（mode={mode}, {pages} 页, {len(text)} 字符, '
          f'{result["elapsed"]}s）')
    return result


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else INPUT_PDF
    if not os.path.exists(pdf_path):
        sys.exit(f"找不到 PDF：{os.path.abspath(pdf_path)}\n改文件顶部的 INPUT_PDF，或用命令行指定路径")
    result = run(pdf_path)
    print('>> 前 300 字预览：')
    print(result['text'][:300] or '(空)')
    if OUT_TXT:
        print(f'>> 全文见 {OUT_TXT}')


if __name__ == '__main__':
    main()
