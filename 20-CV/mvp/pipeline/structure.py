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
    return rows[:idx], rows[idx], rows[idx + 1:], idx


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
