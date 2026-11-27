"""把 parse.json 信封确定性压缩为带位置关系的 prompt 文档地图。

表顺序沿用 collect._candidate_tables；坐标归一化后仍标注原始 space，
不把 source/rectified 混为一谈。所有内容共享字符预算，长文档按页截断。
"""
from .. import collect

DEFAULT_BUDGET = 12000
SAMPLE_ROWS = 3


def _xyxy(box):
    if not isinstance(box, (list, tuple)) or not box:
        return None
    if len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
        x0, y0, x1, y1 = box
    elif all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in box):
        xs = [p[0] for p in box if isinstance(p[0], (int, float))]
        ys = [p[1] for p in box if isinstance(p[1], (int, float))]
        if len(xs) != len(box) or len(ys) != len(box):
            return None
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    else:
        return None
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def _position(box, size, space):
    rect = _xyxy(box)
    if rect is None or not isinstance(size, (list, tuple)) or len(size) < 2:
        return None
    w, h = size[:2]
    if not isinstance(w, (int, float)) or not isinstance(h, (int, float)) \
            or w <= 0 or h <= 0:
        return None
    return {'space': space or 'source',
            'bbox': [round(v, 3) for v in rect],
            'norm': [round(rect[0] / w, 4), round(rect[1] / h, 4),
                     round(rect[2] / w, 4), round(rect[3] / h, 4)]}


