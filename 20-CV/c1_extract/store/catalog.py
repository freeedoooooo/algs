"""
store/catalog.py — 目录元数据 repo（MySQL，design-task-schema.md）。
extract_file(+content) / extract_template(+version) / extract_task /
extract_task_file / extract_quarantine。业务表统一 extract_ 前缀。

只经 db.connect 拿 DB-API 连接，SQL 全部收敛在本文件；DB 必选，错误上抛。
JSON 列：写入 json.dumps，读出 json.loads（驱动无关，不依赖 MySQL JSON 函数）。
无外键约束：引用完整性归应用层（delete_file 引用守卫；级联删除见设计稿 §2）。
extract_file.content（原件 LONGBLOB）只在 get_file_content 里取，
列表/元数据查询一律排除该列，避免把字节拖进列表接口。
"""
import json

from . import db

_FILE_COLS = ('id, name, sha256, kind, size_bytes, tags, note, created_at')


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _j(v):
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


# ---- extract_file ----

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
    """被任务引用禁删（血缘完整）；返回 (ok, reason)。字节随行删除。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM extract_task_file'
                        ' WHERE file_id=%s', (file_id,))
            if cur.fetchone()[0]:
                return False, '该文件已被任务引用，禁止删除（血缘完整）'
            cur.execute('DELETE FROM extract_file WHERE id=%s', (file_id,))
            conn.commit()
            return True, None
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


# ---- extract_template / extract_template_version ----

def list_templates():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            # current_version_id：前端下拉直接提交版本 id，不用再查一次
            cur.execute(
                'SELECT t.id, t.name, t.description, t.current_version,'
                ' (SELECT tv.id FROM extract_template_version tv'
                '   WHERE tv.template_id=t.id'
                '     AND tv.version=t.current_version) AS current_version_id'
                ' FROM extract_template t ORDER BY t.id')
            return _rows(cur)
    finally:
        conn.close()


def get_template_version(version_id=None, name=None):
    """按 id 或模板名（取当前版本）拿三段 JSON。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if version_id is not None:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id WHERE tv.id=%s', (version_id,))
            else:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id'
                    ' WHERE t.name=%s AND tv.version=t.current_version',
                    (name or '原始透传',))
            rows = _rows(cur)
        if not rows:
            return None
        r = rows[0]
        for k in ('schema_json', 'mapping_json', 'transform_json'):
            r[k] = _j(r[k])
        return r
    finally:
        conn.close()


# ---- extract_task / extract_task_file ----

def create_task(mode, template_version_id, params):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_task (mode, template_version_id,'
                ' params_json, state) VALUES (%s,%s,%s,%s)',
                (mode, template_version_id,
                 json.dumps(params or {}, ensure_ascii=False), 'pending'))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_task_state(task_id, state, error=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_task SET state=%s, error=%s WHERE id=%s',
                        (state, error, task_id))
            conn.commit()
    finally:
        conn.close()


def add_task_file(task_id, file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_task_file (task_id, file_id)'
                ' VALUES (%s,%s)', (task_id, file_id))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_task_file_state(task_file_id, state):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_task_file SET state=%s WHERE id=%s',
                        (state, task_file_id))
            conn.commit()
    finally:
        conn.close()


def _task_doc(cur, task_id):
    """task 表投影（tasks API 的唯一数据源，无 task.json 附件）。"""
    cur.execute(
        'SELECT r.id, r.mode, r.state, r.error, r.params_json,'
        ' r.created_at, r.updated_at, t.name AS tpl_name, tv.version,'
        ' tv.id AS version_id'
        ' FROM extract_task r'
        ' JOIN extract_template_version tv ON tv.id=r.template_version_id'
        ' JOIN extract_template t ON t.id=tv.template_id'
        ' WHERE r.id=%s', (task_id,))
    rows = _rows(cur)
    if not rows:
        return None
    r = rows[0]
    cur.execute(
        'SELECT tf.id, tf.file_id, tf.state, s.name,'
        ' (SELECT COUNT(*) FROM extract_staging_record sr'
        '   WHERE sr.task_file_id=tf.id) AS records_n'
        ' FROM extract_task_file tf'
        ' JOIN extract_file s ON s.id=tf.file_id'
        ' WHERE tf.task_id=%s ORDER BY tf.id', (task_id,))
    files = [{'name': f['name'], 'state': f['state'],
              'file_id': f['file_id'],
              'task_file_id': f['id'], 'records_n': f['records_n']}
             for f in _rows(cur)]
    return {
        'task_id': r['id'], 'mode': r['mode'],
        'template': {'name': r['tpl_name'], 'version': r['version'],
                     'version_id': r['version_id']},
        'params': _j(r['params_json']) or {},
        'state': r['state'], 'error': r['error'],
        'files': files,
        'created_at': str(r['created_at']),
        'updated_at': str(r['updated_at']),
    }


def get_task(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            return _task_doc(cur, task_id)
    finally:
        conn.close()


def list_tasks():
    """任务列表（新任务在前）：逐个表投影，P0 规模足够。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_task ORDER BY id DESC')
            ids = [r[0] for r in cur.fetchall()]
            return [_task_doc(cur, i) for i in ids]
    finally:
        conn.close()


def task_file_ids(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_task_file'
                        ' WHERE task_id=%s ORDER BY id', (task_id,))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


# ---- extract_quarantine ----

def add_quarantine(task_id, task_file_id, record_index, stage, reason, payload):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_quarantine (task_id, task_file_id,'
                ' record_index, stage, reason, payload_json)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (task_id, task_file_id, record_index, stage, reason,
                 json.dumps(payload, ensure_ascii=False)))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def list_quarantine(task_id=None, state=None):
    conn = db.connect()
    try:
        where, args = [], []
        if task_id is not None:
            where.append('task_id=%s')
            args.append(task_id)
        if state:
            where.append('state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM extract_quarantine {} ORDER BY id DESC'
                        .format(w), args)
            rows = _rows(cur)
        for r in rows:
            r['payload_json'] = _j(r['payload_json'])
            r['created_at'] = str(r['created_at'])
        return rows
    finally:
        conn.close()