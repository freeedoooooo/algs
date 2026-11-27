"""自然语言自动处理编排：解析 → 生成规则 → 抽取 → 推荐/映射 → 自动入库。"""
import os
import threading
import time
import traceback

from . import config, service, collect
from .store import catalog, content, load_planner
from . import tasklog
from .store.errors import BadRequest, Conflict


def launch(paths, params, warns, ctx, intent, *, rule_generator=None):
    """登记资料并启动单文件自动处理线程。"""
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
    file_id = ctx[0]['file_id']
    label = 'file_{}'.format(file_id)
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=service._on_log)
    task_ctx = {'file_id': file_id, 'files': ctx, 'created_at': service._now(),
                'in_scratch': os.path.dirname(paths[0])}
    with service.LOCK:
        service.STATE.update(
            running=True, ready=False, error=None, steps=[], cases=[],
            started=time.time(), elapsed=0,
            params={k: v for k, v in params.items() if not k.startswith('_')},
            warnings=warns, logs=[], progress=0, stage='auto',
            log_file=label + '.log', rule=None, file_id=file_id,
            task_id=file_id, test_mode=False)
    log.stage('auto', '资料 {} · 自动处理开始'.format(file_id))
    threading.Thread(target=_run,
                     args=(paths, params, log, task_ctx, intent, rule_generator),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'file_id': file_id,
            'task_id': file_id, 'warnings': warns}


def _find_reusable_rule(doc, intent, log):
    from .agent import rule_reuse, validate
    description = str(intent.get('description') or intent.get('prompt') or '')
    try:
        candidate = rule_reuse.best_candidate(description, catalog.list_rules())
        if not candidate:
            return None
        version_id = candidate['current_version_id']
        tpl = catalog.get_rule_version(version_id)
        if not tpl or validate.validate_spec(tpl.get('mapping_json')):
            return None
        diag = validate.dry_run(tpl.get('mapping_json') or {}, doc)
        resolved = service.resolve_rule(version_id) \
            if rule_reuse.acceptable(diag) else None
    except Exception as exc:
        log.warn('rule', '规则复用检查失败，改为生成新规则：{}'.format(exc))
        return None
    if resolved is None:
        log.info('rule', '复用候选 {} 未通过当前文档干跑，改为生成新规则'.format(
            candidate.get('name') or version_id))
        return None
    log.info('rule', '复用规则 {} · v{}（相似度 {}%）'.format(
        tpl.get('name') or version_id, tpl.get('version'),
        round(candidate['reuse_score'] * 100)))
    return resolved


