"""库内零规则时：未指定规则走内存默认透传，不写库；显式指定仍报错。"""
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


class _EmptyCatalog:
    def get_rule_version(self, version_id=None):
        return None


class TestDefaultRuleNoDb(unittest.TestCase):
    def test_fallback_passthrough(self):
        with patch.object(service, '_load', return_value=_EmptyCatalog()):
            tpl = service.resolve_rule()
        self.assertEqual(tpl['name'], '原始透传')
        self.assertIsNone(tpl['version_id'])
        self.assertEqual(tpl['mapping_json'], {})

    def test_default_ignores_db_rules(self):
        def boom(*a, **k):
            raise AssertionError('默认规则不应查库')
        with patch.object(service, '_load', side_effect=boom):
            tpl = service.resolve_rule()
        self.assertEqual(tpl['name'], '原始透传')

    def test_explicit_missing_still_errors(self):
        with patch.object(service, '_load', return_value=_EmptyCatalog()):
            with self.assertRaises(RuntimeError):
                service.resolve_rule(999)

    def test_fallback_mapping_passes_through(self):
        with patch.object(service, '_load', return_value=_EmptyCatalog()):
            tpl = service.resolve_rule()
        box = lambda x: [x, 0, x + 20, 20]
        doc = {'pages': [{'index': 1, 'tables': [
            {'headers': ['名称'], 'rows': [['甲'], ['乙']],
             'cells': [[box(0)], [box(0)]], 'coord': {'space': 'source'}}
        ]}]}
        recs = collect.build(doc, tpl)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]['values']['名称'], '甲')


if __name__ == '__main__':
    unittest.main()
