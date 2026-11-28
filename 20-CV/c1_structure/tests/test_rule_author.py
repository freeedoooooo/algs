"""P0-② generate_rule：生成草稿、中间层对拍、警告与显式失败。"""
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


SPEC = {'spec_version': 2, 'fields': [
    {'target': '金额', 'pipeline': [
        {'op': 'cell', 'source': 'main',
         'column': {'name': '金额'}, 'row': 'current'}]}]}


class FakeContent:
    def __init__(self, states):
        self.states = states

    def get_records(self, file_id):
        return {'files': [{'records': [
            {'index': i, 'values': {'金额': v}, 'original': {'金额': v},
             'review': {'state': s, 'at': None}}
            for i, (v, s) in enumerate(self.states)]}]}


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
        content = FakeContent([('10', 'confirmed'), ('20', 'pending'),
                               ('30', 'rejected'), ('40', 'edited')])
        targets = rule_author._targets_from_middle(content, 1)
        self.assertEqual([t['values']['金额'] for t in targets], ['10', '40'])

    def test_auto_targets_from_middle(self):
        content = FakeContent([('10', 'confirmed'), ('20', 'confirmed')])
        result = rule_author.generate_rule(
            _doc(), [{'target': '金额'}], llm_fn=lambda p, s: dict(SPEC),
            content=content, sample_file_id=1)
        self.assertEqual(result.diagnostics['compare']['targets_n'], 2)
        self.assertEqual(result.diagnostics['compare']['field_accuracy'], 1.0)

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
