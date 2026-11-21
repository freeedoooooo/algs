"""目录库 · 源文件域（extract_file ＋ content 原件字节）。

哈希去重登记；content LONGBLOB 只在 get_file_content 里取，
列表/元数据查询一律排除该列，避免把字节拖进列表接口。
"""
from .. import db
from ..errors import Conflict
from ._common import _rows

_FILE_COLS = ('id, name, sha256, kind, size_bytes, tags, note, created_at')


def register_file(name, kind, size_bytes, sha256, content):
    """哈希去重登记：已存在回已有 id（dedup=True），字节不重复入库。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_file WHERE sha256=%s',
                        (sha256,))
            row = cur.fetchone()
            if row:
                return row[0], True
            cur.execute(
                'INSERT INTO extract_file (name, sha256, kind,'
                ' size_bytes, content) VALUES (%s,%s,%s,%s,%s)',
                (name, sha256, kind, size_bytes, content))
            conn.commit()
            return cur.lastrowid, False
    finally:
        conn.close()


def list_files(q=None, kind=None, tag=None, page=1, per_page=20):
    conn = db.connect()
    try:
        where, args = [], []
        if q:
            where.append('name LIKE %s')
            args.append('%{}%'.format(q))
        if kind:
            where.append('kind=%s')
            args.append(kind)
        if tag:
            where.append('tags LIKE %s')
            args.append('%{}%'.format(tag))
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM extract_file ' + w, args)
            total = cur.fetchone()[0]
            cur.execute(
                'SELECT {} FROM extract_file {} ORDER BY id DESC'
                ' LIMIT %s OFFSET %s'.format(_FILE_COLS, w),
                args + [per_page, (max(1, page) - 1) * per_page])
            items = _rows(cur)
        for it in items:
            it['created_at'] = str(it['created_at'])
        return {'items': items, 'total': total}
    finally:
        conn.close()


def get_file(file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT {} FROM extract_file WHERE id=%s'
                        .format(_FILE_COLS), (file_id,))
            rows = _rows(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def get_file_content(file_id):
    """原件字节 + 路由所需元数据（/srcfiles/{id} 用）；不存在回 None。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, sha256, content'
                        ' FROM extract_file WHERE id=%s', (file_id,))
            row = cur.fetchone()
        if not row:
            return None
        return {'name': row[0], 'kind': row[1], 'sha': row[2], 'data': row[3]}
    finally:
        conn.close()


def delete_file(file_id):
    """被任务引用禁删（血缘完整）抛 Conflict；字节随行删除。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM extract_task_file'
                        ' WHERE file_id=%s', (file_id,))
            if cur.fetchone()[0]:
                raise Conflict('该文件已被任务引用，禁止删除（血缘完整）')
            cur.execute('DELETE FROM extract_file WHERE id=%s', (file_id,))
            conn.commit()
    finally:
        conn.close()


def update_file_meta(file_id, tags=None, note=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_file SET tags=%s, note=%s'
                        ' WHERE id=%s', (tags, note, file_id))
            conn.commit()
    finally:
        conn.close()