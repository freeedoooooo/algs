"""
c1_structure/service.py — 运行引擎与共享运行状态（编排层，自 app.py 抽出）。

模型：一条资料记录 = 一次运行（单文件，file_id 为唯一主键）；无 task 概念。
app.py 只留 HTTP 路由与请求校验；上传校验通过后调 launch() 起后台线程跑
task_batch（解析 → 报告 → collect 记录入库 → 产物 ingest 入 BLOB）。
STATE/LOCK 是单资料串行的运行状态（模型单例非线程安全），/api/status、
/api/logs、/healthz 经 app 读取这里。DB 必选：写失败显式 failed，不降级。
"""
import os
import re
import time
import hashlib
import shutil
import tempfile
import importlib
import logging
import threading
import traceback

from . import config
from .logging_config import log_level

logger = logging.getLogger(__name__)


def _load(name):
    return importlib.import_module(__package__ + '.' + name)


# 单资料串行：模型单例不是线程安全的，也没必要并发加载第二份大模型
STATE = {
    'running': False, 'ready': False, 'error': None,
    'steps': [], 'cases': [],
    'started': None, 'elapsed': 0,
    'params': {}, 'warnings': [],
    'logs': [], 'progress': 0, 'stage': '',
    'log_file': None,
    'rule': None, 'file_id': None, 'task_id': None,
    'extract_results': [],
}
LOCK = threading.Lock()


def step(msg, level='info', stage='batch'):
    """兼容旧调用：纯文本 steps 仍保留，同时生成一条结构化日志。"""
    with LOCK:
        STATE['steps'].append(msg)
        STATE['logs'].append({
            't': round(time.time() - (STATE['started'] or time.time()), 2),
            'ms': 0, 'level': level, 'stage': stage, 'msg': msg,
        })
    logger.log(log_level(level), '[%s] %s', stage, msg)


def _on_log(row):
    """TaskLog 每条日志同步进 STATE，页面轮询 /api/status 即可看到。"""
    with LOCK:
        STATE['logs'].append(row)
        STATE['stage'] = row['stage']


