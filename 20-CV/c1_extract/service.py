"""
c1_extract/service.py — 运行引擎与共享运行状态（编排层，自 app.py 抽出）。

app.py 只留 HTTP 路由与请求校验；上传校验通过后调 launch() 登记任务并起后台
线程跑 task_batch（提取 → 报告 → collect 记录入库 → 产物 ingest 入 BLOB）。
STATE/LOCK 是单任务串行的运行状态（模型单例非线程安全），/api/status、
/api/logs、/healthz 经 app 读取这里。DB 必选：写失败整任务显式 failed，不降级。
"""
import os
import re
import time
import hashlib
import shutil
import tempfile
import importlib
import threading
import traceback

from . import config


def _load(name):
    return importlib.import_module(__package__ + '.' + name)


# 单任务串行：模型单例不是线程安全的，也没必要并发加载第二份大模型
STATE = {
    'running': False, 'ready': False, 'error': None,
    'steps': [], 'cases': [],
    'started': None, 'elapsed': 0,
    'params': {}, 'warnings': [],
    'logs': [], 'progress': 0, 'stage': '',
    'log_file': None,
    'mode': 'preview', 'template': None, 'task_id': None,
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
    """sha256 去重登记，原件字节直接进 extract_file.content。
    DB 必选：失败上抛（调用方回 503）。"""
    sha = hashlib.sha256(data).hexdigest()
    fid, dedup = _load('store.catalog').register_file(
        name, _kind_of(name), len(data), sha, data)
    return {'file_id': fid, 'sha256': sha, 'dedup': dedup}


def resolve_template(version_id=None):
    """模板版本解析；DB 必选，失败上抛（调用方回 503）。"""
    catalog = _load('store.catalog')
    tv = (catalog.get_template_version(version_id=version_id)
          if version_id else catalog.get_template_version())
    if not tv:
        raise RuntimeError('平台库无可用模板版本')
    return {'name': tv['name'], 'version': tv['version'],
            'version_id': tv['id'], 'template_id': tv['template_id'],
            'schema_json': tv['schema_json'],
            'mapping_json': tv['mapping_json'],
            'transform_json': tv['transform_json']}


def launch(paths, params, warns, ctx, mode='preview', tpl=None, load=None):
    """登记任务（DB 必选，失败上抛 503）→ 建日志 → 重置 STATE → 起后台线程。
    load={'datasource_id','load_table_id'}：mode=load 的预登记入库意图
    （执行须手动点入库）。"""
    tpl = tpl or resolve_template()
    catalog = _load('store.catalog')
    task_id = catalog.create_task(mode, tpl['version_id'], params)
    if load:
        catalog.set_task_load(task_id, load['datasource_id'],
                              load['load_table_id'])
    for f in ctx:
        f['task_file_id'] = catalog.add_task_file(task_id, f['file_id'])
        f['state'] = 'pending'
    label = 'task_{}'.format(task_id)
    tasklog = _load('tasklog')
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=_on_log)
    task_ctx = {'task_id': task_id, 'mode': mode, 'template': tpl,
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
                     mode=mode, template=tpl, task_id=task_id)
    log.stage('batch', '任务 {} · 收到 {} 个文件 · 模式 {} · 模板 {} v{}'.format(
        task_id, len(paths), mode, tpl['name'], tpl['version']))
    log.info('params', '生效参数：{}'.format(
        ', '.join('{}={}'.format(k, v) for k, v in params.items()
                  if not k.startswith('_'))))
    for w in warns:
        log.warn('params', w)
    if load:
        log.info('load', '入库预登记：数据源 {} · 映射 {}（全部确认后手动入库）'
                 .format(load['datasource_id'], load['load_table_id']))
    threading.Thread(target=task_batch, args=(paths, params, log, task_ctx),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'task_id': task_id,
            'warnings': warns}


# 阶段 → 单文件内的进度占比（只增不减）。长耗时的模型加载/推理与 OCR
# 各占一段可见区间，进度条不再整个文件期间停在 0%。
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


def _ingest_case(task_file_id, case_abs):
    """scratch 目录全量产物入 extract_artifact（管线/报告生成零改动，
    它们照旧写文件，这里统一收编入库）。"""
    artifact = _load('store.artifact')
    for root, _, files in os.walk(case_abs):
        for fn in files:
            if fn.endswith('.tmp'):
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, case_abs).replace(os.sep, '/')
            with open(p, 'rb') as f:
                artifact.save(task_file_id, rel, f.read())


