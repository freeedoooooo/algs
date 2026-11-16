"""
pipeline/pdf.py — PDF 首页渲染、文本层判断、pdfplumber 表格 + 单元格 bbox。

有文本层时字符本身是精确的，不需要 OCR 再猜一遍；
find_tables()（而非 extract_tables()）同时给文本和每格 bbox，
乘 PDF_DPI/72 即换到预览图像素坐标。
"""
import os

import pdfplumber
import pymupdf

from .. import config


def render_first_page(pdf_path, out_png):
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    doc = pymupdf.open(pdf_path)
    try:
        if len(doc) == 0:
            return None, 0, False
        page = doc[0]
        # pymupdf 默认按 CropBox 渲染；被裁剪的 PDF 要扩到 MediaBox 才看得到整页
        limited = page.cropbox != page.mediabox
        if limited:
            page.set_cropbox(page.mediabox)
        page.get_pixmap(
            matrix=pymupdf.Matrix(config.PDF_DPI / 72,
                                  config.PDF_DPI / 72),
            alpha=False).save(out_png)
        return out_png, len(doc), limited
    finally:
        doc.close()


def text_layer(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return ''.join((p.extract_text() or '') for p in pdf.pages[:3])


def clean_table(rows, cells=None):
    """删空行空列并同步裁剪 bbox 网格，返回 (rows, grid, width)。"""
    rows = [[('' if c is None else str(c)).strip() for c in r]
            for r in (rows or [])]
    grid = None
    if cells is not None:
        grid = [[list(c) if c else None for c in (r or [])] for r in cells]
        pad = max((len(g) for g in grid), default=0)
        while len(grid) < len(rows):
            grid.append([None] * pad)
        grid = grid[:len(rows)]
    keep_i = [i for i, r in enumerate(rows) if any(c for c in r)]
    rows = [rows[i] for i in keep_i]
    if grid is not None:
        grid = [grid[i] for i in keep_i]
    if not rows:
        return [], (grid if grid is not None else []), 0
    width = max(len(r) for r in rows)
    rows = [r + [''] * (width - len(r)) for r in rows]
    if grid is not None:
        grid = [g + [None] * (width - len(g)) for g in grid]
    keep = [j for j in range(width) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    if grid is not None:
        grid = [[g[j] for j in keep] for g in grid]
    return rows, (grid if grid is not None else []), width


def template_lines(pdf_path):
    """
    查人工列边界模板。**源文件自带的数字编号不去掉**，只剥上传时加的
    批次时间戳那一段：

        20261116160231_103_real_bank_statement_textlayer.pdf
                       └── 只剥左边 14 位时间戳 ──┘
        → 103_real_bank_statement_textlayer.pdf   （103_ 保留）

    依次尝试三种键，方便 config 里两种写法都能登记：
      1) 完整带戳名   2) 剥掉时间戳、保留原编号   3) 再剥编号的语义名
    第 3 种只为兼容 week-02 的旧登记方式（换成 108 也照样命中）。
    """
    import re
    name = os.path.basename(pdf_path)
    stripped = re.sub(r'^\d{12,14}_', '', name)   # 只剥时间戳
    semantic = re.sub(r'^\d+_', '', stripped)     # 仅作为查表的兜底键
    for key in (name, stripped, semantic):
        if key in config.TABLE_COLUMN_LINES:
            return config.TABLE_COLUMN_LINES[key]
    return None


def auto_column_lines(page, max_cols=14):
    """
    只有横线、没有竖线的流水表：用表头行的文字左边界聚类出列分隔线。

    注意页面里的横线常被画成「分段短线段」（103 每段仅 51~86pt），
    不能按「长横线」过滤；这里直接用 pdfplumber 的 horizontal_edges，
    取最靠上的横线区间当表头行，避免把页眉混进列边界。
    """
    try:
        hlines = page.horizontal_edges or []
        if len(hlines) < 4:
            return None
        tops = sorted(set(round(e['top'], 1) for e in hlines))
        y0 = tops[0]
        row_h = (tops[1] - tops[0]) if len(tops) > 1 else 20
        # 只取表头那一行（第一条与第二条横线之间）的词
        words = [w for w in (page.extract_words() or [])
                 if y0 - 1 <= w['top'] <= y0 + row_h + 2]
        if len(words) < 3:
            return None
        xs = sorted(w['x0'] for w in words)
        groups = []
        for x in xs:
            if groups and x - groups[-1][-1] < 12:
                groups[-1].append(x)
            else:
                groups.append([x])
        bounds = [max(0.0, float(min(g)) - 4) for g in groups]
        bounds.append(float(page.width))
        if len(bounds) < 3 or len(bounds) > max_cols:
            return None
        return bounds
    except Exception:
        return None


def tables(pdf_path):
    """多策略回退，取填充率最高的那组结果；返回 (raw_tables, notes)。"""
    found, notes = [], []
    scale = config.PDF_DPI / 72.0
    column_lines = template_lines(pdf_path)
    if column_lines:
        notes.append('命中人工列边界模板（{} 条竖线）→ explicit 策略优先'
                     .format(len(column_lines)))
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            picked = None
            # 固定优先级：人工模板 explicit → 自动列边界 explicit →
            # default → lines → text。取第一个抽出表的结果，不按填充率打分 ——
            # 少列的碎表填充率反而更高（实测 25×6 的 0.813 > 正确 25×8 的 0.74），
            # 用打分会把列拆错的表选进来。
            auto_cols = None if column_lines else auto_column_lines(page)
            strategies = [('explicit', column_lines or auto_cols),
                          ('default', None), ('lines', None), ('text', None)]
            for label, cols in strategies:
                if label == 'explicit':
                    if not cols:
                        continue
                    settings = {'vertical_strategy': 'explicit',
                                'explicit_vertical_lines': cols,
                                'horizontal_strategy': 'lines'}
                elif label == 'default':
                    settings = {}
                elif label == 'lines':
                    settings = {'vertical_strategy': 'lines',
                                'horizontal_strategy': 'lines'}
                else:
                    settings = {'vertical_strategy': 'text',
                                'horizontal_strategy': 'text'}
                try:
                    tabs = (page.find_tables(table_settings=settings)
                            if settings else page.find_tables())
                except Exception as e:
                    notes.append('第 {} 页 {} 策略出错：{}'.format(
                        pno, label, e))
                    continue
                cand = []
                for t in tabs or []:
                    raw = t.extract() or []
                    px = [[
                        [round(c[0] * scale, 1), round(c[1] * scale, 1),
                         round(c[2] * scale, 1), round(c[3] * scale, 1)]
                        if c else None for c in row.cells
                    ] for row in t.rows]
                    rows, grid, _width = clean_table(raw, px)
                    if not rows:
                        continue
                    cand.append({'rows': rows, 'cell_grid': grid,
                                 'strategy': label})
                if cand:
                    picked = (label, cand)
                    break
            if not picked:
                notes.append('第 {} 页所有策略都没抽到表格'.format(pno))
                continue
            label, cand = picked
            notes.append('第 {} 页 {} 策略 → {} 张表'.format(
                pno, label, len(cand)))
            for c in cand:
                found.append({
                    'page': pno, 'rows': c['rows'],
                    'cell_grid': c['cell_grid'],
                    'strategy': c['strategy'], 'source': 'pdfplumber',
                    'coord': {
                        'space': 'source', 'origin': 'pdfplumber',
                        'exact': True,
                        'note': 'PDF 文本层单元格 bbox × DPI/72 换算到预览图像素',
                    },
                })
    return found, notes
