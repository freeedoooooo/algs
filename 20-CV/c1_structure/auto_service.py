"""自然语言自动处理编排：解析 → 规则复用/生成 → 多结果抽取 → 单结果入库规划。"""
import os
import threading
import time
import traceback

from . import config, service, collect
from .store import catalog, content, content_db, load_planner
from . import tasklog
from .store.errors import BadRequest, Conflict


def launch(paths, params, warns, ctx, intent, *, rule_generator=None):
    """登记资料并启动单文档自动处理线程。"""
    intent = load_planner.normalize_intent(intent)
    description = str(intent.get('description') or intent.get('prompt') or '').strip()
    if not description:
        raise BadRequest('自动处理需要自然语言描述')
    for f in ctx:
        fid = f['file_id']
        catalog.set_state(fid, 'pending', '')
        catalog.set_params(fid, params)
        load_planner.save_intent(fid, intent)
        f['state'] = 'pending'
    doc_id = ctx[0]['file_id']
    label = 'doc_{}'.format(doc_id)
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=service._on_log)
    task_ctx = {'file_id': doc_id, 'files': ctx, 'created_at': service._now(),
                'in_scratch': os.path.dirname(paths[0])}
    with service.LOCK:
        service.STATE.update(
            running=True, ready=False, error=None, steps=[], cases=[],
            started=time.time(), elapsed=0,
            params={k: v for k, v in params.items() if not k.startswith('_')},
            warnings=warns, logs=[], progress=0, stage='auto',
            log_file=label + '.log', rule=None, file_id=doc_id,
            task_id=doc_id, test_mode=False, extract_results=[])
    log.stage('auto', '资料 {} · 自动处理开始'.format(doc_id))
    threading.Thread(target=_run,
                     args=(paths, params, log, task_ctx, intent, rule_generator),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'file_id': doc_id,
            'task_id': doc_id, 'warnings': warns}


def _find_reusable_rule(doc, intent, log):
    from .agent import rule_reuse
    description = str(intent.get('description') or intent.get('prompt') or '')
    try:
        candidate = rule_reuse.best_candidate(
            description, catalog.list_rules(), doc,
            output_fields=intent.get('output_fields'))
        if not candidate:
            return None
        resolved = service.resolve_rule(candidate['id'])
    except Exception as exc:
        log.warn('rule', '规则复用检查失败，改为生成新规则：{}'.format(exc))
        return None
    log.info('rule', '复用规则 {}（相似度 {}%）'.format(
        resolved.get('name') or candidate.get('id'),
        round(candidate['reuse_score'] * 100)))
    return resolved


def _generated_rules(result):
    if hasattr(result, 'rules'):
        return list(result.rules or [])
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and isinstance(result.get('rules'), list):
        return result['rules']
    return [result]


def _rule_parts(item, index, doc_id, description, reference_doc_ids=None,
                used_names=None):
    spec = item.spec if hasattr(item, 'spec') else item.get('spec') if isinstance(item, dict) else item
    schema = item.schema if hasattr(item, 'schema') else item.get('schema') if isinstance(item, dict) else None
    if not schema:
        schema = {'fields': [
            {'name': f.get('target'), 'type': f.get('type') or 'text'}
            for f in (spec or {}).get('fields') or []
            if isinstance(f, dict) and f.get('target')]}
    name = item.get('name') if isinstance(item, dict) else getattr(item, 'name', None)
    item_description = item.get('description') if isinstance(item, dict) \
        else getattr(item, 'description', None)
    name = str(name or '').strip() or '自动规则-{}-{}'.format(
        doc_id, int(time.time()) + index)
    used_names = used_names if used_names is not None else set()
    base, suffix = name, 2
    while name in used_names:
        name = '{}-{}'.format(base, suffix)
        suffix += 1
    used_names.add(name)
    return {'name': name,
            'description': str(item_description or description)[:200],
            'output_schema_json': schema,
            'extraction_spec_json': spec,
            'reference_doc_ids_json': reference_doc_ids or [doc_id],
            'validation_report_json': item.get('diagnostics')
            if isinstance(item, dict) else getattr(item, 'diagnostics', None)}


