"""
第2周 · 模块A：批量跑真实图片（PaddleOCR 3.7.0 版，可直接运行）

【这份脚本在做什么】
把 input/ 下的图片逐张交给 PaddleOCR，把「每张图识别到什么」存成结构化结果，
用来建立 "什么场景效果好、什么场景效果差" 的直觉，并为 bad case 库挑素材。

环境（本机 miniforge，环境名就是 paddle）：
    conda activate paddle

用法（在 week-02 目录下）：
    python a_batch_ocr.py                        # 用配置区 INPUT_DIR
    python a_batch_ocr.py ../week-01/input       # 命令行临时指定别的图片目录

产物（都在 output/ 下）：
    batch_ocr_results.json   每张图一条记录：文件名 / 行数 / 置信度 / 坐标 / 耗时
    batch_ocr_summary.txt    纯文本汇总，方便直接打开看全文
    vis/index.html           ★ 可视化对照报告：原图 + 识别框 + 逐行文字，浏览器打开即可
    vis/*_boxes.png          ★ 每张原图的带框版本，可直接贴进 bad case 笔记
可视化由 vis_ocr_result.py 生成，跑完本脚本会自动调用；不想要可把 MAKE_VIS 改 False。

【与第1周的关系】
第1周的 b_ocr_image.py 一次只跑一张图；这里复用同样的 3.x API，
只是外面套了一层「遍历目录 → 逐张记录 → 统一落盘」。
模型在进程里只加载一次，之后每张图只剩推理耗时。

【3.x 与 2.x 的三个区别（第1周踩过的坑）】
    use_angle_cls            → use_textline_orientation
    ocr.ocr(path, cls=True)  → ocr.predict(path)
    result[0] / line[1][0]   → res['rec_texts'] / res['rec_scores'] / res['rec_polys']
"""

# =========================== 配置区：调试只改这里 ===========================
INPUT_DIR = 'input'                              # 图片目录（相对当前工作目录）
OUT_DIR = 'output'                               # 产物目录，不存在会自动创建
OUT_JSON = 'output/batch_ocr_results.json'       # 结构化结果；改成 None 就不写
OUT_TXT = 'output/batch_ocr_summary.txt'         # 纯文本汇总；改成 None 就不写
DET_MODEL = 'PP-OCRv4_mobile_det'                # 检测模型（找文字在哪）
REC_MODEL = 'PP-OCRv4_mobile_rec'                # 识别模型（读出来）
# 模型说明：无 GPU 时 server 大模型在 CPU 上极慢（第1周实测 104s vs mobile 3.8s），
#           这里沿用第1周已缓存的 mobile 模型，免下载、跑得快。
LOW_SCORE = 0.8                                 # 低于此置信度算「可疑行」，用于挑 bad case
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp')   # 只处理这些后缀，不区分大小写
# 文档预处理开关（整页方向分类 + UVDoc 去扭曲）：
#   False（推荐）：坐标就是原图像素坐标，可视化报告里的框才套得准；少加载 2 个模型。
#   True         ：对弯曲/歪斜的真实拍照文档可能识别更好，但 rec_polys 会基于
#                  矫正后的图像，画回原图时框会整体错位。想试时改成 True 再跑一次。
USE_DOC_PREPROCESS = False
MAKE_VIS = True                                  # 跑完自动生成可视化对照报告（建议保持 True）
VIS_DIR = 'output/vis'                           # 可视化产物目录
MANIFEST_NAME = 'samples_manifest.json'          # 说明书文件名，脚本会在图片目录里找它
# ==========================================================================

import os       # 拼路径、列目录、建文件夹
import sys      # 读命令行参数 sys.argv
import json     # 把结果写成 .json 文件
import time     # 计时：perf_counter() 相减得到秒数

# 这两个环境变量必须在 import paddleocr 之前设置：paddlex 在被导入时会读一次并「快照」，
# 之后再改就无效了。BOS 是国内模型源，避免第1周遇到的 HuggingFace 下载卡住。
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

from paddleocr import PaddleOCR  # noqa: E402  （放在 env 设置之后是故意的）


