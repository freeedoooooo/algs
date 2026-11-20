"""
store/content.py — 内容 repo（DB-only，design-c1-storage.md）。

extract.json 经 artifact 接缝（BLOB，run_file_id 键）；records 经 content_db
三表（run_id 键）；run 信封由 catalog 表投影（run.json 已退役）。
DB 必选：错误上抛，由调用方显式失败/503。
"""
from .. import config
from . import artifact
from . import catalog
from . import content_db


def get_extract(run_file_id):
    return artifact.get_json(run_file_id, config.EXTRACT_JSON)


def save_extract(run_file_id, doc):
    artifact.save_json(run_file_id, config.EXTRACT_JSON, doc)


def get_records(run_id):
    return content_db.get_records(run_id)


def save_records(doc):
    content_db.save_records(doc)


def get_run(run_id):
    return catalog.get_run(run_id)


def patch_record(run_id, file_index, index, values):
    """校验改值（P1 校验台用）：values 差量合并，original 永不覆盖，
    review.state=edited。返回 (ok, record_or_error)。"""
    return content_db.patch_record(run_id, file_index, index, values)