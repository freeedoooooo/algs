"""P0.5-② generate_rule_react：样本触发 + 受限迭代 + 达标判定。"""
import unittest

from c1_structure.agent import llm, rule_author
from c1_structure.agent.rule_author import is_acceptable


def _doc(rows=None):
    rows = rows if rows is not None else [['10', 'A'], ['20', 'B']]
    return {'file': {'name': 't.csv', 'kind': 'csv'},
            'pages': [{'index': 1, 'space': 'source',
                       'texts': [{'text': '流水', 'box': [0, 0, 1, 1]}],
                       'tables': [{'headers': ['金额', '状态'], 'rows': rows,
                                   'cells': [], 'page': 1,
                                   'coord': {'space': 'source'}}]}],
            'stitched_tables': []}


def _spec(target, column):
    return {'spec_version': 2, 'fields': [
        {'target': target, 'pipeline': [
            {'op': 'cell', 'source': 'main',
             'column': {'name': column}, 'row': 'current'}]}]}


TARGETS = [{'values': {'金额': '10'}}, {'values': {'金额': '20'}}]


class RuleAuthorReactTest(unittest.TestCase):
    def test_one_shot_already_good_skips_react(self):
        calls = []

        def llm_fn(prompt, spec):
            calls.append(1)
            return _spec('金额', '金额')

        result = rule_author.generate_rule_react(
            _doc(), [{'target': '金额'}], llm_fn=llm_fn, targets=TARGETS)
        self.assertTrue(result.meta['react_done'])
        self.assertEqual(result.meta['react_rounds'], 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.diagnostics['compare']['field_accuracy'], 1.0)

    def test_react_revises_to_target(self):
        steps = []

        def llm_fn(prompt_or_obs, spec_or_state):
            # 首轮 llm.call_json 调用（两参数：prompt, spec）
            if isinstance(prompt_or_obs, str):
                return _spec('金额', '不存在列')
            # ReAct 决策（obs, state）
            stage = len(steps)
            steps.append(1)
            if stage == 0:
                return {'tool': 'inspect_tables', 'args': {},
                        'thought': '先看看真实列名'}
            if stage == 1:
                return {'tool': 'revise_spec', 'thought': '改用正确列名',
                        'args': {'spec': _spec('金额', '金额')}}
            return {'tool': 'finish', 'thought': '已达标'}

        result = rule_author.generate_rule_react(
            _doc(), [{'target': '金额'}], llm_fn=llm_fn,
            targets=TARGETS, max_rounds=4)
        self.assertTrue(result.meta['react_done'])
        self.assertGreaterEqual(result.meta['react_rounds'], 2)
        self.assertEqual(result.diagnostics['compare']['field_accuracy'], 1.0)
        tools = [t['tool'] for t in result.meta['react_trace']]
        self.assertIn('inspect_tables', tools)
        self.assertIn('revise_spec', tools)

    def test_is_acceptable_rules(self):
        good = {'anchor_coverage': 1.0, 'empty_fields': [],
                'compare': {'targets_n': 2, 'count_match': True,
                            'field_accuracy': 1.0}}
        self.assertTrue(is_acceptable(good, TARGETS))
        bad = dict(good, compare={'targets_n': 2, 'count_match': True,
                                  'field_accuracy': 0.5})
        self.assertFalse(is_acceptable(bad, TARGETS))
        self.assertFalse(is_acceptable(
            {'anchor_coverage': 0.5, 'empty_fields': []}, TARGETS))

    def test_budget_exhausted_returns_trace(self):
        def llm_fn(prompt_or_obs, spec_or_state):
            if isinstance(prompt_or_obs, str):
                return _spec('金额', '不存在列')
            return {'tool': 'inspect_tables', 'args': {},
                    'thought': '反复看表'}

        result = rule_author.generate_rule_react(
            _doc(), [{'target': '金额'}], llm_fn=llm_fn,
            targets=TARGETS, max_rounds=3)
        self.assertFalse(result.meta['react_done'])
        self.assertEqual(result.meta['react_rounds'], 3)
        self.assertEqual(len(result.meta['react_trace']), 3)

    def test_denied_tool_rejected(self):
        def llm_fn(prompt_or_obs, spec_or_state):
            if isinstance(prompt_or_obs, str):
                return _spec('金额', '不存在列')
            return {'tool': 'drop_table', 'args': {}}

        from c1_structure.agent.react import ReActToolDenied
        with self.assertRaises(ReActToolDenied):
            rule_author.generate_rule_react(
                _doc(), [{'target': '金额'}], llm_fn=llm_fn,
                targets=TARGETS, max_rounds=2)


if __name__ == '__main__':
    unittest.main()
