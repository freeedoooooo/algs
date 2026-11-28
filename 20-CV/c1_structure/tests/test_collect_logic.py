"""C2 单测：取值/变换算子、锚点传播、kv 三方向与双锚点。

运行：
    D:/miniforge3/envs/paddle/python.exe -m unittest discover -s c1_structure/tests -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect
from c1_structure.collect_logic import OPS, apply_pipeline, build_logic


def _table_doc():
    def cells(row_idx):
        return [[1, 10 + row_idx * 20, 60, 25 + row_idx * 20],
                [70, 10 + row_idx * 20, 180, 25 + row_idx * 20]]
    return {
        'pages': [{'index': 1, 'space': 'source', 'plain_text': '第一页',
                   'blocks': [{'role': 'title', 'bbox': [0, 0, 200, 30],
                               'text': '对账单'}],
                   'tables': [{
                       'headers': ['名称', '金额：元'],
                       'rows': [['甲', '1,234.50'], ['乙', '20.00']],
                       'cells': [['名称', '金额：元'],
                                 cells(0), cells(1)],
                       'coord': {'space': 'source'},
                   }]}],
        'stitched_tables': [],
    }


def _ctx(doc=None, page=None, table=None, row=None, row_index=0,
         tables_by_ref=None):
    doc = doc or {'pages': []}
    page = page or (doc.get('pages') or [{}])[0]
    return {'doc': doc, 'page': page, 'page_index': page.get('index'),
            'table': table, 'table_scope': 'page', 'table_index': 0,
            'page_default': page.get('index'), 'row': row or [],
            'row_index': row_index, 'tables_by_ref': tables_by_ref or {},
            'values': {}}


def _texts_doc(lines):
    """lines: [(text, [x0,y0,x1,y1]), ...] → 一页 texts（四点 polygon）。"""
    items = []
    for text, b in lines:
        items.append({'text': text, 'score': 1.0,
                      'box': [[b[0], b[1]], [b[2], b[1]],
                              [b[2], b[3]], [b[0], b[3]]]})
    return {'pages': [{'index': 1, 'space': 'source', 'texts': items}],
            'stitched_tables': []}


class CollectLogicTest(unittest.TestCase):

    def test_cell_chain_and_envelope(self):
        """表格路径：cell → regex → number，锚点保留原文，信封键不变。"""
        doc = _table_doc()
        spec = {'spec_version': 2, 'fields': [
            {'target': '项目名称',
             'pipeline': [{'op': 'cell', 'column': {'name': '名称'}}]},
            {'target': '金额',
             'pipeline': [{'op': 'cell',
                           'column': {'header_contains': '金额'}},
                          {'op': 'regex', 'pattern': r'[\d,]+\.\d+'},
                          {'op': 'number', 'strip': ','}]},
        ]}
        records = collect.build(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 2)
        r = records[0]
        self.assertEqual(set(r), {'index', 'values', 'original',
                                  'lineage', 'review'})
        self.assertEqual(r['values'], {'项目名称': '甲', '金额': 1234.5})
        self.assertEqual(r['original'], {'项目名称': '甲',
                                         '金额': '1,234.50'})
        anchor = r['lineage']['金额'][0]
        self.assertEqual(anchor['raw_text'], '1,234.50')
        self.assertEqual(anchor['cell_bbox'], [70, 10, 180, 25])
        self.assertEqual(anchor['page'], 1)
        self.assertEqual(anchor['table_scope'], 'page')
        self.assertEqual(r['review'], {'state': 'pending', 'at': None})

    def test_cell_source_ref(self):
        """source ref 按 tables 选择器解析，row 可用固定下标。"""
        doc = _table_doc()
        doc['pages'][0]['tables'].append({
            'headers': ['合计金额'], 'rows': [['999']],
            'cells': [['合计金额'], [[1, 40, 80, 55]]],
            'coord': {'space': 'source'}})
        spec = {'spec_version': 2,
                'tables': [{'ref': 'sum', 'header_contains': '合计'}],
                'fields': [{'target': '合计', 'pipeline': [
                    {'op': 'cell', 'source': 'sum',
                     'column': {'index': 0}, 'row': 0}]}]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertTrue(records)
        self.assertEqual(records[0]['values'], {'合计': '999'})

    def test_block_and_page_text(self):
        doc = _table_doc()
        ctx = _ctx(doc)
        value, anchors, meta = apply_pipeline(
            [{'op': 'block', 'role': 'title'}], ctx)
        self.assertEqual(value, '对账单')
        self.assertEqual(anchors[0]['cell_bbox'], [0, 0, 200, 30])
        value, anchors, _ = apply_pipeline([{'op': 'page_text'}], ctx)
        self.assertEqual(value, '第一页')
        self.assertIsNone(anchors[0]['cell_bbox'])

    def test_kv_inline(self):
        """同一行“标签：值”，双锚点共 bbox 但 raw_text 不同。"""
        doc = _texts_doc([
            ('统一社会信用代码：91310115MA1K3PQ45X', [10, 10, 400, 30])])
        ctx = _ctx(doc)
        value, anchors, _ = apply_pipeline([{
            'op': 'kv', 'source': 'texts',
            'label': {'text': '统一社会信用代码', 'match': 'contains'},
            'value': {'direction': 'inline', 'regex': '[0-9A-Z]{18}'},
        }], ctx)
        self.assertEqual(value, '91310115MA1K3PQ45X')
        self.assertEqual(len(anchors), 2)
        self.assertEqual(anchors[0]['raw_text'], '91310115MA1K3PQ45X')
        self.assertEqual(anchors[1]['raw_text'],
                         '统一社会信用代码：91310115MA1K3PQ45X')
        self.assertEqual(anchors[0]['cell_bbox'], [10, 10, 400, 30])

    def test_kv_right_and_below(self):
        doc = _texts_doc([
            ('统一社会信用代码', [100, 100, 200, 120]),
            ('91310115MA1K3PQ45X', [220, 100, 400, 120]),
            ('法定代表人', [100, 200, 200, 220]),
            ('张三', [100, 240, 160, 260]),
        ])
        ctx = _ctx(doc)
        value, anchors, _ = apply_pipeline([{
            'op': 'kv', 'label': {'text': '统一社会信用代码'},
            'value': {'direction': 'right', 'max_gap': 50,
                      'regex': '[0-9A-Z]{18}'},
        }], ctx)
        self.assertEqual(value, '91310115MA1K3PQ45X')
        self.assertEqual([a['raw_text'] for a in anchors],
                         ['91310115MA1K3PQ45X', '统一社会信用代码'])

        value, anchors, _ = apply_pipeline([{
            'op': 'kv', 'label': {'text': '法定代表人'},
            'value': {'direction': 'below', 'max_gap': 50},
        }], ctx)
        self.assertEqual(value, '张三')
        self.assertEqual([a['raw_text'] for a in anchors],
                         ['张三', '法定代表人'])

    def test_kv_regex_guard(self):
        """regex 不匹配时宁可漏抽：空值 + 只留标签锚点。"""
        doc = _texts_doc([
            ('统一社会信用代码', [100, 100, 200, 120]),
            ('某公司地址', [220, 100, 400, 120]),
        ])
        value, anchors, meta = apply_pipeline([{
            'op': 'kv', 'label': {'text': '统一社会信用代码'},
            'value': {'direction': 'right', 'regex': '[0-9A-Z]{18}'},
        }], _ctx(doc))
        self.assertEqual(value, '')
        self.assertEqual(len(anchors), 1)
        self.assertIn('kv_value_not_found', meta['issues'])

    def test_transform_ops(self):
        self.assertEqual(OPS['trim']({}, {}, '  x  ', [])[0], 'x')
        self.assertEqual(OPS['cut']({}, {'begin': 1, 'end': 3},
                                    'abcdef', [])[0], 'bc')
        self.assertEqual(OPS['replace']({}, {'pattern': r'\s+', 'repl': ''},
                                        'a b c', [])[0], 'abc')
        self.assertEqual(OPS['number']({}, {'strip': ','},
                                       '1,200', [])[0], 1200)
        self.assertEqual(OPS['date']({}, {'format': '%Y/%m/%d'},
                                     '2026/11/24', [])[0], '2026-11-24')

    def test_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            apply_pipeline([{'op': 'not_exist'}], {})


class RegionSelectionTest(unittest.TestCase):
    def _table_doc(self):
        def table(name, y):
            return {'headers': ['表名', '金额'],
                    'rows': [[name, '10']],
                    'cells': [['表名', '金额'],
                              [[100, y, 300, y + 50], [400, y, 600, y + 50]]],
                    'coord': {'space': 'source'}}
        return {'pages': [{'index': 1, 'size': [1000, 1000],
                           'rectified_size': [1000, 2000], 'space': 'source',
                           'blocks': [
                               {'role': 'title', 'bbox': [100, 50, 500, 90],
                                'text': '汇总'},
                               {'role': 'text', 'bbox': [100, 600, 700, 650],
                                'text': '明细'}],
                           'texts': [],
                           'tables': [table('汇总表', 100),
                                      table('明细表', 600)]}],
                'stitched_tables': []}

    def test_table_region_restricts_records(self):
        doc = self._table_doc()
        spec = {'spec_version': 2,
                'tables': [{'ref': 'main', 'restrict': True,
                            'region': {'page': 1, 'rect': [0, 0.5, 1, 1]}}],
                'fields': [{'target': '金额', 'pipeline': [
                    {'op': 'cell', 'column': {'name': '金额'}}]}]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['values']['金额'], '10')
        self.assertEqual(records[0]['lineage']['金额'][0]['cell_bbox'],
                         [400, 600, 600, 650])

    def test_region_only_table_selector_resolves_source(self):
        from c1_structure.collect_logic.engine import _tables_by_ref
        doc = self._table_doc()
        doc['pages'][0]['tables'][1]['rows'][0][1] = '20'
        spec = {'spec_version': 2,
                'tables': [{'ref': 'main',
                            'region': {'page': 1, 'rect': [0, 0.5, 1, 1]}}],
                'fields': [{'target': '金额', 'pipeline': [
                    {'op': 'cell', 'source': 'main',
                     'column': {'name': '金额'}}]}]}
        picked = _tables_by_ref(doc, spec)['main']
        self.assertEqual(len(picked), 1)
        self.assertEqual(picked[0][0]['rows'][0][1], '20')

    def test_rectified_table_region_uses_rectified_size(self):
        doc = self._table_doc()
        doc['pages'][0]['tables'][1]['coord']['space'] = 'rectified'
        doc['pages'][0]['tables'][1]['cells'][1] = [
            [100, 1000, 300, 1050], [400, 1000, 600, 1050]]
        spec = {'spec_version': 2,
                'tables': [{'ref': 'main', 'restrict': True,
                            'region': {'page': 1, 'rect': [0, 0.45, 1, 0.55]}}],
                'fields': [{'target': '金额', 'pipeline': [
                    {'op': 'cell', 'column': {'name': '金额'}}]}]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['lineage']['金额'][0]['space'], 'rectified')

    def test_block_region(self):
        doc = self._table_doc()
        value, anchors, meta = apply_pipeline([{
            'op': 'block', 'contains': '明细',
            'region': {'page': 1, 'rect': [0, 0.5, 1, 1]}}], _ctx(doc))
        self.assertEqual(value, '明细')
        self.assertFalse(meta.get('issues'))
        self.assertEqual(anchors[0]['cell_bbox'], [100, 600, 700, 650])

    def test_kv_region_excludes_outside_decoy(self):
        doc = _texts_doc([
            ('账号', [100, 100, 200, 120]), ('错误值', [220, 100, 400, 120]),
            ('账号', [550, 100, 650, 120]), ('正确值', [700, 100, 900, 120])])
        doc['pages'][0]['size'] = [1000, 1000]
        value, anchors, meta = apply_pipeline([{
            'op': 'kv', 'label': {'text': '账号'},
            'region': {'page': 1, 'rect': [0.5, 0, 1, 0.2]},
            'value': {'direction': 'right'}}], _ctx(doc))
        self.assertEqual(value, '正确值')
        self.assertEqual([a['raw_text'] for a in anchors], ['正确值', '账号'])
        self.assertFalse(meta.get('issues'))

    def test_region_text_reading_order_and_anchors(self):
        doc = _texts_doc([
            ('末尾', [100, 600, 300, 630]),
            ('区域外', [100, 100, 300, 130]),
            ('开头', [100, 500, 300, 530])])
        doc['pages'][0]['size'] = [1000, 1000]
        value, anchors, _meta = apply_pipeline([{
            'op': 'region_text', 'sep': '|',
            'region': {'page': 1, 'rect': [0, 0.4, 1, 0.7]}}], _ctx(doc))
        self.assertEqual(value, '开头|末尾')
        self.assertEqual([a['raw_text'] for a in anchors], ['开头', '末尾'])

    def test_stitched_table_region(self):
        doc = {'pages': [{'index': 1, 'size': [1000, 1000], 'space': 'source',
                          'texts': [], 'blocks': [], 'tables': []},
                         {'index': 2, 'size': [1000, 1000], 'space': 'source',
                          'texts': [], 'blocks': [], 'tables': []}],
               'stitched_tables': [{
                   'headers': ['金额'], 'rows': [['10']],
                   'cells': [['金额'],
                             [{'page': 2, 'bbox': [400, 600, 600, 650]}]],
                   'coord': {'space': 'source'},
                   'parts': [{'page': 2, 'tbl': 0}]}]}
        spec = {'spec_version': 2,
                'tables': [{'ref': 'main', 'restrict': True,
                            'region': {'page': 2, 'rect': [0, 0.5, 1, 1]}}],
                'fields': [{'target': '金额', 'pipeline': [
                    {'op': 'cell', 'column': {'name': '金额'}}]}]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['lineage']['金额'][0]['page'], 2)

    def test_region_text_one_per_page_stays_on_current_page(self):
        doc = {'pages': [
            {'index': 1, 'size': [1000, 1000], 'space': 'source',
             'texts': [{'text': '第一页',
                        'box': [[100, 100], [300, 100], [300, 130], [100, 130]]}]},
            {'index': 2, 'size': [1000, 1000], 'space': 'source',
             'texts': [{'text': '第二页',
                        'box': [[100, 100], [300, 100], [300, 130], [100, 130]]}]}],
            'stitched_tables': []}
        spec = {'spec_version': 2, 'records': {'strategy': 'one_per_page'},
                'fields': [{'target': '内容', 'pipeline': [
                    {'op': 'region_text', 'region': {'rect': [0, 0, 0.5, 0.2]}}]}]}
        records = build_logic(doc, {'extraction_spec_json': spec})
        self.assertEqual([r['values']['内容'] for r in records],
                         ['第一页', '第二页'])

    def test_invalid_region_rejected(self):
        from c1_structure.agent import validate
        spec = {'spec_version': 2, 'fields': [{'target': '金额', 'pipeline': [
            {'op': 'region_text', 'region': {'rect': [0, 0, 2, 1]}}]}]}
        self.assertTrue(any('region.rect' in x
                            for x in validate.validate_spec(spec)))


if __name__ == '__main__':
    unittest.main()
