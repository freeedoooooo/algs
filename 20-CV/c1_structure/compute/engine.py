"""compute/engine.py — 计算层纯引擎（index / rule / frame）。

极简设计（2026-11-26）：只做运算，返回结果文本；不采行锚点、不存输入明细、
不算哈希。参与计算的对象从定义表推导；业务库读走 store.loader（白名单 +
参数化 + 标识符转义）。
"""
from decimal import Decimal, InvalidOperation

from ..store import loader
from ..store.catalog import get_datasource
from ..store.errors import BadRequest, NotFound

_FILTER_OP = {'eq': '=', 'ne': '<>', 'gt': '>', 'gte': '>=',
              'lt': '<', 'lte': '<='}
_RULE_OP = ('gt', 'gte', 'lt', 'lte', 'eq', 'ne', 'between')
_COMBINE = ('weighted', 'all_pass', 'any_pass', 'veto')


def _num(value, what='数值'):
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        raise BadRequest('{} 不是有效数值：{}'.format(what, value))


def _where(filter_json, allow_cols=None):
    clauses, args = [], []
    for f in filter_json or []:
        col, op, val = f.get('column'), f.get('op'), f.get('value')
        if allow_cols is not None and col not in allow_cols:
            raise BadRequest('过滤列不在表列白名单内：{}'.format(col))
        if op == 'between':
            if not isinstance(val, (list, tuple)) or len(val) != 2:
                raise BadRequest('between 须给两个边界值')
            clauses.append('{} BETWEEN %s AND %s'.format(loader._ident(col)))
            args.extend(val)
        elif op in _FILTER_OP:
            if val is None:
                clauses.append('{} IS NULL'.format(loader._ident(col)))
            else:
                clauses.append('{} {} %s'.format(loader._ident(col),
                                                 _FILTER_OP[op]))
                args.append(val)
        else:
            raise BadRequest('过滤 op 非法：{}'.format(op))
    return (' WHERE ' + ' AND '.join(clauses)) if clauses else '', args


def _check_index_def(defn):
    if defn is None:
        raise NotFound('指标定义不存在')
    ds = get_datasource(defn['datasource_id'])
    if ds is None:
        raise NotFound('指标绑定的业务库不存在')
    table = str(defn['source_table'] or '').strip()
    if table not in loader.list_tables(ds):
        raise BadRequest('业务表不存在：{}'.format(table))
    cols = [c['name'] for c in loader.list_columns(ds, table)]
    column = defn.get('source_column')
    if column and column not in cols:
        raise BadRequest('聚合列不存在：{}'.format(column))
    return ds, table, cols, column


# ---------------- 指标 ----------------

def compute_index(defn):
    """按指标定义聚合业务表，返回结果文本。"""
    ds, table, cols, column = _check_index_def(defn)
    agg = defn['aggregate']
    where, args = _where(defn.get('filter_json') or [], allow_cols=set(cols))
    if agg == 'count':
        expr = 'COUNT(*)'
    elif agg == 'count_distinct':
        expr = 'COUNT(DISTINCT {})'.format(loader._ident(column))
    else:
        expr = '{}({})'.format(
            {'sum': 'SUM', 'avg': 'AVG', 'min': 'MIN',
             'max': 'MAX'}[agg], loader._ident(column))
    conn = loader.connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT {} FROM {}{}'.format(
                expr, loader._ident(table), where), args)
            raw = cur.fetchone()[0]
    finally:
        conn.close()
    if raw is None:
        return '0' if agg in ('count', 'count_distinct') else ''
    return format(raw, 'f') if isinstance(raw, Decimal) else str(raw)