def rmtree_retry(path, tries=6, delay=0.3):
    # Windows 杀软/索引器会短暂持有新写文件的句柄，首次 rmtree 常瞬败——短重试
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


def task_batch(paths, params=None, log=None, task_ctx=None):
    """后台线程：逐个提取 → raw/ + extract.json → 对照报告 → collect 记录入库
    → 产物 ingest 入 BLOB。DB 必选：写失败整任务 failed；scratch 跑完清尽。"""
    task_ctx = task_ctx or {'task_id': None, 'mode': 'preview',
                            'template': resolve_template(),
                            'files': [{'name': os.path.basename(p), 'path': p}
                                      for p in paths],
                            'created_at': _now()}
    content = _load('store.content')
    collect = _load('collect')
    catalog = _load('store.catalog')

    def db(fn_name, *a):
        # DB 必选：目录状态写失败上抛 → 整任务显式 failed，不降级
        if task_ctx.get('task_id') is None:
            return
        getattr(catalog, fn_name)(*a)

    try:
        def progress(v):
            with LOCK:
                STATE['progress'] = v

        log.stage('load', '加载提取流水线（首次会导入 cv2 / pdfplumber）…')
        progress(1)
        pipeline = _load('pipeline')
        report_mod = _load('extract_report.builder')
        total = len(paths)
        for i, path in enumerate(paths, 1):
            name = os.path.basename(path)
            fc = next((f for f in task_ctx['files']
                       if f.get('name') == name or f.get('path') == path),
                      {})
            log.stage('case', '[{}/{}] 开始处理 {}'.format(i, total, name))
            progress(int((i - 1) / total * 100))
            # 磁盘只是 scratch（paddle 需要真实图片路径），产物最终入 BLOB
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

            if fc.get('task_file_id'):
                db('set_task_file_state', fc['task_file_id'], 'extracting')
            rec = pipeline.extract_one(path, case_abs, params, emit=emit)
            pages = rec.get('pages') or []
            tot_lines = sum((p.get('stats') or {}).get('lines', 0)
                            for p in pages)
            tot_tables = sum(len(p.get('tables') or []) for p in pages)
            routes = '/'.join(sorted({p.get('route', '-') for p in pages}))
            log.ok('case', '识别 {} 行文字 · 表格 {} 张 · 路线 {} · {} 页{}'.format(
                tot_lines, tot_tables, routes, len(pages),
                ' · 跨页合并 {} 张'.format(len(rec.get('stitched_tables') or []))
                if rec.get('stitched_tables') else ''), case=name)
            # 报告只依赖 extract 层，先于 records 写库生成：
            # 断库时引擎产物（extract+报告）仍完整，任务显式 failed
            report_mod.build([rec],
                             os.path.join(case_abs, config.EXTRACT_REPORT_NAME),
                             params=params)
            # L2 记录层：按模板分发（空映射=passthrough）+ 逐格溯源 → DB 三表
            tpl = task_ctx['template']
            recs = collect.build(rec, tpl)
            rdoc = collect.build_records_doc(
                rec, recs, task_id=task_ctx.get('task_id'),
                task_file_id=fc.get('task_file_id'),
                file_id=fc.get('file_id'),
                template={'name': tpl['name'], 'version': tpl['version']})
            content.save_records(rdoc)
            fc['records_n'] = len(recs)
            fc['state'] = 'previewed'
            nfields = len((tpl.get('mapping_json') or {}).get('fields') or [])
            log.ok('collect', '暂存记录 {} 条（{} · 逐格溯源）'.format(
                len(recs), '映射 {} 字段'.format(nfields) if nfields
                else 'passthrough'), case=name)
            if fc.get('task_file_id'):
                db('set_task_file_state', fc['task_file_id'], 'previewed')
                _ingest_case(fc['task_file_id'], case_abs)
            rmtree_retry(case_abs)
            fc.pop('scratch', None)
            progress(int(i / total * 100))
        db('set_task_state', task_ctx.get('task_id'), 'previewed')
        # 完成态最后发布：status 变 running=False 时 DB 必已写完
        with LOCK:
            STATE.update(running=False, ready=True,
                         cases=[{'file': f['name'],
                                 'task_file_id': f.get('task_file_id'),
                                 'records_n': f.get('records_n')}
                                for f in task_ctx['files']],
                         elapsed=round(time.time()
                                       - (STATE['started'] or time.time()), 1),
                         progress=100, stage='done')
        log.ok('done', '完成，共 {} 个文件，耗时 {}s'.format(
            total, STATE['elapsed']))
    except Exception as e:
        if log:
            log.error('error', '出错：' + str(e))
            log.error('error', traceback.format_exc(limit=3).strip())
        try:
            db('set_task_state', task_ctx.get('task_id'), 'failed', str(e))
        except Exception as e2:
            if log:
                log.warn('store', '任务状态写入失败：{}'.format(e2))
        with LOCK:
            STATE.update(running=False, ready=False, error=str(e),
                         stage='error')
        print(traceback.format_exc(limit=3))
    finally:
        for f in task_ctx.get('files') or []:
            if f.get('scratch'):
                rmtree_retry(f['scratch'])
        if task_ctx.get('in_scratch'):
            rmtree_retry(task_ctx['in_scratch'])


