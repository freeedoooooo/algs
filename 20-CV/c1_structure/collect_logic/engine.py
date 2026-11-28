"""抽取引擎：算子管道执行 + 四种记录切分策略（C4）。

策略：row（默认，与老 passthrough 等价）、key_value、group_by、one_per_page。
引擎是纯函数：不读 DB、不写 I/O；records 信封始终是
{index, values, original, lineage, review}。
"""
from .. import collect
from ._common import (as_text, cell_anchor, dedupe_anchors, pick_column)
from .registry import OPS, OP_KINDS
from .ops.validate import run_validates
from .spatial import table_in_region


def _filter_region(cands, doc, region):
    if not region:
        return cands
    pages = doc.get('pages') or []
    out = []
    for cand in cands:
        t, _scope, _ti, page_default = cand
        pg = next((p for p in pages if p.get('index') == page_default), None)
        if pg is None and region.get('page') is not None:
            pg = next((p for p in pages
                       if p.get('index') == region['page']), None)
        if pg is not None and table_in_region(t, pg, page_default, region):
            out.append(cand)
    return out


def _tables_by_ref(doc, spec):
    """tables 选择器 → ref 到候选表的映射（index / header_contains / scope=all）。"""
    cands = collect._candidate_tables(doc)
    selectors = spec.get('tables') or []
    if not selectors:
        return {'main': cands[0] if cands else None}
    by_ref = {}
    for sel in selectors:
        ref = sel.get('ref') or 'main'
        picked = None
        idx = sel.get('index')
        if isinstance(idx, int) and not isinstance(idx, bool):
            picked = cands[idx] if 0 <= idx < len(cands) else None
        elif sel.get('header_contains'):
            kw = str(sel['header_contains'])
            for c in cands:
                head = ' '.join(str(h or '') for h in (c[0].get('headers') or []))
                if kw in head:
                    picked = c
                    break
        elif sel.get('scope') == 'all':
            picked = list(cands)
        elif sel.get('region'):
            picked = list(cands)
        if picked:
            many = isinstance(picked, list)
            filtered = _filter_region(
                picked if many else [picked], doc, sel.get('region'))
            picked = filtered if many else (filtered[0] if filtered else None)
        by_ref[ref] = picked
    return by_ref


def apply_pipeline(pipeline, ctx, value=None, anchors=None):
    """顺序执行算子；返回 (value, anchors, meta)。

    meta.original = 第一个 source 算子的原始值（回流归因的前提）；
    meta.derived = 管道里是否出现过变换算子；issues 供上层诊断，本期不写 review。
    """
    value = value
    anchors = list(anchors or [])
    original = None
    issues = []
    steps = pipeline or []
    for step in steps:
        op = step.get('op') if isinstance(step, dict) else None
        fn = OPS.get(op)
        if fn is None:
            raise ValueError('未知抽取算子: {}'.format(op))
        value, new_anchors, meta = fn(ctx, step, value, anchors)
        anchors = list(new_anchors or [])
        if OP_KINDS.get(op) == 'source' and original is None:
            original = value
        issues.extend((meta or {}).get('issues') or [])
    derived = any(OP_KINDS.get(s.get('op')) != 'source'
                  for s in steps if isinstance(s, dict))
    return value, anchors, {'original': original, 'derived': derived,
                            'issues': issues}


def _record_from_ctx(ctx, fields):
    """在给定上下文上执行所有字段管道，产出一条无 index 的记录。

    校验只写 review.reason，不改值、不改 review.state；存量字段无 validate
    时 reason 为空列表，records 信封多一个空键但不影响任何下游。
    """
    values, original, lineage, reasons = {}, {}, {}, {}
    for field in fields:
        value, anchors, meta = apply_pipeline(field.get('pipeline') or [], ctx)
        target = field['target']
        issues = run_validates(field, ctx, value)
        if issues:
            reasons[target] = issues
        if isinstance(value, dict) and field.get('expand'):
            # link 算子：把关联表的多列展开进同一条记录
            field_anchors = meta.get('field_anchors') or {}
            field_originals = meta.get('field_originals') or {}
            for key, val in value.items():
                values[key] = val
                original[key] = field_originals.get(key, val)
                lineage[key] = dedupe_anchors(field_anchors.get(key) or anchors)
                ctx['values'][key] = val
                ctx['lineage'][key] = lineage[key]
            continue
        values[target] = value
        original[target] = meta.get('original', value)
        lineage[target] = dedupe_anchors(anchors)
        ctx['values'][target] = value
        ctx['lineage'][target] = lineage[target]
    rec = {'values': values, 'original': original, 'lineage': lineage,
           'review': {'state': 'pending', 'at': None}}
    if reasons:
        rec['review']['reason'] = reasons
    return rec


