"""取值族算子：cell / row / block / page_text（kind=source，产出锚点）。"""
from c1_structure import collect
from .._common import (as_text, cell_anchor, make_anchor, pick_column,
                       resolve_tables)
from ..registry import register


@register('cell', kind='source')
def op_cell(ctx, args, value, anchors):
    """按列表取当前行（或指定行）的单元格；scope=all 时取第一张命中表。"""
    args = args or {}
    tables = resolve_tables(ctx, args.get('source'))
    row_sel = args.get('row', 'current')
    for t, scope, ti, page_default in tables:
        t = t or {}
        keys = collect._keys(t.get('headers'))
        col = pick_column(keys, args.get('column'))
        if col is None:
            continue
        rows = t.get('rows') or []
        if isinstance(row_sel, int) and not isinstance(row_sel, bool):
            r = row_sel
            row = rows[r] if 0 <= r < len(rows) else []
        else:
            r = ctx.get('row_index', 0)
            row = ctx.get('row') or []
        v = row[col] if col < len(row) else ''
        return v, [cell_anchor(t, scope, ti, r, col, v, page_default)], {}
    return '', [], {'issues': ['cell_not_found']}


@register('row', kind='source')
def op_row(ctx, args, value, anchors):
    """取整行（供组合算子使用），返回行内所有格的锚点。"""
    row = ctx.get('row') or []
    t = ctx.get('table') or {}
    r = ctx.get('row_index', 0)
    anchors = [collect._anchor(ctx.get('table_scope'), t,
                               ctx.get('table_index'), t.get('cells') or [],
                               r, c, v, ctx.get('page_default'))
               for c, v in enumerate(row)]
    return list(row), anchors, {}


def _page(ctx, args):
    pages = ctx.get('doc', {}).get('pages') or []
    want = (args or {}).get('page')
    if want is not None:
        for pg in pages:
            if pg.get('index') == want:
                return pg
        return {}
    return ctx.get('page') or (pages[0] if pages else {})


@register('block', kind='source')
def op_block(ctx, args, value, anchors):
    """按 role / contains / index 取版面块文本，锚点为块 bbox。"""
    args = args or {}
    pg = _page(ctx, args)
    role, contains, idx = (args.get('role'), args.get('contains'),
                           args.get('index'))
    for i, b in enumerate(pg.get('blocks') or []):
        text = as_text(b.get('text'))
        if role and b.get('role') != role:
            continue
        if contains and str(contains) not in text:
            continue
        if idx is not None and i != idx:
            continue
        anchor = make_anchor(pg.get('index'), pg.get('space'),
                             b.get('bbox'), text)
        return text, [anchor], {}
    return '', [], {'issues': ['block_not_found']}


@register('page_text', kind='source')
def op_page_text(ctx, args, value, anchors):
    """取整页 plain_text；页级锚点无 bbox（前端显示“无源”）。"""
    pg = _page(ctx, args)
    text = as_text(pg.get('plain_text'))
    anchor = make_anchor(pg.get('index'), pg.get('space'), None, text)
    return text, [anchor], {}
