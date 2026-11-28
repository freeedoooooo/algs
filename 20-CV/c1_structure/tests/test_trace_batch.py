"""当前页批量溯源单测（不连 DB）：结果快照映射与单结果过滤。"""
import importlib
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
repo = importlib.import_module(os.path.basename(ROOT) + '.store.content_db')
errors = importlib.import_module(os.path.basename(ROOT) + '.store.errors')

RECORD_COLS = [
    'id', 'doc_id', 'extract_result_id', 'record_index', 'review_state',
    'state', 'field_map_json', 'field_name', 'page', 'space', 'cell_bbox',
    'raw_text', 'table_index', 'table_scope',
]


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
        if 'FROM c1_extract_record sr' not in sql:
            raise AssertionError(sql)
        self.cols = RECORD_COLS
        self.result = [
            (101, 1, 11, 0, 'confirmed', 'loaded',
             '{"设备名称":"device_name","备注":"note"}',
             '设备名称', 1, 'source', '[1,2,3,4]', '泵机', 0, 'page'),
            (102, 1, 11, 1, 'confirmed', 'loaded',
             '{"设备名称":"device_name","备注":"note"}',
             None, None, None, None, None, None, None),
            (103, 999, 11, 0, 'confirmed', None,
             '{"设备名称":"device_name","备注":"note"}',
             None, None, None, None, None, None, None),
            (104, 1, 12, 0, 'confirmed', 'loaded',
             '{"设备名称":"device_name"}',
             '设备名称', 1, 'source', None, '风机', 0, 'page'),
        ]
        if 'sr.extract_result_id=%s' in sql and args:
            self.result = [row for row in self.result
                           if row[2] == args[-1]]

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


class TraceBatchTest(unittest.TestCase):
    def setUp(self):
        self.conn = Conn()
        self.connect = patch.object(repo.db, 'connect', return_value=self.conn)
        self.connect.start()
        self.addCleanup(self.connect.stop)

    def test_real_binding_map_resolves_target_column_to_source_field(self):
        items = repo.trace_records(
            [101, 102, 103, 104, 105], ['device_name', 'note', 'unmapped'])
        self.assertEqual(1, len(self.conn.cur.calls))
        self.assertEqual([101, 102, 103, 104, 105],
                         [item['record_id'] for item in items])
        # binding 的真实形状是 {中文字段: 目标列}，不能按目标列正向查字段。
        self.assertEqual('设备名称', items[0]['fields']['device_name']['field'])
        self.assertTrue(items[0]['fields']['device_name']['traceable'])
        self.assertEqual([1, 2, 3, 4],
                         items[0]['fields']['device_name']['anchors'][0]['cell_bbox'])
        self.assertEqual('no_anchor', items[0]['fields']['note']['reason'])
        self.assertEqual('unmapped', items[0]['fields']['unmapped']['reason'])
        self.assertEqual('no_anchor', items[1]['fields']['device_name']['reason'])
        self.assertEqual('missing_doc', items[2]['fields']['device_name']['reason'])
        self.assertEqual('no_bbox', items[3]['fields']['device_name']['reason'])
        self.assertEqual('missing_record', items[4]['fields']['device_name']['reason'])

    def test_result_scope_filters_before_trace_projection(self):
        self.conn.cur.calls.clear()
        items = repo.trace_records([101, 104], ['device_name'],
                                   extract_result_id=11)
        sql, args = self.conn.cur.calls[0]
        self.assertIn('sr.extract_result_id=%s', sql)
        self.assertEqual([101, 104, 11], args)
        self.assertEqual([101, 104], [item['record_id'] for item in items])
        self.assertEqual(11, items[0]['extract_result_id'])
        # 跨结果 ID 保留占位但不泄露另一结果的字段、血缘或绑定。
        self.assertIsNone(items[1]['extract_result_id'])
        self.assertEqual({}, items[1]['field_map'])
        self.assertEqual('missing_record',
                         items[1]['fields']['device_name']['reason'])

    def test_invalid_batch_arguments_are_rejected_before_database_access(self):
        for record_ids in (None, [], [True], ['x'], list(range(201))):
            with self.subTest(record_ids=record_ids):
                with self.assertRaises(errors.BadRequest):
                    repo.trace_records(record_ids, ['device_name'])
        self.assertEqual([], self.conn.cur.calls)


if __name__ == '__main__':
    unittest.main()
