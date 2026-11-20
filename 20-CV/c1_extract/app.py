"""
c1_extract/app.py — Web 工具入口（FastAPI + uvicorn）。只负责路由与任务编排。

启动：
    D:\\miniforge3\\envs\\paddle\\python.exe c1_extract/app.py
    浏览器打开 http://127.0.0.1:8765

路由：
    GET  /              提取页（assets/upload.html + /static 资源）
    GET  /sources       资料库页 · GET /tasks 任务页 · GET /staging 暂存只读视图
    GET  /healthz       健康检查
    POST /api/upload    上传（base64 JSON，不依赖 python-multipart）
    GET  /api/status    处理进度
    GET  /extract-report   对照报告（重定向到最新 task_file 的报告真实地址）
    /files/<task_file_id>/<path>   产物（DB BLOB，白名单，raw 403）
    /srcfiles/<file_id>            原件（extract_file.content BLOB）
    /static/<path>      页面 css / js

存储契约（design-task-schema.md）：DB 唯一事实源——目录/记录/血缘关系表，
原件字节 extract_file.content，产物字节 extract_artifact（task_file 粒度）；
磁盘仅 tmp/ 运行期 scratch。DB 不可用显式 503/failed，不降级。
审计/file:// 用 export_artifacts.py。提取逻辑在 pipeline/，报告在 extract_report/。
"""
import os
import re
import sys
import time
import base64
import hashlib
import shutil
import tempfile
import importlib
import threading
import traceback
from fnmatch import fnmatch
from urllib.parse import unquote
from contextlib import asynccontextmanager

# ★ 零 IDE 配置的关键：内部模块一律以「包」方式加载。
# 静态分析器能直接解析包内相对导入（from .. import config），不需要标记
# Sources Root / extraPaths；同时下面四种启动方式都成立：
#   python app.py · python c1_extract/app.py · uvicorn app:app · uvicorn c1_extract.app:app
# 包名从目录名动态取，整个目录拷走改名也照样能跑。
ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name):
    """以 <包名>.<name> 加载内部模块，保证包内相对导入始终有效。"""
    return importlib.import_module(PKG + '.' + name)


config = _load('config')           # 必须在 paddle 相关导入之前：设置模型源环境变量
params_mod = _load('params')       # 调试参数 schema / 校验（纯 Python，不碰模型）
from fastapi import FastAPI, Request
from fastapi.responses import (HTMLResponse, JSONResponse, FileResponse,
                               RedirectResponse, PlainTextResponse, Response)
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(_app):
    """
    默认什么都不做 —— 模型保持懒加载，服务启动约 0.5s。
    部署时若想「启动即加载」，设 C1_EXTRACT_WARMUP=1，避免第一个请求等 20~40s；
    代价是启动变慢、内存常驻。两种启动方式（app.py / uvicorn app:app）都生效。
    """
    if config.WARMUP_ON_START:
        engines = _load('pipeline.engines')
        engines.ocr()
        engines.structure()
        print('>> 模型预热完成（PaddleOCR + PPStructureV3）')
    yield


app = FastAPI(title='结构化平台', version='0.1', lifespan=lifespan)

# ---- 产物白名单：页面只见预生成的自有标准视图 ----
# raw/（引擎原样）与旧 result.json 一律 403 —— 引擎结构不出适配层（防方案抄袭）。
_TOP_FILES = {config.EXTRACT_JSON, config.BOXES_NAME,
              config.EXTRACT_REPORT_NAME, 'index.html'}
_IMAGE_SRCS = {'source' + e for e in config.IMAGE_EXTS}
_CSV_PATTERNS = ('table_*.csv', 'stitched_*.csv', 'p*_table_*.csv')


def _files_guard(rel):
    """白名单校验：None=放行，否则 HTTP 状态码。"""
    head = rel.split('/')[0]
    if head == 'raw' or rel == 'result.json':
        return 403
    ok = (rel in _TOP_FILES
          or (rel.startswith('pages/') and rel.endswith('.png'))
          or rel in _IMAGE_SRCS
          or (rel.endswith('.md') and '/' not in rel)
          or any(fnmatch(rel, p) for p in _CSV_PATTERNS))
    return None if ok else 404