def source_preview(defn, limit=50):
    """返回指标当前筛选命中的总数与有界样本，供配置图下钻血缘。"""
    ds, table, cols, column = _check_index_def(defn)
    limit = max(1, min(50, int(limit or 50)))
    where, args = _where(defn.get('filter_json') or [], allow_cols=set(cols))
    relevant = []
    for name in list(loader.TRACE_COLS) + ([column] if column else []) + [
            f.get('column') for f in defn.get('filter_json') or []]:
        if name in cols and name not in relevant:
            relevant.append(name)
    if not relevant:
        relevant = cols[:1]
    conn = loader.connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM {}{}'.format(
                loader._ident(table), where), args)
            total = int(cur.fetchone()[0])
            cur.execute('SELECT {} FROM {}{} LIMIT %s'.format(
                ','.join(loader._ident(c) for c in relevant),
                loader._ident(table), where), args + [limit])
            rows = cur.fetchall()
        items = []
        for row in rows:
            item = dict(zip(relevant, row))
            for key, value in list(item.items()):
                if hasattr(value, 'isoformat'):
                    item[key] = value.isoformat(sep=' ')
                elif isinstance(value, bytes):
                    item[key] = '<binary {} bytes>'.format(len(value))
            items.append(item)
    finally:
        conn.close()
    trace_columns = [c for c in loader.TRACE_COLS if c in cols]
    return {'source': {'datasource_id': defn['datasource_id'],
                       'source_table': table, 'source_column': column,
                       'aggregate': defn['aggregate'],
                       'filter': defn.get('filter_json') or []},
            'total': total, 'limit': limit, 'has_more': total > len(items),
            'columns': relevant, 'trace_columns': trace_columns, 'items': items}


# ---------------- 规则 ----------------

def _compare(actual, op, threshold):
    a = _num(actual, '指标值')
    if op == 'between':
        if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
            raise BadRequest('between 阈值须为两元素数组')
        lo, hi = _num(threshold[0], '下界'), _num(threshold[1], '上界')
        return lo <= a <= hi
    t = _num(threshold, '阈值')
    return {'gt': a > t, 'gte': a >= t, 'lt': a < t,
            'lte': a <= t, 'eq': a == t, 'ne': a != t}[op]


def compute_rule(defn, index_values):
    """按规则定义比较指标值，返回 'pass' / 'fail'。

    index_values：{alias: value_text}，由编排层按 index_refs 解析。
    """
    if defn is None:
        raise NotFound('规则定义不存在')
    if not isinstance(index_values, dict):
        raise BadRequest('index_values 须为 {alias: value_text} 字典')
    flags = []
    for c in defn['conditions_json']:
        op = c.get('op')
        if op not in _RULE_OP:
            raise BadRequest('比较 op 非法：{}'.format(op))
        alias = c.get('alias')
        if alias not in index_values:
            raise BadRequest('条件引用了未解析的指标别名：{}'.format(alias))
        flags.append(_compare(index_values[alias], op, c.get('threshold')))
    if not flags:
        raise BadRequest('规则没有条件')
    result = (all(flags) if defn['combine'] == 'all' else any(flags))
    return 'pass' if result else 'fail'


# ---------------- 框架 ----------------

def compute_frame(defn, rule_values):
    """按框架定义组合规则结论，返回结果文本（通过/未通过 + 得分）。

    rule_values：[{'outcome': 'pass/fail', 'weight':..., 'veto':...}]
    """
    if defn is None:
        raise NotFound('框架定义不存在')
    combine = defn['combine']
    if combine not in _COMBINE:
        raise BadRequest('组合方式非法：{}'.format(combine))
    if not rule_values:
        raise BadRequest('框架没有关联规则')
    flags = [r['outcome'] == 'pass' for r in rule_values]
    if any(r.get('veto') and not ok for r, ok in zip(rule_values, flags)):
        return 'fail（一票否决）'
    if combine in ('all_pass', 'veto'):
        return 'pass' if all(flags) else 'fail'
    if combine == 'any_pass':
        return 'pass' if any(flags) else 'fail'
    total = sum((_num(r.get('weight', 1)) for r in rule_values), Decimal(0))
    if total == 0:
        raise BadRequest('权重合计为 0，无法计算加权得分')
    gained = sum((_num(r.get('weight', 1)) for r, ok in
                  zip(rule_values, flags) if ok), Decimal(0))
    score = gained / total
    threshold = _num(defn.get('threshold'), '阈值')
    outcome = 'pass' if score >= threshold else 'fail'
    return '{}（{}）'.format(outcome, format(score, 'f'))
