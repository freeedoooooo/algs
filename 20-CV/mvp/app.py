"""
mvp/app.py — Web 工具入口（FastAPI + uvicorn）。只负责路由与任务编排。

启动：
    D:\\miniforge3\\envs\\paddle\\python.exe mvp/app.py
    浏览器打开 http://127.0.0.1:8765

路由：
    GET  /              提取页（assets/upload.html + /static 资源）
    GET  /sources       资料库页 · GET /runs 运行页 · GET /staging 暂存只读视图
    GET  /healthz       健康检查
    POST /api/upload    上传（base64 JSON，不依赖 python-multipart）
    GET  /api/status    处理进度
    GET  /extract-report   对照报告（重定向到最新 case 的报告真实地址）
    /files/<path>       各 case 的产物（白名单，raw 403）
    /srcfiles/<path>    资料库规范副本（缩略图/原件预览）
    /static/<path>      页面 css / js

提取逻辑在 pipeline/，对照报告生成在 extract_report/，配置在 config.py。
"""
import os
import re
import sys
import time
import json
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

# ★ 零 IDE 配置的关键：mvp 内部模块一律以「包」方式加载。
# 静态分析器能直接解析包内相对导入（from .. import config），不需要标记
# Sources Root / extraPaths；同时下面四种启动方式都成立：
#   python app.py · python mvp/app.py · uvicorn app:app · uvicorn mvp.app:app
# 包名从目录名动态取，整个目录拷走改名也照样能跑。
ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name):
    """以 <包名>.<name> 加载 mvp 内部模块，保证包内相对导入始终有效。"""
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
    部署时若想「启动即加载」，设 CV_MVP_WARMUP=1，避免第一个请求等 20~40s；
    代价是启动变慢、内存常驻。两种启动方式（app.py / uvicorn app:app）都生效。
    """
    if config.WARMUP_ON_START:
        engines = _load('pipeline.engines')
        engines.ocr()
        engines.structure()
        print('>> 模型预热完成（PaddleOCR + PPStructureV3）')
    yield


app = FastAPI(title='结构化平台', version='0.1', lifespan=lifespan)

# ---- output 静态白名单：页面只见预生成的自有标准视图 ----
# raw/（引擎原样）与旧 result.json 一律 403 —— 引擎结构不出适配层（防方案抄袭）。
_TOP_FILES = {config.EXTRACT_JSON, config.RECORDS_JSON, config.RUN_JSON,
              config.BOXES_NAME, config.EXTRACT_REPORT_NAME, 'index.html'}
_IMAGE_SRCS = {'source' + e for e in config.IMAGE_EXTS}
_CSV_PATTERNS = ('table_*.csv', 'stitched_*.csv', 'p*_table_*.csv')


def _files_guard(rel):
    """白名单校验：None=放行，否则 HTTP 状态码（file/db 两种服务方式共用）。"""
    head = rel.split('/')[0]
    if head == 'raw' or rel == 'result.json':
        return 403
    ok = (rel in _TOP_FILES
          or (rel.startswith('pages/') and rel.endswith('.png'))
          or rel in _IMAGE_SRCS
          or (rel.endswith('.md') and '/' not in rel)
          or any(fnmatch(rel, p) for p in _CSV_PATTERNS))
    return None if ok else 404


class OutputFiles(StaticFiles):
    async def get_response(self, path, scope):
        norm = unquote(path).replace('\\', '/')
        parts = [p for p in norm.split('/') if p not in ('', '.')]
        if '..' in parts:
            return PlainTextResponse('403 Forbidden', status_code=403)
        rel = '/'.join(parts[1:])          # 首段是批次目录名
        code = _files_guard(rel)
        if code:
            msg = ('403 Forbidden（引擎原始层不对外）' if code == 403
                   else '404 Not Found')
            return PlainTextResponse(msg, status_code=code)
        return await super().get_response(path, scope)


def _artifact_response(path, request, sources=False):
    """db 模式的 /files、/srcfiles：BLOB 流式输出，白名单与 raw 403 不变，
    ETag=sha256（内容变才变），If-None-Match 命中回 304。"""
    norm = unquote(path).replace('\\', '/')
    parts = [p for p in norm.split('/') if p not in ('', '.')]
    if not parts or '..' in parts:
        return PlainTextResponse('403 Forbidden', status_code=403)
    if sources:
        case_rel, rel = 'sources', '/'.join(parts)
    else:
        if len(parts) < 2:
            return PlainTextResponse('404 Not Found', status_code=404)
        case_rel, rel = parts[0], '/'.join(parts[1:])
        code = _files_guard(rel)
        if code:
            msg = ('403 Forbidden（引擎原始层不对外）' if code == 403
                   else '404 Not Found')
            return PlainTextResponse(msg, status_code=code)
    try:
        a = _load('store.artifact').get(case_rel, rel)
    except Exception as e:
        return _db_unavailable(e)
    if a is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    etag = '"{}"'.format(a['sha'])
    if request.headers.get('if-none-match') == etag:
        return Response(status_code=304, headers={'ETag': etag})
    return Response(a['data'], media_type=a['mime'], headers={'ETag': etag})


if config.ARTIFACT_STORE == 'db':
    @app.get('/files/{path:path}')
    def files_db(path: str, request: Request):
        return _artifact_response(path, request)

    @app.get('/srcfiles/{path:path}')
    def srcfiles_db(path: str, request: Request):
        return _artifact_response(path, request, sources=True)
else:
    app.mount('/files', OutputFiles(directory=config.OUTPUT_DIR), name='files')
    # 资料库规范副本（sources/）：资料页/选择抽屉的缩略图与原件预览。
    # 目录里只有登记过的上传副本，无引擎产物，直接静态服务即可。
    app.mount('/srcfiles', StaticFiles(directory=config.SOURCES_DIR),
              name='srcfiles')
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
    'steps': [], 'cases': [], 'batch': None,
    'started': None, 'elapsed': 0,
    'params': {}, 'warnings': [],
    'logs': [], 'progress': 0, 'stage': '',
    'log_file': None,
    'mode': 'preview', 'template': None, 'run_id': None,
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
    """RunLog 每条日志同步进 STATE，页面轮询 /api/status 即可看到。"""
    with LOCK:
        STATE['logs'].append(row)
        STATE['stage'] = row['stage']


def safe_name(name):
    """只替换 Windows 文件名非法字符，保留中文与空格。"""
    name = os.path.basename(name or 'upload.bin')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip()
    return name[:120] or 'upload.bin'


def batch_tag():
    """
    本次上传的批次前缀：YYYYMMDDHHmmss（例 20261116160231）。

    input/ 与 output/ 共用它，所以重复传同一个文件也不会覆盖上一次的产物，
    目录按字典序排就是按时间排。同一秒内再传一次加 -2 / -3 区分。
    注意：只加前缀，原文件名（含 103_ 这类数字编号）一字不改。
    """
    if config.ARTIFACT_STORE == 'db':
        existing = set(_load('store.catalog').list_batch_tags())
    else:
        existing = (set(os.listdir(config.INPUT_DIR))
                    | set(os.listdir(config.OUTPUT_DIR)))
    tag = time.strftime(config.BATCH_TS_FMT, time.localtime())
    if not any(n.startswith(tag) for n in existing):
        return tag
    i = 2
    while any(n.startswith('{}-{}'.format(tag, i)) for n in existing):
        i += 1
    return '{}-{}'.format(tag, i)


def case_dir_name(name):
    """输出目录名 = 带时间戳的输入文件名去掉后缀，与 input/ 一一对应。"""
    stem = os.path.splitext(name)[0]
    stem = re.sub(r'[^\w\u4e00-\u9fff.-]', '_', stem)
    return stem[:config.CASE_NAME_MAX] or 'case'


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


def _register_source(name, data):
    """sha256 去重登记 + sources 规范副本（方案 A：库副本与批次副本分离）。

    file 模式：副本落 sources/，DB 不可用只影响登记（id=None），提取照常。
    db 模式：副本入 BLOB，DB 必选，失败上抛（调用方回 503）。
    """
    sha = hashlib.sha256(data).hexdigest()
    base = '{}_{}'.format(sha[:8], name)
    rel = 'sources/' + base
    if config.ARTIFACT_STORE == 'db':
        _load('store.artifact').save('sources', base, data)
        sid, dedup = _load('store.catalog').register_source(
            name, _kind_of(name), len(data), sha, rel)
        return {'source_file_id': sid, 'sha256': sha, 'dedup': dedup,
                'rel_path': rel}
    abs_path = config.to_abs(rel)
    if not os.path.isfile(abs_path):
        with open(abs_path, 'wb') as f:
            f.write(data)
    sid, dedup = None, False
    try:
        sid, dedup = _load('store.catalog').register_source(
            name, _kind_of(name), len(data), sha, rel)
    except Exception:
        pass
    return {'source_file_id': sid, 'sha256': sha, 'dedup': dedup,
            'rel_path': rel}


def _resolve_template(version_id=None):
    """模板版本解析；file 模式 DB 不可用降级为内置「原始透传」；
    db 模式 DB 必选，失败上抛。"""
    try:
        catalog = _load('store.catalog')
        tv = (catalog.get_template_version(version_id=version_id)
              if version_id else catalog.get_template_version())
        if tv:
            return {'name': tv['name'], 'version': tv['version'],
                    'version_id': tv['id']}
        err = '平台库无可用模板版本'
    except Exception as e:
        err = str(e)
    if config.ARTIFACT_STORE == 'db':
        raise RuntimeError(err)
    return {'name': '原始透传', 'version': 1, 'version_id': None}


@app.get('/', response_class=HTMLResponse)
def index():
    return HTMLResponse(asset('upload.html'))


@app.get('/sources', response_class=HTMLResponse)
def sources_page():
    return HTMLResponse(asset('sources.html'))


@app.get('/runs', response_class=HTMLResponse)
def runs_page():
    return HTMLResponse(asset('runs.html'))


@app.get('/staging', response_class=HTMLResponse)
def staging_page():
    return HTMLResponse(asset('staging.html'))


@app.get('/healthz')
def health():
    return {'ok': True, 'service': 'cv-mvp', 'running': STATE['running']}


@app.get('/api/params')
def api_params():
    """返回参数 schema（顺序=优先级）与当前默认值，上传页据此渲染面板。"""
    return {'schema': params_mod.public_schema(),
            'defaults': params_mod.defaults()}


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

    try:
        tag = batch_tag()
    except Exception as e:
        return _db_unavailable(e)
    # db 模式输入副本只落临时 scratch（字节事实源在 sources BLOB），跑完即清
    in_dir = (tempfile.mkdtemp(prefix='cv_in_')
              if config.ARTIFACT_STORE == 'db' else config.INPUT_DIR)
    paths, used, ctx = [], set(), []
    for item in files:
        name = safe_name(item.get('name', ''))
        ext = os.path.splitext(name)[1].lower()
        if ext not in config.ALLOWED_EXTS:
            return JSONResponse(
                {'ok': False, 'error': '不支持的格式：{}'.format(ext)},
                status_code=400)
        # 同一批里出现重名文件时加 -2 区分，避免后一个把前一个覆盖掉
        if name in used:
            stem, e = os.path.splitext(name)
            k = 2
            while '{}-{}{}'.format(stem, k, e) in used:
                k += 1
            name = '{}-{}{}'.format(stem, k, e)
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
        path = os.path.join(in_dir, '{}_{}'.format(tag, name))
        with open(path, 'wb') as f:
            f.write(data)
        paths.append(path)
        try:
            info = _register_source(name, data)
        except Exception as e:
            return _db_unavailable(e)
        ctx.append(dict(info, name=name, path=path))

    return _launch(tag, paths, params, warns, ctx, mode, tpl)


def _launch(tag, paths, params, warns, ctx, mode='preview', tpl=None):
    """建日志 → 重置 STATE → 登记 Run → 起后台线程。
    file 模式 DB 登记可降级；db 模式 DB 必选（登记失败整批 503）。"""
    tpl = tpl or _resolve_template()
    runlog = _load('runlog')
    content = _load('store.content')
    log = runlog.RunLog(tag, log_path=os.path.join(config.LOG_DIR,
                                                   tag + '.log'),
                        on_emit=_on_log)
    run_ctx = {'batch': tag, 'mode': mode, 'template': tpl,
               'run_id': None, 'files': ctx, 'created_at': _now()}
    if config.ARTIFACT_STORE == 'db' and paths:
        run_ctx['in_scratch'] = os.path.dirname(paths[0])
    for f in ctx:
        # case 目录名与 input 批次副本同名（带批次戳）：重跑=新目录，旧批次不动
        f['case'] = case_dir_name('{}_{}'.format(tag, f['name']))
        f['state'] = 'pending'
    # DB 目录登记（file 模式降级隔离：失败只记 warning，提取与文件链路照常）
    try:
        catalog = _load('store.catalog')
        if tpl.get('version_id'):
            run_ctx['run_id'] = catalog.create_run(
                tag, mode, tpl['version_id'], params)
            for f in ctx:
                if f.get('source_file_id'):
                    f['run_file_id'] = catalog.add_run_file(
                        run_ctx['run_id'], f['source_file_id'],
                        'output/{}'.format(f['case']))
    except Exception as e:
        if config.ARTIFACT_STORE == 'db':
            return _db_unavailable(e)
        log.warn('store', '平台库不可用，本次运行仅文件留档（降级）：{}'
                 .format(e))
    if config.ARTIFACT_STORE == 'db' and (
            run_ctx['run_id'] is None
            or any(not f.get('run_file_id') for f in ctx)):
        return JSONResponse(
            {'ok': False, 'error': '目录登记不完整（产物 db 模式 DB 必选）'},
            status_code=503)
    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], batch=tag, started=time.time(), elapsed=0,
                     params={k: v for k, v in params.items()
                             if not k.startswith('_')}, warnings=warns,
                     logs=[], progress=0, stage='batch',
                     log_file='{}.log'.format(tag),
                     mode=mode, template=tpl, run_id=run_ctx['run_id'])
    log.stage('batch', '批次 {} · 收到 {} 个文件 · 模式 {} · 模板 {} v{}'.format(
        tag, len(paths), mode, tpl['name'], tpl['version']))
    log.info('params', '生效参数：{}'.format(
        ', '.join('{}={}'.format(k, v) for k, v in params.items()
                  if not k.startswith('_'))))
    for w in warns:
        log.warn('params', w)
    try:
        _save_run_snapshot(run_ctx, 'extracting', content)
    except Exception as e:
        return _db_unavailable(e)
    threading.Thread(target=run_batch, args=(paths, params, log, run_ctx),
                     daemon=True).start()
    return {'ok': True, 'count': len(paths), 'batch': tag,
            'run_id': run_ctx['run_id'], 'warnings': warns}


def _save_run_snapshot(run_ctx, state, content=None, error=None):
    """run.json 批次快照：每个 case 各留一份（file=磁盘自包含 / db=BLOB）。"""
    content = content or _load('store.content')
    doc = {
        'schema': 'c1-extract-run/1',
        'batch_tag': run_ctx['batch'], 'mode': run_ctx['mode'],
        'template': run_ctx['template'], 'run_id': run_ctx['run_id'],
        'params': STATE.get('params') or {},
        'state': state, 'error': error,
        'files': [{'name': f['name'], 'case': f.get('case'),
                   'state': f.get('state', 'pending'),
                   'source_file_id': f.get('source_file_id'),
                   'run_file_id': f.get('run_file_id'),
                   'records_n': f.get('records_n')}
                  for f in run_ctx['files']],
        'created_at': run_ctx['created_at'], 'updated_at': _now(),
    }
    for f in run_ctx['files']:
        if f.get('case'):
            content.save_run(f['case'], doc)


@app.get('/api/status')
def status():
    with LOCK:
        return dict(STATE)


@app.get('/api/logs')
def api_logs():
    """下载当前批次的纯文本运行日志（结构化日志在 /api/status 的 logs 里）。"""
    rel = STATE.get('log_file')
    path = os.path.join(config.LOG_DIR, rel) if rel else None
    if not path or not os.path.isfile(path):
        return JSONResponse({'ok': False, 'error': '暂无日志'}, status_code=404)
    return FileResponse(path, media_type='text/plain; charset=utf-8',
                        filename='{}.log'.format(STATE.get('batch') or 'run'))


@app.get('/extract-report')
def extract_report():
    """对照报告：重定向到最新 case 的 对照报告.html 真实地址（/files/<case>/…）。
    报告内资源全是相对路径，必须落在 case 目录的 URL 下才能解析；
    file 模式历史批次可 file:// 直开，db 模式用 export_artifacts.py 按需导出。"""
    from urllib.parse import quote
    if config.ARTIFACT_STORE == 'db':
        try:
            artifact = _load('store.artifact')
            for name, _tag in _load('store.catalog').list_run_cases():
                if artifact.exists(name, config.EXTRACT_REPORT_NAME):
                    return RedirectResponse('/files/{}/{}'.format(
                        quote(name, safe=''),
                        quote(config.EXTRACT_REPORT_NAME, safe='')))
        except Exception as e:
            return _db_unavailable(e)
    else:
        for name in sorted(os.listdir(config.OUTPUT_DIR), reverse=True):
            path = os.path.join(config.OUTPUT_DIR, name,
                                config.EXTRACT_REPORT_NAME)
            if os.path.isfile(path):
                return RedirectResponse('/files/{}/{}'.format(
                    quote(name, safe=''),
                    quote(config.EXTRACT_REPORT_NAME, safe='')))
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


