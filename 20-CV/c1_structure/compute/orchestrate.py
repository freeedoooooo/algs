"""compute/orchestrate.py — run 编排层：定义读取 → 引擎运算 → repo 幂等落库。

app.py 只做 HTTP 校验，业务编排收敛在此。三类 execute_* 返回统一信封：
  {def_id, def_version, value_id, value/outcome/score, result_hash, created}
依赖解析按顺序对齐 refs 与传入的 value_id 列表，并校验引用 ID 一致——
防止「拿 A 指标的结果填 B 别名的条件」造成静默错算。
"""
from .. import store
from ..store import index_repo, rule_repo, frame_repo
from ..store.errors import BadRequest, NotFound
from ..store.value_common import value_hash as _value_hash
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


def _locate_url(record_id, column=None):
    url = '/api/staging/locate/{}'.format(record_id)
    if column:
        url += '?key=' + str(column)
    return url


def _index_chain(value_id, chain, file_ids):
    """追加一个指标结果到 chain，并把其行锚点/源文件累积到上下文。"""
    row = index_repo.get_value(value_id)
    if row is None:
        return
    defn = index_repo.get_def(index_id=row['index_id'],
                              version=row['index_version'])
    column = (defn or {}).get('source_column')
    rows = []
    for r in row['input_rows_json'].get('rows') or []:
        item = dict(r)
        item['locate'] = (_locate_url(r['record_id'], column)
                          if r.get('record_id') is not None else None)
        rows.append(item)
        if r.get('file_id') is not None:
            file_ids.add(r['file_id'])
    chain.append({'scope': 'index', 'result_id': row['id'],
                  'value': row['value_text'], 'rows': rows,
                  'matched_rows': row['input_rows_json'].get('matched_rows'),
                  'truncated': row['input_rows_json'].get('truncated'),
                  'result_hash': row['result_hash']})


def _rule_chain(value_id, chain, file_ids):
    row = rule_repo.get_value(value_id)
    if row is None:
        return
    chain.append({'scope': 'rule', 'result_id': row['id'],
                  'outcome': row['outcome'], 'detail': row['detail_json'],
                  'result_hash': row['result_hash']})
    for v in row['index_value_ids_json']:
        _index_chain(v, chain, file_ids)


def _source_files(file_ids):
    """file_id 集合 → 源文件展示信息（名字 + 预览链接）。"""
    out = []
    for fid in sorted(file_ids):
        f = store.catalog.get_file(fid)
        out.append({'file_id': fid,
                    'name': (f or {}).get('name') or '资料 #{}'.format(fid),
                    'open': '/preview?embed=1&file={}'.format(fid)})
    return out


def parse_lineage(scope, value_id):
    """递归展开完整血缘包（设计稿 §7 契约）。

    返回 {ok, scope, result, definition, chain, source_files}：
    chain 从顶层结果逐层下钻到指标行锚点；每行带 locate 链接可复用
    /api/staging/locate 到原图格子；source_files 给出起点资料链接。
    """
    if scope not in ('index', 'rule', 'frame'):
        raise BadRequest('scope 仅支持 index/rule/frame')
    repos = {'index': index_repo, 'rule': rule_repo, 'frame': frame_repo}
    row = repos[scope].get_value(value_id)
    if row is None:
        raise NotFound('{}结果不存在'.format(
            {'index': '指标', 'rule': '规则', 'frame': '框架'}[scope]))
    def_id, def_ver = row[scope + '_id'], row[scope + '_version']
    if scope == 'index':
        defn = index_repo.get_def(index_id=def_id, version=def_ver)
    elif scope == 'rule':
        defn = rule_repo.get_def(rule_id=def_id, version=def_ver)
    else:
        defn = frame_repo.get_def(frame_id=def_id, version=def_ver)
    chain, file_ids = [], set()
    if scope == 'index':
        _index_chain(value_id, chain, file_ids)
    elif scope == 'rule':
        _rule_chain(value_id, chain, file_ids)
    else:
        chain.append({'scope': 'frame', 'result_id': row['id'],
                      'outcome': row['outcome'], 'score': row['score_text'],
                      'detail': row['detail_json'],
                      'result_hash': row['result_hash']})
        for v in row['rule_value_ids_json']:
            _rule_chain(v, chain, file_ids)
    return {'scope': scope, 'result': row,
            'definition': (dict(defn) if defn else None),
            'chain': chain, 'source_files': _source_files(file_ids)}


# ---------------- replay 复现校验 ----------------

