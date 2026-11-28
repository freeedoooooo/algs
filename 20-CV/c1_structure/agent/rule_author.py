"""规则生成 Agent（P0）：doc + 逻辑字段/需求 → v2 规则草稿 + 诊断。

六步生命周期：构造上下文 → 版本化提示词 → LLM 严格解析 → 静态校验 →
内存干跑 → 中间层标准答案对拍。产物是规则草稿，不写 staging、不建版本、
不碰 parse.json；单行规则的保存由调用方负责，人工确认后生效。

llm 可注入（与 build_smart 同构）；Stub 模式不烧 token。
"""
import copy
import hashlib
import json
import logging

from . import context, llm, validate
from .prompts import rule_author_v1
from ..collect_logic import registry

logger = logging.getLogger(__name__)


class GenerationResult:
    """生成产物：单条 spec 草稿，或含 rules 列表的多条规则容器（不落库）。"""

    def __init__(self, spec, schema, confidence, diagnostics, meta,
                 name=None, description=None, rules=None):
        self.spec = spec
        self.schema = schema
        self.confidence = confidence
        self.diagnostics = diagnostics
        self.meta = meta
        self.name = name
        self.description = description
        self.rules = rules

    def as_dict(self):
        if self.rules is not None:
            return {'rules': [rule.as_dict() for rule in self.rules],
                    'confidence': self.confidence,
                    'diagnostics': self.diagnostics,
                    '_agent_meta': self.meta}
        out = {'spec': self.spec, 'schema': self.schema,
               'confidence': self.confidence,
               'diagnostics': self.diagnostics, '_agent_meta': self.meta}
        if self.name is not None:
            out['name'] = self.name
        if self.description is not None:
            out['description'] = self.description
        return out


def _input_sha(doc, fields, refs, reference_docs=None, multiple_rules=False):
    payload = {'doc': doc, 'fields': fields, 'refs': refs or {},
               'reference_docs': reference_docs or [],
               'multiple_rules': bool(multiple_rules)}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _targets_from_middle(extract_result_id):
    """按抽取结果读取 confirmed/edited 记录；其余状态一律不采信。"""
    from ..store import content_db

    doc = content_db.get_records(extract_result_id) or {}
    records = doc.get('records')
    if records is None:
        records = [rec for f in doc.get('files') or []
                   for rec in f.get('records') or []]
    out = []
    for rec in records:
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


def _rule_parts(raw, multiple_rules):
    """拆出多条规则契约；单条模式保持旧原始 spec 返回。"""
    if not multiple_rules:
        return [(None, None, raw)]
    rules = raw.get('rules') if isinstance(raw, dict) else None
    if not isinstance(rules, list) or not rules:
        raise llm.LLMSchemaFail('多条规则须返回非空 rules 数组')
    out = []
    for i, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            raise llm.LLMSchemaFail('rules[{}] 须为对象'.format(i))
        name = rule.get('name')
        if not isinstance(name, str) or not name.strip():
            raise llm.LLMSchemaFail('rules[{}].name 须为非空规则名'.format(i))
        spec = rule.get('spec')
        if not isinstance(spec, dict):
            raise llm.LLMSchemaFail('rules[{}].spec 须为对象'.format(i))
        description = rule.get('description')
        if description is not None and not isinstance(description, str):
            raise llm.LLMSchemaFail('rules[{}].description 须为字符串'.format(i))
        out.append((name.strip(), description, spec))
    return out


def _generated_spec_issues(spec):
    """在通用校验上落实生成契约：中文逻辑字段、多表显式记录驱动。"""
    try:
        issues = validate.validate_spec(spec)
    except (AttributeError, TypeError, ValueError):
        issues = ['spec 包含非法结构类型']
    if not isinstance(spec, dict):
        return issues
    fields = spec.get('fields')
    if isinstance(fields, list):
        for i, field in enumerate(fields):
            target = field.get('target') if isinstance(field, dict) else None
            if target and not any('\u4e00' <= char <= '\u9fff'
                                  for char in str(target)):
                issues.append('fields[{}].target 须为中文逻辑字段名'.format(i))
    tables = spec.get('tables') or []
    if isinstance(tables, list) and len(tables) > 1:
        record_sources = [t.get('ref') for t in tables
                          if isinstance(t, dict)
                          and t.get('role') == 'record_source']
        records = spec.get('records') or {}
        source_ref = records.get('source_ref') if isinstance(records, dict) else None
        if not record_sources:
            issues.append('多表规则须显式声明 tables[].role=record_source')
        if not source_ref:
            issues.append('多表规则须显式声明 records.source_ref')
        elif record_sources and source_ref not in record_sources:
            issues.append('records.source_ref 须指向 role=record_source 的表')
    return issues


