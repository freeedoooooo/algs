"""简化版 compute 引擎单测（不连业务库）：WHERE 白名单、比较、组合、精简快照。"""
import os
import sys
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
PKG = os.path.basename(ROOT)

def _load(name):
    return importlib.import_module(PKG + '.' + name)

engine = _load('compute.engine')
errors = _load('store.errors')

ok = 0

def check(name, cond, detail=''):
    global ok
    if cond:
        ok += 1
        print('  PASS ' + name)
    else:
        raise AssertionError('FAIL ' + name + ' :: ' + str(detail))

# --- WHERE 构造 ---
sql, args = engine._where([
    {'column': 'file_id', 'op': 'eq', 'value': 12},
    {'column': 'amt', 'op': 'gte', 'value': 100},
], allow_cols={'file_id', 'amt'})
check('WHERE 转义/参数顺序',
      sql == ' WHERE `file_id` = %s AND `amt` >= %s' and args == [12, 100],
      (sql, args))
sql2, args2 = engine._where([{'column': 'file_id', 'op': 'eq', 'value': None}])
check('WHERE NULL 分支', 'IS NULL' in sql2 and args2 == [], (sql2, args2))
for bad, label in [([{'column': 'no', 'op': 'eq', 'value': 1}], '列白名单'),
                   ([{'column': 'x', 'op': 'like', 'value': '%'}], '非法 op')]:
    try:
        engine._where(bad, allow_cols={'file_id'})
        check(label + ' 拒绝', False)
    except errors.BadRequest:
        check(label + ' 拒绝', True)

# --- 比较算子 ---
cmp_cases = [
    ('10', 'gt', '5', True), ('10', 'gte', '10', True),
    ('10', 'lt', '5', False), ('10', 'lte', '10', True),
    ('10', 'eq', 10, True), ('10', 'ne', 10, False),
    ('10', 'between', [5, 20], True), ('10', 'between', [11, 20], False),
]
for actual, op, th, expected in cmp_cases:
    check('比较 {}({},{})'.format(op, actual, th),
          engine._compare(actual, op, th) is expected)
check('Decimal 精度',
      engine._compare('0.30000000000000004', 'eq', '0.3') is False)

# --- 规则明细：只含 alias/actual/passed，无配置副本 ---
rdfn = {
    'index_refs_json': [{'index_id': 1, 'alias': 'm1'},
                        {'index_id': 2, 'alias': 'm2'}],
    'conditions_json': [
        {'alias': 'm1', 'op': 'gt', 'threshold': 5},
        {'alias': 'm2', 'op': 'lt', 'threshold': 100},
    ],
    'combine': 'all',
}
out, detail = engine.run_rule(rdfn, {'m1': '10', 'm2': '50'})
check('规则 all 双真 → pass', out == 'pass', out)
check('明细只留 alias/actual/passed',
      all(set(d) == {'alias', 'actual', 'passed'} for d in detail), detail)
rdfn['combine'] = 'any'
check('规则 any 一真 → pass',
      engine.run_rule(rdfn, {'m1': '1', 'm2': '50'})[0] == 'pass')
check('规则 any 双假 → fail',
      engine.run_rule(rdfn, {'m1': '1', 'm2': '500'})[0] == 'fail')
try:
    engine.run_rule(rdfn, {'m1': '10'})
    check('缺别名拒绝', False)
except errors.BadRequest:
    check('缺别名拒绝', True)

# --- 框架组合 ---
def fdefn(combine, threshold=None):
    return {'combine': combine, 'threshold': threshold}

outs = [{'rule_value_id': 1, 'outcome': 'pass', 'weight': 1, 'veto': False},
        {'rule_value_id': 2, 'outcome': 'fail', 'weight': 1, 'veto': False}]
check('框架 all_pass 含 fail → fail',
      engine.run_frame(fdefn('all_pass'), outs)[0] == 'fail')
check('框架 any_pass 含 pass → pass',
      engine.run_frame(fdefn('any_pass'), outs)[0] == 'pass')
out, score, detail = engine.run_frame(fdefn('weighted', '0.4'), outs)
check('框架 weighted 得分=0.5 且 pass', score == '0.5' and out == 'pass')
check('框架明细只留结论/贡献',
      all(set(d) == {'rule_value_id', 'outcome', 'contribution'}
          for d in detail), detail)
check('框架 weighted <0.6 → fail',
      engine.run_frame(fdefn('weighted', '0.6'), outs)[0] == 'fail')
veto = [dict(outs[0]), dict(outs[1], veto=True)]
out, score, _ = engine.run_frame(fdefn('weighted', '0.1'), veto)
check('框架 veto 一票否决', out == 'fail' and score is None)
try:
    engine.run_frame(fdefn('weighted', '0.5'),
                     [dict(outs[0], weight=0), dict(outs[1], weight=0)])
    check('权重合计 0 拒绝', False)
except errors.BadRequest:
    check('权重合计 0 拒绝', True)

print('P1 engine logic: {} checks passed'.format(ok))
