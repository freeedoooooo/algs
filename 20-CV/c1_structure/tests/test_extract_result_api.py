"""多抽取结果 HTTP 路由回归：路径 result_id 必须贯穿存储和编排调用。"""
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from c1_structure import app as app_mod


class _Catalog:
    def __init__(self):
        self.results = {
            31: {'id': 31, 'doc_id': 1, 'rule_id': 7, 'status': 'ready',
                 'rule_name': '设备规则', 'record_count': 1},
            32: {'id': 32, 'doc_id': 1, 'rule_id': 8, 'status': 'ready',
                 'rule_name': '日期规则', 'record_count': 1},
        }
        self.bindings = {
            31: {'id': 501, 'extract_result_id': 31, 'doc_id': 1,
                 'status': 'edited'},
            32: {'id': 502, 'extract_result_id': 32, 'doc_id': 1,
                 'status': 'confirmed'},
        }
        self.receipt_queries = []

    def get_file(self, file_id):
        return {'id': file_id, 'name': 'a.pdf'} if file_id == 1 else None

    def get_extract_result(self, result_id):
        return self.results.get(result_id)

    def list_extract_results(self, doc_id):
        return [r for r in self.results.values() if r['doc_id'] == doc_id]

    def list_bindings(self, doc_id=None):
        return [b for b in self.bindings.values()
                if doc_id is None or b['doc_id'] == doc_id]

    def get_binding(self, extract_result_id=None, binding_id=None):
        if binding_id is not None:
            return next((b for b in self.bindings.values() if b['id'] == binding_id), None)
        return self.bindings.get(extract_result_id)

    def list_receipts(self, load_binding_id=None, doc_id=None):
        self.receipt_queries.append((load_binding_id, doc_id))
        return [{'load_binding_id': load_binding_id, 'record_index': 0}]


