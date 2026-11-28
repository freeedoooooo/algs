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
    GET  /review        校验壳页 · /rules 入库映射 · /dashboard 数据看板
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
import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from fnmatch import fnmatch
from urllib.parse import unquote

from starlette.concurrency import run_in_threadpool

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
_load('logging_config').configure_logging()
logger = logging.getLogger(PKG + '.app')
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
        logger.info('模型预热完成（PaddleOCR + PPStructureV3）')
    yield


app = FastAPI(title='结构化工具', version='0.1', lifespan=lifespan)
# 响应压缩（2026-11-21 性能轮）：报告 HTML 均值 530KB/最大 1.9MB、
# 记录 JSON ~150KB，远端访问下文本 1KB 起压可省 ~85% 传输。
app.add_middleware(GZipMiddleware, minimum_size=1024)

# ---- 错误分类：业务错误类型化（StoreError.code→HTTP），DB 故障 503，
# 编程错误 500（uvicorn 记 traceback）。不再把一切异常伪装成「平台库不可用」。----
store_errors = _load('store.errors')


@app.exception_handler(store_errors.StoreError)
async def store_error_handler(_request, exc):
    return JSONResponse({'ok': False, 'error': exc.msg}, status_code=exc.code)


@app.exception_handler(_load('agent.llm').LLLError)
async def agent_llm_error_handler(_request, exc):
    """Agent LLM 失败显式返回，不静默降级、不伪装成平台库故障。"""
    _agent_llm = _load('agent.llm')
    codes = {_agent_llm.LLMUnconfigured: 400,
             _agent_llm.LLMTimeout: 504,
             _agent_llm.LLMBadJSON: 502,
             _agent_llm.LLMSchemaFail: 422}
    code = codes.get(type(exc), 500)
    return JSONResponse({'ok': False, 'error': str(exc)}, status_code=code)


@app.exception_handler(Exception)
async def fallback_error_handler(_request, exc):
    import pymysql
    if isinstance(exc, (pymysql.MySQLError, OSError, LookupError)):
        logger.error('平台库不可用：error_type=%s', type(exc).__name__)
        return JSONResponse({'ok': False, 'error': '平台库不可用'},
                            status_code=503)
    logger.exception('未处理请求异常：%s: %s', type(exc).__name__, exc)
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
    check = rel
    if rel.startswith('test/'):
        check = rel[len('test/'):]
        if check.startswith('raw/') or check == 'result.json':
            return 403
    ok = (check in _TOP_FILES
          or (check.startswith('pages/') and check.endswith('.png'))
          or check in _IMAGE_SRCS
          or (check.endswith('.md') and '/' not in check)
          or any(fnmatch(check, p) for p in _CSV_PATTERNS))
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


@app.get('/chat', response_class=HTMLResponse)
def chat_page():
    return HTMLResponse(asset('chat.html'))


@app.get('/parse', response_class=HTMLResponse)
def parse_page():
    return HTMLResponse(asset('parse.html'))


@app.get('/sources', response_class=HTMLResponse)
def sources_page():
    return HTMLResponse(asset('sources.html'))


@app.get('/process', response_class=HTMLResponse)
def process_page():
    return HTMLResponse(asset('process.html'))


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


@app.get('/governance', response_class=HTMLResponse)
def governance_page():
    """原始业务表数据治理与全链路血缘追踪，当前为待实现占位页。"""
    return HTMLResponse(asset('governance.html'))


@app.get('/compute', response_class=HTMLResponse)
def compute_page():
    """计算审计：指标→规则→框架 + 全链路追溯 + 复现校验。"""
    return HTMLResponse(asset('compute.html'))


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


def _decode_upload_files(files, in_dir):
    if not files:
        raise store_errors.BadRequest('未收到文件')
    extra_n = max(0, len(files) - 1)
    files = files[:1]
    paths, used, ctx = [], set(), []
    for item in files:
        name = service.safe_name(item.get('name', ''))
        ext = os.path.splitext(name)[1].lower()
        if ext not in config.ALLOWED_EXTS:
            raise store_errors.BadRequest('不支持的格式：{}'.format(ext))
        name = _dedup_name(name, used)
        used.add(name)
        try:
            data = base64.b64decode(str(item.get('data', '')).split(',')[-1])
        except Exception:
            raise store_errors.BadRequest('{} 的 base64 数据无效'.format(name))
        if len(data) > config.MAX_FILE_MB * 1024 * 1024:
            raise store_errors.BadRequest(
                '{} 超过 {}MB'.format(name, config.MAX_FILE_MB))
        path = os.path.join(in_dir, name)
        with open(path, 'wb') as f:
            f.write(data)
        paths.append(path)
        info = service.register_file(name, data)
        ctx.append(dict(info, name=name, path=path))
    return paths, ctx, extra_n


@app.post('/api/upload')
async def upload(request: Request):
    if service.STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等待其完成'},
            status_code=409)
    body = await _json_body(request)
    _reject_retired_load_keys(body)
    files = body.get('files') or []
    # 调试参数：校验一次，非法值回退默认并把警告带回页面（不让整批失败）
    params, warns = params_mod.normalize(body.get('params'))

    # 输入副本只落 tmp/input scratch（字节事实源在 c1_doc_file.content），跑完即清；
    # 任何失败路径（校验 400 / DB 503）都由 finally 回收，不留孤儿
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    launched = False
    try:
        paths, ctx, extra_n = _decode_upload_files(files, in_dir)
        if extra_n:
            warns.insert(0, '一次只解析一个文件，已忽略另外 {} 个文件'.format(extra_n))
        result = service.launch(paths, params, warns, ctx)
        launched = True
        return result
    finally:
        if not launched:
            service.rmtree_retry(in_dir)


