"""抽取层公共纯函数：文本归一、坐标转换、锚点构造与去重。

锚点 dict 的键与 collect._anchor 完全一致：
{page, table_index, table_scope, space, cell_bbox, raw_text}
不新增键，保证现有血缘查看器与 staging_lineage 写入零改动。
"""
import json
import re

from c1_structure import collect


def as_text(value):
    if value is None:
        return ''
    return value if isinstance(value, str) else str(value)


def box_to_bbox(box):
    """四点 polygon（texts[].box）或扁平 bbox（blocks[].bbox）→ [x0,y0,x1,y1]。"""
    if not isinstance(box, (list, tuple)) or not box:
        return None
    if len(box) >= 4 and all(isinstance(p, (list, tuple)) and len(p) >= 2
                             for p in box[:4]):
        xs = [float(p[0]) for p in box[:4]]
        ys = [float(p[1]) for p in box[:4]]
        return [min(xs), min(ys), max(xs), max(ys)]
    flat = []
    for p in box:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            flat.extend((float(p[0]), float(p[1])))
        else:
            flat.append(float(p))
    if len(flat) < 4:
        return None
    return [min(flat[0::2]), min(flat[1::2]),
            max(flat[0::2]), max(flat[1::2])]


def make_anchor(page, space, bbox, raw, table_index=None, table_scope=None):
    return {'page': page, 'table_index': table_index,
            'table_scope': table_scope, 'cell_bbox': bbox,
            'space': space, 'raw_text': as_text(raw)}


def dedupe_anchors(anchors):
    """按内容去重（bbox 是 list 不可哈希，故用 JSON 串作键），保持首次顺序。"""
    out, seen = [], set()
    for a in anchors or []:
        if not isinstance(a, dict):
            continue
        key = json.dumps(a, sort_keys=True, ensure_ascii=False, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def pick_column(keys, sel):
    """列选择器：name / index / header_contains / header_regex，未命中返回 None。"""
    sel = sel or {}
    name = sel.get('name')
    if name is not None:
        return keys.index(name) if name in keys else None
    idx = sel.get('index')
    if isinstance(idx, int):
        return idx if 0 <= idx < len(keys) else None
    kw = sel.get('header_contains')
    if kw:
        for i, k in enumerate(keys):
            if str(kw) in str(k):
                return i
        return None
    pattern = sel.get('header_regex')
    if pattern:
        for i, k in enumerate(keys):
            if re.search(str(pattern), str(k)):
                return i
    return None


def resolve_tables(ctx, source=None):
    """按 ref 解析候选表；scope=all 的 ref 可能是列表，统一返回表元组列表。"""
    by_ref = ctx.get('tables_by_ref') or {}
    if source:
        picked = by_ref.get(source)
        if picked is None:
            return []
        if isinstance(picked, list):
            return [p for p in picked if p]
        return [picked]
    t = ctx.get('table')
    if t is None:
        return []
    return [(t, ctx.get('table_scope'), ctx.get('table_index'),
             ctx.get('page_default'))]


def cell_anchor(t, scope, ti, r, c, value, page_default):
    """表格格锚点统一走 collect._anchor，避免两套形状。"""
    return collect._anchor(scope, t, ti, t.get('cells') or [],
                           r, c, value, page_default)


def merge_anchors(*groups):
    out = []
    for group in groups:
        out.extend(group or [])
    return out


def anchors_of(ctx, names):
    """取已算字段的锚点，供 concat/template/coalesce 合并血缘。"""
    lineage = ctx.get('lineage') or {}
    return merge_anchors(*(lineage.get(n) or [] for n in names))