def list_images(src_dir):
    """列出目录里的图片，返回完整路径组成的列表。"""
    if not os.path.isdir(src_dir):
        sys.exit(
            f'找不到图片目录：{os.path.abspath(src_dir)}\n'
            f'改文件顶部的 INPUT_DIR，或命令行指定：python a_batch_ocr.py 图片目录'
        )
    # sorted() 保证每次运行顺序一致，方便前后对比。
    # name.lower().endswith(...) 让 .JPG 这种大写后缀也能被认出来。
    names = sorted(
        name for name in os.listdir(src_dir)
        if name.lower().endswith(IMAGE_EXTS)
    )
    return [os.path.join(src_dir, name) for name in names]


def build_ocr():
    """创建 OCR 引擎（这一步会加载模型，整个进程只做一次）。"""
    print(f'>> 初始化 PaddleOCR（det={DET_MODEL}, rec={REC_MODEL}），首次加载稍慢…')
    t0 = time.perf_counter()
    ocr = PaddleOCR(
        text_detection_model_name=DET_MODEL,
        text_recognition_model_name=REC_MODEL,
        use_textline_orientation=True,   # 3.x 名称，替代已废弃的 use_angle_cls
        # 不传 lang：显式指定模型名时 lang / ocr_version 会被忽略并报警告，
        # 语言能力已由所选模型决定（PP-OCRv4_mobile_rec 本身就是中英模型）。
        #
        # ↓ 由顶部 USE_DOC_PREPROCESS 控制，默认 False（关闭）。
        # 默认开启的「整页方向分类 + UVDoc 去扭曲」会先把图片矫正一遍，
        # 返回的 rec_polys 是矫正后图像的坐标，直接画回原图时框会整体偏移
        # （实测标题框 y=27~66，而标题墨迹实际在 y=66~98）。
        # 关闭后坐标就是原图像素坐标：标题框 [[74,67],[461,98]] 与墨迹
        # y66~98 / x71~462 完全吻合，可视化报告才准确；顺带少加载 2 个模型。
        # 识别出来的「文字内容」不受影响，受影响的只有坐标。
        # 以后若真要处理弯曲/拍照歪斜的文档可以再打开，但那时需自行做坐标反变换。
        use_doc_orientation_classify=USE_DOC_PREPROCESS,
        use_doc_unwarping=USE_DOC_PREPROCESS,
    )
    print(f'>> 模型加载耗时：{time.perf_counter() - t0:.2f}s')
    return ocr


def to_plain(value):
    """坐标是 numpy 数组，不能直接写进 JSON；.tolist() 转成普通 list。"""
    return value.tolist() if hasattr(value, 'tolist') else value


def recognize(ocr, path):
    """识别一张图，返回一条 dict 记录。"""
    t0 = time.perf_counter()
    results = ocr.predict(path)          # 3.x 用 predict，返回 list[结果对象]
    elapsed = time.perf_counter() - t0

    # predict 对单张图通常只返回 1 个结果；写成循环是为了兼容一次多图的情况。
    texts, scores, boxes = [], [], []
    for res in results:
        texts.extend(res['rec_texts'])                       # 每行文字
        scores.extend(float(s) for s in res['rec_scores'])   # 对应置信度
        polys = res.get('rec_polys') or res.get('dt_polys') or []
        boxes.extend(to_plain(b) for b in polys)             # 每行文字的四点坐标

    avg = sum(scores) / len(scores) if scores else 0.0
    return {
        'file': os.path.basename(path),
        'lines': len(texts),
        'avg_score': round(avg, 4),
        'low_score_lines': sum(1 for s in scores if s < LOW_SCORE),
        'elapsed': round(elapsed, 2),
        'texts': texts,
        'scores': [round(s, 4) for s in scores],
        'boxes': boxes,
    }