@app.post('/api/auto/process')
async def auto_process(request: Request):
    """上传 + 自然语言意图 → 解析、规则生成、抽取、表推荐/映射、自动入库。"""
    if service.STATE['running']:
        return JSONResponse(
            {'ok': False, 'error': '已有任务正在处理，请等待其完成'},
            status_code=409)
    body = await _json_body(request)
    _reject_retired_load_keys(body)
    intent = body.get('intent') or {}
    if not isinstance(intent, dict):
        raise store_errors.BadRequest('intent 须为 JSON 对象')
    if not intent.get('description') and body.get('description'):
        intent = dict(intent, description=body.get('description'))
    if not intent.get('target_table') and body.get('target_table'):
        intent = dict(intent, target_table=body.get('target_table'))
    if intent.get('datasource_id') is None and body.get('datasource_id') is not None:
        intent = dict(intent, datasource_id=body.get('datasource_id'))
    if not str(intent.get('description') or intent.get('prompt') or '').strip():
        raise store_errors.BadRequest('自动处理需要自然语言描述')
    params, warns = params_mod.normalize(body.get('params'))
    in_dir = tempfile.mkdtemp(prefix='in_', dir=config.TMP_INPUT)
    launched = False
    try:
        paths, ctx, extra_n = _decode_upload_files(body.get('files') or [], in_dir)
        if extra_n:
            warns.insert(0, '一次只解析一个文件，已忽略另外 {} 个文件'.format(extra_n))
        result = _load('auto_service').launch(
            paths, params, warns, ctx, intent)
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
    """资料流程追踪：解析产物、全部抽取结果及独立入库绑定。"""
    catalog = _load('store.catalog')
    f = catalog.get_file(file_id)
    if f is None:
        raise store_errors.NotFound('资料文件不存在')
    content_db = _load('store.content_db')
    arts = [a['name'] for a in _load('store.artifact').list(file_id)]
    results = []
    for result in catalog.list_extract_results(file_id):
        gate = content_db.gate_counts(result['id'])
        binding = catalog.get_binding(extract_result_id=result['id'])
        results.append({
            'extract_result_id': result['id'], 'rule_id': result['rule_id'],
            'rule_name': result['rule_name'], 'status': result['status'],
            'record_count': result['record_count'], 'error': result['error'],
            'review_counts': {k: gate[k] for k in
                              ('confirmed', 'edited', 'rejected', 'pending')},
            'load_binding': binding,
        })
    return {'ok': True, 'file': f,
            'pipeline': {'file_id': file_id, 'state': f['state'],
                         'parse_artifacts': arts, 'results': results}}


@app.get('/api/sources/{file_id}/stage-results')
def api_sources_stage_results(file_id: int):
    """聊天阶段卡片：解析摘要与全部抽取结果摘要。"""
    _file_or_404(file_id)
    summary = _load('stage_summary')
    content = _load('store.content')
    catalog = _load('store.catalog')
    artifacts = [a['name'] for a in _load('store.artifact').list(file_id)]
    extracts = []
    for result in catalog.list_extract_results(file_id):
        item = summary.extract_summary(content_db.get_records(result['id']))
        item.update(extract_result_id=result['id'], rule_id=result['rule_id'],
                    rule_name=result['rule_name'], status=result['status'],
                    plan=_load('store.load_planner').get_plan(result['id']),
                    binding=catalog.get_binding(extract_result_id=result['id']))
        extracts.append(item)
    return {'ok': True,
            'parse': summary.parse_summary(content.get_extract(file_id), artifacts),
            'extract': extracts}


@app.get('/api/extract-rules')
def api_rules():
    return {'items': _load('store.catalog').list_rules()}


@app.post('/api/extract-rules')
async def api_rules_add(request: Request):
    body = await _json_body(request)
    rule_id = _load('store.catalog').create_rule(
        body.get('name'), body.get('description'),
        body.get('output_schema_json'),
        body.get('extraction_spec_json'),
        reference_doc_ids_json=body.get('reference_doc_ids_json'),
        validation_report_json=body.get('validation_report_json'))
    return {'ok': True, 'rule_id': rule_id}


@app.get('/api/extract-rules/{rule_id}')
def api_rule_get(rule_id: int):
    rule = _load('store.catalog').get_rule(rule_id)
    if rule is None:
        raise store_errors.NotFound('抽取规则不存在')
    return rule


@app.patch('/api/extract-rules/{rule_id}')
async def api_rule_patch(rule_id: int, request: Request):
    body = await _json_body(request)
    _load('store.catalog').update_rule(
        rule_id, name=body.get('name'),
        description=body.get('description'),
        output_schema_json=body.get('output_schema_json'),
        extraction_spec_json=body.get('extraction_spec_json'),
        reference_doc_ids_json=body.get('reference_doc_ids_json'),
        validation_report_json=body.get('validation_report_json'))
    return {'ok': True}


@app.delete('/api/extract-rules/{rule_id}')
def api_rule_del(rule_id: int):
    _load('store.catalog').delete_rule(rule_id)
    return {'ok': True}


# ---- Agent 规则生成（P0）----
# 独立前缀 /api/agent/...：避开 /api/extract-rules/{rule_id} 的 int 路由歧义。
# 只产草稿、不写库；保存由前端提交单行规则，由用户确认后用于抽取。