def _blob_response(data, mime, sha, request):
    """BLOB 输出：ETag=sha256（内容变才变），If-None-Match 命中回 304。"""
    etag = '"{}"'.format(sha)
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers={'ETag': etag})
    return Response(data, media_type=mime, headers={'ETag': etag})


@app.get('/files/{path:path}')
def files_db(path: str, request: Request):
    """/files/<task_file_id>/<产物相对路径>：白名单 + raw 403。"""
    norm = unquote(path).replace('\\', '/')
    parts = [p for p in norm.split('/') if p not in ('', '.')]
    if not parts or '..' in parts:
        return PlainTextResponse('403 Forbidden', status_code=403)
    if len(parts) < 2 or not parts[0].isdigit():
        return PlainTextResponse('404 Not Found', status_code=404)
    rel = '/'.join(parts[1:])
    code = _files_guard(rel)
    if code:
        msg = ('403 Forbidden（引擎原始层不对外）' if code == 403
               else '404 Not Found')
        return PlainTextResponse(msg, status_code=code)
    try:
        a = _load('store.artifact').get(int(parts[0]), rel)
    except Exception as e:
        return _db_unavailable(e)
    if a is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    return _blob_response(a['data'], a['mime'], a['sha'], request)


@app.get('/srcfiles/{file_id:int}')
def srcfiles_db(file_id: int, request: Request):
    """/srcfiles/<file_id>：原件字节（extract_file.content）。
    用 id 不用名字——同名不同字节是两行，名字会撞。"""
    try:
        s = _load('store.catalog').get_file_content(file_id)
    except Exception as e:
        return _db_unavailable(e)
    if s is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    mime = _load('store.artifact').mime_of(s['name'])
    return _blob_response(s['data'], mime, s['sha'], request)


app.mount('/static', StaticFiles(directory=config.ASSETS_DIR), name='static')


@app.middleware('http')
async def no_cache(request, call_next):
    """本地调试工具：禁止浏览器启发式缓存。StaticFiles/FileResponse 带 ETag/
    Last-Modified，no-cache 让每次使用前先校验（未变 304、变了 200），
    避免「改了 css/js 或重启服务后页面仍是旧样式」——缓存发生在浏览器侧，重启服务无效。"""
    resp = await call_next(request)
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

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