def safe_name(name):
    """只替换 Windows 文件名非法字符，保留中文与空格。"""
    name = os.path.basename(name or 'upload.bin')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip()
    return name[:120] or 'upload.bin'


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _kind_of(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in config.PDF_EXTS:
        return 'pdf'
    return 'text' if ext in config.TEXT_EXTS else 'image'


def register_file(name, data):
    """登记新行（不去重）；sha 仍算供检索/ETag，dedup 恒 False。
    DB 必选：失败上抛（调用方回 503）。"""
    sha = hashlib.sha256(data).hexdigest()
    fid, dedup = _load('store.catalog').register_file(
        name, _kind_of(name), len(data), sha, data)
    return {'file_id': fid, 'sha256': sha, 'dedup': dedup}


def _passthrough_rule():
    """内存默认：原始透传（空 mapping → collect.passthrough）。"""
    return {'name': '原始透传', 'rule_id': None,
            'output_schema_json': {'fields': []},
            'extraction_spec_json': {}, 'transform_json': None}


def resolve_rule(rule_id=None):
    """按规则 ID 读取当前定义；规则没有版本，显式指定找不到时报错。"""
    if rule_id is None:
        return _passthrough_rule()
    catalog = _load('store.catalog')
    rule = catalog.get_rule(rule_id)
    if not rule:
        raise RuntimeError('抽取规则不存在')
    return {'name': rule['name'], 'rule_id': rule['id'],
            'output_schema_json': rule['output_schema_json'],
            'extraction_spec_json': rule['extraction_spec_json'],
            'transform_json': None}


def resolve_rule_snapshot(snapshot):
    """从抽取结果快照恢复执行模板，不依赖规则后续是否被修改。"""
    snapshot = snapshot or {}
    spec = snapshot.get('extraction_spec') or snapshot.get('extraction_spec_json')
    schema = snapshot.get('output_schema') or snapshot.get('output_schema_json')
    return {'name': snapshot.get('name') or '规则快照',
            'rule_id': snapshot.get('rule_id'),
            'output_schema_json': schema or {},
            'extraction_spec_json': spec or {}, 'transform_json': None}


def launch(paths, params, warns, ctx, tpl=None):
    """起解析（DB 必选，失败上抛 503）→ 建日志 → 重置 STATE → 起后台线程。

    ctx 每项须已由 register_file 登记并带 file_id；一条资料=一次运行。
    抽取规则在「执行抽取」时绑定（方案A），解析阶段不绑。
    """
    catalog = _load('store.catalog')
    for f in ctx:
        fid = f['file_id']
        catalog.set_state(fid, 'pending', '')
        catalog.set_params(fid, params)
        f['state'] = 'pending'
    primary = ctx[0]['file_id'] if ctx else None
    label = 'file_{}'.format(primary)
    tasklog = _load('tasklog')
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=_on_log)
    task_ctx = {'file_id': primary, 'rule': tpl,
                'files': ctx, 'created_at': _now()}
    if paths:
        task_ctx['in_scratch'] = os.path.dirname(paths[0])
    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], started=time.time(), elapsed=0,
                     params={k: v for k, v in params.items()
                             if not k.startswith('_')}, warnings=warns,
                     logs=[], progress=0, stage='batch',
                     log_file=label + '.log',
                     rule=tpl, file_id=primary, task_id=primary,
                     test_mode=False, extract_results=[])
    log.stage('batch', '资料 {} · 收到 {} 个文件'.format(primary, len(paths)))
    log.info('params', '生效参数：{}'.format(
        ', '.join('{}={}'.format(k, v) for k, v in params.items()
                  if not k.startswith('_'))))
    for w in warns:
        log.warn('params', w)
    threading.Thread(target=task_batch, args=(paths, params, log, task_ctx),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'file_id': primary,
            'task_id': primary, 'warnings': warns}


# 阶段 → 单文件内的进度占比（只增不减）
_STAGE_FRAC = {
    ('split', 'info'): 0.05,
    ('render', 'info'): 0.15,
    ('model', 'info'): 0.30,
    ('model', 'ok'): 0.60,
    ('model', 'warn'): 0.60,
    ('table', 'info'): 0.45,
    ('ocr', 'info'): 0.70,
    ('ocr', 'ok'): 0.90,
    ('table', 'ok'): 0.95,
}


def _ingest_case(file_id, case_abs, prefix=''):
    """scratch 目录全量产物入 c1_parse_artifact（管线零改动）。"""
    artifact = _load('store.artifact')
    for root, _, files in os.walk(case_abs):
        for fn in files:
            if fn.endswith('.tmp'):
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, case_abs).replace(os.sep, '/')
            with open(p, 'rb') as f:
                artifact.save(file_id, prefix + rel, f.read())


def rmtree_retry(path, tries=6, delay=0.3):
    for k in range(tries):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            if k == tries - 1:
                shutil.rmtree(path, ignore_errors=True)
            else:
                time.sleep(delay)


