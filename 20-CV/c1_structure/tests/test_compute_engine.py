"""极简引擎单测（不连业务库）：WHERE 白名单、比较、组合、结果文本。"""
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

# --- WHERE ---
sql, args = engine._where([
    {'column': 'file_id', 'op': 'eq', 'value': 12},
    {'column': 'amt', 'op': 'gte', 'value': 100}],
    allow_cols={'file_id', 'amt'})
check('WHERE 转义/参数顺序',
      sql == ' WHERE `file_id` = %s AND `amt` >= %s' and args == [12, 100])
check('WHERE NULL',
      'IS NULL' in engine._where([{'column': 'x', 'op': 'eq', 'value': None}])[0])
for bad, label in [([{'column': 'no', 'op': 'eq', 'value': 1}], '列白名单'),
                   ([{'column': 'x', 'op': 'like', 'value': '%'}], '非法 op')]:
    try:
        engine._where(bad, allow_cols={'file_id'})
        check(label + ' 拒绝', False)
    except errors.BadRequest:
        check(label + ' 拒绝', True)

# --- 比较 ---
for actual, op, th, expected in [
    ('10', 'gt', '5', True), ('10', 'gte', '10', True),
    ('10', 'lt', '5', False), ('10', 'lte', '10', True),
    ('10', 'eq', 10, True), ('10', 'ne', 10, False),
    ('10', 'between', [5, 20], True), ('10', 'between', [11, 20], False)]:
    check('比较 {}({},{})'.format(op, actual, th),
          engine._compare(actual, op, th) is expected)
check('Decimal 精度',
      engine._compare('0.30000000000000004', 'eq', '0.3') is False)

# --- 规则结果只返回 pass/fail ---
rdfn = {'index_refs_json': [{'index_id': 1, 'alias': 'm1'},
                            {'index_id': 2, 'alias': 'm2'}],
        'conditions_json': [{'alias': 'm1', 'op': 'gt', 'threshold': 5},
                            {'alias': 'm2', 'op': 'lt', 'threshold': 100}],
        'combine': 'all'}
check('规则 all 双真', engine.compute_rule(rdfn, {'m1': '10', 'm2': '50'}) == 'pass')
rdfn['combine'] = 'any'
check('规则 any 一真', engine.compute_rule(rdfn, {'m1': '1', 'm2': '50'}) == 'pass')
check('规则 any 双假', engine.compute_rule(rdfn, {'m1': '1', 'm2': '500'}) == 'fail')
try:
    engine.compute_rule(rdfn, {'m1': '10'})
    check('缺别名拒绝', False)
except errors.BadRequest:
    check('缺别名拒绝', True)

# --- 框架结果只返回一个文本 ---
def fdefn(combine, threshold=None):
    return {'combine': combine, 'threshold': threshold}

outs = [{'outcome': 'pass', 'weight': 1, 'veto': False},
        {'outcome': 'fail', 'weight': 1, 'veto': False}]
check('框架 all_pass', engine.compute_frame(fdefn('all_pass'), outs) == 'fail')
check('框架 any_pass', engine.compute_frame(fdefn('any_pass'), outs) == 'pass')
r = engine.compute_frame(fdefn('weighted', '0.4'), outs)
check('框架 weighted 得分文本', r == 'pass（0.5）', r)
check('框架 weighted 不达标',
      engine.compute_frame(fdefn('weighted', '0.6'), outs) == 'fail（0.5）')
check('框架一票否决',
      engine.compute_frame(fdefn('weighted', '0.1'),
                           [outs[0], dict(outs[1], veto=True)]) == 'fail（一票否决）')
try:
    engine.compute_frame(fdefn('weighted', '0.5'),
                         [dict(outs[0], weight=0), dict(outs[1], weight=0)])
    check('权重合计 0 拒绝', False)
except errors.BadRequest:
    check('权重合计 0 拒绝', True)

# --- 指标数据源样本 ---
class FakeCursor:
    def __init__(self, owner):
        self.owner = owner
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, args):
        self.owner.calls.append((sql, args))
    def fetchone(self):
        return (53,)
    def fetchall(self):
        return [(7, 901, b'abc')]


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.closed = False
    def cursor(self):
        return FakeCursor(self)
    def close(self):
        self.closed = True


fake_conn = FakeConnection()
orig_check = engine._check_index_def
orig_connect = engine.loader.connect_datasource
engine._check_index_def = lambda d: ({'id': 1}, 'orders',
                                     ['file_id', 'record_id', 'amt', 'note'],
                                     'amt')
engine.loader.connect_datasource = lambda ds: fake_conn
try:
    preview_def = {'datasource_id': 1, 'source_table': 'orders',
                   'source_column': 'amt', 'aggregate': 'sum',
                   'filter_json': [{'column': 'amt', 'op': 'gte', 'value': 100}]}
    out = engine.source_preview(preview_def, limit=999)
    check('样本总数与有界行数', out['total'] == 53 and len(out['items']) == 1)
    check('样本最多 50 行', out['limit'] == 50 and out['has_more'])
    check('样本列仅含溯源/聚合/筛选列',
          out['columns'] == ['file_id', 'record_id', 'amt'])
    check('样本二进制安全显示', out['items'][0]['note'] if 'note' in out['items'][0]
          else out['items'][0]['record_id'] == 901)
    check('样本连接关闭', fake_conn.closed)
    sql, args = fake_conn.calls[1]
    check('样本筛选参数化且 LIMIT 参数化',
          'WHERE `amt` >= %s LIMIT %s' in sql and args == [100, 50])
    preview_def['filter_json'][0]['column'] = 'amt`; DROP TABLE orders; --'
    try:
        engine.source_preview(preview_def)
        check('样本过滤列白名单拒绝', False)
    except errors.BadRequest:
        check('样本过滤列白名单拒绝', True)
finally:
    engine._check_index_def = orig_check
    engine.loader.connect_datasource = orig_connect

print('engine logic: {} checks passed'.format(ok))