def _ingest_case(case_rel, case_abs):
    """db 模式：scratch 目录全量产物入 extract_artifact（管线/报告生成零改动，
    它们照旧写文件，这里统一收编入库）。"""
    artifact = _load('store.artifact')
    for root, _, files in os.walk(case_abs):
        for fn in files:
            if fn.endswith('.tmp'):
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, case_abs).replace(os.sep, '/')
            with open(p, 'rb') as f:
                artifact.save(case_rel, rel, f.read())


def run_batch(paths, params=None, log=None, run_ctx=None):
    """后台线程：逐个提取 → raw/ + extract.json → collect 记录入库 → 对照报告。
    file 模式 DB 状态同步降级隔离；db 模式 DB 必选（写失败整批 failed），
    产物先写 scratch 再 ingest 入 BLOB，跑完清理 scratch。"""
    run_ctx = run_ctx or {'batch': STATE.get('batch'), 'mode': 'preview',
                          'template': _resolve_template(), 'run_id': None,
                          'files': [{'name': os.path.basename(p), 'path': p}
                                    for p in paths],
                          'created_at': _now()}
    content = _load('store.content')
    collect = _load('collect')
    catalog = None
    try:
        catalog = _load('store.catalog')
    except Exception:
        pass

    def db(fn_name, *a):
        if catalog is None or run_ctx.get('run_id') is None:
            return
        try:
            getattr(catalog, fn_name)(*a)
        except Exception as e:
            log.warn('store', '目录同步失败（降级）：{}'.format(e))

    try:
        def progress(v):
            with LOCK:
                STATE['progress'] = v

        log.stage('load', '加载提取流水线（首次会导入 cv2 / pdfplumber）…')
        progress(1)
        pipeline = _load('pipeline')
        report_mod = _load('extract_report.builder')
        records = []
        total = len(paths)
        for i, path in enumerate(paths, 1):
            name = os.path.basename(path)
            fc = next((f for f in run_ctx['files']
                       if f.get('name') == name or f.get('path') == path),
                      {})
            log.stage('case', '[{}/{}] 开始处理 {}'.format(i, total, name))
            progress(int((i - 1) / total * 100))
            case_rel = fc.get('case') or case_dir_name(name)
            fc['case'] = case_rel
            if config.ARTIFACT_STORE == 'db':
                # 磁盘只是 scratch（paddle 需要真实图片路径），产物最终入 BLOB
                case_abs = fc.get('scratch') or tempfile.mkdtemp(
                    prefix='cv_case_')
                fc['scratch'] = case_abs
            else:
                case_abs = os.path.join(config.OUTPUT_DIR, case_rel)
            os.makedirs(case_abs, exist_ok=True)
            frac = [0.0]

            def emit(level, stage, msg, _i=i, _frac=frac, **kw):
                f = _STAGE_FRAC.get((stage, level))
                if f is not None and f > _frac[0]:
                    _frac[0] = f
                    with LOCK:
                        STATE['progress'] = int((_i - 1 + f) / total * 100)
                log.emit(level, stage, msg, **kw)

            if fc.get('run_file_id'):
                db('set_run_file_state', fc['run_file_id'], 'extracting')
            rec = pipeline.extract_one(path, case_abs, case_rel, params,
                                       emit=emit)
            records.append(rec)
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
            # 断库时引擎产物（extract+报告）仍完整，运行显式 failed
            report_mod.build([rec],
                             os.path.join(case_abs, config.EXTRACT_REPORT_NAME),
                             params=params)
            # L2 记录层：passthrough 收集 + 逐格血缘 → DB 三表（db 模式事实源）
            tpl = run_ctx['template']
            recs = collect.passthrough(rec)
            rdoc = collect.build_records_doc(
                rec, recs, run_id=run_ctx.get('run_id'),
                run_file_id=fc.get('run_file_id'),
                source_file_id=fc.get('source_file_id'),
                template={'name': tpl['name'], 'version': tpl['version']})
            content.save_records(case_rel, rdoc)
            fc['records_n'] = len(recs)
            fc['state'] = 'previewed'
            log.ok('collect', '暂存记录 {} 条（passthrough · 逐格血缘）'.format(
                len(recs)), case=name)
            if fc.get('run_file_id'):
                db('set_run_file_state', fc['run_file_id'], 'previewed')
            if config.ARTIFACT_STORE == 'db':
                _ingest_case(case_rel, case_abs)
                shutil.rmtree(case_abs, ignore_errors=True)
                fc.pop('scratch', None)
            progress(int(i / total * 100))
        db('set_run_state', run_ctx.get('run_id'), 'previewed')
        _save_run_snapshot(run_ctx, 'previewed', content)
        # 完成态最后发布：status 变 running=False 时 run.json 必已落盘
        with LOCK:
            STATE.update(running=False, ready=True,
                         cases=[{'file': r['file']['name'], 'case': r['case'],
                                 'records_n': next(
                                     (f.get('records_n') for f in run_ctx['files']
                                      if f.get('case') == r['case']), None)}
                                for r in records],
                         elapsed=round(time.time()
                                       - (STATE['started'] or time.time()), 1),
                         progress=100, stage='done')
        log.ok('done', '完成，共 {} 个文件，耗时 {}s'.format(
            len(records), STATE['elapsed']))
    except Exception as e:
        if log:
            log.error('error', '出错：' + str(e))
            log.error('error', traceback.format_exc(limit=3).strip())
        db('set_run_state', run_ctx.get('run_id'), 'failed', str(e))
        try:
            _save_run_snapshot(run_ctx, 'failed', content, error=str(e))
        except Exception as e2:
            if log:
                log.warn('store', 'run.json 写入失败：{}'.format(e2))
        with LOCK:
            STATE.update(running=False, ready=False, error=str(e),
                         stage='error')
        print(traceback.format_exc(limit=3))
    finally:
        if config.ARTIFACT_STORE == 'db':
            for f in run_ctx.get('files') or []:
                if f.get('scratch'):
                    shutil.rmtree(f['scratch'], ignore_errors=True)
            if run_ctx.get('in_scratch'):
                shutil.rmtree(run_ctx['in_scratch'], ignore_errors=True)