def task_batch(paths, params=None, log=None, task_ctx=None, finalize=True):
    """后台线程（仅解析）：逐个解析 → raw/ + parse.json → 对照报告
    → 产物 ingest 入 BLOB → 资料置 to_extract；抽取由 run_extract 另行触发。
    DB 必选：写失败显式 failed；scratch 跑完清尽。"""
    task_ctx = task_ctx or {'file_id': None,
                            'rule': resolve_rule(),
                            'files': [{'name': os.path.basename(p), 'path': p}
                                      for p in paths],
                            'created_at': _now()}
    catalog = _load('store.catalog')
    preserve_state = bool(task_ctx.get('preserve_state'))
    artifact_prefix = task_ctx.get('artifact_prefix') or ''

    def db(fid, state, error=None):
        # DB 必选：目录状态写失败上抛 → 整批显式 failed，不降级
        if fid is None or preserve_state:
            return
        catalog.set_state(fid, state, error)

    try:
        def progress(v):
            with LOCK:
                STATE['progress'] = v

        log.stage('load', '加载解析流水线（首次会导入 cv2 / pdfplumber）…')
        progress(1)
        pipeline = _load('pipeline')
        report_mod = _load('parse_report.builder')
        total = len(paths)
        for i, path in enumerate(paths, 1):
            name = os.path.basename(path)
            fc = next((f for f in task_ctx['files']
                       if f.get('name') == name or f.get('path') == path),
                      {})
            fid = fc.get('file_id')
            log.stage('case', '[{}/{}] 开始处理 {}'.format(i, total, name))
            progress(int((i - 1) / total * 100))
            case_abs = fc.get('scratch') or tempfile.mkdtemp(
                prefix='case_', dir=config.TMP_WORK)
            fc['scratch'] = case_abs
            os.makedirs(case_abs, exist_ok=True)
            frac = [0.0]

            def emit(level, stage, msg, _i=i, _frac=frac, **kw):
                f = _STAGE_FRAC.get((stage, level))
                if f is not None and f > _frac[0]:
                    _frac[0] = f
                    with LOCK:
                        STATE['progress'] = int((_i - 1 + f) / total * 100)
                log.emit(level, stage, msg, **kw)

            if fid is not None:
                db(fid, 'parsing', None)
            rec = pipeline.parse_one(path, case_abs, params, emit=emit)
            pages = rec.get('pages') or []
            tot_lines = sum((p.get('stats') or {}).get('lines', 0)
                            for p in pages)
            tot_tables = sum(len(p.get('tables') or []) for p in pages)
            routes = '/'.join(sorted({p.get('route', '-') for p in pages}))
            log.ok('case', '识别 {} 行文字 · 表格 {} 张 · 路线 {} · {} 页{}'.format(
                tot_lines, tot_tables, routes, len(pages),
                ' · 跨页合并 {} 张'.format(len(rec.get('stitched_tables') or []))
                if rec.get('stitched_tables') else ''), case=name)
            report_mod.build([rec],
                             os.path.join(case_abs, config.PARSE_REPORT_NAME),
                             params=params)
            # 解析止步：产物先入 BLOB 再置 to_extract（状态不先于内容）
            if fid is not None:
                _ingest_case(fid, case_abs, artifact_prefix)
                db(fid, 'to_extract', None)
            fc['state'] = 'loaded' if preserve_state else 'to_extract'
            rmtree_retry(case_abs)
            fc.pop('scratch', None)
            progress(int(i / total * 100))
        prim = task_ctx.get('file_id')
        if prim is not None:
            db(prim, 'to_extract', None)
        if finalize:
            with LOCK:
                STATE.update(running=False, ready=True,
                             cases=[{'file': f['name'],
                                     'file_id': f.get('file_id'),
                                     'state': f.get('state')}
                                    for f in task_ctx['files']],
                             elapsed=round(time.time()
                                           - (STATE['started'] or time.time()), 1),
                             progress=100, stage='done')
        log.ok('done', '解析完成 {} 个文件（{}），耗时 {}s'.format(
            total, '测试产物已保存，正式状态未变' if preserve_state else '待抽取',
            STATE['elapsed']))
    except Exception as e:
        if log:
            log.error('error', '出错：' + str(e))
            log.error('error', traceback.format_exc(limit=3).strip())
        try:
            db(task_ctx.get('file_id'), 'failed', str(e))
        except Exception as e2:
            if log:
                log.warn('store', '资料状态写入失败：{}'.format(e2))
        if finalize:
            with LOCK:
                STATE.update(running=False, ready=False, error=str(e),
                             stage='error')
        if not log:
            logger.exception('解析失败：file_id=%s', task_ctx.get('file_id'))
    finally:
        for f in task_ctx.get('files') or []:
            if f.get('scratch'):
                rmtree_retry(f['scratch'])
        if task_ctx.get('in_scratch'):
            rmtree_retry(task_ctx['in_scratch'])


