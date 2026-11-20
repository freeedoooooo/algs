"""
store/artifact_db.py — 产物附件 repo（MySQL BLOB，design-c1-storage.md）。

SQL 收敛本文件；只经 db.connect 拿 DB-API 连接。DB 必选：错误上抛不降级。
键＝run_file_id（某次运行里的某个文件）；name＝run_file 内相对路径（正斜杠）。
run_file 删除时附件随 FK 级联删，无需手工清理。
"""
import hashlib

from . import db


def save(run_file_id, name, data, mime, kind):
    sha = hashlib.sha256(data).hexdigest()
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_artifact (run_file_id, name, kind, mime,'
                ' size_bytes, sha256, content) VALUES (%s,%s,%s,%s,%s,%s,%s)'
                ' ON DUPLICATE KEY UPDATE kind=VALUES(kind), mime=VALUES(mime),'
                ' size_bytes=VALUES(size_bytes), sha256=VALUES(sha256),'
                ' content=VALUES(content)',
                (run_file_id, name, kind, mime, len(data), sha, data))
        conn.commit()
        return sha
    finally:
        conn.close()


def get(run_file_id, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT kind, mime, size_bytes, sha256, content'
                ' FROM extract_artifact WHERE run_file_id=%s AND name=%s',
                (run_file_id, name))
            row = cur.fetchone()
        if not row:
            return None
        return {'kind': row[0], 'mime': row[1], 'size': row[2],
                'sha': row[3], 'data': row[4]}
    finally:
        conn.close()


def exists(run_file_id, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM extract_artifact'
                        ' WHERE run_file_id=%s AND name=%s',
                        (run_file_id, name))
            return cur.fetchone() is not None
    finally:
        conn.close()


def list(run_file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, mime, size_bytes, sha256'
                        ' FROM extract_artifact WHERE run_file_id=%s'
                        ' ORDER BY name', (run_file_id,))
            return [{'name': r[0], 'kind': r[1], 'mime': r[2],
                     'size': r[3], 'sha': r[4]} for r in cur.fetchall()]
    finally:
        conn.close()


def latest_run_file_with(name):
    """最新一份含指定产物的 run_file_id（/extract-report 重定向用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT run_file_id FROM extract_artifact'
                        ' WHERE name=%s ORDER BY id DESC LIMIT 1', (name,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()