# ---- 数据链路 API（P0：资料库 / 模板 / 运行 / 预生成内容读取）----
# 目录端点经 catalog repo（DB 故障回 503）；内容端点经 content/artifact repo：
# file 模式读磁盘不依赖 DB，db 模式 DB 必选（故障回 503）。
# 运行以 batch_tag 为键（run.json 留档，DB id 在其中可查）。

def _db_unavailable(e):
    return JSONResponse({'ok': False, 'error': '平台库不可用：{}'.format(e)},
                        status_code=503)


@app.get('/api/sources')
def api_sources(q: str = None, kind: str = None, tag: str = None, page: int = 1):
    try:
        return _load('store.catalog').list_sources(q, kind, tag, page)
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
        info = _register_source(name, data)
    except Exception as e:
        return _db_unavailable(e)
    if info['source_file_id'] is None:
        return _db_unavailable('登记失败')
    return {'ok': True, 'id': info['source_file_id'], 'dedup': info['dedup']}


@app.delete('/api/sources/{source_id}')
def api_sources_del(source_id: int):
    try:
        catalog = _load('store.catalog')
        row = catalog.get_source(source_id)
        ok, reason = catalog.delete_source(source_id)
    except Exception as e:
        return _db_unavailable(e)
    if not ok:
        return JSONResponse({'ok': False, 'reason': reason}, status_code=409)
    if row and row.get('rel_path'):
        try:
            if config.ARTIFACT_STORE == 'db':
                _load('store.artifact').delete(
                    'sources', os.path.basename(row['rel_path']))
            else:
                p = config.to_abs(row['rel_path'])
                if os.path.isfile(p):
                    os.remove(p)
        except Exception as e:
            return _db_unavailable(e)
    return JSONResponse({'ok': True}, status_code=200)


