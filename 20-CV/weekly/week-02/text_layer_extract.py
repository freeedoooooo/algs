"""
第2周 · 有文本层 PDF / CSV 的「直读」提取（不加载 OCR 模型）

【谁在调用我 / 怎么单独测】（11-13 补）
两条路都能用，区别在「要测什么」：
    ① 正式跑批：a_batch_ocr.py 的 build_case_record() 遇到 PDF / CSV 分支时
       调用 extract_case(path, pages_dir=<case 目录>/pages/)，
       返回的 dict 被写进该 case 的 result.json，再和 OCR 结果一起进对比报告。
    ② 单独调试：直接 `python text_layer_extract.py`（见文件末尾 main()），
       不加载 OCR 模型、不写正式产物，只把直读结果打印到终端。
       **只想验证 103 的表格抽得对不对，用这条最轻**，毫秒级、不用跑全量。
两条路页图落点不同：① 在 <case 目录>/pages/，② 在
output/text_layer_extract/pages/（按脚本名隔离，不混进正式产物）。
我自己还 import 了 case_naming，用它的 strip_no() 匹配人工列边界模板。

【为什么单独一个模块】
第1周 weekend_pipeline.py 验证过：PDF 只要有文本层，字符本身就是精确的，
不需要转图让 OCR 再猜一遍。这里把那套「诊断线型 → 策略回退 → 质量打分」
的逻辑搬到第2周，目的只有一个 —— 让 a_batch_ocr.py 的对比预览里能同时看到：

    左图：把 PDF 首页当图片喂给 OCR，识别框套在哪（像素路线）
    右下：直接读文本层抽出来的表格，行列完整、无识别误差（文本层路线）

两者并排，一眼看出两条路线的差距。这正是「对比预览」想表达的东西。

【与第1周的关系】
策略与常量移植自 week-01/weekend_pipeline.py。两份各自独立维护，互不 import，
避免第1周的教学脚手架被第2周改动牵连。
人工列边界模板按「去掉数字编号后的语义名」匹配（见 case_naming.strip_no），
所以给真实 case 换编号（103 → 108）不会让模板失效。

【产物】
    ① 被 a 调用：<case 目录>/pages/p1.png + 返回 dict → 写进该 case 的 result.json
    ② 单独调试：output/text_layer_extract/pages/p1.png + 终端摘要
    本模块自己不写 result.json、不画识别框、不生成 HTML 报告 ——
    那些是 a_batch_ocr.py / vis_ocr_result.py 的职责。

【坑位记录（第1周实测）】
- paddlex 的 save_to_html() 遇空表格会 IndexError → 这里根本不用它，自己写 HTML。
- pdfplumber 默认 / lines 策略靠竖线切列；只有横线的流水表会静默返回 0 张表。
- pymupdf 默认按 CropBox 渲染；被裁剪过的 PDF 要用 set_cropbox(mediabox)
  才能看到整页（test3.pdf 默认只有 910×218，整页是 910×1287）。
- 【11-13 新增】显式列边界必须配 horizontal_strategy='lines' 一起用。只用
  'text' 会把「单元格内换行」当成新表格行，103 从 24 笔交易膨胀成 105 行碎表。
  判断标准看填充率：碎表 0.293，按横线切的真表 0.74。

【我负责到哪一步】
本模块只负责「把字符和表格抽出来」并返回一个 dict。把抽出来的表格整理成
带表头的结构、导出 CSV、在报告里作为主结果展示，是 table_extract.py 和
vis_ocr_result.py 的事 —— 我不写文件、不加载模型、不画 HTML。
"""

