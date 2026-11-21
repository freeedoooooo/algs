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

from .. import config
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
        ' r.load_datasource_id, r.load_table_id,'
        ' d.name AS datasource_name, d.db_name,'
        ' lt.target_table, lt.write_mode'
        ' FROM extract_task r'
        ' JOIN extract_template_version tv ON tv.id=r.template_version_id'
        ' JOIN extract_template t ON t.id=tv.template_id'
        ' LEFT JOIN extract_load_datasource d ON d.id=r.load_datasource_id'
        ' LEFT JOIN extract_load_table lt ON lt.id=r.load_table_id'
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
        'load': ({'datasource_id': r['load_datasource_id'],
                  'load_table_id': r['load_table_id'],
                  'datasource_name': r['datasource_name'],
                  'db_name': r['db_name'],
                  'target_table': r['target_table'],
                  'write_mode': r['write_mode']}
                 if r['load_datasource_id'] else None),
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


# ---- extract_load_datasource / extract_load_table(_field) / extract_load_log（P2b）----

_DS_COLS = 'id, name, db_type, host, port, user, password, db_name, created_at'


def _ds_doc(r):
    r['created_at'] = str(r['created_at'])
    return r


def list_datasources():
    """含密码明文（2026-11-21 裁决：页面可见可编辑）；日志永不打印。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT d.id, d.name, d.db_type, d.host, d.port, d.user,'
                ' d.password, d.db_name, d.created_at,'
                ' (SELECT COUNT(*) FROM extract_load_table lt'
                '   WHERE lt.datasource_id=d.id) AS table_count'
                ' FROM extract_load_datasource d ORDER BY d.id')
            return [_ds_doc(r) for r in _rows(cur)]
    finally:
        conn.close()


def get_datasource(ds_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + _DS_COLS +
                        ' FROM extract_load_datasource WHERE id=%s', (ds_id,))
            rows = _rows(cur)
        return _ds_doc(rows[0]) if rows else None
    finally:
        conn.close()


def create_datasource(name, host, port, user, password, db_name,
                      db_type='mysql'):
    name = str(name or '').strip()
    host = str(host or '').strip()
    db_name = str(db_name or '').strip()
    if not name:
        raise BadRequest('数据源名称不能为空')
    if not host or not db_name:
        raise BadRequest('主机与库名不能为空')
    if db_type != 'mysql':
        raise BadRequest('首个实现仅支持 mysql')
    try:
        port = int(port or 3306)
    except (TypeError, ValueError):
        raise BadRequest('端口须为整数')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_datasource'
                        ' WHERE name=%s', (name,))
            if cur.fetchone():
                raise Conflict('数据源名称已存在')
            cur.execute(
                'INSERT INTO extract_load_datasource (name, db_type, host,'
                ' port, user, password, db_name)'
                ' VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (name, db_type, host, port, str(user or ''),
                 str(password or ''), db_name))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def update_datasource(ds_id, name=None, host=None, port=None, user=None,
                      password=None, db_name=None):
    """name/user/password 恒可改（凭据轮换合法）；host/port/db_name 被映射
    引用后锁定——改它们＝换目标库，历史回执追溯断裂（审计规则）→Conflict。"""
    if host is not None and not str(host).strip():
        raise BadRequest('主机不能为空')
    if db_name is not None and not str(db_name).strip():
        raise BadRequest('库名不能为空')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_datasource WHERE id=%s',
                        (ds_id,))
            if not cur.fetchone():
                raise NotFound('数据源不存在')
            if name is not None:
                name = str(name).strip()
                if not name:
                    raise BadRequest('数据源名称不能为空')
                cur.execute('SELECT id FROM extract_load_datasource'
                            ' WHERE name=%s AND id<>%s', (name, ds_id))
                if cur.fetchone():
                    raise Conflict('数据源名称已存在')
                cur.execute('UPDATE extract_load_datasource SET name=%s'
                            ' WHERE id=%s', (name, ds_id))
            if user is not None:
                cur.execute('UPDATE extract_load_datasource SET user=%s'
                            ' WHERE id=%s', (str(user), ds_id))
            if password is not None:
                cur.execute('UPDATE extract_load_datasource SET password=%s'
                            ' WHERE id=%s', (str(password), ds_id))
            target = {}
            if host is not None:
                target['host'] = str(host).strip()
            if port is not None:
                try:
                    target['port'] = int(port)
                except (TypeError, ValueError):
                    raise BadRequest('端口须为整数')
            if db_name is not None:
                target['db_name'] = str(db_name).strip()
            if target:
                cur.execute('SELECT COUNT(*) FROM extract_load_table'
                            ' WHERE datasource_id=%s', (ds_id,))
                if cur.fetchone()[0]:
                    raise Conflict('已被映射引用，目标（主机/端口/库名）锁定；'
                                   '账号密码可改，换目标请新建数据源')
                sets = ', '.join('{}=%s'.format(k) for k in target)
                cur.execute('UPDATE extract_load_datasource SET ' + sets +
                            ' WHERE id=%s', list(target.values()) + [ds_id])
            conn.commit()
    finally:
        conn.close()


def delete_datasource(ds_id):
    """被映射引用禁删 Conflict（引用完整性归应用层）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_datasource WHERE id=%s',
                        (ds_id,))
            if not cur.fetchone():
                raise NotFound('数据源不存在')
            cur.execute('SELECT COUNT(*) FROM extract_load_table'
                        ' WHERE datasource_id=%s', (ds_id,))
            if cur.fetchone()[0]:
                raise Conflict('该数据源已被映射引用，禁止删除')
            cur.execute('DELETE FROM extract_load_datasource WHERE id=%s',
                        (ds_id,))
            conn.commit()
    finally:
        conn.close()


