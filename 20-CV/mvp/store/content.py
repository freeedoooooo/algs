"""
store/content.py — 内容 repo（保存方式接缝，当前 = 文件实现）。

extract.json / records.json / run.json 的读写全部经过这里：
将来换 DB / 对象存储只换本文件实现，API 与页面不动。
写入一律原子（tmp + os.replace）；--workers 1 单写者，无并发竞争。
路径只存相对（正斜杠），经 config.to_abs 唯一换算。
"""
import os
import json
import time

from .. import config


def _path(case_rel, name):
    return config.to_abs('output/{}/{}'.format(case_rel, name))


def atomic_write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, path)


def _read(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_extract(case_rel):
    return _read(_path(case_rel, config.EXTRACT_JSON))


def save_extract(case_rel, doc):
    atomic_write_json(_path(case_rel, config.EXTRACT_JSON), doc)


def get_records(case_rel):
    return _read(_path(case_rel, config.RECORDS_JSON))


def save_records(case_rel, doc):
    atomic_write_json(_path(case_rel, config.RECORDS_JSON), doc)


def get_run(case_rel):
    return _read(_path(case_rel, config.RUN_JSON))


def save_run(case_rel, doc):
    atomic_write_json(_path(case_rel, config.RUN_JSON), doc)


def patch_record(case_rel, file_index, index, values):
    """校验改值（P1 校验台用）：values 差量合并，original 永不覆盖，
    review.state=edited；整文件原子重写。返回 (ok, record_or_error)。"""
    doc = get_records(case_rel)
    if not doc:
        return False, 'records.json 不存在'
    files = doc.get('files') or []
    if file_index >= len(files):
        return False, '文件下标越界'
    recs = files[file_index].get('records') or []
    rec = next((r for r in recs if r.get('index') == index), None)
    if rec is None:
        return False, '记录下标越界'
    rec['values'].update(values)
    rec['review'] = {'state': 'edited',
                     'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    save_records(case_rel, doc)
    return True, rec