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
# 确定性优先：只合并「相邻页 + 同列数 + 列 x 边界对齐 + 表头逐字重复」的续表，
# 丢掉后续页的重复表头、数据行顺接。判据不满足一律不合并（宁可不拼，不误拼）。
# 合并表每个单元格保留 {bbox, page, space}，报告据此做「页感知回溯」：
# 悬停某格自动切到它所在页的图并高亮。

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


def _continues(a, b):
    """b 是否为 a 的跨页续表（重复表头）。是→True，否→False。"""
    if not a.get('n_cols') or a.get('n_cols') != b.get('n_cols'):
        return False
    if (a.get('coord') or {}).get('space') != (b.get('coord') or {}).get('space'):
        return False
    if not (a.get('coord') or {}).get('exact'):
        return False
    if not _cols_aligned(a, b):
        return False
    ha, hb = _norm_header(a.get('headers')), _norm_header(b.get('headers'))
    return bool(ha) and bool(hb) and ha == hb


def _annotate_cells(grid_rows, page, space):
    return [[{'bbox': (list(b) if b and len(b) >= 4 else None),
              'page': page, 'space': space} for b in row]
            for row in grid_rows]


def _build_stitched(chain, si):
    p0, _ti0, a0 = chain[0]
    space = (a0.get('coord') or {}).get('space') or 'source'
    headers = list(a0.get('headers') or [])
    width = a0.get('n_cols') or len(headers)
    rows = [list(r) for r in (a0.get('rows') or [])]
    row_pages = [p0] * len(rows)
    a0_cells = a0.get('cells') or []
    cells = _annotate_cells(a0_cells[:1], p0, space)          # 表头行
    cells += _annotate_cells(a0_cells[1:1 + len(rows)], p0, space)
    parts = [{'page': p0, 'tbl': _ti0, 'header_dropped': False,
              'n_rows': len(rows)}]
    for p, ti, b in chain[1:]:
        br = [list(r) for r in (b.get('rows') or [])]
        rows += br
        row_pages += [p] * len(br)
        bc = b.get('cells') or []
        cells += _annotate_cells(bc[1:1 + len(br)], p, space)  # 丢重复表头行
        parts.append({'page': p, 'tbl': ti, 'header_dropped': True,
                      'n_rows': len(br)})
    return {
        'id': si,
        'title': a0.get('title', ''),
        'headers': headers,
        'rows': rows,
        'row_pages': row_pages,
        'cells': cells,
        'n_rows': len(rows),
        'n_cols': width,
        'source_pages': [p for p, _t, _b in chain],
        'parts': parts,
        'coord': {'mixed': True, 'space': 'per-cell', 'exact': True},
        'csv_file': 'stitched_{}.csv'.format(si),
    }


def stitch_tables(pages):
    """pages（按页排序的 pageRec 列表）→ 跨页合并表列表（仅含 >=2 页的续表）。

    只从每页最后一张表起链，接下一页第一张表，逐页延伸；已被合并的表不再重复起链。
    """
    by_page = {pg.get('page'): (pg.get('structured_tables') or [])
               for pg in pages}
    used, stitched = set(), []
    for p in sorted(k for k in by_page if k is not None):
        tabs = by_page[p]
        if not tabs:
            continue
        ai = len(tabs) - 1
        if (p, ai) in used:
            continue
        chain = [(p, ai, tabs[ai])]
        cur, np = tabs[ai], p + 1
        while by_page.get(np):
            b = by_page[np][0]
            if (np, 0) in used or not _continues(cur, b):
                break
            chain.append((np, 0, b))
            used.add((np, 0))
            cur, np = b, np + 1
        if len(chain) >= 2:
            used.add((p, ai))
            stitched.append(_build_stitched(chain, len(stitched) + 1))
    return stitched