# ---- 抽取引擎（与解析解耦）：parse.json 纯投影 → staging 三表 ----

def extract_records(doc, tpl):
    """规则当前定义或结果快照 → 记录列表；保持纯编排边界。"""
    spec = tpl.get('extraction_spec_json') or {}
    if spec.get('spec_version') == 3:
        return _load('smart_extract').build_smart(doc, tpl)
    return _load('collect').build(doc, tpl)


def _rule_snapshot(tpl):
    return {'name': tpl.get('name'), 'rule_id': tpl.get('rule_id'),
            'output_schema': tpl.get('output_schema_json') or {},
            'extraction_spec': tpl.get('extraction_spec_json') or {}}


def run_extract(doc_id, force=False, rule_id=None, extract_result_id=None):
    """执行一条规则并覆盖该文档对应的当前抽取结果。"""
    catalog = _load('store.catalog')
    content_db = _load('store.content_db')
    content = _load('store.content')
    errors = _load('store.errors')
    if STATE['running']:
        raise errors.Conflict('已有任务正在处理，请等待其完成')
    f = catalog.get_file(doc_id)
    if f is None:
        raise errors.NotFound('资料不存在')
    if f['state'] == 'parsing':
        raise errors.Conflict('资料解析中，暂不能抽取')
    if extract_result_id is not None:
        current = catalog.get_extract_result(extract_result_id)
        if not current or current['doc_id'] != doc_id:
            raise errors.NotFound('抽取结果不存在')
        if rule_id is not None and rule_id != current['rule_id']:
            raise errors.BadRequest('rule_id 与抽取结果不一致')
        tpl = resolve_rule_snapshot(current['rule_snapshot_json'])
        rule_id = current['rule_id']
        exists = bool(content_db.gate_counts(extract_result_id)['records_n'])
    else:
        if not isinstance(rule_id, int) or isinstance(rule_id, bool) or rule_id <= 0:
            raise errors.BadRequest('请选择抽取规则')
        tpl = resolve_rule(rule_id)
        current = next((r for r in catalog.list_extract_results(doc_id)
                        if r['rule_id'] == rule_id), None)
        exists = bool(current and current['record_count'])
    if exists and not force:
        raise errors.Conflict('该规则已有抽取结果，重新抽取会覆盖记录与入库绑定')
    doc = content.get_extract(doc_id)
    if doc is None:
        raise errors.Conflict('资料缺少解析产物，请重新解析')
    result_id = catalog.ensure_extract_result(
        doc_id, rule_id, _rule_snapshot(tpl), status='running')
    logger.info('开始抽取：doc_id=%s rule_id=%s extract_result_id=%s force=%s',
                doc_id, rule_id, result_id, force)
    try:
        recs = extract_records(doc, tpl)
        spec = tpl.get('extraction_spec_json') or {}
        if spec.get('spec_version') == 2:
            from . import smart_extract
            recs, fallback = smart_extract.build_row_fallback(doc, tpl, recs)
            if fallback.get('attempted'):
                logger.info('逐行兜底：extract_result_id=%s attempted=%s filled=%s failed=%s',
                            result_id, fallback['attempted'], fallback['filled'],
                            len(fallback['failed']))
        content_db.save_records(result_id, recs)
        catalog.finish_extract_result(result_id, status='ready')
        catalog.set_state(doc_id, 'to_review', None)
    except Exception as exc:
        catalog.finish_extract_result(result_id, status='failed', error=str(exc))
        logger.exception('抽取失败：doc_id=%s rule_id=%s result_id=%s',
                         doc_id, rule_id, result_id)
        raise
    logger.info('抽取完成：doc_id=%s rule_id=%s result_id=%s records=%s',
                doc_id, rule_id, result_id, len(recs))
    return {'ok': True, 'doc_id': doc_id, 'rule_id': rule_id,
            'extract_result_id': result_id, 'records_n': len(recs)}


