"""S1 单测：智能抽取的提示词构造、证据回锚与无证据留空。不触发真实模型调用。"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import config
from c1_structure import smart_extract


def _doc():
    return {
        'pages': [{
            'index': 1, 'space': 'source', 'plain_text': '',
            'texts': [
                {'text': '统一社会信用代码：91310115MA1K3PQ45X',
                 'box': [[10, 10], [400, 10], [400, 30], [10, 30]]},
                {'text': '法定代表人 张三',
                 'box': [[10, 40], [220, 40], [220, 60], [10, 60]]},
            ],
            'tables': [],
        }],
        'stitched_tables': [],
    }


def _tpl():
    return {'mapping_json': {
        'spec_version': 3,
        'records': {'strategy': 'all'},
        'fields': [
            {'target': '信用代码', 'description': '18 位统一社会信用代码'},
            {'target': '法人', 'description': '法定代表人姓名'},
            {'target': '缺失项', 'description': '原文中没有'},
        ],
    }}


class SmartExtractTest(unittest.TestCase):

    def setUp(self):
        self._stub = config.SMART_STUB
        config.SMART_STUB = False

    def tearDown(self):
        config.SMART_STUB = self._stub

    def test_stub_returns_fixed_kv_without_llm(self):
        config.SMART_STUB = True
        def forbidden_llm(prompt, spec):
            self.fail('占位模式不应调用模型')
        rec = smart_extract.build_smart(_doc(), _tpl(), llm=forbidden_llm)[0]
        self.assertEqual(rec['values'], {'field1': '智能抽取结果1'})
        self.assertEqual(rec['original'], {'field1': '智能抽取结果1'})
        self.assertEqual(rec['lineage'], {'field1': []})
        self.assertEqual(rec['review'], {'state': 'pending', 'at': None})

    def test_evidence_anchor_and_empty_on_no_evidence(self):
        seen = {}

        def fake_llm(prompt, spec):
            seen['prompt'] = prompt
            return {'fields': [
                {'target': '信用代码', 'value': '91310115MA1K3PQ45X',
                 'evidence': '统一社会信用代码：91310115MA1K3PQ45X'},
                {'target': '法人', 'value': '张三', 'evidence': '法定代表人 张三'},
                {'target': '缺失项', 'value': '臆造值', 'evidence': ''},
            ]}

        records = smart_extract.build_smart(_doc(), _tpl(), llm=fake_llm)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(set(rec), {'index', 'values', 'original',
                                    'lineage', 'review'})
        self.assertEqual(rec['values']['信用代码'], '91310115MA1K3PQ45X')
        self.assertEqual(rec['values']['法人'], '张三')
        self.assertEqual(rec['values']['缺失项'], '')
        anchor = rec['lineage']['信用代码'][0]
        self.assertEqual(anchor['page'], 1)
        self.assertEqual(anchor['cell_bbox'], [10, 10, 400, 30])
        self.assertIn('信用代码', seen['prompt'])
        self.assertIn('18 位统一社会信用代码', seen['prompt'])

    def test_dict_payload_and_missing_target(self):
        def fake_llm(prompt, spec):
            return {'信用代码': {'value': '91310115MA1K3PQ45X',
                                 'evidence': '91310115MA1K3PQ45X'}}
        rec = smart_extract.build_smart(_doc(), _tpl(), llm=fake_llm)[0]
        self.assertEqual(rec['values']['法人'], '')
        self.assertEqual(rec['lineage']['法人'], [])
        self.assertEqual(rec['values']['信用代码'], '91310115MA1K3PQ45X')

    def test_no_fields_returns_empty(self):
        self.assertEqual(smart_extract.build_smart(
            _doc(), {'mapping_json': {'spec_version': 3}}), [])

    def test_missing_config_fails_loudly(self):
        old = (config.LLM_BASE_URL, config.LLM_API_KEY, config.LLM_MODEL)
        try:
            config.LLM_BASE_URL = ''
            config.LLM_API_KEY = ''
            config.LLM_MODEL = ''
            with self.assertRaises(RuntimeError):
                smart_extract.build_smart(_doc(), _tpl())
        finally:
            (config.LLM_BASE_URL, config.LLM_API_KEY,
             config.LLM_MODEL) = old


if __name__ == '__main__':
    unittest.main()