@app.post('/api/agent/generate-rule')
async def api_agent_generate_rule(request: Request):
    """参考一份或多份已解析附件，生成一条或多条中文逻辑字段规则草稿。"""
    body = await _json_body(request)
    file_id = body.get('file_id')
    if not isinstance(file_id, int) or isinstance(file_id, bool) or file_id <= 0:
        raise store_errors.BadRequest('file_id 须为正整数（主参考文件）')
    raw_refs = body.get('reference_doc_ids')
    if raw_refs is None:
        raw_refs = []
    if not isinstance(raw_refs, list) or len(raw_refs) > 10:
        raise store_errors.BadRequest('reference_doc_ids 须为最多 10 个附件 ID')
    doc_ids = []
    for value in [file_id] + raw_refs:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise store_errors.BadRequest('参考附件 ID 须为正整数')
        if value not in doc_ids:
            doc_ids.append(value)
    fields = body.get('fields')
    user_prompt = body.get('prompt')
    has_fields = isinstance(fields, list) and bool(fields)
    has_prompt = bool(str(user_prompt or '').strip())
    if has_fields == has_prompt:
        raise store_errors.BadRequest(
            'fields（精确模式）与 prompt（自然语言模式）须且只须提供一个')
    content = _load('store.content')
    catalog = _load('store.catalog')
    references = []
    primary = None
    for doc_id in doc_ids:
        f = catalog.get_file(doc_id)
        if f is None:
            raise store_errors.NotFound('参考文件不存在')
        doc = content.get_extract(doc_id)
        if doc is None:
            raise store_errors.Conflict('参考文件尚无解析产物，请先解析')
        item = {'file_id': doc_id, 'name': f['name'],
                'doc_type': f.get('doc_type'), 'doc': doc}
        if doc_id == file_id:
            primary = item
        else:
            references.append(item)
    sample_result_id = body.get('sample_extract_result_id')
    if sample_result_id is not None:
        if not isinstance(sample_result_id, int) or isinstance(sample_result_id, bool) \
                or sample_result_id <= 0:
            raise store_errors.BadRequest('sample_extract_result_id 须为正整数')
        if catalog.get_extract_result(sample_result_id) is None:
            raise store_errors.NotFound('标准答案抽取结果不存在')

    from fastapi.concurrency import run_in_threadpool
    agent = _load('agent.rule_author')
    refs = {'file_id': file_id, 'reference_doc_ids': doc_ids}
    result = await run_in_threadpool(
        agent.generate_rule, primary['doc'], fields if has_fields else None, refs,
        doc_type=primary.get('doc_type'), generation=body.get('generation'),
        targets=body.get('targets'),
        sample_extract_result_id=sample_result_id,
        user_prompt=user_prompt if has_prompt else None,
        reference_docs=references,
        multiple_rules=body.get('multiple_rules') is True)

    tasklog_mod = _load('tasklog')
    log_path = os.path.join(config.LOG_DIR, 'agent_{}.log'.format(file_id))
    log = tasklog_mod.TaskLog('agent_{}'.format(file_id), log_path=log_path)
    out_fields = (result.schema or {}).get('fields') or []
    log.emit('info', 'agent', '生成规则草稿（{}模式，{}条）：目标字段 {}'.format(
        (result.meta or {}).get('mode', 'precise'),
        (result.meta or {}).get('rules_n', 1), len(out_fields)))
    if result.rules is None:
        log.emit('ok', 'agent', '静态校验通过；干跑 {} 条；置信度 {}'.format(
            result.diagnostics.get('records_n', 0), result.confidence))
        if result.diagnostics.get('warning'):
            log.emit('warn', 'agent', result.diagnostics['warning'])
    out = result.as_dict()
    out['reference_doc_ids_json'] = doc_ids
    out['validation_report_json'] = result.diagnostics
    return out


# ---- P2b 入库：数据源 / 映射绑定 / introspection ----
# 数据源密码明文存库、API 明文返回（2026-11-21 裁决，页面可见可编辑）；
# 但日志永不打印凭据，测试连接回显仅 host:port/库名。

# ---- 计算层 API：index / rule / frame（定义 CRUD + run）----
# 三类前缀完全隔离；编排在 compute/orchestrate.py，本层只做请求校验。

@app.get('/api/compute/definitions')
def api_compute_definitions():
    return {'ok': True,
            'index': _load('store.index_repo').list_defs(),
            'rule': _load('store.rule_repo').list_defs(),
            'frame': _load('store.frame_repo').list_defs()}


@app.get('/api/compute/layout')
def api_compute_layout_list():
    return _load('store.compute_layout_repo').list_layout()


@app.put('/api/compute/layout')
async def api_compute_layout_save(request: Request):
    body = await _json_body(request)
    return {'ok': True, **_load('store.compute_layout_repo').save_layout(
        body.get('items'))}


