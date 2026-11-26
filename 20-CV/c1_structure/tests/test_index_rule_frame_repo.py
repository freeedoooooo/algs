"""简化版 repo 逻辑单测（不连 DB）：校验规则 + 命名口径。

版本/哈希/配置快照已按用户裁决移除，故不再测试哈希。
"""
import os
import sys
import glob
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
PKG = os.path.basename(ROOT)

def _load(name):
    return importlib.import_module(PKG + '.' + name)

ir = _load('store.index_repo')
rr = _load('store.rule_repo')
fr = _load('store.frame_repo')
errors = _load('store.errors')

ok = 0

def check(name, cond, detail=''):
    global ok
    if cond:
        ok += 1
        print('  PASS ' + name)
    else:
        raise AssertionError('FAIL ' + name + ' :: ' + str(detail))

# --- index 校验 ---
for args, label in [
    (('', 1, 't', None, 'sum'), '空指标名'),
    (('x', 1, 't', None, 'median'), '非法聚合'),
    (('x', 1, '', None, 'sum'), '空表名'),
]:
    try:
        ir.save_def(*args)
        check(label + ' 拒绝', False)
    except errors.BadRequest:
        check(label + ' 拒绝', True)
try:
    ir.save_def('x', 1, 't', None, 'sum',
                [{'column': 'f', 'op': 'like', 'value': 1}])
    check('非法过滤 op 拒绝', False)
except errors.BadRequest:
    check('非法过滤 op 拒绝', True)

# --- rule 校验 ---
refs = [{'index_id': 1, 'alias': 'm1'}]
conds = [{'alias': 'm1', 'op': 'gt', 'threshold': 100}]
for args, label in [
    (('r', refs, [{'alias': 'm2', 'op': 'gt', 'threshold': 1}]), '未定义别名'),
    (('r', refs, [{'alias': 'm1', 'op': 'regex', 'threshold': 1}]), '非法比较 op'),
    (('r', [], conds), '空指标引用'),
]:
    try:
        rr.save_def(*args)
        check(label + ' 拒绝', False)
    except errors.BadRequest:
        check(label + ' 拒绝', True)

# --- frame 校验 ---
rrefs = [{'rule_id': 1, 'weight': 1, 'veto': False}]
try:
    fr.save_def('f', rrefs, 'weighted', None)
    check('weighted 缺阈值拒绝', False)
except errors.BadRequest:
    check('weighted 缺阈值拒绝', True)
try:
    fr.save_def('f', rrefs, 'no_such_combine', 0.8)
    check('非法组合拒绝', False)
except errors.BadRequest:
    check('非法组合拒绝', True)

# --- 指标结果先删后写 ---
class ValueCursor:
    def __init__(self):
        self.calls = []
        self.lastrowid = 9
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, args):
        self.calls.append((sql, args))
    def fetchone(self):
        return (1,)


class ValueConnection:
    def __init__(self):
        self.cur = ValueCursor()
        self.commits = 0
        self.closed = False
    def cursor(self):
        return self.cur
    def commit(self):
        self.commits += 1
    def close(self):
        self.closed = True


value_conn = ValueConnection()
orig_connect = ir.db.connect
ir.db.connect = lambda: value_conn
try:
    vid = ir.add_value(1, '12.5')
    sqls = [sql for sql, args in value_conn.cur.calls]
    check('指标结果返回新 ID', vid == 9)
    check('指标结果先删后写',
          len(sqls) == 3 and sqls[1].startswith('DELETE FROM c1_index_value')
          and sqls[2].startswith('INSERT INTO c1_index_value'), sqls)
    check('指标结果删除参数正确',
          value_conn.cur.calls[1][1] == (1,))
    check('指标结果事务提交并关闭连接',
          value_conn.commits == 1 and value_conn.closed)
finally:
    ir.db.connect = orig_connect


# --- 简化口径：无版本/哈希列 ---
for mod in (ir, rr, fr):
    for cols_name in ('_INFO_COLS', '_VALUE_COLS'):
        cols = getattr(mod, cols_name)
        check(mod.__name__.split('.')[-1] + ' ' + cols_name + ' 无版本/哈希',
              not any(k in cols for k in ('version', 'result_hash', 'spec_hash')),
              cols)

# --- 命名口径：无旧前缀残留 ---
py_files = ([os.path.join(ROOT, 'app.py'), os.path.join(ROOT, 'service.py')]
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
