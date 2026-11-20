"""
mvp/check_env.py — 独立部署自检（只读，不加载任何模型权重，秒级完成）。

用法：
    cd mvp && python check_env.py

检查四件事：
    1) requirements.txt 里的包能否 import、装的是哪个版本
    2) input/ output/ sources/ data/ 是否存在且可写
    3) PaddleX 官方模型缓存是否就绪（没有→首次处理会联网下载）
    4) 平台库（MySQL）连通性 —— 可选项，连不上只 WARN（降级隔离，提取照常）

有任何缺包时退出码为 1，方便在 CI / Docker build 里当门禁用。
平台库不通 / 未装 PyMySQL 不影响退出码（P0 降级设计：文件链路独立可用）。
"""
import os
import sys
import importlib
from importlib.metadata import version, PackageNotFoundError

ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# 与 app.py 一致：以包方式加载，静态分析器无需任何 IDE 配置
config = importlib.import_module(PKG + '.config')

# (pip 发行包名, import 名, 用途)
PACKAGES = [
    ('fastapi', 'fastapi', 'Web 框架'),
    ('uvicorn', 'uvicorn', 'ASGI 服务器'),
    ('jinja2', 'jinja2', '对照报告模板渲染'),
    ('paddlepaddle', 'paddle', 'Paddle 运行时'),
    ('paddleocr', 'paddleocr', 'OCR / 表格模型'),
    ('paddlex', 'paddlex', '模型管线'),
    ('opencv-contrib-python', 'cv2', '网格预筛（cv2）'),
    ('numpy', 'numpy', '数值计算'),
    ('Pillow', 'PIL', '图像处理'),
    ('pdfplumber', 'pdfplumber', '文本层表格 + bbox'),
    ('PyMuPDF', 'pymupdf', 'PDF 首页渲染'),
]


def check_packages():
    missing = []
    for dist, mod, use in PACKAGES:
        try:
            importlib.import_module(mod)
            try:
                v = version(dist)
            except PackageNotFoundError:
                v = '? (换个发行包装的)'
            print('  OK      {:<24} {:<14} {}'.format(dist, v, use))
        except Exception as e:
            missing.append(dist)
            print('  MISSING {:<24} {:<14} {} · {}'.format(
                dist, '-', use, type(e).__name__))
    return missing


def check_dirs():
    bad = []
    for label, path in (('input', config.INPUT_DIR),
                        ('output', config.OUTPUT_DIR),
                        ('logs', config.LOG_DIR),
                        ('sources', config.SOURCES_DIR),
                        ('data', config.DATA_DIR),
                        ('assets', config.ASSETS_DIR),
                        ('templates', config.TEMPLATES_DIR)):
        ok = os.path.isdir(path) and (label in ('assets', 'templates')
                                      or os.access(path, os.W_OK))
        print('  {:<7} {:<8} {}'.format('OK' if ok else 'FAIL',
                                        label, path))
        if not ok:
            bad.append(path)
    return bad


def check_models():
    cache = (os.environ.get('PADDLE_PDX_CACHE_HOME')
             or os.path.join(os.path.expanduser('~'), '.paddlex'))
    models = os.path.join(cache, 'official_models')
    if os.path.isdir(models):
        n = len([d for d in os.listdir(models)
                 if os.path.isdir(os.path.join(models, d))])
        print('  OK      模型缓存 {}（{} 个模型）'.format(models, n))
        if n < 5:
            print('           模型偏少，首次处理仍可能联网补齐')
    else:
        print('  WARN    未找到模型缓存 {}'.format(models))
        print('           首次处理会联网下载（数百 MB）；离线部署请先预置该目录')
        print('           并设置环境变量 PADDLE_PDX_CACHE_HOME 指向其上级目录')


def check_platform_db():
    """平台库（MySQL）连通性：可选项，失败不致命（降级隔离，提取照常）。

    只读探针（SELECT VERSION()，不触发迁移、不写库）；只回显脱敏 host/库名，
    凭据永不打印。未装 PyMySQL / 未配引用 / 连不上 → WARN + 降级说明。
    """
    ref = config.PLATFORM_DB_REF
    try:
        import pymysql
    except Exception:
        print('  WARN    未装 PyMySQL：平台库不可用，降级运行（文件链路照常）')
        print('           启用平台库：pip install -r requirements.txt'
              '（含 PyMySQL + cryptography）')
        return
    db = importlib.import_module(PKG + '.store.db')
    try:
        p = db._parts(db.resolve_conn(ref))
    except Exception as e:
        print('  WARN    凭据引用 {} 未配置：{}'.format(ref, e))
        print('           设环境变量 {} 或 data/secrets.json；未配置则降级运行'
              .format(ref))
        return
    detail = '{}:{}/{}'.format(p['host'], p['port'], p['database'])
    try:
        conn = pymysql.connect(
            host=p['host'], port=p['port'], user=p['user'],
            password=p['password'], database=p['database'],
            charset='utf8mb4', connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT VERSION()')
                ver = cur.fetchone()[0]
        finally:
            conn.close()
        print('  OK      MySQL {} · {}'.format(ver, detail))
    except Exception as e:
        print('  WARN    平台库连接失败（{}）：{}'.format(detail, type(e).__name__))
        print('           提取与预览降级照常；资料目录 / 登记暂不可用')


def main():
    print('Python {} · mvp = {}'.format(sys.version.split()[0], ROOT))
    print('\n[1/4] 依赖包')
    missing = check_packages()
    print('\n[2/4] 目录')
    bad_dirs = check_dirs()
    print('\n[3/4] 模型缓存')
    check_models()
    print('\n[4/4] 平台库（可选 · 降级隔离）')
    check_platform_db()
    print('\n结论：', '依赖齐全，可启动' if not (missing or bad_dirs)
          else '缺 {} 个包 / {} 个目录，执行 pip install -r requirements.txt'.format(
              len(missing), len(bad_dirs)))
    return 1 if (missing or bad_dirs) else 0


if __name__ == '__main__':
    sys.exit(main())
