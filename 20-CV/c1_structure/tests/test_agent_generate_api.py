import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from c1_structure import app, auto_service
from c1_structure.store.errors import BadRequest


class Request:
    def __init__(self, body):
        self.body = body

    async def json(self):
        return self.body


class GenerateRuleApiTests(unittest.TestCase):
    def test_multiple_references_and_result_sample_reach_generator(self):
        docs = {1: {'file': {'name': '主表.pdf'}},
                2: {'file': {'name': '参考甲.pdf'}},
                3: {'file': {'name': '参考乙.csv'}}}
        files = {
            1: {'name': '主表.pdf', 'doc_type': 'pdf'},
            2: {'name': '参考甲.pdf', 'doc_type': 'pdf'},
            3: {'name': '参考乙.csv', 'doc_type': 'csv'},
        }
        content = SimpleNamespace(get_extract=Mock(side_effect=docs.get))
        catalog = SimpleNamespace(
            get_file=Mock(side_effect=files.get),
            get_extract_result=Mock(return_value={'id': 9}))
        generated = SimpleNamespace(
            schema={'fields': [{'name': '金额'}]},
            diagnostics={'records_n': 2}, rules=None,
            confidence=0.9, meta={'mode': 'natural', 'rules_n': 1},
            as_dict=Mock(return_value={'spec': {'spec_version': 2}}))
        generator = Mock(return_value=generated)
        agent = SimpleNamespace(generate_rule=generator)
        log = Mock()
        modules = {'store.content': content, 'store.catalog': catalog,
                   'agent.rule_author': agent,
                   'tasklog': SimpleNamespace(TaskLog=Mock(return_value=log))}
        with patch.object(app, '_load', side_effect=modules.__getitem__):
            out = asyncio.run(app.api_agent_generate_rule(Request({
                'file_id': 1, 'reference_doc_ids': [2, 3, 2],
                'prompt': '提取金额', 'sample_extract_result_id': 9,
                'multiple_rules': False})))
        args, kwargs = generator.call_args
        self.assertIs(args[0], docs[1])
        self.assertEqual({'file_id': 1, 'reference_doc_ids': [1, 2, 3]},
                         args[2])
        self.assertEqual([2, 3], [r['file_id'] for r in
                                  kwargs['reference_docs']])
        self.assertEqual(9, kwargs['sample_extract_result_id'])
        self.assertFalse(kwargs['multiple_rules'])
        self.assertNotIn('content', kwargs)
        self.assertNotIn('sample_file_id', kwargs)
        self.assertEqual([1, 2, 3], out['reference_doc_ids_json'])
        self.assertIs(generated.diagnostics, out['validation_report_json'])

    def test_unparsed_reference_stops_before_generation(self):
        content = SimpleNamespace(get_extract=Mock(return_value=None))
        catalog = SimpleNamespace(get_file=Mock(return_value={'name': 'a.pdf'}))
        generator = Mock()
        modules = {'store.content': content, 'store.catalog': catalog,
                   'agent.rule_author': SimpleNamespace(generate_rule=generator)}
        with patch.object(app, '_load', side_effect=modules.__getitem__):
            with self.assertRaisesRegex(Exception, '请先解析'):
                asyncio.run(app.api_agent_generate_rule(Request({
                    'file_id': 1, 'prompt': '提取金额'})))
        generator.assert_not_called()

    def test_invalid_reference_ids_are_rejected(self):
        for value in (True, 0, -1, '2'):
            with self.subTest(value=value):
                with patch.object(app, '_json_body', return_value={
                        'file_id': 1, 'reference_doc_ids': [value],
                        'prompt': '提取金额'}), \
                        patch('fastapi.concurrency.run_in_threadpool') as run:
                    with self.assertRaises(BadRequest):
                        asyncio.run(app.api_agent_generate_rule(object()))
                    run.assert_not_called()


class AutoGenerationIntegrationTests(unittest.TestCase):
    def test_automatic_generation_receives_all_parsed_references(self):
        docs = {1: {'pages': []}, 2: {'pages': [{'index': 2}]}}
        files = {1: {'name': '主表.pdf', 'state': 'to_extract', 'doc_type': 'pdf'},
                 2: {'name': '参考.pdf', 'state': 'to_extract', 'doc_type': 'pdf'}}
        spec = {'spec_version': 2, 'fields': [
            {'target': '金额', 'pipeline': []}]}
        generated = SimpleNamespace(
            spec=spec, schema={'fields': [{'name': '金额', 'type': 'text'}]})
        generator = Mock(return_value=generated)
        intent = {'description': '提取金额'}
        task_ctx = {'file_id': 1, 'files': [
            {'file_id': 1, 'name': '主表.pdf', 'doc_type': 'pdf'},
            {'file_id': 2, 'name': '参考.pdf', 'doc_type': 'pdf'}]}
        plan = {'status': 'waiting_target', 'message': '待选表'}
        patches = [
            patch.object(auto_service.service, 'task_batch'),
            patch.object(auto_service.catalog, 'get_file', side_effect=files.get),
            patch.object(auto_service.content, 'get_extract', side_effect=docs.get),
            patch.object(auto_service, '_find_reusable_rule', return_value=None),
            patch('c1_structure.agent.rule_author.generate_rule', generator),
            patch.object(auto_service.catalog, 'list_rules', return_value=[]),
            patch.object(auto_service.catalog, 'create_rule', return_value=7),
            patch.object(auto_service.service, 'resolve_rule', return_value={
                'rule_id': 7, 'name': '金额规则', 'extraction_spec_json': spec}),
            patch.object(auto_service, '_extract_one', return_value=(31, [])),
            patch.object(auto_service.load_planner, 'plan_for_extract_result',
                         return_value=plan),
            patch.object(auto_service.catalog, 'set_state'),
            patch.object(auto_service, '_finish'),
            patch.dict(auto_service.service.STATE,
                       {'progress': 0, 'extract_results': [], 'started': 1},
                       clear=True),
        ]
        for patcher in patches:
            patcher.start()
        self.addCleanup(lambda: [patcher.stop() for patcher in reversed(patches)])
        auto_service._run(['主表.pdf', '参考.pdf'], {}, Mock(), task_ctx,
                          intent, None)
        args, kwargs = generator.call_args
        self.assertIs(args[0], docs[1])
        self.assertEqual({'file_id': 1, 'reference_doc_ids': [1, 2]},
                         kwargs['refs'])
        self.assertEqual([2], [r['file_id'] for r in
                               kwargs['reference_docs']])
        self.assertTrue(kwargs['multiple_rules'])
        auto_service._extract_one.assert_called_once()


if __name__ == '__main__':
    unittest.main()
