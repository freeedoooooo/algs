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
import threading
import traceback

from . import config


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
    """登记新行（不去重）；sha 仍算供检索/ETag，dedup 恒 False。
    DB 必选：失败上抛（调用方回 503）。"""
    sha = hashlib.sha256(data).hexdigest()
    fid, dedup = _load('store.catalog').register_file(
        name, _kind_of(name), len(data), sha, data)
    return {'file_id': fid, 'sha256': sha, 'dedup': dedup}


def _passthrough_rule():
    """内存默认：原始透传（空 mapping → collect.passthrough）。
    不落库、不占 id；未指定/未绑定规则时恒用它，不受库内其他规则影响。"""
    return {'name': '原始透传', 'version': 1,
            'version_id': None, 'rule_id': None,
            'schema_json': {'fields': []},
            'mapping_json': {}, 'transform_json': None}


def resolve_rule(version_id=None):
    """抽取规则版本解析；未指定版本恒用内存默认「原始透传」，
    不再从库里取第一条（避免用户新建规则后悄悄变成默认）。
    显式指定 version_id 找不到仍报错，避免静默替换用户选择。"""
    if version_id is None:
        return _passthrough_rule()
    catalog = _load('store.catalog')
    tv = catalog.get_rule_version(version_id=version_id)
    if not tv:
        raise RuntimeError('抽取规则版本不存在')
    return {'name': tv['name'], 'version': tv['version'],
            'version_id': tv['id'], 'rule_id': tv['rule_id'],
            'schema_json': tv['schema_json'],
            'mapping_json': tv['mapping_json'],
            'transform_json': tv['transform_json']}


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
                     test_mode=False)
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
        print(traceback.format_exc(limit=3))
    finally:
        for f in task_ctx.get('files') or []:
            if f.get('scratch'):
                rmtree_retry(f['scratch'])
        if task_ctx.get('in_scratch'):
            rmtree_retry(task_ctx['in_scratch'])


# ---- 抽取引擎（与解析解耦）：parse.json 纯投影 → staging 三表 ----

def extract_records(doc, tpl):
    """规则版本 → 记录列表；解析、抽取、入库可分别测试的纯编排边界。"""
    spec = tpl.get('mapping_json') or {}
    if spec.get('spec_version') == 3:
        return _load('smart_extract').build_smart(doc, tpl)
    return _load('collect').build(doc, tpl)


def run_extract(file_id, force=False, rule_version_id=None):
    """执行抽取：回读 parse.json → 规则分流 → save_records。
    spec_version 缺省/1/2 走 collect.build（纯函数）；=3 走 smart_extract。
    rule_version_id=None/0：本次走内存默认「原始透传」，不回写配置；
    正整数按版本 id 解析，抽取成功后回写资料绑定（M4，Agent 选规则可追溯）。
    资料已配置 rule_version_id 不参与本次抽取（由 UI 显式传值）。

    仅处理 to_extract；已有暂存记录（to_review/to_load）须 force=true——
    重抽先删后插，校验结论清零。loading/loaded 拒绝；缺 parse.json 拒绝。"""
    catalog = _load('store.catalog')
    content = _load('store.content')
    collect = _load('collect')
    errors = _load('store.errors')
    if STATE['running']:
        raise errors.Conflict('解析进行中，请等待其完成后再抽取')
    f = catalog.get_file(file_id)
    if f is None:
        raise errors.NotFound('资料不存在')
    state = f['state']
    if state in ('loading', 'loaded'):
        raise errors.Conflict('资料入库中/已入库，不能再抽取')
    if state not in ('to_extract', 'to_review', 'to_load'):
        raise errors.Conflict('资料状态为 {}，无解析产物可抽取'.format(state))
    if state != 'to_extract' and not force:
        raise errors.Conflict('资料已有暂存记录，重新抽取将覆盖校验结论（须显式确认）')
    vid = None if rule_version_id in (None, 0) else rule_version_id
    tpl = resolve_rule(vid)
    doc = content.get_extract(file_id)
    if doc is None:
        raise errors.Conflict('资料缺少解析产物，请重新解析')
    recs = extract_records(doc, tpl)
    catalog.clear_load_logs(file_id)
    content.save_records(collect.build_records_doc(
        doc, recs, task_id=file_id,
        task_file_id=file_id, file_id=file_id,
        rule={'name': tpl['name'], 'version': tpl['version']}))
    # 显式指定版本时回写绑定：抽取用的规则即资料当前规则（Agent 自动选规则可追溯）。
    # rule_version_id=None/0 的透传调用不回写，保持 API 兼容与"不抹配置"语义。
    if vid is not None:
        catalog.set_rule(file_id, vid)
    catalog.set_state(file_id, 'to_review', None)
    return {'ok': True, 'file_id': file_id,
            'files': [{'file_id': file_id, 'name': f['name'],
                       'records_n': len(recs)}]}