def _sample_indexes(count):
    if count <= SAMPLE_ROWS:
        return list(range(count))
    return sorted({0, (count - 1) // 2, count - 1})


def _cell_boxes(cells, page=None):
    for row in cells or []:
        for cell in row:
            if isinstance(cell, dict):
                if page is None or cell.get('page') == page:
                    yield cell.get('bbox')
            else:
                yield cell


def _table_bbox(table, page=None):
    boxes = [b for b in _cell_boxes(table.get('cells'), page)
             if _xyxy(b) is not None]
    if not boxes:
        return None
    rects = [_xyxy(b) for b in boxes]
    return [min(b[0] for b in rects), min(b[1] for b in rects),
            max(b[2] for b in rects), max(b[3] for b in rects)]


def _neighbors(ref, regions):
    current = next((r for r in regions if r['ref'] == ref), None)
    if not current or not current.get('norm'):
        return {}
    x0, y0, x1, y1 = current['norm']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    found = {}
    for other in regions:
        if other['ref'] == ref or not other.get('norm') \
                or other.get('space') != current.get('space'):
            continue
        ox0, oy0, ox1, oy1 = other['norm']
        ocx, ocy = (ox0 + ox1) / 2, (oy0 + oy1) / 2
        candidates = []
        if oy1 <= y0:
            candidates.append('above')
        if oy0 >= y1:
            candidates.append('below')
        if ox1 <= x0:
            candidates.append('left')
        if ox0 >= x1:
            candidates.append('right')
        for direction in candidates:
            distance = (ocx - cx) ** 2 + (ocy - cy) ** 2
            if direction not in found or distance < found[direction][0]:
                found[direction] = (distance, other['ref'])
    return {k: v[1] for k, v in found.items()}


def _page_map(page, page_tables):
    pindex = page.get('index')
    size = page.get('size')
    space = page.get('space') or 'source'
    blocks = []
    for i, block in enumerate(page.get('blocks') or []):
        item = {'ref': 'p{}.b{}'.format(pindex, i),
                'role': block.get('role'), 'text': str(block.get('text') or ''),
                'position': _position(block.get('bbox'), size, space)}
        if item['position']:
            blocks.append(item)
    texts = []
    for i, line in enumerate(page.get('texts') or []):
        item = {'ref': 'p{}.x{}'.format(pindex, i),
                'text': str(line.get('text') or ''),
                'position': _position(line.get('box'), size, space)}
        if item['position']:
            texts.append(item)
    tables = []
    for table_id, table in page_tables:
        coord = table.get('coord') or {}
        tspace = coord.get('space') or space
        tsize = page.get('rectified_size') if tspace == 'rectified' else size
        region = {'ref': table_id, 'kind': 'table',
                  'position': _position(_table_bbox(
                      table, pindex if table_id.startswith('stitched.') else None),
                      tsize, tspace)}
        if region['position']:
            tables.append(region)
    regions = []
    for group in (blocks, texts, tables):
        for item in group:
            region = {'ref': item['ref'], 'kind': item.get('role') or
                      ('text' if group is texts else 'table'), 'space': '',
                      'norm': None}
            region.update(item['position'])
            regions.append(region)
    regions.sort(key=lambda r: ((r['norm'] or [0, 0])[1],
                                (r['norm'] or [0, 0])[0], r['ref']))
    return {'index': pindex, 'size': size, 'rectified_size': page.get('rectified_size'),
            'space': space, 'route': page.get('route'),
            'table_count': len(page.get('tables') or []),
            'blocks': blocks, 'texts': texts, 'tables': tables,
            'regions': regions}


def doc_to_context(doc, budget=DEFAULT_BUDGET):
    """c1-structure 信封 → 旧版上下文键 + document_map；纯函数，不改输入。"""
    doc = doc or {}
    pages = doc.get('pages') or []
    cands = collect._candidate_tables(doc)
    tables = []
    table_meta = {}
    page_tables = {p.get('index'): [] for p in pages}
    for t, scope, ti, page_default in cands:
        table_id = 'p{}.t{}'.format(page_default, ti) if scope == 'page' \
            else 'stitched.t{}'.format(ti)
        headers = [str(h or '') for h in (t.get('headers') or [])]
        rows = t.get('rows') or []
        picked = _sample_indexes(len(rows))
        samples = [[str(c or '') for c in rows[i]] for i in picked]
        item = {'ref': 't{}'.format(ti), 'id': table_id, 'index': ti,
                'scope': scope, 'page': page_default, 'headers': headers,
                'samples': samples, 'row_count': len(rows),
                'sample_rows': picked}
        table_meta[table_id] = item
        tables.append(item)
        if scope == 'page':
            page_tables[page_default].append((table_id, t))

    for si, t in enumerate(doc.get('stitched_tables') or []):
        table_id = 'stitched.t{}'.format(si)
        for part in t.get('parts') or []:
            if part.get('page') in page_tables:
                page_tables[part['page']].append((table_id, t))

    maps = []
    for pg in pages:
        pmap = _page_map(pg, page_tables.get(pg.get('index'), []))
        for region in pmap['regions']:
            if region['kind'] == 'table':
                table_meta[region['ref']]['neighbors'] = _neighbors(
                    region['ref'], pmap['regions'])
        for region in pmap['tables']:
            item = table_meta[region['ref']]
            item.setdefault('positions', []).append({
                'page': pg.get('index'), **region['position']})
            if 'position' not in item:
                item['position'] = region['position']
        maps.append(pmap)

    out_tables = []
    map_pages = []
    used = 0
    truncated = False
    for item in tables:
        chunk = len(str(item))
        if used + chunk > budget:
            truncated = True
            continue
        out_tables.append(item)
        used += chunk
    for pmap in maps:
        chunk = len(str(pmap))
        if used + chunk > budget:
            truncated = True
            continue
        map_pages.append(pmap)
        used += chunk
    if len(out_tables) != len(tables) or len(map_pages) != len(maps):
        truncated = True

    texts = []
    for pg in pages:
        lines = pg.get('texts') or []
        for i in _sample_indexes(len(lines)):
            text = str((lines[i] or {}).get('text') or '')
            if text.strip():
                texts.append('p{}: {}'.format(pg.get('index'), text))
    hint = '\n'.join(texts)
    if len(hint) > 1200:
        hint = hint[:1200]
        truncated = True
    if used + len(hint) > budget:
        truncated = True
    return {
        'shape': {'page_count': len(pages), 'table_count': len(cands),
                  'kind': (doc.get('file') or {}).get('kind')},
        'tables': out_tables, 'text_hint': hint, 'truncated': truncated,
        'document_map': {'pages': map_pages,
                         'omitted_pages': len(maps) - len(map_pages),
                         'omitted_tables': len(tables) - len(out_tables)},
    }


def render_context(ctx):
    """上下文渲染为 prompt 文本片段（与 doc_to_context 配套，纯函数）。"""
    lines = ['文档形状：{}'.format(ctx.get('shape') or {})]
    for t in ctx.get('tables') or []:
        lines.append('表 {}（id={}, scope={}, page={}, {}行）：'.format(
            t['ref'], t.get('id', t['ref']), t.get('scope'), t.get('page'),
            t.get('row_count')))
        if t.get('position'):
            lines.append('  位置：{}'.format(t['position']))
        if t.get('neighbors'):
            lines.append('  相邻区域：{}'.format(t['neighbors']))
        lines.append('  列名：{}'.format(t.get('headers')))
        picked = t.get('sample_rows') or list(range(len(t.get('samples') or [])))
        for row_index, row in zip(picked, t.get('samples') or []):
            lines.append('  样例[第{}行]：{}'.format(row_index, row))
    if ctx.get('text_hint'):
        lines.append('文本行：\n{}'.format(ctx['text_hint']))
    doc_map = ctx.get('document_map') or {}
    if doc_map.get('pages'):
        lines.append('文档地图（norm=[左,上,右,下]，相对各坐标空间页面）：')
        for pg in doc_map['pages']:
            lines.append('  第{}页 size={} space={} route={}：'.format(
                pg.get('index'), pg.get('size'), pg.get('space'), pg.get('route')))
            lines.append('    区域顺序：{}'.format([
                (r['ref'], r['kind'], r.get('norm')) for r in pg.get('regions') or []]))
            for block in pg.get('blocks') or []:
                lines.append('    块 {} {} norm={} 文本={}'.format(
                    block['ref'], block.get('role'),
                    (block.get('position') or {}).get('norm'), block['text']))
            for text in pg.get('texts') or []:
                lines.append('    文字 {} norm={} 文本={}'.format(
                    text['ref'], (text.get('position') or {}).get('norm'), text['text']))
            for table in pg.get('tables') or []:
                lines.append('    表 {} norm={}'.format(
                    table['ref'], (table.get('position') or {}).get('norm')))
    if doc_map.get('omitted_pages') or doc_map.get('omitted_tables'):
        lines.append('预算截断：省略{}页、{}张表。'.format(
            doc_map.get('omitted_pages', 0), doc_map.get('omitted_tables', 0)))
    if ctx.get('truncated'):
        lines.append('上下文因预算不足已截断。')
    return '\n'.join(lines)