# =========================== 配置区：调试只改这里 ===========================
PDF_RENDER_DPI = 110                             # PDF 首页预览图分辨率，够看清即可，别太大
# 只有单独调试本模块（不传 pages_dir）时才用这个默认值；正常由 a_batch_ocr.py
# 传入 <case 目录>/pages/，让每个输入的中间产物各自隔离。
# ★ 这里刻意放在本模块专属目录，不要写成 output/a_batch_ocr/pages：
#   那会在 a 的正式产物根目录里多出一个「不属于任何 case」的目录，
#   破坏按输入隔离的结构，还会被 report_stale_cases() 当成旧 case 误报。
PDF_PAGES_DIR = 'output/text_layer_extract/pages'
# 不传命令行参数时，`python text_layer_extract.py` 默认单独调试哪个 case。
# 想测别的文件直接跟在后面：python text_layer_extract.py input/105_real_transactions_gbk.csv
DEBUG_CASE = 'input/103_real_bank_statement_textlayer.pdf'
TABLE_STRATEGIES = (None, 'lines', 'text')       # 策略回退顺序：默认 → 网格线 → 文字对齐
TABLE_MIN_FILL_RATIO = 0.20                      # 非空单元格占比低于它 → 标「低置信度」
# 人工标定的列边界（固定版式专用）：键是**去掉数字编号后的文件名**。
#   103_real_bank_statement_textlayer.pdf → real_bank_statement_textlayer.pdf
# 这是第1周那份银行流水，9 条竖线能拆出正确的 8 列表头；自动按 words 的 x0
# 聚类会把页眉混进表头，实测不如人工模板。
# 用语义名当键的好处：以后换编号、复制出新 case，模板照样命中，不必改这里。
# 换文件请删掉或改掉这一项；不需要就把字典清空。
TABLE_COLUMN_LINES = {
    'real_bank_statement_textlayer.pdf': [17, 112, 175, 265, 326, 393, 463, 532, 578],
}
TEXT_ENCODINGS = ('utf-8-sig', 'gbk', 'latin-1')  # CSV 编码回退顺序（Excel 中文常存成 GBK）
MIN_TEXT_LAYER_CHARS = 50                         # 前几页抽到超过这么多字 → 判定「有文本层」
# ==========================================================================

import os
import io
import csv
import sys
import json
from pathlib import Path   # as_posix()：把 Windows 的 \ 统一显示成 /，方便和文档路径对照

import pdfplumber
import pymupdf

import case_naming as naming   # 命名规则的唯一真相源（这里只用 strip_no）


# --------------------------------------------------------------------------
# 一、PDF 首页渲染 + 文本层判断
# --------------------------------------------------------------------------

def render_first_page(pdf_path, out_path, dpi=None):
    """
    把 PDF 第 1 页渲染成 PNG，返回 (PNG 路径, 总页数, 是否被 CropBox 裁剪)。

    为什么不直接 page.get_pixmap()：pymupdf 默认按 CropBox（阅读器显示的视口）
    渲染。第1周 test3.pdf 的 CropBox 只有 142.5pt 高、MediaBox 有 842pt，
    默认渲染出来只有顶部一小条，表格根本不在画面里。
    set_cropbox(mediabox) 只是改内存里的页面对象，不会写回原 PDF。
    """
    dpi = PDF_RENDER_DPI if dpi is None else dpi
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    doc = pymupdf.open(pdf_path)
    try:
        pages = len(doc)
        if pages == 0:
            return None, 0, False
        page = doc[0]
        limited = page.cropbox != page.mediabox
        if limited:
            page.set_cropbox(page.mediabox)      # 临时扩到整页，才能看到被裁掉的表格
        matrix = pymupdf.Matrix(dpi / 72, dpi / 72)
        page.get_pixmap(matrix=matrix, alpha=False).save(out_path)
        return out_path, pages, limited
    finally:
        doc.close()                              # 一定关掉，避免文件被占用


def has_text_layer(pdf_path):
    """前几页能抽出足够文字 = 有文本层（可以不跑 OCR 直接读）。"""
    with pdfplumber.open(pdf_path) as pdf:
        sample = ''.join((p.extract_text() or '') for p in pdf.pages[:3])
    return len(sample.strip()) > MIN_TEXT_LAYER_CHARS


# --------------------------------------------------------------------------
# 二、文本层表格：策略回退（移植自 week-01）
# --------------------------------------------------------------------------

