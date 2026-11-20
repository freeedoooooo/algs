"""
store/artifact.py — 产物附件接缝（design-artifacts-db.md）。

file=持久磁盘（现状，原子写）；db=extract_artifact BLOB（DB 必选，错误上抛）。
case_rel='<case目录名>' 或 'sources'；name=case 内相对路径（正斜杠）。
kind/mime 由 name 推断；raw/ 前缀 kind=raw（服务路由 403）。
"""
import os
import json
import hashlib

from .. import config

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


def _db():
    from . import artifact_db
    return artifact_db


def _fpath(case_rel, name):
    base = (config.SOURCES_DIR if case_rel == 'sources'
            else os.path.join(config.OUTPUT_DIR, case_rel))
    return os.path.join(base, name.replace('/', os.sep))


def save(case_rel, name, data, mime=None, kind=None):
    mime = mime or mime_of(name)
    kind = kind or kind_of(name)
    if config.ARTIFACT_STORE == 'db':
        return _db().save(case_rel, name, data, mime, kind)
    path = _fpath(case_rel, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)
    return hashlib.sha256(data).hexdigest()


def save_json(case_rel, name, doc):
    return save(case_rel, name,
                json.dumps(doc, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8'),
                'application/json', 'json')


def get(case_rel, name):
    if config.ARTIFACT_STORE == 'db':
        return _db().get(case_rel, name)
    path = _fpath(case_rel, name)
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        data = f.read()
    return {'kind': kind_of(name), 'mime': mime_of(name), 'size': len(data),
            'sha': hashlib.sha256(data).hexdigest(), 'data': data}


def get_json(case_rel, name):
    a = get(case_rel, name)
    return json.loads(a['data'].decode('utf-8')) if a else None


def exists(case_rel, name):
    if config.ARTIFACT_STORE == 'db':
        return _db().exists(case_rel, name)
    return os.path.isfile(_fpath(case_rel, name))


def list(case_rel):
    if config.ARTIFACT_STORE == 'db':
        return _db().list(case_rel)
    base = (config.SOURCES_DIR if case_rel == 'sources'
            else os.path.join(config.OUTPUT_DIR, case_rel))
    out = []
    for root, _, files in os.walk(base):
        for fn in files:
            if fn.endswith('.tmp'):
                continue
            rel = os.path.relpath(os.path.join(root, fn), base)
            rel = rel.replace(os.sep, '/')
            out.append({'name': rel, 'kind': kind_of(rel),
                        'mime': mime_of(rel)})
    return sorted(out, key=lambda x: x['name'])


def cases():
    if config.ARTIFACT_STORE == 'db':
        return [c for c in _db().cases() if c != 'sources']
    if not os.path.isdir(config.OUTPUT_DIR):
        return []
    return sorted(d for d in os.listdir(config.OUTPUT_DIR)
                  if os.path.isdir(os.path.join(config.OUTPUT_DIR, d)))


def delete(case_rel, name):
    if config.ARTIFACT_STORE == 'db':
        return _db().delete(case_rel, name)
    path = _fpath(case_rel, name)
    if os.path.isfile(path):
        os.remove(path)


def delete_case(case_rel):
    if config.ARTIFACT_STORE == 'db':
        return _db().delete_case(case_rel)
    import shutil
    shutil.rmtree(_fpath(case_rel, ''), ignore_errors=True)