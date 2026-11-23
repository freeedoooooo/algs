"""
pipeline/structure.py — 把 raw 表整理成「有表头、每格带 bbox」的结构化表。

cells[r][c] 与「表头 1 行 + 数据 n 行」严格同形状，
报告里的 <td data-cell="r_c"> 才能直接索引，不用再换算。
"""
import os
import re
import csv


def align_cell_grid(rows, grid):
    if not grid:
        return []
    width = max((len(r) for r in rows), default=0)
    out = [g[:width] + [None] * max(0, width - len(g))
           for g in grid][:len(rows)]
    while len(out) < len(rows):
        out.append([None] * width)
    return out


def split_header(rows):
    """返回 (标题行, 表头, 数据行, 表头在原 rows 里的下标)。"""
    if not rows:
        return [], [], [], 0
    width = max(len(r) for r in rows)
    rows = [list(r) + [''] * (width - len(r)) for r in rows]
    idx = 0
    for i, row in enumerate(rows[:6]):
        filled = sum(1 for c in row if str(c).strip())
        if filled >= 3 and filled == width:
            idx = i
            break
    # 表头前的「碎片标签行」（如 108 单独一行的 余额/摘要）并入表头对应列，
    # 而不是误当成表格标题。真实标题通常是单个跨列长单元格，不满足此条件。
    headers = list(rows[idx])
    title_rows = []
    for r in rows[:idx]:
        cells = [(c, str(v).strip()) for c, v in enumerate(r) if str(v).strip()]
        label_like = (len(cells) >= 2 and
                      all(len(v) <= 8 and not any(ch.isdigit() for ch in v)
                          for _, v in cells))
        if label_like:
            for c, v in cells:
                if c < len(headers):
                    headers[c] = v
        else:
            title_rows.append(r)
    return title_rows, headers, rows[idx + 1:], idx


def structure_table(raw, index):
    rows = [[re.sub(r'\s+', ' ', str(c or '')).strip()
             for c in r] for r in (raw.get('rows') or [])]
    grid = align_cell_grid(rows, raw.get('cell_grid') or [])
    title_rows, headers, data, hidx = split_header(rows)
    head_grid = grid[hidx] if grid else []
    data_grid = grid[hidx + 1:] if grid else []
    keep = [i for i, r in enumerate(data) if any(r)]
    data = [data[i] for i in keep]
    data_grid = [data_grid[i] for i in keep] if data_grid else []
    width = len(headers) if headers else max((len(r) for r in data), default=0)
    total = len(data) * width
    filled = sum(1 for r in data for c in r if c)
    cells = ([head_grid] + data_grid) if grid else []
    coord = dict(raw.get('coord') or {'space': 'none', 'exact': False,
                                      'note': '无坐标'})
    coord['grid_rows'] = len(cells)
    coord['grid_cols'] = width
    return {
        'page': raw.get('page', 1),
        'source': raw.get('source', '?'),
        'strategy': raw.get('strategy', '?'),
        'title': ' / '.join(c for r in title_rows for c in r if c),
        'headers': headers,
        'rows': data,
        'cells': cells,
        'coord': coord,
        'n_rows': len(data),
        'n_cols': width,
        'fill_ratio': round(filled / total, 3) if total else 0.0,
        'low_confidence': (filled / total if total else 0) < 0.20,
        'csv_file': 'table_{}.csv'.format(index),
    }


def structure_all(raw_tables):
    return [structure_table(t, i) for i, t in enumerate(raw_tables, 1)]


def export_csvs(structured, case_abs):
    """每张表一份 UTF-8 BOM 的 CSV，第一行固定是表头。"""
    for t in structured:
        path = os.path.join(case_abs, t['csv_file'])
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            if t['headers']:
                w.writerow(t['headers'])
            w.writerows(t['rows'])


# ---- 跨页表拼接：相邻页续表合并成一张逻辑表 ----
# 确定性优先，两条通路：
#   repeat    —— 同列数 + 列 x 对齐 + 表头逐字重复：丢后续页重复表头、数据顺接（原严格通路）。
#   headerless—— 续页无重复表头（首行数据被误标表头）+ 末尾空列被裁：列位置子集对齐 +
#                续页贴顶 + 首行像数据 → 回收首行作数据、按主表布局补齐空列。
# 判据不满足一律不合并（宁可不拼，不误拼）。合并表每个单元格保留 {bbox, page, space}，
# 报告据此做「页感知回溯」：悬停某格自动切到它所在页的图并高亮。

