"""P0 验证：index/rule/frame repo 的纯逻辑部分（不连 DB）。

覆盖：spec_hash / value_hash 确定性与敏感性、create 参数校验、命名口径。
DB 相关的幂等/CRUD 由 8799 端到端验收脚本验证（见 P2）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))

PKG = os.path.basename(ROOT)
import importlib

def _load(name):
    return importlib.import_module(PKG + '.' + name)

value_common = _load('store.value_common')
index_repo = _load('store.index_repo')
rule_repo = _load('store.rule_repo')
frame_repo = _load('store.frame_repo')
errors = _load('store.errors')

ok = 0

def check(name, cond, detail=''):
    global ok
    if cond:
        ok += 1
        print('  PASS ' + name)
    else:
        raise AssertionError('FAIL ' + name + ' :: ' + str(detail))

# --- 哈希确定性/敏感性 ---
spec = {'datasource_id': 1, 'source_table': 't', 'source_column': 'amt',
        'aggregate': 'sum', 'filter_json': []}
h1 = value_common.spec_hash(spec)
h2 = value_common.spec_hash(dict(reversed(list(spec.items()))))
check('spec_hash 键序无关', h1 == h2, (h1, h2))
spec2 = dict(spec); spec2['aggregate'] = 'avg'
check('spec_hash 语义敏感', h1 != value_common.spec_hash(spec2))
vh1 = value_common.value_hash(h1, {'rows': [1, 2], 'table': 't'})
vh2 = value_common.value_hash(h1, {'table': 't', 'rows': [1, 2]})
check('value_hash 键序无关', vh1 == vh2, (vh1, vh2))
check('value_hash 输入敏感',
      vh1 != value_common.value_hash(h1, {'rows': [1, 3], 'table': 't'}))
check('value_hash 定义敏感',
      vh1 != value_common.value_hash(value_common.spec_hash(spec2),
                                     {'rows': [1, 2], 'table': 't'}))

# --- index 校验 ---
try:
    index_repo.create_def('', 1, 't', 'amt', 'sum')
    check('空指标名拒绝', False)
except errors.BadRequest:
    check('空指标名拒绝', True)
try:
    index_repo.create_def('x', 1, 't', 'amt', 'median')
    check('非法聚合拒绝', False)
except errors.BadRequest:
    check('非法聚合拒绝', True)
try:
    index_repo.create_def('x', 1, 't', 'amt', 'sum',
                          [{'column': 'f', 'op': 'like', 'value': 1}])
    check('非法过滤 op 拒绝', False)
except errors.BadRequest:
    check('非法过滤 op 拒绝', True)

# --- rule 校验 ---
refs = [{'index_id': 1, 'alias': 'm1'}]
conds = [{'alias': 'm1', 'op': 'gt', 'threshold': 100}]
try:
    rule_repo.create_def('r', refs, [{'alias': 'm2', 'op': 'gt', 'threshold': 1}])
    check('条件引用未定义别名拒绝', False)
except errors.BadRequest:
    check('条件引用未定义别名拒绝', True)
try:
    rule_repo.create_def('r', refs, [{'alias': 'm1', 'op': 'regex', 'threshold': 1}])
    check('非法比较 op 拒绝', False)
except errors.BadRequest:
    check('非法比较 op 拒绝', True)
try:
    rule_repo.create_def('r', [], conds)
    check('空指标引用拒绝', False)
except errors.BadRequest:
    check('空指标引用拒绝', True)

# --- frame 校验 ---
rrefs = [{'rule_id': 1, 'weight': 1, 'veto': False}]
try:
    frame_repo.create_def('f', rrefs, 'weighted', None)
    check('weighted 缺阈值拒绝', False)
except errors.BadRequest:
    check('weighted 缺阈值拒绝', True)
try:
    frame_repo.create_def('f', rrefs, 'no_such_combine', 0.8)
    check('非法组合拒绝', False)
except errors.BadRequest:
    check('非法组合拒绝', True)

# --- 命名口径：无旧前缀残留 ---
import glob
py_files = ([os.path.join(ROOT, f) for f in ('app.py', 'service.py')]
            + glob.glob(os.path.join(ROOT, 'store', '*.py')))
bad = []
for p in py_files:
    with open(p, encoding='utf-8') as fh:
        text = fh.read()
    for token in ('c1_metric_', 'c1_framework_', '/api/biz-rules', '/api/metrics'):
        if token in text:
            bad.append((os.path.basename(p), token))
check('产品代码无 metric/framework/biz-rules 旧命名', not bad, bad)

print('P0 repo logic: {} checks passed'.format(ok))