def asset(name):
    with open(os.path.join(config.ASSETS_DIR, name), 'r',
              encoding='utf-8') as f:
        return f.read()


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _kind_of(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in config.PDF_EXTS:
        return 'pdf'
    return 'text' if ext in config.TEXT_EXTS else 'image'


def _register_file(name, data):
    """sha256 去重登记，原件字节直接进 extract_file.content。
    DB 必选：失败上抛（调用方回 503）。"""
    sha = hashlib.sha256(data).hexdigest()
    fid, dedup = _load('store.catalog').register_file(
        name, _kind_of(name), len(data), sha, data)
    return {'file_id': fid, 'sha256': sha, 'dedup': dedup}


def _resolve_template(version_id=None):
    """模板版本解析；DB 必选，失败上抛（调用方回 503）。"""
    catalog = _load('store.catalog')
    tv = (catalog.get_template_version(version_id=version_id)
          if version_id else catalog.get_template_version())
    if not tv:
        raise RuntimeError('平台库无可用模板版本')
    return {'name': tv['name'], 'version': tv['version'],
            'version_id': tv['id']}


@app.get('/', response_class=HTMLResponse)
def index():
    return HTMLResponse(asset('upload.html'))


@app.get('/sources', response_class=HTMLResponse)
def sources_page():
    return HTMLResponse(asset('sources.html'))


@app.get('/tasks', response_class=HTMLResponse)
def tasks_page():
    return HTMLResponse(asset('tasks.html'))


@app.get('/staging', response_class=HTMLResponse)
def staging_page():
    return HTMLResponse(asset('staging.html'))


@app.get('/healthz')
def health():
    return {'ok': True, 'service': 'c1-extract', 'running': STATE['running']}


@app.get('/api/params')
def api_params():
    """返回参数 schema（顺序=优先级）与当前默认值，上传页据此渲染面板。"""
    return {'schema': params_mod.public_schema(),
            'defaults': params_mod.defaults()}


def _dedup_name(name, used):
    """同一批里重名文件加 -2/-3 区分（scratch 内避免互相覆盖）。"""
    if name not in used:
        return name
    stem, e = os.path.splitext(name)
    k = 2
    while '{}-{}{}'.format(stem, k, e) in used:
        k += 1
    return '{}-{}{}'.format(stem, k, e)


@app.post('/api/upload')
async def upload(request: Request):
    if STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等它完成'},
            status_code=409)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': '请求体不是合法 JSON'},
                            status_code=400)
    files = body.get('files') or []
    if not files:
        return JSONResponse({'ok': False, 'error': '没有收到文件'},
                            status_code=400)
    mode = body.get('mode') or 'preview'
    if mode != 'preview':
        return JSONResponse(
            {'ok': False, 'error': '入库模式在 P2 开放，当前请用预览模式'},
            status_code=400)
    try:
        tpl = _resolve_template(body.get('template_version_id'))
    except Exception as e:
        return _db_unavailable(e)
    # 调试参数：校验一次，非法值回退默认并把警告带回页面（不让整批失败）
    params, warns = params_mod.normalize(body.get('params'))

    # 输入副本只落 tmp/input scratch（字节事实源在 extract_file.content），跑完即清
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    paths, used, ctx = [], set(), []
    for item in files:
        name = safe_name(item.get('name', ''))
        ext = os.path.splitext(name)[1].lower()
        if ext not in config.ALLOWED_EXTS:
            return JSONResponse(
                {'ok': False, 'error': '不支持的格式：{}'.format(ext)},
                status_code=400)
        name = _dedup_name(name, used)
        used.add(name)
        try:
            data = base64.b64decode(str(item.get('data', '')).split(',')[-1])
        except Exception:
            return JSONResponse(
                {'ok': False, 'error': '{} 的 base64 数据无效'.format(name)},
                status_code=400)
        if len(data) > config.MAX_FILE_MB * 1024 * 1024:
            return JSONResponse(
                {'ok': False,
                 'error': '{} 超过 {}MB'.format(name, config.MAX_FILE_MB)},
                status_code=400)
        path = os.path.join(in_dir, name)
        with open(path, 'wb') as f:
            f.write(data)
        paths.append(path)
        try:
            info = _register_file(name, data)
        except Exception as e:
            return _db_unavailable(e)
        ctx.append(dict(info, name=name, path=path))

    return _launch(paths, params, warns, ctx, mode, tpl)


def _launch(paths, params, warns, ctx, mode='preview', tpl=None):
    """登记任务（DB 必选，失败整批 503）→ 建日志 → 重置 STATE → 起后台线程。"""
    tpl = tpl or _resolve_template()
    catalog = _load('store.catalog')
    try:
        task_id = catalog.create_task(mode, tpl['version_id'], params)
        for f in ctx:
            f['task_file_id'] = catalog.add_task_file(task_id, f['file_id'])
            f['state'] = 'pending'
    except Exception as e:
        return _db_unavailable(e)
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
    threading.Thread(target=task_batch, args=(paths, params, log, task_ctx),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'task_id': task_id,
            'warnings': warns}


@app.get('/api/status')
def status():
    with LOCK:
        return dict(STATE)


@app.get('/api/logs')
def api_logs():
    """下载当前任务的纯文本运行日志（结构化日志在 /api/status 的 logs 里）。"""
    rel = STATE.get('log_file')
    path = os.path.join(config.LOG_DIR, rel) if rel else None
    if not path or not os.path.isfile(path):
        return JSONResponse({'ok': False, 'error': '暂无日志'}, status_code=404)
    return FileResponse(path, media_type='text/plain; charset=utf-8',
                        filename='task_{}.log'.format(STATE.get('task_id')))