def _col_left_edges(t):
    """取首个有效坐标行的各列左缘 x0（缺格为 None），用于列对齐判断。"""
    for row in t.get('cells') or []:
        if sum(1 for b in row if b and len(b) >= 4) >= 2:
            return [(b[0] if b and len(b) >= 4 else None) for b in row]
    return []


def _cols_aligned(a, b, tol=12.0):
    ea, eb = _col_left_edges(a), _col_left_edges(b)
    pairs = [(ea[i], eb[i]) for i in range(min(len(ea), len(eb)))
             if ea[i] is not None and eb[i] is not None]
    if len(pairs) < 2:
        return False
    return all(abs(x - y) <= tol for x, y in pairs)


def _norm_header(h):
    return [re.sub(r'\s+', ' ', str(c or '')).strip() for c in (h or [])]


# 通用数据形态（不写死任何 case）：长数字串 / YYYYMMDD 日期 / 带小数点金额。
_DATA_RE = re.compile(
    r'\d{6,}|(?:19|20)\d{2}(?:0[1-9]|1[2])(?:0[1-9]|[12]\d|3[01])|\d+\.\d{1,2}')


def _col_xs(t):
    """每列左缘 x0：跨所有坐标行取首个非 None，比单行更完整（缺格列也能定位）。"""
    xs = []
    for row in t.get('cells') or []:
        while len(xs) < len(row):
            xs.append(None)
        for j, b in enumerate(row):
            if xs[j] is None and b and len(b) >= 4:
                xs[j] = b[0]
    return xs


def _col_map(a, b, tol=12.0):
    """续页列 → 主表列 的保序单射 x 匹配（贪心双指针）。

    允许续页缺主表若干列（被裁的空列）；续页任何列在主表找不到位置 → None（不拼）。
    返回 {cont_col: master_col}；匹配对 <2 → None。
    """
    ea, eb = _col_xs(a), _col_xs(b)
    if not ea or not eb or any(x is None for x in eb):
        return None
    cmap, i = {}, 0
    for j, x in enumerate(eb):
        while i < len(ea) and (ea[i] is None or ea[i] < x - tol):
            i += 1
        if i >= len(ea) or ea[i] is None or abs(ea[i] - x) > tol:
            return None
        cmap[j] = i
        i += 1
    return cmap if len(cmap) >= 2 else None


def _table_y0(t):
    for row in t.get('cells') or []:
        ys = [b[1] for b in row if b and len(b) >= 4]
        if ys:
            return min(ys)
    return None


def _data_like(row, master_headers, cmap):
    """首行是否像数据：≥1 格命中数据形态，且对应主表头是非数字标签。"""
    for j, v in enumerate(row):
        s = str(v or '').strip()
        if not s or not _DATA_RE.search(s):
            continue
        i = cmap.get(j)
        if i is None or i >= len(master_headers):
            continue
        lab = str(master_headers[i] or '').strip()
        if lab and not re.search(r'\d', lab):
            return True
    return False


def _continues(a, b, page_h=None, master=None):
    """b 是否为 a 的跨页续表。返回 (模式, 列映射) 或 None。

    模式 'repeat'：原严格通路（同列数+列对齐+表头重复），列映射为恒等。
    模式 'headerless'：子集对齐 + 续页贴顶 + 首行像数据（无重复表头）。
    master 为链首主表（真表头/规范列布局）；headerless 链中直接前驱 a 的
    「headers」可能已是数据，故 G2/G4 一律以 master 为参照，默认 master=a。
    """
    if (a.get('coord') or {}).get('space') != (b.get('coord') or {}).get('space'):
        return None
    if not (a.get('coord') or {}).get('exact'):
        return None
    ha, hb = _norm_header(a.get('headers')), _norm_header(b.get('headers'))
    if (a.get('n_cols') and a.get('n_cols') == b.get('n_cols')
            and _cols_aligned(a, b) and ha and hb and ha == hb):
        n = b.get('n_cols') or len(hb)
        return 'repeat', {j: j for j in range(n)}
    m = master if master is not None else a
    cmap = _col_map(m, b)
    if cmap is None:
        return None
    y0 = _table_y0(b)
    if not page_h or y0 is None or y0 > 0.10 * page_h:
        return None
    mh = _norm_header(m.get('headers'))
    if not hb or not _data_like(hb, mh, cmap):
        return None
    return 'headerless', cmap