# ---- P2 入库引擎（design-p2-load.md）：手动闸门 → 后台逐条写入＋幂等回执 ----

def launch_load(task_id):
    """POST /api/tasks/{id}/load 的编排：状态/门禁/预检全过才起线程。
    校验失败抛 StoreError（app 处理器映射 HTTP）；目标库连不上→503。"""
    catalog = _load('store.catalog')
    errors = _load('store.errors')
    if STATE['running']:
        raise errors.Conflict('已有任务正在处理，请等它完成')
    task = catalog.get_task(task_id)
    if task is None:
        raise errors.NotFound('任务不存在')
    if task['mode'] != 'load' or not task.get('load'):
        raise errors.BadRequest('任务非入库模式（上传时须选 mode=load）')
    state = task['state']
    if state == 'loaded':
        raise errors.Conflict('任务已入库')
    if state == 'loading':
        raise errors.Conflict('入库进行中')
    if state not in ('previewed', 'partial'):
        raise errors.Conflict('任务状态 {} 不可入库（须先提取完成）'.format(state))
    lt = catalog.get_load_table(task['load']['load_table_id'])
    if lt is None:
        raise errors.NotFound('入库映射不存在')
    ds = catalog.get_datasource(task['load']['datasource_id'])
    if ds is None:
        raise errors.NotFound('数据源不存在')
    tpl = resolve_template(task['template']['version_id'])
    sj = tpl.get('schema_json')
    fields = ([f.get('name') for f in sj.get('fields') or []]
              if isinstance(sj, dict) else [])
    fields = [f for f in fields if f]
    if not fields:
        raise errors.BadRequest('透传模板无固定目标字段，不可入库')
    loader = _load('store.loader')
    loader.preflight(ds, lt['target_table'], lt['fields'],
                     lt['write_mode'], fields)
    doc = _load('store.content').get_records(task_id)
    recs = [r for f in (doc['files'] if doc else []) for r in f['records']]
    if not recs:
        raise errors.Conflict('无暂存记录，不可入库')
    c = loader.review_gate(recs)
    blocked = c['pending'] + c['edited'] + c['rejected']
    if blocked:
        raise errors.Conflict(
            '{} 条待校验 / {} 条已修改未确认 / {} 条已拒绝，'
            '请先处理完（仅全部 confirmed 可入库）'.format(
                c['pending'], c['edited'], c['rejected']))
    label = 'task_{}_load'.format(task_id)
    tasklog = _load('tasklog')
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=_on_log)
    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], started=time.time(), elapsed=0,
                     params={}, warnings=[], logs=[], progress=0,
                     stage='load', log_file=label + '.log',
                     mode='load', template=tpl, task_id=task_id)
    log.stage('load', '任务 {} 入库 → {}.{}（{} · 共 {} 条）'.format(
        task_id, ds['db_name'], lt['target_table'], lt['write_mode'],
        len(recs)))
    threading.Thread(target=run_load,
                     args=(task_id, task, ds, lt, tpl, log),
                     daemon=True).start()
    return {'ok': True, 'task_id': task_id}


