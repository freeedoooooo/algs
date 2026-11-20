"""
collect.py — 字段映射 Mapping：cvdoc → 暂存记录集（只认 cvdoc，不认识引擎字段）。

P0：passthrough（无配置整表透传）——每表每行一条记录，键 = 表头原文
（空表头 col_<n>，重名加下标），lineage 逐格（1:N 锚点数组形态）。
被并入跨页合并表的逐页表跳过（避免重复计数）；合并表 cells 逐格带 page，
血缘页码天然正确。P1 加选择器（table{index|header_contains} × column{name|index}）。
"""
from .adapter.base import RECORDS_SCHEMA


def _keys(headers):
    keys, seen = [], {}
    for c, h in enumerate(headers or []):
        k = str(h or '').strip() or 'col_{}'.format(c)
        if k in seen:
            k = '{}_{}'.format(k, c)
        seen[k] = True
        keys.append(k)
    return keys


def _anchor(scope, t, ti, cells, r, c, value, page_default):
    cell = None
    if r + 1 < len(cells) and c < len(cells[r + 1]):
        cell = cells[r + 1][c]
    if scope == 'page':
        bbox = cell if isinstance(cell, list) else None
        page = t.get('page', page_default)
        space = (t.get('coord') or {}).get('space')
    else:
        cell = cell or {}
        bbox = cell.get('bbox')
        page = cell.get('page')
        space = cell.get('space')
    return {'page': page, 'table_index': ti, 'table_scope': scope,
            'cell_bbox': bbox, 'space': space, 'raw_text': value}


def passthrough(doc):
    """cvdoc 信封 → 记录列表（values/original/lineage/review）。"""
    records = []
    stitched = doc.get('stitched_tables') or []
    merged = {(part.get('page'), part.get('tbl'))
              for t in stitched for part in (t.get('parts') or [])}

    def add_table(t, scope, ti, page_default):
        keys = _keys(t.get('headers'))
        cells = t.get('cells') or []
        for r, row in enumerate(t.get('rows') or []):
            values, lineage = {}, {}
            for c, key in enumerate(keys):
                v = row[c] if c < len(row) else ''
                values[key] = v
                lineage[key] = [_anchor(scope, t, ti, cells, r, c, v,
                                        page_default)]
            records.append({
                'index': len(records),
                'values': values,
                'original': dict(values),
                'lineage': lineage,
                'review': {'state': 'pending', 'at': None},
            })

    for pg in doc.get('pages') or []:
        for ti, t in enumerate(pg.get('tables') or []):
            if (pg.get('index'), ti) in merged:
                continue
            add_table(t, 'page', ti, pg.get('index'))
    for si, t in enumerate(stitched):
        add_table(t, 'stitched', si, None)
    return records


def build_records_doc(doc, records, run_id=None, run_file_id=None,
                      source_file_id=None, template=None):
    """records.json 信封（L2 事实源形态）。"""
    return {
        'schema': RECORDS_SCHEMA,
        'run_id': run_id,
        'template': template or {'name': '原始透传', 'version': 1},
        'files': [{
            'run_file_id': run_file_id,
            'source_file_id': source_file_id,
            'name': (doc.get('file') or {}).get('name'),
            'records': records,
        }],
    }