"""
第2周 · 模块C：感受 PaddleOCR 参数对结果的影响（PaddleOCR 3.7.0 版）

【做什么】
对同一张「有漏检」的图片跑两次：一次用默认阈值，一次调低检测阈值，
然后对比「多认出了哪些行、又丢了哪些行」，判断是救回漏检还是引入误检。

环境（本机 miniforge，环境名就是 paddle）：
    conda activate paddle

用法（在 week-02 目录下）：
    python c_try_params.py                                       # 用配置区 IMG
    python c_try_params.py input/real_terminal_screenshot.jpg    # 命令行临时指定图片

【3.x 的关键变化】
    参数名：det_db_thresh / det_db_box_thresh  →  text_det_thresh / text_det_box_thresh
    默认值：0.3 / 0.6（旧教程写的 0.5 已不是默认值）
    位置  ：3.x 支持在 predict() 调用时「按次覆盖」参数，
            所以只需创建 1 个引擎、加载 1 次模型，就能对比两组参数。
            2.x 写法要 new 两个 PaddleOCR，白白多加载一次模型。

【本周目标】
只需感受「调这个旋钮能改变结果」，不要求真的调好。原理在 P4 讲 DBNet 时才深入。
"""

# =========================== 配置区：调试只改这里 ===========================
IMG = 'input/real_terminal_screenshot.jpg'   # 真实终端截图（亮字暗底，有漏检），第1周原件
OUT_TXT = 'output/param_compare.txt'     # 对比结果存哪里；改成 None 就不写
DET_MODEL = 'PP-OCRv4_mobile_det'        # 检测模型（第1周已缓存，免下载）
REC_MODEL = 'PP-OCRv4_mobile_rec'        # 识别模型

# A 组不传参数 = 用 3.x 默认值（text_det_thresh=0.3, text_det_box_thresh=0.6）
# B 组把两个阈值都调低 = 更「敏感」，可能救回漏检，也可能带来误检。
SENSITIVE_DET_THRESH = 0.2
SENSITIVE_BOX_THRESH = 0.4
# ==========================================================================

import os       # 检查文件、建目录
import sys      # 读命令行参数
import time     # 计时

# 必须在 import paddleocr 之前设置（详见第1周 d_table_ocr.py 的说明）
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE', 'BOS')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK', 'True')

from paddleocr import PaddleOCR  # noqa: E402


def collect(results):
    """从 predict() 的返回值里取出所有文字与置信度，合成两个列表。"""
    texts, scores = [], []
    for res in results:
        texts.extend(res['rec_texts'])                      # list[str]
        scores.extend(float(s) for s in res['rec_scores'])  # list[float]
    return texts, scores


