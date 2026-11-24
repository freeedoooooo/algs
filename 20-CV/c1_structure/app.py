"""
c1_structure/app.py — Web 工具入口（FastAPI + uvicorn）。只负责 HTTP 路由与请求校验；
运行引擎与共享运行状态（STATE/LOCK、task_batch）在 service.py。

启动：
    D:\\miniforge3\\envs\\paddle\\python.exe c1_structure/app.py
    浏览器打开 http://127.0.0.1:8765

路由（页面地址＝产品名词，与 web/ 文件一一对应）：
    GET  /              工作台首页（web/home.html）
    GET  /sources       资料清单（唯一功能入口） · /parse 解析 · /extract 抽取规则
    GET  /preview       资料数据预览（preview.html，二级页）
    GET  /review        校验壳页 · /rules 入库规则 · /dashboard 数据看板
    GET  /healthz       健康检查
    POST /api/upload    上传解析（base64 JSON；单文件）
    GET  /api/status    处理进度
    GET  /parse-report   对照报告（重定向到最新资料的报告真实地址）
    /files/<file_id>/<path>   产物（DB BLOB，白名单，raw 403）
    /srcfiles/<file_id>       原件（c1_doc_file.content BLOB）
    /static/<path>      页面 css / js

模型：一条资料记录 = 一次运行（单文件，file_id 为唯一主键）；无 task 概念。
全部流程 API 收敛在 /api/sources/{file_id}/... 下；配置 API 见 /api/extract-rules
与 /api/load/*。存储契约：DB 唯一事实源，原件字节 c1_doc_file.content，
产物字节 c1_parse_artifact（file_id 粒度）；磁盘仅 tmp/ 运行期 scratch。
DB 不可用显式 503/failed，不降级。
审计/file:// 用 export_artifacts.py。解析逻辑在 pipeline/，报告在 parse_report/。
"""
import base64
import importlib
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
from fnmatch import fnmatch
from urllib.parse import unquote

# ★ 零 IDE 配置的关键：内部模块一律以「包」方式加载。
# 静态分析器能直接解析包内相对导入（from .. import config），不需要标记
# Sources Root / extraPaths；同时下面四种启动方式都成立：
#   python app.py · python c1_structure/app.py · uvicorn app:app · uvicorn c1_structure.app:app
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


config = _load('config')  # 必须在 paddle 相关导入之前：设置模型源环境变量
params_mod = _load('params')  # 调试参数 schema / 校验（纯 Python，不碰模型）
service = _load('service')  # 运行引擎：STATE/LOCK、launch、task_batch
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import (HTMLResponse, JSONResponse, FileResponse,
                               RedirectResponse, PlainTextResponse, Response)
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(_app):
    """
    默认什么都不做 —— 模型保持懒加载，服务启动约 0.5s。
    部署时若想「启动即加载」，设 C1_STRUCTURE_WARMUP=1，避免第一个请求等 20~40s；
    代价是启动变慢、内存常驻。两种启动方式（app.py / uvicorn app:app）都生效。
    """
    try:
        _load('store.catalog').ensure_default_datasource()
    except Exception:
        pass  # 尽力而为补种「产品库」默认行：断库启动不炸，页面可手建
    if config.WARMUP_ON_START:
        engines = _load('pipeline.engines')
        engines.ocr()
        engines.structure()
        print('>> 模型预热完成（PaddleOCR + PPStructureV3）')
    yield


app = FastAPI(title='结构化平台', version='0.1', lifespan=lifespan)
# 响应压缩（2026-11-21 性能轮）：报告 HTML 均值 530KB/最大 1.9MB、
# 记录 JSON ~150KB，远端访问下文本 1KB 起压可省 ~85% 传输。
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ---- 错误分类：业务错误类型化（StoreError.code→HTTP），DB 故障 503，
# 编程错误 500（uvicorn 记 traceback）。不再把一切异常伪装成「平台库不可用」。----
store_errors = _load('store.errors')


@app.exception_handler(store_errors.StoreError)
async def store_error_handler(_request, exc):
    return JSONResponse({'ok': False, 'error': exc.msg}, status_code=exc.code)