def _extract_one(doc_id, doc, tpl, log):
    result_id = catalog.ensure_extract_result(
        doc_id, tpl['rule_id'], service._rule_snapshot(tpl), status='running')
    recs = service.extract_records(doc, tpl)
    spec = tpl.get('extraction_spec_json') or {}
    if spec.get('spec_version') == 2:
        from . import smart_extract
        recs, fallback = smart_extract.build_row_fallback(doc, tpl, recs)
        if fallback.get('attempted'):
            log.info('extract', '逐行兜底：尝试{}行，补全{}个字段，失败{}行'.format(
                fallback['attempted'], fallback['filled'], len(fallback['failed'])))
    content_db.save_records(result_id, recs)
    catalog.finish_extract_result(result_id, status='ready')
    return result_id, recs


def _intent_for_rule(intent, index):
    targets = intent.get('targets')
    if isinstance(targets, list) and index < len(targets) and isinstance(targets[index], dict):
        return load_planner.normalize_intent(dict(intent, **targets[index]))
    return intent


def _run(paths, params, log, task_ctx, intent, rule_generator):
    doc_id = task_ctx['file_id']
    try:
        service.task_batch(paths, params, log, task_ctx, finalize=False)
        f = catalog.get_file(doc_id)
        if f is None or f['state'] != 'to_extract':
            raise RuntimeError('解析未完成，自动处理停止')
        doc = content.get_extract(doc_id)
        if doc is None:
            raise RuntimeError('解析产物缺失，自动处理停止')
        with service.LOCK:
            service.STATE['progress'] = 45
        log.stage('parse', '解析完成，已生成页面、文本与表格产物',
                  event='parse_complete')

        reused = _find_reusable_rule(doc, intent, log)
        if reused is not None:
            rules = [reused]
        else:
            reference_docs = []
            reference_ids = []
            for item in task_ctx.get('files') or []:
                ref_id = item.get('file_id')
                if ref_id is None:
                    continue
                ref_doc = content.get_extract(ref_id)
                if ref_doc is None:
                    log.warn('rule', '参考附件 {} 无解析产物，已跳过'.format(ref_id))
                    continue
                reference_ids.append(ref_id)
                if ref_id != doc_id:
                    reference_docs.append({
                        'file_id': ref_id, 'name': item.get('name'),
                        'doc_type': item.get('doc_type'), 'doc': ref_doc})
            if rule_generator is None:
                from .agent import rule_author
                log.stage('rule', '开始根据自然语言生成抽取规则')
                generated = rule_author.generate_rule(
                    doc,
                    user_prompt=intent.get('description') or intent.get('prompt'),
                    refs={'file_id': doc_id,
                          'reference_doc_ids': reference_ids},
                    doc_type=f.get('doc_type'), reference_docs=reference_docs,
                    multiple_rules=True)
            else:
                generated = rule_generator(doc, intent)
            used_names = {r['name'] for r in catalog.list_rules()}
            rules = []
            for index, item in enumerate(_generated_rules(generated)):
                parts = _rule_parts(
                    item, index, doc_id,
                    intent.get('description') or intent.get('prompt') or '',
                    reference_ids or None, used_names)
                spec = parts['extraction_spec_json'] or {}
                if not spec or spec.get('_stub') or not (spec.get('fields') or []):
                    log.warn('rule', '第{}条规则为空，已跳过'.format(index + 1))
                    continue
                rule_id = catalog.create_rule(**parts)
                rules.append(service.resolve_rule(rule_id))
        if not rules:
            plan = {'status': 'rule_empty',
                    'message': '规则生成为空占位；自动处理需要 live 模式或有效规则',
                    'target': None, 'mapping': None,
                    'recommendations': [], 'warnings': []}
            load_planner.save_intent(doc_id, plan)
            catalog.set_state(doc_id, 'to_review', '自动规则未生成有效字段')
            _finish(plan['status'], None, plan['message'])
            return

        summaries = []
        for index, tpl in enumerate(rules, 1):
            log.stage('extract', '开始按规则 {} 抽取中文字段'.format(tpl['name']))
            result_id, recs = _extract_one(doc_id, doc, tpl, log)
            plan = load_planner.plan_for_extract_result(
                result_id,
                datasource_code=_intent_for_rule(intent, index - 1).get('datasource_code'),
                table_intent=_intent_for_rule(intent, index - 1))
            summaries.append({'extract_result_id': result_id,
                              'rule_id': tpl['rule_id'], 'rule_name': tpl['name'],
                              'records_n': len(recs), 'plan': plan})
            log.ok('extract', '抽取完成：{} 条记录，规则 {}；规划 {}'.format(
                len(recs), tpl['name'], plan['status']),
                event='extract_complete')
        catalog.set_state(doc_id, 'to_review', None)
        with service.LOCK:
            service.STATE['progress'] = 90
            service.STATE['extract_results'] = summaries
        ready = sum(1 for item in summaries if item['plan']['status'] == 'ready')
        stage = 'ready' if ready == len(summaries) else 'results_ready'
        message = ('已生成{}个抽取结果；聊天写库须逐条显式确认'.format(len(summaries))
                   if ready == len(summaries) else
                   '已生成{}个抽取结果；请先选择目标表或补齐字段映射'.format(len(summaries)))
        _finish(stage, None, message)
    except Exception as exc:
        log.error('error', '自动处理失败：{}'.format(exc))
        log.error('error', traceback.format_exc(limit=3).strip())
        try:
            catalog.set_state(doc_id, 'failed', str(exc))
        except Exception as store_exc:
            log.warn('store', '资料状态写入失败：{}'.format(store_exc))
        _finish('error', str(exc), str(exc))