@app.get('/api/templates')
def api_templates():
    try:
        return {'items': _load('store.catalog').list_templates()}
    except Exception:
        return {'items': [{'id': None, 'name': '原始透传', 'current_version': 1,
                           'description': '平台库未连接，降级默认模板'}],
                'degraded': True}


def _batch_cases(batch):
    """按 batch_tag 找各 case 的 run.json（file=扫磁盘 / db=目录 join + BLOB）。"""
    if config.ARTIFACT_STORE == 'db':
        content = _load('store.content')
        out = []
        for name, tag in _load('store.catalog').list_run_cases():
            if tag != batch:
                continue
            doc = content.get_run(name)
            if doc:
                out.append((name, doc))
        return out
    out = []
    if not os.path.isdir(config.OUTPUT_DIR):
        return out
    for name in sorted(os.listdir(config.OUTPUT_DIR)):
        p = os.path.join(config.OUTPUT_DIR, name, config.RUN_JSON)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding='utf-8') as f:
                doc = json.load(f)
        except Exception:
            continue
        if doc.get('batch_tag') == batch:
            out.append((name, doc))
    return out


@app.get('/api/runs')
def api_runs():
    """运行列表：file=扫 output/*/run.json（停 MySQL 照常）；
    db=目录 join + run.json BLOB，按批次去重（DB 故障 503）。"""
    seen = {}
    if config.ARTIFACT_STORE == 'db':
        try:
            content = _load('store.content')
            for name, _tag in _load('store.catalog').list_run_cases():
                doc = content.get_run(name)
                tag = (doc or {}).get('batch_tag')
                if tag and tag not in seen:
                    seen[tag] = doc
        except Exception as e:
            return _db_unavailable(e)
        return {'items': list(seen.values())}
    if os.path.isdir(config.OUTPUT_DIR):
        for name in sorted(os.listdir(config.OUTPUT_DIR), reverse=True):
            p = os.path.join(config.OUTPUT_DIR, name, config.RUN_JSON)
            if not os.path.isfile(p):
                continue
            try:
                with open(p, encoding='utf-8') as f:
                    doc = json.load(f)
            except Exception:
                continue
            tag = doc.get('batch_tag')
            if tag and tag not in seen:
                seen[tag] = doc
    return {'items': list(seen.values())}


