"""
c1_extract/app.py — Web 工具入口（FastAPI + uvicorn）。只负责 HTTP 路由与请求校验；
运行引擎与共享运行状态（STATE/LOCK、task_batch）在 service.py。

启动：
    D:\\miniforge3\\envs\\paddle\\python.exe c1_extract/app.py
    浏览器打开 http://127.0.0.1:8765

路由：
    GET  /              提取页（web/upload.html + /static 资源）
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
import base64
import importlib
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from fnmatch import fnmatch
from urllib.parse import unquote

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


config = _load('config')  # 必须在 paddle 相关导入之前：设置模型源环境变量
params_mod = _load('params')  # 调试参数 schema / 校验（纯 Python，不碰模型）
service = _load('service')  # 运行引擎：STATE/LOCK、launch、task_batch
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
    a = _load('store.artifact').get(int(parts[0]), rel)
    if a is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    return _blob_response(a['data'], a['mime'], a['sha'], request)


@app.get('/srcfiles/{file_id:int}')
def srcfiles_db(file_id: int, request: Request):
    """/srcfiles/<file_id>：原件字节（extract_file.content）。
    用 id 不用名字——同名不同字节是两行，名字会撞。"""
    s = _load('store.catalog').get_file_content(file_id)
    if s is None:
        return PlainTextResponse('404 Not Found', status_code=404)
    mime = _load('store.artifact').mime_of(s['name'])
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


@app.get('/templates', response_class=HTMLResponse)
def templates_page():
    return HTMLResponse(asset('templates.html'))


@app.get('/load', response_class=HTMLResponse)
def load_page():
    return HTMLResponse(asset('load.html'))


@app.get('/healthz')
def health():
    return {'ok': True, 'service': 'c1-extract',
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
    目标改在 POST /api/tasks/{id}/load 时选择。"""
    if any(k in body for k in ('mode', 'load_datasource_id', 'load_table_id')):
        raise store_errors.BadRequest(
            '上传不再携带入库目标，请在任务入库时选择')


@app.post('/api/upload')
async def upload(request: Request):
    if service.STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等它完成'},
            status_code=409)
    body = await _json_body(request)
    _reject_retired_load_keys(body)
    files = body.get('files') or []
    if not files:
        return JSONResponse({'ok': False, 'error': '没有收到文件'},
                            status_code=400)
    tpl = service.resolve_template(body.get('template_version_id'))
    # 调试参数：校验一次，非法值回退默认并把警告带回页面（不让整批失败）
    params, warns = params_mod.normalize(body.get('params'))

    # 输入副本只落 tmp/input scratch（字节事实源在 extract_file.content），跑完即清；
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
        result = service.launch(paths, params, warns, ctx, tpl)
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
                        filename='task_{}.log'.format(
                            service.STATE.get('task_id')))


@app.get('/extract-report')
def extract_report():
    """对照报告：重定向到最新 task_file 的 对照报告.html 真实地址。
    报告内资源全是相对路径，必须落在该 task_file 的 URL 下才能解析；
    file:// 直开用 export_artifacts.py 按需导出。"""
    from urllib.parse import quote
    tf = _load('store.artifact_db').latest_task_file_with(
        config.EXTRACT_REPORT_NAME)
    if tf is not None:
        return RedirectResponse('/files/{}/{}'.format(
            tf, quote(config.EXTRACT_REPORT_NAME, safe='')))
    return HTMLResponse(
        '<h3>还没有对照报告</h3><p><a href="/">返回上传页</a>先上传一个文件。</p>')


# ---- 数据链路 API（P0：资料库 / 模板 / 任务 / 预生成内容读取）----
# 全部经 catalog / content / artifact repo 查 DB。错误分类归异常处理器：
# StoreError→对应码，DB 故障→503，编程错误→500。任务以 task id 为键；
# 文件以 task_file_id 为键；原件以 file_id 为键。


@app.get('/api/sources')
def api_sources(q: str = None, kind: str = None, tag: str = None, page: int = 1):
    return _load('store.catalog').list_files(q, kind, tag, page)


@app.post('/api/sources')
async def api_sources_add(request: Request):
    """只登记不提取（资料页上传）。哈希命中回已有 id。"""
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


@app.get('/api/templates')
def api_templates():
    return {'items': _load('store.catalog').list_templates()}


@app.post('/api/templates')
async def api_templates_add(request: Request):
    body = await _json_body(request)
    vid = _load('store.catalog').create_template(
        body.get('name'), body.get('description'),
        body.get('schema'), body.get('mapping'), body.get('transform'))
    return {'ok': True, 'version_id': vid}


@app.get('/api/templates/{template_id}')
def api_template_get(template_id: int):
    return _load('store.catalog').get_template(template_id)