def _target_table(datasource_code, target_table, fields):
    metadata = [dict(field, field_name=field.get('field_name') or field.get('name'))
                for field in fields or []]
    existing = next((t for t in catalog.list_load_tables(datasource_code)
                     if t['target_table'] == target_table), None)
    if existing:
        if not existing.get('fields') and metadata:
            catalog.update_load_table(existing['id'], fields=metadata)
            existing = catalog.get_load_table(existing['id'])
        return existing
    return catalog.get_load_table(catalog.create_load_table(
        datasource_code, target_table, metadata))


def apply_plan(extract_result_id, intent):
    """用户在聊天中明确确认后，创建/更新绑定并执行单结果入库。"""
    if not isinstance(intent, dict) or intent.get('confirmed') is not True:
        raise Conflict('请明确确认入库规划和字段映射')
    plan = load_planner.plan_for_extract_result(
        extract_result_id, datasource_code=intent.get('datasource_code'),
        table_intent=intent)
    if plan['status'] != 'ready':
        raise Conflict(plan['message'])
    mapping = plan['mapping']
    target = plan['target']
    field_map = mapping.get('field_map') or {}
    if not field_map:
        raise Conflict('请至少为一个中文字段选择数据库列后再入库')
    result = catalog.get_extract_result(extract_result_id)
    if result is None:
        raise Conflict('抽取结果不存在')
    lt = _target_table(target['datasource_code'], target['table'],
                       mapping.get('available_columns') or [])
    write_mode = mapping.get('write_mode') or 'insert'
    business_keys = mapping.get('business_key') or []
    binding = catalog.get_binding(extract_result_id=extract_result_id)
    if binding is None:
        binding_id = catalog.create_binding(
            extract_result_id, lt['code'], field_map, write_mode, business_keys)
    else:
        if binding['status'] in ('confirmed', 'running', 'ready'):
            raise Conflict('该结果已有确认或执行中的入库绑定')
        catalog.update_binding(binding['id'], table_code=lt['code'],
                               field_map=field_map, write_mode=write_mode,
                               business_keys=business_keys)
        binding_id = binding['id']
    records = (content_db.get_records(extract_result_id) or {}).get('records') or []
    indexes = [r['index'] for r in records
               if (r.get('review') or {}).get('state') in ('pending', 'edited')]
    if indexes:
        content_db.set_review(extract_result_id, indexes, 'confirmed')
    catalog.confirm_binding(binding_id)
    return service.launch_load(extract_result_id, background=True)


def _finish(stage, error, message):
    with service.LOCK:
        service.STATE.update(running=False, ready=error is None, error=error,
                             elapsed=round(time.time()
                                           - (service.STATE['started']
                                              or time.time()), 1),
                             progress=100, stage=stage)
    if message:
        service.step(message, level='info' if error is None else 'error',
                     stage=stage)