@app.exception_handler(Exception)
async def fallback_error_handler(_request, exc):
    import pymysql
    if isinstance(exc, (pymysql.MySQLError, OSError, LookupError)):
        print('>> 平台库不可用：{}: {}'.format(type(exc).__name__, exc))
        return JSONResponse({'ok': False, 'error': '平台库不可用'},
                            status_code=503)
    return JSONResponse({'ok': False, 'error': '服务器内部错误'},
                        status_code=500)


# ---- 产物白名单：页面只见预生成的自有标准视图 ----
# raw/（引擎原样）与旧 result.json 一律 403 —— 引擎结构不出适配层（防方案抄袭）。
_TOP_FILES = {config.PARSE_JSON, config.BOXES_NAME,
              config.PARSE_REPORT_NAME, 'index.html'}
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
    """/files/<file_id>/<产物相对路径>：白名单 + raw 403。"""
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
    a = _load('store.artifact').get(int(parts[0]), rel)
    if a is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    return _blob_response(a['data'], a['mime'], a['sha'], request)


@app.get('/srcfiles/{file_id:int}')
def srcfiles_db(file_id: int, request: Request, download: int = 0):
    """/srcfiles/<file_id>：原件字节（c1_doc_file.content）。
    用 id 不用名字——同名不同字节是两行，名字会撞。
    ?download=1 时加 Content-Disposition: attachment 触发下载。"""
    s = _load('store.catalog').get_file_content(file_id)
    if s is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    mime = _load('store.artifact').mime_of(s['name'])
    if download:
        from urllib.parse import quote
        resp = _blob_response(s['data'], mime, s['sha'], request)
        resp.headers['Content-Disposition'] = (
            "attachment; filename*=UTF-8''" + quote(s['name']))
        return resp
    return _blob_response(s['data'], mime, s['sha'], request)


app.mount('/static', StaticFiles(directory=config.WEB_DIR), name='static')


@app.middleware('http')
async def no_cache(request, call_next):
    """本地调试工具：禁止浏览器启发式缓存。StaticFiles/FileResponse 带 ETag/
    Last-Modified，no-cache 让每次使用前先校验（未变 304、变了 200），
    避免「改了 css/js 或重启服务后页面仍是旧样式」——缓存发生在浏览器侧，重启服务无效。"""
    resp = await call_next(request)
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


def asset(name):
    with open(os.path.join(config.WEB_DIR, name), 'r',
              encoding='utf-8') as f:
        return f.read()


@app.get('/', response_class=HTMLResponse)
def index():
    return HTMLResponse(asset('home.html'))


@app.get('/parse', response_class=HTMLResponse)
def parse_page():
    return HTMLResponse(asset('parse.html'))


@app.get('/sources', response_class=HTMLResponse)
def sources_page():
    return HTMLResponse(asset('sources.html'))


@app.get('/preview', response_class=HTMLResponse)
def preview_page():
    return HTMLResponse(asset('preview.html'))


@app.get('/review', response_class=HTMLResponse)
def review_page():
    """校验壳页：自动化校验待实现；记录核对入口在任务的数据预览。"""
    return HTMLResponse(asset('review_home.html'))


@app.get('/extract', response_class=HTMLResponse)
def extract_page():
    return HTMLResponse(asset('extract.html'))


@app.get('/rules', response_class=HTMLResponse)
def rules_page():
    return HTMLResponse(asset('rules.html'))


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard_page():
    """数据看板：分页查看业务表数据，按 record_id 跳预览做血缘回溯。"""
    return HTMLResponse(asset('dashboard.html'))


@app.get('/healthz')
def health():
    return {'ok': True, 'service': 'c1-structure',
            'running': service.STATE['running']}


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


async def _json_body(request):
    try:
        return await request.json()
    except Exception:
        raise store_errors.BadRequest('请求体不是合法 JSON')


def _reject_retired_load_keys(body):
    """P2c：上传不再携带入库目标。旧契约键显式 400（防旧浏览器缓存静默错行），
    目标改在 POST /api/sources/{id}/load 时选择。"""
    if any(k in body for k in ('mode', 'load_datasource_id', 'load_table_id')):
        raise store_errors.BadRequest(
            '上传不再携带入库目标，请在任务入库时选择')
    if 'rule_version_id' in body:
        raise store_errors.BadRequest(
            '上传不再选择抽取规则，请在「执行抽取」时选择')