def ensure_default_datasource():
    """幂等种「产品库」默认行：解析 C1_EXTRACT_DB 明文落行（升级脚本与
    新库首启共用）。尽力而为：解析/连接/写入失败静默跳过，断库启动不炸。"""
    try:
        p = db._parts(db.resolve_conn(config.PLATFORM_DB_REF))
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM extract_load_datasource'
                            " WHERE name='产品库'")
                row = cur.fetchone()
                if row:
                    return row[0]
                cur.execute(
                    'INSERT INTO extract_load_datasource (name, db_type,'
                    ' host, port, user, password, db_name)'
                    " VALUES ('产品库','mysql',%s,%s,%s,%s,%s)",
                    (p['host'], p['port'], p['user'], p['password'],
                     p['database']))
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()
    except Exception:
        return None


_LT_COLS = (
    ' lt.id, lt.datasource_id, d.name AS datasource_name, d.db_name,'
    ' lt.template_id, t.name AS tpl_name, lt.target_table,'
    ' lt.write_mode, lt.created_at')
_LT_JOIN = (
    ' FROM extract_load_table lt'
    ' JOIN extract_load_datasource d ON d.id=lt.datasource_id'
    ' JOIN extract_template t ON t.id=lt.template_id')


def list_load_tables(datasource_id=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if datasource_id is None:
                cur.execute('SELECT' + _LT_COLS + _LT_JOIN + ' ORDER BY lt.id')
            else:
                cur.execute('SELECT' + _LT_COLS + _LT_JOIN +
                            ' WHERE lt.datasource_id=%s ORDER BY lt.id',
                            (datasource_id,))
            rows = _rows(cur)
            for r in rows:
                r['created_at'] = str(r['created_at'])
                cur.execute(
                    'SELECT target_column, is_business_key'
                    ' FROM extract_load_table_field WHERE load_table_id=%s'
                    ' ORDER BY sort_order, id', (r['id'],))
                fs = _rows(cur)
                r['field_count'] = len(fs)
                r['business_keys'] = [f['target_column'] for f in fs
                                      if f['is_business_key']]
            return rows
    finally:
        conn.close()


def get_load_table(lt_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT' + _LT_COLS + _LT_JOIN + ' WHERE lt.id=%s',
                        (lt_id,))
            rows = _rows(cur)
            if not rows:
                return None
            r = rows[0]
            r['created_at'] = str(r['created_at'])
            cur.execute('SELECT COUNT(*) FROM extract_task'
                        ' WHERE load_table_id=%s', (lt_id,))
            r['task_refs'] = cur.fetchone()[0]
            cur.execute('SELECT template_field, target_column,'
                        ' is_business_key, sort_order'
                        ' FROM extract_load_table_field WHERE load_table_id=%s'
                        ' ORDER BY sort_order, id', (lt_id,))
            r['fields'] = _rows(cur)
            return r
    finally:
        conn.close()


def _tpl_schema_fields(cur, template_id):
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
    return fields


def _insert_fields(cur, lt_id, fields, schema_fields):
    order = {f: i for i, f in enumerate(schema_fields)}
    for f in fields:
        cur.execute(
            'INSERT INTO extract_load_table_field (load_table_id,'
            ' template_field, target_column, is_business_key, sort_order)'
            ' VALUES (%s,%s,%s,%s,%s)',
            (lt_id, f['template_field'], f['target_column'],
             1 if f.get('is_business_key') else 0,
             order.get(f['template_field'], 0)))


def create_load_table(datasource_id, template_id, target_table, write_mode,
                      fields):
    """映射绑定：数据源×表×模板。fields=[{template_field,target_column,
    is_business_key}]；契约校验在建时做，目标列存在性归预检。
    UNIQUE(ds,tpl,table)→Conflict（同物理表可被不同模板各建一行）。"""
    target_table = str(target_table or '').strip()
    if not target_table:
        raise BadRequest('目标表名不能为空')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_datasource WHERE id=%s',
                        (datasource_id,))
            if not cur.fetchone():
                raise NotFound('数据源不存在')
            _tpl_exists(cur, template_id)
            schema_fields = _tpl_schema_fields(cur, template_id)
            loader.validate_fields(schema_fields, fields, write_mode)
            cur.execute('SELECT id FROM extract_load_table'
                        ' WHERE datasource_id=%s AND template_id=%s'
                        ' AND target_table=%s',
                        (datasource_id, template_id, target_table))
            if cur.fetchone():
                raise Conflict('同数据源＋模板＋目标表的映射已存在')
            cur.execute(
                'INSERT INTO extract_load_table (datasource_id, template_id,'
                ' target_table, write_mode) VALUES (%s,%s,%s,%s)',
                (datasource_id, template_id, target_table, write_mode))
            lt_id = cur.lastrowid
            _insert_fields(cur, lt_id, fields, schema_fields)
            conn.commit()
            return lt_id
    finally:
        conn.close()


