"""§6.9 自然语言驱动：多参考附件、多条规则、逻辑字段类型。"""
import copy
import inspect
import unittest
from unittest import mock

from c1_structure.agent import rule_author
from c1_structure.agent.prompts import rule_author_v1, rule_author_v2


def _doc():
    return {'file': {'name': 't.csv', 'kind': 'csv'},
            'pages': [{'index': 1, 'space': 'source', 'texts': [],
                       'tables': [{'headers': ['交易日期', '借', '余额'],
                                   'rows': [['2021-01-01', '10', '100']],
                                   'cells': [], 'page': 1,
                                   'coord': {'space': 'source'}}]}],
            'stitched_tables': []}


def _reference_doc(name, header, value):
    doc = _doc()
    doc['file']['name'] = name
    table = doc['pages'][0]['tables'][0]
    table['headers'] = [header]
    table['rows'] = [[value]]
    return doc


def _spec(fields, strategy='row'):
    items = []
    for field in fields:
        target, column = field[:2]
        field_type = field[2] if len(field) > 2 else 'string'
        items.append({'target': target, 'type': field_type, 'pipeline': [
            {'op': 'cell', 'source': 't0',
             'column': {'name': column}, 'row': 'current'}]})
    return {'spec_version': 2,
            'tables': [{'ref': 't0', 'role': 'record_source', 'index': 0}],
            'records': {'strategy': strategy, 'source_ref': 't0'},
            'fields': items}


class PromptV2Test(unittest.TestCase):
    def test_render_uses_user_and_logical_fields_without_candidates(self):
        from c1_structure.agent import context
        ctx = context.doc_to_context(_doc())
        text = rule_author_v2.render(ctx, '提取借方金额和余额',
                                     {'reference_doc_id': 'doc-1'})
        self.assertIn('提取借方金额和余额', text)
        self.assertIn('doc-1', text)
        self.assertNotIn('account_1', text)
        self.assertNotIn('候选物理列名', text)
        self.assertIn('中文语义名', text)
        self.assertIn('type', text)
        self.assertIn(rule_author_v2.PROMPT_VERSION, text)
        self.assertIn('records.strategy', text)
        self.assertIn('records.source_ref', text)
        self.assertIn('region_text', text)
        self.assertIn('文档地图', text)
        self.assertIn(rule_author_v1.RULES.split('\n')[2], text)

    def test_render_includes_every_reference_attachment(self):
        from c1_structure.agent import context
        refs = [
            {'file_id': 'file-a', 'name': '附件甲', 'doc_type': 'pdf',
             'doc': _reference_doc('甲.pdf', '参考金额', '111')},
            _reference_doc('附件乙.csv', '参考余额', '222'),
        ]
        text = rule_author_v2.render(context.doc_to_context(_doc()),
                                     '提取借方金额和余额', reference_docs=refs)
        for expected in ('file-a', '附件甲', 'pdf', '参考金额', '111',
                         '附件乙.csv', '参考余额', '222', '主文档解析上下文'):
            self.assertIn(expected, text)
        self.assertIn('不得把参考附件中的 ref 混入规则', text)

    def test_render_multiple_rule_contract(self):
        from c1_structure.agent import context
        text = rule_author_v2.render(context.doc_to_context(_doc()),
                                     '分别生成两条规则', multiple_rules=True)
        self.assertIn('{"rules": [...]}', text)
        self.assertIn('规则名称（中文，不含版本号）', text)
        self.assertIn('每条规则都须单独满足 spec_version=2', text)

    def test_render_rejects_empty_prompt(self):
        from c1_structure.agent import context
        with self.assertRaises(ValueError):
            rule_author_v2.render(context.doc_to_context(_doc()), '')