@app.post('/api/upload')
async def upload(request: Request):
    if service.STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等待其完成'},
            status_code=409)
    body = await _json_body(request)
    _reject_retired_load_keys(body)
    files = body.get('files') or []
    if not files:
        return JSONResponse({'ok': False, 'error': '未收到文件'},
                            status_code=400)
    # 一条资料 = 一次运行（单文件）：兼容旧缓存前端的多选请求，只取第一个，
    # 把"忽略其余文件"作为 warning 回显，不让整次上传静默失败。
    extra_n = max(0, len(files) - 1)
    if extra_n:
        files = files[:1]
    # 调试参数：校验一次，非法值回退默认并把警告带回页面（不让整批失败）
    params, warns = params_mod.normalize(body.get('params'))
    if extra_n:
        warns.insert(0, '一次只解析一个文件，已忽略另外 {} 个文件'.format(extra_n))

    # 输入副本只落 tmp/input scratch（字节事实源在 c1_doc_file.content），跑完即清；
    # 任何失败路径（校验 400 / DB 503）都由 finally 回收，不留孤儿
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    launched = False
    try:
        paths, used, ctx = [], set(), []
        for item in files:
            name = service.safe_name(item.get('name', ''))
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
            info = service.register_file(name, data)
            ctx.append(dict(info, name=name, path=path))
        result = service.launch(paths, params, warns, ctx)
        launched = True
        return result
    finally:
        if not launched:
            service.rmtree_retry(in_dir)


@app.get('/api/status')
def status():
    with service.LOCK:
        return dict(service.STATE)


@app.get('/api/logs')
def api_logs():
    """下载当前任务的纯文本运行日志（结构化日志在 /api/status 的 logs 里）。"""
    rel = service.STATE.get('log_file')
    path = os.path.join(config.LOG_DIR, rel) if rel else None
    if not path or not os.path.isfile(path):
        return JSONResponse({'ok': False, 'error': '暂无日志'}, status_code=404)
    return FileResponse(path, media_type='text/plain; charset=utf-8',
                        filename='file_{}.log'.format(
                            service.STATE.get('file_id')))


@app.get('/parse-report')
def parse_report():
    """对照报告：重定向到最新资料的 对照报告.html 真实地址。
    报告内资源全是相对路径，必须落在该资料的 URL 下才能解析；
    file:// 直开用 export_artifacts.py 按需导出。"""
    from urllib.parse import quote
    fid = _load('store.artifact').latest_file_with(config.PARSE_REPORT_NAME)
    if fid is not None:
        return RedirectResponse('/files/{}/{}'.format(
            fid, quote(config.PARSE_REPORT_NAME, safe='')))
    return HTMLResponse(
        '<h3>还没有对照报告</h3><p><a href="/">返回工作台</a>先上传文件发起解析。</p>')


# ---- 数据链路 API（P0：资料库 / 抽取规则 / 任务 / 预生成内容读取）----
# 全部经 catalog / content / artifact repo 查 DB。错误分类归异常处理器：
# StoreError→对应码，DB 故障→503，编程错误→500。任务以 task id 为键；
# 资料/产物/记录/回执一律以 file_id 为键（一资料=一次运行）。


@app.get('/api/sources')
def api_sources(q: str = None, kind: str = None, tag: str = None,
                state: str = None, page: int = 1, size: int = 20):
    return _load('store.catalog').list_files(
        q, kind, tag, page, per_page=max(1, min(size, 200)), state=state)


@app.post('/api/sources')
async def api_sources_add(request: Request):
    """只登记不解析（资料页上传）。哈希命中回已有 id。"""
    body = await _json_body(request)
    name = service.safe_name(body.get('name', ''))
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
    info = service.register_file(name, data)
    return {'ok': True, 'id': info['file_id'], 'dedup': info['dedup']}


@app.delete('/api/sources/{file_id}')
def api_sources_del(file_id: int):
    _load('store.catalog').delete_file(file_id)
    return {'ok': True}


