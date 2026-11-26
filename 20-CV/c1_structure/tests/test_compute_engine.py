"""P1 验证：compute 引擎纯逻辑（不连业务库，不写平台库）。

覆盖：WHERE 构造、六种比较、四种组合、指标 SQL 选择、哈希复现口径。
DB 端到端由 P2 验收脚本验证。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
import importlib

def _load(name):
    return importlib.import_module(os.path.basename(ROOT) + '.' + name)

engine = _load('compute.engine')
errors = _load('store.errors')
vc = _load('store.value_common')

ok = 0

def check(name, cond, detail=''):
    global ok
    if cond:
        ok += 1
        print('  PASS ' + name)
    else:
        raise AssertionError('FAIL ' + name + ' :: ' + str(detail))

# --- WHERE 构造：值参数化 + 列名转义 ---
sql, args = engine._where([
    {'column': 'file_id', 'op': 'eq', 'value': 12},
    {'column': 'amt', 'op': 'gte', 'value': 100},
], allow_cols={'file_id', 'amt'})
check('WHERE 优先级/转义', sql == ' WHERE `file_id` = %s AND `amt` >= %s', sql)
check('WHERE 参数顺序', args == [12, 100], args)
sql2, args2 = engine._where([{'column': 'file_id', 'op': 'eq', 'value': None}])
check('WHERE NULL 分支', 'IS NULL' in sql2 and args2 == [], (sql2, args2))
try:
    engine._where([{'column': 'no_such', 'op': 'eq', 'value': 1}],
                  allow_cols={'file_id'})
    check('WHERE 列白名单拒绝', False)
except errors.BadRequest:
    check('WHERE 列白名单拒绝', True)
try:
    engine._where([{'column': 'x', 'op': 'like', 'value': '%'}])
    check('WHERE 非法 op 拒绝', False)
except errors.BadRequest:
    check('WHERE 非法 op 拒绝', True)

# --- 比较算子 ---
cmp_cases = [
    ('10', 'gt', '5', True), ('10', 'gte', '10', True),
    ('10', 'lt', '5', False), ('10', 'lte', '10', True),
    ('10', 'eq', 10, True), ('10', 'ne', 10, False),
    ('10', 'between', [5, 20], True), ('10', 'between', [11, 20], False),
]
for actual, op, th, expected in cmp_cases:
    got = engine._compare(actual, op, th)
    check('比较 {}({}, {})'.format(op, actual, th), got is expected, got)
check('Decimal 精度（0.1+0.2 类）',
      engine._compare('0.30000000000000004', 'eq', '0.3') is False)

# --- 规则组合 all / any ---
rdfn = {
    'index_refs_json': [{'index_id': 1, 'alias': 'm1', 'version': 1},
                        {'index_id': 2, 'alias': 'm2', 'version': 1}],
    'conditions_json': [
        {'alias': 'm1', 'op': 'gt', 'threshold': 5},
        {'alias': 'm2', 'op': 'lt', 'threshold': 100},
    ],
    'combine': 'all',
}
out, detail = engine.run_rule(rdfn, {'m1': '10', 'm2': '50'})
check('规则 all 双真 → pass', out == 'pass', out)
check('规则明细含实际值', detail[0]['actual'] == '10', detail)
rdfn['combine'] = 'any'
out, _ = engine.run_rule(rdfn, {'m1': '1', 'm2': '50'})
check('规则 any 一真 → pass', out == 'pass', out)
out, _ = engine.run_rule(rdfn, {'m1': '1', 'm2': '500'})
check('规则 any 双假 → fail', out == 'fail', out)
try:
    engine.run_rule(rdfn, {'m1': '10'})
    check('规则缺别名拒绝', False)
except errors.BadRequest:
    check('规则缺别名拒绝', True)

# --- 框架四种组合 ---
def fdefn(combine, threshold=None):
    return {'combine': combine, 'threshold': threshold}

outs = [
    {'rule_value_id': 1, 'outcome': 'pass', 'weight': 1, 'veto': False},
    {'rule_value_id': 2, 'outcome': 'fail', 'weight': 1, 'veto': False},
]
out, score, detail = engine.run_frame(fdefn('all_pass'), outs)
check('框架 all_pass 含 fail → fail', out == 'fail', out)
out, score, detail = engine.run_frame(fdefn('any_pass'), outs)
check('框架 any_pass 含 pass → pass', out == 'pass', out)
out, score, detail = engine.run_frame(fdefn('weighted', '0.4'), outs)
check('框架 weighted 得分=0.5', score == '0.5', score)
check('框架 weighted ≥0.4 → pass', out == 'pass', out)
out, score, detail = engine.run_frame(fdefn('weighted', '0.6'), outs)
check('框架 weighted <0.6 → fail', out == 'fail', out)
veto_outs = [dict(outs[0]), dict(outs[1], veto=True)]
out, score, detail = engine.run_frame(fdefn('weighted', '0.1'), veto_outs)
check('框架 veto 一票否决', out == 'fail' and score is None, (out, score))
zero_outs = [dict(outs[0], weight=0), dict(outs[1], weight=0)]
try:
    engine.run_frame(fdefn('weighted', '0.5'), zero_outs)
    check('框架权重合计 0 拒绝', False)
except errors.BadRequest:
    check('框架权重合计 0 拒绝', True)

# --- 哈希复现口径 ---
spec = {'datasource_id': 1, 'source_table': 't', 'aggregate': 'sum'}
h = vc.spec_hash(spec)
snap = {'rows': [{'file_id': 1, 'record_id': 2, 'value': '10'}], 'filter': []}
vh = vc.value_hash(h, snap)
check('结果哈希可复算',
      vh == vc.value_hash(vc.spec_hash(dict(spec)), dict(snap)), vh)

print('P1 engine logic: {} checks passed'.format(ok))