def derive_review_state(file_id):
    """校验动作提交后重算派生态：to_review ↔ to_load——
    全部记录已定论（无 pending/edited/rejected 且有记录）→ to_load，
    否则回 to_review。只动资料态，不碰记录。返回新状态。"""
    catalog = _load('store.catalog')
    content_db = _load('store.content_db')
    f = catalog.get_file(file_id)
    if f is None or f['state'] not in ('to_review', 'to_load'):
        return None
    c = content_db.gate_counts(file_id)
    target = ('to_load'
              if c['records_n'] and not (c['pending'] + c['edited']
                                         + c['rejected'])
              else 'to_review')
    if target != f['state']:
        catalog.set_state(file_id, target, None)
    return target


def approve_all(file_id):
    """执行校验（全部通过）：把该资料所有待审(pending/edited)记录批量
    设为 confirmed，推进到 to_load；拒绝的记录不动（须人工处理），
    有 rejected 时保持 to_review。仅 to_review/to_load 可执行。"""
    catalog = _load('store.catalog')
    content = _load('store.content')
    errors = _load('store.errors')
    f = catalog.get_file(file_id)
    if f is None:
        raise errors.NotFound('资料不存在')
    if f['state'] not in ('to_review', 'to_load'):
        raise errors.Conflict('资料状态为 {}，无待校验记录'.format(f['state']))
    doc = _load('store.content_db').get_records(file_id)
    recs = (doc or {}).get('files', [{}])[0].get('records', [])
    idxs = [r['index'] for r in recs
            if (r.get('review') or {}).get('state') in ('pending', 'edited')]
    n = content.set_review(file_id, idxs, 'confirmed') if idxs else 0
    new_state = derive_review_state(file_id)
    return {'ok': True, 'file_id': file_id, 'updated': n,
            'file_state': new_state}


def reparse(file_id, params=None, test_mode=False):
    """原地重放解析：原件字节从 c1_doc_file 回捞，按资料生效参数重跑。
    普通重放清空旧产物、暂存、校验结论、隔离行与回执，规则绑定不保留。
    test_mode 仅允许已入库资料，产物写入 test/，正式数据与状态全部保留。"""
    catalog = _load('store.catalog')
    content_db = _load('store.content_db')
    artifact = _load('store.artifact')
    load = _load('store.catalog.load')
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
            content_db.purge_records(file_id)
            artifact.delete_all(file_id)
            load.clear_load_logs(file_id)
            catalog.clear_quarantine(file_id)
            catalog.set_rule(file_id, None)
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
                         test_mode=test_mode)
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

def _snapshot_names(snap):
    """运行时只读映射快照；快照缺失即拒绝，不再回查抽取规则做契约校验。"""
    errors = _load('store.errors')
    names = [f.get('name') for f in (snap or {}).get('fields') or []
             if isinstance(f, dict) and f.get('name')]
    if not names:
        raise errors.BadRequest('入库映射缺少抽取输出快照，请重新保存映射')
    return names


