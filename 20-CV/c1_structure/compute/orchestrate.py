"""compute/orchestrate.py — 计算层编排：定义读取 → 引擎运算 → repo 落库。

极简设计（2026-11-26）：
  · 结果表只存「定义 ID + 结果值 + 时间」；依赖对象从定义推导（取最新结果值）。
  · lineage 返回「参与计算的元数据链」（定义配置），不下钻行锚点。
  · replay 用当前定义重算一次结果，与存储值比对。
"""
from .. import store
from ..store import index_repo, rule_repo, frame_repo
from ..store.errors import BadRequest, NotFound
from . import engine

_LABEL = {'index': '指标', 'rule': '规则', 'frame': '框架'}
_VALUE_FIELD = {'index': 'index_value', 'rule': 'rule_value',
                'frame': 'frame_value'}


def _repo(scope):
    return {'index': index_repo, 'rule': rule_repo,
            'frame': frame_repo}[scope]


def _def(scope, def_id):
    fn = {'index': index_repo.get_def, 'rule': rule_repo.get_def,
          'frame': frame_repo.get_def}[scope]
    key = {'index': 'index_id', 'rule': 'rule_id', 'frame': 'frame_id'}[scope]
    d = fn(**{key: def_id})
    if d is None:
        raise NotFound('{}定义不存在'.format(_LABEL[scope]))
    return d


def _latest(scope, def_id):
    """某定义最近一次结果值（无则 None）。"""
    key = {'index': 'index_id', 'rule': 'rule_id', 'frame': 'frame_id'}[scope]
    vals = _repo(scope).list_values(**{key: def_id, 'limit': 1})
    if not vals:
        return None
    return vals[0][_VALUE_FIELD[scope]]


def execute_index(index_id):
    defn = _def('index', index_id)
    value = engine.compute_index(defn)
    vid = index_repo.add_value(index_id, value)
    return {'def_id': index_id, 'value_id': vid, 'value': value}


def execute_rule(rule_id):
    """从规则定义引用指标，取各指标最新值，比较得结论。"""
    defn = _def('rule', rule_id)
    alias_values = {}
    for ref in defn['index_refs_json']:
        val = _latest('index', ref['index_id'])
        if val is None:
            raise BadRequest('引用的指标 #{} 还没有结果，请先运行指标'.format(
                ref['index_id']))
        alias_values[ref['alias']] = val
    value = engine.compute_rule(defn, alias_values)
    vid = rule_repo.add_value(rule_id, value)
    return {'def_id': rule_id, 'value_id': vid, 'value': value}


def execute_frame(frame_id):
    """从框架定义引用规则，取各规则最新结论，组合得结果。"""
    defn = _def('frame', frame_id)
    rule_values = []
    combine = defn['combine']
    for ref in defn['rule_refs_json']:
        val = _latest('rule', ref['rule_id'])
        if val is None:
            raise BadRequest('引用的规则 #{} 还没有结果，请先运行规则'.format(
                ref['rule_id']))
        outcome = ('pass' if str(val).startswith('pass') else 'fail')
        rule_values.append({'outcome': outcome,
                            'weight': ref.get('weight', 1),
                            'veto': bool(ref.get('veto'))})
    value = engine.compute_frame(defn, rule_values)
    vid = frame_repo.add_value(frame_id, value)
    return {'def_id': frame_id, 'value_id': vid, 'value': value}


# ---------------- 元数据链（lineage） ----------------

def _meta_index(index_id):
    d = index_repo.get_def(index_id=index_id)
    if not d:
        return None
    return {'scope': 'index', 'id': d['id'], 'name': d['name'],
            'config': {'source_table': d['source_table'],
                       'source_column': d['source_column'],
                       'aggregate': d['aggregate'],
                       'filter': d['filter_json']}}


def _meta_rule(rule_id):
    d = rule_repo.get_def(rule_id=rule_id)
    if not d:
        return None
    return {'scope': 'rule', 'id': d['id'], 'name': d['name'],
            'config': {'conditions': d['conditions_json'],
                       'combine': d['combine']},
            'refs': [_meta_index(r['index_id'])
                     for r in d['index_refs_json'] if _meta_index(r['index_id'])]}


def parse_lineage(scope, value_id):
    """返回参与计算的元数据链：结果 → 定义 → 下级定义（数组）。"""
    if scope not in ('index', 'rule', 'frame'):
        raise BadRequest('scope 仅支持 index/rule/frame')
    row = _repo(scope).get_value(value_id)
    if row is None:
        raise NotFound('{}结果不存在'.format(_LABEL[scope]))
    def_id = row[scope + '_id']
    if scope == 'index':
        meta = _meta_index(def_id)
    elif scope == 'rule':
        meta = _meta_rule(def_id)
    else:
        d = frame_repo.get_def(frame_id=def_id)
        if not d:
            raise NotFound('框架定义不存在')
        meta = {'scope': 'frame', 'id': d['id'], 'name': d['name'],
                'config': {'combine': d['combine'], 'threshold': d['threshold']},
                'refs': [_meta_rule(r['rule_id'])
                         for r in d['rule_refs_json'] if _meta_rule(r['rule_id'])]}
    return {'scope': scope, 'result': row, 'definition': meta}


# ---------------- 复核（replay） ----------------

def replay_value(scope, value_id):
    """用当前定义重算一次结果，与存储值比对。"""
    if scope not in ('index', 'rule', 'frame'):
        raise BadRequest('scope 仅支持 index/rule/frame')
    row = _repo(scope).get_value(value_id)
    if row is None:
        raise NotFound('{}结果不存在'.format(_LABEL[scope]))
    def_id = row[scope + '_id']
    defn = _def(scope, def_id)
    field = _VALUE_FIELD[scope]
    if scope == 'index':
        recomputed = engine.compute_index(defn)
    elif scope == 'rule':
        alias_values = {}
        for ref in defn['index_refs_json']:
            val = _latest('index', ref['index_id'])
            if val is None:
                raise BadRequest('引用的指标 #{} 还没有结果'.format(ref['index_id']))
            alias_values[ref['alias']] = val
        recomputed = engine.compute_rule(defn, alias_values)
    else:
        rule_values = []
        for ref in defn['rule_refs_json']:
            val = _latest('rule', ref['rule_id'])
            if val is None:
                raise BadRequest('引用的规则 #{} 还没有结果'.format(ref['rule_id']))
            rule_values.append({'outcome': ('pass' if str(val).startswith('pass')
                                            else 'fail'),
                                'weight': ref.get('weight', 1),
                                'veto': bool(ref.get('veto'))})
        recomputed = engine.compute_frame(defn, rule_values)
    stored = row[field]
    check = {'stored': stored, 'recomputed': recomputed,
             'match': recomputed == stored}
    return {'scope': scope, 'value_id': value_id,
            'checks': {field: check}, 'consistent': check['match'],
            'note': '极简复核：按当前定义与最新结果重算比对'}
