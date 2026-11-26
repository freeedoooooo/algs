"""编排层单测（不连 DB）：依赖对齐守卫 + 血缘展开 + 降级 replay + 路由注册。"""
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
        return {'id': 1, 'name': 'stub', 'source_column': 'amt'}

# --- 依赖对齐 ---
defn = {'index_refs_json': [
    {'index_id': 1, 'alias': 'm1'}, {'index_id': 2, 'alias': 'm2'}]}
repo = FakeRepo({10: {'id': 10, 'index_id': 1, 'value_text': '100'},
                 20: {'id': 20, 'index_id': 2, 'value_text': '200'}})
check('对齐数量与顺序',
      [r['id'] for _, r in orch._resolve_deps(defn, [10, 20], repo, 'index_id')]
      == [10, 20])
swap = FakeRepo({10: {'id': 10, 'index_id': 2, 'value_text': '100'},
                 20: {'id': 20, 'index_id': 1, 'value_text': '200'}})
try:
    orch._resolve_deps(defn, [10, 20], swap, 'index_id')
    check('引用错位拒绝', False)
except errors.BadRequest:
    check('引用错位拒绝', True)
for bad_ids, label in [([10], '数量不符'), ([10, 10], '重复 ID'),
                       ([10, 999], '结果不存在')]:
    try:
        orch._resolve_deps(defn, bad_ids, repo, 'index_id')
        check(label + ' 拒绝', False)
    except (errors.BadRequest, errors.NotFound):
        check(label + ' 拒绝', True)

# --- locate 链接 ---
check('locate 带列名',
      orch._locate_url(101, 'amt') == '/api/staging/locate/101?key=amt')

# --- 血缘展开（打桩）---
index_row = {'id': 7, 'index_id': 6, 'value_text': '24',
             'input_rows_json': {'rows': [
                 {'file_id': 1, 'record_id': 121, 'value': '10'},
                 {'file_id': 2, 'record_id': 200, 'value': '14'}],
                 'matched_rows': 2, 'truncated': False}}
rule_row = {'id': 8, 'rule_id': 3, 'outcome': 'pass',
            'detail_json': [{'alias': 'm1', 'actual': '24', 'passed': True}],
            'index_value_ids_json': [7]}
frame_row = {'id': 9, 'frame_id': 2, 'outcome': 'pass', 'score_text': '1',
             'detail_json': [], 'rule_value_ids_json': [8]}
orig = (orch.index_repo, orch.rule_repo, orch.frame_repo, orch.store.catalog)
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
    check('血缘链 3 层',
          [c['scope'] for c in out['chain']] == ['frame', 'rule', 'index'])
    idx = out['chain'][-1]
    check('行锚点带 locate',
          idx['rows'][0]['locate'] == '/api/staging/locate/121?key=amt')
    check('源文件去重带 open',
          len(out['source_files']) == 2
          and out['source_files'][0]['open'].startswith('/preview?embed=1'))
finally:
    (orch.index_repo, orch.rule_repo, orch.frame_repo, orch.store.catalog) = orig

# --- 降级 replay（指标：当前定义重算值比对）---
engine_mod = _load('compute.engine')
orig_replay = engine_mod.replay_index
engine_mod.replay_index = lambda d: '24'
try:
    defn_i = {'id': 6, 'aggregate': 'count'}
    row_ok = {'id': 7, 'index_id': 6, 'value_text': '24'}
    row_bad = {'id': 8, 'index_id': 6, 'value_text': '999'}
    fake = FakeRepo({7: row_ok, 8: row_bad})
    old = orch.index_repo
    orch.index_repo = fake
    try:
        r = orch.replay_value('index', 7)
        check('replay 一致', r['consistent'] and r['checks']['value']['match'])
        r2 = orch.replay_value('index', 8)
        check('replay 检测值篡改', not r2['consistent'])
        check('replay 无哈希项', 'result_hash' not in r['checks'])
    finally:
        orch.index_repo = old
finally:
    engine_mod.replay_index = orig_replay

# --- 路由注册 ---
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
check('24 路由全部注册', not missing, missing)
check('抽取规则 API 保留', ('GET', '/api/extract-rules') in paths)

print('P2 orchestrate/routes: {} checks passed'.format(ok))
