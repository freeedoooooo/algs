"""
第1周 · 模块B：PaddleOCR 识别一张图片（可直接运行）

用法：
    把一张含中文的图片命名为 test1.jpg 放到 input/ 目录，然后（在 week-01 目录下）：
    python b_ocr_image.py

说明：
    OCR = 文字检测（找文字在哪）+ 文字识别（读出来）。
    本周当黑盒 API 用即可，原理留到 P4。

版本说明（paddleocr 3.x）：
    - 3.x 把 .ocr(cls=True) 改成了 .predict()，返回结构也变了（dict 形式）。
      本脚本已按 3.x 写好。
    - 模型默认会用最新的 PP-OCRv6，需要联网下载。为了离线/秒开，
      这里显式指定你本地已缓存的 PP-OCRv5 模型；想用默认 v6 就把下面
      两个 model_name 参数删掉。
    - use_angle_cls 已废弃，用 use_textline_orientation 代替。
"""

import os
import sys

from paddleocr import PaddleOCR

# ---- 本地已缓存的模型（免下载）；想用更快的移动端可换成 PP-OCRv4_mobile_det/rec ----
DET_MODEL = 'PP-OCRv5_server_det'
REC_MODEL = 'PP-OCRv5_server_rec'

# 命令行可选传图片路径：python b_ocr_image.py input/test2.jpg
IMAGE = sys.argv[1] if len(sys.argv) > 1 else os.path.join('input', 'test1.jpg')

if not os.path.exists(IMAGE):
    sys.exit(f'找不到图片：{os.path.abspath(IMAGE)}\n请把测试图片放到 week-01/input/test1.jpg')

print(f'>> 初始化 PaddleOCR（det={DET_MODEL}, rec={REC_MODEL}），首次加载稍慢…')
ocr = PaddleOCR(
    text_detection_model_name=DET_MODEL,
    text_recognition_model_name=REC_MODEL,
    use_textline_orientation=True,   # 替代已废弃的 use_angle_cls，自动摆正倾斜文字
    lang='ch',                       # 中英混合
)

print(f'>> 开始识别：{IMAGE}')
results = ocr.predict(IMAGE)         # 3.x 用 predict，返回 list[OCRResult]（dict 结构）

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