@app.get('/api/sources/{file_id}/pipeline')
def api_sources_pipeline(file_id: int):
    """资料流程追踪：单链路（一资料=一次运行）四节点状态与产物入口。"""
    catalog = _load('store.catalog')
    f = catalog.get_file(file_id)
    if f is None:
        raise store_errors.NotFound('资料文件不存在')
    content_db = _load('store.content_db')
    arts = [a['name'] for a in _load('store.artifact').list(file_id)]
    gate = content_db.gate_counts(file_id)
    logs = catalog.list_load_logs(file_id)
    actions = {}
    for l in logs:
        actions[l['action']] = actions.get(l['action'], 0) + 1
    rule = None
    if f.get('rule_version_id'):
        tv = catalog.get_rule_version(version_id=f['rule_version_id'])
        if tv:
            rule = {'name': tv['name'], 'version': tv['version'],
                    'rule_id': tv['rule_id'], 'version_id': tv['id']}
    load = None
    if f.get('load_table_id'):
        lt = catalog.get_load_table(f['load_table_id'])
        ds = catalog.get_datasource(f['load_datasource_id']) \
            if f.get('load_datasource_id') else None
        if lt:
            load = {'target_table': lt['target_table'],
                    'write_mode': lt['write_mode'],
                    'datasource_id': f['load_datasource_id'],
                    'datasource_name': ds['name'] if ds else None,
                    'db_name': ds['db_name'] if ds else None}
    return {'ok': True, 'file': f,
            'pipeline': {
                'file_id': file_id,
                'state': f['state'],
                'rule': rule,
                'parse_artifacts': arts,
                'review_counts': {k: gate[k] for k in
                                  ('confirmed', 'edited', 'rejected', 'pending')},
                'load': load,
                'load_actions': actions,
            }}


@app.get('/api/extract-rules')
def api_rules():
    return {'items': _load('store.catalog').list_rules()}


@app.post('/api/extract-rules')
async def api_rules_add(request: Request):
    body = await _json_body(request)
    vid = _load('store.catalog').create_rule(
        body.get('name'), body.get('description'),
        body.get('schema'), body.get('mapping'), body.get('transform'))
    return {'ok': True, 'version_id': vid}


@app.get('/api/extract-rules/{rule_id}')
def api_rule_get(rule_id: int):
    return _load('store.catalog').get_rule(rule_id)


@app.patch('/api/extract-rules/{rule_id}')
async def api_rule_patch(rule_id: int, request: Request):
    body = await _json_body(request)
    _load('store.catalog').update_rule(
        rule_id, name=body.get('name'),
        description=body.get('description'),
        current_version=body.get('current_version'))
    return {'ok': True}


@app.delete('/api/extract-rules/{rule_id}')
def api_rule_del(rule_id: int):
    _load('store.catalog').delete_rule(rule_id)
    return {'ok': True}


@app.get('/api/extract-rules/{rule_id}/versions')
def api_rule_versions(rule_id: int):
    return {'items': _load('store.catalog').list_versions(rule_id)}


@app.get('/api/extract-rules/{rule_id}/versions/{version_id}')
def api_rule_version_get(rule_id: int, version_id: int):
    tv = _load('store.catalog').get_rule_version(version_id=version_id)
    if not tv or tv['rule_id'] != rule_id:
        raise _load('store.errors').NotFound('抽取规则版本不存在')
    return tv


@app.post('/api/extract-rules/{rule_id}/versions')
async def api_rule_version_add(rule_id: int, request: Request):
    body = await _json_body(request)
    vid = _load('store.catalog').create_version(
        rule_id, body.get('schema'), body.get('mapping'),
        body.get('transform'))
    return {'ok': True, 'version_id': vid}


# ---- P2b 入库：数据源 / 映射绑定 / introspection ----
# 数据源密码明文存库、API 明文返回（2026-11-21 裁决，页面可见可编辑）；
# 但日志永不打印凭据，测试连接回显仅 host:port/库名。

@app.get('/api/load/datasources')
def api_load_datasources():
    return {'items': _load('store.catalog').list_datasources()}


@app.post('/api/load/datasources')
async def api_load_datasource_add(request: Request):
    body = await _json_body(request)
    did = _load('store.catalog').create_datasource(
        body.get('name'), body.get('host'), body.get('port'),
        body.get('user'), body.get('password'), body.get('db_name'),
        body.get('db_type') or 'mysql')
    return {'ok': True, 'id': did}


@app.patch('/api/load/datasources/{ds_id}')
async def api_load_datasource_patch(ds_id: int, request: Request):
    body = await _json_body(request)
    _load('store.catalog').update_datasource(
        ds_id, name=body.get('name'), host=body.get('host'),
        port=body.get('port'), user=body.get('user'),
        password=body.get('password'), db_name=body.get('db_name'))
    return {'ok': True}


