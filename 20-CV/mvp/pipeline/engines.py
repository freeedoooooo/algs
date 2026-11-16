"""
pipeline/engines.py — 模型单例（懒加载）。

上传页不需要模型，只有真正处理文件时才加载；同一进程内复用，
避免每个文件都重建十来个模型（首次约 20~40s，之后每张图几秒）。
"""
import config

_OCR = None
_STRUCT = None


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


def structure():
    global _STRUCT
    if _STRUCT is None:
        from paddleocr import PPStructureV3
        # 刻意保留 UVDoc 去扭曲：关闭会让表格文字质量下降，
        # 而 cell_box_list 本就基于矫正图，直接 1:1 叠加即可。
        _STRUCT = PPStructureV3(
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_seal_recognition=False,
            use_region_detection=False,
            use_table_recognition=True,
            text_detection_model_name=config.DET_MODEL,
            text_recognition_model_name=config.REC_MODEL,
        )
    return _STRUCT