def _finalize(records):
    for i, record in enumerate(records):
        record['index'] = i
    return records


def _iter_table_ctxs(doc, by_ref, cands=None):
    """按 passthrough 的候选表顺序逐行产出上下文；cands 可限定表集合。"""
    cands = cands if cands is not None else collect._candidate_tables(doc)
    pages = doc.get('pages') or []
    page0 = pages[0] if pages else {}
    for t, scope, ti, page_default in cands:
        pg = page0
        if page_default is not None:
            pg = next((p for p in pages if p.get('index') == page_default), page0)
        for r, row in enumerate(t.get('rows') or []):
            yield {'doc': doc, 'page': pg, 'page_index': pg.get('index'),
                   'table': t, 'table_scope': scope, 'table_index': ti,
                   'page_default': page_default, 'row': row, 'row_index': r,
                   'tables_by_ref': by_ref, 'values': {}, 'lineage': {}}


def _restricted_cands(doc, spec):
    """简单规则译为 v2 时限定仅所选表产出记录；旧 spec 无 restrict 不受影响。"""
    for sel in spec.get('tables') or []:
        if not isinstance(sel, dict) or not sel.get('restrict'):
            continue
        cands = collect._candidate_tables(doc)
        idx = sel.get('index')
        if isinstance(idx, int) and not isinstance(idx, bool):
            picked = [cands[idx]] if 0 <= idx < len(cands) else []
        elif sel.get('header_contains'):
            kw = sel['header_contains']
            picked = [c for c in cands
                      if str(kw) in ' '.join(str(h or '')
                                             for h in (c[0].get('headers') or []))]
        else:
            picked = cands
        return _filter_region(picked, doc, sel.get('region'))
    return None


def _record_cands(doc, spec, by_ref):
    """解析记录驱动表；显式 source_ref/record_source 不允许静默回退到全表。"""
    cfg = spec.get('records') or {}
    ref = cfg.get('source_ref')
    if ref:
        picked = by_ref.get(ref)
        if not picked:
            raise ValueError('records.source_ref 未命中表: {}'.format(ref))
        return list(picked) if isinstance(picked, list) else [picked]
    role_refs = [s.get('ref') or 'main' for s in spec.get('tables') or []
                 if isinstance(s, dict) and s.get('role') == 'record_source']
    if len(role_refs) > 1:
        raise ValueError('多条 record_source 必须通过 records.source_ref 指定')
    if role_refs:
        picked = by_ref.get(role_refs[0])
        if not picked:
            raise ValueError('record_source 未命中表: {}'.format(role_refs[0]))
        return list(picked) if isinstance(picked, list) else [picked]
    return None


def _records_row(doc, spec, fields, by_ref):
    """默认策略：无 fields 时直接复用老 passthrough，逐字段完全相等。"""
    if not fields:
        if _record_cands(doc, spec, by_ref) is not None:
            raise ValueError('无 fields 的 row 规则不能指定记录来源')
        return collect.passthrough(doc)
    picked = _record_cands(doc, spec, by_ref)
    if picked is None:
        picked = _restricted_cands(doc, spec)
    return _finalize([_record_from_ctx(ctx, fields)
                      for ctx in _iter_table_ctxs(doc, by_ref, picked)])