@app.delete('/api/load/datasources/{ds_id}')
def api_load_datasource_del(ds_id: int):
    _load('store.catalog').delete_datasource(ds_id)
    return {'ok': True}


def _ds_or_404(ds_id):
    ds = _load('store.catalog').get_datasource(ds_id)
    if ds is None:
        raise store_errors.NotFound('业务库不存在')
    return ds


@app.post('/api/load/datasources/{ds_id}/test')
def api_load_datasource_test(ds_id: int):
    """测试连接：只回 host:port/库名，永不回显凭据。"""
    ds = _ds_or_404(ds_id)
    detail = '{}:{}/{}'.format(ds['host'], ds['port'], ds['db_name'])
    try:
        conn = _load('store.loader').connect_datasource(ds)
    except Exception as e:
        return JSONResponse(
            {'ok': False,
             'error': '目标库连接失败（{}）'.format(type(e).__name__)},
            status_code=503)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
    except Exception as e:
        return JSONResponse(
            {'ok': False,
             'error': '目标库连接失败（{}）'.format(type(e).__name__)},
            status_code=503)
    finally:
        conn.close()
    return {'ok': True, 'detail': detail}


@app.get('/api/load/datasources/{ds_id}/tables')
def api_load_datasource_tables(ds_id: int):
    ds = _ds_or_404(ds_id)
    return {'items': _load('store.loader').list_tables(ds)}


@app.get('/api/load/datasources/{ds_id}/columns')
def api_load_datasource_columns(ds_id: int, table: str = None):
    ds = _ds_or_404(ds_id)
    if not table:
        raise store_errors.BadRequest('table 参数必填')
    return {'items': _load('store.loader').list_columns(ds, table)}


@app.get('/api/load/datasources/{ds_id}/rows')
def api_load_datasource_rows(ds_id: int, table: str = None,
                             page: int = 1, per_page: int = 100):
    """数据看板：只读分页查询业务表（表名白名单＋列白名单＋参数化）。"""
    ds = _ds_or_404(ds_id)
    if not table:
        raise store_errors.BadRequest('table 参数必填')
    return {'ok': True, **_load('store.loader').query_rows(
        ds, table, page=page, per_page=per_page)}


@app.get('/api/load/tables')
def api_load_tables(datasource_id: int = None):
    return {'items': _load('store.catalog').list_load_tables(datasource_id)}


@app.post('/api/load/tables')
async def api_load_table_add(request: Request):
    body = await _json_body(request)
    try:
        ds_id = int(body.get('datasource_id'))
        tpl_id = int(body.get('rule_id'))
    except (TypeError, ValueError):
        raise store_errors.BadRequest('须选择业务库与抽取规则')
    lt_id = _load('store.catalog').create_load_table(
        ds_id, tpl_id, body.get('target_table'),
        body.get('write_mode') or 'upsert', body.get('fields'))
    return {'ok': True, 'id': lt_id}


@app.get('/api/load/tables/{lt_id}')
def api_load_table_get(lt_id: int):
    lt = _load('store.catalog').get_load_table(lt_id)
    if lt is None:
        raise store_errors.NotFound('入库规则不存在')
    return lt


@app.patch('/api/load/tables/{lt_id}')
async def api_load_table_patch(lt_id: int, request: Request):
    body = await _json_body(request)
    _load('store.catalog').update_load_table(
        lt_id, write_mode=body.get('write_mode'), fields=body.get('fields'))
    return {'ok': True}


@app.delete('/api/load/tables/{lt_id}')
def api_load_table_del(lt_id: int):
    _load('store.catalog').delete_load_table(lt_id)
    return {'ok': True}


# ---- 资料流程 API：全部以 file_id 为键，一条资料 = 一次运行 ----

def _file_or_404(file_id):
    f = _load('store.catalog').get_file(file_id)
    if f is None:
        raise store_errors.NotFound('资料不存在')
    return f


@app.get('/api/sources/state')
def api_sources_state(state: str = None):
    """工作台/筛选：资料带运行状态列表（替代原 /api/tasks）。"""
    return {'items': _load('store.catalog').list_files(
        state=state, per_page=200)['items']}


@app.get('/api/sources/ledger')
def api_sources_ledger():
    """校验台账：按资料聚合记录数与校验进度。"""
    return {'ok': True, 'items': _load('store.content_db').ledger()}


