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


def render_first_page(pdf_path, out_png, page_no=1, dpi=None):
    """渲染指定页（页码 1 起）；dpi / page_no 来自页面调试参数。"""
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    doc = pymupdf.open(pdf_path)
    try:
        if len(doc) == 0:
            return None, 0, False
        idx = min(max(int(page_no) - 1, 0), len(doc) - 1)
        page = doc[idx]
        # pymupdf 默认按 CropBox 渲染；被裁剪的 PDF 要扩到 MediaBox 才看得到整页
        limited = page.cropbox != page.mediabox
        if limited:
            page.set_cropbox(page.mediabox)
        zoom = (dpi or config.PDF_DPI) / 72
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom),
                        alpha=False).save(out_png)
        return out_png, len(doc), limited
    finally:
        doc.close()


def text_layer(pdf_path, page_no=None):
    """取文本层；指定 page_no 时只读那一页（配合页码参数定位跨页 case）。"""
    with pdfplumber.open(pdf_path) as pdf:
        if page_no is not None:
            idx = min(max(int(page_no) - 1, 0), len(pdf.pages) - 1)
            return pdf.pages[idx].extract_text() or ''
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


def _lines_from_edges(page, max_cols=14):
    """
    首选：从 pdfplumber 的横线端点推列边界。

    流水表的横线常是「分段短线段」（103 每段仅 51~86pt），每段端点就是
    列的左右边界；把出现多次（跨多行）的端点聚类，能还原出真实列数。
    实测 103：端点簇给出 9 条边界 → 25×8 真表，与当初人工模板逐字一致，
    因此不再需要写死任何 case 的列边界。
    """
    try:
        edges = page.horizontal_edges or []
        if len(edges) < 4:
            return None
        xs = sorted([float(e['x0']) for e in edges]
                    + [float(e['x1']) for e in edges])
        # 端点会重复出现在很多行；按容差聚类，只保留出现 >=2 次的稳定边界
        groups = [[xs[0]]]
        for x in xs[1:]:
            if x - groups[-1][-1] <= 2:
                groups[-1].append(x)
            else:
                groups.append([x])
        bounds, seen = [], set()
        for g in groups:
            if len(g) < 2:          # 端点只出现 1 次 = 噪点
                continue
            v = round(sum(g) / len(g), 1)
            if not seen or v - max(seen) >= 8:   # 合并 8pt 内的近邻簇
                bounds.append(v)
                seen.add(v)
        if len(bounds) < 3 or len(bounds) > max_cols + 1:
            return None
        return bounds
    except Exception:
        return None


def _lines_from_words(page, max_cols=14):
    """兜底：横线端点不可用时，用表头行的文字左边界聚类。"""
    try:
        hlines = page.horizontal_edges or []
        if len(hlines) < 4:
            return None
        tops = sorted(set(round(e['top'], 1) for e in hlines))
        y0 = tops[0]
        row_h = (tops[1] - tops[0]) if len(tops) > 1 else 20
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


def auto_column_lines(page, max_cols=14):
    """
    自动推列边界：横线端点优先，但要防止「一页多表」时各表端点混在一起。

    判据：端点数 == 文字数 + 1 时才用端点法 —— 这正好是「两个列名被 pdfplumber
    粘成一个 word」造成的缺口（103 端点 9 / 文字 8，还原出被粘的 8 列）。
    其它情况回退文字法：20 两者相等（端点位置略偏，保持原有 7 列）；
    21/23/26 端点远多于文字（多表端点混叠），用端点会把列数虚高到 10。
    """
    edges = _lines_from_edges(page, max_cols)
    words = _lines_from_words(page, max_cols)
    if not edges:
        return words
    if words and len(edges) == len(words) + 1:
        return edges
    return words or edges


def tables(pdf_path, column_lines=None, strategy='auto', dpi=None, page_no=1):
    """
    多策略回退，取第一个抽出表的结果；返回 (raw_tables, notes)。

    column_lines 来自页面参数（特殊版式临时覆盖），没填就从 PDF 横线端点自动推断；
    strategy='auto' 用固定优先级，否则把用户指定的策略提到最前；
    dpi 决定 cell_grid 缩放（须与预览图一致）；page_no 只处理指定页。
    """
    found, notes = [], []
    scale = (dpi or config.PDF_DPI) / 72.0
    lines = list(column_lines) if column_lines else None
    if lines:
        notes.append('使用页面人工列边界（{} 条竖线）→ explicit 策略优先'
                     .format(len(lines)))
    # 固定优先级：人工/自动列边界 explicit → default → lines → text。
    # 取第一个抽出表的结果，不按填充率打分 —— 少列碎表填充率反而更高
    # （实测 25×6 的 0.813 > 正确 25×8 的 0.74），打分会选进列拆错的表。
    with pdfplumber.open(pdf_path) as pdf:
        if page_no:
            idx = min(max(int(page_no) - 1, 0), len(pdf.pages) - 1)
            pages, start = [pdf.pages[idx]], idx + 1
        else:
            pages, start = pdf.pages, 1
        for pno, page in enumerate(pages, start):
            picked = None
            auto_cols = None if lines else auto_column_lines(page)
            strategies = [('explicit', lines or auto_cols),
                          ('default', None), ('lines', None), ('text', None)]
            if strategy and strategy != 'auto':
                # 用户强制首选某策略：提到最前，其余仍保留回退
                chosen = [x for x in strategies if x[0] == strategy]
                strategies = chosen + [x for x in strategies if x[0] != strategy]
                notes.append('第 {} 页：表格策略首选 = {}'.format(pno, strategy))
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
