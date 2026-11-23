"""
pipeline/engines.py — 模型单例（懒加载）。

上传页不需要模型，只有真正处理文件时才加载；同一进程内复用，
避免每个文件都重建十来个模型（首次约 20~40s，之后每张图几秒）。

表格模型按 use_unwarp 分两个槽位缓存 —— 文档矫正是「引擎构造级」参数，
每次构造都要重新载入十来个子模型；按开关缓存后，两种配置各建一次，
之后同配置的文件直接复用，不会因为用户切了 doc_unwarp 就反复重建。
"""
from .. import config

_OCR = None
_STRUCT = {}          # key: use_unwarp(bool) -> PPStructureV3 实例


def ocr():
    global _OCR
    if _OCR is None:
        from paddleocr import PaddleOCR
        _OCR = PaddleOCR(
            text_detection_model_name=config.DET_MODEL,
            text_recognition_model_name=config.REC_MODEL,
            use_textline_orientation=True,
            # 关闭整页预处理，rec_polys 才是原图像素坐标，框才套得准
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
    return _OCR


def structure(use_unwarp=True):
    """
    use_unwarp=True （默认）：方向分类 + UVDoc 去扭曲，适合旋转/弯曲扫描件。
        代价：cell_box_list 基于矫正图，需另存 rectified.png 才能 1:1 叠框。
    use_unwarp=False：关闭文档预处理，适合电子版平整截图（108 这类）。
        实测矫正图与原图逐像素一致（identity），坐标直接就是原图坐标，
        单元格框叠在 source.<ext> 上即可，无形变误差、无需原图/矫正图切换。
    """
    key = bool(use_unwarp)
    if key not in _STRUCT:
        from paddleocr import PPStructureV3
        _STRUCT[key] = PPStructureV3(
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_region_detection=False,
            use_table_recognition=True,
            text_detection_model_name=config.DET_MODEL,
            text_recognition_model_name=config.REC_MODEL,
            use_doc_orientation_classify=key,
            use_doc_unwarping=key,
        )
    return _STRUCT[key]
