"""
第2周 · 模块C：感受 PaddleOCR 参数对结果的影响（可直接运行）

目的：本周只需"感受旋钮存在"——调阈值能改变漏检/误检。真正会调是 P4。

用法：
    把一张漏检的图放到 bad_cases/06_漏检/，改下面的 IMG 路径，运行对比。
"""
from paddleocr import PaddleOCR

IMG = 'bad_cases/06_漏检/xxx.png'   # 换成你的漏检样本

# A) 默认参数
ocr_default = PaddleOCR(use_angle_cls=True, lang='ch')
res_a = ocr_default.ocr(IMG, cls=True)

# B) 调低检测阈值 → 更"敏感"，可能救回漏检（也可能带来误检）
ocr_sensitive = PaddleOCR(use_angle_cls=True, lang='ch',
                          det_db_thresh=0.2,        # 默认约 0.3
                          det_db_box_thresh=0.5)
res_b = ocr_sensitive.ocr(IMG, cls=True)


def count(res):
    return len(res[0] or [])

print(f'默认参数识别到 {count(res_a)} 行')
print(f'调低阈值识别到 {count(res_b)} 行')
print('\n观察：调低阈值后是救回了漏检，还是多了误检？记进 notes.md')

# 参数名/默认值可能随版本变化，以官方文档为准：
# https://github.com/PaddlePaddle/PaddleOCR
