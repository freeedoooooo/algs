"""Agent 模型公共层：QoderCN / Qoder Agent SDK + OpenAI 兼容端点 + 严格 JSON。

· PAT 只从 config 读取，不写库、不打印；
· 规则生成使用受限单轮查询，不允许文件或命令副作用；
· 缺配置显式抛 LLMUnconfigured，绝不静默降级；
· call_json 严格解析 + ≤2 次定点修复，llm 可注入供单测/Stub 使用。

模式由 C1_SMART_STUB=stub|live 控制（默认 stub）：
stub 时 call_json 不做网络调用，返回占位对象供联调、不烧 token；
live 时优先走 QoderCN / Qoder Agent SDK，未配置 PAT 时复用 C1_LLM_* OpenAI 兼容接口。
兼容旧值 1/0。
"""
import asyncio
import json
import re
import urllib.error
import urllib.request

from .. import config


class LLLError(Exception):
    """Agent LLM 层异常基类（类型化，便于 API 映射 HTTP 码）。"""


class LLMUnconfigured(LLLError):
    pass


class LLMTimeout(LLLError):
    pass


class LLMBadJSON(LLLError):
    pass


class LLMSchemaFail(LLLError):
    pass


def _strip_fence(text):
    text = str(text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.S)
    return text.strip()


def _load_qoder_sdk():
    module = ('qodercn_agent_sdk' if config.QODER_REGION == 'cn'
              else 'qoder_agent_sdk')
    try:
        return __import__(module)
    except ImportError as exc:
        raise LLMUnconfigured(
            '未安装 {}，请在项目环境执行 '
            'python -m pip install -r requirements.txt'.format(module)) from exc


def _sdk_failure(exc):
    name = type(exc).__name__
    code = getattr(exc, 'code', None)
    exit_code = getattr(exc, 'exit_code', None)
    auth_codes = {'auth_not_configured',
                  'auth_access_token_env_var_not_configured',
                  'auth_service_account_env_var_not_configured'}
    if code in auth_codes or exit_code == 41:
        raise LLMUnconfigured(
            'Qoder Agent SDK 凭据无效或未配置（{}）'.format(name))
    if name in ('CLINotFoundError', 'CLIConnectionError',
                'ProtocolVersionMismatchError',
                'UnsupportedCliCapabilityError'):
        raise LLMUnconfigured(
            'Qoder Agent SDK 运行环境不可用（{}）'.format(name))
    if code == 10408 or name == 'ModelPolicyTimeoutError':
        raise LLMTimeout('Qoder Agent SDK 调用超时（{}）'.format(name))
    raise LLLError('Qoder Agent SDK 调用失败（{}）'.format(name))


def _provider(spec=None):
    spec = spec or {}
    if config.QODER_PERSONAL_ACCESS_TOKEN:
        provider = ('qodercn_agent_sdk' if config.QODER_REGION == 'cn'
                    else 'qoder_agent_sdk')
        return (provider,
                spec.get('model') or config.QODER_MODEL or 'account-default')
    model = spec.get('model') or config.LLM_MODEL
    if config.LLM_BASE_URL and config.LLM_API_KEY and model:
        return 'openai_compatible', model
    return None, (spec.get('model') or config.QODER_MODEL or model
                  or 'account-default')


def raw_call(prompt, spec=None):
    """单次受限模型查询，返回解析后的 dict（不修复、不校验）。"""
    spec = spec or {}
    provider, _ = _provider(spec)
    if provider in ('qoder_agent_sdk', 'qodercn_agent_sdk'):
        return _qoder_call(prompt, spec)
    if provider == 'openai_compatible':
        return _openai_call(prompt, spec)
    raise LLMUnconfigured(
        'Agent 模型未配置：需设置 QODERCN_PERSONAL_ACCESS_TOKEN '
        '（或 QODER_PERSONAL_ACCESS_TOKEN），'
        '或完整配置 C1_LLM_BASE_URL / C1_LLM_API_KEY / C1_LLM_MODEL')


def _qoder_call(prompt, spec):
    token = config.QODER_PERSONAL_ACCESS_TOKEN
    sdk = _load_qoder_sdk()
    model = spec.get('model') or config.QODER_MODEL or None
    options = {
        'auth': sdk.access_token(token),
        'system_prompt': ('你是规则生成器。只根据用户提示返回一个合法 JSON '
                          '对象，不要解释，不要调用工具。'),
        'tools': [],
        'allowed_tools': [],
        'permission_mode': 'dontAsk',
        'max_turns': 1,
        'skills': [],
        'mcp_servers': {},
        'allowed_mcp_server_names': [],
        'strict_mcp_config': True,
        'setting_sources': [],
        'memory': {},
    }
    if model:
        options['model'] = model
    if config.QODER_CLI_PATH:
        options['cli_path'] = config.QODER_CLI_PATH
    if config.QODER_TMP_DIR:
        options['env'] = {'TEMP': config.QODER_TMP_DIR,
                          'TMP': config.QODER_TMP_DIR}

    async def consume():
        stream = sdk.query(prompt=prompt,
                           options=sdk.QoderAgentOptions(**options))
        final_text = ''
        last_text = ''
        result_seen = False
        try:
            async for message in stream:
                if isinstance(message, sdk.AssistantMessage):
                    for block in message.content:
                        if isinstance(block, sdk.TextBlock):
                            last_text = block.text
                        elif isinstance(block, sdk.ToolUseBlock):
                            raise LLLError(
                                'Qoder Agent 尝试调用工具，规则生成已阻止')
                elif isinstance(message, sdk.ResultMessage):
                    result_seen = True
                    if message.subtype != 'success' or message.is_error:
                        code = getattr(message, 'error_code', None)
                        terminal = getattr(message, 'terminal_reason', '') or ''
                        errors = getattr(message, 'errors', None) or []
                        auth_error = any(
                            'access token' in str(item).lower()
                            and any(word in str(item).lower()
                                    for word in ('rejected', 'invalid', 'expired'))
                            for item in errors)
                        if (code == 105 or auth_error or terminal in (
                                'auth_payload_invalid', 'access_token_invalid')):
                            raise LLMUnconfigured(
                                'Qoder Agent 凭据已过期、无效或运行时不可用')
                        if code == 10408:
                            raise LLMTimeout('Qoder Agent 生成超时')
                        raise LLLError(
                            'Qoder Agent 生成失败（subtype={}, reason={}）'.format(
                                message.subtype, terminal or code))
                    final_text = message.result or last_text
            if not result_seen:
                raise LLLError('Qoder Agent 消息流结束但未返回结果')
            if not final_text:
                raise LLLError('Qoder Agent 未返回文本结果')
            return final_text
        finally:
            close = getattr(stream, 'aclose', None)
            if close is not None:
                await close()

    try:
        content = asyncio.run(asyncio.wait_for(
            consume(), timeout=config.QODER_TIMEOUT))
    except asyncio.TimeoutError as exc:
        raise LLMTimeout('Qoder Agent SDK 调用超时') from exc
    except (LLLError, LLMBadJSON):
        raise
    except Exception as exc:
        _sdk_failure(exc)
    try:
        return json.loads(_strip_fence(content))
    except ValueError:
        raise LLMBadJSON('Qoder Agent 返回的不是合法 JSON')