def build_table_settings(strategy, column_lines=None):
    """把策略名翻译成 pdfplumber 认识的 table_settings 字典；空字典 = 用默认值。"""
    if strategy == 'explicit' and column_lines:
        # 人工给定竖线（列边界），横线交给页面里真实画出来的表格线。
        #
        # ★ 11-13 实测修正：这里原来是 horizontal_strategy='text'（按文字行切），
        #   结果 103 那份银行流水被切成 105 行「伪表格」：一笔交易因为单元格里
        #   换了行（日期 / 时间 / 金额 / 摘要分属不同物理行）被拆成 3~5 行，
        #   列内容互相错位，填充率只有 0.293。
        #   改成 'lines' 后按 26 条真实横线切出 25 行（1 行表头 + 24 笔交易），
        #   抬头「用户所属公司 / 打印时间 / 记录数」因为没有横线包围会自动落在
        #   表格之外，填充率升到 0.74。单元格内的换行由 pdfplumber 保留成 \n，
        #   导出 CSV 时再压成空格（见 table_extract.py）。
        # 注意：只有「有横线但没竖线」的流水表才配这个组合；纯 lines 策略在
        #   竖线数为 0 时会直接抽不到表，所以不能整体改成 lines。
        return {'vertical_strategy': 'explicit',
                'explicit_vertical_lines': column_lines,
                'horizontal_strategy': 'lines'}
    if strategy == 'lines':
        return {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'}
    if strategy == 'text':
        return {'vertical_strategy': 'text', 'horizontal_strategy': 'text'}
    return {}


def clean_table(table):
    """丢全空行 / 全空列、补齐长短不齐的行，返回 (rows, 质量信息 dict)。"""
    rows = [[('' if c is None else str(c)).strip() for c in row] for row in (table or [])]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return [], {}
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]
    keep = [j for j in range(width) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    total = len(rows) * len(rows[0]) if rows[0] else 0
    filled = sum(1 for r in rows for c in r if c)
    ratio = round(filled / total, 3) if total else 0.0
    info = {'n_rows': len(rows), 'n_cols': len(rows[0]) if rows else 0,
            'fill_ratio': ratio, 'low_confidence': ratio < TABLE_MIN_FILL_RATIO}
    return rows, info


def table_strategies_for(pdf_path):
    """命中人工模板时把 explicit 插到最前；返回 (策略元组, 列边界或 None)。"""
    name = os.path.basename(pdf_path)
    # 先按原名找，再按「去掉数字编号」的语义名找。
    # 这样 103_real_xxx.pdf 换成 108_real_xxx.pdf 后模板照样命中。
    lines = (TABLE_COLUMN_LINES.get(name)
             or TABLE_COLUMN_LINES.get(naming.strip_no(name)))
    if lines:
        return ('explicit',) + tuple(TABLE_STRATEGIES), lines
    return tuple(TABLE_STRATEGIES), None


def extract_pdf_tables(pdf_path):
    """
    有文本层时直接抽表格，返回 (tables, diagnostics)。

    tables 里一条记录 = 一张表，字段与第1周一致：
        page / source / strategy / rows / n_rows / n_cols / fill_ratio / low_confidence
    diagnostics 是给人看的诊断信息，会一起显示在对比预览里。
    """
    strategies, column_lines = table_strategies_for(pdf_path)
    diag = {'text_layer': True, 'template': bool(column_lines), 'pages': [], 'notes': []}
    if column_lines:
        diag['notes'].append(f'命中人工列边界模板（{len(column_lines)} 条竖线）→ explicit 策略优先')
    found = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):   # 页码 1 起，全仓统一
            # 竖边满足 x0 ≈ x1；没有竖线就说明这是「靠文字对齐」的 stream 型表格。
            try:
                edges = page.edges
                vertical = sum(1 for e in edges if abs(e['x0'] - e['x1']) < 1)
                horizontal = len(edges) - vertical
                diag['pages'].append(f'第 {page_no} 页：横线 {horizontal} / 竖线 {vertical}')
                if vertical == 0:
                    diag['notes'].append(f'第 {page_no} 页无竖线，默认策略通常抽不到表')
            except Exception:
                diag['pages'].append(f'第 {page_no} 页：线型诊断不可用')

            picked = None
            for strategy in strategies:
                label = strategy or 'default'
                settings = build_table_settings(strategy, column_lines)
                try:
                    if settings:
                        raw = page.extract_tables(table_settings=settings)
                    else:
                        raw = page.extract_tables()
                    raw = raw or []
                except Exception as e:
                    diag['notes'].append(f'第 {page_no} 页 {label} 策略出错：{e}')
                    continue
                cleaned = [clean_table(t) for t in raw]
                cleaned = [item for item in cleaned if item[0]]
                if cleaned:
                    picked = label
                    for rows, info in cleaned:
                        record = {'page': page_no, 'source': 'pdfplumber',
                                  'strategy': label, 'rows': rows}
                        record.update(info)
                        found.append(record)
                    diag['pages'].append(f'第 {page_no} 页 {label} 策略 → {len(cleaned)} 张表')
                    break
                diag['pages'].append(f'第 {page_no} 页 {label} 策略 → 0 张表，回退')
            if not picked:
                diag['notes'].append(f'第 {page_no} 页所有策略都没抽到表格：'
                                     f'可能是贴图表格，建议只把这一页转图走表格结构模型')
    return found, diag