def _validate_and_dry_run(spec, doc, label='生成规则'):
    issues = _generated_spec_issues(spec)
    if issues:
        raise llm.LLMSchemaFail(label + '未通过静态校验：' + '；'.join(issues))
    diag = validate.dry_run(spec, doc)
    if diag.get('error'):
        raise llm.LLMSchemaFail(label + '干跑失败：' + diag['error'])
    return diag


def _stub_multiple(raw, doc):
    """内置 stub 也遵守多条规则外层契约，返回一条可联调的占位规则。"""
    name = str(((doc or {}).get('file') or {}).get('name') or '生成规则')
    return {'rules': [{'name': name, 'description': 'Stub 占位规则', 'spec': raw}]}


def generate_rule(doc, fields=None, refs=None, *, doc_type=None,
                  generation=None, targets=None,
                  sample_extract_result_id=None, llm_fn=None, stub_fn=None,
                  user_prompt=None, reference_docs=None,
                  multiple_rules=False):
    """生成 v2 规则草稿（精确模式 / 自然语言模式二选一）。

    精确模式：fields=[{target,description}]，用 v1 提示词（用户定字段名）。
    自然语言模式：user_prompt=需求描述，用 v2 提示词，AI 推断中文逻辑字段、
                  字段类型与记录模式；不接收数据库物理列白名单。
    reference_docs 支持 [{file_id,name,doc_type,doc}, ...] 或解析 doc 列表；
    所有参考附件进入提示词，但仅主 doc 参与干跑。multiple_rules=True 时返回
    GenerationResult.rules；默认 False 保持旧单条 GenerationResult。
    """
    fields = [f for f in (fields or [])
              if isinstance(f, dict) and f.get('target')]
    natural = bool(str(user_prompt or '').strip())
    if natural and fields:
        raise ValueError('fields 与 user_prompt 只能二选一')
    if not natural and not fields:
        raise ValueError('须提供 fields（精确模式）或 user_prompt（自然语言模式）')
    # 附件规范化同时校验输入，空列表与未提供等价。
    context.normalize_reference_docs(reference_docs)
    multiple_rules = bool(multiple_rules)
    inp_sha = _input_sha(doc, fields if fields else user_prompt, refs,
                         reference_docs, multiple_rules)

    if targets is None and sample_extract_result_id is not None:
        targets = _targets_from_middle(sample_extract_result_id)

    ctx = context.doc_to_context(doc)
    if natural:
        from .prompts import rule_author_v2
        prompt = rule_author_v2.render(ctx, user_prompt, refs, reference_docs,
                                       multiple_rules=multiple_rules)
        pv = rule_author_v2.PROMPT_VERSION
        stub_targets = [{'target': '占位字段'}]
    else:
        prompt = rule_author_v1.render(ctx, fields, refs)
        pv = rule_author_v1.PROMPT_VERSION
        stub_targets = fields
        extra = []
        reference_text = context.render_reference_docs(reference_docs)
        if reference_text:
            extra.append('参考附件上下文（仅供主文档规则参考）：\n' + reference_text)
        if multiple_rules:
            from .prompts._schema import schema_text
            extra.append('多条规则模式：以上单条 JSON 契约替换为以下契约；'
                         '只返回 rules 数组，每条规则独立完整：\n'
                         + schema_text(multiple_rules=True))
        if extra:
            prompt += '\n\n' + '\n\n'.join(extra)
    spec_conf = {'prompt_version': pv,
                 'tool_version': str(len(registry.OPS)),
                 'multiple_rules': multiple_rules}
    logger.info('规则生成开始：mode=%s sample_extract_result_id=%s',
                'natural' if natural else 'precise', sample_extract_result_id)
    raw, meta = llm.call_json(prompt, None, llm=llm_fn, stub=stub_fn,
                              spec=spec_conf, stub_fields=stub_targets)
    if multiple_rules and meta.get('stub') and raw.get('_stub') \
            and 'rules' not in raw:
        raw = _stub_multiple(raw, doc)
    logger.info('规则校验与干跑开始：mode=%s provider=%s model=%s',
                'natural' if natural else 'precise', meta.get('provider'),
                meta.get('model'))
    parts = _rule_parts(raw, multiple_rules)
    meta['mode'] = 'natural' if natural else 'precise'
    meta['multiple_rules'] = multiple_rules
    if natural:
        meta['user_prompt_sha256'] = hashlib.sha256(
            str(user_prompt).encode('utf-8')).hexdigest()

    if not multiple_rules:
        _, _, spec = parts[0]
        diag = _validate_and_dry_run(spec, doc)
        # 自然语言模式下 fields 由模型产出，schema 从 spec 推导（见 _finalize）
        return _finalize(spec, diag, targets, fields or None, meta, inp_sha,
                         doc_type, sample_extract_result_id)

    results = []
    rule_targets = targets if len(parts) == 1 else None
    for i, (name, description, spec) in enumerate(parts, 1):
        label = '第{}条规则（{}）'.format(i, name)
        diag = _validate_and_dry_run(spec, doc, label)
        results.append(_finalize(
            spec, diag, rule_targets, fields or None, meta, inp_sha, doc_type,
            sample_extract_result_id, name=name, description=description,
            rule_index=i, rules_n=len(parts)))
    aggregate_meta = dict(meta)
    aggregate_meta.update({
        'generator': 'rule_author', 'input_sha256': inp_sha,
        'doc_type': doc_type,
        'sample_extract_result_id': sample_extract_result_id,
        'rules_n': len(results),
    })
    aggregate_diag = {'rules_n': len(results), 'all_valid': True}
    confidence = round(sum(r.confidence for r in results) / len(results), 4)
    return GenerationResult(None, None, confidence, aggregate_diag,
                            aggregate_meta, rules=results)