def _annotate_cells(grid_rows, page, space):
    return [[{'bbox': (list(b) if b and len(b) >= 4 else None),
              'page': page, 'space': space} for b in row]
            for row in grid_rows]


def _pad_row(row, cmap, width, fill):
    out = [fill] * width
    for j, v in enumerate(row):
        i = cmap.get(j)
        if i is not None and i < width:
            out[i] = v
    return out


def _build_stitched(chain, si):
    p0, _ti0, a0, _m0, _c0 = chain[0]
    space = (a0.get('coord') or {}).get('space') or 'source'
    headers = list(a0.get('headers') or [])
    width = a0.get('n_cols') or len(headers)
    rows = [_pad_row(r, {j: j for j in range(width)}, width, '')
            for r in (a0.get('rows') or [])]
    row_pages = [p0] * len(rows)
    a0_cells = a0.get('cells') or []
    cells = _annotate_cells(a0_cells[:1], p0, space)          # 表头行
    cells += _annotate_cells(a0_cells[1:1 + len(rows)], p0, space)
    parts = [{'page': p0, 'tbl': _ti0, 'header_dropped': False,
              'header_recovered': False, 'n_rows': len(rows)}]
    for p, ti, b, mode, cmap in chain[1:]:
        b_rows = b.get('rows') or []
        b_cells = b.get('cells') or []
        if mode == 'headerless':
            # 无重复表头：被误标成 headers 的首行其实是数据，回收进数据行
            br = [list(b.get('headers') or [])] + [list(r) for r in b_rows]
            bc = b_cells[:1 + len(b_rows)]
            dropped, recovered = False, True
        else:
            br = [list(r) for r in b_rows]
            bc = b_cells[1:1 + len(br)]                       # 丢重复表头行
            dropped, recovered = True, False
        bc = list(bc) + [[] for _ in range(max(0, len(br) - len(bc)))]
        for r, crow in zip(br, bc):
            rows.append(_pad_row(r, cmap, width, ''))
            cells += _annotate_cells(
                [_pad_row(crow, cmap, width, None)], p, space)
        row_pages += [p] * len(br)
        parts.append({'page': p, 'tbl': ti, 'header_dropped': dropped,
                      'header_recovered': recovered, 'n_rows': len(br)})
    return {
        'id': si,
        'title': a0.get('title', ''),
        'headers': headers,
        'rows': rows,
        'row_pages': row_pages,
        'cells': cells,
        'n_rows': len(rows),
        'n_cols': width,
        'source_pages': [p for p, _t, _b, _m, _c in chain],
        'parts': parts,
        'coord': {'mixed': True, 'space': 'per-cell', 'exact': True},
        'csv_file': 'stitched_{}.csv'.format(si),
    }


def stitch_tables(pages):
    """pages（按页排序的 pageRec 列表）→ 跨页合并表列表（仅含 >=2 页的续表）。

    只从每页最后一张表起链，接下一页第一张表，逐页延伸；已被合并的表不再重复起链。
    页高（image_size[1]）传进判据供「续页贴顶」闸使用。
    """
    by_page = {pg.get('page'): (pg.get('structured_tables') or [])
               for pg in pages}
    heights = {pg.get('page'): (pg.get('image_size') or [0, 0])[1]
               for pg in pages}
    used, stitched = set(), []
    for p in sorted(k for k in by_page if k is not None):
        tabs = by_page[p]
        if not tabs:
            continue
        ai = len(tabs) - 1
        if (p, ai) in used:
            continue
        chain = [(p, ai, tabs[ai], None, None)]
        master = tabs[ai]
        cur, np = tabs[ai], p + 1
        while by_page.get(np):
            b = by_page[np][0]
            res = None if (np, 0) in used else _continues(
                cur, b, heights.get(np), master)
            if res is None:
                break
            mode, cmap = res
            chain.append((np, 0, b, mode, cmap))
            used.add((np, 0))
            cur, np = b, np + 1
        if len(chain) >= 2:
            used.add((p, ai))
            stitched.append(_build_stitched(chain, len(stitched) + 1))
    return stitched