def _records_key_value(doc, spec, fields, by_ref):
    """左列键、右列值 → 每张表一条记录（审计附表常见）。"""
    cfg = spec.get('records') or {}
    key_sel = cfg.get('key_column') or {'index': 0}
    value_sel = cfg.get('value_column') or {'index': 1}
    records = []
    cands = _record_cands(doc, spec, by_ref)
    if cands is None:
        cands = collect._candidate_tables(doc)
    for t, scope, ti, page_default in cands:
        keys = collect._keys(t.get('headers'))
        kc, vc = pick_column(keys, key_sel), pick_column(keys, value_sel)
        if kc is None or vc is None:
            continue
        values, original, lineage = {}, {}, {}
        for r, row in enumerate(t.get('rows') or []):
            name = as_text(row[kc] if kc < len(row) else '')
            val = row[vc] if vc < len(row) else ''
            lineage.setdefault(name, []).append(
                cell_anchor(t, scope, ti, r, vc, val, page_default))
            values[name], original[name] = val, val
        if not values:
            continue
        records.append({
            'values': values, 'original': original,
            'lineage': {k: dedupe_anchors(v) for k, v in lineage.items()},
            'review': {'state': 'pending', 'at': None}})
    return _finalize(records)


def _records_group_by(doc, spec, fields, by_ref):
    """按字段分组：组内多行 → 一条记录，其他字段成数组；锚点合并去重。"""
    names = (spec.get('records') or {}).get('group_by') or []
    if not names:
        raise ValueError('group_by 策略需要至少 1 个字段')
    groups = {}
    for rec in _records_row(doc, spec, fields, by_ref):
        key = tuple(as_text(rec['values'].get(n)) for n in names)
        groups.setdefault(key, []).append(rec)
    records = []
    for group in groups.values():
        first = group[0]
        values, original, lineage = {}, {}, {}
        for name in first['values']:
            seq = [r['values'].get(name) for r in group]
            if name in names:
                values[name] = seq[0]
                original[name] = group[0]['original'].get(name)
            else:
                values[name] = seq
                original[name] = [r['original'].get(name) for r in group]
            lineage[name] = dedupe_anchors(
                [a for r in group for a in (r['lineage'].get(name) or [])])
        records.append({'values': values, 'original': original,
                        'lineage': lineage,
                        'review': {'state': 'pending', 'at': None}})
    return _finalize(records)


def _records_one_per_page(doc, spec, fields, by_ref):
    """每页一条记录；无 fields 时填 page_text，非表格 kv 规则走这里。"""
    pages = doc.get('pages') or []
    cands = collect._candidate_tables(doc)
    driver = _record_cands(doc, spec, by_ref) if fields else None
    records = []
    for pg in pages:
        page_cands = [c for c in (driver or cands)
                      if c[3] in (None, pg.get('index'))]
        picked = page_cands[0] if page_cands else None
        ctx = {'doc': doc, 'page': pg, 'page_index': pg.get('index'),
               'table': picked[0] if picked else None,
               'table_scope': picked[1] if picked else None,
               'table_index': picked[2] if picked else None,
               'page_default': pg.get('index'), 'row': None, 'row_index': 0,
               'page_only': True, 'tables_by_ref': by_ref,
               'values': {}, 'lineage': {}}
        if fields:
            rec = _record_from_ctx(ctx, fields)
        else:
            value, anchors, _meta = apply_pipeline([{'op': 'page_text'}], ctx)
            rec = {'values': {'text': value}, 'original': {'text': value},
                   'lineage': {'text': dedupe_anchors(anchors)},
                   'review': {'state': 'pending', 'at': None}}
        records.append(rec)
    return _finalize(records)


def build_logic(doc, tpl=None):
    """spec_version=2 入口：c1-structure 信封 → records（信封形态不变）。"""
    doc = doc or {}
    spec = ((tpl or {}).get('extraction_spec_json') or {})
    fields = [f for f in (spec.get('fields') or [])
              if isinstance(f, dict) and f.get('target')]
    by_ref = _tables_by_ref(doc, spec)
    strategy = (spec.get('records') or {}).get('strategy') or 'row'
    handlers = {'row': _records_row, 'key_value': _records_key_value,
                'group_by': _records_group_by,
                'one_per_page': _records_one_per_page}
    handler = handlers.get(strategy)
    if handler is None:
        raise ValueError('未知记录切分策略: {}'.format(strategy))
    return handler(doc, spec, fields, by_ref)
