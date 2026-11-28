"""抽取结果记录、绑定和回执的隔离回归；全部使用内存 SQL 替身。"""
import unittest
from unittest.mock import Mock, patch

from c1_structure import service
from c1_structure.store import content_db, errors, loader as loader_mod
from c1_structure.store.catalog import results as result_repo
from c1_structure.store.loader import LoadRecordError


class _Cursor:
    def __init__(self):
        self.calls = []
        self.rows = []
        self.row = None
        self.lastrowid = 910
        self.missing = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, args=None):
        self.calls.append((sql, args))
        if sql.startswith('SELECT doc_id FROM c1_extract_result'):
            self.row = None if self.missing else (1,)
        elif sql.startswith('SELECT id FROM c1_load_binding'):
            self.row = (501,)
        elif sql.startswith('INSERT INTO c1_extract_record '):
            self.lastrowid += 1
        else:
            self.row = None

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, cursor):
        self.cur = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class ResultRepositoryIsolationTest(unittest.TestCase):
    def test_record_id_map_is_keyed_by_result_and_index(self):
        cur = _Cursor()
        cur.rows = [(910, 0), (911, 1)]
        conn = _Conn(cur)
        with patch.object(content_db.db, 'connect', return_value=conn):
            mapping = content_db.record_id_map(31)
        self.assertEqual({(31, 0): 910, (31, 1): 911}, mapping)
        self.assertEqual(('SELECT id, record_index FROM c1_extract_record'
                          ' WHERE extract_result_id=%s', (31,)),
                         cur.calls[0])
        self.assertTrue(conn.closed)

    def test_save_records_replaces_only_one_result_chain(self):
        cur = _Cursor()
        conn = _Conn(cur)
        records = [{'index': 0, 'values': {'设备名称': '泵机'},
                    'original': {'设备名称': '泵机'},
                    'lineage': {'设备名称': [{
                        'page': 1, 'space': 'source', 'cell_bbox': [1, 2, 3, 4],
                        'raw_text': '泵机'}]},
                    'review': {'state': 'confirmed'}}]
        with patch.object(content_db.db, 'connect', return_value=conn):
            self.assertEqual(1, content_db.save_records(31, records))
        deletes = [(sql, args) for sql, args in cur.calls
                   if sql.startswith('DELETE')]
        self.assertIn(('DELETE FROM c1_load_receipt'
                       ' WHERE load_binding_id=%s', (501,)), deletes)
        self.assertIn(('DELETE FROM c1_load_binding WHERE id=%s', (501,)), deletes)
        self.assertNotIn(502, [value for _, args in cur.calls for value in (args or ())])
        record_insert = next(args for sql, args in cur.calls
                             if sql.startswith('INSERT INTO c1_extract_record '))
        self.assertEqual((1, 31, 0), record_insert[:3])
        lineage_insert = next(args for sql, args in cur.calls
                              if sql.startswith('INSERT INTO c1_extract_record_lineage'))
        self.assertEqual((911, '设备名称', 0), lineage_insert[:3])
        self.assertEqual(('UPDATE c1_extract_result SET record_count=%s,'
                          ' updated_at=NOW() WHERE id=%s', (1, 31)), cur.calls[-1])
        self.assertEqual(1, conn.commits)
        self.assertEqual(0, conn.rollbacks)

    def test_missing_result_rolls_back_without_deleting_another_result(self):
        cur = _Cursor()
        cur.missing = True
        conn = _Conn(cur)
        with patch.object(content_db.db, 'connect', return_value=conn), \
                patch.object(content_db, 'purge_result_data') as purge:
            with self.assertRaises(errors.NotFound):
                content_db.save_records(99, [])
        purge.assert_not_called()
        self.assertEqual(1, conn.rollbacks)
        self.assertEqual(0, conn.commits)
        self.assertTrue(conn.closed)

    def test_document_purge_clears_every_result_and_legacy_binding_chain(self):
        class DocumentCursor(_Cursor):
            def execute(self, sql, args=None):
                super().execute(sql, args)
                if sql.startswith('SELECT id FROM c1_extract_result'):
                    self.rows = [(31,), (32,)]
                elif sql.startswith('SELECT id FROM c1_load_binding WHERE doc_id'):
                    self.rows = [(903,)]

            def fetchone(self):
                # 每次结果各有一条绑定；遗留文档绑定查询使用 fetchall。
                return (501 + len([c for c in self.calls
                                   if c[0].startswith('SELECT id FROM c1_load_binding')
                                   and 'extract_result_id' in c[0]]) - 1,)

        cur = DocumentCursor()
        result_repo.purge_document_results(cur, 1)
        receipt_deletes = [args for sql, args in cur.calls
                           if sql == 'DELETE FROM c1_load_receipt WHERE load_binding_id=%s']
        self.assertEqual([(501,), (502,), (903,)], receipt_deletes)
        self.assertIn(('DELETE FROM c1_extract_result WHERE id=%s', (31,)), cur.calls)
        self.assertIn(('DELETE FROM c1_extract_result WHERE id=%s', (32,)), cur.calls)
        self.assertIn(('DELETE FROM c1_load_receipt WHERE doc_id=%s', (1,)), cur.calls)


