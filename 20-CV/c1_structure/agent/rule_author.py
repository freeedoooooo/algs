"""规则生成 Agent（P0）：doc + 目标列名 → v2 规则草稿 + 诊断。

六步生命周期：构造上下文 → 版本化提示词 → LLM 严格解析 → 静态校验 →
内存干跑 → 中间层标准答案对拍。产物是规则草稿，不写 staging、不建版本、
不碰 parse.json；保存由调用方走既有 create_version，人工确认后生效。

llm 可注入（与 build_smart 同构）；Stub 模式不烧 token。
"""
import hashlib
import json

from . import context, llm, validate
from .prompts import rule_author_v1
from .. import config
from ..collect_logic import registry


class GenerationResult:
    """生成产物：spec 草稿 + 诊断 + 置信度信号（不落库）。"""

    def __init__(self, spec, schema, confidence, diagnostics, meta):
        self.spec = spec
        self.schema = schema
        self.confidence = confidence
        self.diagnostics = diagnostics
        self.meta = meta

    def as_dict(self):
        return {'spec': self.spec, 'schema': self.schema,
                'confidence': self.confidence,
                'diagnostics': self.diagnostics, '_agent_meta': self.meta}


def _input_sha(doc, fields, refs):
    payload = {'doc': doc, 'fields': fields, 'refs': refs or {}}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _targets_from_middle(content, file_id):
    """取中间层 confirmed/edited 记录作标准答案；其余状态一律不采信。"""
    doc = content.get_records(file_id)
    out = []
    for f in (doc or {}).get('files') or []:
        for rec in f.get('records') or []:
            review = rec.get('review') or {}
            if review.get('state') in ('confirmed', 'edited'):
                out.append({'index': rec.get('index'),
                            'values': rec.get('values') or {},
                            'original': rec.get('original') or {}})
    return out


def _confidence(diag, cmp):
    """置信度由确定性信号合成，不由 LLM 自报。"""
    acc = cmp.get('field_accuracy')
    coverage = diag.get('anchor_coverage') or 0.0
    if acc is None:
        return round(coverage * 0.6, 4)
    return round(0.6 * acc + 0.4 * coverage, 4)


def generate_rule(doc, fields, refs=None, *, doc_type=None,
                  generation=None, targets=None, content=None,
                  sample_file_id=None, llm_fn=None, stub_fn=None):
    """生成 v2 规则草稿。

    doc          : c1-structure 信封（parse.json 内容）
    fields       : [{target, description}] 目标列名与说明
    refs/generation : 随版本保存的参考来源与生成参数（写进 _agent_meta）
    targets      : 中间层标准答案（可选；不给则只做锚点覆盖干跑）
    content/sample_file_id : 未给 targets 时按 file_id 自动取中间层已确认记录
    llm_fn/stub_fn : 注入，测试用
    """
    fields = [f for f in (fields or [])
              if isinstance(f, dict) and f.get('target')]
    if not fields:
        raise ValueError('目标字段不能为空')
    inp_sha = _input_sha(doc, fields, refs)

    if targets is None and content is not None and sample_file_id:
        targets = _targets_from_middle(content, sample_file_id)

    ctx = context.doc_to_context(doc)
    prompt = rule_author_v1.render(ctx, fields, refs)
    spec_conf = {'prompt_version': rule_author_v1.PROMPT_VERSION,
                 'tool_version': str(len(registry.OPS)),
                 'model': config.LLM_MODEL}
    raw, meta = llm.call_json(prompt, None, llm=llm_fn, stub=stub_fn,
                              spec=spec_conf, stub_fields=fields)
    issues = validate.validate_spec(raw)
    if issues:
        raise llm.LLMSchemaFail('生成规则未通过静态校验：' + '；'.join(issues))

    diag = validate.dry_run(raw, doc)
    if diag.get('error'):
        raise llm.LLMSchemaFail('生成规则干跑失败：' + diag['error'])

    return _finalize(raw, diag, targets, fields, meta, inp_sha,
                     doc_type, sample_file_id)


def _finalize(spec, diag, targets, fields, meta, inp_sha,
              doc_type=None, sample_file_id=None):
    """校验结果组装：对拍 → 警告 → 置信度 → GenerationResult（P0/P0.5 共用）。"""
    cmp = validate.compare_targets(diag['records'], targets or [])
    diag['compare'] = cmp
    diag['warning'] = None
    if cmp.get('targets_n') and not cmp.get('count_match'):
        diag['warning'] = '样例不完整：记录数与已确认样本不一致'
    if diag.get('empty_fields'):
        diag['warning'] = '存在全空字段：' + '、'.join(diag['empty_fields'])

    meta.update({'generator': 'rule_author',
                 'input_sha256': inp_sha,
                 'doc_type': doc_type,
                 'sample_file_id': sample_file_id,
                 'targets_n': cmp.get('targets_n', 0),
                 'temperature': config.LLM_TEMPERATURE})
    spec['_agent_meta'] = meta
    schema = {'fields': [{'name': str(f['target']), 'type': 'text'}
                         for f in fields]}
    return GenerationResult(spec, schema, _confidence(diag, cmp), diag, meta)


