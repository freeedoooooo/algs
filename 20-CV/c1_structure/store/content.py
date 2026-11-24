"""
store/content.py — 内容 repo（DB-only）。

parse.json 经 artifact 接缝（BLOB，file_id 键）；records 经 content_db
三表（file_id 键）；资料信封由 catalog.get_file 取。DB 必选：错误上抛。
"""
from .. import config
from . import artifact
from . import catalog
from . import content_db


def get_extract(file_id):
    return artifact.get_json(file_id, config.PARSE_JSON)


def save_extract(file_id, doc):
    artifact.save_json(file_id, config.PARSE_JSON, doc)


def get_records(file_id):
    return content_db.get_records(file_id)


def save_records(doc):
    content_db.save_records(doc)


def record_id_map(file_id):
    """(file_id, record_index) → staging_record.id；入库写溯源列用。"""
    return content_db.record_id_map(file_id)


def locate_record(record_id):
    """按 record_id 反查 file_id；数据看板血缘跳转用。"""
    return content_db.locate_record(record_id)


def get_file(file_id):
    return catalog.get_file(file_id)


def patch_record(file_id, index, values):
    """校验改值：values 差量合并，original 永不覆盖，
    review.state=edited；返回更新后的记录。业务错误抛 StoreError。"""
    return content_db.patch_record(file_id, index, values)


def set_review(file_id, indexes, state):
    """批量确认/拒绝：返回更新条数。业务错误抛 StoreError。"""
    return content_db.set_review(file_id, indexes, state)