@app.get('/api/compute/source-documents')
def api_compute_source_documents():
    definitions = _load('store.index_repo').list_defs()
    loader = _load('store.loader')
    catalog_load = _load('store.catalog.load')
    tables, errors, seen_tables = [], [], set()
    docs_by_table = {}
    for loaded in catalog_load.list_loaded_results():
        doc = dict(loaded, file_id=loaded['doc_id'])
        key = (doc['datasource_id'], doc['target_table'])
        docs_by_table.setdefault(key, []).append(doc)
    comments = {}
    datasource_ids = list(dict.fromkeys(
        definition['datasource_id'] for definition in definitions))
    for datasource_id in datasource_ids:
        names = list(dict.fromkeys(
            definition['source_table'] for definition in definitions
            if definition['datasource_id'] == datasource_id))
        ds = catalog_load.get_datasource(datasource_id)
        try:
            values = loader.table_comments(ds, names) if ds else {}
        except Exception:
            values = {}
            errors.append({'datasource_id': datasource_id,
                           'error': '表注释读取失败'})
        for name in names:
            comments[(datasource_id, name)] = values.get(name, '')
    for definition in definitions:
        table_key = (definition['datasource_id'], definition['source_table'])
        if table_key not in seen_tables:
            tables.append({'datasource_id': definition['datasource_id'],
                           'source_table': definition['source_table'],
                           'table_comment': comments.get(table_key, '')})
            seen_tables.add(table_key)
    items = []
    for definition in definitions:
        key = (definition['datasource_id'], definition['source_table'])
        for doc in docs_by_table.get(key, []):
            items.append({'index_id': definition['id'],
                          'source_table': definition['source_table'],
                          'file_id': doc['file_id'],
                          'file_name': doc.get('name') or (
                              '资料 #' + str(doc['file_id'])),
                          'row_count': int(doc['row_count'])})
    return {'ok': True, 'items': items, 'tables': tables, 'errors': errors}


@app.get('/api/index')
def api_index_list():
    return {'items': _load('store.index_repo').list_defs()}


@app.post('/api/index')
async def api_index_add(request: Request):
    body = await _json_body(request)
    did = _load('store.index_repo').save_def(
        body.get('name'), body.get('datasource_id'),
        body.get('source_table'), body.get('source_column'),
        body.get('aggregate'), body.get('filter_json'),
        index_id=body.get('id'))
    return {'ok': True, 'id': did}


@app.get('/api/index/{index_id}')
def api_index_get(index_id: int):
    d = _load('store.index_repo').get_def(index_id=index_id)
    if d is None:
        raise _load('store.errors').NotFound('指标定义不存在')
    return d


@app.delete('/api/index/{index_id}')
def api_index_del(index_id: int):
    _load('store.index_repo').delete_def(index_id)
    return {'ok': True}


@app.post('/api/index/{index_id}/run')
def api_index_run(index_id: int):
    return {'ok': True, **_load('compute').execute_index(index_id)}


@app.get('/api/index/{index_id}/values')
def api_index_values(index_id: int, limit: int = 200):
    return {'items': _load('store.index_repo').list_values(
        index_id=index_id, limit=limit)}


@app.get('/api/index/{index_id}/source-preview')
def api_index_source_preview(index_id: int, limit: int = 50):
    d = _load('store.index_repo').get_def(index_id=index_id)
    if d is None:
        raise _load('store.errors').NotFound('指标定义不存在')
    result = _load('compute').source_preview(d, limit=limit)
    ds = _load('store.catalog.load').get_datasource(d['datasource_id'])
    result['source']['table_comment'] = (
        _load('store.loader').table_comment(ds, d['source_table']) if ds else '')
    return {'ok': True, **result}


@app.get('/api/index/value/{value_id}/lineage')
def api_index_lineage(value_id: int):
    return {'ok': True, **_load('compute').parse_lineage('index', value_id)}


@app.get('/api/index/value/{value_id}/replay')
def api_index_replay(value_id: int):
    return {'ok': True, **_load('compute').replay_value('index', value_id)}


@app.get('/api/rule')
def api_rule_list():
    return {'items': _load('store.rule_repo').list_defs()}


@app.post('/api/rule')
async def api_rule_add(request: Request):
    body = await _json_body(request)
    did = _load('store.rule_repo').save_def(
        body.get('name'), body.get('index_refs'),
        body.get('conditions'), body.get('combine') or 'all',
        rule_id=body.get('id'))
    return {'ok': True, 'id': did}


@app.get('/api/rule/{rule_id}')
def api_rule_get(rule_id: int):
    d = _load('store.rule_repo').get_def(rule_id=rule_id)
    if d is None:
        raise _load('store.errors').NotFound('规则定义不存在')
    return d


@app.delete('/api/rule/{rule_id}')
def api_rule_del(rule_id: int):
    _load('store.rule_repo').delete_def(rule_id)
    return {'ok': True}


@app.post('/api/rule/{rule_id}/run')
def api_rule_run(rule_id: int):
    return {'ok': True, **_load('compute').execute_rule(rule_id)}


@app.get('/api/rule/{rule_id}/values')
def api_rule_values(rule_id: int, limit: int = 200):
    return {'items': _load('store.rule_repo').list_values(
        rule_id=rule_id, limit=limit)}


@app.get('/api/rule/value/{value_id}/lineage')
def api_rule_lineage(value_id: int):
    return {'ok': True, **_load('compute').parse_lineage('rule', value_id)}


@app.get('/api/rule/value/{value_id}/replay')
def api_rule_replay(value_id: int):
    return {'ok': True, **_load('compute').replay_value('rule', value_id)}


@app.get('/api/frame')
def api_frame_list():
    return {'items': _load('store.frame_repo').list_defs()}


@app.post('/api/frame')
async def api_frame_add(request: Request):
    body = await _json_body(request)
    did = _load('store.frame_repo').save_def(
        body.get('name'), body.get('rule_refs'),
        body.get('combine') or 'weighted', body.get('threshold'),
        frame_id=body.get('id'))
    return {'ok': True, 'id': did}


@app.get('/api/frame/{frame_id}')
def api_frame_get(frame_id: int):
    d = _load('store.frame_repo').get_def(frame_id=frame_id)
    if d is None:
        raise _load('store.errors').NotFound('框架定义不存在')
    return d


