"""
第2周 · 模块A：批量跑真实图片（可直接运行）

用法：
    把收集的图片放进 test_images/ 目录，然后：
    python batch_ocr.py

目标：故意覆盖多种场景（清晰/模糊/倾斜/反光/密集小字），
      建立"什么场景效果好、什么效果差"的直觉。
"""
import os
from paddleocr import PaddleOCR

ocr = PaddleOCR(use_angle_cls=True, lang='ch')

SRC_DIR = "test_images"
for name in sorted(os.listdir(SRC_DIR)):
    if not name.lower().endswith(('.png', '.jpg', '.jpeg')):
        continue
    path = os.path.join(SRC_DIR, name)
    result = ocr.ocr(path, cls=True)
    texts = [line[1][0] for line in (result[0] or [])]   # 取出所有识别文字
    print(f'\n=== {name} ===')
    print("\n".join(texts) if texts else "（什么都没识别到 → 可能是漏检，存进 bad_cases/06_漏检）")
