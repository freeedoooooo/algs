"""
store/artifact.py — 产物附件接缝（design-artifacts-db.md，DB-only）。

字节事实源＝extract_artifact BLOB（MySQL 驱动在 artifact_db.py，
将来换 MinIO/对象存储只换驱动实现，本接缝 API 不变）。
case_rel='<case目录名>' 或 'sources'；name=case 内相对路径（正斜杠）。
kind/mime 由 name 推断；raw/ 前缀 kind=raw（服务路由 403）。
DB 必选：错误上抛，不降级。
"""
import os
import json

from . import artifact_db

_MIME = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
         '.json': 'application/json', '.html': 'text/html',
         '.md': 'text/markdown', '.csv': 'text/csv', '.pdf': 'application/pdf',
         '.txt': 'text/plain'}


def kind_of(name):
    if name.startswith('raw/'):
        return 'raw'
    ext = os.path.splitext(name)[1].lower()
    return {'.json': 'json', '.html': 'html', '.md': 'md', '.csv': 'csv',
            '.png': 'image', '.jpg': 'image', '.jpeg': 'image',
            '.pdf': 'source'}.get(ext, 'bin')


def mime_of(name):
    return _MIME.get(os.path.splitext(name)[1].lower(),
                     'application/octet-stream')


def save(case_rel, name, data, mime=None, kind=None):
    return artifact_db.save(case_rel, name, data,
                            mime or mime_of(name), kind or kind_of(name))


def save_json(case_rel, name, doc):
    return save(case_rel, name,
                json.dumps(doc, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8'),
                'application/json', 'json')


def get(case_rel, name):
    return artifact_db.get(case_rel, name)


def get_json(case_rel, name):
    a = get(case_rel, name)
    return json.loads(a['data'].decode('utf-8')) if a else None


def exists(case_rel, name):
    return artifact_db.exists(case_rel, name)


def list(case_rel):
    return artifact_db.list(case_rel)


def cases():
    return [c for c in artifact_db.cases() if c != 'sources']


def delete(case_rel, name):
    return artifact_db.delete(case_rel, name)


def delete_case(case_rel):
    return artifact_db.delete_case(case_rel)