@app.delete('/api/frame/{frame_id}')
def api_frame_del(frame_id: int):
    _load('store.frame_repo').delete_def(frame_id)
    return {'ok': True}


@app.post('/api/frame/{frame_id}/run')
def api_frame_run(frame_id: int):
    return {'ok': True, **_load('compute').execute_frame(frame_id)}


@app.get('/api/frame/{frame_id}/values')
def api_frame_values(frame_id: int, limit: int = 200):
    return {'items': _load('store.frame_repo').list_values(
        frame_id=frame_id, limit=limit)}


@app.get('/api/frame/value/{value_id}/lineage')
def api_frame_lineage(value_id: int):
    return {'ok': True, **_load('compute').parse_lineage('frame', value_id)}


@app.get('/api/frame/value/{value_id}/replay')
def api_frame_replay(value_id: int):
    return {'ok': True, **_load('compute').replay_value('frame', value_id)}


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
def api_load_datasource_tables(ds_id: int, include_comment: bool = False):
    ds = _ds_or_404(ds_id)
    loader = _load('store.loader')
    tables = loader.list_tables(ds)
    if include_comment:
        return {'items': [
            {'name': table, 'table_comment': loader.table_comment(ds, table)}
            for table in tables]}
    return {'items': tables}


@app.get('/api/load/datasources/{ds_id}/columns')
def api_load_datasource_columns(ds_id: int, table: str = None):
    ds = _ds_or_404(ds_id)
    if not table:
        raise store_errors.BadRequest('table 参数必填')
    return {'items': _load('store.loader').list_columns(ds, table)}


@app.get('/api/load/datasources/{ds_id}/rows')
def api_load_datasource_rows(ds_id: int, table: str = None,
                             page: int = 1, per_page: int = 100,
                             file_id: str = None):
    """数据看板：只读分页查询业务表（表名白名单＋列白名单＋参数化）。"""
    ds = _ds_or_404(ds_id)
    if not table:
        raise store_errors.BadRequest('table 参数必填')
    return {'ok': True, **_load('store.loader').query_rows(
        ds, table, page=page, per_page=per_page, file_id=file_id)}


@app.get('/api/load/tables')
def api_load_tables(datasource_id: int = None):
    return {'items': _load('store.catalog').list_load_tables(datasource_id)}


@app.get('/api/load/business-table-options')
def api_load_business_table_options():
    """聊天选择其他目标表：只返回业务表，排除 c1_ 平台产品配置表。"""
    catalog = _load('store.catalog')
    loader = _load('store.loader')
    datasources, tables, warnings = [], [], []
    for ds in catalog.list_datasources():
        datasources.append({'id': ds['id'], 'name': ds.get('name')})
        try:
            names = loader.list_business_tables(ds)
        except Exception as exc:
            warnings.append('数据源 {} 暂不可用，已跳过'.format(
                ds.get('name') or ds['id']))
            logger.warning('可选业务表读取失败：datasource_id=%s error=%s',
                           ds['id'], type(exc).__name__)
            continue
        tables.extend({'datasource_id': ds['id'], 'table': name}
                      for name in names)
    logger.info('可选业务表读取完成：datasources=%s tables=%s skipped=%s',
                len(datasources), len(tables), len(warnings))
    return {'ok': True, 'datasources': datasources, 'tables': tables,
            'warnings': warnings}


@app.post('/api/load/tables')
async def api_load_table_add(request: Request):
    body = await _json_body(request)
    try:
        ds_id = int(body.get('datasource_id'))
    except (TypeError, ValueError):
        raise store_errors.BadRequest('须选择业务库')
    fields = body.get('fields')
    if isinstance(fields, list):
        fields = [dict(field, field_name=field.get('field_name') or field.get('name'))
                  for field in fields]
    lt_id = _load('store.catalog').create_load_table(
        ds_id, body.get('target_table'), fields)
    return {'ok': True, 'id': lt_id}


@app.get('/api/load/tables/{lt_id}')
def api_load_table_get(lt_id: int):
    lt = _load('store.catalog').get_load_table(lt_id)
    if lt is None:
        raise store_errors.NotFound('入库表配置不存在')
    return lt


@app.patch('/api/load/tables/{lt_id}')
async def api_load_table_patch(lt_id: int, request: Request):
    body = await _json_body(request)
    fields = body.get('fields')
    if isinstance(fields, list):
        fields = [dict(field, field_name=field.get('field_name') or field.get('name'))
                  for field in fields]
    _load('store.catalog').update_load_table(
        lt_id, target_table=body.get('target_table'), fields=fields)
    return {'ok': True}


@app.delete('/api/load/tables/{lt_id}')
def api_load_table_del(lt_id: int):
    _load('store.catalog').delete_load_table(lt_id)
    return {'ok': True}


@app.get('/api/load/bindings')
def api_load_bindings(doc_id: int = None, extract_result_id: int = None):
    return {'items': _load('store.catalog').list_bindings(
        doc_id=doc_id, extract_result_id=extract_result_id)}


@app.get('/api/load/bindings/{binding_id}')
def api_load_binding_get(binding_id: int):
    binding = _load('store.catalog').get_binding(binding_id=binding_id)
    if binding is None:
        raise store_errors.NotFound('入库绑定不存在')
    return binding