@app.get('/api/sources/{file_id}')
def api_source_detail(file_id: int):
    """资料详情（替代原 task 投影）：状态/规则/入库绑定/记录数。"""
    f = _file_or_404(file_id)
    rule = None
    if f.get('rule_version_id'):
        tv = _load('store.catalog').get_rule_version(
            version_id=f['rule_version_id'])
        if tv:
            rule = {'name': tv['name'], 'version': tv['version'],
                    'version_id': tv['id'], 'rule_id': tv['rule_id']}
    gate = _load('store.content_db').gate_counts(file_id)
    load = None
    if f.get('load_table_id'):
        lt = _load('store.catalog').get_load_table(f['load_table_id'])
        if lt:
            load = {'datasource_id': f['load_datasource_id'],
                    'load_table_id': f['load_table_id'],
                    'target_table': lt['target_table'],
                    'write_mode': lt['write_mode']}
    return {'file': {'file_id': file_id, 'state': f['state'],
                     'error': f['error'], 'rule': rule, 'load': load,
                     'params': f.get('params_json') or {},
                     'created_at': str(f['created_at']),
                     'name': f['name'],
                     'records_n': gate['records_n'],
                     'files': [{'file_id': file_id, 'name': f['name'],
                                'state': f['state'],
                                'records_n': gate['records_n']}]}}


@app.get('/api/sources/{file_id}/gate')
def api_file_gate(file_id: int):
    """门禁四态计数（轻量）：入库前检查，不拉记录内容。"""
    _file_or_404(file_id)
    return dict(_load('store.content_db').gate_counts(file_id), ok=True)


@app.get('/api/sources/{file_id}/load-log')
def api_file_load_log(file_id: int):
    _file_or_404(file_id)
    return {'ok': True, 'items': _load('store.catalog').list_load_logs(file_id)}


@app.post('/api/sources/{file_id}/load')
async def api_file_load(file_id: int, request: Request):
    """手动入库闸门：未绑定带 {load_datasource_id, load_table_id}；
    已绑定空体沿用原绑定。门禁/预检在 service.launch_load。"""
    raw = await request.body()
    body = await _json_body(request) if raw else {}
    target = None
    if 'load_datasource_id' in body or 'load_table_id' in body:
        try:
            target = {'datasource_id': int(body.get('load_datasource_id')),
                      'load_table_id': int(body.get('load_table_id'))}
        except (TypeError, ValueError):
            raise store_errors.BadRequest('入库目标须为业务库/入库规则 id')
    return service.launch_load(file_id, target)


@app.post('/api/sources/{file_id}/extract')
async def api_file_run_extract(file_id: int, request: Request):
    """执行抽取：{force?, rule_version_id?}；空体=资料已绑规则（未绑默认透传）。
    parse.json 纯投影、同步毫秒级；重抽覆盖校验结论须 force=true。"""
    raw = await request.body()
    body = await _json_body(request) if raw else {}
    rv = body.get('rule_version_id')
    if rv is not None and not isinstance(rv, int):
        raise store_errors.BadRequest('rule_version_id 须为整数')
    return await run_in_threadpool(service.run_extract, file_id,
                                   force=bool(body.get('force')),
                                   rule_version_id=rv)


@app.post('/api/sources/{file_id}/reparse')
def api_file_reparse(file_id: int):
    """原地重放解析：原件回捞重跑；暂存/产物/回执/隔离全清（D4）。
    解析中/入库中/已入库回 409。"""
    return service.reparse(file_id)


@app.post('/api/sources/{file_id}/load-preview')
async def api_file_load_preview(file_id: int, request: Request):
    """入库向导 dry-run（只读）：{load_table_id} 或 {draft:{...}}。"""
    body = await _json_body(request)
    draft = body.get('draft')
    table_id = body.get('load_table_id')
    return service.preview_load(file_id,
                                table_id=None if draft else table_id,
                                draft=draft if isinstance(draft, dict) else None)


@app.get('/api/sources/{file_id}/quarantine')
def api_file_quarantine(file_id: int):
    """隔离区只读展示：该资料的隔离条目。"""
    _file_or_404(file_id)
    return {'ok': True,
            'items': _load('store.catalog').list_quarantine(file_id=file_id)}