class _Catalog:
    def __init__(self):
        self.results = {31: {'id': 31, 'doc_id': 1}, 32: {'id': 32, 'doc_id': 1}}
        self.bindings = {
            31: {'id': 501, 'doc_id': 1, 'extract_result_id': 31,
                 'datasource_id': 2, 'load_table_id': 55,
                 'field_map_json': {'设备名称': 'device_name'},
                 'write_mode': 'insert', 'business_keys_json': [],
                 'status': 'confirmed'},
            32: {'id': 502, 'doc_id': 1, 'extract_result_id': 32,
                 'datasource_id': 2, 'load_table_id': 55,
                 'field_map_json': {'设备名称': 'device_name'},
                 'write_mode': 'insert', 'business_keys_json': [],
                 'status': 'confirmed'},
        }
        self.receipts = {501: [], 502: []}
        self.receipt_queries = []
        self.added_receipts = []
        self.quarantine = []
        self.finished = []
        self.states = []

    def get_extract_result(self, result_id):
        return self.results.get(result_id)

    def list_extract_results(self, doc_id):
        return [r for r in self.results.values() if r['doc_id'] == doc_id]

    def get_binding(self, extract_result_id=None, binding_id=None):
        if binding_id is not None:
            return next((b for b in self.bindings.values() if b['id'] == binding_id), None)
        return self.bindings.get(extract_result_id)

    def get_load_table(self, table_id):
        return {'id': table_id, 'target_table': 'inspection'}

    def get_datasource(self, datasource_id):
        return {'id': datasource_id, 'db_name': 'fake'}

    def list_receipts(self, load_binding_id=None, doc_id=None):
        self.receipt_queries.append(load_binding_id)
        return list(self.receipts.get(load_binding_id, []))

    def add_receipt(self, binding_id, index, record_id, action):
        row = {'load_binding_id': binding_id, 'record_index': index,
               'record_id': record_id, 'action': action}
        self.receipts[binding_id].append(row)
        self.added_receipts.append(row)

    def add_quarantine(self, *args, **kwargs):
        self.quarantine.append((args, kwargs))

    def finish_binding(self, binding_id, **kwargs):
        self.bindings[next(r for r, b in self.bindings.items()
                           if b['id'] == binding_id)]['status'] = kwargs['status']
        self.finished.append((binding_id, kwargs))

    def set_state(self, doc_id, state, error=None):
        self.states.append((doc_id, state, error))

    def start_binding(self, binding_id):
        self.bindings[next(r for r, b in self.bindings.items()
                           if b['id'] == binding_id)]['status'] = 'running'
        self.finished.append((binding_id, {'status': 'running'}))


class _ContentDB:
    def __init__(self):
        self.record_ids = {31: {(31, 0): 910, (31, 1): 912},
                           32: {(32, 0): 911, (32, 1): 913}}
        self.queries = []

    def get_records(self, result_id):
        self.queries.append(result_id)
        value = '泵机' if result_id == 31 else '风机'
        return {'files': [{'records': [
            {'index': 0, 'values': {'设备名称': value},
             'review': {'state': 'confirmed'}},
            {'index': 1, 'values': {'设备名称': value + '二'},
             'review': {'state': 'confirmed'}}]}]}

    def record_id_map(self, result_id):
        return self.record_ids[result_id]