@app.post('/api/load/bindings')
async def api_load_binding_add(request: Request):
    body = await _json_body(request)
    try:
        result_id = int(body.get('extract_result_id'))
        table_id = int(body.get('load_table_id'))
    except (TypeError, ValueError):
        raise store_errors.BadRequest('须选择抽取结果与入库表配置')
    if result_id <= 0 or table_id <= 0:
        raise store_errors.BadRequest('须选择抽取结果与入库表配置')
    business_keys = body.get('business_keys')
    if business_keys is None:
        business_keys = body.get('business_key')
    if isinstance(business_keys, str) and business_keys.strip():
        business_keys = [business_keys.strip()]
    binding_id = _load('store.catalog').create_binding(
        result_id, table_id, body.get('field_map') or {},
        body.get('write_mode') or 'insert', business_keys)
    return {'ok': True, 'load_binding_id': binding_id}


@app.patch('/api/load/bindings/{binding_id}')
async def api_load_binding_patch(binding_id: int, request: Request):
    body = await _json_body(request)
    if body.get('confirmed') is True:
        _load('store.catalog').confirm_binding(binding_id)
    else:
        business_keys = body.get('business_keys')
        if business_keys is None:
            business_keys = body.get('business_key')
        if isinstance(business_keys, str) and business_keys.strip():
            business_keys = [business_keys.strip()]
        _load('store.catalog').update_binding(
            binding_id, load_table_id=body.get('load_table_id'),
            field_map=body.get('field_map'), write_mode=body.get('write_mode'),
            business_keys=business_keys)
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
    """资料详情：汇总状态、全部抽取结果与独立入库绑定。"""
    f = _file_or_404(file_id)
    catalog = _load('store.catalog')
    results = catalog.list_extract_results(file_id)
    bindings = {b['extract_result_id']: b for b in catalog.list_bindings(doc_id=file_id)}
    return {'file': {'file_id': file_id, 'doc_id': file_id,
                     'state': f['state'], 'error': f['error'],
                     'params': f.get('params_json') or {},
                     'created_at': str(f['created_at']), 'name': f['name'],
                     'records_n': sum(r['record_count'] for r in results),
                     'results': [dict(r, load_binding=bindings.get(r['id']))
                                 for r in results],
                     'files': [{'file_id': file_id, 'name': f['name'],
                                'state': f['state'],
                                'records_n': sum(r['record_count'] for r in results)}]}}


@app.get('/api/sources/{file_id}/config')
def api_file_config_get(file_id: int):
    """资料解析配置与可选规则/入库表；规则和入库绑定按结果单独管理。"""
    catalog = _load('store.catalog')
    f = _file_or_404(file_id)
    return {
        'ok': True, 'file_id': file_id, 'doc_id': file_id,
        'params': f.get('params_json') or {},
        'schema': params_mod.public_schema(),
        'rules': catalog.list_rules(),
        'datasources': catalog.list_datasources(),
        'load_tables': catalog.list_load_tables(),
    }


@app.post('/api/sources/{file_id}/config')
async def api_file_config_set(file_id: int, request: Request):
    """只更新解析参数；抽取规则与入库目标在对应结果上配置。"""
    catalog = _load('store.catalog')
    f = _file_or_404(file_id)
    if f['state'] in ('parsing', 'loading'):
        raise store_errors.Conflict('资料处理中，配置只读')
    body = await _json_body(request)
    changed = []
    if 'params' in body:
        params, _warns = params_mod.normalize(body.get('params'))
        catalog.set_params(file_id, params)
        changed.append('params')
    return {'ok': True, 'file_id': file_id, 'changed': changed}


def _result_or_404(extract_result_id):
    result = _load('store.catalog').get_extract_result(extract_result_id)
    if result is None:
        raise store_errors.NotFound('抽取结果不存在')
    return result


def _binding_or_empty(binding_id):
    binding = _load('store.catalog').get_binding(binding_id=binding_id)
    return binding or {}


@app.get('/api/sources/{file_id}/extract-results')
def api_file_extract_results(file_id: int):
    _file_or_404(file_id)
    catalog = _load('store.catalog')
    bindings = {b['extract_result_id']: b for b in
                catalog.list_bindings(doc_id=file_id)}
    return {'ok': True, 'items': [dict(r, load_binding=bindings.get(r['id']))
                                  for r in catalog.list_extract_results(file_id)]}


@app.get('/api/extract-results/{extract_result_id}')
def api_extract_result_detail(extract_result_id: int):
    result = _result_or_404(extract_result_id)
    binding = _load('store.catalog').get_binding(
        extract_result_id=extract_result_id)
    return {'ok': True, 'result': result, 'load_binding': binding}


@app.delete('/api/extract-results/{extract_result_id}')
def api_extract_result_delete(extract_result_id: int):
    result = _result_or_404(extract_result_id)
    binding = _load('store.catalog').get_binding(
        extract_result_id=extract_result_id)
    if binding and binding['status'] in ('confirmed', 'running', 'ready'):
        raise store_errors.Conflict('已确认或已入库的抽取结果不可删除')
    _load('store.catalog').purge_extract_result(extract_result_id)
    remaining = _load('store.catalog').list_extract_results(result['doc_id'])
    if remaining:
        service.derive_review_state(remaining[0]['id'])
    else:
        _load('store.catalog').set_state(result['doc_id'], 'to_extract', None)
    return {'ok': True, 'doc_id': result['doc_id']}


@app.post('/api/extract-results/{extract_result_id}/rerun')
async def api_extract_result_rerun(extract_result_id: int, request: Request):
    raw = await request.body()
    body = await _json_body(request) if raw else {}
    return await run_in_threadpool(
        service.run_extract, _result_or_404(extract_result_id)['doc_id'],
        force=body.get('force') is True,
        extract_result_id=extract_result_id)


