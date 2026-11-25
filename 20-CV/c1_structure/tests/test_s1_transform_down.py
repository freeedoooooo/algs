"""S1 单测：简单规则转换下沉到抽取阶段，且 restrict 只产出所选表记录。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect
from c1_structure.store import loader


def _doc():
    box = lambda x: [x, 0, x + 20, 20]
    return {
        'pages': [{'index': 1, 'space': 'source', 'tables': [
            {'headers': ['名称', '金额'],
             'rows': [['甲', ' 1,234.50 ']],
             'cells': [[box(0), box(70)], [box(0), box(70)]],
             'coord': {'space': 'source'}},
            {'headers': ['备注'],
             'rows': [['X'], ['Y']],
             'cells': [[box(0)], [box(0)], [box(0)]],
             'coord': {'space': 'source'}},
        ]}],
        'stitched_tables': [],
    }


def _spec(restrict=True):
    table = {'ref': 'main', 'index': 0}
    if restrict:
        table['restrict'] = True
    return {
        'spec_version': 2,
        'tables': [table],
        'records': {'strategy': 'row'},
        'fields': [
            {'target': '名称',
             'pipeline': [{'op': 'cell', 'source': 'main',
                           'column': {'name': '名称'}}]},
            {'target': '金额',
             'pipeline': [{'op': 'cell', 'source': 'main',
                           'column': {'name': '金额'}},
                          {'op': 'trim'},
                          {'op': 'replace', 'pattern': r'\s+', 'repl': ''},
                          {'op': 'number', 'strip': ','}]},
        ],
    }


class TransformDownTest(unittest.TestCase):

    def test_extract_values_match_old_load_transform(self):
        doc = _doc()
        records = collect.build(doc, {'mapping_json': _spec()})
        self.assertEqual(len(records), 1)
        rec = records[0]
        old, errs = loader.apply_transform(
            {'名称': '甲', '金额': ' 1,234.50 '},
            {'fields': [{'target': '金额', 'apply': ['trim', 'number']}]})
        self.assertEqual(errs, [])
        self.assertEqual(rec['values'], old)
        self.assertEqual(rec['original'],
                         {'名称': '甲', '金额': ' 1,234.50 '})
        self.assertEqual(rec['lineage']['金额'][0]['raw_text'], ' 1,234.50 ')

    def test_restrict_limits_records_to_selected_table(self):
        doc = _doc()
        self.assertEqual(len(collect.build(doc, {'mapping_json': _spec(True)})), 1)
        self.assertEqual(len(collect.build(doc, {'mapping_json': _spec(False)})), 3)

    def test_header_contains_selector_also_restricts(self):
        doc = _doc()
        spec = _spec(True)
        spec['tables'] = [{'ref': 'main', 'header_contains': '金额',
                           'restrict': True}]
        records = collect.build(doc, {'mapping_json': spec})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['values']['名称'], '甲')


if __name__ == '__main__':
    unittest.main()