class _Loader:
    LoadRecordError = LoadRecordError
    review_gate = staticmethod(loader_mod.review_gate)

    def __init__(self):
        self.calls = []
        self.preflights = []
        self.fail_index = None

    def connect_datasource(self, ds):
        return self

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def write_record(self, cur, table, field_map, values, write_mode, keys,
                     extra_values=None):
        self.calls.append((table, field_map, values, write_mode, keys,
                           extra_values))
        if extra_values['record_id'] == self.fail_index:
            raise LoadRecordError('模拟单条写入失败')
        return 'insert', str(extra_values['record_id'])

    def preflight(self, *args):
        self.preflights.append(args)


class BindingReceiptIsolationTest(unittest.TestCase):
    def setUp(self):
        self.catalog = _Catalog()
        self.content_db = _ContentDB()
        self.loader = _Loader()
        self.log = Mock()
        self.modules = {'store.catalog': self.catalog,
                        'store.content_db': self.content_db,
                        'store.loader': self.loader,
                        'store.errors': errors,
                        'tasklog': Mock(TaskLog=Mock(return_value=self.log))}
        self.load = patch.object(service, '_load', side_effect=lambda n: self.modules[n])
        self.load.start()
        self.addCleanup(self.load.stop)
        self.state = patch.dict(service.STATE, {'running': False, 'started': 1})
        self.state.start()
        self.addCleanup(self.state.stop)

    def run_result(self, result_id):
        service.run_load(result_id, self.catalog.bindings[result_id],
                         {'id': 2, 'db_name': 'fake'},
                         {'target_table': 'inspection'}, self.log)

    def test_same_index_in_two_results_uses_distinct_record_ids(self):
        self.run_result(31)
        self.assertEqual([910, 912],
                         [call[5]['record_id'] for call in self.loader.calls])
        self.assertEqual([501], [r['load_binding_id']
                                        for r in self.catalog.added_receipts[:1]])
        self.assertEqual([], self.catalog.receipts[502])
        self.run_result(32)
        self.assertEqual([910, 912, 911, 913],
                         [call[5]['record_id'] for call in self.loader.calls])
        self.assertEqual([501, 501, 502, 502],
                         [r['load_binding_id'] for r in self.catalog.added_receipts])

    def test_receipt_from_other_binding_does_not_skip_record(self):
        self.catalog.receipts[501] = [
            {'load_binding_id': 501, 'record_index': 0, 'record_id': 910}]
        self.run_result(31)
        self.assertEqual([912],
                         [call[5]['record_id'] for call in self.loader.calls])
        self.run_result(32)
        self.assertEqual([501, 502], self.catalog.receipt_queries)
        self.assertEqual([912, 911, 913],
                         [call[5]['record_id'] for call in self.loader.calls])
        self.assertEqual([0, 1],
                         [r['record_index'] for r in self.catalog.receipts[501]])

    def test_failed_record_quarantine_is_scoped_to_result_and_binding(self):
        self.loader.fail_index = 910
        self.run_result(31)
        self.assertEqual(1, len(self.catalog.quarantine))
        args, kwargs = self.catalog.quarantine[0]
        self.assertEqual(('load', '模拟单条写入失败'), args[2:4])
        self.assertEqual({'extract_result_id': 31, 'load_binding_id': 501}, kwargs)
        self.assertEqual([], self.catalog.receipts[502])
        self.assertEqual('failed', self.catalog.bindings[31]['status'])
        self.assertEqual('confirmed', self.catalog.bindings[32]['status'])

    def test_confirmed_launch_preflights_only_its_result_mapping(self):
        with patch.object(service.threading, 'Thread') as thread:
            response = service.launch_load(31)
        self.assertEqual({'ok': True, 'doc_id': 1, 'extract_result_id': 31,
                          'load_binding_id': 501}, response)
        self.assertEqual([({'id': 2, 'db_name': 'fake'}, 'inspection',
                           {'设备名称': 'device_name'}, 'insert',
                           ['设备名称'], [])], self.loader.preflights)
        self.assertEqual([31], self.content_db.queries)
        self.assertEqual(service.run_load, thread.call_args.kwargs['target'])
        self.assertEqual((31, self.catalog.bindings[31]),
                         thread.call_args.kwargs['args'][:2])
        self.assertEqual([], self.loader.calls)

    def test_launch_rejects_unconfirmed_binding_before_preflight_or_write(self):
        self.catalog.bindings[31]['status'] = 'edited'
        with self.assertRaises(errors.Conflict):
            service.launch_load(31)
        self.assertEqual([], self.loader.preflights)
        self.assertEqual([], self.loader.calls)
        self.assertEqual([], self.catalog.receipt_queries)


if __name__ == '__main__':
    unittest.main()