def run_load(task_id, task, ds, lt, tpl, log):
    """后台线程：逐记录 回执跳过→transform→写目标库→回执/隔离。
    单条数据级错误→隔离继续；连接级失败→中止（已写回执保留）→partial。
    平台库写失败→整任务 failed（DB 必选）。完成态最后发布。"""
    catalog = _load('store.catalog')
    content = _load('store.content')
    loader = _load('store.loader')
    import pymysql
    datasource_id = task['load']['datasource_id']
    table = lt['target_table']
    cm, bk = loader.fields_to_map(lt['fields'])
    wm = lt['write_mode']
    transform = tpl.get('transform_json')
    try:
        catalog.set_task_state(task_id, 'loading')
        for f in task['files']:
            catalog.set_task_file_state(f['task_file_id'], 'loading')
        doc = content.get_records(task_id)
        receipts = {(r['task_file_id'], r['record_index'])
                    for r in catalog.list_load_logs(task_id)}
        total = sum(len(f['records']) for f in doc['files'])
        written = skipped = quarantined = done = 0
        aborted = None
        conn = loader.connect_datasource(ds)
        try:
            for f in doc['files']:
                for rec in f['records']:
                    done += 1
                    with LOCK:
                        STATE['progress'] = int(done / total * 100) if total else 100
                    key = (f['task_file_id'], rec['index'])
                    if key in receipts:
                        skipped += 1
                        continue
                    vals, errs = loader.apply_transform(rec['values'], transform)
                    if errs:
                        catalog.add_quarantine(
                            task_id, f['task_file_id'], rec['index'], 'load',
                            '；'.join(e['reason'] for e in errs),
                            {'values': rec['values'], 'errors': errs})
                        quarantined += 1
                        log.warn('load', '记录 {} 隔离：{}'.format(
                            rec['index'], errs[0]['reason']))
                        continue
                    try:
                        with conn.cursor() as cur:
                            action, pk = loader.write_record(
                                cur, table, cm, vals, wm, bk)
                        conn.commit()
                    except loader.LoadRecordError as e:
                        conn.rollback()
                        catalog.add_quarantine(
                            task_id, f['task_file_id'], rec['index'], 'load',
                            e.msg, {'values': rec['values']})
                        quarantined += 1
                        log.warn('load', '记录 {} 隔离：{}'.format(
                            rec['index'], e.msg))
                        continue
                    except pymysql.MySQLError as e:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if isinstance(e, (pymysql.IntegrityError,
                                          pymysql.DataError,
                                          pymysql.ProgrammingError)):
                            catalog.add_quarantine(
                                task_id, f['task_file_id'], rec['index'],
                                'load', str(e), {'values': rec['values']})
                            quarantined += 1
                            log.warn('load', '记录 {} 隔离：{}'.format(
                                rec['index'], e))
                            continue
                        aborted = '{}: {}'.format(type(e).__name__, e)
                        log.error('load', '目标库连接中断，中止：{}'.format(aborted))
                        break
                    except OSError as e:
                        aborted = '{}: {}'.format(type(e).__name__, e)
                        log.error('load', '目标库连接中断，中止：{}'.format(aborted))
                        break
                    catalog.add_load_log(task_id, f['task_file_id'],
                                         rec['index'], datasource_id, table,
                                         pk, action)
                    written += 1
                if aborted:
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if aborted:
            state, err = 'partial', '目标库连接中断：{}'.format(aborted)
        elif quarantined:
            state, err = 'partial', '{} 条隔离（详见隔离区）'.format(quarantined)
        else:
            state, err = 'loaded', None
        catalog.set_task_state(task_id, state, err)
        for f in task['files']:
            catalog.set_task_file_state(f['task_file_id'], state)
        log.ok('done', '入库完成：写入 {} · 回执跳过 {} · 隔离 {}'.format(
            written, skipped, quarantined))
        with LOCK:
            STATE.update(running=False, ready=True, error=err,
                         elapsed=round(time.time()
                                       - (STATE['started'] or time.time()), 1),
                         progress=100, stage='done')
    except Exception as e:
        log.error('error', '出错：' + str(e))
        log.error('error', traceback.format_exc(limit=3).strip())
        try:
            catalog.set_task_state(task_id, 'failed', str(e))
        except Exception as e2:
            log.warn('store', '任务状态写入失败：{}'.format(e2))
        with LOCK:
            STATE.update(running=False, ready=False, error=str(e),
                         stage='error')
        print(traceback.format_exc(limit=3))