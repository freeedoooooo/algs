"""P0.5-① 受限 ReAct：封闭工具集 + 确定性终止 + 预算 + 留痕。"""
import unittest

from c1_structure.agent import react
from c1_structure.agent.llm import LLMSchemaFail


class ReActTest(unittest.TestCase):
    def test_done_early_stops(self):
        def bump(args):
            return {'n': args.get('n', 1)}
        calls = []

        def llm_fn(obs, state):
            calls.append(state.get('n', 0))
            return {'tool': 'bump', 'args': {'n': 3},
                    'thought': '直接给达标值'}

        loop = react.ReActLoop({'bump': bump},
                               lambda s, o: s.get('n') == 3, llm_fn)
        result = loop.run('goal')
        self.assertTrue(result.done)
        self.assertEqual(result.rounds, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.trace[0]['tool'], 'bump')

    def test_budget_exhausted(self):
        def bump(args):
            return {'n': state_n(args)}
        state_n = lambda a: 0  # 永不达标

        def llm_fn(obs, state):
            return {'tool': 'bump', 'args': {}}

        loop = react.ReActLoop({'bump': bump},
                               lambda s, o: s.get('n') == 999, llm_fn,
                               max_rounds=3)
        result = loop.run('goal')
        self.assertFalse(result.done)
        self.assertEqual(result.rounds, 3)
        self.assertEqual(len(result.trace), 3)

    def test_denied_tool(self):
        def llm_fn(obs, state):
            return {'tool': 'drop_table', 'args': {}}

        loop = react.ReActLoop({'safe': lambda a: {}},
                               lambda s, o: False, llm_fn)
        with self.assertRaises(react.ReActToolDenied):
            loop.run('goal')

    def test_finish_only_when_validator_agrees(self):
        def llm_fn(obs, state):
            return {'tool': 'finish', 'thought': '我觉得好了'}

        loop = react.ReActLoop({'noop': lambda a: {}},
                               lambda s, o: False, llm_fn, max_rounds=2)
        result = loop.run('goal')
        self.assertFalse(result.done)
        self.assertEqual(result.rounds, 2)
        self.assertTrue(all(t['tool'] == 'finish' for t in result.trace))

    def test_bad_decision_rejected(self):
        loop = react.ReActLoop({'noop': lambda a: {}},
                               lambda s, o: False, lambda o, s: 'not dict')
        with self.assertRaises(LLMSchemaFail):
            loop.run('goal')

    def test_tool_result_must_be_dict(self):
        loop = react.ReActLoop({'bad': lambda a: []},
                               lambda s, o: False,
                               lambda o, s: {'tool': 'bad', 'args': {}})
        with self.assertRaises(LLMSchemaFail):
            loop.run('goal')

    def test_render_tools(self):
        def inspect(args):
            """看候选表列与样例"""
            return {}
        text = react.render_tools({'inspect': inspect})
        self.assertIn('inspect', text)
        self.assertIn('看候选表列与样例', text)


if __name__ == '__main__':
    unittest.main()
