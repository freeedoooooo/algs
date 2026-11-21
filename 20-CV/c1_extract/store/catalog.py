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

from . import db, loader
from .errors import BadRequest, Conflict, NotFound

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
                '     AND tv.version=t.current_version) AS current_version_id,'
                ' (SELECT COUNT(*) FROM extract_template_version tv'
                '   WHERE tv.template_id=t.id) AS version_count,'
                ' t.updated_at'
                ' FROM extract_template t ORDER BY t.id')
            return _rows(cur)
    finally:
        conn.close()


def get_template_version(version_id=None, name=None):
    """按 id / 模板名取版本；都不给则取第一个模板的当前版本（名可改，不硬编码）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if version_id is not None:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id WHERE tv.id=%s', (version_id,))
            elif name:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id'
                    ' WHERE t.name=%s AND tv.version=t.current_version',
                    (name,))
            else:
                cur.execute(
                    'SELECT tv.id, tv.template_id, tv.version, tv.schema_json,'
                    ' tv.mapping_json, tv.transform_json, t.name'
                    ' FROM extract_template_version tv JOIN extract_template t'
                    ' ON t.id = tv.template_id'
                    ' WHERE tv.version=t.current_version'
                    ' ORDER BY t.id LIMIT 1')
            rows = _rows(cur)
        if not rows:
            return None
        r = rows[0]
        for k in ('schema_json', 'mapping_json', 'transform_json'):
            r[k] = _j(r[k])
        return r
    finally:
        conn.close()


def _tpl_exists(cur, template_id):
    cur.execute('SELECT id FROM extract_template WHERE id=%s', (template_id,))
    if not cur.fetchone():
        raise NotFound('模板不存在')


def _tpl_payload(schema, mapping, transform):
    for v in (schema, mapping, transform):
        if v is not None and not isinstance(v, dict):
            raise BadRequest('模板 JSON 须为对象')
    return (json.dumps(schema), json.dumps(mapping), json.dumps(transform))


def get_template(template_id):
    """模板元数据＋当前版本三段 JSON（编辑器加载用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute(
                'SELECT t.id, t.name, t.description, t.current_version,'
                ' tv.id AS current_version_id, tv.schema_json,'
                ' tv.mapping_json, tv.transform_json'
                ' FROM extract_template t LEFT JOIN extract_template_version tv'
                ' ON tv.template_id=t.id AND tv.version=t.current_version'
                ' WHERE t.id=%s', (template_id,))
            r = _rows(cur)[0]
        for k in ('schema_json', 'mapping_json', 'transform_json'):
            r[k] = _j(r[k])
        return r
    finally:
        conn.close()


def create_template(name, description=None, schema=None, mapping=None,
                    transform=None):
    """建模板＋v1 不可变快照＋current=1；重名 Conflict。返回版本 id。"""
    name = str(name or '').strip()
    if not name:
        raise BadRequest('模板名不能为空')
    sj, mj, tj = _tpl_payload(schema, mapping, transform)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_template WHERE name=%s', (name,))
            if cur.fetchone():
                raise Conflict('模板名已存在')
            cur.execute('INSERT INTO extract_template (name, description,'
                        ' current_version) VALUES (%s,%s,1)',
                        (name, description))
            tid = cur.lastrowid
            cur.execute('INSERT INTO extract_template_version'
                        ' (template_id, version, schema_json, mapping_json,'
                        ' transform_json) VALUES (%s,1,%s,%s,%s)',
                        (tid, sj, mj, tj))
            vid = cur.lastrowid
            conn.commit()
            return vid
    finally:
        conn.close()


def create_version(template_id, schema=None, mapping=None, transform=None):
    """编辑＝新版本不可变快照＋current 前移（旧任务引用旧版本不受影响）。"""
    sj, mj, tj = _tpl_payload(schema, mapping, transform)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute('SELECT COALESCE(MAX(version),0) FROM'
                        ' extract_template_version WHERE template_id=%s',
                        (template_id,))
            v = cur.fetchone()[0] + 1
            cur.execute('INSERT INTO extract_template_version'
                        ' (template_id, version, schema_json, mapping_json,'
                        ' transform_json) VALUES (%s,%s,%s,%s,%s)',
                        (template_id, v, sj, mj, tj))
            vid = cur.lastrowid
            cur.execute('UPDATE extract_template SET current_version=%s'
                        ' WHERE id=%s', (v, template_id))
            conn.commit()
            return vid
    finally:
        conn.close()


