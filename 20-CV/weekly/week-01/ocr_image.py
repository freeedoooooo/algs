"""
第1周 · 模块B：PaddleOCR 识别一张图片（可直接运行）

用法：
    把一张含中文的图片命名为 test.png 放到本目录，然后：
    python ocr_image.py

说明：
    OCR = 文字检测（找文字在哪）+ 文字识别（读出来）。
    本周当黑盒 API 用即可，原理留到 P4。
"""
from paddleocr import PaddleOCR

# lang='ch' 中英混合；use_angle_cls=True 自动摆正倾斜文字
ocr = PaddleOCR(use_angle_cls=True, lang='ch')

IMAGE = 'test.png'  # 换成你的图片路径
result = ocr.ocr(IMAGE, cls=True)

# ⚠️ 版本提示：PaddleOCR 3.x 把 .ocr() 改成了 .predict()，返回结构略不同。
#    若下面报错，去官方 README 看当前版本用法：
#    https://github.com/PaddlePaddle/PaddleOCR
for line in result[0]:
    box, (text, conf) = line          # box=四点坐标, text=识别文字, conf=置信度
    print(f'{text}  置信度={conf:.2f}')
