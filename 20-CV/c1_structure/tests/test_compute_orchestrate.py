"""编排层单测（不连 DB）：元数据链、极简复核、路由注册、结果表无冗余字段。"""
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

# --- 结果表列：只有 id + def_id + 前缀_value + computed_at ---
for mod, cols_name, value_col in [
    (_load('store.index_repo'), '_VALUE_COLS', 'index_value'),
    (_load('store.rule_repo'), '_VALUE_COLS', 'rule_value'),
    (_load('store.frame_repo'), '_VALUE_COLS', 'frame_value')]:
    cols = getattr(mod, cols_name)
    check(mod.__name__.split('.')[-1] + ' 结果列极简',
          set(cols) == {'id', 'computed_at', value_col,
                        cols[1]}, cols)
    check(mod.__name__.split('.')[-1] + ' 无输入/依赖/锚点字段',
          not any(k in cols for k in ('input_rows_json', 'detail_json',
                                      '_ids_json', 'outcome', 'score_text')),
          cols)

# --- 元数据链（打桩）---
class FakeRepo:
    def __init__(self, rows, defs=None):
        self.rows, self.defs = rows, defs or {}
    def get_value(self, vid):
        return self.rows.get(vid)
    def get_def(self, **kw):
        key = list(kw.values())[0]
        return self.defs.get(key)
    def list_values(self, **kw):
        field = getattr(self, 'field', 'value')
        return ([{field: '24'}] if self.rows else [])

index_repo = _load('store.index_repo')
rule_repo = _load('store.rule_repo')
frame_repo = _load('store.frame_repo')

i_def = {'id': 1, 'name': '金额合计', 'source_table': 't',
         'source_column': 'amt', 'aggregate': 'count', 'filter_json': []}
r_def = {'id': 2, 'name': '超阈值', 'conditions_json': [
             {'alias': 'm1', 'op': 'gt', 'threshold': 10}],
         'combine': 'all', 'index_refs_json': [{'index_id': 1, 'alias': 'm1'}]}
f_def = {'id': 3, 'name': '综合', 'combine': 'weighted', 'threshold': '0.8',
         'rule_refs_json': [{'rule_id': 2, 'weight': 1, 'veto': False}]}

orig = (orch.index_repo, orch.rule_repo, orch.frame_repo)
fi = FakeRepo({}, {1: i_def}); fi.field = 'index_value'
fr = FakeRepo({}, {2: r_def}); fr.field = 'rule_value'
ff = FakeRepo({}, {3: f_def}); ff.field = 'frame_value'
orch.index_repo, orch.rule_repo, orch.frame_repo = fi, fr, ff
try:
    # 给 frame 结果行
    ff.rows = {1: {'id': 1, 'frame_id': 3, 'frame_value': 'pass（1）'}}
    out = orch.parse_lineage('frame', 1)
    check('框架 lineage 顶层 scope', out['definition']['scope'] == 'frame')
    check('框架 lineage 引用规则数组',
          len(out['definition']['refs']) == 1
          and out['definition']['refs'][0]['scope'] == 'rule')
    check('规则 lineage 引用指标数组',
          out['definition']['refs'][0]['refs'][0]['scope'] == 'index')
    check('元数据链无行锚点',
          all(k not in str(out) for k in ('record_id', 'cell_bbox')))
finally:
    orch.index_repo, orch.rule_repo, orch.frame_repo = orig

# --- 复核字段名 ---
engine_mod = _load('compute.engine')
orig_ci = engine_mod.compute_index
engine_mod.compute_index = lambda d: '24'
try:
    orch.index_repo = FakeRepo({1: {'id': 1, 'index_id': 1, 'index_value': '24'}})
    orch.index_repo.defs = {1: i_def}
    r = orch.replay_value('index', 1)
    check('replay 用 index_value 字段', 'index_value' in r['checks'])
    check('replay 一致', r['consistent'])
    orch.index_repo = FakeRepo({2: {'id': 2, 'index_id': 1, 'index_value': '999'}})
    orch.index_repo.defs = {1: i_def}
    r2 = orch.replay_value('index', 2)
    check('replay 检测值篡改', not r2['consistent'])
finally:
    engine_mod.compute_index = orig_ci
    orch.index_repo = index_repo

# --- 路由注册 ---
appmod = _load('app')
paths = {}
for route in appmod.app.routes:
    for m in getattr(route, 'methods', []) or []:
        paths.setdefault((m, route.path), True)
required = [
    ('GET', '/api/compute/layout'), ('PUT', '/api/compute/layout'),
    ('GET', '/api/index'), ('POST', '/api/index'),
    ('GET', '/api/index/{index_id}'), ('DELETE', '/api/index/{index_id}'),
    ('POST', '/api/index/{index_id}/run'),
    ('GET', '/api/index/{index_id}/values'),
    ('GET', '/api/index/{index_id}/source-preview'),
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
check('27 路由全注册', not missing, missing)
check('抽取规则 API 保留', ('GET', '/api/extract-rules') in paths)

print('orchestrate logic: {} checks passed'.format(ok))