def derive_review_state(extract_result_id):
    """按单个结果的复核结论更新资料汇总态。"""
    catalog = _load('store.catalog')
    result = catalog.get_extract_result(extract_result_id)
    if result is None:
        return None
    counts = _load('store.content_db').gate_counts(extract_result_id)
    results = catalog.list_extract_results(result['doc_id'])
    total = sum(_load('store.content_db').gate_counts(r['id'])['records_n']
                for r in results)
    blocked = sum(sum(_load('store.content_db').gate_counts(r['id'])[k]
                      for k in ('pending', 'edited', 'rejected')) for r in results)
    state = 'to_load' if total and not blocked else 'to_review'
    catalog.set_state(result['doc_id'], state, None)
    return state


def approve_all(extract_result_id):
    """确认单个抽取结果中全部待审记录。"""
    catalog = _load('store.catalog')
    content_db = _load('store.content_db')
    errors = _load('store.errors')
    result = catalog.get_extract_result(extract_result_id)
    if result is None:
        raise errors.NotFound('抽取结果不存在')
    records = content_db.get_records(extract_result_id) or {}
    recs = records.get('records') or [
        rec for group in records.get('files') or [] for rec in group['records']]
    indexes = [r['index'] for r in recs
               if (r.get('review') or {}).get('state') in ('pending', 'edited')]
    n = content_db.set_review(extract_result_id, indexes, 'confirmed') if indexes else 0
    state = derive_review_state(extract_result_id)
    return {'ok': True, 'doc_id': result['doc_id'],
            'extract_result_id': extract_result_id, 'updated': n,
            'doc_state': state}


def reparse(file_id, params=None, test_mode=False):
    """原地重放解析：原件字节从 c1_doc_file 回捞，按资料生效参数重跑。
    普通重放清空旧产物、暂存、校验结论、隔离行与回执，规则绑定不保留。
    test_mode 仅允许已入库资料，产物写入 test/，正式数据与状态全部保留。"""
    catalog = _load('store.catalog')
    content_db = _load('store.content_db')
    artifact = _load('store.artifact')
    errors = _load('store.errors')
    if STATE['running']:
        raise errors.Conflict('有解析正在进行，暂不能重放')
    f = catalog.get_file(file_id)
    if f is None:
        raise errors.NotFound('资料不存在')
    if f['state'] == 'loading':
        raise errors.Conflict('资料入库中，不能重放')
    if f['state'] == 'loaded' and not test_mode:
        raise errors.Conflict('资料已入库，请使用测试重解析（保留正式数据）')
    if test_mode and f['state'] != 'loaded':
        raise errors.Conflict('测试重解析仅适用于已入库资料')
    params = params if params is not None else (f.get('params_json') or {})
    src = catalog.get_file_content(file_id)
    if src is None:
        raise errors.NotFound('原件字节缺失，无法重放')
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    try:
        name = os.path.basename(f['name'])
        path = os.path.join(in_dir, name)
        with open(path, 'wb') as fh:
            fh.write(src['data'])
        if not test_mode:
            catalog.clear_document_results(file_id)
            artifact.delete_all(file_id)
            catalog.set_state(file_id, 'pending', '')
        ctx = [{'file_id': file_id, 'name': name, 'path': path,
                'state': f['state']}]
        label = 'file_{}{}'.format(file_id, '_test' if test_mode else '')
        tasklog = _load('tasklog')
        log = tasklog.TaskLog(label,
                              log_path=os.path.join(config.LOG_DIR,
                                                    label + '.log'),
                              on_emit=_on_log)
        task_ctx = {'file_id': file_id, 'rule': None, 'files': ctx,
                    'created_at': f.get('created_at') or _now(),
                    'in_scratch': in_dir,
                    'preserve_state': test_mode,
                    'artifact_prefix': 'test/' if test_mode else ''}
        with LOCK:
            STATE.update(running=True, ready=False, error=None, steps=[],
                         cases=[], started=time.time(), elapsed=0,
                         params={k: v for k, v in params.items()
                                 if not k.startswith('_')}, warnings=[],
                         logs=[], progress=0, stage='batch',
                         log_file=label + '.log',
                         rule=None, file_id=file_id, task_id=file_id,
                         test_mode=test_mode, extract_results=[])
        log.stage('batch', '资料 {} · {}'.format(
            file_id, '测试重解析（保留正式数据）' if test_mode else '重放解析（原地）'))
        threading.Thread(target=task_batch,
                         args=([path], params, log, task_ctx),
                         daemon=True).start()
        return {'ok': True, 'file_id': file_id, 'count': 1,
                'test_mode': test_mode,
                'report_url': '/files/{}/test/{}'.format(
                    file_id, config.PARSE_REPORT_NAME) if test_mode else None}
    except Exception:
        rmtree_retry(in_dir)
        raise


