"""P0-① agent 公共层：LLM 注入/Stub、上下文压缩、静态校验与干跑对拍。"""
import asyncio
import copy
import json
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

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


class _TextBlock:
    def __init__(self, text):
        self.text = text


class _ToolUseBlock:
    pass


class _AssistantMessage:
    def __init__(self, content):
        self.content = content


class _ResultMessage:
    def __init__(self, result=None, *, subtype='success', is_error=False,
                 error_code=None, terminal_reason=None, errors=None):
        self.result = result
        self.subtype = subtype
        self.is_error = is_error
        self.error_code = error_code
        self.terminal_reason = terminal_reason
        self.errors = errors


class _Options:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _HTTPResponse:
    def __init__(self, content):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.content


def _model_response(text):
    payload = {'choices': [{'message': {'content': text}}]}
    return _HTTPResponse(json.dumps(payload).encode('utf-8'))


def _fake_sdk(batches):
    calls = []

    def query(*, prompt, options):
        calls.append((prompt, options))
        batch = batches.pop(0)

        async def stream():
            for message in batch:
                yield message

        return stream()

    return SimpleNamespace(
        AssistantMessage=_AssistantMessage,
        TextBlock=_TextBlock,
        ToolUseBlock=_ToolUseBlock,
        ResultMessage=_ResultMessage,
        QoderAgentOptions=_Options,
        access_token=lambda token: ('token', token),
        query=query), calls


