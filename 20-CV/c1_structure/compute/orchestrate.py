"""compute/orchestrate.py — run 编排层：定义读取 → 引擎运算 → repo 幂等落库。

app.py 只做 HTTP 校验，业务编排收敛在此。三类 execute_* 返回统一信封：
  {def_id, def_version, value_id, value/outcome/score, result_hash, created}
依赖解析按顺序对齐 refs 与传入的 value_id 列表，并校验引用 ID 一致——
防止「拿 A 指标的结果填 B 别名的条件」造成静默错算。
"""
from .. import store
from ..store import index_repo, rule_repo, frame_repo
from ..store.errors import BadRequest, NotFound
from . import engine


def _resolve_alias_values(defn, value_ids, repo, id_key):
    """按 refs 顺序对齐 value_ids → {alias: value_text} / 明细列表。

    defn 的 refs 为 index_refs_json 或 rule_refs_json；repo 按 id 取结果行，
    校验每个结果的父定义 ID 与 ref 一致，别名/规则 ID 不串位。
    """
    refs_key = 'index_refs_json' if id_key == 'index_id' else 'rule_refs_json'
    refs = defn.get(refs_key) or []
    if not isinstance(value_ids, list) or not value_ids:
        raise BadRequest('须提供依赖的结果 ID 列表')
    if len(value_ids) != len(refs):
        raise BadRequest('依赖结果数量与定义引用数量不符：{} vs {}'.format(
            len(value_ids), len(refs)))
    try:
        ids = [int(v) for v in value_ids]
    except (TypeError, ValueError):
        raise BadRequest('结果 ID 须为整数')
    if len(set(ids)) != len(ids):
        raise BadRequest('依赖结果 ID 重复')

    aligned = []
    for ref, vid in zip(refs, ids):
        row = repo.get_value(vid)
        if row is None:
            raise NotFound('依赖的结果不存在：{}'.format(vid))
        if row[id_key] != ref[id_key]:
            raise BadRequest(
                '结果 #{} 属于 {}#{}，与定义引用的 {}#{} 不符'.format(
                    vid, id_key, row[id_key], id_key, ref[id_key]))
        aligned.append((ref, row))
    return aligned


def execute_index(index_id):
    """跑指标：读定义 → 聚合 + 行锚点 → 写 c1_index_value。"""
    defn = index_repo.get_def(index_id=index_id)
    if defn is None:
        raise NotFound('指标定义不存在')
    value_text, input_rows = engine.run_index(defn)
    vid, vh, created = index_repo.add_value(
        defn['id'], defn['version'], defn['spec_hash'],
        value_text, input_rows)
    return {'def_id': defn['id'], 'def_version': defn['version'],
            'value_id': vid, 'value': value_text,
            'result_hash': vh, 'created': created,
            'matched_rows': input_rows.get('matched_rows'),
            'truncated': input_rows.get('truncated')}


def execute_rule(rule_id, index_value_ids):
    """跑规则：解析指标值 → 比较 → 写 c1_rule_value。"""
    defn = rule_repo.get_def(rule_id=rule_id)
    if defn is None:
        raise NotFound('规则定义不存在')
    aligned = _resolve_alias_values(defn, index_value_ids,
                                    index_repo, 'index_id')
    alias_values = {ref['alias']: row['value_text']
                    for ref, row in aligned}
    outcome, detail = engine.run_rule(defn, alias_values)
    vid, vh, created = rule_repo.add_value(
        defn['id'], defn['version'], defn['spec_hash'],
        list(int(v) for v in index_value_ids), outcome, detail)
    return {'def_id': defn['id'], 'def_version': defn['version'],
            'value_id': vid, 'outcome': outcome,
            'result_hash': vh, 'created': created, 'detail': detail}


def execute_frame(frame_id, rule_value_ids):
    """跑框架：解析规则值 → 组合 → 写 c1_frame_value。"""
    defn = frame_repo.get_def(frame_id=frame_id)
    if defn is None:
        raise NotFound('框架定义不存在')
    aligned = _resolve_alias_values(defn, rule_value_ids,
                                    rule_repo, 'rule_id')
    outcomes = []
    for ref, row in aligned:
        outcomes.append({'rule_value_id': row['id'],
                         'outcome': row['outcome'],
                         'weight': ref.get('weight', 1),
                         'veto': bool(ref.get('veto'))})
    outcome, score, detail = engine.run_frame(defn, outcomes)
    vid, vh, created = frame_repo.add_value(
        defn['id'], defn['version'], defn['spec_hash'],
        list(int(v) for v in rule_value_ids), outcome, detail, score)
    return {'def_id': defn['id'], 'def_version': defn['version'],
            'value_id': vid, 'outcome': outcome, 'score': score,
            'result_hash': vh, 'created': created, 'detail': detail}


def parse_lineage(scope, value_id):
    """展开单个结果的血缘上下文（lineage/replay 接口的基础数据）。

    index：返回输入行锚点 + locate 链接；
    rule：返回依赖的 index value 列表；
    frame：返回依赖的 rule value 列表。
    递归全链展开留给 P2 后续接口，本函数提供逐层数据。
    """
    if scope == 'index':
        row = index_repo.get_value(value_id)
        if row is None:
            raise NotFound('指标结果不存在')
        defn = index_repo.get_def(index_id=row['index_id'],
                                  version=row['index_version'])
        rows = []
        for r in row['input_rows_json'].get('rows') or []:
            item = dict(r)
            item['locate'] = ('/api/staging/locate/{}'.format(r['record_id'])
                              if r.get('record_id') is not None else None)
            rows.append(item)
        return {'scope': 'index', 'result': row,
                'definition': (dict(defn) if defn else None),
                'chain_rows': rows,
                'source_files': sorted({r.get('file_id') for r in rows
                                        if r.get('file_id') is not None})}
    if scope == 'rule':
        row = rule_repo.get_value(value_id)
        if row is None:
            raise NotFound('规则结果不存在')
        defn = rule_repo.get_def(rule_id=row['rule_id'],
                                 version=row['rule_version'])
        deps = [index_repo.get_value(v)
                for v in row['index_value_ids_json']]
        return {'scope': 'rule', 'result': row,
                'definition': (dict(defn) if defn else None),
                'deps': [d for d in deps if d]}
    if scope == 'frame':
        row = frame_repo.get_value(value_id)
        if row is None:
            raise NotFound('框架结果不存在')
        defn = frame_repo.get_def(frame_id=row['frame_id'],
                                  version=row['frame_version'])
        deps = [rule_repo.get_value(v)
                for v in row['rule_value_ids_json']]
        return {'scope': 'frame', 'result': row,
                'definition': (dict(defn) if defn else None),
                'deps': [d for d in deps if d]}
    raise BadRequest('scope 仅支持 index/rule/frame')