@app.patch('/api/templates/{template_id}')
async def api_template_patch(template_id: int, request: Request):
    body = await _json_body(request)
    _load('store.catalog').update_template(
        template_id, name=body.get('name'),
        description=body.get('description'),
        current_version=body.get('current_version'))
    return {'ok': True}


@app.delete('/api/templates/{template_id}')
def api_template_del(template_id: int):
    _load('store.catalog').delete_template(template_id)
    return {'ok': True}


@app.get('/api/templates/{template_id}/versions')
def api_template_versions(template_id: int):
    return {'items': _load('store.catalog').list_versions(template_id)}


@app.get('/api/templates/{template_id}/versions/{version_id}')
def api_template_version_get(template_id: int, version_id: int):
    tv = _load('store.catalog').get_template_version(version_id=version_id)
    if not tv or tv['template_id'] != template_id:
        raise _load('store.errors').NotFound('模板版本不存在')
    return tv


@app.post('/api/templates/{template_id}/versions')
async def api_template_version_add(template_id: int, request: Request):
    body = await _json_body(request)
    vid = _load('store.catalog').create_version(
        template_id, body.get('schema'), body.get('mapping'),
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
        raise store_errors.NotFound('数据源不存在')
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


@app.get('/api/load/tables')
def api_load_tables(datasource_id: int = None):
    return {'items': _load('store.catalog').list_load_tables(datasource_id)}


@app.post('/api/load/tables')
async def api_load_table_add(request: Request):
    body = await _json_body(request)
    try:
        ds_id = int(body.get('datasource_id'))
        tpl_id = int(body.get('template_id'))
    except (TypeError, ValueError):
        raise store_errors.BadRequest('须选择数据源与模板')
    lt_id = _load('store.catalog').create_load_table(
        ds_id, tpl_id, body.get('target_table'),
        body.get('write_mode') or 'upsert', body.get('fields'))
    return {'ok': True, 'id': lt_id}


@app.get('/api/load/tables/{lt_id}')
def api_load_table_get(lt_id: int):
    lt = _load('store.catalog').get_load_table(lt_id)
    if lt is None:
        raise store_errors.NotFound('映射不存在')
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


@app.get('/api/tasks/{task_id}/load-log')
def api_task_load_log(task_id: int):
    if _load('store.catalog').get_task(task_id) is None:
        raise store_errors.NotFound('任务不存在')
    return {'ok': True, 'items': _load('store.catalog').list_load_logs(task_id)}


@app.post('/api/tasks/{task_id}/load')
async def api_task_load(task_id: int, request: Request):
    """手动入库闸门（P2c）：未绑定任务带 {load_datasource_id, load_table_id}
    入库时绑定；已绑定任务空体沿用原绑定。门禁/预检在 service.launch_load。"""
    raw = await request.body()
    body = await _json_body(request) if raw else {}
    target = None
    if 'load_datasource_id' in body or 'load_table_id' in body:
        try:
            target = {'datasource_id': int(body.get('load_datasource_id')),
                      'load_table_id': int(body.get('load_table_id'))}
        except (TypeError, ValueError):
            raise store_errors.BadRequest('入库目标须为数据源/映射 id')
    return service.launch_load(task_id, target)


@app.get('/api/tasks/{task_id}/quarantine')
def api_task_quarantine(task_id: int):
    """隔离区只读展示（本轮无解决 UI）：任务内全部隔离条目。"""
    if _load('store.catalog').get_task(task_id) is None:
        raise store_errors.NotFound('任务不存在')
    return {'ok': True,
            'items': _load('store.catalog').list_quarantine(task_id=task_id)}


@app.get('/api/tasks')
def api_tasks():
    """任务列表：task/task_file/file 表投影（无 run.json 附件）。"""
    return {'items': _load('store.catalog').list_tasks()}


@app.get('/api/tasks/{task_id}')
def api_task_detail(task_id: int):
    doc = _load('store.catalog').get_task(task_id)
    if doc is None:
        return JSONResponse({'ok': False, 'error': '任务不存在'},
                            status_code=404)
    live = None
    with service.LOCK:
        if service.STATE.get('task_id') == task_id:
            live = {'running': service.STATE['running'],
                    'progress': service.STATE['progress'],
                    'stage': service.STATE['stage'],
                    'error': service.STATE['error']}
    return {'task': doc, 'live': live}


def _tf_of(task_id, file):
    """任务内选 task_file：file 指定则校验归属，否则取第一个。"""
    tfs = _load('store.catalog').task_file_ids(task_id)
    if not tfs:
        return None
    if file:
        try:
            fid = int(file)
        except ValueError:
            raise store_errors.BadRequest('file 须为 task_file_id')
        return fid if fid in tfs else None
    return tfs[0]


@app.get('/api/tasks/{task_id}/extract')
def api_task_extract(task_id: int, file: str = None):
    tf = _tf_of(task_id, file)
    doc = _load('store.content').get_extract(tf) if tf else None
    if doc is None:
        return JSONResponse({'ok': False, 'error': 'extract.json 不存在'},
                            status_code=404)
    return doc


@app.get('/api/tasks/{task_id}/staging')
def api_task_staging(task_id: int, file: str = None):
    doc = _load('store.content').get_records(task_id)
    if doc and file:
        doc['files'] = [f for f in doc['files']
                        if f['task_file_id'] == int(file)]
        if not doc['files']:
            doc = None
    if doc is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    return doc


@app.get('/api/staging/query')
def api_staging_query(field: str = None, q: str = None,
                      task: str = None, state: str = None):
    """跨任务暂存查询：DB 直查 field 投影；DB down → 503。"""
    rows = _load('store.content_db').query_fields(field, q, task, state)
    return {'ok': True, 'items': rows}


@app.get('/api/staging/ledger')
def api_staging_ledger():
    """校验台账：按 task_file 聚合记录数与校验进度；DB down → 503。"""
    return {'ok': True, 'items': _load('store.content_db').ledger()}


def _review_target(task_id, task_file_id):
    """校验台写操作公共守卫：返回 file_index。

    task 不存在 / 文件不属于 task → NotFound；入库中/部分入库/已入库 → Conflict。
    files 序与 content_db._task_files 的 ORDER BY tf.id 一致。
    """
    t = _load('store.catalog').get_task(task_id)
    if t is None:
        raise store_errors.NotFound('任务不存在')
    if t['state'] in ('loading', 'partial', 'loaded'):
        raise store_errors.Conflict(
            {'loading': '入库进行中，记录只读',
             'partial': '任务部分入库，记录只读（可重新入库）',
             'loaded': '任务已入库，记录只读'}[t['state']])
    fi = next((i for i, f in enumerate(t['files'])
               if f['task_file_id'] == task_file_id), None)
    if fi is None:
        raise store_errors.NotFound('文件不属于该任务')
    return fi


@app.patch('/api/tasks/{task_id}/staging/{task_file_id}/{index}')
async def api_staging_patch(task_id: int, task_file_id: int, index: int,
                            request: Request):
    """校验改值：values 差量合并→edited，original 永不覆盖。"""
    fi = _review_target(task_id, task_file_id)
    body = await _json_body(request)
    values = body.get('values')
    if not isinstance(values, dict) or not values:
        return JSONResponse({'ok': False, 'error': 'values 须为非空对象'},
                            status_code=400)
    rec = _load('store.content').patch_record(task_id, fi, index, values)
    return {'ok': True, 'record': rec}


@app.post('/api/tasks/{task_id}/staging/{task_file_id}/review')
async def api_staging_review(task_id: int, task_file_id: int,
                             request: Request):
    """批量确认/拒绝：indexes（记录内下标）＋ state。"""
    fi = _review_target(task_id, task_file_id)
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
    n = _load('store.content').set_review(task_id, fi, indexes, state)
    return {'ok': True, 'updated': n}


@app.post('/api/tasks')
async def api_tasks_create(request: Request):
    """从资料库选文件发起任务（复用上传编排；字节直读 extract_file.content）。"""
    if service.STATE['running']:
        return JSONResponse({'ok': False, 'error': '已有任务正在处理'},
                            status_code=409)
    body = await _json_body(request)
    _reject_retired_load_keys(body)
    ids = body.get('file_ids') or []
    if not ids:
        return JSONResponse({'ok': False, 'error': '未选择文件'},
                            status_code=400)
    catalog = _load('store.catalog')
    rows = [catalog.get_file(int(i)) for i in ids]
    if any(r is None for r in rows):
        return JSONResponse({'ok': False, 'error': '存在未登记的文件 id'},
                            status_code=400)
    params, warns = params_mod.normalize(body.get('params'))
    tpl = service.resolve_template(body.get('template_version_id'))
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    launched = False
    try:
        paths, used, ctx = [], set(), []
        for row in rows:
            name = _dedup_name(row['name'], used)
            used.add(name)
            s = catalog.get_file_content(row['id'])
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
        result = service.launch(paths, params, warns, ctx, tpl)
        launched = True
        return result
    finally:
        if not launched:
            service.rmtree_retry(in_dir)


if __name__ == '__main__':
    import uvicorn

    print('>> 结构化平台 地址： http://{}:{}'.format(config.HOST, config.PORT))
    print('>> 结构化平台 存储： {}'.format(
        _load('store.db').safe_detail(config.PLATFORM_DB_REF)))
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level='warning')