class LLMTest(unittest.TestCase):
    def test_injected_llm_no_network(self):
        obj, meta = llm.call_json(
            'p', {}, llm=lambda p, s: {'spec_version': 2})
        self.assertEqual(obj, {'spec_version': 2})
        self.assertFalse(meta['stub'])
        self.assertEqual(meta['provider'], 'injected')
        self.assertEqual(meta['model'], 'injected')

    def test_stub_no_network(self):
        obj, meta = llm.call_json('p', {}, stub=lambda p: {'stub': 1})
        self.assertEqual(obj, {'stub': 1})
        self.assertTrue(meta['stub'])
        self.assertEqual(meta['provider'], 'stub')
        self.assertEqual(meta['model'], 'stub')

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
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                LLM_BASE_URL='', LLM_API_KEY='', LLM_MODEL=''), \
                mock.patch.object(llm.urllib.request, 'urlopen') as urlopen:
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('p')
        urlopen.assert_not_called()

    def test_qoder_preferred_when_both_providers_configured(self):
        sdk, calls = _fake_sdk([[_ResultMessage('{"ok": true}')]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.object(llm, '_openai_call') as openai_call, \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='qoder-test-model', QODER_CLI_PATH='',
                    QODER_TIMEOUT=2, LLM_BASE_URL='https://llm.example/v1',
                    LLM_API_KEY='llm-test-key', LLM_MODEL='llm-test-model'):
            self.assertEqual(llm.raw_call('prompt'), {'ok': True})
        openai_call.assert_not_called()
        self.assertEqual(len(calls), 1)

    def test_openai_fallback_success_and_metadata(self):
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                QODER_MODEL='qoder-model-must-not-leak',
                LLM_BASE_URL='https://llm.example/v1/',
                LLM_API_KEY='llm-test-key', LLM_MODEL='llm-test-model',
                LLM_TIMEOUT=3, LLM_TEMPERATURE=0.2, SMART_STUB=False), \
                mock.patch.object(llm.urllib.request, 'urlopen',
                                  return_value=_model_response(
                                      '```json\n{"ok": true}\n```')) as urlopen:
            obj, meta = llm.call_json('prompt', {})
        self.assertEqual(obj, {'ok': True})
        self.assertEqual(meta['provider'], 'openai_compatible')
        self.assertEqual(meta['model'], 'llm-test-model')
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, 'https://llm.example/v1/chat/completions')
        self.assertEqual(req.get_method(), 'POST')
        self.assertEqual(req.get_header('Authorization'),
                         'Bearer llm-test-key')
        body = json.loads(req.data.decode('utf-8'))
        self.assertEqual(body['model'], 'llm-test-model')
        self.assertEqual(body['temperature'], 0.2)
        self.assertEqual(body['messages'][0]['role'], 'system')
        self.assertEqual(body['messages'][1], {'role': 'user',
                                               'content': 'prompt'})
        self.assertNotIn('tools', body)

    def test_openai_fallback_repairs_bad_json(self):
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                LLM_BASE_URL='https://llm.example/v1', LLM_API_KEY='test-key',
                LLM_MODEL='test-model', LLM_TIMEOUT=2, SMART_STUB=False), \
                mock.patch.object(
                    llm.urllib.request, 'urlopen',
                    side_effect=[_model_response('not-json'),
                                 _model_response('{"ok": true}')]) as urlopen:
            obj, meta = llm.call_json('base', {}, max_repair=1)
        self.assertEqual(obj, {'ok': True})
        self.assertEqual(meta['repairs'], 1)
        self.assertEqual(meta['provider'], 'openai_compatible')
        self.assertEqual(urlopen.call_count, 2)
        repair_body = json.loads(urlopen.call_args.args[0].data.decode('utf-8'))
        self.assertIn('上次返回的不是合法 JSON',
                      repair_body['messages'][1]['content'])

    def test_openai_fallback_requires_complete_config(self):
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                LLM_BASE_URL='https://llm.example/v1', LLM_API_KEY='test-key',
                LLM_MODEL=''), \
                mock.patch.object(llm.urllib.request, 'urlopen') as urlopen:
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('prompt')
        urlopen.assert_not_called()

    def test_openai_auth_failure_maps_unconfigured(self):
        error = urllib.error.HTTPError(
            'https://llm.example/v1/chat/completions', 401, 'Unauthorized',
            None, None)
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                LLM_BASE_URL='https://llm.example/v1', LLM_API_KEY='test-key',
                LLM_MODEL='test-model', LLM_TIMEOUT=2), \
                mock.patch.object(llm.urllib.request, 'urlopen',
                                  side_effect=error):
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('prompt')

    def test_openai_timeout_maps_to_typed_error(self):
        with mock.patch.multiple(
                llm.config, QODER_PERSONAL_ACCESS_TOKEN='',
                LLM_BASE_URL='https://llm.example/v1', LLM_API_KEY='test-key',
                LLM_MODEL='test-model', LLM_TIMEOUT=2), \
                mock.patch.object(llm.urllib.request, 'urlopen',
                                  side_effect=TimeoutError()):
            with self.assertRaises(llm.LLMTimeout):
                llm.raw_call('prompt')

    def test_qoder_success_and_restricted_options(self):
        sdk, calls = _fake_sdk([
            [_ResultMessage('```json\n{"ok": true}\n```')]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='qoder-test-model',
                    QODER_CLI_PATH='C:/qodercli.exe', QODER_TIMEOUT=2,
                    QODER_TMP_DIR='D:/qoder-tmp'):
            self.assertEqual(llm.raw_call('prompt'), {'ok': True})
        opts = calls[0][1].kwargs
        self.assertEqual(opts['auth'], ('token', 'pt-test'))
        self.assertEqual(opts['model'], 'qoder-test-model')
        self.assertEqual(opts['cli_path'], 'C:/qodercli.exe')
        self.assertEqual(opts['tools'], [])
        self.assertEqual(opts['allowed_tools'], [])
        self.assertEqual(opts['permission_mode'], 'dontAsk')
        self.assertEqual(opts['max_turns'], 1)
        self.assertEqual(opts['skills'], [])
        self.assertEqual(opts['mcp_servers'], {})
        self.assertEqual(opts['allowed_mcp_server_names'], [])
        self.assertTrue(opts['strict_mcp_config'])
        self.assertEqual(opts['setting_sources'], [])
        self.assertEqual(opts['memory'], {})
        self.assertEqual(opts['env'], {'TEMP': 'D:/qoder-tmp',
                                      'TMP': 'D:/qoder-tmp'})

    def test_qoder_tool_use_is_blocked(self):
        sdk, _ = _fake_sdk([[
            _AssistantMessage([_ToolUseBlock()]),
            _ResultMessage('{"ok": true}')]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=2):
            with self.assertRaises(llm.LLLError):
                llm.raw_call('prompt')

    def test_qoder_auth_result_maps_unconfigured(self):
        sdk, _ = _fake_sdk([[
            _ResultMessage(subtype='error_during_execution', is_error=True,
                           error_code=105)]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=2):
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('prompt')

    def test_qoder_rejected_token_result_maps_unconfigured(self):
        sdk, _ = _fake_sdk([[
            _ResultMessage(subtype='error_during_execution', is_error=True,
                           terminal_reason='access_token_invalid',
                           errors=['The provided access token was rejected by the API'])]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=2,
                    QODER_TMP_DIR=''):
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('prompt')

    def test_qoder_failed_result_maps_error(self):
        sdk, _ = _fake_sdk([[
            _ResultMessage(subtype='error_during_execution', is_error=True,
                           error_code=500)]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=2):
            with self.assertRaises(llm.LLLError):
                llm.raw_call('prompt')

    def test_qoder_bad_json_uses_repair_loop(self):
        sdk, calls = _fake_sdk([
            [_ResultMessage('not-json')],
            [_ResultMessage('{"ok": true}')]])
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=2,
                    SMART_STUB=False):
            obj, meta = llm.call_json('base', {}, max_repair=1)
        self.assertEqual(obj, {'ok': True})
        self.assertEqual(meta['repairs'], 1)
        self.assertEqual(meta['provider'], 'qoder_agent_sdk')
        self.assertEqual(meta['model'], 'account-default')
        self.assertEqual(len(calls), 2)
        self.assertIn('上次返回的不是合法 JSON', calls[1][0])

    def test_qoder_sdk_auth_exception_maps_unconfigured(self):
        class AuthError(Exception):
            code = 'auth_not_configured'

        sdk, _ = _fake_sdk([])

        def query(*, prompt, options):
            async def stream():
                raise AuthError()
                yield

            return stream()

        sdk.query = query
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=2):
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('prompt')

    def test_qoder_timeout_maps_to_typed_error(self):
        sdk, _ = _fake_sdk([])

        def query(*, prompt, options):
            async def stream():
                await asyncio.sleep(1)
                yield _ResultMessage('{"ok": true}')

            return stream()

        sdk.query = query
        with mock.patch.object(llm, '_load_qoder_sdk', return_value=sdk), \
                mock.patch.multiple(
                    llm.config, QODER_PERSONAL_ACCESS_TOKEN='pt-test',
                    QODER_MODEL='', QODER_CLI_PATH='', QODER_TIMEOUT=0.01):
            with self.assertRaises(llm.LLMTimeout):
                llm.raw_call('prompt')


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


class DocumentMapTest(unittest.TestCase):
    def _spatial_doc(self):
        rows = [['行{}'.format(i)] for i in range(10)]
        cells = [['金额']] + [[[100, 200 + i * 20, 800, 215 + i * 20]]
                              for i in range(10)]
        return {'file': {'name': 'map.pdf', 'kind': 'pdf'},
                'pages': [{'index': 1, 'size': [1000, 1000],
                           'rectified_size': [2000, 2000], 'space': 'source',
                           'route': 'model',
                           'blocks': [{'role': 'title', 'bbox': [100, 50, 500, 100],
                                       'text': '对账单'}],
                           'texts': [{'text': '表后说明',
                                      'box': [[100, 500], [900, 500],
                                              [900, 550], [100, 550]]}],
                           'tables': [{'headers': ['金额'], 'rows': rows,
                                       'cells': cells,
                                       'coord': {'space': 'source'}}]}],
                'stitched_tables': []}

    def test_spatial_map_and_neighbors(self):
        ctx = context.doc_to_context(self._spatial_doc())
        table = ctx['tables'][0]
        self.assertEqual(table['position']['norm'], [0.1, 0.2, 0.8, 0.395])
        self.assertEqual(table['neighbors']['above'], 'p1.b0')
        self.assertEqual(table['neighbors']['below'], 'p1.x0')
        page = ctx['document_map']['pages'][0]
        self.assertEqual(page['regions'][0]['ref'], 'p1.b0')
        self.assertEqual(page['regions'][1]['ref'], 'p1.t0')
        self.assertIn('文档地图', context.render_context(ctx))

    def test_representative_first_middle_last_rows(self):
        ctx = context.doc_to_context(self._spatial_doc())
        table = ctx['tables'][0]
        self.assertEqual(table['sample_rows'], [0, 4, 9])
        self.assertEqual([r[0] for r in table['samples']], ['行0', '行4', '行9'])

    def test_rectified_table_uses_rectified_size(self):
        doc = self._spatial_doc()
        doc['pages'][0]['tables'][0]['coord']['space'] = 'rectified'
        position = context.doc_to_context(doc)['tables'][0]['position']
        self.assertEqual(position['space'], 'rectified')
        self.assertEqual(position['norm'], [0.05, 0.1, 0.4, 0.1975])

    def test_empty_page_and_stitched_table(self):
        doc = self._spatial_doc()
        doc['pages'].append({'index': 2, 'size': [800, 600], 'space': 'source',
                             'texts': [], 'blocks': [], 'tables': []})
        doc['stitched_tables'] = [{'headers': ['跨页'], 'rows': [['值']],
                                   'cells': [[[10, 20, 100, 40]]],
                                   'coord': {'space': 'source'},
                                   'parts': [{'page': 2, 'tbl': 0}]}]
        ctx = context.doc_to_context(doc)
        self.assertEqual(ctx['document_map']['pages'][1]['index'], 2)
        stitched = next(t for t in ctx['tables'] if t['scope'] == 'stitched')
        self.assertEqual(stitched['position']['norm'], [0.0125, 0.0333, 0.125, 0.0667])

    def test_large_document_budget_and_input_unchanged(self):
        doc = self._spatial_doc()
        doc['pages'].extend(
            {'index': i, 'size': [1000, 1000], 'space': 'source',
             'texts': [], 'blocks': [], 'tables': []} for i in range(2, 31))
        before = copy.deepcopy(doc)
        ctx = context.doc_to_context(doc, budget=2500)
        self.assertTrue(ctx['truncated'])
        self.assertGreater(ctx['document_map']['omitted_pages'], 0)
        self.assertLess(len(ctx['document_map']['pages']), 30)
        self.assertEqual(doc, before)
        self.assertEqual(doc['pages'][0]['tables'][0]['rows'],
                         before['pages'][0]['tables'][0]['rows'])


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