@app.post('/api/sources/{file_id}/extract')
async def api_file_run_extract(file_id: int, request: Request):
    """按单条规则抽取；同资料同规则覆盖该结果，其他规则结果不变。"""
    _file_or_404(file_id)
    raw = await request.body()
    body = await _json_body(request) if raw else {}
    rule_id = body.get('rule_id')
    if not isinstance(rule_id, int) or isinstance(rule_id, bool) or rule_id <= 0:
        raise store_errors.BadRequest('请选择抽取规则')
    return await run_in_threadpool(
        service.run_extract, file_id, force=body.get('force') is True,
        rule_id=rule_id)


@app.get('/api/extract-results/{extract_result_id}/gate')
def api_extract_result_gate(extract_result_id: int):
    _result_or_404(extract_result_id)
    return dict(_load('store.content_db').gate_counts(extract_result_id), ok=True)


@app.post('/api/extract-results/{extract_result_id}/approve-all')
def api_extract_result_approve_all(extract_result_id: int):
    _result_or_404(extract_result_id)
    return service.approve_all(extract_result_id)


@app.get('/api/extract-results/{extract_result_id}/load-log')
def api_extract_result_load_log(extract_result_id: int):
    _result_or_404(extract_result_id)
    binding = _load('store.catalog').get_binding(
        extract_result_id=extract_result_id)
    items = (_load('store.catalog').list_receipts(
        load_binding_id=binding['id']) if binding else [])
    return {'ok': True, 'items': items}


@app.get('/api/sources/{file_id}/load-log')
def api_file_load_log(file_id: int):
    _file_or_404(file_id)
    return {'ok': True, 'items': _load('store.catalog').list_receipts(doc_id=file_id)}


@app.get('/api/extract-results/{extract_result_id}/load-plan')
def api_extract_result_load_plan_get(extract_result_id: int):
    _result_or_404(extract_result_id)
    plan = _load('store.load_planner').get_plan(extract_result_id)
    if plan is None:
        return JSONResponse({'ok': False, 'error': '尚无入库规划'}, status_code=404)
    return dict(plan, ok=True)


@app.post('/api/extract-results/{extract_result_id}/load-plan')
async def api_extract_result_load_plan(extract_result_id: int, request: Request):
    """推荐业务表与字段映射；只读业务库，不写业务数据。"""
    _result_or_404(extract_result_id)
    raw = await request.body()
    body = await _json_body(request) if raw else {}
    intent = body.get('intent') or body
    if not isinstance(intent, dict):
        raise store_errors.BadRequest('入库规划须为 JSON 对象')
    plan = await run_in_threadpool(
        _load('store.load_planner').plan_for_extract_result,
        extract_result_id, intent.get('datasource_id'), intent)
    return dict(plan, ok=True)


@app.post('/api/extract-results/{extract_result_id}/load-plan/apply')
async def api_extract_result_load_plan_apply(extract_result_id: int,
                                             request: Request):
    _result_or_404(extract_result_id)
    body = await _json_body(request)
    intent = body.get('intent') or body
    if not isinstance(intent, dict):
        raise store_errors.BadRequest('入库规划须为 JSON 对象')
    return await run_in_threadpool(
        _load('auto_service').apply_plan, extract_result_id, intent)


@app.post('/api/extract-results/{extract_result_id}/load')
async def api_extract_result_load(extract_result_id: int):
    _result_or_404(extract_result_id)
    return await run_in_threadpool(service.launch_load, extract_result_id)


@app.post('/api/sources/{file_id}/reparse')
async def api_file_reparse(file_id: int, request: Request):
    """重放解析；已入库资料须显式 test_mode，正式数据和状态保持不变。"""
    body = await _json_body(request)
    if not isinstance(body, dict):
        raise store_errors.BadRequest('请求体须为 JSON 对象')
    return await run_in_threadpool(service.reparse, file_id,
                                   test_mode=body.get('test_mode') is True)


@app.post('/api/extract-results/{extract_result_id}/load-preview')
async def api_extract_result_load_preview(extract_result_id: int,
                                          request: Request):
    """入库 dry-run；只读目标业务表，不创建绑定、不写记录。"""
    _result_or_404(extract_result_id)
    body = await _json_body(request)
    draft = body.get('draft')
    if not isinstance(draft, dict):
        table_id = body.get('load_table_id')
        keys = ('datasource_id', 'target_table', 'field_map',
                'write_mode', 'business_keys', 'business_key')
        if table_id is None and not any(key in body for key in keys):
            draft = None
        elif table_id is None:
            draft = {key: body[key] for key in keys if key in body}
        else:
            lt = _load('store.catalog').get_load_table(int(table_id))
            if lt is None:
                raise store_errors.NotFound('入库表配置不存在')
            draft = {'datasource_id': lt['datasource_id'],
                     'target_table': lt['target_table']}
    return service.preview_load(extract_result_id, draft=draft)


@app.get('/api/extract-results/{extract_result_id}/quarantine')
def api_extract_result_quarantine(extract_result_id: int):
    _result_or_404(extract_result_id)
    return {'ok': True,
            'items': _load('store.catalog').list_quarantine(
                extract_result_id=extract_result_id)}


@app.get('/api/sources/{file_id}/quarantine')
def api_file_quarantine(file_id: int):
    """隔离区只读展示：该资料全部抽取结果的隔离条目。"""
    _file_or_404(file_id)
    return {'ok': True,
            'items': _load('store.catalog').list_quarantine(doc_id=file_id)}


