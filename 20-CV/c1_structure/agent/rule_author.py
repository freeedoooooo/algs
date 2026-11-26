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


def generate_rule(doc, fields=None, refs=None, *, doc_type=None,
                  generation=None, targets=None, content=None,
                  sample_file_id=None, llm_fn=None, stub_fn=None,
                  user_prompt=None, column_candidates=None):
    """生成 v2 规则草稿（精确模式 / 自然语言模式二选一）。

    精确模式：fields=[{target,description}]，用 v1 提示词（用户定字段名）。
    自然语言模式：user_prompt=需求描述，用 v2 提示词，AI 推断字段与模式；
                  column_candidates 非空时 target 必须取自其中（参考业务表）。
    """
    fields = [f for f in (fields or [])
              if isinstance(f, dict) and f.get('target')]
    natural = bool(str(user_prompt or '').strip())
    if natural and fields:
        raise ValueError('fields 与 user_prompt 只能二选一')
    if not natural and not fields:
        raise ValueError('须提供 fields（精确模式）或 user_prompt（自然语言模式）')
    inp_sha = _input_sha(doc, fields if fields else user_prompt, refs)

    if targets is None and content is not None and sample_file_id:
        targets = _targets_from_middle(content, sample_file_id)

    ctx = context.doc_to_context(doc)
    if natural:
        from .prompts import rule_author_v2
        prompt = rule_author_v2.render(ctx, user_prompt, refs,
                                        column_candidates)
        pv = rule_author_v2.PROMPT_VERSION
        stub_targets = None
    else:
        prompt = rule_author_v1.render(ctx, fields, refs)
        pv = rule_author_v1.PROMPT_VERSION
        stub_targets = fields
    spec_conf = {'prompt_version': pv,
                 'tool_version': str(len(registry.OPS)),
                 'model': config.QODER_MODEL or None}
    raw, meta = llm.call_json(prompt, None, llm=llm_fn, stub=stub_fn,
                              spec=spec_conf, stub_fields=stub_targets)
    issues = validate.validate_spec(raw)
    if issues:
        raise llm.LLMSchemaFail('生成规则未通过静态校验：' + '；'.join(issues))
    if natural:
        cand = [str(c) for c in (column_candidates or []) if str(c or '').strip()]
        if cand:
            got = [str(f.get('target')) for f in raw.get('fields') or []]
            bad = [t for t in got if t not in cand]
            if bad:
                raise llm.LLMSchemaFail(
                    '生成字段名不在参考业务表列内：' + '、'.join(bad))

    diag = validate.dry_run(raw, doc)
    if diag.get('error'):
        raise llm.LLMSchemaFail('生成规则干跑失败：' + diag['error'])

    meta['mode'] = 'natural' if natural else 'precise'
    if natural:
        meta['user_prompt_sha256'] = hashlib.sha256(
            str(user_prompt).encode('utf-8')).hexdigest()
    # 自然语言模式下 fields 由模型产出，schema 从 spec 推导（见 _finalize）
    return _finalize(raw, diag, targets, fields or None, meta, inp_sha,
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
                 'targets_n': cmp.get('targets_n', 0)})
    spec['_agent_meta'] = meta
    if fields is None:
        # 自然语言模式：字段名由模型产出，schema 从生成结果推导
        eff = [f for f in (spec.get('fields') or [])
               if isinstance(f, dict) and f.get('target')]
    else:
        eff = fields
    schema = {'fields': [{'name': str(f['target']), 'type': 'text'}
                         for f in eff]}
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
                 'model': config.QODER_MODEL or None}

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
