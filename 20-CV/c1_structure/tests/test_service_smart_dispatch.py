"""S2 单测：service.run_extract 按 spec_version 分流到智能抽取，不写 DB。"""
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect, service
from c1_structure.store import errors


class _Catalog:
    def get_file(self, file_id):
        return {'id': file_id, 'state': 'to_extract',
                'rule_version_id': 1, 'name': 'a.pdf'}

    def get_rule_version(self, version_id=None):
        return {'id': version_id or 1, 'rule_id': 1, 'version': 1,
                'name': '智能抽取', 'schema_json': {},
                'mapping_json': {'spec_version': 3, 'fields': [
                    {'target': '信用代码', 'description': '18 位码'}]},
                'transform_json': {}}

    def set_rule(self, file_id, version_id):
        pass

    def set_state(self, file_id, state, error=None):
        pass


class _Content:
    def __init__(self):
        self.saved = []

    def get_extract(self, task_file_id):
        return {'pages': [{'index': 1, 'space': 'source',
                           'texts': [{'text': '代码 91310115MA1K3PQ45X',
                                      'box': [[1, 1], [50, 1], [50, 9], [1, 9]]}],
                           'tables': []}],
                'stitched_tables': []}

    def save_records(self, doc):
        self.saved.append(doc)


class _Smart:
    def __init__(self):
        self.calls = []

    def build_smart(self, doc, tpl):
        self.calls.append((doc, tpl))
        return [{'index': 0, 'values': {'信用代码': '91310115MA1K3PQ45X'},
                 'original': {'信用代码': '91310115MA1K3PQ45X'},
                 'lineage': {'信用代码': []},
                 'review': {'state': 'pending', 'at': None}}]


class ServiceSmartDispatchTest(unittest.TestCase):

    def test_v3_uses_smart_extract(self):
        catalog, content, smart = _Catalog(), _Content(), _Smart()
        mods = {'store.catalog': catalog, 'store.content': content,
                'collect': collect, 'store.errors': errors,
                'smart_extract': smart}
        with patch.object(service, '_load', side_effect=lambda n: mods[n]):
            result = service.run_extract(1, rule_version_id=99)
        self.assertEqual(len(smart.calls), 1)
        self.assertEqual(len(content.saved), 1)
        self.assertEqual(result['files'][0]['records_n'], 1)
        self.assertEqual(
            content.saved[0]['files'][0]['records'][0]['values']['信用代码'],
            '91310115MA1K3PQ45X')


if __name__ == '__main__':
    unittest.main()