@app.get('/api/runs/{batch}')
def api_run_detail(batch: str):
    try:
        cases = _batch_cases(batch)
    except Exception as e:
        return _db_unavailable(e)
    if not cases:
        return JSONResponse({'ok': False, 'error': '批次不存在'},
                            status_code=404)
    doc = cases[0][1]
    live = None
    with LOCK:
        if STATE.get('batch') == batch:
            live = {'running': STATE['running'], 'progress': STATE['progress'],
                    'stage': STATE['stage'], 'error': STATE['error']}
    return {'run': doc, 'live': live}


def _case_of(batch, file):
    cases = _batch_cases(batch)
    if not cases:
        return None
    if file:
        return next((c for c, _ in cases if c == file), None)
    return cases[0][0]


@app.get('/api/runs/{batch}/extract')
def api_run_extract(batch: str, file: str = None):
    try:
        case = _case_of(batch, file)
        doc = _load('store.content').get_extract(case) if case else None
    except Exception as e:
        return _db_unavailable(e)
    if doc is None:
        return JSONResponse({'ok': False, 'error': 'extract.json 不存在'},
                            status_code=404)
    return doc


@app.get('/api/runs/{batch}/staging')
def api_run_staging(batch: str, file: str = None):
    try:
        case = _case_of(batch, file)
        doc = _load('store.content').get_records(case) if case else None
    except Exception as e:
        return _db_unavailable(e)
    if doc is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    return doc


