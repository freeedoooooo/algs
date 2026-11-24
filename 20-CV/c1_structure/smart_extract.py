"""smart_extract — 智能抽取（spec_version=3）。

与 collect_logic 的纯函数规则引擎平级：完全跳过算子管道，把 parse.json 里的
文本行/表格格序列化给大模型，要求返回“值 + 证据原文”。证据必须匹配回原文，
匹配不到的值一律留空（宁可漏抽不错抽）。输出仍是既有 records 信封。

本模块做 I/O 且非确定，不进 collect.build；由 service.run_extract 分流调用。
凭据只走 config 的环境变量，不写库、不打印。
"""
import json
import re
import unicodedata
import urllib.error
import urllib.request

from . import collect, config
from .collect_logic._common import box_to_bbox, make_anchor


def _norm(text):
    """证据匹配用：NFKC + 去所有空白，避免全角冒号/空格造成假不匹配。"""
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC',
                                                   str(text or '')))


def _candidates(doc, scope='all', page=None):
    """可回锚的原文片段：页内 texts + 表格格；每项带同款锚点 dict。"""
    out = []
    pages = doc.get('pages') or []
    for pg in pages:
        idx = pg.get('index')
        if scope == 'page' and page is not None and idx != page:
            continue
        space = pg.get('space')
        for item in pg.get('texts') or []:
            text = str(item.get('text') or '')
            if not text.strip():
                continue
            out.append({'text': text,
                        'anchor': make_anchor(idx, space,
                                              box_to_bbox(item.get('box')),
                                              text)})
        for ti, t in enumerate(pg.get('tables') or []):
            cells = t.get('cells') or []
            for r, row in enumerate(t.get('rows') or []):
                for c, value in enumerate(row):
                    text = str(value or '')
                    if not text.strip():
                        continue
                    out.append({'text': text,
                                'anchor': collect._anchor(
                                    'page', t, ti, cells, r, c, text, idx)})
            for c, head in enumerate(t.get('headers') or []):
                text = str(head or '')
                if text.strip() and _norm(text) not in {
                        _norm(x['text']) for x in out}:
                    out.append({'text': text,
                                'anchor': collect._anchor(
                                    'page', t, ti, cells, 0, c, text, idx)})
    return out


def _prompt(fields, candidates, template=None):
    lines = ['[{}] {}'.format(c['anchor']['page'], c['text'])
             for c in candidates[:1200]]
    context = '\n'.join(lines)[:24000]
    targets = '\n'.join('- {}: {}'.format(
        f.get('target'), f.get('description') or '') for f in fields)
    rule = template or (
        '你是文档结构化抽取助手。只返回 JSON，不要解释。\n'
        '对每个目标字段返回对象：{"target":字段名,"value":值,"evidence":值在原文中的片段}。\n'
        'evidence 必须原样取自下面的解析结果；找不到证据时 evidence 返回空字符串。\n'
        '若目标字段在原文中不存在，value 返回空字符串。')
    return '{}\n\n目标字段：\n{}\n\n解析结果：\n{}'.format(rule, targets, context)


def _call_llm(prompt, spec):
    """OpenAI 兼容 chat/completions；缺配置显式失败，不静默降级。"""
    base = spec.get('base_url') or config.LLM_BASE_URL
    key = config.LLM_API_KEY
    model = spec.get('model') or config.LLM_MODEL
    if not (base and key and model):
        raise RuntimeError('智能抽取未配置：需设置 C1_LLM_BASE_URL / '
                           'C1_LLM_API_KEY / C1_LLM_MODEL')
    body = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': spec.get('temperature', config.LLM_TEMPERATURE),
    }
    req = urllib.request.Request(
        base + '/chat/completions',
        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + key},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise RuntimeError('智能抽取模型调用失败：{}'.format(type(exc).__name__))
    try:
        content = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise RuntimeError('智能抽取模型响应缺少 choices[0].message.content')
    text = str(content).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.S)
    try:
        return json.loads(text)
    except ValueError:
        raise RuntimeError('智能抽取模型返回的不是合法 JSON')


def _items(payload):
    """归一化模型输出：优先 fields 数组，其次 {target: value} 对象。"""
    out = {}
    rows = payload.get('fields') if isinstance(payload, dict) else payload
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get('target'):
                out[str(row['target'])] = (row.get('value'), row.get('evidence'))
    elif isinstance(payload, dict):
        for target, value in payload.items():
            if isinstance(value, dict):
                out[str(target)] = (value.get('value'), value.get('evidence'))
            else:
                out[str(target)] = (value, None)
    return out


def _match_anchor(evidence, candidates):
    """证据文本回锚：精确 > 片段包含；匹配不到返回 None。"""
    needle = _norm(evidence)
    if len(needle) < 3:
        return None
    for c in candidates:
        if _norm(c['text']) == needle:
            return c['anchor']
    for c in candidates:
        hay = _norm(c['text'])
        if len(hay) >= 3 and (needle in hay or hay in needle):
            return c['anchor']
    return None


def build_smart(doc, tpl=None, llm=None):
    """spec_version=3 入口：c1-structure 信封 → records（每文件一条）。

    llm 仅用于测试注入；生产路径调用 OpenAI 兼容端点。
    """
    if config.SMART_STUB:
        # 占位链路：不访问模型、不构造提示词，供界面与暂存链路联调。
        fixed = {'field1': '智能抽取结果1'}
        return [{
            'index': 0,
            'values': dict(fixed),
            'original': dict(fixed),
            'lineage': {'field1': []},
            'review': {'state': 'pending', 'at': None},
        }]

    spec = ((tpl or {}).get('mapping_json') or {})
    smart = spec.get('smart') or spec
    fields = [f for f in (spec.get('fields') or [])
              if isinstance(f, dict) and f.get('target')]
    if not fields:
        return []
    scope = (spec.get('records') or {}).get('scope') or 'all'
    page = (spec.get('records') or {}).get('page')
    candidates = _candidates(doc, scope, page)
    prompt = _prompt(fields, candidates, smart.get('prompt_template'))
    payload = llm(prompt, smart) if llm is not None else _call_llm(prompt, smart)
    items = _items(payload)

    values, original, lineage = {}, {}, {}
    for field in fields:
        target = str(field['target'])
        value, evidence = items.get(target, ('', None))
        value = '' if value is None else value
        anchor = _match_anchor(evidence, candidates) if evidence else None
        if anchor is None:
            value = ''  # 无证据不写值
        values[target] = value
        original[target] = value
        lineage[target] = [anchor] if anchor else []
    return [{
        'index': 0,
        'values': values,
        'original': original,
        'lineage': lineage,
        'review': {'state': 'pending', 'at': None},
    }]