def is_acceptable(diag, targets, acc_threshold=0.95, cov_threshold=0.95):
    """确定性达标判定（不由 LLM 自评）。

    有中间层标准答案：记录数一致 + 字段一致率达标 + 锚点覆盖达标；
    无标准答案：仅以锚点覆盖与全空字段判定（ weaker，warning 标注）。
    """
    if diag.get('error') or diag.get('empty_fields'):
        return False
    coverage = diag.get('anchor_coverage') or 0.0
    if coverage < cov_threshold:
        return False
    cmp = diag.get('compare') or {}
    if cmp.get('targets_n'):
        if not cmp.get('count_match'):
            return False
        acc = cmp.get('field_accuracy')
        return acc is not None and acc >= acc_threshold
    return True


def generate_rule_react(doc, fields, refs=None, *, doc_type=None,
                        targets=None, content=None, sample_file_id=None,
                        llm_fn=None, stub_fn=None, max_rounds=6,
                        acc_threshold=0.95, cov_threshold=0.95):
    """受限 ReAct 迭代生成：首轮不达标才进入工具循环（样本触发）。

    P0 一次性路径保持不变；本入口默认不启用，需显式调用或 use_react=True。
    工具白名单封闭：inspect_tables / validate_spec / dry_run / revise_spec。
    """
    from . import react as react_mod

    fields = [f for f in (fields or [])
              if isinstance(f, dict) and f.get('target')]
    if not fields:
        raise ValueError('目标字段不能为空')
    inp_sha = _input_sha(doc, fields, refs)
    if targets is None and content is not None and sample_file_id:
        targets = _targets_from_middle(content, sample_file_id)

    ctx = context.doc_to_context(doc)
    prompt = rule_author_v1.render(ctx, fields, refs)
    spec_conf = {'prompt_version': rule_author_v1.PROMPT_VERSION,
                 'tool_version': str(len(registry.OPS)),
                 'model': config.LLM_MODEL}

    # 首轮：复用 P0 一次性生成（严格解析 + 静态校验 + 干跑）
    raw, meta = llm.call_json(prompt, None, llm=llm_fn, stub=stub_fn,
                              spec=spec_conf, stub_fields=fields)
    if validate.validate_spec(raw):
        raise llm.LLMSchemaFail('生成规则未通过静态校验')
    diag = validate.dry_run(raw, doc)
    if diag.get('error'):
        raise llm.LLMSchemaFail('生成规则干跑失败：' + diag['error'])
    diag['compare'] = validate.compare_targets(diag['records'], targets or [])

    def tool_inspect(args):
        """看候选表列与样例"""
        return {'tables': ctx['tables'], 'text_hint': ctx['text_hint']}

    def tool_validate_spec(args):
        """静态校验指定 spec"""
        return {'issues': validate.validate_spec(args.get('spec') or {})}

    def tool_dry_run(args):
        """内存试跑指定 spec，返回诊断与对拍"""
        spec = args.get('spec') or {}
        d = validate.dry_run(spec, doc)
        d['compare'] = validate.compare_targets(d.get('records') or [],
                                                targets or [])
        return d

    def tool_revise_spec(args):
        """替换当前 spec 草稿，并立即重算诊断（闭环关键：改完即验）"""
        spec = args.get('spec')
        if not isinstance(spec, dict):
            raise llm.LLMSchemaFail('revise_spec 须提供 spec 对象')
        issues = validate.validate_spec(spec)
        if issues:
            raise llm.LLMSchemaFail(
                'revise_spec 的 spec 未通过静态校验：' + '；'.join(issues))
        d = validate.dry_run(spec, doc)
        if d.get('error'):
            return {'spec': spec, 'diag': d, 'revise_error': d['error']}
        d['compare'] = validate.compare_targets(d['records'], targets or [])
        return {'spec': spec, 'diag': d, 'result': spec}

    tools = {'inspect_tables': tool_inspect,
             'validate_spec': tool_validate_spec,
             'dry_run': tool_dry_run,
             'revise_spec': tool_revise_spec}

    def done_check(state, observation):
        d = state.get('diag') or {}
        return is_acceptable(d, targets, acc_threshold, cov_threshold)

    init = {'spec': raw, 'diag': diag, 'result': raw, 'fields': fields}
    loop = react_mod.ReActLoop(tools, done_check, llm_fn, max_rounds)

    if is_acceptable(diag, targets, acc_threshold, cov_threshold):
        meta.update({'react_rounds': 0, 'react_done': True,
                     'react_trace': [], 'react_triggered': False})
        return _finalize(raw, diag, targets, fields, meta, inp_sha,
                         doc_type, sample_file_id)

    result = loop.run('生成达标规则', initial=init)
    final_spec = result.value or init['spec']
    final_diag = validate.dry_run(final_spec, doc)
    meta.update({'react_rounds': result.rounds, 'react_done': result.done,
                 'react_triggered': True, 'react_trace': result.trace})
    return _finalize(final_spec, final_diag, targets, fields, meta, inp_sha,
                     doc_type, sample_file_id)