def update_load_table(lt_id, write_mode=None, fields=None):
    """被任务引用→只读 Conflict（回执语义）；否则整体编辑 write_mode/字段行。
    数据源/模板/目标表不可改——改它们＝新绑定，走新建。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT template_id, write_mode'
                        ' FROM extract_load_table WHERE id=%s', (lt_id,))
            row = cur.fetchone()
            if not row:
                raise NotFound('映射不存在')
            cur.execute('SELECT COUNT(*) FROM extract_task'
                        ' WHERE load_table_id=%s', (lt_id,))
            if cur.fetchone()[0]:
                raise Conflict('该映射已被任务引用，只读（删除亦禁止）')
            wm = write_mode if write_mode is not None else row[1]
            fs = fields
            if fs is None:
                cur.execute('SELECT template_field, target_column,'
                            ' is_business_key FROM extract_load_table_field'
                            ' WHERE load_table_id=%s ORDER BY sort_order, id',
                            (lt_id,))
                fs = _rows(cur)
            schema_fields = _tpl_schema_fields(cur, row[0])
            loader.validate_fields(schema_fields, fs, wm)
            cur.execute('UPDATE extract_load_table SET write_mode=%s'
                        ' WHERE id=%s', (wm, lt_id))
            cur.execute('DELETE FROM extract_load_table_field'
                        ' WHERE load_table_id=%s', (lt_id,))
            _insert_fields(cur, lt_id, fs, schema_fields)
            conn.commit()
    finally:
        conn.close()


def delete_load_table(lt_id):
    """被任务引用禁删 Conflict（入库意图的血缘完整）；先删字段行再删主行。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_table WHERE id=%s',
                        (lt_id,))
            if not cur.fetchone():
                raise NotFound('映射不存在')
            cur.execute('SELECT COUNT(*) FROM extract_task'
                        ' WHERE load_table_id=%s', (lt_id,))
            if cur.fetchone()[0]:
                raise Conflict('该映射已被任务引用，禁止删除')
            cur.execute('DELETE FROM extract_load_table_field'
                        ' WHERE load_table_id=%s', (lt_id,))
            cur.execute('DELETE FROM extract_load_table WHERE id=%s', (lt_id,))
            conn.commit()
    finally:
        conn.close()


def set_task_load(task_id, datasource_id, load_table_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_task SET load_datasource_id=%s,'
                        ' load_table_id=%s WHERE id=%s',
                        (datasource_id, load_table_id, task_id))
            conn.commit()
    finally:
        conn.close()


def add_load_log(task_id, task_file_id, record_index, datasource_id,
                 target_table, target_pk, action):
    """幂等回执：唯一键已存在→跳过返回 False（单任务串行，先查后插无竞态）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_load_log'
                        ' WHERE task_file_id=%s AND record_index=%s'
                        ' AND datasource_id=%s AND target_table=%s',
                        (task_file_id, record_index, datasource_id,
                         target_table))
            if cur.fetchone():
                return False
            cur.execute(
                'INSERT INTO extract_load_log (task_id, task_file_id,'
                ' record_index, datasource_id, target_table, target_pk, action)'
                ' VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (task_id, task_file_id, record_index, datasource_id,
                 target_table, str(target_pk)[:255], action))
            conn.commit()
            return True
    finally:
        conn.close()


def list_load_logs(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT l.id, l.task_file_id, l.record_index,'
                        ' l.datasource_id, d.name AS datasource_name,'
                        ' d.db_name, l.target_table, l.target_pk, l.action,'
                        ' l.loaded_at'
                        ' FROM extract_load_log l'
                        ' LEFT JOIN extract_load_datasource d'
                        ' ON d.id=l.datasource_id'
                        ' WHERE l.task_id=%s'
                        ' ORDER BY l.task_file_id, l.record_index', (task_id,))
            rows = _rows(cur)
        for r in rows:
            r['loaded_at'] = str(r['loaded_at'])
        return rows
    finally:
        conn.close()