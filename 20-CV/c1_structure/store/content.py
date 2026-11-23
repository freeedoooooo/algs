"""
store/content.py — 内容 repo（DB-only）。

parse.json 经 artifact 接缝（BLOB，task_file_id 键）；records 经 content_db
三表（task_id 键）；task 信封由 catalog 表投影（run.json 已退役）。
DB 必选：错误上抛，由调用方显式失败/503。
"""
from .. import config
from . import artifact
from . import catalog
from . import content_db


def get_extract(task_file_id):
    return artifact.get_json(task_file_id, config.PARSE_JSON)


def save_extract(task_file_id, doc):
    artifact.save_json(task_file_id, config.PARSE_JSON, doc)


def get_records(task_id):
    return content_db.get_records(task_id)


def save_records(doc):
    content_db.save_records(doc)


def get_task(task_id):
    return catalog.get_task(task_id)


def patch_record(task_id, file_index, index, values):
    """校验改值（P1 校验台用）：values 差量合并，original 永不覆盖，
    review.state=edited；返回更新后的记录。业务错误抛 StoreError。"""
    return content_db.patch_record(task_id, file_index, index, values)


def set_review(task_id, file_index, indexes, state):
    """批量确认/拒绝（P1 校验台用）：返回更新条数。业务错误抛 StoreError。"""
    return content_db.set_review(task_id, file_index, indexes, state)