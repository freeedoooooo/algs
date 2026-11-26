"""P2 验证：编排层依赖对齐守卫 + 路由注册（不连 DB）。"""
import os
import sys
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
PKG = os.path.basename(ROOT)

def _load(name):
    return importlib.import_module(PKG + '.' + name)

orch = _load('compute.orchestrate')
errors = _load('store.errors')

ok = 0

def check(name, cond, detail=''):
    global ok
    if cond:
        ok += 1
        print('  PASS ' + name)
    else:
        raise AssertionError('FAIL ' + name + ' :: ' + str(detail))


class FakeRepo:
    def __init__(self, rows):
        self.rows = rows

    def get_value(self, vid):
        return self.rows.get(vid)

    def get_def(self, **kwargs):
        return {'id': 1, 'name': 'stub', 'version': 1,
                'source_column': 'amt'}


# --- 依赖对齐：正常 ---
defn = {'index_refs_json': [
    {'index_id': 1, 'alias': 'm1', 'version': 1},
    {'index_id': 2, 'alias': 'm2', 'version': 1}]}
repo = FakeRepo({10: {'id': 10, 'index_id': 1, 'value_text': '100'},
                 20: {'id': 20, 'index_id': 2, 'value_text': '200'}})
aligned = orch._resolve_alias_values(defn, [10, 20], repo, 'index_id')
check('对齐数量与顺序', [r['id'] for _, r in aligned] == [10, 20], aligned)

# --- 依赖对齐：错位拒绝（关键防错算守卫）---
repo_swap = FakeRepo({10: {'id': 10, 'index_id': 2, 'value_text': '100'},
                      20: {'id': 20, 'index_id': 1, 'value_text': '200'}})
try:
    orch._resolve_alias_values(defn, [10, 20], repo_swap, 'index_id')
    check('引用错位拒绝', False)
except errors.BadRequest:
    check('引用错位拒绝', True)

# --- 数量不符 / 重复 / 不存在 ---
for bad_ids, label in [([10], '数量不符'), ([10, 10], '重复 ID'),
                       ([10, 999], '结果不存在')]:
    try:
        orch._resolve_alias_values(defn, bad_ids, repo, 'index_id')
        check(label + ' 拒绝', False)
    except (errors.BadRequest, errors.NotFound):
        check(label + ' 拒绝', True)
try:
    orch._resolve_alias_values(defn, 'not-a-list', repo, 'index_id')
    check('非列表拒绝', False)
except errors.BadRequest:
    check('非列表拒绝', True)

# --- 路由注册完整性 ---
appmod = _load('app')
paths = {}
for r in appmod.app.routes:
    for m in getattr(r, 'methods', []) or []:
        paths.setdefault((m, r.path), True)
required = [
    ('GET', '/api/index'), ('POST', '/api/index'),
    ('GET', '/api/index/{index_id}'), ('DELETE', '/api/index/{index_id}'),
    ('POST', '/api/index/{index_id}/run'),
    ('GET', '/api/index/{index_id}/values'),
    ('GET', '/api/index/value/{value_id}/lineage'),
    ('GET', '/api/index/value/{value_id}/replay'),
    ('GET', '/api/rule'), ('POST', '/api/rule'),
    ('GET', '/api/rule/{rule_id}'), ('DELETE', '/api/rule/{rule_id}'),
    ('POST', '/api/rule/{rule_id}/run'),
    ('GET', '/api/rule/{rule_id}/values'),
    ('GET', '/api/rule/value/{value_id}/lineage'),
    ('GET', '/api/rule/value/{value_id}/replay'),
    ('GET', '/api/frame'), ('POST', '/api/frame'),
    ('GET', '/api/frame/{frame_id}'), ('DELETE', '/api/frame/{frame_id}'),
    ('POST', '/api/frame/{frame_id}/run'),
    ('GET', '/api/frame/{frame_id}/values'),
    ('GET', '/api/frame/value/{value_id}/lineage'),
    ('GET', '/api/frame/value/{value_id}/replay'),
]
missing = [k for k in required if k not in paths]
check('24 个 CRUD/run/values/lineage/replay 路由全部注册', not missing, missing)

