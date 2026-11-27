import unittest

from c1_structure import collect, config, smart_extract


def _doc():
    return {'pages': [{
        'index': 1, 'space': 'source',
        'texts': [],
        'tables': [{
            'page': 1, 'coord': {'space': 'source'},
            'headers': ['设备编号', '设备名称'],
            'rows': [['EQ-001', '1号泵'], ['EQ-002', '2号泵']],
            'cells': [
                [[0, 0, 80, 20], [80, 0, 180, 20]],
                [[0, 20, 80, 40], [80, 20, 180, 40]],
                [[0, 40, 80, 60], [80, 40, 180, 60]],
            ],
        }],
    }], 'stitched_tables': []}


def _tpl():
    return {'mapping_json': {'spec_version': 2, 'fields': [
        {'target': '设备编号', 'pipeline': []},
        {'target': '设备名称', 'pipeline': []},
    ]}}


class SmartRowFallbackTest(unittest.TestCase):
    def setUp(self):
        self.old_stub = config.SMART_STUB
        config.SMART_STUB = False

    def tearDown(self):
        config.SMART_STUB = self.old_stub

    def test_only_failed_row_is_sent_and_filled(self):
        records = collect.passthrough(_doc())
        records[1]['values']['设备名称'] = ''
        records[1]['original']['设备名称'] = ''
        records[1]['lineage']['设备名称'] = []
        prompts = []

        def llm(prompt, spec):
            prompts.append(prompt)
            return {'设备名称': {'value': '2号泵', 'evidence': '2号泵'}}

        output, diag = smart_extract.build_row_fallback(
            _doc(), _tpl(), records, llm=llm)
        self.assertEqual(diag['attempted'], 1)
        self.assertEqual(diag['filled'], 1)
        self.assertEqual(output[1]['values']['设备名称'], '2号泵')
        self.assertEqual(output[1]['lineage']['设备名称'][0]['cell_bbox'],
                         [80, 40, 180, 60])
        self.assertEqual(len(prompts), 1)
        self.assertNotIn('1号泵', prompts[0])
        self.assertIn('设备编号', prompts[0])

    def test_complete_records_do_not_call_model(self):
        records = collect.passthrough(_doc())
        output, diag = smart_extract.build_row_fallback(
            _doc(), _tpl(), records,
            llm=lambda *_: self.fail('完整记录不应调用模型'))
        self.assertEqual(output, records)
        self.assertEqual(diag['attempted'], 0)

    def test_model_failure_preserves_v2_record(self):
        records = collect.passthrough(_doc())
        records[1]['values']['设备名称'] = ''
        before = dict(records[1]['values'])

        def llm(*_):
            raise RuntimeError('model unavailable')

        output, diag = smart_extract.build_row_fallback(
            _doc(), _tpl(), records, llm=llm)
        self.assertEqual(output[1]['values'], before)
        self.assertEqual(diag['failed'], [{'index': 1,
                                          'reason': 'RuntimeError'}])

    def test_missing_lineage_can_be_anchored_without_changing_value(self):
        records = collect.passthrough(_doc())
        records[0]['lineage']['设备名称'] = []

        def llm(*_):
            return {'设备名称': {'value': '1号泵', 'evidence': '1号泵'}}

        output, diag = smart_extract.build_row_fallback(
            _doc(), _tpl(), records, llm=llm)
        self.assertEqual(output[0]['values']['设备名称'], '1号泵')
        self.assertTrue(output[0]['lineage']['设备名称'])
        self.assertEqual(diag['filled'], 1)

    def test_fallback_cannot_overwrite_existing_value(self):
        records = collect.passthrough(_doc())
        records[0]['lineage']['设备名称'] = []

        def llm(*_):
            return {'设备名称': {'value': '错误值', 'evidence': '1号泵'}}

        output, diag = smart_extract.build_row_fallback(
            _doc(), _tpl(), records, llm=llm)
        self.assertEqual(output[0]['values']['设备名称'], '1号泵')
        self.assertFalse(output[0]['lineage']['设备名称'])
        self.assertEqual(diag['filled'], 0)

    def test_stub_mode_skips_fallback(self):
        config.SMART_STUB = True
        records = collect.passthrough(_doc())
        output, diag = smart_extract.build_row_fallback(
            _doc(), _tpl(), records,
            llm=lambda *_: self.fail('stub 模式不应调用模型'))
        self.assertEqual(output, records)
        self.assertEqual(diag['skipped'], 'stub')

    def test_max_rows_bounds_model_calls(self):
        doc = _doc()
        doc['pages'][0]['tables'][0]['rows'] = [
            ['EQ-003', ''], ['EQ-004', '']]
        records = collect.passthrough(doc)
        calls = []

        def llm(*_):
            calls.append(1)
            return {}

        _, diag = smart_extract.build_row_fallback(
            doc, _tpl(), records, llm=llm, max_rows=1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(diag['attempted'], 1)


if __name__ == '__main__':
    unittest.main()
