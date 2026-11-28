"""
collect.py — 字段映射 Mapping：c1-structure → 暂存记录集（只认 c1-structure，不认识引擎字段）。

P0：passthrough（无配置整表透传）——每表每行一条记录，键 = 表头原文
（空表头 col_<n>，重名加下标），lineage 逐格（1:N 锚点数组形态）。
被并入跨页合并表的逐页表跳过（避免重复计数）；合并表 cells 逐格带 page，
血缘页码天然正确。P1b 选择器已实现（build/apply_mapping：单源表
table{index|header_contains} × column{name|index}＋重命名）；简单规则保存时把转换译为 v2 pipeline。
spec_version=2 走 collect_logic.build_logic 新引擎（C1 分发占位，C2 实现）。
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


def _candidate_tables(doc):
    """候选源表有序列表（passthrough 迭代序）：非合并页表在前，stitched 表在后。
    每项 (table, scope, table_index, page_default)。映射选择器与透传共用此序。"""
    stitched = doc.get('stitched_tables') or []
    merged = {(part.get('page'), part.get('tbl'))
              for t in stitched for part in (t.get('parts') or [])}
    out = []
    for pg in doc.get('pages') or []:
        for ti, t in enumerate(pg.get('tables') or []):
            if (pg.get('index'), ti) in merged:
                continue
            out.append((t, 'page', ti, pg.get('index')))
    for si, t in enumerate(stitched):
        out.append((t, 'stitched', si, None))
    return out


def passthrough(doc):
    """c1-structure 信封 → 记录列表（values/original/lineage/review）。"""
    records = []

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

    for t, scope, ti, page_default in _candidate_tables(doc):
        add_table(t, scope, ti, page_default)
    return records


def _pick_table(cands, sel):
    """table 选择器：index 优先，否则 header_contains 取第一张命中（确定性）。"""
    sel = sel or {}
    i = sel.get('index')
    if isinstance(i, int):
        return cands[i] if 0 <= i < len(cands) else None
    kw = sel.get('header_contains')
    if kw:
        for c in cands:
            head = ' '.join(str(h or '') for h in (c[0].get('headers') or []))
            if kw in head:
                return c
    return None


def _pick_column(keys, sel):
    """column 选择器：name 命中 _keys 键，否则 index 原始列下标；未命中 None。"""
    sel = sel or {}
    n = sel.get('name')
    if n is not None:
        return keys.index(n) if n in keys else None
    i = sel.get('index')
    return i if isinstance(i, int) and 0 <= i < len(keys) else None


def apply_mapping(doc, mapping):
    """单源表选择＋列选择/重命名 → 记录列表；lineage 复用 _anchor（字段级溯源）。
    缺表→0 条；缺列→空值＋空 lineage。"""
    picked = _pick_table(_candidate_tables(doc), (mapping or {}).get('table'))
    if picked is None:
        return []
    t, scope, ti, page_default = picked
    keys = _keys(t.get('headers'))
    cells = t.get('cells') or []
    cols = []
    for f in (mapping or {}).get('fields') or []:
        target = f.get('target')
        if not target:
            continue
        cols.append((target, _pick_column(keys, f.get('column'))))
    records = []
    for r, row in enumerate(t.get('rows') or []):
        values, lineage = {}, {}
        for target, c in cols:
            if c is None:
                values[target] = ''
                lineage[target] = []
            else:
                v = row[c] if c < len(row) else ''
                values[target] = v
                lineage[target] = [_anchor(scope, t, ti, cells, r, c, v,
                                           page_default)]
        records.append({
            'index': len(records),
            'values': values,
            'original': dict(values),
            'lineage': lineage,
            'review': {'state': 'pending', 'at': None},
        })
    return records


def build(doc, tpl=None):
    """按抽取规则当前定义或结果快照执行。"""
    spec = (tpl or {}).get('extraction_spec_json') or {}
    if spec.get('spec_version') == 2:
        from .collect_logic import build_logic
        return build_logic(doc, tpl)
    if not spec.get('fields'):
        return passthrough(doc)
    return apply_mapping(doc, spec)


def build_records_doc(doc, records, *, extract_result_id=None, rule=None):
    """按抽取结果构造 records 信封。"""
    return {
        'schema': RECORDS_SCHEMA,
        'extract_result_id': extract_result_id,
        'rule': rule or {'name': '规则结果'},
        'files': [{
            'file_id': (doc.get('file') or {}).get('file_id'),
            'name': (doc.get('file') or {}).get('name'),
            'records': records,
        }],
    }