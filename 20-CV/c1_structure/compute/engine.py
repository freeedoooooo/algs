"""compute/engine.py — 计算层纯引擎（index / rule / frame）。

职责：按定义快照执行运算，构造「输入快照 / 依赖快照」供 repo 算 result_hash。
不做 DB 写入；业务库读走 store.loader（白名单 + 参数化 + 标识符转义）。

设计约束（docs/design-index-rule-frame.md §4.3 / §6）：
- 算子固定枚举，拒绝自由 SQL / 表达式；
- 指标同一只读连接内跑聚合 + 明细两条查询，避免中间数据变动；
- 行锚点上限 MAX_INPUT_ROWS，超出置 truncated=True；
- 所有数值比较用 Decimal，避免浮点误差；结果值以字符串保真。
"""
import json
from decimal import Decimal, InvalidOperation

from ..store import loader
from ..store.catalog import get_datasource
from ..store.errors import BadRequest, NotFound

MAX_INPUT_ROWS = 500
_AGG_SQL = {
    'sum': 'SUM',
    'count': 'COUNT',
    'avg': 'AVG',
    'min': 'MIN',
    'max': 'MAX',
    'count_distinct': 'COUNT(DISTINCT',
}
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
    """构造 WHERE 子句（值参数化，列名白名单校验）。返回 (sql, args)。"""
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


# ---------------- 指标 index ----------------

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
    if not hasattr(loader, '_ident'):
        raise BadRequest('存储层标识符转义不可用')
    return ds, table, cols, column


def run_index(defn):
    """执行指标定义 → (value_text, input_rows_snapshot)。

    defn：c1_index_info 一行（filter_json 已反序列化）。
    input_rows：{datasource_id,table,column,filter,rows,truncated,aggregate}。
    """
    ds, table, cols, column = _check_index_def(defn)
    agg = defn['aggregate']
    filters = defn.get('filter_json') or []
    where, wargs = _where(filters, allow_cols=set(cols))
    if agg == 'count':
        expr = 'COUNT(*)'
    elif agg == 'count_distinct':
        expr = 'COUNT(DISTINCT {})'.format(loader._ident(column))
    else:
        expr = '{}({})'.format(_AGG_SQL[agg], loader._ident(column))

    conn = loader.connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT {} FROM {}{}'.format(
                expr, loader._ident(table), where), wargs)
            raw = cur.fetchone()[0]
            # 明细：行锚点采集（同一连接、同一 WHERE）
            sel_cols = 'file_id, record_id'
            if column and column not in ('file_id', 'record_id'):
                sel_cols += ', ' + loader._ident(column)
            cur.execute('SELECT {} FROM {}{}'.format(
                sel_cols, loader._ident(table), where), wargs)
            db_rows = cur.fetchall()
    finally:
        conn.close()

    if raw is None:
        raw_out = '0' if agg in ('count', 'count_distinct') else ''
    elif isinstance(raw, Decimal):
        raw_out = format(raw, 'f')
    else:
        raw_out = str(raw)

    captured, truncated = [], len(db_rows) > MAX_INPUT_ROWS
    for r in db_rows[:MAX_INPUT_ROWS]:
        item = {'file_id': r[0], 'record_id': r[1]}
        if len(r) > 2:
            item['value'] = (format(r[2], 'f') if isinstance(r[2], Decimal)
                             else str(r[2]))
        captured.append(item)
    snapshot = {
        'datasource_id': defn['datasource_id'], 'table': table,
        'column': column, 'aggregate': agg, 'filter': filters,
        'rows': captured, 'truncated': truncated,
        'matched_rows': len(db_rows),
    }
    return raw_out, snapshot