def _finalize(spec, diag, targets, fields, meta, inp_sha,
              doc_type=None, sample_extract_result_id=None, name=None,
              description=None, rule_index=None, rules_n=None):
    """校验结果组装：对拍 → 警告 → 置信度 → GenerationResult（P0/P0.5 共用）。"""
    cmp = validate.compare_targets(diag['records'], targets or [])
    diag['compare'] = cmp
    diag['warning'] = None
    if cmp.get('targets_n') and not cmp.get('count_match'):
        diag['warning'] = '样例不完整：记录数与已确认样本不一致'
    if diag.get('empty_fields'):
        diag['warning'] = '存在全空字段：' + '、'.join(diag['empty_fields'])

    result_meta = dict(meta)
    result_meta.update({'generator': 'rule_author',
                        'input_sha256': inp_sha,
                        'doc_type': doc_type,
                        'sample_extract_result_id': sample_extract_result_id,
                        'targets_n': cmp.get('targets_n', 0)})
    if name is not None:
        result_meta.update({'name': name, 'description': description})
    if rule_index is not None:
        result_meta.update({'rule_index': rule_index, 'rules_n': rules_n})
    logger.info('规则生成完成：fields=%s records=%s anchor_coverage=%s '
                'field_accuracy=%s confidence=%s',
                len(spec.get('fields') or []), diag.get('records_n'),
                diag.get('anchor_coverage'), cmp.get('field_accuracy'),
                _confidence(diag, cmp))
    spec = copy.deepcopy(spec)
    spec['_agent_meta'] = result_meta
    if fields is None:
        # 自然语言模式：字段名由模型产出，schema 从生成结果推导
        eff = [f for f in (spec.get('fields') or [])
               if isinstance(f, dict) and f.get('target')]
    else:
        eff = fields
    schema_fields = []
    for f in eff:
        field = {'name': str(f['target'])}
        # 自然语言模式的类型契约来自模型输出；精确模式保持既有 text 默认值。
        field['type'] = str(f.get('type') or 'text') if fields is None else 'text'
        schema_fields.append(field)
    schema = {'fields': schema_fields}
    return GenerationResult(spec, schema, _confidence(diag, cmp), diag,
                            result_meta, name=name, description=description)


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
                        targets=None, sample_extract_result_id=None,
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
    if targets is None and sample_extract_result_id is not None:
        targets = _targets_from_middle(sample_extract_result_id)

    ctx = context.doc_to_context(doc)
    prompt = rule_author_v1.render(ctx, fields, refs)
    spec_conf = {'prompt_version': rule_author_v1.PROMPT_VERSION,
                 'tool_version': str(len(registry.OPS))}

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
                         doc_type, sample_extract_result_id)

    result = loop.run('生成达标规则', initial=init)
    final_spec = result.value or init['spec']
    final_diag = validate.dry_run(final_spec, doc)
    meta.update({'react_rounds': result.rounds, 'react_done': result.done,
                 'react_triggered': True, 'react_trace': result.trace})
    return _finalize(final_spec, final_diag, targets, fields, meta, inp_sha,
                     doc_type, sample_extract_result_id)
