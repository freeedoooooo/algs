"""
store/catalog.py — 目录元数据 repo（MySQL）。P0 子集：
extract_source_file / extract_template(+version) / extract_run / extract_run_file /
extract_quarantine。业务表统一 extract_ 前缀（002 迁移）；schema_version 为迁移簿记表。

只经 db.connect 拿 DB-API 连接，SQL 全部收敛在本文件；DB 必选，错误上抛
（DB 故障只记 warning，提取与 Preview 文件链路不受影响）。
JSON 列：写入 json.dumps，读出 json.loads（驱动无关，不依赖 MySQL JSON 函数）。
"""
import json

from . import db


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _j(v):
    if isinstance(v, (str, bytes)):
        return json.loads(v)
    return v


# ---- extract_source_file ----

def register_source(name, kind, size_bytes, sha256, rel_path):
    """哈希去重登记：已存在回已有 id（dedup=True），不重复建副本。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_source_file WHERE sha256=%s',
                        (sha256,))
            row = cur.fetchone()
            if row:
                return row[0], True
            cur.execute(
                'INSERT INTO extract_source_file (name, sha256, kind, size_bytes,'
                ' rel_path) VALUES (%s,%s,%s,%s,%s)',
                (name, sha256, kind, size_bytes, rel_path))
            conn.commit()
            return cur.lastrowid, False
    finally:
        conn.close()


def list_sources(q=None, kind=None, tag=None, page=1, per_page=20):
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
            cur.execute('SELECT COUNT(*) FROM extract_source_file ' + w, args)
            total = cur.fetchone()[0]
            cur.execute(
                'SELECT * FROM extract_source_file {} ORDER BY id DESC LIMIT %s'
                ' OFFSET %s'.format(w),
                args + [per_page, (max(1, page) - 1) * per_page])
            items = _rows(cur)
        for it in items:
            it['created_at'] = str(it['created_at'])
        return {'items': items, 'total': total}
    finally:
        conn.close()


def get_source(source_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM extract_source_file WHERE id=%s',
                        (source_id,))
            rows = _rows(cur)
        return rows[0] if rows else None
    finally:
        conn.close()


def delete_source(source_id):
    """被 Run 引用禁删（血缘完整）；返回 (ok, reason)。副本删除由调用方做。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM extract_run_file'
                        ' WHERE source_file_id=%s', (source_id,))
            if cur.fetchone()[0]:
                return False, '该文件已被运行引用，禁止删除（血缘完整）'
            cur.execute('DELETE FROM extract_source_file WHERE id=%s',
                        (source_id,))
            conn.commit()
            return True, None
    finally:
        conn.close()


def update_source_meta(source_id, tags=None, note=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_source_file SET tags=%s, note=%s'
                        ' WHERE id=%s', (tags, note, source_id))
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


# ---- extract_run / extract_run_file ----

def create_run(batch_tag, mode, template_version_id, params):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_run (batch_tag, mode, template_version_id,'
                ' params_json, state) VALUES (%s,%s,%s,%s,%s)',
                (batch_tag, mode, template_version_id,
                 json.dumps(params or {}, ensure_ascii=False), 'pending'))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_run_state(run_id, state, error=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_run SET state=%s, error=%s WHERE id=%s',
                        (state, error, run_id))
            conn.commit()
    finally:
        conn.close()


def add_run_file(run_id, source_file_id, output_rel_dir):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_run_file (run_id, source_file_id,'
                ' output_rel_dir) VALUES (%s,%s,%s)',
                (run_id, source_file_id, output_rel_dir))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_run_file_state(run_file_id, state):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_run_file SET state=%s WHERE id=%s',
                        (state, run_file_id))
            conn.commit()
    finally:
        conn.close()


def list_batch_tags():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT batch_tag FROM extract_run')
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def list_run_cases():
    """(case 目录名, batch_tag) 列表，新 run 在前 —— artifact db 模式的 runs 数据源。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT rf.output_rel_dir, r.batch_tag'
                ' FROM extract_run r JOIN extract_run_file rf ON rf.run_id=r.id'
                ' ORDER BY r.id DESC, rf.id')
            return [(row[0].rsplit('/', 1)[-1], row[1])
                    for row in cur.fetchall()]
    finally:
        conn.close()


# ---- extract_quarantine ----

def add_quarantine(run_id, run_file_id, record_index, stage, reason, payload):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_quarantine (run_id, run_file_id,'
                ' record_index, stage, reason, payload_json)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (run_id, run_file_id, record_index, stage, reason,
                 json.dumps(payload, ensure_ascii=False)))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def list_quarantine(run_id=None, state=None):
    conn = db.connect()
    try:
        where, args = [], []
        if run_id is not None:
            where.append('run_id=%s')
            args.append(run_id)
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