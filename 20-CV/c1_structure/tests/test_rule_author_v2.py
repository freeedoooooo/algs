"""§6.9 自然语言驱动：v2 提示词、字段名约束、模式二选一。"""
import unittest

from c1_structure.agent import llm, rule_author
from c1_structure.agent.prompts import rule_author_v1, rule_author_v2


def _doc():
    return {'file': {'name': 't.csv', 'kind': 'csv'},
            'pages': [{'index': 1, 'space': 'source', 'texts': [],
                       'tables': [{'headers': ['交易日期', '借', '余额'],
                                   'rows': [['2021-01-01', '10', '100']],
                                   'cells': [], 'page': 1,
                                   'coord': {'space': 'source'}}]}],
            'stitched_tables': []}


def _spec(fields, strategy='row'):
    return {'spec_version': 2, 'records': {'strategy': strategy},
            'fields': [{'target': t, 'pipeline': [
                {'op': 'cell', 'source': 'main',
                 'column': {'name': c}, 'row': 'current'}]}
                for t, c in fields]}


class PromptV2Test(unittest.TestCase):
    def test_render_includes_user_and_candidates(self):
        from c1_structure.agent import context
        ctx = context.doc_to_context(_doc())
        text = rule_author_v2.render(ctx, '提取借方金额和余额', None,
                                      ['account_1', 'account_2'])
        self.assertIn('提取借方金额和余额', text)
        self.assertIn('account_1', text)
        self.assertIn(rule_author_v2.PROMPT_VERSION, text)
        self.assertIn('records.strategy', text)
        self.assertIn(rule_author_v1.RULES.split('\n')[2], text)

    def test_render_rejects_empty_prompt(self):
        from c1_structure.agent import context
        with self.assertRaises(ValueError):
            rule_author_v2.render(context.doc_to_context(_doc()), '')


class NaturalModeTest(unittest.TestCase):
    def test_natural_generates_from_prompt(self):
        result = rule_author.generate_rule(
            _doc(), user_prompt='提取借方金额',
            llm_fn=lambda p, s: _spec([('借方金额', '借')]))
        self.assertEqual(result.meta['mode'], 'natural')
        self.assertTrue(result.meta['user_prompt_sha256'])
        self.assertEqual(result.schema['fields'][0]['name'], '借方金额')

    def test_column_candidates_enforced(self):
        with self.assertRaises(llm.LLMSchemaFail):
            rule_author.generate_rule(
                _doc(), user_prompt='提取金额',
                column_candidates=['account_1', 'account_2'],
                llm_fn=lambda p, s: _spec([('借方金额', '借')]))
        ok = rule_author.generate_rule(
            _doc(), user_prompt='提取金额',
            column_candidates=['account_1', 'account_2'],
            llm_fn=lambda p, s: _spec([('account_1', '借')]))
        self.assertEqual(ok.schema['fields'][0]['name'], 'account_1')

    def test_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            rule_author.generate_rule(
                _doc(), fields=[{'target': 'a'}], user_prompt='提取a')
        with self.assertRaises(ValueError):
            rule_author.generate_rule(_doc())

    def test_precise_mode_unchanged(self):
        result = rule_author.generate_rule(
            _doc(), fields=[{'target': '借方金额', 'description': ''}],
            llm_fn=lambda p, s: _spec([('借方金额', '借')]))
        self.assertEqual(result.meta['mode'], 'precise')
        self.assertNotIn('user_prompt_sha256', result.meta)


if __name__ == '__main__':
    unittest.main()
