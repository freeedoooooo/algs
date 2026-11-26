"""P0-① agent 公共层：LLM 注入/Stub、上下文压缩、静态校验与干跑对拍。"""
import unittest

from c1_structure.agent import context, llm, validate
from c1_structure.agent.prompts import rule_author_v1


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


class LLMTest(unittest.TestCase):
    def test_injected_llm_no_network(self):
        obj, meta = llm.call_json(
            'p', {}, llm=lambda p, s: {'spec_version': 2})
        self.assertEqual(obj, {'spec_version': 2})
        self.assertFalse(meta['stub'])

    def test_stub_no_network(self):
        obj, meta = llm.call_json('p', {}, stub=lambda p: {'stub': 1})
        self.assertEqual(obj, {'stub': 1})
        self.assertTrue(meta['stub'])

    def test_repair_on_bad_json(self):
        calls = []

        def fake(prompt, spec):
            calls.append(prompt)
            if len(calls) == 1:
                raise llm.LLMBadJSON('bad')
            return {'ok': True}

        obj, meta = llm.call_json('base', {}, llm=fake)
        self.assertEqual(obj, {'ok': True})
        self.assertEqual(meta['repairs'], 1)
        self.assertIn('上次返回的不是合法 JSON', calls[1])

    def test_unconfigured_raises(self):
        # 生产配置缺 API key 时显式报错，不静默降级
        import c1_structure.config as cfg
        old = (cfg.LLM_API_KEY, cfg.LLM_BASE_URL, cfg.LLM_MODEL)
        try:
            cfg.LLM_API_KEY, cfg.LLM_BASE_URL, cfg.LLM_MODEL = '', 'x', 'm'
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('p')
        finally:
            cfg.LLM_API_KEY, cfg.LLM_BASE_URL, cfg.LLM_MODEL = old


class ContextTest(unittest.TestCase):
    def test_context_shape_and_order(self):
        ctx = context.doc_to_context(_doc())
        self.assertEqual(ctx['shape']['table_count'], 1)
        self.assertEqual(ctx['tables'][0]['headers'], ['金额', '状态'])
        self.assertEqual(len(ctx['tables'][0]['samples']), 2)
        self.assertIn('流水', ctx['text_hint'])
        self.assertIn('列名', context.render_context(ctx))

    def test_budget_truncates(self):
        ctx = context.doc_to_context(_doc(), budget=20)
        self.assertTrue(ctx['truncated'])


class ValidateTest(unittest.TestCase):
    def test_validate_spec_ok_and_bad(self):
        good = {'spec_version': 2, 'fields': [
            {'target': '金额', 'pipeline': [{'op': 'cell'}]}]}
        self.assertEqual(validate.validate_spec(good), [])
        bad = {'spec_version': 3, 'fields': [
            {'target': '金额', 'pipeline': [{'op': 'bogus'}]},
            {'target': '金额', 'pipeline': []}]}
        issues = validate.validate_spec(bad)
        self.assertTrue(any('spec_version' in x for x in issues))
        self.assertTrue(any('未知算子' in x for x in issues))
        self.assertTrue(any('target 重复' in x for x in issues))

    def test_dry_run_and_compare(self):
        doc = _doc()
        spec = {'spec_version': 2, 'records': {'strategy': 'row'},
                'fields': [{'target': '金额',
                            'pipeline': [{'op': 'cell', 'source': 'main',
                                          'column': {'name': '金额'},
                                          'row': 'current'}]}]}
        d = validate.dry_run(spec, doc)
        self.assertEqual(d['records_n'], 2)
        self.assertEqual(d['field_hits'], {'金额': 2})
        self.assertEqual(d['anchor_coverage'], 1.0)
        targets = [{'values': {'金额': '10'}}, {'values': {'金额': '99'}}]
        cmp = validate.compare_targets(d['records'], targets)
        self.assertTrue(cmp['count_match'])
        self.assertEqual(cmp['field_accuracy'], 0.5)
        self.assertEqual(len(cmp['diffs']), 1)

    def test_dry_run_bad_spec_no_crash(self):
        d = validate.dry_run({'spec_version': 2, 'fields': [],
                              'records': {'strategy': 'bogus'}}, _doc())
        self.assertIn('error', d)

    def test_prompt_has_schema_and_version(self):
        text = rule_author_v1.render(
            context.doc_to_context(_doc()), [{'target': '金额'}])
        self.assertIn('spec_version', text)
        self.assertIn('target', text)
        self.assertIn(rule_author_v1.PROMPT_VERSION, text)


if __name__ == '__main__':
    unittest.main()
