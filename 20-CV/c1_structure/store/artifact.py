"""
store/artifact.py — 产物附件接缝（，DB-only）。

字节事实源＝c1_parse_artifact BLOB（MySQL 驱动在 artifact_db.py，
将来换 MinIO/对象存储只换驱动实现，本接缝 API 不变）。
键＝task_file_id；name＝task_file 内相对路径（正斜杠）。
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


def save(task_file_id, name, data, mime=None, kind=None):
    return artifact_db.save(task_file_id, name, data,
                            mime or mime_of(name), kind or kind_of(name))


def save_json(task_file_id, name, doc):
    return save(task_file_id, name,
                json.dumps(doc, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8'),
                'application/json', 'json')


def get(task_file_id, name):
    return artifact_db.get(task_file_id, name)


def get_json(task_file_id, name):
    a = get(task_file_id, name)
    return json.loads(a['data'].decode('utf-8')) if a else None


def exists(task_file_id, name):
    return artifact_db.exists(task_file_id, name)


def list(task_file_id):
    return artifact_db.list(task_file_id)


def delete_all(task_file_id):
    """清空该文件全部产物（原地重解析前置；重跑按 name 覆盖，先清防孤儿）。"""
    return artifact_db.delete_all(task_file_id)


def delete_all(task_file_id):
    """清空该文件全部产物（原地重解析前置；重跑按 name 覆盖，先清防孤儿）。"""
    return artifact_db.delete_all(task_file_id)