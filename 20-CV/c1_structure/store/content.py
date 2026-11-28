"""内容 repo：解析产物经 artifact 接缝读取，抽取记录由 content_db 管理。"""
from .. import config
from . import artifact


def get_extract(doc_id):
    return artifact.get_json(doc_id, config.PARSE_JSON)


def save_extract(doc_id, doc):
    artifact.save_json(doc_id, config.PARSE_JSON, doc)
