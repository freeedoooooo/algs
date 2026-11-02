"""
第1周 · 模块B：PaddleOCR 识别一张图片（可直接运行）

用法（在 week-01 目录下）：
    python b_ocr_image.py                      # 默认 input/test2.jpg
    python b_ocr_image.py input/test1.jpg      # 也可指定任意图片

说明：
    OCR = 文字检测（找文字在哪）+ 文字识别（读出来）。
    本周当黑盒 API 用即可，原理留到 P4。

版本说明（paddleocr 3.x）：
    - 3.x 把 .ocr(cls=True) 改成了 .predict()，返回 dict 结构（rec_texts / rec_scores）。
    - 默认模型是 PP-OCRv6（需联网下载）。这里显式指定你本地已缓存的 v5，免下载。
      想用默认 v6 就把两个 model_name 参数删掉。
    - use_angle_cls 已废弃，用 use_textline_orientation 代替。

关于"一张图很慢"：
    单张耗时 = 模型加载（仅进程内第一次） + 推理。
    第一次加载模型要好几秒（含 oneDNN 预热），之后同进程每张图只剩推理。
    想更快：① 换移动端模型 PP-OCRv4_mobile_det / PP-OCRv4_mobile_rec（小、快）；
           ② det 侧减小 text_det_limit_side_len；③ paddle.set_num_threads(物理核数)。
"""

import os
import sys
import time

from paddleocr import PaddleOCR

# ---- 模型选择（重要）----
# 没 GPU 时，server 大模型在 CPU 上极慢（实测 test2.jpg：server 推理 104s，mobile 仅 3.8s）。
# 所以默认用移动端模型；追求最高精度且能忍慢，再换回 server 版：
#   DET_MODEL = 'PP-OCRv5_server_det'; REC_MODEL = 'PP-OCRv5_server_rec'
DET_MODEL = 'PP-OCRv4_mobile_det'
REC_MODEL = 'PP-OCRv4_mobile_rec'

# 命令行可选传图片路径
IMAGE = sys.argv[1] if len(sys.argv) > 1 else os.path.join('input', 'test2.jpg')

if not os.path.exists(IMAGE):
    sys.exit(f'找不到图片：{os.path.abspath(IMAGE)}\n请把测试图片放到 week-01/input/test2.jpg')

# ---------- 1) 初始化（加载模型） ----------
print(f'>> 初始化 PaddleOCR（det={DET_MODEL}, rec={REC_MODEL}），首次加载稍慢…')
t0 = time.perf_counter()
ocr = PaddleOCR(
    text_detection_model_name=DET_MODEL,
    text_recognition_model_name=REC_MODEL,
    use_textline_orientation=True,   # 替代已废弃的 use_angle_cls
    lang='ch',                       # 中英混合
)
t1 = time.perf_counter()
print(f'>> 模型加载耗时：{t1 - t0:.2f}s')

# ---------- 2) 推理（真正识别） ----------
print(f'>> 开始识别：{IMAGE}')
results = ocr.predict(IMAGE)         # 3.x 用 predict，返回 list[OCRResult]（dict 结构）
t2 = time.perf_counter()
print(f'>> 推理耗时：{t2 - t1:.2f}s')

# ---------- 3) 打印结果 ----------
# results 里每张图一个 OCRResult；单张图就是 results[0]
total = 0
for res in results:
    texts = res['rec_texts']         # list[str]  识别出的每一行文字
    scores = res['rec_scores']       # list[float] 对应置信度
    # 每行文字的 4 点坐标；不同模型字段名略有差异，做个兜底
    boxes = res.get('rec_polys') or res.get('dt_polys') or [None] * len(texts)
    for text, conf, box in zip(texts, scores, boxes):
        total += 1
        print(f'{text}  置信度={conf:.2f}')

print(f'>> 共识别 {total} 行文字')
print(f'>> 总耗时：{t2 - t0:.2f}s（模型加载 {t1 - t0:.2f}s + 推理 {t2 - t1:.2f}s）')
print('>> 提示：模型加载只在进程内第一次发生；同进程连跑多张图，后续每张只剩推理时间。')
