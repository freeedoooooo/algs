"""test_collect_selectors.py — P1b collect 选择器单测骨架（C 项，无 DB 纯函数）。

跑法（从 20-CV）：
  D:/miniforge3/envs/paddle/python.exe -m unittest c1_structure.test_collect_selectors -v
或直跑：D:/miniforge3/envs/paddle/python.exe c1_structure/test_collect_selectors.py
合成 doc 直造，不碰真实库/服务。覆盖：空映射＝passthrough、index/header_contains
选表、name/index 选列、缺列/缺表、重命名键序、lineage page/scope、重名表头键。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from c1_structure import collect


def tbl(headers, rows, cells=None, **kw):
    t = {'headers': headers, 'rows': rows, 'cells': cells or []}
    t.update(kw)
    return t


def page_doc(tables, index=1):
    return {'pages': [{'index': index, 'tables': tables}], 'stitched_tables': []}


def bbox_cells(rows):
    """page scope：cells[r+1][c] = bbox list。"""
    return [[None] * 8] + [[[c, r, c + 1, r + 1] for c in range(8)]
                           for r in range(rows)]


class Selectors(unittest.TestCase):
    def setUp(self):
        self.t = tbl(['账号', '金额', '备注'],
                     [['6227', '100', 'a'], ['6228', '200', 'b']],
                     bbox_cells(2))
        self.doc = page_doc([self.t])

    def test_empty_mapping_is_passthrough(self):
        for tpl in (None, {}, {'mapping_json': None}, {'mapping_json': {}},
                    {'mapping_json': {'fields': []}}):
            self.assertEqual(collect.build(self.doc, tpl),
                             collect.passthrough(self.doc))

    def test_index_table_name_column_rename(self):
        m = {'table': {'index': 0}, 'fields': [
            {'target': '卡号', 'column': {'name': '账号'}},
            {'target': '交易额', 'column': {'name': '金额'}}]}
        recs = collect.build(self.doc, {'mapping_json': m})
        self.assertEqual(len(recs), 2)
        self.assertEqual(list(recs[0]['values']), ['卡号', '交易额'])
        self.assertEqual(recs[0]['values'], {'卡号': '6227', '交易额': '100'})
        self.assertEqual(recs[1]['values']['卡号'], '6228')
        self.assertEqual(recs[0]['original'], recs[0]['values'])
        self.assertEqual(recs[0]['review']['state'], 'pending')

    def test_lineage_page_scope_anchor(self):
        m = {'table': {'index': 0}, 'fields': [
            {'target': '卡号', 'column': {'name': '账号'}}]}
        recs = collect.build(self.doc, {'mapping_json': m})
        lin = recs[1]['lineage']['卡号'][0]
        self.assertEqual(lin['page'], 1)
        self.assertEqual(lin['table_scope'], 'page')
        self.assertEqual(lin['table_index'], 0)
        self.assertEqual(lin['raw_text'], '6228')
        self.assertEqual(lin['cell_bbox'], [0, 1, 1, 2])

    def test_header_contains_picks_first_match(self):
        t2 = tbl(['交易明细', '日期'], [['x', '2022']], bbox_cells(1))
        doc = page_doc([self.t, t2])
        m = {'table': {'header_contains': '交易明细'}, 'fields': [
            {'target': '摘要', 'column': {'name': '交易明细'}}]}
        recs = collect.build(doc, {'mapping_json': m})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['values']['摘要'], 'x')
        self.assertEqual(recs[0]['lineage']['摘要'][0]['table_index'], 1)

    def test_column_index(self):
        m = {'table': {'index': 0}, 'fields': [
            {'target': '第三列', 'column': {'index': 2}}]}
        recs = collect.build(self.doc, {'mapping_json': m})
        self.assertEqual(recs[0]['values']['第三列'], 'a')

    def test_missing_column_empty_and_no_lineage(self):
        m = {'table': {'index': 0}, 'fields': [
            {'target': '不存在', 'column': {'name': 'nope'}},
            {'target': '越界', 'column': {'index': 9}}]}
        recs = collect.build(self.doc, {'mapping_json': m})
        self.assertEqual(recs[0]['values'], {'不存在': '', '越界': ''})
        self.assertEqual(recs[0]['lineage'], {'不存在': [], '越界': []})

    def test_missing_table_zero_records(self):
        for sel in ({'index': 99}, {'header_contains': '无此表'}):
            m = {'table': sel, 'fields': [
                {'target': 'x', 'column': {'index': 0}}]}
            self.assertEqual(collect.build(self.doc, {'mapping_json': m}), [])

    def test_stitched_scope_lineage_from_cell(self):
        st = tbl(['账号', '金额'], [['6227', '100']],
                 [[None, None], [{'bbox': [0, 0, 1, 1], 'page': 3, 'space': 'px'},
                                 {'bbox': [1, 0, 2, 1], 'page': 3, 'space': 'px'}]])
        doc = {'pages': [], 'stitched_tables': [st]}
        m = {'table': {'index': 0}, 'fields': [
            {'target': '卡号', 'column': {'name': '账号'}}]}
        recs = collect.build(doc, {'mapping_json': m})
        lin = recs[0]['lineage']['卡号'][0]
        self.assertEqual(lin['table_scope'], 'stitched')
        self.assertEqual(lin['page'], 3)
        self.assertEqual(lin['space'], 'px')

    def test_merged_page_table_skipped(self):
        st = tbl(['账号'], [['s1']], [[None], [{'bbox': [0, 0, 1, 1], 'page': 1}]])
        st['parts'] = [{'page': 1, 'tbl': 0}]
        doc = {'pages': [{'index': 1, 'tables': [self.t]}],
               'stitched_tables': [st]}
        cands = collect._candidate_tables(doc)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0][1], 'stitched')
        m = {'table': {'index': 0}, 'fields': [
            {'target': '卡号', 'column': {'name': '账号'}}]}
        recs = collect.build(doc, {'mapping_json': m})
        self.assertEqual(recs[0]['values']['卡号'], 's1')

    def test_duplicate_header_keys(self):
        t = tbl(['金额', '金额'], [['1', '2']], bbox_cells(1))
        doc = page_doc([t])
        m = {'table': {'index': 0}, 'fields': [
            {'target': '借方', 'column': {'name': '金额'}},
            {'target': '贷方', 'column': {'name': '金额_1'}}]}
        recs = collect.build(doc, {'mapping_json': m})
        self.assertEqual(recs[0]['values'], {'借方': '1', '贷方': '2'})

    def test_field_without_target_skipped(self):
        m = {'table': {'index': 0}, 'fields': [
            {'column': {'name': '账号'}},
            {'target': '卡号', 'column': {'name': '账号'}}]}
        recs = collect.build(self.doc, {'mapping_json': m})
        self.assertEqual(list(recs[0]['values']), ['卡号'])


if __name__ == '__main__':
    unittest.main()