def update_template(template_id, name=None, description=None,
                    current_version=None):
    """改名/说明不建新版本；current_version 须已存在否则 BadRequest。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            if name is not None:
                name = str(name).strip()
                if not name:
                    raise BadRequest('模板名不能为空')
                cur.execute('SELECT id FROM extract_template'
                            ' WHERE name=%s AND id<>%s', (name, template_id))
                if cur.fetchone():
                    raise Conflict('模板名已存在')
                cur.execute('UPDATE extract_template SET name=%s WHERE id=%s',
                            (name, template_id))
            if description is not None:
                cur.execute('UPDATE extract_template SET description=%s'
                            ' WHERE id=%s', (description, template_id))
            if current_version is not None:
                cur.execute('SELECT id FROM extract_template_version'
                            ' WHERE template_id=%s AND version=%s',
                            (template_id, current_version))
                if not cur.fetchone():
                    raise BadRequest('版本号不存在')
                cur.execute('UPDATE extract_template SET current_version=%s'
                            ' WHERE id=%s', (current_version, template_id))
            conn.commit()
    finally:
        conn.close()


def delete_template(template_id):
    """被任务引用（任一版本）禁删 Conflict；无引用先删 versions 再删模板。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute('SELECT COUNT(*) FROM extract_task WHERE'
                        ' template_version_id IN (SELECT id FROM'
                        ' extract_template_version WHERE template_id=%s)',
                        (template_id,))
            if cur.fetchone()[0]:
                raise Conflict('该模板已被任务引用，禁止删除')
            cur.execute('DELETE FROM extract_template_version'
                        ' WHERE template_id=%s', (template_id,))
            cur.execute('DELETE FROM extract_template WHERE id=%s',
                        (template_id,))
            conn.commit()
    finally:
        conn.close()


def list_versions(template_id):
    """版本倒序＋是否当前（版本历史/设当前用）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _tpl_exists(cur, template_id)
            cur.execute('SELECT tv.id, tv.version, tv.created_at,'
                        ' (tv.version=t.current_version) AS is_current'
                        ' FROM extract_template_version tv'
                        ' JOIN extract_template t ON t.id=tv.template_id'
                        ' WHERE tv.template_id=%s ORDER BY tv.version DESC',
                        (template_id,))
            return _rows(cur)
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
        ' tv.id AS version_id, tv.template_id,'
        ' r.load_dest_id, r.load_mapping_id,'
        ' ld.name AS dest_name, lm.target_table, lm.write_mode'
        ' FROM extract_task r'
        ' JOIN extract_template_version tv ON tv.id=r.template_version_id'
        ' JOIN extract_template t ON t.id=tv.template_id'
        ' LEFT JOIN extract_load_dest ld ON ld.id=r.load_dest_id'
        ' LEFT JOIN extract_load_mapping lm ON lm.id=r.load_mapping_id'
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
                     'version_id': r['version_id'],
                     'template_id': r['template_id']},
        'params': _j(r['params_json']) or {},
        'state': r['state'], 'error': r['error'],
        'load': ({'dest_id': r['load_dest_id'],
                  'mapping_id': r['load_mapping_id'],
                  'dest_name': r['dest_name'],
                  'target_table': r['target_table'],
                  'write_mode': r['write_mode']}
                 if r['load_dest_id'] else None),
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


# ---- extract_load_dest / extract_load_mapping / extract_load_log（P2）----

def list_dests():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name, db_type, conn_ref, created_at'
                        ' FROM extract_load_dest ORDER BY id')
            rows = _rows(cur)
        for r in rows:
            r['created_at'] = str(r['created_at'])
        return rows
    finally:
        conn.close()


def get_dest(dest_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name, db_type, conn_ref, created_at'
                        ' FROM extract_load_dest WHERE id=%s', (dest_id,))
            rows = _rows(cur)
        if not rows:
            return None
        rows[0]['created_at'] = str(rows[0]['created_at'])
        return rows[0]
    finally:
        conn.close()


def create_dest(name, conn_ref, db_type='mysql'):
    name = str(name or '').strip()
    conn_ref = str(conn_ref or '').strip()
    if not name:
        raise BadRequest('目的地名称不能为空')
    if not conn_ref:
        raise BadRequest('conn_ref 不能为空（凭据引用名，非密码）')
    if db_type != 'mysql':
        raise BadRequest('首个实现仅支持 mysql')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_dest WHERE name=%s',
                        (name,))
            if cur.fetchone():
                raise Conflict('目的地名称已存在')
            cur.execute('INSERT INTO extract_load_dest (name, db_type,'
                        ' conn_ref) VALUES (%s,%s,%s)',
                        (name, db_type, conn_ref))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def delete_dest(dest_id):
    """被映射引用禁删 Conflict（引用完整性归应用层）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_dest WHERE id=%s',
                        (dest_id,))
            if not cur.fetchone():
                raise NotFound('目的地不存在')
            cur.execute('SELECT COUNT(*) FROM extract_load_mapping'
                        ' WHERE load_dest_id=%s', (dest_id,))
            if cur.fetchone()[0]:
                raise Conflict('该目的地已被映射引用，禁止删除')
            cur.execute('DELETE FROM extract_load_dest WHERE id=%s', (dest_id,))
            conn.commit()
    finally:
        conn.close()


_MAPPING_COLS = (
    ' m.id, m.load_dest_id, d.name AS dest_name, d.conn_ref,'
    ' m.template_id, t.name AS tpl_name, m.target_table,'
    ' m.column_map_json, m.write_mode, m.business_key_json, m.created_at')
