"""当前页批量溯源单测（不连 DB）。"""
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
repo = importlib.import_module(os.path.basename(ROOT) + '.store.content_db')
errors = importlib.import_module(os.path.basename(ROOT) + '.store.errors')

RECORD_COLS = [
    'id', 'file_id', 'record_index', 'review_state', 'state', 'load_table_id',
    'field_name', 'page', 'space', 'cell_bbox', 'raw_text', 'table_index',
    'table_scope',
]
FIELD_COLS = ['load_table_id', 'rule_field', 'target_column']


class Cursor:
    def __init__(self):
        self.calls = []
        self.result = []
        self.cols = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, args=None):
        self.calls.append((sql, args))
        if 'FROM c1_staging_record' in sql:
            self.cols = RECORD_COLS
            self.result = [
                (101, 1, 0, 'confirmed', 'loaded', 10, 'amount', 1,
                 'source', '[1,2,3,4]', '100', 0, 'page'),
                (102, 2, 0, 'confirmed', 'loaded', 10, None, None,
                 None, None, None, None, None),
                (103, 999, 0, 'confirmed', None, None, None, None,
                 None, None, None, None, None),
                (104, 1, 1, 'confirmed', 'loaded', 10, 'amount', 1,
                 'source', None, '100', 0, 'page'),
            ]
        elif 'FROM c1_load_table_field' in sql:
            self.cols = FIELD_COLS
            self.result = [(10, 'amount', 'amt'), (10, 'memo', 'note')]
        else:
            raise AssertionError(sql)

    @property
    def description(self):
        return [(c,) for c in self.cols]

    def fetchall(self):
        return self.result


class Conn:
    def __init__(self):
        self.cur = Cursor()

    def cursor(self):
        return self.cur

    def close(self):
        pass


conn = Conn()
repo.db.connect = lambda *a, **k: conn
items = repo.trace_records(
    ['101', 101, 102, 103, 104, 105], ['amt', 'note', 'unmapped'])
assert len(conn.cur.calls) == 2, conn.cur.calls
assert [x['record_id'] for x in items] == [101, 102, 103, 104, 105]
assert items[0]['fields']['amt']['traceable'] is True
assert items[0]['fields']['amt']['anchors'][0]['cell_bbox'] == [1, 2, 3, 4]
assert items[0]['fields']['note']['reason'] == 'no_anchor'
assert items[0]['fields']['unmapped']['reason'] == 'unmapped'
assert items[1]['fields']['amt']['reason'] == 'no_anchor'
assert items[2]['fields']['amt']['reason'] == 'missing_file'
assert items[3]['fields']['amt']['reason'] == 'no_bbox'
assert items[4]['fields']['amt']['reason'] == 'missing_record'

for bad in (None, [], [True], ['x'], list(range(201))):
    try:
        repo.trace_records(bad, ['amt'])
    except errors.BadRequest:
        pass
    else:
        raise AssertionError('expected BadRequest for {!r}'.format(bad))

print('trace batch: all checks passed')