# --- locate 链接构造 ---
check('locate 无列名', orch._locate_url(101) == '/api/staging/locate/101')
check('locate 带列名',
      orch._locate_url(101, 'amt') == '/api/staging/locate/101?key=amt')

# --- 递归血缘展开（打桩 repo，不连库）---
index_row = {'id': 7, 'index_id': 6, 'index_version': 1,
             'value_text': '24', 'result_hash': 'h7',
             'input_rows_json': {'rows': [
                 {'file_id': 1, 'record_id': 121, 'value': '10'},
                 {'file_id': 2, 'record_id': 200, 'value': '14'}],
                 'matched_rows': 2, 'truncated': False}}
rule_row = {'id': 8, 'rule_id': 3, 'rule_version': 1, 'outcome': 'pass',
            'detail_json': [{'alias': 'cnt', 'passed': True}],
            'index_value_ids_json': [7], 'result_hash': 'h8'}
frame_row = {'id': 9, 'frame_id': 2, 'frame_version': 1, 'outcome': 'pass',
             'score_text': '1', 'detail_json': [],
             'rule_value_ids_json': [8], 'result_hash': 'h9'}

orig_ir, orig_rr, orig_fr = orch.index_repo, orch.rule_repo, orch.frame_repo
orig_cat = orch.store.catalog
orch.index_repo = FakeRepo({7: index_row})
orch.rule_repo = FakeRepo({8: rule_row})
orch.frame_repo = FakeRepo({9: frame_row})

class FakeCatalog:
    @staticmethod
    def get_file(fid):
        return {'id': fid, 'name': 'doc{}.pdf'.format(fid)}
orch.store.catalog = FakeCatalog()

try:
    out = orch.parse_lineage('frame', 9)
    check('血缘链顶层是 frame', out['chain'][0]['scope'] == 'frame')
    check('血缘链完整 3 层',
          [c['scope'] for c in out['chain']] == ['frame', 'rule', 'index'],
          [c['scope'] for c in out['chain']])
    idx = out['chain'][-1]
    check('行锚点带 locate（含列名）',
          idx['rows'][0]['locate'] == '/api/staging/locate/121?key=amt',
          idx['rows'][0])
    check('源文件去重且带 open',
          len(out['source_files']) == 2
          and out['source_files'][0]['open'].startswith('/preview?embed=1&file='),
          out['source_files'])
    check('血缘 result 保真', out['result']['result_hash'] == 'h9')
finally:
    orch.index_repo, orch.rule_repo, orch.frame_repo = orig_ir, orig_rr, orig_fr
    orch.store.catalog = orig_cat

# --- replay 复现校验（打桩，含篡改检测）---
vc = _load('store.value_common')
import hashlib

defn_hash = 'a' * 64
snap = {'datasource_id': 5, 'table': 't', 'column': None,
        'aggregate': 'count', 'filter': [], 'rows': [],
        'matched_rows': 24, 'truncated': False}
good_hash = vc.value_hash(defn_hash, snap)
idx_replay_row = {'id': 7, 'index_id': 6, 'index_version': 1,
                  'value_text': '24', 'result_hash': good_hash,
                  'input_rows_json': snap}
replay_defn = {'id': 6, 'version': 1, 'spec_hash': defn_hash}
engine_mod = _load('compute.engine')
orig_replay_index = engine_mod.replay_index
engine_mod.replay_index = lambda d, s: '24'
try:
    checks = orch._replay_index(idx_replay_row, replay_defn)
    check('replay 正常一致',
          all(v['match'] for v in checks.values()), checks)
    # 篡改哈希
    bad = dict(idx_replay_row, result_hash='f' * 64)
    c2 = orch._replay_index(bad, replay_defn)
    check('replay 检测哈希篡改',
          c2['result_hash']['match'] is False, c2)
    # 篡改值
    bad2 = dict(idx_replay_row, value_text='999')
    c3 = orch._replay_index(bad2, replay_defn)
    check('replay 检测值篡改', c3['value']['match'] is False, c3)
finally:
    engine_mod.replay_index = orig_replay_index

# --- 与既有 API 不冲突 ---
check('抽取规则 API 保留', ('GET', '/api/extract-rules') in paths)
check('数据源 API 保留', ('GET', '/api/load/datasources') in paths)

print('P2 orchestrate/routes: {} checks passed'.format(ok))
