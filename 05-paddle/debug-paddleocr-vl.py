# 验证脚本 test_vl.py
try:
    # 方式一对应的导入
    from paddlex.inference.pipelines import VLMPipeline
    print("✅ PaddleX VLM 管道导入成功")
except ImportError:
    pass

try:
    # 方式二对应的导入
    from paddleocr_vl import PaddleOCRVL
    print("✅ PaddleOCR-VL 独立模块导入成功")
except ImportError:
    pass

# 如果两个都失败，说明安装未成功
print("⚠️ 如果以上均无输出，请检查安装日志")