class NaturalModeTest(unittest.TestCase):
    def test_natural_generates_from_prompt_and_preserves_type(self):
        result = rule_author.generate_rule(
            _doc(), user_prompt='提取借方金额',
            llm_fn=lambda p, s: _spec([('借方金额', '借', 'number')]))
        self.assertEqual(result.meta['mode'], 'natural')
        self.assertTrue(result.meta['user_prompt_sha256'])
        self.assertEqual(result.schema['fields'], [
            {'name': '借方金额', 'type': 'number'}])
        self.assertEqual(result.spec['fields'][0]['type'], 'number')

    def test_column_candidates_parameter_is_removed(self):
        for fn in (rule_author.generate_rule, rule_author.generate_rule_react):
            self.assertNotIn('column_candidates', inspect.signature(fn).parameters)
        with self.assertRaises(TypeError):
            rule_author.generate_rule(
                _doc(), user_prompt='提取金额', column_candidates=['account_1'],
                llm_fn=lambda p, s: _spec([('借方金额', '借')]))

    def test_logical_target_is_not_restricted_to_physical_headers(self):
        result = rule_author.generate_rule(
            _doc(), user_prompt='提取借方发生金额',
            llm_fn=lambda p, s: _spec([('借方发生金额', '借', 'number')]))
        self.assertEqual(result.schema['fields'][0]['name'], '借方发生金额')
        self.assertNotIn('借方发生金额', _doc()['pages'][0]['tables'][0]['headers'])

    def test_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            rule_author.generate_rule(
                _doc(), fields=[{'target': 'a'}], user_prompt='提取a')
        with self.assertRaises(ValueError):
            rule_author.generate_rule(_doc())

    def test_reference_docs_enter_prompt_but_not_main_dry_run(self):
        prompts = []
        reference_docs = [
            {'file_id': 'a', 'name': '甲附件', 'doc_type': 'pdf',
             'doc': _reference_doc('甲.pdf', '甲方字段', '甲内容')},
            _reference_doc('乙.csv', '乙方字段', '乙内容'),
        ]

        def llm_fn(prompt, _spec_conf):
            prompts.append(prompt)
            return _spec([('借方金额', '借', 'number')])

        main_doc = _doc()
        with mock.patch.object(rule_author.validate, 'dry_run',
                               wraps=rule_author.validate.dry_run) as dry_run:
            result = rule_author.generate_rule(
                main_doc, user_prompt='提取借方金额', llm_fn=llm_fn,
                reference_docs=reference_docs)
        self.assertEqual(len(prompts), 1)
        for expected in ('甲附件', '甲方字段', '甲内容', '乙.csv',
                         '乙方字段', '乙内容'):
            self.assertIn(expected, prompts[0])
        dry_run.assert_called_once()
        self.assertIs(dry_run.call_args.args[1], main_doc)
        self.assertEqual(result.diagnostics['records'][0]['values'],
                         {'借方金额': '10'})
        self.assertIsNone(result.rules)
        self.assertEqual(result.meta['multiple_rules'], False)

    def test_reference_docs_change_input_hash(self):
        def generate(refs):
            return rule_author.generate_rule(
                _doc(), user_prompt='提取金额',
                reference_docs=refs,
                llm_fn=lambda p, s: _spec([('借方金额', '借')]))
        plain = generate([])
        attached = generate([_reference_doc('ref.csv', '参考列', 'x')])
        self.assertNotEqual(plain.meta['input_sha256'],
                            attached.meta['input_sha256'])

    def test_multiple_rules_returns_independent_generation_results(self):
        payload = {'rules': [
            {'name': '金额规则', 'description': '提取借方',
             'spec': _spec([('借方金额', '借', 'number')]),
             'schema': {'fields': [{'name': '不应采信', 'type': 'string'}]}},
            {'name': '余额规则',
             'spec': _spec([('账户余额', '余额', 'number')])},
        ]}
        prompts = []

        def llm_fn(prompt, _spec_conf):
            prompts.append(prompt)
            return copy.deepcopy(payload)

        main_doc = _doc()
        with mock.patch.object(rule_author.validate, 'dry_run',
                               wraps=rule_author.validate.dry_run) as dry_run:
            result = rule_author.generate_rule(
                main_doc, user_prompt='生成金额和余额两条规则',
                llm_fn=llm_fn, multiple_rules=True)
        self.assertIsNone(result.spec)
        self.assertEqual(len(result.rules), 2)
        self.assertEqual([r.name for r in result.rules], ['金额规则', '余额规则'])
        self.assertEqual(result.rules[0].description, '提取借方')
        self.assertEqual(result.rules[0].schema['fields'],
                         [{'name': '借方金额', 'type': 'number'}])
        self.assertEqual(result.rules[1].schema['fields'],
                         [{'name': '账户余额', 'type': 'number'}])
        for i, rule in enumerate(result.rules, 1):
            self.assertEqual(rule.diagnostics['records_n'], 1)
            self.assertEqual(rule.meta['rule_index'], i)
            self.assertEqual(rule.meta['rules_n'], 2)
            self.assertEqual(rule.spec['_agent_meta']['name'], rule.name)
        self.assertIsNot(result.rules[0].meta, result.rules[1].meta)
        self.assertEqual(dry_run.call_count, 2)
        for call in dry_run.call_args_list:
            self.assertIs(call.args[1], main_doc)
        self.assertEqual(result.meta['rules_n'], 2)
        self.assertEqual(len(result.as_dict()['rules']), 2)
        self.assertIn('多条规则模式', prompts[0])

    def test_multiple_rules_validates_each_rule(self):
        bad = _spec([('余额', '余额')])
        bad['fields'][0]['pipeline'][0]['op'] = 'bogus'
        payload = {'rules': [
            {'name': '有效规则', 'spec': _spec([('金额', '借')])},
            {'name': '无效规则', 'spec': bad},
        ]}
        with self.assertRaises(rule_author.llm.LLMSchemaFail) as raised:
            rule_author.generate_rule(
                _doc(), user_prompt='生成两条规则', multiple_rules=True,
                llm_fn=lambda p, s: payload)
        self.assertIn('第2条规则', str(raised.exception))
        self.assertIn('未知算子', str(raised.exception))

    def test_generated_spec_requires_chinese_logical_fields(self):
        payload = _spec([('account_1', '借')])
        with self.assertRaisesRegex(rule_author.llm.LLMSchemaFail,
                                    '中文逻辑字段名'):
            rule_author.generate_rule(
                _doc(), user_prompt='提取金额',
                llm_fn=lambda p, s: payload)

    def test_multitable_rule_requires_explicit_record_source(self):
        payload = _spec([('金额', '借')])
        payload['tables'][0].pop('role')
        payload['tables'].append({'ref': 't1', 'index': 1})
        payload['records'].pop('source_ref')
        with self.assertRaises(rule_author.llm.LLMSchemaFail) as raised:
            rule_author.generate_rule(
                _doc(), user_prompt='提取金额',
                llm_fn=lambda p, s: payload)
        self.assertIn('多表规则须显式声明 tables[].role=record_source',
                      str(raised.exception))
        self.assertIn('多表规则须显式声明 records.source_ref',
                      str(raised.exception))

    def test_multiple_rules_require_wrapper_and_names(self):
        invalid = [
            _spec([('金额', '借')]),
            {'rules': []},
            {'rules': [{'spec': _spec([('金额', '借')])}]},
            {'rules': [{'name': '规则'}]},
            {'rules': [{'name': '规则', 'description': 1,
                        'spec': _spec([('金额', '借')])}]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(rule_author.llm.LLMSchemaFail):
                    rule_author.generate_rule(
                        _doc(), user_prompt='生成规则', multiple_rules=True,
                        llm_fn=lambda p, s: payload)

    def test_builtin_stub_returns_deterministic_rule_container(self):
        payload = {'rules': [
            {'name': '占位规则', 'spec': _spec([('金额', '借')])},
        ]}
        with mock.patch.object(rule_author.llm.config, 'SMART_STUB', True), \
                mock.patch.object(rule_author.llm, 'raw_call') as raw_call:
            builtin = rule_author.generate_rule(
                _doc(), user_prompt='生成规则', multiple_rules=True)
            single = rule_author.generate_rule(
                _doc(), user_prompt='生成规则')
            custom = rule_author.generate_rule(
                _doc(), user_prompt='生成规则', multiple_rules=True,
                stub_fn=lambda p: copy.deepcopy(payload))
        raw_call.assert_not_called()
        self.assertEqual(len(builtin.rules), 1)
        self.assertEqual(builtin.rules[0].name, 't.csv')
        self.assertTrue(builtin.rules[0].spec['_stub'])
        self.assertTrue(builtin.rules[0].meta['stub'])
        self.assertIsNone(single.rules)
        self.assertEqual(single.spec['fields'][0]['target'], '占位字段')
        self.assertEqual(custom.rules[0].name, '占位规则')
        self.assertTrue(custom.meta['stub'])

    def test_invalid_reference_docs_rejected_before_llm(self):
        for refs in ({'doc': _doc()}, ['not-a-doc'],
                     [{'file_id': 'a', 'doc': None}]):
            with self.subTest(refs=refs):
                with self.assertRaises(ValueError):
                    rule_author.generate_rule(
                        _doc(), user_prompt='提取金额', reference_docs=refs,
                        llm_fn=lambda p, s: _spec([('金额', '借')]))

    def test_precise_mode_unchanged(self):
        result = rule_author.generate_rule(
            _doc(), fields=[{'target': '借方金额', 'description': ''}],
            llm_fn=lambda p, s: _spec([('借方金额', '借')]))
        self.assertEqual(result.meta['mode'], 'precise')
        self.assertNotIn('user_prompt_sha256', result.meta)
        self.assertEqual(result.schema['fields'], [
            {'name': '借方金额', 'type': 'text'}])


if __name__ == '__main__':
    unittest.main()