# --------------------------------------------------------------------------
# 三、CSV / TXT 纯文本：连模型都不用加载
# --------------------------------------------------------------------------

def read_plain_text(path):
    """按候选编码逐个试，返回 (文本, 实际编码)。Windows Excel 存的中文 CSV 常是 GBK。"""
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in TEXT_ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace'), 'utf-8(replace)'


def csv_tables(text):
    """把 CSV 文本拆成行列表；整份文件算第 1 页、1 张表，与 PDF 分支结构对齐。"""
    if not text.strip():
        return []
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    return [{'page': 1, 'source': 'csv', 'strategy': 'csv.reader',
             'rows': rows, 'n_rows': len(rows),
             'n_cols': max((len(r) for r in rows), default=0),
             'fill_ratio': 1.0, 'low_confidence': False}] if rows else []


def extract_case(path, pages_dir=None):
    """
    统一入口：a_batch_ocr.py 对 PDF / CSV 调这个，返回一段「直读」结果 dict。

    pages_dir 可由调用方传入，方便和 a_batch_ocr.py 配置区的 PAGES_DIR 保持一致；
    不传就用本模块配置区的 PDF_PAGES_DIR。

    返回字段：
        kind            'pdf' / 'csv'
        preview_image   PDF 首页 PNG 的路径（CSV 为 None）
        pages           PDF 总页数（CSV 为 1）
        text_layer      是否有文本层（CSV 为 True，本来就是文字）
        cropbox_limited 是否被裁剪（只影响渲染，不影响抽取）
        tables          抽出的表格列表
        diagnostics     给人看的诊断信息
        plain_text      CSV 原文 / PDF 未使用
        encoding        CSV 实际编码
    """
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    result = {
        'kind': 'csv' if ext in ('.csv', '.txt', '.md') else 'pdf',
        'preview_image': None, 'pages': 1, 'text_layer': True,
        'cropbox_limited': False, 'tables': [], 'diagnostics': {},
        'plain_text': '', 'encoding': '',
    }
    if result['kind'] == 'csv':
        text, enc = read_plain_text(path)
        result['plain_text'] = text
        result['encoding'] = enc
        result['tables'] = csv_tables(text) if ext == '.csv' else []
        result['diagnostics'] = {
            'text_layer': True, 'template': False,
            'pages': [f'纯文本文件，按 {enc} 解码，共 {len(text)} 字符'],
            'notes': [] if ext == '.csv' else ['.txt / .md 不做表格解析，只展示全文'],
        }
        return result

    # ---- PDF ----
    # pages_dir 由调用方传入 <case 目录>/pages/，目录名已经带上了 case 名，
    # 所以图片本身统一叫 p1.png，不再把文件名重复拼一遍。
    out_png = os.path.join(pages_dir or PDF_PAGES_DIR, 'p1.png')
    png, pages, limited = render_first_page(path, out_png)
    result['preview_image'] = png
    result['pages'] = pages
    result['cropbox_limited'] = limited
    try:
        result['text_layer'] = has_text_layer(path)
    except Exception:
        result['text_layer'] = False
    if result['text_layer']:
        tables, diag = extract_pdf_tables(path)
        result['tables'] = tables
        result['diagnostics'] = diag
    else:
        result['diagnostics'] = {
            'text_layer': False, 'template': False,
            'pages': [f'共 {pages} 页，无文本层'],
            'notes': ['这是扫描件 PDF：没有文本层可直读，表格只能走 OCR / 表格结构模型'],
        }
    if limited:
        result['diagnostics'].setdefault('notes', []).append(
            '该 PDF 有 CropBox 裁剪，预览图已按 MediaBox 整页渲染（含阅读器里看不到的内容）')
    return result


