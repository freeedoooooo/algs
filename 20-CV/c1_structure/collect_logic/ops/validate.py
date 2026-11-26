"""声明式校验算子：只评估、只标记，绝不改值。

与 transform 族的区别：校验算子不进 pipeline，由字段的 validate 数组消费；
返回值是 issue 标记（字符串）而非新值，由引擎汇总进 record.review.reason。
未知 op 显式报错，与 apply_pipeline 对未知抽取算子的处理保持一致。
"""
import re

from .._common import as_text

VALIDATORS = {}


def _reg(name):
    def deco(fn):
        if name in VALIDATORS:
            raise ValueError('校验算子重复注册: {}'.format(name))
        VALIDATORS[name] = fn
        return fn
    return deco


def _empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


@_reg('required')
def _required(ctx, args, value):
    return 'required' if _empty(value) else None


@_reg('regex')
def _regex(ctx, args, value):
    pattern = str((args or {}).get('pattern') or '')
    if not pattern or _empty(value):
        return None
    return None if re.search(pattern, as_text(value)) else 'regex'


@_reg('enum')
def _enum(ctx, args, value):
    allowed = (args or {}).get('values') or []
    if _empty(value):
        return None
    return None if as_text(value) in {as_text(v) for v in allowed} else 'enum'


@_reg('range')
def _range(ctx, args, value):
    if _empty(value):
        return None
    args = args or {}
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 'range'
    lo, hi = args.get('min'), args.get('max')
    if lo is not None and num < float(lo):
        return 'range'
    if hi is not None and num > float(hi):
        return 'range'
    return None


@_reg('cross_field')
def _cross_field(ctx, args, value):
    """跨字段关系：other 字段名 + cmp（=,!=,>,<,>=,<=）表示比较符。

    比较符字段必须叫 cmp 而非 op——op 已被算子名占用（step['op']='cross_field'），
    若复用会被 run_validates 当成算子名解析。数值比较失败记 issue。
    """
    args = args or {}
    other = (ctx.get('values') or {}).get(args.get('other'))
    if _empty(value) or _empty(other):
        return None
    cmp_ = str(args.get('cmp') or '=')
    try:
        a, b = float(value), float(other)
    except (TypeError, ValueError):
        return 'cross_field'
    checks = {'=': a == b, '!=': a != b, '>': a > b,
              '<': a < b, '>=': a >= b, '<=': a <= b}
    if cmp_ not in checks:
        raise ValueError('cross_field 未知比较符: {}'.format(cmp_))
    return None if checks[cmp_] else 'cross_field'


def run_validates(field, ctx, value):
    """按字段 validate 数组顺序评估，返回 issue 标记列表（只标记不改值）。"""
    out = []
    for step in (field or {}).get('validate') or []:
        if not isinstance(step, dict):
            continue
        op = step.get('op')
        fn = VALIDATORS.get(op)
        if fn is None:
            raise ValueError('未知校验算子: {}'.format(op))
        issue = fn(ctx, step, value)
        if issue:
            out.append(issue)
    return out
