"""逻辑族算子：if / switch，按条件选择子管道执行。

子管道递归调用引擎的 apply_pipeline；此处延迟导入避免注册期循环依赖。
"""
from .._common import as_text
from ..registry import register


def _test(cond, ctx, value):
    cond = cond or {}
    values = ctx.get('values') or {}
    left = values.get(cond.get('field')) if cond.get('field') else value
    op = cond.get('op') or 'eq'
    right = cond.get('value')
    if op == 'eq':
        return as_text(left) == as_text(right)
    if op == 'neq':
        return as_text(left) != as_text(right)
    if op == 'contains':
        return as_text(right) in as_text(left)
    if op == 'empty':
        return not as_text(left)
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return False
    return {'gt': a > b, 'gte': a >= b, 'lt': a < b, 'lte': a <= b}.get(op, False)


@register('if')
def op_if(ctx, args, value, anchors):
    args = args or {}
    from ..engine import apply_pipeline
    chosen = args.get('then') if _test(args.get('when'), ctx, value) \
        else (args.get('else') or [])
    return apply_pipeline(chosen, ctx, value, anchors)


@register('switch')
def op_switch(ctx, args, value, anchors):
    args = args or {}
    from ..engine import apply_pipeline
    for case in args.get('cases') or []:
        if _test(case.get('when'), ctx, value):
            return apply_pipeline(case.get('then') or [], ctx, value, anchors)
    return apply_pipeline(args.get('default') or [], ctx, value, anchors)
