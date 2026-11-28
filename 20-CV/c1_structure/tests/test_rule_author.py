"""P0-② generate_rule：生成草稿、抽取结果对拍、警告与显式失败。"""
import inspect
import unittest
from unittest import mock

from c1_structure.agent import llm, rule_author
from c1_structure.agent.rule_author import GenerationResult


def _doc(rows=None):
    rows = rows if rows is not None else [['10', 'A'], ['20', 'B']]
    return {
        'file': {'name': 't.csv', 'kind': 'csv'},
        'pages': [{'index': 1, 'space': 'source',
                   'texts': [{'text': '流水', 'box': [0, 0, 1, 1]}],
                   'tables': [{'headers': ['金额', '状态'], 'rows': rows,
                               'cells': [], 'page': 1,
                               'coord': {'space': 'source'}}]}],
        'stitched_tables': [],
    }


SPEC = {'spec_version': 2,
        'tables': [{'ref': 'main', 'role': 'record_source', 'index': 0}],
        'records': {'strategy': 'row', 'source_ref': 'main'},
        'fields': [
    {'target': '金额', 'pipeline': [
        {'op': 'cell', 'source': 'main',
         'column': {'name': '金额'}, 'row': 'current'}]}]}


def _result_records(states):
    return {'extract_result_id': 7, 'records': [
        {'index': i, 'values': {'金额': v}, 'original': {'金额': v},
         'review': {'state': s, 'at': None}}
        for i, (v, s) in enumerate(states)]}


class RuleAuthorTest(unittest.TestCase):
    def test_generate_with_targets(self):
        result = rule_author.generate_rule(
            _doc(), [{'target': '金额', 'description': '借方发生额'}],
            llm_fn=lambda p, s: dict(SPEC),
            targets=[{'values': {'金额': '10'}}, {'values': {'金额': '99'}}])
        self.assertIsInstance(result, GenerationResult)
        self.assertEqual(result.diagnostics['records_n'], 2)
        self.assertEqual(result.diagnostics['compare']['field_accuracy'], 0.5)
        self.assertEqual(result.confidence, round(0.6 * 0.5 + 0.4 * 1.0, 4))
        self.assertTrue(result.spec['_agent_meta']['input_sha256'])
        self.assertEqual(result.schema['fields'][0]['name'], '金额')
        d = result.as_dict()
        self.assertIn('diagnostics', d)
        self.assertIn('spec', d)

    def test_middle_states_only_confirmed_or_edited(self):
        from c1_structure.store import content_db
        records = _result_records([('10', 'confirmed'), ('20', 'pending'),
                                   ('30', 'rejected'), ('40', 'edited')])
        with mock.patch.object(content_db, 'get_records',
                               return_value=records) as get_records:
            targets = rule_author._targets_from_middle(7)
        get_records.assert_called_once_with(7)
        self.assertEqual([t['values']['金额'] for t in targets], ['10', '40'])

    def test_auto_targets_from_extract_result(self):
        from c1_structure.store import content_db
        records = _result_records([('10', 'confirmed'), ('20', 'confirmed')])
        with mock.patch.object(content_db, 'get_records',
                               return_value=records) as get_records:
            result = rule_author.generate_rule(
                _doc(), [{'target': '金额'}], llm_fn=lambda p, s: dict(SPEC),
                sample_extract_result_id=7)
        get_records.assert_called_once_with(7)
        self.assertEqual(result.diagnostics['compare']['targets_n'], 2)
        self.assertEqual(result.diagnostics['compare']['field_accuracy'], 1.0)
        self.assertEqual(result.meta['sample_extract_result_id'], 7)
        self.assertNotIn('sample_file_id', result.meta)

    def test_sample_result_parameter_replaces_file_content_api(self):
        for fn in (rule_author.generate_rule, rule_author.generate_rule_react):
            params = inspect.signature(fn).parameters
            self.assertIn('sample_extract_result_id', params)
            self.assertNotIn('sample_file_id', params)
            self.assertNotIn('content', params)

    def test_count_mismatch_warning(self):
        result = rule_author.generate_rule(
            _doc(), [{'target': '金额'}], llm_fn=lambda p, s: dict(SPEC),
            targets=[{'values': {'金额': '10'}}])
        self.assertIn('样例不完整', result.diagnostics['warning'])

    def test_invalid_spec_rejected(self):
        bad = dict(SPEC)
        bad['fields'] = [{'target': '金额', 'pipeline': [{'op': 'bogus'}]}]
        with self.assertRaises(llm.LLMSchemaFail):
            rule_author.generate_rule(
                _doc(), [{'target': '金额'}], llm_fn=lambda p, s: bad)

    def test_empty_fields_rejected(self):
        with self.assertRaises(ValueError):
            rule_author.generate_rule(_doc(), [], llm_fn=lambda p, s: SPEC)

    def test_provider_model_selected_without_qoder_model_leak(self):
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                QODER_MODEL='qoder-only-model',
                LLM_BASE_URL='https://llm.example/v1', LLM_API_KEY='test-key',
                LLM_MODEL='openai-model', SMART_STUB=False), \
                mock.patch.object(llm, 'raw_call', return_value=dict(SPEC)) as call:
            result = rule_author.generate_rule(
                _doc(), [{'target': '金额'}])
        self.assertEqual(result.meta['provider'], 'openai_compatible')
        self.assertEqual(result.meta['model'], 'openai-model')
        self.assertNotIn('model', call.call_args.args[1])

    def test_stub_no_network(self):
        result = rule_author.generate_rule(
            _doc(), [{'target': '金额'}], stub_fn=lambda p: dict(SPEC))
        self.assertTrue(result.meta['stub'])
        self.assertEqual(result.diagnostics['records_n'], 2)


if __name__ == '__main__':
    unittest.main()