class ExtractResultApiTest(unittest.TestCase):
    def setUp(self):
        self.catalog = _Catalog()
        self.content_db = Mock()
        self.content_db.get_records.side_effect = lambda result_id: {
            'doc_id': 1, 'extract_result_id': result_id,
            'records': [{'index': 0,
                         'values': {'设备名称': '泵机' if result_id == 31 else '风机'}}]}
        self.content_db.record_id_map.side_effect = lambda result_id: {
            (result_id, 0): 910 if result_id == 31 else 911}
        self.content_db.gate_counts.side_effect = lambda result_id: {
            'records_n': 1, 'pending': 1 if result_id == 31 else 0}
        self.content_db.set_review.return_value = 1
        self.planner = Mock()
        self.planner.get_plan.side_effect = lambda result_id: {
            'status': 'ready', 'extract_result_id': result_id}
        self.planner.plan_for_extract_result.return_value = {'status': 'ready'}
        self.auto = Mock()
        self.auto.apply_plan.return_value = {'ok': True}
        self.modules = {'store.catalog': self.catalog,
                        'store.content_db': self.content_db,
                        'store.load_planner': self.planner,
                        'auto_service': self.auto}
        self.load = patch.object(app_mod, '_load', side_effect=lambda n: self.modules[n])
        self.load.start()
        self.addCleanup(self.load.stop)
        # 不进入 lifespan：避免默认数据源补种和任何真实数据库访问。
        self.client = TestClient(app_mod.app)

    def test_process_page_route_serves_result_workflow(self):
        response = self.client.get('/process?file=1&node=extract&result=31')
        self.assertEqual(200, response.status_code)
        self.assertIn('/static/process.js', response.text)

    def test_result_list_and_detail_keep_independent_bindings(self):
        response = self.client.get('/api/sources/1/extract-results')
        self.assertEqual(200, response.status_code)
        items = response.json()['items']
        self.assertEqual([31, 32], [item['id'] for item in items])
        self.assertEqual([501, 502], [item['load_binding']['id'] for item in items])
        detail = self.client.get('/api/extract-results/31').json()
        self.assertEqual(31, detail['result']['id'])
        self.assertEqual(501, detail['load_binding']['id'])
        self.assertEqual(404, self.client.get('/api/extract-results/99').status_code)

    def test_staging_gate_and_review_use_path_result_id(self):
        staging = self.client.get('/api/extract-results/31/staging')
        self.assertEqual(31, staging.json()['extract_result_id'])
        self.content_db.get_records.assert_called_once_with(31)
        gate = self.client.get('/api/extract-results/32/gate').json()
        self.assertEqual(0, gate['pending'])
        self.content_db.gate_counts.assert_called_once_with(32)
        with patch.object(app_mod.service, 'derive_review_state',
                          return_value='to_review') as derive:
            response = self.client.post(
                '/api/extract-results/31/staging/review',
                json={'indexes': [0], 'state': 'confirmed'})
        self.assertEqual({'ok': True, 'updated': 1, 'doc_state': 'to_review'},
                         response.json())
        self.content_db.set_review.assert_called_once_with(31, [0], 'confirmed')
        derive.assert_called_once_with(31)

    def test_loaded_result_is_read_only_but_other_result_remains_reviewable(self):
        response = self.client.post(
            '/api/extract-results/32/staging/review',
            json={'indexes': [0], 'state': 'confirmed'})
        self.assertEqual(409, response.status_code)
        self.content_db.set_review.assert_not_called()
        with patch.object(app_mod.service, 'derive_review_state', return_value='to_load'):
            response = self.client.post(
                '/api/extract-results/31/staging/review',
                json={'indexes': [0], 'state': 'confirmed'})
        self.assertEqual(200, response.status_code)
        self.content_db.set_review.assert_called_once_with(31, [0], 'confirmed')

    def test_record_id_routes_include_result_identity(self):
        items = self.client.get('/api/extract-results/31/record-ids').json()['items']
        self.assertEqual([{'index': 0, 'record_id': 910}], items)
        items = self.client.get('/api/sources/1/record-ids').json()['items']
        self.assertEqual([
            {'extract_result_id': 31, 'index': 0, 'record_id': 910},
            {'extract_result_id': 32, 'index': 0, 'record_id': 911}], items)
        self.assertEqual([31, 32], [c.args[0]
                                    for c in self.content_db.record_id_map.call_args_list[-2:]])

    def test_rerun_uses_result_snapshot_route_and_literal_force(self):
        with patch.object(app_mod.service, 'run_extract',
                          return_value={'ok': True}) as run:
            response = self.client.post(
                '/api/extract-results/31/rerun', json={'force': 1})
            self.assertEqual(200, response.status_code)
            run.assert_called_once_with(1, force=False, extract_result_id=31)
            self.client.post('/api/extract-results/32/rerun', json={'force': True})
            self.assertEqual(32, run.call_args.kwargs['extract_result_id'])
            self.assertTrue(run.call_args.kwargs['force'])

    def test_plan_apply_and_load_are_scoped_to_one_result(self):
        self.assertEqual(31, self.client.get(
            '/api/extract-results/31/load-plan').json()['extract_result_id'])
        intent = {'datasource_id': 2, 'target_table': 'inspection', 'confirmed': True}
        response = self.client.post('/api/extract-results/31/load-plan',
                                    json={'intent': intent})
        self.assertEqual(200, response.status_code)
        self.planner.plan_for_extract_result.assert_called_once_with(31, 2, intent)
        response = self.client.post('/api/extract-results/31/load-plan/apply',
                                    json={'intent': intent})
        self.assertEqual({'ok': True}, response.json())
        self.auto.apply_plan.assert_called_once_with(31, intent)
        with patch.object(app_mod.service, 'launch_load',
                          return_value={'ok': True}) as launch:
            response = self.client.post('/api/extract-results/31/load')
            self.assertEqual(200, response.status_code)
            launch.assert_called_once_with(31)

    def test_empty_preview_reuses_saved_binding(self):
        with patch.object(app_mod.service, 'preview_load',
                          return_value={'ok': True, 'total': 1}) as preview:
            response = self.client.post('/api/extract-results/31/load-preview', json={})
        self.assertEqual(200, response.status_code)
        preview.assert_called_once_with(31, draft=None)

    def test_result_load_log_reads_only_its_binding_receipts(self):
        first = self.client.get('/api/extract-results/31/load-log').json()['items']
        self.assertEqual([{'load_binding_id': 501, 'record_index': 0}], first)
        second = self.client.get('/api/extract-results/32/load-log').json()['items']
        self.assertEqual([{'load_binding_id': 502, 'record_index': 0}], second)
        self.assertEqual([(501, None), (502, None)], self.catalog.receipt_queries)


if __name__ == '__main__':
    unittest.main()