def launch_load(file_id, target=None, *, auto=False, background=True):
    """POST /api/sources/{id}/load 的编排：入库时绑定目标。
    未绑定须带 target={datasource_id,load_table_id}：归属/规则/预检/门禁
    全过才登记绑定＋起线程，任何一步失败都不落绑定（下次可另选）。
    已绑定沿用原绑定（带 target→409，回执语义）。
    auto=True 用于自动处理：跳过人工 confirmed 门禁；background=False 同步执行。"""
    catalog = _load('store.catalog')
    errors = _load('store.errors')
    if STATE['running'] and not auto:
        raise errors.Conflict('已有资料正在处理，请等待其完成')
    f = catalog.get_file(file_id)
    if f is None:
        raise errors.NotFound('资料不存在')
    state = f['state']
    if state == 'loaded':
        raise errors.Conflict('资料已入库')
    if state == 'loading':
        raise errors.Conflict('入库进行中')
    if not auto and state != 'to_load':
        raise errors.Conflict(
            '资料状态为 {}，未到「待入库」（须全部记录校验确认）'.format(state))
    bound = (f['load_datasource_id'], f['load_table_id']) \
        if f.get('load_table_id') else None
    if bound:
        if target:
            raise errors.Conflict('已绑定入库目标，不可修改（重试将沿用原目标）')
        ds_id, lt_id = bound
    else:
        if not target:
            raise errors.BadRequest('请选择业务库与入库映射')
        ds_id, lt_id = target['datasource_id'], target['load_table_id']
    lt = catalog.get_load_table(lt_id)
    if lt is None:
        raise errors.NotFound('入库映射不存在')
    ds = catalog.get_datasource(ds_id)
    if ds is None:
        raise errors.NotFound('业务库不存在')
    if lt['datasource_id'] != ds_id:
        raise errors.BadRequest('入库映射不属于所选业务库')
    # 抽取规则仅作参考：契约来自映射快照；transform 仅存量 v1 规则仍需要
    tpl = resolve_rule(f['rule_version_id']) if f.get('rule_version_id') else None
    fields = _snapshot_names(lt.get('source_snapshot'))
    loader = _load('store.loader')
    loader.preflight(ds, lt['target_table'], lt['fields'],
                     lt['write_mode'], fields)
    doc = _load('store.content').get_records(file_id)
    recs = [r for fs in (doc['files'] if doc else []) for r in fs['records']]
    if not recs:
        raise errors.Conflict('暂无暂存记录，无法入库')
    if not auto:
        c = loader.review_gate(recs)
        blocked = c['pending'] + c['edited'] + c['rejected']
        if blocked:
            raise errors.Conflict(
                '{} 条待校验 / {} 条已修改未确认 / {} 条已拒绝，'
                '请先完成校验：仅当全部记录为「已确认」时才可入库'.format(
                    c['pending'], c['edited'], c['rejected']))
    if not bound:
        catalog.set_load(file_id, ds_id, lt_id)
    label = 'file_{}_load'.format(file_id)
    tasklog = _load('tasklog')
    log = tasklog.TaskLog(label, log_path=os.path.join(config.LOG_DIR,
                                                       label + '.log'),
                          on_emit=_on_log)
    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], started=time.time(), elapsed=0,
                     params={}, warnings=[], logs=[], progress=0,
                     stage='load', log_file=label + '.log',
                     rule=tpl, file_id=file_id, task_id=file_id)
    log.stage('load', '资料 {} 入库 → {}.{}（{} · 共 {} 条）'.format(
        file_id, ds['db_name'], lt['target_table'], lt['write_mode'],
        len(recs)))
    if background:
        threading.Thread(target=run_load,
                         args=(file_id, ds, lt, tpl, log),
                         daemon=True).start()
    else:
        run_load(file_id, ds, lt, tpl, log)
    return {'ok': True, 'file_id': file_id}


