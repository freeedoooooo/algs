"""P0-① agent 公共层：LLM 注入/Stub、上下文压缩、静态校验与干跑对拍。"""
import asyncio
import unittest
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
        import c1_structure.config as cfg
        old = cfg.QODER_PERSONAL_ACCESS_TOKEN
        try:
            cfg.QODER_PERSONAL_ACCESS_TOKEN = ''
            with self.assertRaises(llm.LLMUnconfigured):
                llm.raw_call('p')
        finally:
            cfg.QODER_PERSONAL_ACCESS_TOKEN = old

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