def replay_index(defn, input_rows):
    """用结果自带输入快照重算聚合，返回重算 value_text（不查明细）。"""
    ds, table, cols, column = _check_index_def(defn)
    agg = defn['aggregate']
    where, wargs = _where(input_rows.get('filter') or [], allow_cols=set(cols))
    if agg == 'count':
        expr = 'COUNT(*)'
    elif agg == 'count_distinct':
        expr = 'COUNT(DISTINCT {})'.format(loader._ident(column))
    else:
        expr = '{}({})'.format(_AGG_SQL[agg], loader._ident(column))
    conn = loader.connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT {} FROM {}{}'.format(
                expr, loader._ident(table), where), wargs)
            raw = cur.fetchone()[0]
    finally:
        conn.close()
    if raw is None:
        return '0' if agg in ('count', 'count_distinct') else ''
    return format(raw, 'f') if isinstance(raw, Decimal) else str(raw)


# ---------------- 规则 rule ----------------

def _compare(actual, op, threshold):
    a = _num(actual, '指标值')
    if op == 'between':
        if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
            raise BadRequest('between 阈值须为两元素数组')
        lo, hi = _num(threshold[0], '下界'), _num(threshold[1], '上界')
        return lo <= a <= hi
    t = _num(threshold, '阈值')
    return {
        'gt': a > t, 'gte': a >= t, 'lt': a < t,
        'lte': a <= t, 'eq': a == t, 'ne': a != t,
    }[op]


def run_rule(defn, index_values):
    """执行业务规则 → (outcome, detail_snapshot)。

    index_values：{alias: value_text}，由 app 层按 index_refs 解析后传入。
    这样不依赖列表顺序，别名与条件通过显式键对齐。
    """
    if defn is None:
        raise NotFound('规则定义不存在')
    if not isinstance(index_values, dict):
        raise BadRequest('index_values 须为 {alias: value_text} 字典')
    aliases = dict(index_values)
    detail, passed = [], []
    for c in defn['conditions_json']:
        op = c.get('op')
        if op not in _RULE_OP:
            raise BadRequest('比较 op 非法：{}'.format(op))
        alias = c.get('alias')
        if alias not in aliases:
            raise BadRequest('条件引用了未解析的指标别名：{}'.format(alias))
        ok = _compare(aliases[alias], op, c.get('threshold'))
        passed.append(ok)
        detail.append({'alias': alias, 'op': op,
                       'threshold': c.get('threshold'),
                       'actual': str(aliases[alias]), 'passed': ok})
    outcome = ('all' if defn['combine'] == 'all' else 'any')
    result = all(passed) if outcome == 'all' else any(passed)
    return ('pass' if result else 'fail'), detail


# ---------------- 框架 frame ----------------

def run_frame(defn, rule_outcomes):
    """执行框架组合 → (outcome, score_text_or_None, detail_snapshot)。

    rule_outcomes：[{'rule_value_id':..., 'outcome':'pass/fail', 'weight':..., 'veto':...}]
    """
    if defn is None:
        raise NotFound('框架定义不存在')
    combine = defn['combine']
    if combine not in _COMBINE:
        raise BadRequest('组合方式非法：{}'.format(combine))
    detail = [dict(r) for r in rule_outcomes]
    flags = [r['outcome'] == 'pass' for r in rule_outcomes]
    if any(r.get('veto') and not ok for r, ok in zip(rule_outcomes, flags)):
        return 'fail', None, detail
    if combine == 'all_pass':
        return ('pass' if all(flags) else 'fail'), None, detail
    if combine == 'any_pass':
        return ('pass' if any(flags) else 'fail'), None, detail
    if combine == 'veto':
        return ('pass' if all(flags) else 'fail'), None, detail
    # weighted
    total = sum((_num(r.get('weight', 1)) for r in rule_outcomes), Decimal(0))
    if total == 0:
        raise BadRequest('权重合计为 0，无法计算加权得分')
    gained = sum((_num(r.get('weight', 1)) for r, ok in
                  zip(rule_outcomes, flags) if ok), Decimal(0))
    score = gained / total
    score_text = format(score, 'f')
    threshold = _num(defn.get('threshold'), '阈值')
    outcome = 'pass' if score >= threshold else 'fail'
    for r, ok in zip(detail, flags):
        r['contribution'] = str(_num(r.get('weight', 1)) / total) if ok else '0'
    return outcome, score_text, detail