def preview_load(file_id, table_id=None, draft=None):
    """入库向导 dry-run：镜像 run_load 的分类（回执跳过→转换→去重依据 SELECT），
    只读目标库，不写、不绑定、不动 STATE。"""
    catalog = _load('store.catalog')
    errors = _load('store.errors')
    loader = _load('store.loader')
    f = catalog.get_file(file_id)
    if f is None:
        raise errors.NotFound('资料不存在')
    bound = f.get('load_table_id')
    if bound:
        if draft is not None:
            raise errors.Conflict('资料已绑定入库目标，预览不再接受草稿')
        table_id = bound
    elif table_id is None and draft is None:
        raise errors.BadRequest('请选择业务库与入库映射')
    if table_id is not None and draft is not None:
        raise errors.BadRequest('预览只认一种目标：规则 id 或草稿')
    if table_id is not None:
        lt = catalog.get_load_table(int(table_id))
        if lt is None:
            raise errors.NotFound('入库映射不存在')
        ds = catalog.get_datasource(lt['datasource_id'])
        field_rows, table, wm = lt['fields'], lt['target_table'], lt['write_mode']
        fields = _snapshot_names(lt.get('source_snapshot'))
        tpl = resolve_rule(f['rule_version_id']) if f.get('rule_version_id') else None
    else:
        ds = catalog.get_datasource(int(draft.get('datasource_id') or 0))
        field_rows = draft.get('fields') or []
        table = str(draft.get('target_table') or '')
        wm = str(draft.get('write_mode') or 'upsert')
        tpl = resolve_rule(f.get('rule_version_id')) if f.get('rule_version_id') else None
        fields = ([fr.get('rule_field') for fr in field_rows
                   if isinstance(fr, dict) and fr.get('rule_field')])
        if isinstance(draft.get('snapshot'), dict):
            fields = _snapshot_names(draft['snapshot'])
    if ds is None:
        raise errors.NotFound('业务库不存在')
    loader.preflight(ds, table, field_rows, wm, fields)
    doc = _load('store.content').get_records(file_id)
    recs = [r for fs in (doc['files'] if doc else []) for r in fs['records']]
    if not recs:
        raise errors.Conflict('无暂存记录')
    cm, bk = loader.fields_to_map(field_rows)
    transform = (tpl or {}).get('transform_json')
    receipts = {(r['record_index']) for r in catalog.list_load_logs(file_id)}
    counts = {'insert': 0, 'update': 0, 'skip': 0, 'quarantine': 0}
    conn = loader.connect_datasource(ds)
    try:
        for rec in recs:
            if rec['index'] in receipts:
                counts['skip'] += 1
                continue
            vals, errs = loader.apply_transform(rec['values'], transform)
            if errs:
                counts['quarantine'] += 1
                continue
            if wm == 'insert':
                counts['insert'] += 1
                continue
            mapped = {cm[k]: v for k, v in vals.items() if k in cm}
            where = ' AND '.join(
                '{}=%s'.format(loader._ident(c)) for c in bk)
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM {} WHERE {} LIMIT 1'.format(
                    loader._ident(table), where),
                    [mapped[c] for c in bk])
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


def run_load(file_id, ds, lt, tpl, log):
    """后台线程：逐记录 回执跳过→transform→写目标库→回执/隔离。
    单条数据级错误→隔离继续；连接级失败→中止（已写回执保留）→to_load＋说明。
    平台库写失败→整资料 failed（DB 必选）。完成态最后发布。"""
    catalog = _load('store.catalog')
    content = _load('store.content')
    loader = _load('store.loader')
    import pymysql
    datasource_id = ds['id']
    table = lt['target_table']
    cm, bk = loader.fields_to_map(lt['fields'])
    wm = lt['write_mode']
    transform = (tpl or {}).get('transform_json')
    try:
        catalog.set_state(file_id, 'loading', None)
        doc = content.get_records(file_id)
        rid_map = content.record_id_map(file_id)
        receipts = {r['record_index'] for r in catalog.list_load_logs(file_id)}
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
                    if rec['index'] in receipts:
                        skipped += 1
                        continue
                    vals, errs = loader.apply_transform(rec['values'], transform)
                    if errs:
                        catalog.add_quarantine(
                            file_id, rec['index'], 'load',
                            '；'.join(e['reason'] for e in errs),
                            {'values': rec['values'], 'errors': errs})
                        quarantined += 1
                        log.warn('load', '记录 {} 隔离：{}'.format(
                            rec['index'], errs[0]['reason']))
                        continue
                    try:
                        with conn.cursor() as cur:
                            action, pk = loader.write_record(
                                cur, table, cm, vals, wm, bk,
                                extra_values={
                                    'file_id': file_id,
                                    'record_id': rid_map.get((file_id, rec['index']))})
                        conn.commit()
                    except loader.LoadRecordError as e:
                        conn.rollback()
                        catalog.add_quarantine(
                            file_id, rec['index'], 'load',
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
                                file_id, rec['index'],
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
                    catalog.add_load_log(file_id, rec['index'], datasource_id,
                                         table, pk, action)
                    written += 1
                if aborted:
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if aborted:
            state, err = 'to_load', '目标库连接中断：{}'.format(aborted)
        elif quarantined:
            state, err = 'to_load', '{} 条隔离（详见隔离区）'.format(quarantined)
        else:
            state, err = 'loaded', None
        catalog.set_state(file_id, state, err)
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
            catalog.set_state(file_id, 'failed', str(e))
        except Exception as e2:
            log.warn('store', '资料状态写入失败：{}'.format(e2))
        with LOCK:
            STATE.update(running=False, ready=False, error=str(e),
                         stage='error')
        print(traceback.format_exc(limit=3))