def _openai_call(prompt, spec):
    base = config.LLM_BASE_URL.rstrip('/')
    model = spec.get('model') or config.LLM_MODEL
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': ('你是规则生成器。只根据用户提示返回一个合法 JSON '
                                           '对象，不要解释，不要调用工具。')},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': spec.get('temperature', config.LLM_TEMPERATURE),
    }
    req = urllib.request.Request(
        base + '/chat/completions',
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + config.LLM_API_KEY},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise LLMUnconfigured(
                'OpenAI 兼容模型凭据无效或无权访问（HTTP {}）'.format(exc.code))
        raise LLLError('OpenAI 兼容模型调用失败（HTTP {}）'.format(exc.code))
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, 'reason', exc)
        if isinstance(reason, TimeoutError):
            raise LLMTimeout('OpenAI 兼容模型调用超时') from exc
        raise LLLError('OpenAI 兼容模型网络调用失败（{}）'.format(
            type(reason).__name__))
    except (ValueError, OSError) as exc:
        raise LLLError('OpenAI 兼容模型响应读取失败（{}）'.format(
            type(exc).__name__))
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise LLLError('OpenAI 兼容模型响应缺少 choices[0].message.content')
    if not str(content or '').strip():
        raise LLLError('OpenAI 兼容模型未返回文本结果')
    try:
        return json.loads(_strip_fence(content))
    except ValueError:
        raise LLMBadJSON('OpenAI 兼容模型返回的不是合法 JSON')


def call_json(prompt, schema, *, llm=None, max_repair=2, spec=None,
              stub=None, stub_fields=None):
    """返回 (dict, meta)：严格 JSON 解析，失败时把报错回喂模型定点修复。

    llm 注入签名 llm(prompt, spec) -> dict；stub 注入签名 stub(prompt) -> dict。
    生产路径：SMART_STUB=True（stub）用占位，否则走 raw_call。
    """
    provider, model = _provider(spec)
    if stub is not None or (llm is None and config.SMART_STUB):
        provider, model = 'stub', 'stub'
    elif llm is not None:
        provider, model = 'injected', (spec or {}).get('model') or 'injected'
    meta = {'prompt_version': (spec or {}).get('prompt_version'),
            'provider': provider or 'qoder_agent_sdk',
            'model': model,
            'repairs': 0, 'stub': False}
    if stub is not None:
        meta['stub'] = True
        return stub(prompt), meta
    if llm is None and config.SMART_STUB:
        # Stub 必须返回结构合法的占位 spec，供前端/API 联调走完整链路；
        # pipeline 留空（不取值），干跑标"全空字段"警告，不会误当可用规则。
        # target 跟随用户字段，保证前端填入编辑器的草稿与用户目标一致。
        targets = [str(f.get('target')) for f in (stub_fields or [])
                   if isinstance(f, dict) and f.get('target')] or ['_stub']
        meta['stub'] = True
        return {'spec_version': 2,
                'fields': [{'target': t, 'pipeline': []} for t in targets],
                '_stub': True}, meta

    # 修复是 call_json 的职责，与传输来源无关：注入的 llm 也走同一循环。
    transport = llm if llm is not None else raw_call
    current = prompt
    last_error = None
    for attempt in range(max_repair + 1):
        try:
            obj = transport(current, spec or {})
        except LLMBadJSON as exc:
            last_error = exc
            if attempt >= max_repair:
                break
            current = (prompt + '\n\n上次返回的不是合法 JSON：{}\n'
                       '请只返回合法 JSON，不要解释。'.format(exc))
            meta['repairs'] += 1
            continue
        if not isinstance(obj, dict):
            last_error = LLMBadJSON('Agent 模型返回的 JSON 顶层不是对象')
            if attempt >= max_repair:
                break
            current = (prompt + '\n\n上次返回的 JSON 顶层不是对象，'
                       '请返回一个 JSON 对象。')
            meta['repairs'] += 1
            continue
        return obj, meta
    raise last_error or LLMBadJSON('Agent 模型未能返回合法 JSON')