_MAPPING_JOIN = (
    ' FROM extract_load_mapping m'
    ' JOIN extract_load_dest d ON d.id=m.load_dest_id'
    ' JOIN extract_template t ON t.id=m.template_id')


def _mapping_doc(r):
    r['column_map_json'] = _j(r['column_map_json'])
    r['business_key_json'] = _j(r['business_key_json'])
    r['created_at'] = str(r['created_at'])
    return r


def list_mappings():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT' + _MAPPING_COLS + _MAPPING_JOIN +
                        ' ORDER BY m.id')
            return [_mapping_doc(r) for r in _rows(cur)]
    finally:
        conn.close()


def get_mapping(mapping_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT' + _MAPPING_COLS + _MAPPING_JOIN +
                        ' WHERE m.id=%s', (mapping_id,))
            rows = _rows(cur)
        return _mapping_doc(rows[0]) if rows else None
    finally:
        conn.close()


def create_mapping(load_dest_id, template_id, target_table, column_map,
                   write_mode='upsert', business_key=None):
    """契约校验（覆盖/业务键/写入模式）在建时做；目标列存在性归预检。
    透传模板（schema 无 fields）不可入库。UNIQUE(dest,tpl,table)→Conflict。"""
    target_table = str(target_table or '').strip()
    if not target_table:
        raise BadRequest('目标表名不能为空')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_dest WHERE id=%s',
                        (load_dest_id,))
            if not cur.fetchone():
                raise NotFound('目的地不存在')
            _tpl_exists(cur, template_id)
            cur.execute(
                'SELECT tv.schema_json FROM extract_template_version tv'
                ' JOIN extract_template t ON t.id=tv.template_id'
                ' WHERE tv.template_id=%s AND tv.version=t.current_version',
                (template_id,))
            row = cur.fetchone()
            sj = _j(row[0]) if row else None
            fields = ([f.get('name') for f in sj.get('fields') or []]
                      if isinstance(sj, dict) else [])
            fields = [f for f in fields if f]
            if not fields:
                raise BadRequest('透传模板无固定目标字段，不可登记入库映射')
            loader.validate_column_map(fields, column_map, write_mode,
                                       business_key)
            cur.execute('SELECT id FROM extract_load_mapping'
                        ' WHERE load_dest_id=%s AND template_id=%s'
                        ' AND target_table=%s',
                        (load_dest_id, template_id, target_table))
            if cur.fetchone():
                raise Conflict('同目的地＋模板＋目标表的映射已存在')
            cur.execute(
                'INSERT INTO extract_load_mapping (load_dest_id, template_id,'
                ' target_table, column_map_json, write_mode, business_key_json)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (load_dest_id, template_id, target_table,
                 json.dumps(column_map, ensure_ascii=False), write_mode,
                 json.dumps(business_key, ensure_ascii=False)
                 if business_key else None))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def delete_mapping(mapping_id):
    """被任务引用禁删 Conflict（入库意图的血缘完整）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_mapping WHERE id=%s',
                        (mapping_id,))
            if not cur.fetchone():
                raise NotFound('映射不存在')
            cur.execute('SELECT COUNT(*) FROM extract_task'
                        ' WHERE load_mapping_id=%s', (mapping_id,))
            if cur.fetchone()[0]:
                raise Conflict('该映射已被任务引用，禁止删除')
            cur.execute('DELETE FROM extract_load_mapping WHERE id=%s',
                        (mapping_id,))
            conn.commit()
    finally:
        conn.close()


def set_task_load(task_id, dest_id, mapping_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_task SET load_dest_id=%s,'
                        ' load_mapping_id=%s WHERE id=%s',
                        (dest_id, mapping_id, task_id))
            conn.commit()
    finally:
        conn.close()


def add_load_log(task_id, task_file_id, record_index, load_dest_id,
                 target_table, target_pk, action):
    """幂等回执：唯一键已存在→跳过返回 False（单任务串行，先查后插无竞态）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_log'
                        ' WHERE task_file_id=%s AND record_index=%s'
                        ' AND load_dest_id=%s AND target_table=%s',
                        (task_file_id, record_index, load_dest_id,
                         target_table))
            if cur.fetchone():
                return False
            cur.execute(
                'INSERT INTO extract_load_log (task_id, task_file_id,'
                ' record_index, load_dest_id, target_table, target_pk, action)'
                ' VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (task_id, task_file_id, record_index, load_dest_id,
                 target_table, str(target_pk)[:255], action))
            conn.commit()
            return True
    finally:
        conn.close()


def list_load_logs(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, task_file_id, record_index, load_dest_id,'
                        ' target_table, target_pk, action, loaded_at'
                        ' FROM extract_load_log WHERE task_id=%s'
                        ' ORDER BY task_file_id, record_index', (task_id,))
            rows = _rows(cur)
        for r in rows:
            r['loaded_at'] = str(r['loaded_at'])
        return rows
    finally:
        conn.close()