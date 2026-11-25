"""目录库 · 资料域（c1_doc_file ＋ content 原件字节 ＋ 运行状态）。

一条资料记录 = 一次运行（单文件）。哈希不去重：每次上传插新行，
同字节文件允许多条独立运行（D2 裁决）；sha256 仅作检索/ETag。
content LONGBLOB 只在 get_file_content 里取，列表/元数据查询一律排除该列。
"""
from .. import db
from ..errors import Conflict
from ._common import _rows, _j

_FILE_COLS = ('c1_doc_file.id, c1_doc_file.name, c1_doc_file.sha256,'
              ' c1_doc_file.kind, c1_doc_file.size_bytes, c1_doc_file.tags,'
              ' c1_doc_file.note, c1_doc_file.created_at, c1_doc_file.state,'
              ' c1_doc_file.error, c1_doc_file.rule_version_id,'
              ' c1_doc_file.params_json, c1_doc_file.load_datasource_id,'
              ' c1_doc_file.load_table_id, c1_doc_file.updated_at')

# 抽取规则名＋版本号（资料列表直接展示「规则名 vN」，避免只显示空版本号看不清）
_RULE_JOIN = (
    ' LEFT JOIN c1_extract_rule_version rv'
    ' ON rv.id=c1_doc_file.rule_version_id'
    ' LEFT JOIN c1_extract_rule er ON er.id=rv.rule_id')
_RULE_COLS = ', er.name AS rule_name, rv.version AS rule_version'


def register_file(name, kind, size_bytes, sha256, content):
    """登记新行（不去重，恒返回 (new_id, False) 兼容旧 dedup 契约）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_doc_file (name, sha256, kind,'
                ' size_bytes, content) VALUES (%s,%s,%s,%s,%s)',
                (name, sha256, kind, size_bytes, content))
            conn.commit()
            return cur.lastrowid, False
    finally:
        conn.close()


def list_files(q=None, kind=None, tag=None, page=1, per_page=20, state=None):
    conn = db.connect()
    try:
        where, args = [], []
        if q:
            where.append('c1_doc_file.name LIKE %s')
            args.append('%{}%'.format(q))
        if kind:
            where.append('c1_doc_file.kind=%s')
            args.append(kind)
        if tag:
            where.append('c1_doc_file.tags LIKE %s')
            args.append('%{}%'.format(tag))
        if state:
            where.append('c1_doc_file.state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM c1_doc_file ' + w, args)
            total = cur.fetchone()[0]
            cur.execute(
                'SELECT {}{} FROM c1_doc_file {} {} ORDER BY c1_doc_file.id DESC'
                ' LIMIT %s OFFSET %s'.format(_FILE_COLS, _RULE_COLS,
                                             _RULE_JOIN, w),
                args + [per_page, (max(1, page) - 1) * per_page])
            items = _rows(cur)
        for it in items:
            it['created_at'] = str(it['created_at'])
            it['updated_at'] = str(it['updated_at'])
            it['params_json'] = _j(it.get('params_json')) or {}
        return {'items': items, 'total': total}
    finally:
        conn.close()


def get_file(file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT {} FROM c1_doc_file WHERE id=%s'
                        .format(_FILE_COLS), (file_id,))
            rows = _rows(cur)
        if rows:
            rows[0]['params_json'] = _j(rows[0].get('params_json')) or {}
        return rows[0] if rows else None
    finally:
        conn.close()


def get_file_content(file_id):
    """原件字节 + 路由所需元数据（/srcfiles/{id} 用）；不存在回 None。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, sha256, content'
                        ' FROM c1_doc_file WHERE id=%s', (file_id,))
            row = cur.fetchone()
        if not row:
            return None
        return {'name': row[0], 'kind': row[1], 'sha': row[2], 'data': row[3]}
    finally:
        conn.close()


def delete_file(file_id):
    """运行中有产物/暂存时禁删（保血缘）；否则应用层级联清子表后删行。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT state FROM c1_doc_file WHERE id=%s', (file_id,))
            row = cur.fetchone()
            if row and row[0] in ('parsing', 'loading', 'loaded'):
                raise Conflict('该资料正在处理或已入库，为保证血缘可追溯，不可删除')
            # 无外键：先显式清子表，避免留孤儿产物/记录
            cur.execute('DELETE FROM c1_staging_field WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id=%s)',
                        (file_id,))
            cur.execute('DELETE FROM c1_staging_lineage WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id=%s)',
                        (file_id,))
            for t in ('c1_staging_record', 'c1_parse_artifact',
                      'c1_load_log', 'c1_load_quarantine'):
                cur.execute('DELETE FROM ' + t + ' WHERE file_id=%s', (file_id,))
            cur.execute('DELETE FROM c1_doc_file WHERE id=%s', (file_id,))
            conn.commit()
    finally:
        conn.close()


def update_file_meta(file_id, tags=None, note=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_doc_file SET tags=%s, note=%s'
                        ' WHERE id=%s', (tags, note, file_id))
            conn.commit()
    finally:
        conn.close()


# ---- 运行状态（原 c1_task / c1_task_file 的职责，落到资料行）----

def set_state(file_id, state, error=None):
    """更新运行状态；error=None 表示不动该列（重放复位须显式传空串）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if error is None:
                cur.execute('UPDATE c1_doc_file SET state=%s WHERE id=%s',
                            (state, file_id))
            else:
                cur.execute('UPDATE c1_doc_file SET state=%s, error=%s'
                            ' WHERE id=%s', (state, error, file_id))
            conn.commit()
    finally:
        conn.close()


def set_rule(file_id, version_id):
    """执行抽取时绑定/换绑规则版本（抽取时刻生效）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_doc_file SET rule_version_id=%s'
                        ' WHERE id=%s', (version_id, file_id))
            conn.commit()
    finally:
        conn.close()


def set_load(file_id, datasource_id, load_table_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_doc_file SET load_datasource_id=%s,'
                        ' load_table_id=%s WHERE id=%s',
                        (datasource_id, load_table_id, file_id))
            conn.commit()
    finally:
        conn.close()


def set_params(file_id, params):
    import json
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_doc_file SET params_json=%s WHERE id=%s',
                        (json.dumps(params or {}, ensure_ascii=False), file_id))
            conn.commit()
    finally:
        conn.close()


# ---- 隔离区（原 catalog/tasks.py 迁入，键改 file_id）----

def add_quarantine(file_id, record_index, stage, reason, payload):
    import json
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_load_quarantine (file_id, record_index,'
                ' stage, reason, payload_json) VALUES (%s,%s,%s,%s,%s)',
                (file_id, record_index, stage, reason,
                 json.dumps(payload, ensure_ascii=False)))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def clear_quarantine(file_id):
    """重放解析前置：清该资料隔离行（回执按 D4 另由调用方清）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute('DELETE FROM c1_load_quarantine WHERE file_id=%s',
                            (file_id,))
            conn.commit()
        return n
    finally:
        conn.close()


def list_quarantine(file_id=None, state=None):
    import json
    conn = db.connect()
    try:
        where, args = [], []
        if file_id is not None:
            where.append('file_id=%s')
            args.append(file_id)
        if state:
            where.append('state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM c1_load_quarantine {} ORDER BY id DESC'
                        .format(w), args)
            rows = _rows(cur)
        for r in rows:
            r['payload_json'] = json.loads(r['payload_json'])
            r['created_at'] = str(r['created_at'])
        return rows
    finally:
        conn.close()
