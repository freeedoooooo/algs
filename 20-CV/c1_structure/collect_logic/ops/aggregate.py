"""跨表算子：sum / count / join / link。

所有跨表读取都通过 tables 的 ref 解析（cell.source / join.source 同规则），
锚点来自两侧真实单元格，合并后按内容去重；不产生“无源”的凭空值。
"""
from c1_structure import collect
from .._common import (as_text, cell_anchor, merge_anchors, pick_column,
                       resolve_tables)
from ..registry import register


def _row_match(keys, row, where):
    if not where:
        return True
    col = pick_column(keys, where.get('column'))
    if col is None or col >= len(row):
        return False
    return as_text(row[col]) == as_text(where.get('equals'))


def _cells(ctx, source, column, where=None):
    """目标表中符合 where 的指定列 (值, 锚点) 列表。"""
    out = []
    for t, scope, ti, page_default in resolve_tables(ctx, source):
        t = t or {}
        keys = collect._keys(t.get('headers'))
        col = pick_column(keys, column)
        if col is None:
            continue
        for r, row in enumerate(t.get('rows') or []):
            if not _row_match(keys, row, where):
                continue
            v = row[col] if col < len(row) else ''
            out.append((v, cell_anchor(t, scope, ti, r, col, v, page_default)))
    return out


@register('sum')
def op_sum(ctx, args, value, anchors):
    args = args or {}
    strip = str(args.get('strip') or '')
    total, used = 0.0, []
    for raw, anchor in _cells(ctx, args.get('source'),
                              args.get('column'), args.get('where')):
        text = as_text(raw)
        for ch in strip:
            text = text.replace(ch, '')
        try:
            total += float(text)
        except ValueError:
            continue
        used.append(anchor)
    number = int(total) if total.is_integer() else total
    return number, used, {'derived': True}


@register('count')
def op_count(ctx, args, value, anchors):
    args = args or {}
    if args.get('column'):
        pairs = [(v, a) for v, a in _cells(
            ctx, args.get('source'), args.get('column'), args.get('where'))
                 if as_text(v)]
        return len(pairs), [a for _v, a in pairs], {'derived': True}
    count, used = 0, []
    for t, scope, ti, page_default in resolve_tables(ctx, args.get('source')):
        t = t or {}
        keys = collect._keys(t.get('headers'))
        for r, row in enumerate(t.get('rows') or []):
            if not _row_match(keys, row, args.get('where')):
                continue
            count += 1
            if keys:
                used.append(cell_anchor(t, scope, ti, r, 0,
                                        row[0] if row else '', page_default))
    return count, used, {'derived': True}


def _left_key(ctx, args, value, anchors):
    """左键取值与锚点：优先已算字段，其次当前行单元格，最后上游值。"""
    cfg = args.get('left') or {}
    field = cfg.get('field')
    if field:
        values = ctx.get('values') or {}
        lineage = ctx.get('lineage') or {}
        anchor = (lineage.get(field) or [None])[0]
        return values.get(field), anchor
    if cfg.get('column'):
        t = ctx.get('table') or {}
        keys = collect._keys(t.get('headers'))
        col = pick_column(keys, cfg.get('column'))
        if col is not None:
            r = ctx.get('row_index', 0)
            row = ctx.get('row') or []
            v = row[col] if col < len(row) else ''
            return v, cell_anchor(t, ctx.get('table_scope'),
                                  ctx.get('table_index'), r, col, v,
                                  ctx.get('page_default'))
    return value, (anchors or [None])[0]


def _match_row(ctx, args, left_value):
    """在 source 表中按 right.column 找第一键相等的行。"""
    source = args.get('source')
    right = args.get('right') or {}
    column = right.get('column') or {'index': 0}
    for picked in resolve_tables(ctx, source):
        t, scope, ti, page_default = picked
        t = t or {}
        keys = collect._keys(t.get('headers'))
        col = pick_column(keys, column)
        if col is None:
            continue
        for r, row in enumerate(t.get('rows') or []):
            v = row[col] if col < len(row) else ''
            if as_text(v) == as_text(left_value):
                return picked, r, row, col, v
    return None


@register('join')
def op_join(ctx, args, value, anchors):
    """按左键取右表 take 列的值，锚点合并左键、右键与取值格。"""
    args = args or {}
    left_value, left_anchor = _left_key(ctx, args, value, anchors)
    hit = _match_row(ctx, args, left_value)
    if hit is None:
        return '', ([left_anchor] if left_anchor else []), {
            'derived': True, 'issues': ['join_no_match']}
    (t, scope, ti, page_default), r, row, key_col, key_value = hit
    take = args.get('take') or {'index': key_col}
    keys = collect._keys(t.get('headers'))
    col = pick_column(keys, take)
    if col is None:
        return '', [left_anchor] if left_anchor else [], {
            'derived': True, 'issues': ['join_take_not_found']}
    v = row[col] if col < len(row) else ''
    return v, merge_anchors(
        [left_anchor] if left_anchor else [],
        [cell_anchor(t, scope, ti, r, key_col, key_value, page_default)],
        [cell_anchor(t, scope, ti, r, col, v, page_default)]), {'derived': True}


@register('link')
def op_link(ctx, args, value, anchors):
    """按左键取右表多列，返回 dict；字段 spec 加 expand=true 可展开进记录。"""
    args = args or {}
    left_value, left_anchor = _left_key(ctx, args, value, anchors)
    hit = _match_row(ctx, args, left_value)
    if hit is None:
        return {}, ([left_anchor] if left_anchor else []), {
            'derived': True, 'issues': ['join_no_match']}
    (t, scope, ti, page_default), r, row, key_col, key_value = hit
    keys = collect._keys(t.get('headers'))
    mapping = args.get('fields') or [{'target': k, 'index': i}
                                     for i, k in enumerate(keys)]
    out, field_anchors, field_originals = {}, {}, {}
    all_anchors = [left_anchor] if left_anchor else []
    all_anchors.append(cell_anchor(t, scope, ti, r, key_col,
                                   key_value, page_default))
    for item in mapping:
        target = item.get('target')
        if not target:
            continue
        col = pick_column(keys, item.get('column') or item)
        if col is None:
            continue
        v = row[col] if col < len(row) else ''
        anchor = cell_anchor(t, scope, ti, r, col, v, page_default)
        out[target] = v
        field_originals[target] = v
        field_anchors[target] = list(all_anchors) + [anchor]
        all_anchors.append(anchor)
    return out, all_anchors, {'derived': True,
                              'field_anchors': field_anchors,
                              'field_originals': field_originals}