# ---- P2 入库引擎：手动闸门 → 后台逐条写入＋幂等回执 ----

def launch_load(extract_result_id, *, background=True):
    """执行已显式确认的单结果入库绑定；预检失败不写业务库。"""
    catalog = _load('store.catalog')
    errors = _load('store.errors')
    if STATE['running']:
        raise errors.Conflict('已有任务正在处理，请等待其完成')
    result = catalog.get_extract_result(extract_result_id)
    if result is None:
        raise errors.NotFound('抽取结果不存在')
    binding = catalog.get_binding(extract_result_id=extract_result_id)
    if binding is None:
        raise errors.BadRequest('该抽取结果尚未配置入库目标')
    if binding['status'] != 'confirmed':
        raise errors.Conflict('入库绑定尚未显式确认')
    lt = catalog.get_load_table(binding['load_table_id'])
    ds = catalog.get_datasource_by_code(binding['datasource_code'])
    if lt is None or ds is None:
        raise errors.NotFound('入库目标不存在')
    loader = _load('store.loader')
    loader.preflight(ds, lt['target_table'], binding['field_map_json'],
                     binding['write_mode'], list(binding['field_map_json']),
                     binding['business_keys_json'])
    doc = _load('store.content_db').get_records(extract_result_id)
    recs = [r for f in (doc or {}).get('files') or [] for r in f['records']]
    if not recs:
        raise errors.Conflict('暂无抽取记录，无法入库')
    counts = loader.review_gate(recs)
    blocked = counts['pending'] + counts['edited'] + counts['rejected']
    if blocked:
        raise errors.Conflict(
            '{} 条待校验 / {} 条已修改未确认 / {} 条已拒绝，请先完成校验'.format(
                counts['pending'], counts['edited'], counts['rejected']))
    catalog.start_binding(binding['id'])
    label = 'result_{}_load'.format(extract_result_id)
    tasklog = _load('tasklog')
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=_on_log)
    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], started=time.time(), elapsed=0,
                     params={}, warnings=[], logs=[], progress=0,
                     stage='load', log_file=label + '.log',
                     rule=None, file_id=result['doc_id'],
                     task_id=extract_result_id, extract_results=[])
    log.stage('load', '抽取结果 {} 入库 → {}.{}（{} · 共 {} 条）'.format(
        extract_result_id, ds['db_name'], lt['target_table'],
        binding['write_mode'], len(recs)))
    if background:
        threading.Thread(target=run_load,
                         args=(extract_result_id, binding, ds, lt, log),
                         daemon=True).start()
    else:
        run_load(extract_result_id, binding, ds, lt, log)
    return {'ok': True, 'doc_id': result['doc_id'],
            'extract_result_id': extract_result_id,
            'load_binding_id': binding['id']}