@app.get('/api/sources/{file_id}/parse')
def api_file_extract(file_id: int):
    doc = _load('store.content').get_extract(file_id)
    if doc is None:
        return JSONResponse({'ok': False, 'error': 'parse.json 不存在'},
                            status_code=404)
    return doc


@app.get('/api/sources/{file_id}/staging')
def api_file_staging(file_id: int):
    doc = _load('store.content').get_records(file_id)
    if doc is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    return doc


@app.get('/api/staging/query')
def api_staging_query(field: str = None, q: str = None,
                      task: str = None, state: str = None):
    """跨资料暂存查询：DB 直查 field 投影；DB down → 503。task 参数按资料 ID 过滤。"""
    rows = _load('store.content_db').query_fields(field, q, task, state)
    return {'ok': True, 'items': rows}


@app.get('/api/staging/locate/{record_id}')
def api_staging_locate(record_id: int):
    """按 record_id 反查 file_id，用于数据看板血缘跳转。"""
    hit = _load('store.content_db').locate_record(record_id)
    if hit is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    return {'ok': True, **hit}


def _review_guard(file_id):
    """校验写操作公共守卫：入库中/已入库记录只读。"""
    f = _file_or_404(file_id)
    if f['state'] in ('loading', 'loaded'):
        raise store_errors.Conflict(
            {'loading': '入库进行中，记录只读',
             'loaded': '资料已入库，记录只读'}[f['state']])


@app.patch('/api/sources/{file_id}/staging/{index}')
async def api_staging_patch(file_id: int, index: int, request: Request):
    """校验改值：values 差量合并→edited，original 永不覆盖。"""
    _review_guard(file_id)
    body = await _json_body(request)
    values = body.get('values')
    if not isinstance(values, dict) or not values:
        return JSONResponse({'ok': False, 'error': 'values 须为非空对象'},
                            status_code=400)
    rec = _load('store.content').patch_record(file_id, index, values)
    return {'ok': True, 'record': rec,
            'file_state': service.derive_review_state(file_id)}


@app.post('/api/sources/{file_id}/staging/review')
async def api_staging_review(file_id: int, request: Request):
    """批量确认/拒绝：indexes（记录内下标）＋ state。"""
    _review_guard(file_id)
    body = await _json_body(request)
    indexes = body.get('indexes')
    state = body.get('state')
    if not isinstance(indexes, list) or not indexes \
            or not all(isinstance(i, int) for i in indexes):
        return JSONResponse(
            {'ok': False, 'error': 'indexes 须为非空整数数组'},
            status_code=400)
    if state not in ('confirmed', 'rejected'):
        return JSONResponse(
            {'ok': False, 'error': 'state 仅支持 confirmed/rejected'},
            status_code=400)
    n = _load('store.content').set_review(file_id, indexes, state)
    return {'ok': True, 'updated': n,
            'file_state': service.derive_review_state(file_id)}


@app.post('/api/sources/{file_id}/parse')
async def api_sources_parse(file_id: int, request: Request):
    """从资料库选一条资料发起解析（字节直读 c1_doc_file.content）。"""
    if service.STATE['running']:
        return JSONResponse({'ok': False, 'error': '已有资料正在解析'},
                            status_code=409)
    body = await _json_body(request)
    _reject_retired_load_keys(body)
    catalog = _load('store.catalog')
    row = catalog.get_file(file_id)
    if row is None:
        raise store_errors.NotFound('资料不存在')
    s = catalog.get_file_content(file_id)
    if s is None:
        return JSONResponse({'ok': False, 'error': '原件内容缺失'},
                            status_code=409)
    params, warns = params_mod.normalize(body.get('params'))
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    launched = False
    try:
        name = service.safe_name(row['name'])
        path = os.path.join(in_dir, name)
        with open(path, 'wb') as fo:
            fo.write(s['data'])
        ctx = [{'name': name, 'path': path, 'file_id': file_id,
                'sha256': row['sha256'], 'dedup': False}]
        result = service.launch([path], params, warns, ctx)
        launched = True
        return result
    finally:
        if not launched:
            service.rmtree_retry(in_dir)


if __name__ == '__main__':
    import uvicorn

    print('>> 结构化平台 地址： http://{}:{}'.format(config.HOST, config.PORT))
    print('>> 结构化平台 存储： {}'.format(
        _load('store.db').safe_detail(config.PLATFORM_DB)))
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level='warning')
