"""组合族算子：concat / template / coalesce / lookup（字典内联在规则里）。

依赖上游已算字段：build_logic 在 ctx.values / ctx.lineage 中维护字段值与其锚点，
本族算子合并这些锚点，保证组合值的血缘可回溯到各来源格。
"""
import re

from .._common import anchors_of, as_text, merge_anchors
from ..registry import register


@register('concat')
def op_concat(ctx, args, value, anchors):
    args = args or {}
    names = args.get('fields') or []
    values = ctx.get('values') or {}
    text = str(args.get('sep', '')).join(as_text(values.get(n)) for n in names)
    return text, merge_anchors(anchors, anchors_of(ctx, names)), {'derived': True}


@register('template')
def op_template(ctx, args, value, anchors):
    args = args or {}
    pattern = str(args.get('pattern') or '')
    names = re.findall(r'\{([^{}]+)\}', pattern)
    values = ctx.get('values') or {}
    text = pattern
    for name in names:
        text = text.replace('{' + name + '}', as_text(values.get(name)))
    return text, merge_anchors(anchors, anchors_of(ctx, names)), {'derived': True}


@register('coalesce')
def op_coalesce(ctx, args, value, anchors):
    names = (args or {}).get('fields') or []
    values = ctx.get('values') or {}
    for name in names:
        if as_text(values.get(name)):
            return (values[name],
                    merge_anchors(anchors, anchors_of(ctx, [name])),
                    {'derived': True})
    return '', anchors, {'derived': True}


@register('lookup')
def op_lookup(ctx, args, value, anchors):
    args = args or {}
    field = args.get('field')
    key = (ctx.get('values') or {}).get(field) if field else value
    table = {str(k): v for k, v in (args.get('dict') or {}).items()}
    out = table.get(as_text(key), args.get('default', ''))
    return out, anchors, {'derived': True}