def preview_load(extract_result_id, draft=None):
    """单结果入库 dry-run；只读目标库，不创建绑定、不写记录。"""
    catalog = _load('store.catalog')
    errors = _load('store.errors')
    loader = _load('store.loader')
    result = catalog.get_extract_result(extract_result_id)
    if result is None:
        raise errors.NotFound('抽取结果不存在')
    binding = catalog.get_binding(extract_result_id=extract_result_id)
    if binding:
        if draft is not None:
            raise errors.Conflict('已有入库绑定，预览不再接受草稿')
        ds = catalog.get_datasource_by_code(binding['datasource_code'])
        lt = catalog.get_load_table(binding['load_table_id'])
        cm, bk = binding['field_map_json'], binding['business_keys_json']
        table, wm = lt['target_table'], binding['write_mode']
    else:
        if not isinstance(draft, dict):
            raise errors.BadRequest('请选择业务库与目标表')
        ds_code = str(draft.get('datasource_code') or '').strip()
        if ds_code:
            ds = catalog.get_datasource_by_code(ds_code)
        else:
            try:
                ds_id = int(draft.get('datasource_id'))
            except (TypeError, ValueError):
                raise errors.BadRequest('请选择业务库')
            ds = catalog.get_datasource(ds_id)
        table = str(draft.get('target_table') or '').strip()
        wm = str(draft.get('write_mode') or 'upsert')
        cm = draft.get('field_map') if isinstance(draft.get('field_map'), dict) else {}
        bk = draft.get('business_keys') or draft.get('business_key') or []
    if ds is None:
        raise errors.NotFound('业务库不存在')
    loader.preflight(ds, table, cm, wm, list(cm), bk)
    doc = _load('store.content_db').get_records(extract_result_id)
    recs = [r for f in (doc or {}).get('files') or [] for r in f['records']]
    if not recs:
        raise errors.Conflict('无抽取记录')
    receipts = {r['record_index'] for r in
                catalog.list_receipts(load_binding_id=binding['id'])} if binding else set()
    counts = {'insert': 0, 'update': 0, 'skip': 0, 'quarantine': 0}
    conn = loader.connect_datasource(ds)
    try:
        for rec in recs:
            if rec['index'] in receipts:
                counts['skip'] += 1
                continue
            selected = {name: value for name, value in rec['values'].items()
                        if name in cm}
            if not selected:
                counts['quarantine'] += 1
                continue
            if wm == 'insert':
                counts['insert'] += 1
                continue
            mapped = {cm[k]: v for k, v in selected.items()}
            missing = [key for key in bk if key not in mapped]
            if missing:
                counts['quarantine'] += 1
                continue
            where = ' AND '.join('{}=%s'.format(loader._ident(c)) for c in bk)
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM {} WHERE {} LIMIT 1'.format(
                    loader._ident(table), where), [mapped[c] for c in bk])
                found = cur.fetchone() is not None
            if found:
                counts['update'] += 1
            elif wm == 'update':
                counts['quarantine'] += 1
            else:
                counts['insert'] += 1
    finally:
        conn.close()
    return dict(counts, total=len(recs), write_mode=wm, ok=True)


def _refresh_doc_load_state(doc_id):
    catalog = _load('store.catalog')
    results = catalog.list_extract_results(doc_id)
    bindings = [catalog.get_binding(extract_result_id=r['id']) for r in results]
    bindings = [b for b in bindings if b]
    if bindings and all(b['status'] == 'ready' for b in bindings) \
            and len(bindings) == len(results):
        catalog.set_state(doc_id, 'loaded', None)
    elif any(b and b['status'] == 'running' for b in bindings):
        catalog.set_state(doc_id, 'loading', None)
    else:
        catalog.set_state(doc_id, 'to_load', None)


