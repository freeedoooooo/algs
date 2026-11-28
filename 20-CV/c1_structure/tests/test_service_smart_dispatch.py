"""S2 单测：service.run_extract 按 extraction_spec_json 分流并隔离结果。"""
import copy
import os
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect, service
from c1_structure.store import content, errors


class _Catalog:
    def __init__(self):
        self.files = {1: {'id': 1, 'state': 'to_extract', 'name': 'a.pdf'},
                      2: {'id': 2, 'state': 'to_extract', 'name': 'b.pdf'}}
        self.rules = {
            7: {'id': 7, 'name': '智能抽取',
                'output_schema_json': {'fields': [{'name': '信用代码'}]},
                'extraction_spec_json': {'spec_version': 3, 'fields': [
                    {'target': '信用代码', 'description': '18 位码'}]}},
            8: {'id': 8, 'name': '另一结果',
                'output_schema_json': {'fields': [{'name': '客户名称'}]},
                'extraction_spec_json': {'spec_version': 3, 'fields': [
                    {'target': '客户名称'}]}},
        }
        self.results = {}
        self.next_ids = {7: 31, 8: 32}
        self.states = []
        self.finished = []
        self.record_counts = {}

    def get_file(self, doc_id):
        return self.files.get(doc_id)

    def get_rule(self, rule_id):
        return self.rules.get(rule_id)

    def list_extract_results(self, doc_id, rule_id=None):
        return [r for r in self.results.values()
                if r['doc_id'] == doc_id
                and (rule_id is None or r['rule_id'] == rule_id)]

    def get_extract_result(self, result_id):
        return self.results.get(result_id)

    def ensure_extract_result(self, doc_id, rule_id, snapshot, status='running'):
        result_id = self.next_ids[rule_id]
        self.results[result_id] = {
            'id': result_id, 'doc_id': doc_id, 'rule_id': rule_id,
            'rule_snapshot_json': copy.deepcopy(snapshot), 'status': status,
            'record_count': 0,
        }
        return result_id

    def finish_extract_result(self, result_id, status='ready', error=None):
        self.finished.append((result_id, status, error))
        self.results[result_id]['status'] = status
        if status == 'ready':
            count = self.record_counts.get(result_id, 0)
            self.results[result_id]['record_count'] = count

    def set_state(self, doc_id, state, error=None):
        self.states.append((doc_id, state, error))
        self.files[doc_id]['state'] = state


class _ContentDB:
    def __init__(self, catalog):
        self.records = {}
        self.saved = []
        self.catalog = catalog

    def gate_counts(self, result_id):
        return {'records_n': len(self.records.get(result_id, []))}

    def save_records(self, result_id, records):
        self.saved.append((result_id, copy.deepcopy(records)))
        self.records[result_id] = copy.deepcopy(records)
        self.catalog.record_counts[result_id] = len(records)
        return len(records)

    def get_records(self, result_id):
        records = self.records.get(result_id, [])
        return {'doc_id': 1, 'extract_result_id': result_id,
                'records': copy.deepcopy(records),
                'files': [{'records': copy.deepcopy(records)}]}


class _Content:
    def get_extract(self, doc_id):
        return {'pages': [{'index': 1, 'space': 'source',
                           'texts': [{'text': '代码 91310115MA1K3PQ45X',
                                      'box': [[1, 1], [50, 1], [50, 9], [1, 9]]}],
                           'tables': []}],
                'stitched_tables': []}


class _Smart:
    def __init__(self):
        self.calls = []

    def build_smart(self, doc, tpl):
        self.calls.append((doc, copy.deepcopy(tpl)))
        target = tpl['extraction_spec_json']['fields'][0]['target']
        value = '91310115MA1K3PQ45X' if target == '信用代码' else '客户甲'
        return [{'index': 0, 'values': {target: value},
                 'original': {target: value},
                 'lineage': {target: []},
                 'review': {'state': 'pending', 'at': None}}]


