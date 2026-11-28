"""store/artifact_db.py — 当前解析产物 repo（MySQL BLOB）。

产物按 doc_id + name 覆盖；不保留解析运行历史，也不保存 sha256。
同一文档重解析直接覆盖 parse.json 等当前产物。
"""
import hashlib

from . import db


def save(doc_id, name, data, mime, kind):
    sha = hashlib.sha256(data).hexdigest()
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_parse_artifact (doc_id, name, kind, mime,'
                ' size_bytes, content) VALUES (%s,%s,%s,%s,%s,%s)'
                ' ON DUPLICATE KEY UPDATE kind=VALUES(kind), mime=VALUES(mime),'
                ' size_bytes=VALUES(size_bytes), content=VALUES(content)',
                (doc_id, name, kind, mime, len(data), data))
        conn.commit()
        return sha
    finally:
        conn.close()


def get(doc_id, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT kind, mime, size_bytes, content'
                        ' FROM c1_parse_artifact WHERE doc_id=%s AND name=%s',
                        (doc_id, name))
            row = cur.fetchone()
        if not row:
            return None
        return {'kind': row[0], 'mime': row[1], 'size': row[2], 'data': row[3],
                'sha': hashlib.sha256(row[3]).hexdigest()}
    finally:
        conn.close()


def exists(doc_id, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM c1_parse_artifact'
                        ' WHERE doc_id=%s AND name=%s', (doc_id, name))
            return cur.fetchone() is not None
    finally:
        conn.close()


def list(doc_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, mime, size_bytes, content'
                        ' FROM c1_parse_artifact WHERE doc_id=%s ORDER BY name',
                        (doc_id,))
            return [{'name': row[0], 'kind': row[1], 'mime': row[2],
                     'size': row[3],
                     'sha': hashlib.sha256(row[4]).hexdigest()}
                    for row in cur.fetchall()]
    finally:
        conn.close()


def delete_all(doc_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute('DELETE FROM c1_parse_artifact WHERE doc_id=%s',
                            (doc_id,))
            conn.commit()
            return n
    finally:
        conn.close()


def latest_doc_with(name):
    """最新一份包含指定产物的 doc_id。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT doc_id FROM c1_parse_artifact'
                        ' WHERE name=%s ORDER BY id DESC LIMIT 1', (name,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


# artifact.py 门面尚未改名前保留别名；新调用方使用 latest_doc_with。
latest_file_with = latest_doc_with
