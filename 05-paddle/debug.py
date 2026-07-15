import os
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR
import inspect

sig = inspect.signature(PaddleOCR.__init__)
print("=" * 50)
print("当前 PaddleOCR 版本支持的 __init__ 参数：")
print("=" * 50)
for name, param in sig.parameters.items():
    if name != 'self':
        default = param.default if param.default is not inspect.Parameter.empty else "(必填)"
        print(f"  {name:30s} = {default}")
print("=" * 50)

# 同时打印版本号
import paddleocr
print(f"PaddleOCR 版本: {paddleocr.__version__}")