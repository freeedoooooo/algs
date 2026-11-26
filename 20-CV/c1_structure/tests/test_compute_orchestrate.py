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
    ('GET', '/api/rule'), ('POST', '/api/rule'),
    ('GET', '/api/rule/{rule_id}'), ('DELETE', '/api/rule/{rule_id}'),
    ('POST', '/api/rule/{rule_id}/run'),
    ('GET', '/api/frame'), ('POST', '/api/frame'),
    ('GET', '/api/frame/{frame_id}'), ('DELETE', '/api/frame/{frame_id}'),
    ('POST', '/api/frame/{frame_id}/run'),
]
missing = [k for k in required if k not in paths]
check('15 个 CRUD/run 路由全部注册', not missing, missing)

# --- 与既有 API 不冲突 ---
check('抽取规则 API 保留', ('GET', '/api/extract-rules') in paths)
check('数据源 API 保留', ('GET', '/api/load/datasources') in paths)

print('P2 orchestrate/routes: {} checks passed'.format(ok))
