"""
mvp/app.py — Web 工具入口（FastAPI + uvicorn）。只负责路由与任务编排。

启动：
    D:\\miniforge3\\envs\\paddle\\python.exe mvp/app.py
    浏览器打开 http://127.0.0.1:8765

路由：
    GET  /              上传页（assets/upload.html + /static 资源）
    GET  /healthz       健康检查
    POST /api/upload    上传（base64 JSON，不依赖 python-multipart）
    GET  /api/status    处理进度
    GET  /report        生成的报告
    /files/<path>       各 case 的产物
    /static/<path>      上传页的 css / js

提取逻辑在 pipeline/，报告生成在 report/，配置在 config.py。
"""
import os
import re
import time
import base64
import threading
import traceback

import config                      # 必须第一个导入：设置 paddle 环境变量
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title='CV 提取 MVP', version='0.1')
app.mount('/files', StaticFiles(directory=config.OUTPUT_DIR), name='files')
app.mount('/static', StaticFiles(directory=config.ASSETS_DIR), name='static')

# 单任务串行：模型单例不是线程安全的，也没必要并发加载第二份大模型
STATE = {
    'running': False, 'ready': False, 'error': None,
    'steps': [], 'cases': [], 'started': None, 'elapsed': 0,
}
LOCK = threading.Lock()


def step(msg):
    with LOCK:
        STATE['steps'].append(msg)


def safe_name(name):
    """只替换 Windows 文件名非法字符，保留中文与空格。"""
    name = os.path.basename(name or 'upload.bin')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip()
    return name[:120] or 'upload.bin'


def case_dir_name(index, name):
    stem = os.path.splitext(name)[0]
    stem = re.sub(r'[^\w\u4e00-\u9fff.-]', '_', stem)[:60]
    return '{:02d}_{}'.format(index, stem)


def asset(name):
    with open(os.path.join(config.ASSETS_DIR, name), 'r',
              encoding='utf-8') as f:
        return f.read()


@app.get('/', response_class=HTMLResponse)
def index():
    return HTMLResponse(asset('upload.html'))


@app.get('/healthz')
def health():
    return {'ok': True, 'service': 'cv-mvp', 'running': STATE['running']}


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

    paths = []
    for item in files:
        name = safe_name(item.get('name', ''))
        ext = os.path.splitext(name)[1].lower()
        if ext not in config.ALLOWED_EXTS:
            return JSONResponse(
                {'ok': False, 'error': '不支持的格式：{}'.format(ext)},
                status_code=400)
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
        path = os.path.join(config.INPUT_DIR, name)
        with open(path, 'wb') as f:
            f.write(data)
        paths.append(path)

    with LOCK:
        STATE.update(running=True, ready=False, error=None, steps=[],
                     cases=[], started=time.time(), elapsed=0)
    threading.Thread(target=run_batch, args=(paths,), daemon=True).start()
    return {'ok': True, 'count': len(paths)}


@app.get('/api/status')
def status():
    with LOCK:
        return dict(STATE)


@app.get('/report')
def report():
    path = os.path.join(config.OUTPUT_DIR, config.REPORT_NAME)
    if not os.path.isfile(path):
        return HTMLResponse(
            '<h3>还没有报告</h3><p><a href="/">返回上传页</a>先上传一个文件。</p>')
    return FileResponse(path, media_type='text/html; charset=utf-8')


def run_batch(paths):
    """后台线程：逐个提取 → 落 result.json → 生成汇总报告。"""
    try:
        import pipeline
        import report as report_mod
        records = []
        for i, path in enumerate(paths, 1):
            name = os.path.basename(path)
            step('[{}/{}] 正在处理 {} …'.format(i, len(paths), name))
            case_rel = case_dir_name(i, name)
            case_abs = os.path.join(config.OUTPUT_DIR, case_rel)
            os.makedirs(case_abs, exist_ok=True)
            rec = pipeline.extract_one(path, case_abs, case_rel)
            records.append(rec)
            step('  ✓ 识别 {} 行文字 · 结构化表格 {} 张 · 路线 {}'.format(
                rec['lines'], len(rec['structured_tables']),
                rec['table_route']))
        step('正在生成报告 …')
        report_mod.build(
            records, os.path.join(config.OUTPUT_DIR, config.REPORT_NAME))
        with LOCK:
            STATE.update(running=False, ready=True,
                         cases=[r['file'] for r in records],
                         elapsed=round(time.time()
                                       - (STATE['started'] or time.time()), 1))
        step('完成，共 {} 个文件，耗时 {}s'.format(
            len(records), STATE['elapsed']))
    except Exception as e:
        step('出错：' + str(e))
        with LOCK:
            STATE.update(running=False, ready=False, error=str(e))
        print(traceback.format_exc(limit=3))


if __name__ == '__main__':
    import uvicorn
    print('>> CV MVP 启动： http://{}:{}'.format(config.HOST, config.PORT))
    print('>> 输入目录：{}'.format(config.INPUT_DIR))
    print('>> 产物目录：{}'.format(config.OUTPUT_DIR))
    uvicorn.run(app, host=config.HOST, port=config.PORT,
                log_level='warning')
