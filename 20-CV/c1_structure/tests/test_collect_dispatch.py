"""C1 golden：spec_version 分发正确 + 老规则逐字段输出不变。

运行（用项目环境）：
    D:/miniforge3/envs/paddle/python.exe -m unittest discover -s c1_structure/tests -v
"""
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import collect, collect_logic


def _doc():
    """一页一表两行；cells 是 headers 行 + 两条数据行（_anchor 取 r+1）。"""
    return {
        'pages': [{
            'index': 1,
            'tables': [{
                'headers': ['名称', '金额'],
                'rows': [['甲', '10'], ['乙', '20']],
                'cells': [
                    ['名称', '金额'],
                    [[1, 1, 2, 2], [3, 1, 4, 2]],
                    [[1, 3, 2, 4], [3, 3, 4, 4]],
                ],
                'coord': {'space': 'A'},
            }],
        }],
        'stitched_tables': [],
    }


def _expected(values, lineage):
    """测试脚手架：包装预期信封；values/lineage 全部在下方逐字写死。"""
    return {
        'index': 0,
        'values': values,
        'original': dict(values),
        'lineage': lineage,
        'review': {'state': 'pending', 'at': None},
    }


def _anchor(bbox, raw):
    return {'page': 1, 'table_index': 0, 'table_scope': 'page',
            'cell_bbox': bbox, 'space': 'A', 'raw_text': raw}


GOLDEN_PASSTHROUGH = [
    _expected(
        {'名称': '甲', '金额': '10'},
        {'名称': [_anchor([1, 1, 2, 2], '甲')],
         '金额': [_anchor([3, 1, 4, 2], '10')]}),
    _expected(
        {'名称': '乙', '金额': '20'},
        {'名称': [_anchor([1, 3, 2, 4], '乙')],
         '金额': [_anchor([3, 3, 4, 4], '20')]}),
]
GOLDEN_PASSTHROUGH[1]['index'] = 1

GOLDEN_MAPPING = [
    _expected(
        {'项目': '甲', '数量': '10'},
        {'项目': [_anchor([1, 1, 2, 2], '甲')],
         '数量': [_anchor([3, 1, 4, 2], '10')]}),
    _expected(
        {'项目': '乙', '数量': '20'},
        {'项目': [_anchor([1, 3, 2, 4], '乙')],
         '数量': [_anchor([3, 3, 4, 4], '20')]}),
]
GOLDEN_MAPPING[1]['index'] = 1

MAPPING_V1 = {'table': {'index': 0}, 'fields': [
    {'target': '项目', 'column': {'name': '名称'}},
    {'target': '数量', 'column': {'index': 1}},
]}


class CollectDispatchTest(unittest.TestCase):

    def setUp(self):
        self.doc = _doc()

    def test_passthrough_golden(self):
        """无 mapping_json：老透传输出逐字段等于 C1 前的 golden。"""
        self.assertEqual(collect.build(self.doc), GOLDEN_PASSTHROUGH)

    def test_explicit_v1_golden(self):
        """spec_version=1 与缺省 v1 映射输出均等于 golden。"""
        for mapping in (MAPPING_V1,
                        dict(MAPPING_V1, spec_version=1)):
            got = collect.build(self.doc, {'mapping_json': mapping})
            self.assertEqual(got, GOLDEN_MAPPING)

    def test_v2_dispatches_to_build_logic(self):
        """spec_version=2 只走新引擎，不碰老分支。"""
        sentinel = [{'sentinel': True}]
        tpl = {'mapping_json': {'spec_version': 2, 'fields': []}}
        with patch.object(collect_logic, 'build_logic',
                          return_value=sentinel) as stub:
            got = collect.build(self.doc, tpl)
        stub.assert_called_once_with(self.doc, tpl)
        self.assertIs(got, sentinel)

    def test_v2_empty_spec_is_passthrough(self):
        """C4 起默认 row 策略在无 fields 时与老 passthrough 逐字段相等。"""
        records = collect.build(self.doc, {'mapping_json': {'spec_version': 2}})
        self.assertEqual(records, GOLDEN_PASSTHROUGH)


if __name__ == '__main__':
    unittest.main()
