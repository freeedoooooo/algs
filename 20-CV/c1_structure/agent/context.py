"""把 parse.json 信封确定性压缩为 prompt 上下文。

只用 collect._candidate_tables 的同一迭代序（非合并页表在前、stitched 在后），
不另造一套；候选表保留 headers + 前 N 行样例 + index/scope/page。
token 预算按字符数截断，不重新 OCR、不重复存储 parse.json。
"""
from .. import collect

DEFAULT_BUDGET = 12000
SAMPLE_ROWS = 3


def doc_to_context(doc, budget=DEFAULT_BUDGET):
    """c1-structure 信封 → {shape, tables, text_hint, truncated}。"""
    doc = doc or {}
    pages = doc.get('pages') or []
    cands = collect._candidate_tables(doc)
    tables = []
    used = 0
    truncated = False
    for t, scope, ti, page_default in cands:
        headers = [str(h or '') for h in (t.get('headers') or [])]
        rows = [[str(c or '') for c in row]
                for row in (t.get('rows') or [])[:SAMPLE_ROWS]]
        item = {'ref': 't{}'.format(ti), 'index': ti, 'scope': scope,
                'page': page_default, 'headers': headers, 'samples': rows,
                'row_count': len(t.get('rows') or [])}
        chunk = len(str(item))
        if used + chunk > budget:
            truncated = True
            break
        tables.append(item)
        used += chunk
    texts = []
    for pg in pages:
        for line in (pg.get('texts') or [])[:SAMPLE_ROWS]:
            text = str((line or {}).get('text') or '')
            if text.strip():
                texts.append('p{}: {}'.format(pg.get('index'), text))
    hint = '\n'.join(texts)
    if len(hint) > 1200:
        hint = hint[:1200]
        truncated = True
    return {
        'shape': {'page_count': len(pages),
                  'table_count': len(cands),
                  'kind': (doc.get('file') or {}).get('kind')},
        'tables': tables, 'text_hint': hint, 'truncated': truncated,
    }


def render_context(ctx):
    """上下文渲染为 prompt 文本片段（与 doc_to_context 配套，纯函数）。"""
    lines = ['文档形状：{}'.format(ctx.get('shape') or {})]
    for t in ctx.get('tables') or []:
        lines.append('表 {}（scope={}, page={}, {}行）：'.format(
            t['ref'], t.get('scope'), t.get('page'), t.get('row_count')))
        lines.append('  列名：{}'.format(t.get('headers')))
        for row in t.get('samples') or []:
            lines.append('  样例：{}'.format(row))
    if ctx.get('text_hint'):
        lines.append('文本行：\n{}'.format(ctx['text_hint']))
    return '\n'.join(lines)
