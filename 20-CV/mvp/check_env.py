"""
mvp/check_env.py — 独立部署自检（只读，不加载任何模型权重，秒级完成）。

用法：
    cd mvp && python check_env.py

检查三件事：
    1) requirements.txt 里的包能否 import、装的是哪个版本
    2) input/ output/ 是否存在且可写
    3) PaddleX 官方模型缓存是否就绪（没有→首次处理会联网下载）

有任何缺包时退出码为 1，方便在 CI / Docker build 里当门禁用。
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
                        ('assets', config.ASSETS_DIR)):
        ok = os.path.isdir(path) and (label == 'assets'
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


def main():
    print('Python {} · mvp = {}'.format(sys.version.split()[0], ROOT))
    print('\n[1/3] 依赖包')
    missing = check_packages()
    print('\n[2/3] 目录')
    bad_dirs = check_dirs()
    print('\n[3/3] 模型缓存')
    check_models()
    print('\n结论：', '依赖齐全，可启动' if not (missing or bad_dirs)
          else '缺 {} 个包 / {} 个目录，执行 pip install -r requirements.txt'.format(
              len(missing), len(bad_dirs)))
    return 1 if (missing or bad_dirs) else 0


if __name__ == '__main__':
    sys.exit(main())