def save_results(records, out_json, out_txt):
    """把全部记录写成 JSON + 纯文本汇总。"""
    os.makedirs(OUT_DIR, exist_ok=True)   # exist_ok=True：目录已存在也不报错
    payload = {
        'model': {'det': DET_MODEL, 'rec': REC_MODEL},
        'image_count': len(records),
        'records': records,
    }
    if out_json:
        # ensure_ascii=False 保证中文原样写入，不变成 \uXXXX；indent=2 方便人看。
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    if out_txt:
        lines = [
            f'模型：{DET_MODEL} + {REC_MODEL}',
            f'图片数：{len(records)}',
            '',
        ]
        for rec in records:
            lines.append(
                f'=== {rec["file"]} | {rec["lines"]} 行 | '
                f'平均置信度 {rec["avg_score"]:.2f} | {rec["elapsed"]}s ==='
            )
            if rec.get('error'):
                lines.append(f'识别失败：{rec["error"]}')
            # zip() 把文字和置信度一一配对
            for text, score in zip(rec['texts'], rec['scores']):
                lines.append(f'{text}\t{score:.2f}')
            lines.append('')
        with open(out_txt, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    print(f'>> 结果已保存：{out_json or "(未写 JSON)"}、{out_txt or "(未写 TXT)"}')


def main():
    # 命令行第一个参数优先于配置区，方便临时指向别的图片目录。
    src_dir = sys.argv[1] if len(sys.argv) > 1 else INPUT_DIR
    images = list_images(src_dir)

    # 没有图片就直接退出，不加载模型 —— 省得白等几秒。
    if not images:
        print(f'>> {os.path.abspath(src_dir)} 里没有图片（支持 {", ".join(IMAGE_EXTS)}）')
        print('>> 先把收集的图片放进 input/，或用命令行指定别的目录。')
        return

    print(f'>> 共 {len(images)} 张图片，开始批量识别')
    ocr = build_ocr()                 # 只创建一次，后面循环复用
    t_all = time.perf_counter()

    records = []
    for i, path in enumerate(images, start=1):   # enumerate 同时给序号和元素
        name = os.path.basename(path)
        try:
            rec = recognize(ocr, path)
        except Exception as e:
            # 单张失败不能让整批中断，记下来继续跑下一张。
            print(f'>> [{i}/{len(images)}] {name} 识别失败：{e}')
            rec = {
                'file': name, 'error': str(e), 'lines': 0,
                'avg_score': 0.0, 'low_score_lines': 0, 'elapsed': 0.0,
                'texts': [], 'scores': [], 'boxes': [],
            }
        records.append(rec)
        if not rec.get('error'):
            print(
                f'>> [{i}/{len(images)}] {name}: {rec["lines"]} 行, '
                f'平均置信度 {rec["avg_score"]:.2f}, '
                f'低置信 {rec["low_score_lines"]} 行, {rec["elapsed"]}s'
            )

    save_results(records, OUT_JSON, OUT_TXT)
    # 先记下「纯识别」耗时，再画图；否则报告生成时间会混进这个数字里。
    elapsed_all = time.perf_counter() - t_all

    # ---- 自动生成可视化对照报告 ----
    # 放在 try 里：画图属于附加功能，万一某张图的坐标格式异常，也不能让已经
    # 落盘的 JSON / TXT 白跑。函数内 import 是懒加载（第1周 weekend_pipeline 用过）。
    if MAKE_VIS:
        try:
            from vis_ocr_result import build_report
            report = build_report(
                records,
                image_dir=src_dir,                                  # 原图要和跑 OCR 时同一个目录
                vis_dir=VIS_DIR,
                manifest_path=os.path.join(src_dir, MANIFEST_NAME),
                result_json=OUT_JSON or '',
            )
            print(f'>> 可视化对照报告（用浏览器打开）：{report}')
        except Exception as e:
            print(f'>> 可视化生成失败（识别结果不受影响）：{e}')

    print(f'>> 全部完成，总耗时 {elapsed_all:.2f}s（含模型加载）')
    print('>> 下一步：打开 output/vis/index.html，把有问题的图按类型放进 bad_cases/ 子目录，')
    print('           并在 bad_cases/notes.md 记一行「现象 + 我的猜测」。')


# 主程序守卫：直接运行才执行 main()；被别的文件 import 时不会自动跑。
if __name__ == '__main__':
    main()