class ServiceSmartDispatchTest(unittest.TestCase):
    def setUp(self):
        self.catalog = _Catalog()
        self.content_db = _ContentDB(self.catalog)
        self.smart = _Smart()
        self.mods = {'store.catalog': self.catalog,
                     'store.content_db': self.content_db,
                     'store.content': _Content(),
                     'collect': collect, 'store.errors': errors,
                     'smart_extract': self.smart}
        self.load = patch.object(service, '_load', side_effect=lambda n: self.mods[n])
        self.load.start()
        self.addCleanup(self.load.stop)
        self.state = patch.dict(service.STATE, {'running': False})
        self.state.start()
        self.addCleanup(self.state.stop)

    def test_v3_uses_smart_extract_and_saves_to_result(self):
        result = service.run_extract(1, rule_id=7)
        self.assertEqual(len(self.smart.calls), 1)
        expected = [{'index': 0,
                     'values': {'信用代码': '91310115MA1K3PQ45X'},
                     'original': {'信用代码': '91310115MA1K3PQ45X'},
                     'lineage': {'信用代码': []},
                     'review': {'state': 'pending', 'at': None}}]
        self.assertEqual([(31, expected)], self.content_db.saved)
        self.assertEqual({'ok': True, 'doc_id': 1, 'rule_id': 7,
                          'extract_result_id': 31, 'records_n': 1}, result)
        self.assertEqual((1, 'to_review', None), self.catalog.states[-1])

    def test_rerun_uses_result_snapshot_after_rule_changes(self):
        service.run_extract(1, rule_id=7)
        self.catalog.rules[7]['extraction_spec_json']['fields'] = [
            {'target': '已变更字段'}]
        with patch.object(service, 'resolve_rule',
                          wraps=service.resolve_rule) as resolve:
            result = service.run_extract(1, force=True, extract_result_id=31)
        resolve.assert_not_called()
        self.assertEqual(31, result['extract_result_id'])
        self.assertEqual('信用代码', self.smart.calls[-1][1][
            'extraction_spec_json']['fields'][0]['target'])
        self.assertEqual(self.catalog.results[31]['rule_snapshot_json'],
                         service._rule_snapshot(self.smart.calls[-1][1]))

    def test_force_rerun_one_result_does_not_touch_other_result(self):
        service.run_extract(1, rule_id=7)
        service.run_extract(1, rule_id=8)
        other = copy.deepcopy(self.content_db.records[32])
        service.run_extract(1, force=True, extract_result_id=31)
        self.assertEqual(other, self.content_db.records[32])
        self.assertEqual([31, 32, 31],
                         [result_id for result_id, _ in self.content_db.saved])
        self.assertEqual(2, len(self.catalog.results))

    def test_existing_result_requires_force(self):
        service.run_extract(1, rule_id=7)
        with self.assertRaises(errors.Conflict):
            service.run_extract(1, rule_id=7)
        self.assertEqual(1, len(self.content_db.saved))

    def test_result_id_cannot_cross_document_or_rule(self):
        service.run_extract(1, rule_id=7)
        cases = [(2, {'extract_result_id': 31}, errors.NotFound),
                 (1, {'rule_id': 8, 'extract_result_id': 31}, errors.BadRequest)]
        for doc_id, kwargs, expected in cases:
            with self.subTest(doc_id=doc_id, kwargs=kwargs):
                with self.assertRaises(expected):
                    service.run_extract(doc_id, **kwargs)
        self.assertEqual(1, len(self.content_db.saved))

    def test_failed_rerun_preserves_previous_records(self):
        service.run_extract(1, rule_id=7)
        before = copy.deepcopy(self.content_db.records[31])
        self.smart.build_smart = Mock(side_effect=RuntimeError('抽取失败'))
        with self.assertRaises(RuntimeError):
            service.run_extract(1, force=True, extract_result_id=31)
        self.assertEqual(before, self.content_db.records[31])
        self.assertEqual((31, 'failed', '抽取失败'), self.catalog.finished[-1])

    def test_content_module_only_owns_parse_artifact_boundary(self):
        self.assertTrue(callable(content.get_extract))
        self.assertTrue(callable(content.save_extract))
        self.assertFalse(hasattr(content, 'get_records'))
        self.assertFalse(hasattr(content, 'save_records'))


if __name__ == '__main__':
    unittest.main()
