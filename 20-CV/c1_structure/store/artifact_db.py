"""
store/artifact_db.py — 产物附件 repo（MySQL BLOB）。

SQL 收敛本文件；只经 db.connect 拿 DB-API 连接。DB 必选：错误上抛不降级。
键＝file_id（资料记录，一次运行）；name＝资料内相对路径（正斜杠）。
无外键约束：资料删除前须应用层先清附件。
"""
import hashlib

from . import db


def save(file_id, name, data, mime, kind):
    sha = hashlib.sha256(data).hexdigest()
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_parse_artifact (file_id, name, kind, mime,'
                ' size_bytes, sha256, content) VALUES (%s,%s,%s,%s,%s,%s,%s)'
                ' ON DUPLICATE KEY UPDATE kind=VALUES(kind), mime=VALUES(mime),'
                ' size_bytes=VALUES(size_bytes), sha256=VALUES(sha256),'
                ' content=VALUES(content)',
                (file_id, name, kind, mime, len(data), sha, data))
        conn.commit()
        return sha
    finally:
        conn.close()


def get(file_id, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT kind, mime, size_bytes, sha256, content'
                ' FROM c1_parse_artifact WHERE file_id=%s AND name=%s',
                (file_id, name))
            row = cur.fetchone()
        if not row:
            return None
        return {'kind': row[0], 'mime': row[1], 'size': row[2],
                'sha': row[3], 'data': row[4]}
    finally:
        conn.close()


def exists(file_id, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM c1_parse_artifact'
                        ' WHERE file_id=%s AND name=%s',
                        (file_id, name))
            return cur.fetchone() is not None
    finally:
        conn.close()


def list(file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, mime, size_bytes, sha256'
                        ' FROM c1_parse_artifact WHERE file_id=%s'
                        ' ORDER BY name', (file_id,))
            return [{'name': r[0], 'kind': r[1], 'mime': r[2],
                     'size': r[3], 'sha': r[4]} for r in cur.fetchall()]
    finally:
        conn.close()


def delete_all(file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute('DELETE FROM c1_parse_artifact'
                            ' WHERE file_id=%s', (file_id,))
            conn.commit()
        return n
    finally:
        conn.close()


def latest_file_with(name):
    """最新一份含指定产物的 file_id（/parse-report 重定向用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT file_id FROM c1_parse_artifact'
                        ' WHERE name=%s ORDER BY id DESC LIMIT 1', (name,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()