@app.get('/extract-report')
def extract_report():
    """对照报告：重定向到最新 task_file 的 对照报告.html 真实地址。
    报告内资源全是相对路径，必须落在该 task_file 的 URL 下才能解析；
    file:// 直开用 export_artifacts.py 按需导出。"""
    from urllib.parse import quote
    try:
        tf = _load('store.artifact_db').latest_task_file_with(
            config.EXTRACT_REPORT_NAME)
    except Exception as e:
        return _db_unavailable(e)
    if tf is not None:
        return RedirectResponse('/files/{}/{}'.format(
            tf, quote(config.EXTRACT_REPORT_NAME, safe='')))
    return HTMLResponse(
        '<h3>还没有对照报告</h3><p><a href="/">返回上传页</a>先上传一个文件。</p>')


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


def _rmtree_retry(path, tries=6, delay=0.3):
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
                            'template': _resolve_template(),
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
            # L2 记录层：passthrough 收集 + 逐格血缘 → DB 三表（事实源）
            tpl = task_ctx['template']
            recs = collect.passthrough(rec)
            rdoc = collect.build_records_doc(
                rec, recs, task_id=task_ctx.get('task_id'),
                task_file_id=fc.get('task_file_id'),
                file_id=fc.get('file_id'),
                template={'name': tpl['name'], 'version': tpl['version']})
            content.save_records(rdoc)
            fc['records_n'] = len(recs)
            fc['state'] = 'previewed'
            log.ok('collect', '暂存记录 {} 条（passthrough · 逐格血缘）'.format(
                len(recs)), case=name)
            if fc.get('task_file_id'):
                db('set_task_file_state', fc['task_file_id'], 'previewed')
                _ingest_case(fc['task_file_id'], case_abs)
            _rmtree_retry(case_abs)
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
                _rmtree_retry(f['scratch'])
        if task_ctx.get('in_scratch'):
            _rmtree_retry(task_ctx['in_scratch'])


# ---- 数据链路 API（P0：资料库 / 模板 / 任务 / 预生成内容读取）----
# 全部经 catalog / content / artifact repo 查 DB（DB 故障回 503）。
# 任务以 task id 为键；文件以 task_file_id 为键；原件以 file_id 为键。

def _db_unavailable(e):
    return JSONResponse({'ok': False, 'error': '平台库不可用：{}'.format(e)},
                        status_code=503)


@app.get('/api/sources')
def api_sources(q: str = None, kind: str = None, tag: str = None, page: int = 1):
    try:
        return _load('store.catalog').list_files(q, kind, tag, page)
    except Exception as e:
        return _db_unavailable(e)


