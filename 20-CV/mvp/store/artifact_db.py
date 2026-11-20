"""
store/artifact_db.py — 产物附件 repo（MySQL BLOB，design-artifacts-db.md）。

SQL 收敛本文件；只经 db.connect 拿 DB-API 连接。DB 必选：错误上抛不降级。
case_rel='<case目录名>' 或 'sources'；name=case 内相对路径（正斜杠）。
"""
import hashlib

from . import db


def save(case_rel, name, data, mime, kind):
    sha = hashlib.sha256(data).hexdigest()
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_artifact (case_rel, name, kind, mime,'
                ' size_bytes, sha256, content) VALUES (%s,%s,%s,%s,%s,%s,%s)'
                ' ON DUPLICATE KEY UPDATE kind=VALUES(kind), mime=VALUES(mime),'
                ' size_bytes=VALUES(size_bytes), sha256=VALUES(sha256),'
                ' content=VALUES(content)',
                (case_rel, name, kind, mime, len(data), sha, data))
        conn.commit()
        return sha
    finally:
        conn.close()


def get(case_rel, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT kind, mime, size_bytes, sha256, content'
                ' FROM extract_artifact WHERE case_rel=%s AND name=%s',
                (case_rel, name))
            row = cur.fetchone()
        if not row:
            return None
        return {'kind': row[0], 'mime': row[1], 'size': row[2],
                'sha': row[3], 'data': row[4]}
    finally:
        conn.close()


def exists(case_rel, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM extract_artifact'
                        ' WHERE case_rel=%s AND name=%s', (case_rel, name))
            return cur.fetchone() is not None
    finally:
        conn.close()


def list(case_rel):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, mime, size_bytes, sha256'
                        ' FROM extract_artifact WHERE case_rel=%s'
                        ' ORDER BY name', (case_rel,))
            return [{'name': r[0], 'kind': r[1], 'mime': r[2],
                     'size': r[3], 'sha': r[4]} for r in cur.fetchall()]
    finally:
        conn.close()


def cases():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT DISTINCT case_rel FROM extract_artifact'
                        ' ORDER BY case_rel')
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def delete(case_rel, name):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM extract_artifact'
                        ' WHERE case_rel=%s AND name=%s', (case_rel, name))
        conn.commit()
    finally:
        conn.close()


def delete_case(case_rel):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM extract_artifact WHERE case_rel=%s',
                        (case_rel,))
        conn.commit()
    finally:
        conn.close()