def run_load(extract_result_id, binding, ds, lt, log):
    """逐记录执行已确认绑定；回执、隔离与业务键均按绑定隔离。"""
    catalog = _load('store.catalog')
    loader = _load('store.loader')
    import pymysql
    binding_id = binding['id']
    doc_id = binding['doc_id']
    table = lt['target_table']
    cm = binding['field_map_json']
    bk = binding['business_keys_json']
    wm = binding['write_mode']
    try:
        catalog.set_state(doc_id, 'loading', None)
        doc = _load('store.content_db').get_records(extract_result_id)
        rid_map = _load('store.content_db').record_id_map(extract_result_id)
        receipts = {r['record_index'] for r in
                    catalog.list_receipts(load_binding_id=binding_id)}
        recs = [r for f in (doc or {}).get('files') or [] for r in f['records']]
        total = len(recs)
        written = skipped = quarantined = done = 0
        aborted = None
        conn = loader.connect_datasource(ds)
        try:
            for rec in recs:
                done += 1
                with LOCK:
                    STATE['progress'] = int(done / total * 100) if total else 100
                if rec['index'] in receipts:
                    skipped += 1
                    continue
                selected = {name: value for name, value in rec['values'].items()
                            if name in cm}
                try:
                    with conn.cursor() as cur:
                        action, pk = loader.write_record(
                            cur, table, cm, selected, wm, bk,
                            extra_values={'file_id': doc_id,
                                          'record_id': rid_map.get(
                                              (extract_result_id, rec['index']))})
                    conn.commit()
                except loader.LoadRecordError as exc:
                    conn.rollback()
                    catalog.add_quarantine(
                        doc_id, rec['index'], 'load', exc.msg,
                        {'values': rec['values']}, extract_result_id=extract_result_id,
                        load_binding_id=binding_id)
                    quarantined += 1
                    log.warn('load', '记录 {} 隔离：{}'.format(rec['index'], exc.msg))
                    continue
                except pymysql.MySQLError as exc:
                    conn.rollback()
                    if isinstance(exc, (pymysql.IntegrityError,
                                        pymysql.DataError,
                                        pymysql.ProgrammingError)):
                        catalog.add_quarantine(
                            doc_id, rec['index'], 'load', str(exc),
                            {'values': rec['values']},
                            extract_result_id=extract_result_id,
                            load_binding_id=binding_id)
                        quarantined += 1
                        log.warn('load', '记录 {} 隔离：{}'.format(rec['index'], exc))
                        continue
                    aborted = '{}: {}'.format(type(exc).__name__, exc)
                    log.error('load', '目标库连接中断，中止：{}'.format(aborted))
                    break
                except OSError as exc:
                    aborted = '{}: {}'.format(type(exc).__name__, exc)
                    log.error('load', '目标库连接中断，中止：{}'.format(aborted))
                    break
                catalog.add_receipt(binding_id, rec['index'], pk, action)
                written += 1
        finally:
            conn.close()
        if aborted:
            catalog.finish_binding(binding_id, status='failed', error=aborted)
            state, err = 'to_load', '目标库连接中断：{}'.format(aborted)
        elif quarantined:
            catalog.finish_binding(binding_id, status='failed',
                                   error='{} 条隔离'.format(quarantined))
            state, err = 'to_load', '{} 条隔离（详见隔离区）'.format(quarantined)
        else:
            catalog.finish_binding(binding_id, status='ready')
            state, err = None, None
        if state:
            catalog.set_state(doc_id, state, err)
        else:
            _refresh_doc_load_state(doc_id)
        log.ok('done', '入库完成：写入 {} · 回执跳过 {} · 隔离 {}'.format(
            written, skipped, quarantined))
        with LOCK:
            STATE.update(running=False, ready=err is None, error=err,
                         elapsed=round(time.time()
                                       - (STATE['started'] or time.time()), 1),
                         progress=100, stage='done')
    except Exception as exc:
        log.error('error', '出错：{}'.format(exc))
        log.error('error', traceback.format_exc(limit=3).strip())
        try:
            catalog.finish_binding(binding_id, status='failed', error=str(exc))
            catalog.set_state(doc_id, 'failed', str(exc))
        except Exception as store_exc:
            log.warn('store', '资料状态写入失败：{}'.format(store_exc))
        with LOCK:
            STATE.update(running=False, ready=False, error=str(exc),
                         stage='error')