@app.get('/api/staging/query')
def api_staging_query(field: str = None, q: str = None,
                      batch: str = None, state: str = None):
    """跨批暂存查询（选项 B）：DB 直查 field 投影；未启用 / DB down → 503。"""
    if config.RECORDS_STORE != 'db':
        return JSONResponse(
            {'ok': False, 'error': '跨批查询需 CV_MVP_RECORDS_STORE=db'},
            status_code=503)
    try:
        rows = _load('store.content_db').query_fields(field, q, batch, state)
    except Exception as e:
        return _db_unavailable(e)
    return {'ok': True, 'items': rows}


@app.post('/api/runs')
async def api_runs_create(request: Request):
    """从资料库选文件发起运行（复用上传编排；登记过的文件不重复收 base64）。"""
    if STATE['running']:
        return JSONResponse({'ok': False, 'error': '已有任务正在处理'},
                            status_code=409)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': '请求体不是合法 JSON'},
                            status_code=400)
    ids = body.get('source_file_ids') or []
    if not ids:
        return JSONResponse({'ok': False, 'error': '未选择文件'},
                            status_code=400)
    try:
        catalog = _load('store.catalog')
        rows = [catalog.get_source(int(i)) for i in ids]
    except Exception as e:
        return _db_unavailable(e)
    if any(r is None for r in rows):
        return JSONResponse({'ok': False, 'error': '存在未登记的文件 id'},
                            status_code=400)
    params, warns = params_mod.normalize(body.get('params'))
    try:
        tpl = _resolve_template(body.get('template_version_id'))
        tag = batch_tag()
    except Exception as e:
        return _db_unavailable(e)
    in_dir = (tempfile.mkdtemp(prefix='cv_in_')
              if config.ARTIFACT_STORE == 'db' else config.INPUT_DIR)
    paths, used, ctx = [], set(), []
    for row in rows:
        name = row['name']
        if name in used:
            stem, e = os.path.splitext(name)
            k = 2
            while '{}-{}{}'.format(stem, k, e) in used:
                k += 1
            name = '{}-{}{}'.format(stem, k, e)
        used.add(name)
        if config.ARTIFACT_STORE == 'db':
            try:
                a = _load('store.artifact').get(
                    'sources', os.path.basename(row['rel_path']))
            except Exception as e:
                return _db_unavailable(e)
            if a is None:
                return JSONResponse(
                    {'ok': False,
                     'error': '规范副本缺失：{}'.format(row['rel_path'])},
                    status_code=409)
            data = a['data']
        else:
            src = config.to_abs(row['rel_path'])
            if not os.path.isfile(src):
                return JSONResponse(
                    {'ok': False,
                     'error': '规范副本缺失：{}'.format(row['rel_path'])},
                    status_code=409)
            with open(src, 'rb') as fi:
                data = fi.read()
        path = os.path.join(in_dir, '{}_{}'.format(tag, name))
        with open(path, 'wb') as fo:
            fo.write(data)
        paths.append(path)
        ctx.append({'name': name, 'path': path,
                    'source_file_id': row['id'], 'sha256': row['sha256'],
                    'dedup': True, 'rel_path': row['rel_path']})
    return _launch(tag, paths, params, warns, ctx, 'preview', tpl)


if __name__ == '__main__':
    import uvicorn
    print('>> 结构化平台 启动： http://{}:{}'.format(config.HOST, config.PORT))
    print('>> 输入目录：{}'.format(config.INPUT_DIR))
    print('>> 产物目录：{}'.format(config.OUTPUT_DIR))
    uvicorn.run(app, host=config.HOST, port=config.PORT,
                log_level='warning')
