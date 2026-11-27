"""计算流程图布局仓储单测（不连 DB）。"""
import os
import sys
import importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
repo = importlib.import_module(os.path.basename(ROOT) + '.store.compute_layout_repo')
errors = importlib.import_module(os.path.basename(ROOT) + '.store.errors')

ok = 0


def check(name, cond, detail=''):
    global ok
    if not cond:
        raise AssertionError('FAIL ' + name + ' :: ' + str(detail))
    ok += 1
    print('  PASS ' + name)


class Cursor:
    def __init__(self, missing=False, defs=True):
        self.missing, self.defs = missing, defs
        self.calls, self.batch = [], []
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, args=None):
        self.calls.append((sql, args))
        if self.missing and 'c1_compute_graph_layout' in sql:
            raise Exception(1146, "Table doesn't exist")
        if sql.startswith('SELECT scope,def_id'):
            self.result = [('index', 1, 10.5, 20.0)]
        elif sql.startswith('SELECT id FROM c1_'):
            self.result = [(args[0],)] if self.defs else []

    def executemany(self, sql, values):
        if self.missing:
            raise Exception(1146, "Table doesn't exist")
        self.calls.append((sql, values))
        self.batch = list(values)

    def fetchall(self):
        return self.result

    @property
    def description(self):
        return [('scope',), ('def_id',), ('pos_x',), ('pos_y',)]


class Conn:
    def __init__(self, cursor):
        self.cur, self.committed = cursor, False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def close(self):
        pass


def use(cur):
    conn = Conn(cur)
    repo.db.connect = lambda *a, **k: conn
    return conn


bad_items = [None, {}, [{'scope': 'x', 'id': 1, 'x': 0, 'y': 0}],
             [{'scope': 'index', 'id': True, 'x': 0, 'y': 0}],
             [{'scope': 'index', 'id': 1.5, 'x': 0, 'y': 0}],
             [{'scope': 'index', 'id': 1, 'x': float('nan'), 'y': 0}],
             [{'scope': 'index', 'id': 1, 'x': 1000001, 'y': 0}],
             [{'scope': 'index', 'id': 1, 'x': 0, 'y': 0}] * 2]
for item in bad_items:
    try:
        repo.normalize_items(item)
        check('非法布局拒绝 ' + repr(item)[:30], False)
    except errors.BadRequest:
        check('非法布局拒绝 ' + repr(item)[:30], True)

conn = use(Cursor(missing=True))
check('缺表时读取返回未安装', repo.list_layout() ==
      {'available': False, 'items': []})

conn = use(Cursor())
check('读取坐标字段投影', repo.list_layout()['items'] ==
      [{'scope': 'index', 'id': 1, 'x': 10.5, 'y': 20.0}])

items = [{'scope': 'document', 'id': '6', 'x': '30', 'y': '70'},
         {'scope': 'source', 'id': 1, 'x': 220, 'y': 80},
         {'scope': 'index', 'id': '1', 'x': '30', 'y': '70'},
         {'scope': 'rule', 'id': 2, 'x': 320, 'y': 170}]
conn = use(Cursor())
check('批量保存成功', repo.save_layout(items)['saved'] == 4 and conn.committed)
check('保存使用参数化 upsert', len(conn.cur.batch) == 4 and
      'ON DUPLICATE KEY UPDATE' in conn.cur.calls[-1][0])

try:
    conn = use(Cursor(defs=False))
    repo.save_layout(items)
    check('不存在定义拒绝', False)
except errors.NotFound:
    check('不存在定义拒绝', True)

try:
    conn = use(Cursor(missing=True))
    repo.save_layout(items)
    check('缺表时保存提示迁移', False)
except errors.BadRequest as exc:
    check('缺表时保存提示迁移', '005_compute_graph_layout.sql' in exc.msg)

repo.delete_for_def(Cursor(missing=True), 'index', 1)
check('旧库无布局表仍允许删除定义', True)

print('compute layout: {} checks passed'.format(ok))