# --------------------------------------------------------------------------
# 四、单独调试入口（不跑 OCR，只把直读结果打印出来）
# --------------------------------------------------------------------------

def debug_summary(path, result):
    """把 extract_case() 返回的 dict 打印成人能读的摘要；--json 时再补一份全量。"""
    print('>> 单独调试 text_layer_extract（不加载任何 OCR 模型，不写正式产物）')
    print(f'>> 文件：{path}')
    print(f"类型：{result['kind']}　页数：{result['pages']}　"
          f"文本层：{'是' if result['text_layer'] else '否'}　"
          f"CropBox 裁剪：{'是' if result['cropbox_limited'] else '否'}")
    if result['preview_image']:
        print(f"首页预览图：{Path(result['preview_image']).as_posix()}")

    tables = result['tables']
    print(f'抽到表格：{len(tables)} 张')
    for t in tables:
        print(f"  第 {t['page']} 页 / {t['strategy']} 策略 / "
              f"{t['n_rows']}×{t['n_cols']} / 填充率 {t['fill_ratio']} / "
              f"低置信度：{'是' if t['low_confidence'] else '否'}")

    diag = result.get('diagnostics') or {}
    notes, pages = diag.get('notes') or [], diag.get('pages') or []
    if pages or notes:
        print('--- 抽取诊断 ---')
        for line in pages + notes:
            print(f'  {line}')

    if tables and tables[0].get('rows'):
        print(f"--- 第 1 张表前 3 行（共 {tables[0]['n_rows']} 行）---")
        for i, row in enumerate(tables[0]['rows'][:3], 1):
            print(f"  {i} | {' | '.join(str(c) for c in row)}")
    if result.get('plain_text'):
        print(f"--- 原文（{result.get('encoding')}）---")
        print(result['plain_text'].strip()[:500])


def main():
    """
    单独调试入口。和 a_batch_ocr.py 的区别见文件头「谁在调用我 / 怎么单独测」：
        python text_layer_extract.py                      # 测配置区 DEBUG_CASE（默认 103）
        python text_layer_extract.py input/105_...csv     # 测别的文件
        python text_layer_extract.py --json               # 额外打印完整 dict
    只调用 extract_case()，所以不加载 OCR 模型、不写 result.json、不画框、不生成 HTML。
    """
    # 把 --json 从位置参数里挑出来，剩下的第一个当作文件路径。
    args = [a for a in sys.argv[1:] if a != '--json']
    path = args[0] if args else DEBUG_CASE
    if not os.path.isfile(path):
        sys.exit(f'找不到文件：{os.path.abspath(path)}\n'
                 f'改配置区 DEBUG_CASE，或命令行指定：'
                 f'python text_layer_extract.py 文件路径')

    result = extract_case(path)
    debug_summary(path, result)
    if '--json' in sys.argv[1:]:
        print('--- 完整 dict（--json）---')
        print(json.dumps(result, ensure_ascii=False, indent=2))


# 主程序守卫：直接运行才执行 main()；被 a_batch_ocr.py import 时不会自动跑。
if __name__ == '__main__':
    main()
