"""compute/orchestrate.py — 计算层编排：定义读取 → 引擎运算 → repo 落库。

简化设计（2026-11-26）：无版本、无哈希、无配置快照副本。
  · 定义同名唯一，保存即更新；结果每次运行新增一行。
  · 结果只存血缘锚点/依赖 ID/实际值，全链路追溯仍可下钻到源文件格子。
  · replay 降级为「当前定义重算一次」与存储值比对。
"""
from .. import store
from ..store import index_repo, rule_repo, frame_repo
from ..store.errors import BadRequest, NotFound
from . import engine


def _resolve_deps(defn, value_ids, repo, id_key):
    """按 refs 顺序对齐 value_ids，校验引用 ID 一致（防串位错算）。"""
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
            raise BadRequest('结果 #{} 属于 {}#{}，与定义引用的 {}#{} 不符'.format(
                vid, id_key, row[id_key], id_key, ref[id_key]))
        aligned.append((ref, row))
    return aligned


def execute_index(index_id):
    defn = index_repo.get_def(index_id=index_id)
    if defn is None:
        raise NotFound('指标定义不存在')
    value_text, anchors = engine.run_index(defn)
    vid = index_repo.add_value(defn['id'], value_text, anchors)
    return {'def_id': defn['id'], 'value_id': vid, 'value': value_text,
            'matched_rows': anchors.get('matched_rows'),
            'truncated': anchors.get('truncated')}


def execute_rule(rule_id, index_value_ids):
    defn = rule_repo.get_def(rule_id=rule_id)
    if defn is None:
        raise NotFound('规则定义不存在')
    aligned = _resolve_deps(defn, index_value_ids, index_repo, 'index_id')
    alias_values = {ref['alias']: row['value_text'] for ref, row in aligned}
    outcome, detail = engine.run_rule(defn, alias_values)
    vid = rule_repo.add_value(defn['id'],
                              [int(v) for v in index_value_ids],
                              outcome, detail)
    return {'def_id': defn['id'], 'value_id': vid, 'outcome': outcome,
            'detail': detail}


def execute_frame(frame_id, rule_value_ids):
    defn = frame_repo.get_def(frame_id=frame_id)
    if defn is None:
        raise NotFound('框架定义不存在')
    aligned = _resolve_deps(defn, rule_value_ids, rule_repo, 'rule_id')
    outcomes = []
    for ref, row in aligned:
        outcomes.append({'rule_value_id': row['id'], 'outcome': row['outcome'],
                         'weight': ref.get('weight', 1),
                         'veto': bool(ref.get('veto'))})
    outcome, score, detail = engine.run_frame(defn, outcomes)
    vid = frame_repo.add_value(defn['id'],
                               [int(v) for v in rule_value_ids],
                               outcome, detail, score)
    return {'def_id': defn['id'], 'value_id': vid, 'outcome': outcome,
            'score': score, 'detail': detail}


# ---------------- 血缘展开 ----------------

def _locate_url(record_id, column=None):
    url = '/api/staging/locate/{}'.format(record_id)
    if column:
        url += '?key=' + str(column)
    return url


def _index_chain(value_id, chain, file_ids):
    row = index_repo.get_value(value_id)
    if row is None:
        return
    defn = index_repo.get_def(index_id=row['index_id'])
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
                  'truncated': row['input_rows_json'].get('truncated')})


def _rule_chain(value_id, chain, file_ids):
    row = rule_repo.get_value(value_id)
    if row is None:
        return
    chain.append({'scope': 'rule', 'result_id': row['id'],
                  'outcome': row['outcome'], 'detail': row['detail_json']})
    for v in row['index_value_ids_json']:
        _index_chain(v, chain, file_ids)


def _source_files(file_ids):
    out = []
    for fid in sorted(file_ids):
        f = store.catalog.get_file(fid)
        out.append({'file_id': fid,
                    'name': (f or {}).get('name') or '资料 #{}'.format(fid),
                    'open': '/preview?embed=1&file={}'.format(fid)})
    return out


