"""C3 单测：组合/逻辑算子、跨表聚合、join/link 双表锚点合并。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect
from c1_structure.collect_logic import apply_pipeline, build_logic
from c1_structure.collect_logic.engine import _tables_by_ref


def _table(headers, rows, base_y):
    cells = [list(headers)]
    for r, row in enumerate(rows):
        cells.append([[1, base_y + r * 20, 80, base_y + r * 20 + 15],
                      [90, base_y + r * 20, 190, base_y + r * 20 + 15]])
    return {'headers': headers, 'rows': rows, 'cells': cells,
            'coord': {'space': 'source'}}


def _doc():
    detail = _table(['客户ID', '金额'], [['C1', '100'], ['C2', '200']], 10)
    summary = _table(['客户ID', '合计金额'],
                     [['C1', '1,000'], ['C2', '2,000']], 100)
    return {'pages': [{'index': 1, 'space': 'source', 'plain_text': '',
                       'texts': [], 'blocks': [],
                       'tables': [detail, summary]}],
            'stitched_tables': []}


def _ctx(values=None, lineage=None):
    return {'doc': {}, 'table': {}, 'row': [], 'row_index': 0,
            'values': values or {}, 'lineage': lineage or {},
            'tables_by_ref': {}}


class CollectLogicC3Test(unittest.TestCase):

    def test_compose_ops(self):
        anchor = {'page': 1, 'table_index': 0, 'table_scope': 'page',
                  'cell_bbox': [1, 2, 3, 4], 'space': 'source',
                  'raw_text': '张'}
        ctx = _ctx({'姓': '张', '名': '三', '别名': '', '客户ID': 'C1'},
                   {'姓': [anchor], '名': [dict(anchor, raw_text='三')]})
        value, anchors, _ = apply_pipeline(
            [{'op': 'concat', 'fields': ['姓', '名'], 'sep': ''}], ctx)
        self.assertEqual(value, '张三')
        self.assertEqual(len(anchors), 2)

        value, _a, _m = apply_pipeline(
            [{'op': 'template', 'pattern': '{姓}{名}-已核对'}], ctx)
        self.assertEqual(value, '张三-已核对')

        value, anchors, _ = apply_pipeline(
            [{'op': 'coalesce', 'fields': ['别名', '姓']}], ctx)
        self.assertEqual(value, '张')
        self.assertEqual(anchors[0]['raw_text'], '张')

        value, _a, _m = apply_pipeline(
            [{'op': 'lookup', 'field': '客户ID',
              'dict': {'C1': '甲类'}, 'default': '其他'}], ctx)
        self.assertEqual(value, '甲类')

    def test_if_and_switch(self):
        ctx = _ctx({'金额': 150})
        value, _a, _m = apply_pipeline([{
            'op': 'if', 'when': {'field': '金额', 'op': 'gt', 'value': 100},
            'then': [{'op': 'template', 'pattern': '高'}],
            'else': [{'op': 'template', 'pattern': '低'}]}], ctx)
        self.assertEqual(value, '高')

        value, _a, _m = apply_pipeline([{
            'op': 'switch',
            'cases': [{'when': {'field': '金额', 'op': 'lt', 'value': 100},
                       'then': [{'op': 'template', 'pattern': '低'}]}],
            'default': [{'op': 'template', 'pattern': '其他'}]}], ctx)
        self.assertEqual(value, '其他')

    def test_sum_and_count_scope_all(self):
        spec = {'spec_version': 2,
                'tables': [{'ref': 'all', 'scope': 'all'}],
                'fields': [
                    {'target': '总额', 'pipeline': [
                        {'op': 'sum', 'source': 'all',
                         'column': {'header_contains': '金额'},
                         'strip': ','}]},
                    {'target': '行数', 'pipeline': [
                        {'op': 'count', 'source': 'all',
                         'column': {'name': '客户ID'}}]},
                ]}
        records = build_logic(_doc(), {'mapping_json': spec})
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]['values'], {'总额': 3300, '行数': 4})
        self.assertEqual(len(records[0]['lineage']['总额']), 4)

    def test_join_merges_both_sides(self):
        spec = {'spec_version': 2,
                'tables': [{'ref': 'sum', 'index': 1}],
                'fields': [
                    {'target': '客户ID', 'pipeline': [
                        {'op': 'cell', 'column': {'name': '客户ID'}}]},
                    {'target': '合计', 'pipeline': [
                        {'op': 'join', 'source': 'sum',
                         'left': {'field': '客户ID'},
                         'right': {'column': {'name': '客户ID'}},
                         'take': {'name': '合计金额'}}]},
                ]}
        records = build_logic(_doc(), {'mapping_json': spec})
        first = records[0]
        self.assertEqual(first['values']['客户ID'], 'C1')
        self.assertEqual(first['values']['合计'], '1,000')
        raw = [a['raw_text'] for a in first['lineage']['合计']]
        self.assertIn('C1', raw)
        self.assertIn('1,000', raw)
        pages = [a['cell_bbox'][1] for a in first['lineage']['合计']]
        self.assertTrue(any(y < 50 for y in pages))   # 明细表锚点
        self.assertTrue(any(y >= 100 for y in pages))  # 汇总表锚点

    def test_link_expand_into_record(self):
        spec = {'spec_version': 2,
                'tables': [{'ref': 'sum', 'index': 1}],
                'fields': [
                    {'target': '客户ID', 'pipeline': [
                        {'op': 'cell', 'column': {'name': '客户ID'}}]},
                    {'target': 'link', 'expand': True, 'pipeline': [
                        {'op': 'link', 'source': 'sum',
                         'left': {'field': '客户ID'},
                         'right': {'column': {'name': '客户ID'}},
                         'fields': [{'target': '对账合计',
                                     'column': {'name': '合计金额'}}]}]},
                ]}
        records = build_logic(_doc(), {'mapping_json': spec})
        first = records[0]
        self.assertEqual(first['values']['对账合计'], '1,000')
        self.assertNotIn('link', first['values'])
        raw = [a['raw_text'] for a in first['lineage']['对账合计']]
        self.assertIn('C1', raw)
        self.assertIn('1,000', raw)

    def test_scope_all_resolves_to_table_list(self):
        spec = {'tables': [{'ref': 'all', 'scope': 'all'}]}
        by_ref = _tables_by_ref(_doc(), spec)
        self.assertEqual(len(by_ref['all']), 2)
        self.assertEqual(by_ref['all'][0][0]['headers'], ['客户ID', '金额'])


if __name__ == '__main__':
    unittest.main()