def _run(paths, params, log, task_ctx, intent, rule_generator):
    file_id = task_ctx['file_id']
    try:
        service.task_batch(paths, params, log, task_ctx, finalize=False)
        f = catalog.get_file(file_id)
        if f is None or f['state'] != 'to_extract':
            raise RuntimeError('解析未完成，自动处理停止')
        doc = content.get_extract(file_id)
        if doc is None:
            raise RuntimeError('解析产物缺失，自动处理停止')

        tpl = _find_reusable_rule(doc, intent, log)
        if tpl is None:
            refs = {'target_table': intent.get('target_table') or intent.get('table'),
                    'datasource_id': intent.get('datasource_id')}
            if rule_generator is None:
                from .agent import rule_author
                result = rule_author.generate_rule(
                    doc, user_prompt=intent.get('description') or intent.get('prompt'),
                    refs=refs, doc_type=f.get('doc_type'), content=content,
                    sample_file_id=file_id)
            else:
                result = rule_generator(doc, intent)

            spec = result.spec if hasattr(result, 'spec') else result
            schema = result.schema if hasattr(result, 'schema') else {
                'fields': [{'name': f.get('target'), 'type': f.get('type') or 'text'}
                           for f in (spec or {}).get('fields') or []
                           if isinstance(f, dict) and f.get('target')]}
            if not spec or spec.get('_stub') or not (spec.get('fields') or []):
                plan = {'status': 'rule_empty',
                        'message': '规则生成为空占位；自动处理需要 live 模式或有效规则',
                        'target': None, 'mapping': None,
                        'recommendations': [], 'warnings': []}
                load_planner.save_plan(file_id, plan)
                catalog.set_state(file_id, 'to_review',
                                  '自动规则未生成有效字段，请检查模型配置')
                _finish(plan['status'], None, '自动规则为空，已停止')
                return

            description = str(intent.get('description') or intent.get('prompt') or '')
            rule_name = '自动规则-{}-{}'.format(file_id, int(time.time()))
            version_id = catalog.create_rule(
                rule_name, description=description[:200], schema=schema,
                mapping=spec, transform={})
            tpl = service.resolve_rule(version_id)
        recs = service.extract_records(doc, tpl)
        if (tpl.get('mapping_json') or {}).get('spec_version') == 2:
            from . import smart_extract
            recs, fallback = smart_extract.build_row_fallback(doc, tpl, recs)
            if fallback.get('attempted'):
                log.info('extract', 'v3 逐行兜底：尝试{}行，补全{}个字段，失败{}行'.format(
                    fallback['attempted'], fallback['filled'],
                    len(fallback['failed'])))
                for item in fallback['failed']:
                    log.warn('extract', '第{}行兜底失败（{}），保留 v2 结果'.format(
                        item.get('index'), item.get('reason')))
        catalog.clear_load_logs(file_id)
        content.save_records(collect.build_records_doc(
            doc, recs, task_id=file_id, task_file_id=file_id, file_id=file_id,
            rule={'name': tpl['name'], 'version': tpl['version']}))
        catalog.set_rule(file_id, tpl['version_id'])
        catalog.set_state(file_id, 'to_review', None)

        plan = load_planner.plan_for_file(file_id, intent)
        if plan['status'] == 'ready' and intent.get('auto_load', True):
            create_and_load(file_id, plan, background=False)
            return
        if plan['status'] == 'ready':
            _finish(plan['status'], None,
                    '规划已就绪，等待你确认后写入数据库')
            return
        _finish(plan['status'], None, plan['message'])
    except Exception as exc:
        log.error('error', '自动处理失败：{}'.format(exc))
        log.error('error', traceback.format_exc(limit=3).strip())
        try:
            catalog.set_state(file_id, 'failed', str(exc))
        except Exception as store_exc:
            log.warn('store', '资料状态写入失败：{}'.format(store_exc))
        _finish('error', str(exc), str(exc))


def create_and_load(file_id, plan, *, background=True):
    if not isinstance(plan, dict) or plan.get('status') != 'ready':
        raise Conflict('入库规划尚未就绪，不能自动入库')
    if not (plan.get('confirmed') or
            (load_planner.get_intent(file_id) or {}).get('auto_load', True)):
        raise Conflict('请先确认入库规划')
    mapping = plan.get('mapping') or {}
    target = plan.get('target') or {}
    if not mapping.get('complete') or not target.get('table'):
        raise Conflict('字段映射不完整，不能自动入库')
    f = catalog.get_file(file_id)
    if f is None:
        raise Conflict('资料不存在')
    if f.get('state') not in ('to_review', 'to_load'):
        raise Conflict('资料状态为 {}，不能执行入库'.format(f.get('state')))
    if f.get('load_table_id'):
        bound = catalog.get_load_table(f['load_table_id'])
        if (not bound or bound.get('datasource_id') != target.get('datasource_id')
                or bound.get('target_table') != target.get('table')):
            raise Conflict('资料已绑定其他入库目标，不能自动改写')
        return service.launch_load(file_id, auto=True, background=background)
    tpl = service.resolve_rule(f['rule_version_id']) \
        if f.get('rule_version_id') else None
    snapshot = load_planner.snapshot_from_mapping(mapping)
    business_keys = set(mapping.get('business_key') or [])
    fields = [{'rule_field': name, 'target_column': column,
               'is_business_key': column in business_keys}
              for name, column in (mapping.get('field_map') or {}).items()]
    load_table_id = catalog.create_load_table(
        target['datasource_id'], (tpl or {}).get('rule_id'),
        target['table'], mapping.get('write_mode') or 'insert', fields,
        rule_version_id=(tpl or {}).get('version_id'), snapshot=snapshot)
    return service.launch_load(
        file_id, {'datasource_id': target['datasource_id'],
                  'load_table_id': load_table_id},
        auto=True, background=background)


def apply_plan(file_id, intent):
    mapping = intent.get('mapping') if isinstance(intent, dict) else None
    if isinstance(mapping, dict) and not intent.get('field_map'):
        intent = dict(intent, field_map=mapping.get('field_map') or {})
    plan = load_planner.plan_for_file(file_id, intent)
    if plan['status'] != 'ready':
        raise Conflict(plan['message'])
    plan['confirmed'] = True
    return create_and_load(file_id, plan, background=True)


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