def parse_lineage(scope, value_id):
    """递归展开血缘：frame→rule→index→行锚点→源文件。"""
    if scope not in ('index', 'rule', 'frame'):
        raise BadRequest('scope 仅支持 index/rule/frame')
    repos = {'index': index_repo, 'rule': rule_repo, 'frame': frame_repo}
    row = repos[scope].get_value(value_id)
    if row is None:
        raise NotFound('{}结果不存在'.format(
            {'index': '指标', 'rule': '规则', 'frame': '框架'}[scope]))
    def_id = row[scope + '_id']
    if scope == 'index':
        defn = index_repo.get_def(index_id=def_id)
    elif scope == 'rule':
        defn = rule_repo.get_def(rule_id=def_id)
    else:
        defn = frame_repo.get_def(frame_id=def_id)
    chain, file_ids = [], set()
    if scope == 'index':
        _index_chain(value_id, chain, file_ids)
    elif scope == 'rule':
        _rule_chain(value_id, chain, file_ids)
    else:
        chain.append({'scope': 'frame', 'result_id': row['id'],
                      'outcome': row['outcome'], 'score': row['score_text'],
                      'detail': row['detail_json']})
        for v in row['rule_value_ids_json']:
            _rule_chain(v, chain, file_ids)
    return {'scope': scope, 'result': row,
            'definition': (dict(defn) if defn else None),
            'chain': chain, 'source_files': _source_files(file_ids)}


# ---------------- 复现校验（降级） ----------------

def replay_value(scope, value_id):
    """降级复现：用当前定义重算一次结果，与存储值比对。

    无版本/哈希/输入快照，无法证明历史口径；仅能发现当前定义或数据变化。
    """
    if scope not in ('index', 'rule', 'frame'):
        raise BadRequest('scope 仅支持 index/rule/frame')
    repos = {'index': index_repo, 'rule': rule_repo, 'frame': frame_repo}
    row = repos[scope].get_value(value_id)
    if row is None:
        raise NotFound('{}结果不存在'.format(
            {'index': '指标', 'rule': '规则', 'frame': '框架'}[scope]))
    def_id = row[scope + '_id']
    checks = {}
    if scope == 'index':
        defn = index_repo.get_def(index_id=def_id)
        if defn is None:
            raise NotFound('指标定义不存在，无法复现')
        recomputed = engine.replay_index(defn)
        checks['value'] = {'stored': row['value_text'],
                           'recomputed': recomputed,
                           'match': recomputed == row['value_text']}
    elif scope == 'rule':
        defn = rule_repo.get_def(rule_id=def_id)
        if defn is None:
            raise NotFound('规则定义不存在，无法复现')
        aligned = _resolve_deps(defn, row['index_value_ids_json'],
                                index_repo, 'index_id')
        alias_values = {ref['alias']: dep['value_text']
                        for ref, dep in aligned}
        outcome, detail = engine.run_rule(defn, alias_values)
        checks['outcome'] = {'stored': row['outcome'],
                             'recomputed': outcome,
                             'match': outcome == row['outcome']}
        checks['detail'] = {'stored': row['detail_json'],
                            'recomputed': detail,
                            'match': detail == row['detail_json']}
    else:
        defn = frame_repo.get_def(frame_id=def_id)
        if defn is None:
            raise NotFound('框架定义不存在，无法复现')
        aligned = _resolve_deps(defn, row['rule_value_ids_json'],
                                rule_repo, 'rule_id')
        outcomes = [{'rule_value_id': dep['id'], 'outcome': dep['outcome'],
                     'weight': ref.get('weight', 1),
                     'veto': bool(ref.get('veto'))}
                    for ref, dep in aligned]
        outcome, score, detail = engine.run_frame(defn, outcomes)
        checks['outcome'] = {'stored': row['outcome'],
                             'recomputed': outcome,
                             'match': outcome == row['outcome']}
        checks['score'] = {'stored': row['score_text'],
                           'recomputed': score,
                           'match': (score or None) == (row['score_text'] or None)}
    consistent = all(v['match'] for v in checks.values())
    return {'scope': scope, 'value_id': value_id,
            'checks': checks, 'consistent': consistent,
            'note': '降级复现：按当前定义重算比对，无历史版本/哈希快照'}