def _replay_index(row, defn):
    """指标复现：用存储的输入快照重算聚合值与哈希。"""
    snapshot = row['input_rows_json']
    recomputed_value = engine.replay_index(defn, snapshot)
    recomputed_hash = _value_hash(defn['spec_hash'], snapshot)
    return {
        'result_hash': {
            'stored': row['result_hash'],
            'recomputed': recomputed_hash,
            'match': recomputed_hash == row['result_hash']},
        'value': {
            'stored': row['value_text'],
            'recomputed': recomputed_value,
            'match': recomputed_value == row['value_text']},
    }


def _replay_rule(row, defn):
    """规则复现：用依赖的指标值重算比较结论与哈希。"""
    ids = row['index_value_ids_json']
    refs = defn['index_refs_json']
    alias_values = {}
    for ref, vid in zip(refs, ids):
        iv = index_repo.get_value(vid)
        if iv is None:
            raise NotFound('依赖的指标结果不存在：{}'.format(vid))
        alias_values[ref['alias']] = iv['value_text']
    outcome, detail = engine.run_rule(defn, alias_values)
    recomputed_hash = _value_hash(defn['spec_hash'], {
        'index_value_ids': ids, 'detail': detail, 'outcome': outcome})
    return {
        'result_hash': {
            'stored': row['result_hash'], 'recomputed': recomputed_hash,
            'match': recomputed_hash == row['result_hash']},
        'outcome': {
            'stored': row['outcome'], 'recomputed': outcome,
            'match': outcome == row['outcome']},
        'detail': {
            'stored': row['detail_json'], 'recomputed': detail,
            'match': detail == row['detail_json']},
    }


def _replay_frame(row, defn):
    """框架复现：用依赖的规则值重算组合结论与哈希。"""
    ids = row['rule_value_ids_json']
    refs = defn['rule_refs_json']
    outcomes = []
    for ref, vid in zip(refs, ids):
        rv = rule_repo.get_value(vid)
        if rv is None:
            raise NotFound('依赖的规则结果不存在：{}'.format(vid))
        outcomes.append({'rule_value_id': rv['id'], 'outcome': rv['outcome'],
                         'weight': ref.get('weight', 1),
                         'veto': bool(ref.get('veto'))})
    outcome, score, detail = engine.run_frame(defn, outcomes)
    recomputed_hash = _value_hash(defn['spec_hash'], {
        'rule_value_ids': ids, 'detail': detail,
        'outcome': outcome, 'score': score})
    return {
        'result_hash': {
            'stored': row['result_hash'], 'recomputed': recomputed_hash,
            'match': recomputed_hash == row['result_hash']},
        'outcome': {
            'stored': row['outcome'], 'recomputed': outcome,
            'match': outcome == row['outcome']},
        'score': {
            'stored': row['score_text'], 'recomputed': score,
            'match': (score or None) == (row['score_text'] or None)},
        'detail': {
            'stored': row['detail_json'], 'recomputed': detail,
            'match': detail == row['detail_json']},
    }


def replay_value(scope, value_id):
    """复现校验：用结果绑定版本的定义 + 存储快照重算，逐字段比对。

    返回 {scope, value_id, definition:{id,version,spec_hash}, checks:{...},
    consistent:bool}。consistent 为所有 check.match 的合取——
    任何字段被篡改（结果值/依赖/明细/哈希）都会使对应 match=false。
    """
    if scope not in ('index', 'rule', 'frame'):
        raise BadRequest('scope 仅支持 index/rule/frame')
    repos = {'index': index_repo, 'rule': rule_repo, 'frame': frame_repo}
    row = repos[scope].get_value(value_id)
    if row is None:
        raise NotFound('{}结果不存在'.format(
            {'index': '指标', 'rule': '规则', 'frame': '框架'}[scope]))
    def_id, def_ver = row[scope + '_id'], row[scope + '_version']
    if scope == 'index':
        defn = index_repo.get_def(index_id=def_id, version=def_ver)
    elif scope == 'rule':
        defn = rule_repo.get_def(rule_id=def_id, version=def_ver)
    else:
        defn = frame_repo.get_def(frame_id=def_id, version=def_ver)
    if defn is None:
        raise NotFound('结果绑定的定义版本不存在，无法复现')
    checks = {'index': _replay_index, 'rule': _replay_rule,
              'frame': _replay_frame}[scope](row, defn)
    consistent = all(v['match'] for v in checks.values())
    return {'scope': scope, 'value_id': value_id,
            'definition': {'id': def_id, 'version': def_ver,
                           'spec_hash': defn['spec_hash']},
            'checks': checks, 'consistent': consistent}