@app.get('/api/sources/{file_id}/parse')
def api_file_extract(file_id: int):
    doc = _load('store.content').get_extract(file_id)
    if doc is None:
        return JSONResponse({'ok': False, 'error': 'parse.json 不存在'},
                            status_code=404)
    return doc


@app.get('/api/extract-results/{extract_result_id}/staging')
def api_extract_result_staging(extract_result_id: int):
    doc = _load('store.content_db').get_records(extract_result_id)
    if doc is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    return doc


@app.get('/api/staging/query')
def api_staging_query(field: str = None, q: str = None,
                      task: str = None, state: str = None,
                      extract_result_id: int = None, doc_id: int = None):
    """跨结果暂存查询；task 保留为 doc_id 别名。"""
    rows = _load('store.content_db').query_fields(
        field, q, task, state, extract_result_id=extract_result_id,
        doc_id=doc_id)
    return {'ok': True, 'items': rows}


@app.get('/api/extract-results/{extract_result_id}/record-ids')
def api_extract_result_record_ids(extract_result_id: int):
    _result_or_404(extract_result_id)
    mapping = _load('store.content_db').record_id_map(extract_result_id)
    return {'ok': True, 'items': [
        {'index': key[1], 'record_id': rid}
        for key, rid in sorted(mapping.items(), key=lambda item: item[0][1])]}


@app.get('/api/sources/{file_id}/record-ids')
def api_source_record_ids(file_id: int):
    _file_or_404(file_id)
    items = []
    for result in _load('store.catalog').list_extract_results(file_id):
        mapping = _load('store.content_db').record_id_map(result['id'])
        items.extend({'extract_result_id': key[0], 'index': key[1],
                      'record_id': rid}
                     for key, rid in sorted(mapping.items(),
                                            key=lambda item: item[0][1]))
    return {'ok': True, 'items': items}


@app.post('/api/staging/trace-batch')
async def api_staging_trace_batch(request: Request):
    """当前页批量溯源状态：一次请求判断 record_id→资料/字段/图像锚点。"""
    body = await _json_body(request)
    if not isinstance(body, dict):
        raise store_errors.BadRequest('请求体须为 JSON 对象')
    items = _load('store.content_db').trace_records(
        body.get('record_ids'), body.get('columns'))
    return {'ok': True, 'items': items}


@app.get('/api/staging/locate/{record_id}')
def api_staging_locate(record_id: int, key: str = None):
    """按 record_id 反查 file_id，用于数据看板血缘跳转。
    key=业务表列名时附带 field（暂存字段名）与完整 field_map，
    供单元格级回溯与「原图→表格」反向定位。"""
    catalog = _load('store.catalog')
    hit = _load('store.content_db').locate_record(record_id)
    if hit is None:
        return JSONResponse({'ok': False, 'error': '暂存记录不存在'},
                            status_code=404)
    binding = catalog.get_binding(extract_result_id=hit['extract_result_id'])
    field_map = (binding or {}).get('field_map_json') or {}
    out = {'ok': True, **hit, 'field_map': field_map}
    if key is not None:
        reverse_map = {column: name for name, column in field_map.items()}
        out['field'] = reverse_map.get(key, key)
    return out


def _review_guard(extract_result_id):
    """已执行入库的结果只读；其他结果仍可独立复核。"""
    result = _result_or_404(extract_result_id)
    if result['status'] != 'ready':
        raise store_errors.Conflict('抽取结果尚未完成，记录只读')
    binding = _load('store.catalog').get_binding(
        extract_result_id=extract_result_id)
    if binding and binding['status'] in ('confirmed', 'running', 'ready'):
        raise store_errors.Conflict('已确认或已入库的记录只读')


@app.patch('/api/extract-results/{extract_result_id}/staging/{index}')
async def api_staging_patch(extract_result_id: int, index: int,
                            request: Request):
    """校验改值：values 差量合并，original 与血缘不变。"""
    _review_guard(extract_result_id)
    body = await _json_body(request)
    values = body.get('values')
    if not isinstance(values, dict) or not values:
        return JSONResponse({'ok': False, 'error': 'values 须为非空对象'},
                            status_code=400)
    rec = _load('store.content_db').patch_record(
        extract_result_id, index, values)
    return {'ok': True, 'record': rec,
            'doc_state': service.derive_review_state(extract_result_id)}


@app.post('/api/extract-results/{extract_result_id}/staging/review')
async def api_staging_review(extract_result_id: int, request: Request):
    """批量确认/拒绝单个抽取结果的记录。"""
    _review_guard(extract_result_id)
    body = await _json_body(request)
    indexes = body.get('indexes')
    state = body.get('state')
    if not isinstance(indexes, list) or not indexes \
            or not all(isinstance(i, int) and not isinstance(i, bool)
                       for i in indexes):
        return JSONResponse(
            {'ok': False, 'error': 'indexes 须为非空整数数组'},
            status_code=400)
    if state not in ('confirmed', 'rejected'):
        return JSONResponse(
            {'ok': False, 'error': 'state 仅支持 confirmed/rejected'},
            status_code=400)
    n = _load('store.content_db').set_review(
        extract_result_id, indexes, state)
    return {'ok': True, 'updated': n,
            'doc_state': service.derive_review_state(extract_result_id)}


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

    logger.info('结构化工具地址：http://%s:%s', config.HOST, config.PORT)
    logger.info('结构化工具存储：%s', _load('store.db').safe_detail(config.PLATFORM_DB))
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level='info',
                log_config=_load('logging_config').uvicorn_log_config())
