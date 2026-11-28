"""C4 单测：四种记录切分策略与 records 信封一致性。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect
from c1_structure.collect_logic import build_logic


def _table_doc(headers, rows, base_y=10):
    cells = [list(headers)]
    for r, _row in enumerate(rows):
        cells.append([[1, base_y + r * 20, 80, base_y + r * 20 + 15],
                      [90, base_y + r * 20, 190, base_y + r * 20 + 15]])
    return {'pages': [{'index': 1, 'space': 'source', 'plain_text': '第一页',
                       'tables': [{'headers': headers, 'rows': rows,
                                   'cells': cells,
                                   'coord': {'space': 'source'}}]}],
            'stitched_tables': []}


def _pages_doc(lines_per_page):
    pages = []
    for i, lines in enumerate(lines_per_page, 1):
        texts = [{'text': text, 'score': 1.0,
                  'box': [[10, 10 + j * 30, 400, 30 + j * 30],
                          [400, 10 + j * 30, 400, 30 + j * 30],
                          [400, 30 + j * 30, 10, 30 + j * 30],
                          [10, 30 + j * 30, 10, 10 + j * 30]]}
                 for j, text in enumerate(lines)]
        pages.append({'index': i, 'space': 'source',
                      'plain_text': '第{}页正文'.format(i),
                      'texts': texts, 'tables': []})
    return {'pages': pages, 'stitched_tables': []}


class CollectLogicC4Test(unittest.TestCase):

    def test_row_default_equals_passthrough(self):
        doc = _table_doc(['名称', '金额'], [['甲', '10'], ['乙', '20']])
        expected = collect.passthrough(doc)
        for records_cfg in (None, {'strategy': 'row'}):
            spec = {'spec_version': 2}
            if records_cfg:
                spec['records'] = records_cfg
            got = collect.build(doc, {'extraction_spec_json': spec})
            self.assertEqual(got, expected)

    def test_key_value(self):
        doc = _table_doc(['字段', '值'], [['名称', '甲'], ['金额', '100']])
        spec = {'spec_version': 2,
                'records': {'strategy': 'key_value'},
                'fields': []}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec['values'], {'名称': '甲', '金额': '100'})
        self.assertEqual([a['raw_text'] for a in rec['lineage']['金额']],
                         ['100'])
        self.assertEqual(set(rec), {'index', 'values', 'original',
                                    'lineage', 'review'})

    def test_group_by(self):
        doc = _table_doc(['客户ID', '金额'],
                         [['C1', '100'], ['C1', '300'], ['C2', '200']])
        spec = {'spec_version': 2,
                'records': {'strategy': 'group_by', 'group_by': ['客户ID']},
                'fields': [
                    {'target': '客户ID', 'pipeline': [
                        {'op': 'cell', 'column': {'name': '客户ID'}}]},
                    {'target': '金额', 'pipeline': [
                        {'op': 'cell', 'column': {'name': '金额'}}]},
                ]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['values'],
                         {'客户ID': 'C1', '金额': ['100', '300']})
        self.assertEqual(records[1]['values'],
                         {'客户ID': 'C2', '金额': ['200']})
        self.assertEqual([a['raw_text'] for a in
                          records[0]['lineage']['金额']], ['100', '300'])
        self.assertEqual([r['index'] for r in records], [0, 1])

    def test_one_per_page_with_kv(self):
        doc = _pages_doc([
            ['统一社会信用代码：91310115MA1K3PQ45X'],
            ['统一社会信用代码：91310115MA1K3PQ46Y'],
        ])
        spec = {'spec_version': 2,
                'records': {'strategy': 'one_per_page'},
                'fields': [{'target': '信用代码', 'pipeline': [
                    {'op': 'kv', 'source': 'texts',
                     'label': {'text': '统一社会信用代码'},
                     'value': {'direction': 'inline',
                               'regex': '[0-9A-Z]{18}'}}]}]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['values']['信用代码'],
                         '91310115MA1K3PQ45X')
        self.assertEqual(records[1]['values']['信用代码'],
                         '91310115MA1K3PQ46Y')
        self.assertEqual(len(records[0]['lineage']['信用代码']), 2)

    def test_one_per_page_without_fields(self):
        doc = _pages_doc([['无关文本'], ['无关文本']])
        spec = {'spec_version': 2,
                'records': {'strategy': 'one_per_page'}}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual([r['values']['text'] for r in records],
                         ['第1页正文', '第2页正文'])

    def test_unknown_strategy_raises(self):
        with self.assertRaises(ValueError):
            build_logic(_table_doc(['A'], [['1']]),
                        {'extraction_spec_json': {'spec_version': 2,
                                          'records': {'strategy': 'nope'}}})
    def test_two_tables_use_explicit_record_source(self):
        def table(headers, rows, base_y):
            cells = [list(headers)]
            for r, row in enumerate(rows):
                cells.append([[10 + c * 100, base_y + r * 20,
                               90 + c * 100, base_y + r * 20 + 15]
                              for c in range(len(headers))])
            return {'headers': headers, 'rows': rows, 'cells': cells,
                    'coord': {'space': 'source'}}

        detail_rows = [['D{}'.format(i), str(i * 10)] for i in range(1, 7)]
        detail = table(['订单编号', '收入'], detail_rows, 10)
        summary = table(['项目', '笔数', '金额', '状态'], [
            ['收入合计', '6', '210', '正常'],
            ['支出合计', '2', '30', '正常'],
            ['净额', '4', '180', '正常'],
        ], 200)
        doc = {'pages': [{'index': 1, 'space': 'source', 'plain_text': '',
                          'tables': [detail, summary]}],
               'stitched_tables': []}

        def spec(ref, index, targets):
            return {'spec_version': 2,
                    'tables': [{'ref': ref, 'index': index,
                                'role': 'record_source'}],
                    'records': {'strategy': 'row', 'source_ref': ref},
                    'fields': [{'target': target, 'pipeline': [
                        {'op': 'cell', 'source': ref,
                         'column': {'name': target}}]} for target in targets]}

        detail_records = build_logic(doc, {'extraction_spec_json': spec(
            'detail', 0, ['订单编号', '收入'])})
        summary_records = build_logic(doc, {'extraction_spec_json': spec(
            'summary', 1, ['项目', '笔数', '金额', '状态'])})
        self.assertEqual(len(detail_records), 6)
        self.assertEqual(len(summary_records), 3)
        self.assertEqual(summary_records[0]['values'], {
            '项目': '收入合计', '笔数': '6', '金额': '210', '状态': '正常'})
        self.assertEqual(summary_records[-1]['values']['项目'], '净额')

    def test_unknown_record_source_raises(self):
        spec = {'spec_version': 2,
                'tables': [{'ref': 'main', 'index': 0,
                            'role': 'record_source'}],
                'records': {'strategy': 'row', 'source_ref': 'missing'},
                'fields': [{'target': '名称', 'pipeline': [
                    {'op': 'cell', 'source': 'main',
                     'column': {'name': '名称'}}]}]}
        with self.assertRaisesRegex(ValueError, 'source_ref'):
            build_logic(_table_doc(['名称'], [['甲']]),
                        {'extraction_spec_json': spec})

    def test_key_value_uses_record_source(self):
        doc = {'pages': [{'index': 1, 'space': 'source', 'plain_text': '',
                          'tables': [
                              {'headers': ['字段', '值'],
                               'rows': [['名称', '甲']], 'cells': []},
                              {'headers': ['字段', '值'],
                               'rows': [['金额', '100']], 'cells': []}]}],
               'stitched_tables': []}
        spec = {'spec_version': 2,
                'tables': [{'ref': 'kv', 'index': 1,
                            'role': 'record_source'}],
                'records': {'strategy': 'key_value', 'source_ref': 'kv'},
                'fields': []}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['values'], {'金额': '100'})

    def test_group_by_uses_record_source(self):
        doc = {'pages': [{'index': 1, 'space': 'source', 'plain_text': '',
                          'tables': [
                              {'headers': ['客户', '金额'],
                               'rows': [['甲', '10']], 'cells': []},
                              {'headers': ['客户', '金额'],
                               'rows': [['乙', '20'], ['乙', '30']],
                               'cells': []}]}], 'stitched_tables': []}
        spec = {'spec_version': 2,
                'tables': [{'ref': 'detail', 'index': 1,
                            'role': 'record_source'}],
                'records': {'strategy': 'group_by', 'source_ref': 'detail',
                            'group_by': ['客户']},
                'fields': [
                    {'target': '客户', 'pipeline': [
                        {'op': 'cell', 'source': 'detail',
                         'column': {'name': '客户'}}]},
                    {'target': '金额', 'pipeline': [
                        {'op': 'cell', 'source': 'detail',
                         'column': {'name': '金额'}}]},
                ]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['values'],
                         {'客户': '乙', '金额': ['20', '30']})


if __name__ == '__main__':
    unittest.main()
