"""公共 LLM 客户端：OpenAI 兼容 /chat/completions，零新依赖。

复用 smart_extract._call_llm 的传输方式并抽出为公共层：
· 凭据只从 config 读环境变量，不写库、不打印；
· 缺配置显式抛 LLMUnconfigured，绝不静默降级；
· call_json 严格解析 + ≤2 次定点修复，llm 可注入供单测/Stub 使用。

模式由 C1_SMART_STUB=stub|live 控制（默认 stub）：
stub 时 call_json 不做网络调用，返回占位对象供联调、不烧 token；
live 时走配置模型。兼容旧值 1/0。
"""
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


def raw_call(prompt, spec=None):
    """单次 chat/completions，返回解析后的 dict（不修复、不校验）。"""
    spec = spec or {}
    base = spec.get('base_url') or config.LLM_BASE_URL
    key = config.LLM_API_KEY
    model = spec.get('model') or config.LLM_MODEL
    if not (base and key and model):
        raise LLMUnconfigured(
            'Agent 模型未配置：需设置 C1_LLM_BASE_URL / '
            'C1_LLM_API_KEY / C1_LLM_MODEL')
    body = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': spec.get('temperature', config.LLM_TEMPERATURE),
    }
    req = urllib.request.Request(
        base.rstrip('/') + '/chat/completions',
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + key},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', 'replace')[:200]
        except Exception:
            pass
        if exc.code in (401, 403):
            raise LLMUnconfigured(
                'Agent 模型凭据无效（HTTP {}）：{}'.format(exc.code, detail))
        raise LLLError('Agent 模型 HTTP {}：{}'.format(exc.code, detail))
    except urllib.error.URLError as exc:
        raise LLMTimeout('Agent 模型调用失败：{}'.format(type(exc).__name__))
    except (ValueError, OSError) as exc:
        raise LLLError('Agent 模型响应解析失败：{}'.format(type(exc).__name__))
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise LLLError('Agent 模型响应缺少 choices[0].message.content')
    try:
        return json.loads(_strip_fence(content))
    except ValueError:
        raise LLMBadJSON('Agent 模型返回的不是合法 JSON')


def call_json(prompt, schema, *, llm=None, max_repair=2, spec=None,
              stub=None, stub_fields=None):
    """返回 (dict, meta)：严格 JSON 解析，失败时把报错回喂模型定点修复。

    llm 注入签名 llm(prompt, spec) -> dict；stub 注入签名 stub(prompt) -> dict。
    生产路径：SMART_STUB=True（stub）用占位，否则走 raw_call。
    """
    meta = {'prompt_version': (spec or {}).get('prompt_version'),
            'model': (spec or {}).get('model') or config.LLM_MODEL,
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