def main():
    # 命令行参数优先于配置区，方便临时换图。
    image = sys.argv[1] if len(sys.argv) > 1 else IMG
    if not os.path.exists(image):
        sys.exit(
            f'找不到图片：{os.path.abspath(image)}\n'
            f'改文件顶部的 IMG，或命令行指定：python c_try_params.py 你的图片.jpg'
        )

    print(f'>> 对比图片：{image}')
    print(f'>> 初始化 PaddleOCR（det={DET_MODEL}, rec={REC_MODEL}），只加载一次模型…')
    t0 = time.perf_counter()
    ocr = PaddleOCR(
        text_detection_model_name=DET_MODEL,
        text_recognition_model_name=REC_MODEL,
        use_textline_orientation=True,   # 替代已废弃的 use_angle_cls
        # 不传 lang：显式指定模型名时 lang 会被忽略并报警告。
        # 与 a_batch_ocr.py 保持一致：关闭文档预处理，避免坐标基于矫正后的图。
        # 本脚本只比文字，不看坐标，但两边参数一致才能横向对比结果。
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )
    print(f'>> 模型加载耗时：{time.perf_counter() - t0:.2f}s')

    # ---- A 组：默认参数 ----
    t_a = time.perf_counter()
    texts_a, scores_a = collect(ocr.predict(image))
    elapsed_a = time.perf_counter() - t_a

    # ---- B 组：调低检测阈值（在 predict 时按次覆盖，不用重建引擎）----
    t_b = time.perf_counter()
    results_b = ocr.predict(
        image,
        text_det_thresh=SENSITIVE_DET_THRESH,
        text_det_box_thresh=SENSITIVE_BOX_THRESH,
    )
    texts_b, scores_b = collect(results_b)
    elapsed_b = time.perf_counter() - t_b

    # ---- 对比 ----
    # 列表推导式：只保留「B 有而 A 没有」的行，反之亦然。
    only_b = [t for t in texts_b if t not in texts_a]
    only_a = [t for t in texts_a if t not in texts_b]
    avg_a = sum(scores_a) / len(scores_a) if scores_a else 0.0
    avg_b = sum(scores_b) / len(scores_b) if scores_b else 0.0

    print(f'\n默认参数   ：{len(texts_a)} 行，平均置信度 {avg_a:.2f}，{elapsed_a:.2f}s')
    print(f'调低阈值   ：{len(texts_b)} 行，平均置信度 {avg_b:.2f}，{elapsed_b:.2f}s')
    print(f'B 新增行   ：{len(only_b)} 行，A 独有行：{len(only_a)} 行')
    if not only_b and not only_a:
        print('提示：两组结果完全一致。常见原因有两类，别急着下结论：')
        print('      ① 这张图本来就没有漏检（例如清晰对照组）；')
        print('      ② 漏检处的文字像素已被破坏（过曝洗白、糊成色块），')
        print('         调低检测阈值也救不回来，因为信息已经不存在了。')
        print('      判断方法：打开 output/vis/index.html，看原图上')
        print('      「有字却没有框」的位置 —— 有，就是第 ② 种。')
        print('      两种情况都不是脚本没生效。')
    print('\nB 组新认出的前 10 行：')
    for t in only_b[:10]:
        print(f'  + {t}')
    print('\nB 组反而丢掉的前 10 行：')
    for t in only_a[:10]:
        print(f'  - {t}')

    # ---- 落盘（方便回头翻，也给 notes.md 留证据）----
    if OUT_TXT:
        os.makedirs(os.path.dirname(OUT_TXT) or '.', exist_ok=True)
        lines = [
            f'图片：{image}',
            f'模型：{DET_MODEL} + {REC_MODEL}',
            f'A 组：默认阈值，{len(texts_a)} 行，平均置信度 {avg_a:.2f}，{elapsed_a:.2f}s',
            f'B 组：text_det_thresh={SENSITIVE_DET_THRESH}, '
            f'text_det_box_thresh={SENSITIVE_BOX_THRESH}，'
            f'{len(texts_b)} 行，平均置信度 {avg_b:.2f}，{elapsed_b:.2f}s',
            '',
            '=== A 组全文 ===',
        ]
        lines.extend(f'{t}\t{s:.2f}' for t, s in zip(texts_a, scores_a))
        lines.extend(['', '=== B 组全文 ==='])
        lines.extend(f'{t}\t{s:.2f}' for t, s in zip(texts_b, scores_b))
        lines.extend(['', '=== B 新增（可能是救回的漏检，也可能是误检）==='])
        lines.extend(only_b)
        lines.extend(['', '=== B 丢掉 ==='])
        lines.extend(only_a)
        with open(OUT_TXT, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f'\n>> 完整对比已保存：{OUT_TXT}')

    print('\n观察：调低阈值后是救回了漏检，还是多了误检？')
    print('      把「调了什么 + 结果怎么变」记进 bad_cases/notes.md。')
    print('      本周只需感受旋钮存在，调得不好是正常的。')


# 主程序守卫：被 import 时不会自动执行。
if __name__ == '__main__':
    main()
