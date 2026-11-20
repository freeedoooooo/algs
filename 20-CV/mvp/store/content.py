"""
store/content.py — 内容 repo（DB-only，design-artifacts-db.md）。

extract.json / run.json 经 artifact 接缝（BLOB）；records 经 content_db 三表。
DB 必选：错误上抛，由调用方显式失败/503。file 实现已删除（过渡态）。
"""
from .. import config
from . import artifact
from . import content_db


def get_extract(case_rel):
    return artifact.get_json(case_rel, config.EXTRACT_JSON)


def save_extract(case_rel, doc):
    artifact.save_json(case_rel, config.EXTRACT_JSON, doc)


def get_records(case_rel):
    return content_db.get_records(case_rel)


def save_records(case_rel, doc):
    content_db.save_records(case_rel, doc)


def get_run(case_rel):
    return artifact.get_json(case_rel, config.RUN_JSON)


def save_run(case_rel, doc):
    artifact.save_json(case_rel, config.RUN_JSON, doc)


def patch_record(case_rel, file_index, index, values):
    """校验改值（P1 校验台用）：values 差量合并，original 永不覆盖，
    review.state=edited。返回 (ok, record_or_error)。"""
    return content_db.patch_record(case_rel, file_index, index, values)