@app.post('/api/sources')
async def api_sources_add(request: Request):
    """只登记不提取（资料页上传）。哈希命中回已有 id。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': '请求体不是合法 JSON'},
                            status_code=400)
    name = safe_name(body.get('name', ''))
    ext = os.path.splitext(name)[1].lower()
    if ext not in config.ALLOWED_EXTS:
        return JSONResponse({'ok': False, 'error': '不支持的格式：{}'.format(ext)},
                            status_code=400)
    try:
        data = base64.b64decode(str(body.get('data', '')).split(',')[-1])
    except Exception:
        return JSONResponse({'ok': False, 'error': 'base64 数据无效'},
                            status_code=400)
    if len(data) > config.MAX_FILE_MB * 1024 * 1024:
        return JSONResponse(
            {'ok': False, 'error': '{} 超过 {}MB'.format(name, config.MAX_FILE_MB)},
            status_code=400)
    try:
        info = _register_file(name, data)
    except Exception as e:
        return _db_unavailable(e)
    return {'ok': True, 'id': info['file_id'], 'dedup': info['dedup']}


@app.delete('/api/sources/{file_id}')
def api_sources_del(file_id: int):
    try:
        ok, reason = _load('store.catalog').delete_file(file_id)
    except Exception as e:
        return _db_unavailable(e)
    if not ok:
        return JSONResponse({'ok': False, 'reason': reason}, status_code=409)
    return JSONResponse({'ok': True}, status_code=200)


@app.get('/api/templates')
def api_templates():
    try:
        return {'items': _load('store.catalog').list_templates()}
    except Exception as e:
        return _db_unavailable(e)


@app.get('/api/tasks')
def api_tasks():
    """任务列表：task/task_file/file 表投影（无 run.json 附件）。"""
    try:
        return {'items': _load('store.catalog').list_tasks()}
    except Exception as e:
        return _db_unavailable(e)


@app.get('/api/tasks/{task_id}')
def api_task_detail(task_id: int):
    try:
        doc = _load('store.catalog').get_task(task_id)
    except Exception as e:
        return _db_unavailable(e)
    if doc is None:
        return JSONResponse({'ok': False, 'error': '任务不存在'},
                            status_code=404)
    live = None
    with LOCK:
        if STATE.get('task_id') == task_id:
            live = {'running': STATE['running'], 'progress': STATE['progress'],
                    'stage': STATE['stage'], 'error': STATE['error']}
    return {'task': doc, 'live': live}


def _tf_of(task_id, file):
    """任务内选 task_file：file 指定则校验归属，否则取第一个。"""
    tfs = _load('store.catalog').task_file_ids(task_id)
    if not tfs:
        return None
    if file:
        return int(file) if int(file) in tfs else None
    return tfs[0]


@app.get('/api/tasks/{task_id}/extract')
def api_task_extract(task_id: int, file: str = None):
    try:
        tf = _tf_of(task_id, file)
        doc = _load('store.content').get_extract(tf) if tf else None
    except Exception as e:
        return _db_unavailable(e)
    if doc is None:
        return JSONResponse({'ok': False, 'error': 'extract.json 不存在'},
                            status_code=404)
    return doc


@app.get('/api/tasks/{task_id}/staging')
def api_task_staging(task_id: int, file: str = None):
    try:
        doc = _load('store.content').get_records(task_id)
        if doc and file:
            doc['files'] = [f for f in doc['files']
                            if f['task_file_id'] == int(file)]
            if not doc['files']:
                doc = None
    except Exception as e:
        return _db_unavailable(e)
    if doc is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    return doc


@app.get('/api/staging/query')
def api_staging_query(field: str = None, q: str = None,
                      task: str = None, state: str = None):
    """跨任务暂存查询：DB 直查 field 投影；DB down → 503。"""
    try:
        rows = _load('store.content_db').query_fields(field, q, task, state)
    except Exception as e:
        return _db_unavailable(e)
    return {'ok': True, 'items': rows}


@app.post('/api/tasks')
async def api_tasks_create(request: Request):
    """从资料库选文件发起任务（复用上传编排；字节直读 extract_file.content）。"""
    if STATE['running']:
        return JSONResponse({'ok': False, 'error': '已有任务正在处理'},
                            status_code=409)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': '请求体不是合法 JSON'},
                            status_code=400)
    ids = body.get('file_ids') or []
    if not ids:
        return JSONResponse({'ok': False, 'error': '未选择文件'},
                            status_code=400)
    try:
        catalog = _load('store.catalog')
        rows = [catalog.get_file(int(i)) for i in ids]
    except Exception as e:
        return _db_unavailable(e)
    if any(r is None for r in rows):
        return JSONResponse({'ok': False, 'error': '存在未登记的文件 id'},
                            status_code=400)
    params, warns = params_mod.normalize(body.get('params'))
    try:
        tpl = _resolve_template(body.get('template_version_id'))
    except Exception as e:
        return _db_unavailable(e)
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    paths, used, ctx = [], set(), []
    for row in rows:
        name = _dedup_name(row['name'], used)
        used.add(name)
        try:
            s = catalog.get_file_content(row['id'])
        except Exception as e:
            return _db_unavailable(e)
        if s is None:
            return JSONResponse(
                {'ok': False,
                 'error': '原件字节缺失：file {}'.format(row['id'])},
                status_code=409)
        path = os.path.join(in_dir, name)
        with open(path, 'wb') as fo:
            fo.write(s['data'])
        paths.append(path)
        ctx.append({'name': name, 'path': path,
                    'file_id': row['id'], 'sha256': row['sha256'],
                    'dedup': True})
    return _launch(paths, params, warns, ctx, 'preview', tpl)


if __name__ == '__main__':
    import uvicorn
    print('>> 结构化平台 启动： http://{}:{}'.format(config.HOST, config.PORT))
    print('>> 存储：DB 唯一事实源 · {}'.format(
        _load('store.db').safe_detail(config.PLATFORM_DB_REF)))
    uvicorn.run(app, host=config.HOST, port=config.PORT,
                log_level='warning')