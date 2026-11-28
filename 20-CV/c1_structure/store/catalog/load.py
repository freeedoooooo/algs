"""目录库 · 入库配置、绑定与回执。

c1_load_table/c1_load_mapping_field 只描述目标业务表；来源字段、写模式和
业务键属于 c1_load_binding。回执按 load_binding_id 隔离，平台表不可作为
业务目标，也不自动创建/修改业务表。
"""
import json

from ... import config
from .. import db, loader
from ..errors import BadRequest, Conflict, NotFound
from ._common import _j, _rows, snapshot_field_names

_DS_COLS = 'id, name, db_type, host, port, user, password, db_name, created_at'
_BINDING_STATUSES = ('pending', 'confirmed', 'running', 'ready', 'failed')


def _ds_doc(row):
    row['created_at'] = str(row['created_at'])
    return row


def list_datasources():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT d.id, d.name, d.db_type, d.host, d.port, d.user,'
                ' d.password, d.db_name, d.created_at,'
                ' (SELECT COUNT(*) FROM c1_load_table lt'
                '   WHERE lt.datasource_id=d.id) AS table_count'
                ' FROM c1_load_datasource d ORDER BY d.id')
            return [_ds_doc(row) for row in _rows(cur)]
    finally:
        conn.close()


def get_datasource(ds_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + _DS_COLS +
                        ' FROM c1_load_datasource WHERE id=%s', (ds_id,))
            rows = _rows(cur)
        return _ds_doc(rows[0]) if rows else None
    finally:
        conn.close()


def create_datasource(name, host, port, user, password, db_name,
                      db_type='mysql'):
    name, host, db_name = (str(name or '').strip(), str(host or '').strip(),
                           str(db_name or '').strip())
    if not name:
        raise BadRequest('业务库名称不能为空')
    if not host or not db_name:
        raise BadRequest('主机与库名不能为空')
    if db_type != 'mysql':
        raise BadRequest('当前版本仅支持 MySQL')
    try:
        port = int(port or 3306)
    except (TypeError, ValueError):
        raise BadRequest('端口须为整数')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_datasource WHERE name=%s',
                        (name,))
            if cur.fetchone():
                raise Conflict('业务库名称已存在')
            cur.execute(
                'INSERT INTO c1_load_datasource (name, db_type, host, port,'
                ' user, password, db_name) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (name, db_type, host, port, str(user or ''), str(password or ''),
                 db_name))
            ds_id = cur.lastrowid
            conn.commit()
            return ds_id
    finally:
        conn.close()


def update_datasource(ds_id, name=None, host=None, port=None, user=None,
                      password=None, db_name=None):
    """目标坐标被表配置引用后锁定；凭据轮换不影响历史回执。"""
    if host is not None and not str(host).strip():
        raise BadRequest('主机不能为空')
    if db_name is not None and not str(db_name).strip():
        raise BadRequest('库名不能为空')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_datasource WHERE id=%s', (ds_id,))
            if not cur.fetchone():
                raise NotFound('业务库不存在')
            if name is not None:
                name = str(name).strip()
                if not name:
                    raise BadRequest('业务库名称不能为空')
                cur.execute('SELECT id FROM c1_load_datasource'
                            ' WHERE name=%s AND id<>%s', (name, ds_id))
                if cur.fetchone():
                    raise Conflict('业务库名称已存在')
                cur.execute('UPDATE c1_load_datasource SET name=%s WHERE id=%s',
                            (name, ds_id))
            if user is not None:
                cur.execute('UPDATE c1_load_datasource SET user=%s WHERE id=%s',
                            (str(user), ds_id))
            if password is not None:
                cur.execute('UPDATE c1_load_datasource SET password=%s'
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
                cur.execute('SELECT COUNT(*) FROM c1_load_table'
                            ' WHERE datasource_id=%s', (ds_id,))
                if cur.fetchone()[0]:
                    raise Conflict('该业务库已被入库表配置引用，主机、端口、库名不可修改')
                cur.execute('UPDATE c1_load_datasource SET ' +
                            ', '.join(k + '=%s' for k in target) +
                            ' WHERE id=%s', list(target.values()) + [ds_id])
            conn.commit()
            loader.clear_introspection_cache()
    finally:
        conn.close()


def delete_datasource(ds_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_datasource WHERE id=%s', (ds_id,))
            if not cur.fetchone():
                raise NotFound('业务库不存在')
            cur.execute('SELECT COUNT(*) FROM c1_load_table'
                        ' WHERE datasource_id=%s', (ds_id,))
            if cur.fetchone()[0]:
                raise Conflict('该业务库已被入库表配置引用，禁止删除')
            cur.execute('DELETE FROM c1_load_datasource WHERE id=%s', (ds_id,))
            conn.commit()
            loader.clear_introspection_cache()
    finally:
        conn.close()


def ensure_default_datasource():
    """尽力而为地初始化默认数据源；连接或写入失败不阻断启动。"""
    try:
        parts = db._parts(db.resolve_conn(config.PLATFORM_DB))
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM c1_load_datasource WHERE name='产品库'")
                row = cur.fetchone()
                if row:
                    return row[0]
                cur.execute(
                    "INSERT INTO c1_load_datasource (name, db_type, host, port,"
                    " user, password, db_name) VALUES ('产品库','mysql',%s,%s,%s,%s,%s)",
                    (parts['host'], parts['port'], parts['user'],
                     parts['password'], parts['database']))
                conn.commit()
                return cur.lastrowid
        finally:
            conn.close()
    except Exception:
        return None


# ---- 目标表配置：只有 datasource_id/target_table 与字段元数据 ----

def _table_row(cur, lt_id):
    cur.execute(
        'SELECT lt.id, lt.datasource_id, lt.target_table, lt.created_at,'
        ' lt.updated_at, d.name AS datasource_name, d.db_name'
        ' FROM c1_load_table lt JOIN c1_load_datasource d'
        ' ON d.id=lt.datasource_id WHERE lt.id=%s', (lt_id,))
    return cur.fetchone()


def _attach_fields(cur, row):
    cur.execute(
        'SELECT id, load_table_id, field_name, data_type, is_primary,'
        ' has_default, sort_order FROM c1_load_mapping_field'
        ' WHERE load_table_id=%s ORDER BY sort_order, id', (row['id'],))
    row['fields'] = _rows(cur)
    row['field_count'] = len(row['fields'])
    return row


def list_load_tables(datasource_id=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            sql = ('SELECT lt.id, lt.datasource_id, lt.target_table, lt.created_at,'
                   ' lt.updated_at, d.name AS datasource_name, d.db_name'
                   ' FROM c1_load_table lt JOIN c1_load_datasource d'
                   ' ON d.id=lt.datasource_id')
            args = []
            if datasource_id is not None:
                sql += ' WHERE lt.datasource_id=%s'
                args.append(datasource_id)
            sql += ' ORDER BY lt.id'
            cur.execute(sql, args)
            rows = [_attach_fields(cur, row) for row in _rows(cur)]
        for row in rows:
            row['created_at'] = str(row['created_at'])
            row['updated_at'] = str(row['updated_at'])
        return rows
    finally:
        conn.close()


def get_load_table(lt_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT lt.id, lt.datasource_id, lt.target_table, lt.created_at,'
                ' lt.updated_at, d.name AS datasource_name, d.db_name'
                ' FROM c1_load_table lt JOIN c1_load_datasource d'
                ' ON d.id=lt.datasource_id WHERE lt.id=%s', (lt_id,))
            rows = _rows(cur)
            if not rows:
                return None
            row = _attach_fields(cur, rows[0])
            cur.execute('SELECT COUNT(*) FROM c1_load_binding'
                        ' WHERE load_table_id=%s', (lt_id,))
            row['binding_refs'] = cur.fetchone()[0]
        row['created_at'] = str(row['created_at'])
        row['updated_at'] = str(row['updated_at'])
        return row
    finally:
        conn.close()


def _metadata(fields):
    if fields is None:
        return []
    if not isinstance(fields, list):
        raise BadRequest('目标字段元数据须为数组')
    out, seen = [], set()
    for order, field in enumerate(fields):
        if not isinstance(field, dict):
            raise BadRequest('目标字段元数据格式不正确')
        name = str(field.get('field_name') or '').strip()
        if not name:
            raise BadRequest('目标字段名不能为空')
        if name in seen:
            raise BadRequest('目标字段重复：{}'.format(name))
        seen.add(name)
        out.append({
            'field_name': name,
            'data_type': str(field.get('data_type') or field.get('type') or 'text'),
            'is_primary': 1 if field.get('is_primary') or field.get('primary') else 0,
            'has_default': 1 if field.get('has_default') or field.get('default') is not None else 0,
            'sort_order': int(field.get('sort_order', order)),
        })
    return out


def _replace_fields(cur, lt_id, fields):
    cur.execute('DELETE FROM c1_load_mapping_field WHERE load_table_id=%s', (lt_id,))
    for field in fields:
        cur.execute(
            'INSERT INTO c1_load_mapping_field (load_table_id, field_name,'
            ' data_type, is_primary, has_default, sort_order)'
            ' VALUES (%s,%s,%s,%s,%s,%s)',
            (lt_id, field['field_name'], field['data_type'], field['is_primary'],
             field['has_default'], field['sort_order']))


def create_load_table(datasource_id, target_table, fields=None):
    """创建可跨抽取结果复用的目标表配置，返回 load_table_id。"""
    target_table = str(target_table or '').strip()
    if not loader.is_business_table(target_table):
        raise BadRequest('只能选择现有业务表，不能写入平台 c1_ 表')
    metadata = _metadata(fields)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_datasource WHERE id=%s',
                        (datasource_id,))
            if not cur.fetchone():
                raise NotFound('业务库不存在')
            cur.execute('SELECT id FROM c1_load_table WHERE datasource_id=%s'
                        ' AND target_table=%s', (datasource_id, target_table))
            if cur.fetchone():
                raise Conflict('该业务表配置已存在')
            cur.execute('INSERT INTO c1_load_table (datasource_id, target_table)'
                        ' VALUES (%s,%s)', (datasource_id, target_table))
            lt_id = cur.lastrowid
            _replace_fields(cur, lt_id, metadata)
            conn.commit()
            return lt_id
    finally:
        conn.close()


def update_load_table(lt_id, target_table=None, fields=None):
    """只改目标表配置/字段元数据；来源映射不属于本实体。"""
    metadata = _metadata(fields)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            row = _table_row(cur, lt_id)
            if not row:
                raise NotFound('入库表配置不存在')
            if target_table is not None:
                target_table = str(target_table).strip()
                if not loader.is_business_table(target_table):
                    raise BadRequest('只能选择现有业务表，不能写入平台 c1_ 表')
                cur.execute('SELECT COUNT(*) FROM c1_load_binding'
                            ' WHERE load_table_id=%s', (lt_id,))
                if cur.fetchone()[0]:
                    raise Conflict('该表配置已有绑定，不可更换目标表')
                cur.execute('UPDATE c1_load_table SET target_table=%s,'
                            ' updated_at=NOW() WHERE id=%s', (target_table, lt_id))
            if fields is not None:
                allowed = {field['field_name'] for field in metadata}
                cur.execute('SELECT field_map_json FROM c1_load_binding'
                            ' WHERE load_table_id=%s', (lt_id,))
                for (raw,) in cur.fetchall():
                    missing = set((_j(raw) or {}).values()) - allowed
                    if missing:
                        raise Conflict('字段元数据不能删除已绑定目标列：{}'.format(
                            '、'.join(sorted(missing))))
                _replace_fields(cur, lt_id, metadata)
                cur.execute('UPDATE c1_load_table SET updated_at=NOW()'
                            ' WHERE id=%s', (lt_id,))
            conn.commit()
            loader.clear_introspection_cache()
    finally:
        conn.close()


def delete_load_table(lt_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if not _table_row(cur, lt_id):
                raise NotFound('入库表配置不存在')
            cur.execute('SELECT COUNT(*) FROM c1_load_binding'
                        ' WHERE load_table_id=%s', (lt_id,))
            if cur.fetchone()[0]:
                raise Conflict('该入库表配置已被绑定引用，禁止删除')
            _replace_fields(cur, lt_id, [])
            cur.execute('DELETE FROM c1_load_table WHERE id=%s', (lt_id,))
            conn.commit()
    finally:
        conn.close()


# ---- 入库绑定：每条抽取结果最多一条 ----

def _binding_row(cur, binding_id):
    cur.execute(
        'SELECT b.id, b.doc_id, b.extract_result_id, b.load_table_id,'
        ' b.field_map_json, b.write_mode, b.business_keys_json, b.status,'
        ' b.confirmed_at, b.error, b.created_at, b.updated_at,'
        ' r.rule_id, t.name AS rule_name, d.name AS doc_name,'
        ' lt.target_table, ds.id AS datasource_id, ds.name AS datasource_name,'
        ' ds.db_name FROM c1_load_binding b'
        ' JOIN c1_extract_result r ON r.id=b.extract_result_id'
        ' JOIN c1_extract_rule t ON t.id=r.rule_id'
        ' JOIN c1_doc d ON d.id=b.doc_id'
        ' JOIN c1_load_table lt ON lt.id=b.load_table_id'
        ' JOIN c1_load_datasource ds ON ds.id=lt.datasource_id'
        ' WHERE b.id=%s', (binding_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(zip([d[0] for d in cur.description], row))


def _decode_binding(row):
    if not row:
        return None
    row['field_map_json'] = _j(row.get('field_map_json')) or {}
    row['business_keys_json'] = _j(row.get('business_keys_json')) or []
    for key in ('confirmed_at', 'created_at', 'updated_at'):
        row[key] = str(row[key]) if row.get(key) else None
    return row


def _result_fields(cur, extract_result_id):
    cur.execute('SELECT rule_snapshot_json FROM c1_extract_result'
                ' WHERE id=%s', (extract_result_id,))
    row = cur.fetchone()
    if not row:
        raise NotFound('抽取结果不存在')
    fields = snapshot_field_names(_j(row[0]))
    if fields:
        return fields
    cur.execute('SELECT values_json FROM c1_extract_record'
                ' WHERE extract_result_id=%s', (extract_result_id,))
    names = []
    for (raw,) in cur.fetchall():
        for name in (_j(raw) or {}):
            if name not in names:
                names.append(name)
    return fields or names


def _validate_binding(cur, extract_result_id, load_table_id, field_map,
                      write_mode, business_keys):
    cur.execute('SELECT doc_id FROM c1_extract_result WHERE id=%s',
                (extract_result_id,))
    row = cur.fetchone()
    if not row:
        raise NotFound('抽取结果不存在')
    if not _table_row(cur, load_table_id):
        raise NotFound('入库表配置不存在')
    cur.execute('SELECT field_name FROM c1_load_mapping_field'
                ' WHERE load_table_id=%s', (load_table_id,))
    columns = [r[0] for r in cur.fetchall()]
    if not columns:
        raise BadRequest('入库表配置缺少目标字段元数据，请先刷新字段')
    loader.validate_fields(_result_fields(cur, extract_result_id), field_map,
                           write_mode, business_keys, columns)
    return row[0]


def _binding_params(field_map, write_mode, business_keys):
    return (json.dumps(field_map, ensure_ascii=False), write_mode,
            json.dumps(list(business_keys or []), ensure_ascii=False))


def create_binding(extract_result_id, load_table_id, field_map,
                  write_mode='insert', business_keys=None):
    """创建待确认绑定；返回 load_binding_id。不会写业务库。"""
    if write_mode not in ('insert', 'upsert', 'update'):
        raise BadRequest('非法写入方式：{}'.format(write_mode))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_binding'
                        ' WHERE extract_result_id=%s', (extract_result_id,))
            if cur.fetchone():
                raise Conflict('该抽取结果已有入库绑定')
            doc_id = _validate_binding(cur, extract_result_id, load_table_id,
                                       field_map, write_mode, business_keys)
            fm, wm, bk = _binding_params(field_map, write_mode, business_keys)
            cur.execute(
                'INSERT INTO c1_load_binding (doc_id, extract_result_id,'
                ' load_table_id, field_map_json, write_mode, business_keys_json,'
                " status) VALUES (%s,%s,%s,%s,%s,%s,'pending')",
                (doc_id, extract_result_id, load_table_id, fm, wm, bk))
            binding_id = cur.lastrowid
            conn.commit()
            return binding_id
    finally:
        conn.close()


def update_binding(binding_id, load_table_id=None, field_map=None,
                   write_mode=None, business_keys=None):
    """修改待确认/失败绑定；修改后回到 pending，旧回执与入库隔离清空。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            raw = _binding_row(cur, binding_id)
            if not raw:
                raise NotFound('入库绑定不存在')
            old = raw
            if old['status'] in ('confirmed', 'running', 'ready'):
                raise Conflict('已确认或执行中的绑定不可修改；重抽后重新配置')
            fm = field_map if field_map is not None else (_j(old['field_map_json']) or {})
            wm = write_mode or old['write_mode']
            bk = business_keys if business_keys is not None else \
                (_j(old['business_keys_json']) or [])
            lt_id = load_table_id or old['load_table_id']
            _validate_binding(cur, old['extract_result_id'], lt_id, fm, wm, bk)
            fmj, wmj, bkj = _binding_params(fm, wm, bk)
            cur.execute(
                'UPDATE c1_load_binding SET load_table_id=%s, field_map_json=%s,'
                ' write_mode=%s, business_keys_json=%s, status=%s,'
                ' confirmed_at=NULL, error=NULL, updated_at=NOW() WHERE id=%s',
                (lt_id, fmj, wmj, bkj, 'pending', binding_id))
            cur.execute('DELETE FROM c1_load_receipt WHERE load_binding_id=%s',
                        (binding_id,))
            cur.execute('DELETE FROM c1_quarantine_record'
                        ' WHERE load_binding_id=%s', (binding_id,))
            conn.commit()
    finally:
        conn.close()


def get_binding(binding_id=None, extract_result_id=None):
    if binding_id is None and extract_result_id is None:
        raise BadRequest('请指定 binding_id 或 extract_result_id')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if binding_id is not None:
                raw = _binding_row(cur, binding_id)
            else:
                cur.execute('SELECT id FROM c1_load_binding'
                            ' WHERE extract_result_id=%s', (extract_result_id,))
                row = cur.fetchone()
                raw = _binding_row(cur, row[0]) if row else None
        return _decode_binding(raw)
    finally:
        conn.close()


def list_bindings(doc_id=None, extract_result_id=None, load_table_id=None):
    where, args = [], []
    for key, value in (('b.doc_id', doc_id),
                       ('b.extract_result_id', extract_result_id),
                       ('b.load_table_id', load_table_id)):
        if value is not None:
            where.append(key + '=%s')
            args.append(value)
    w = (' WHERE ' + ' AND '.join(where)) if where else ''
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT b.id, b.doc_id, b.extract_result_id, b.load_table_id,'
                ' b.field_map_json, b.write_mode, b.business_keys_json, b.status,'
                ' b.confirmed_at, b.error, b.created_at, b.updated_at,'
                ' r.rule_id, t.name AS rule_name, d.name AS doc_name,'
                ' lt.target_table, ds.id AS datasource_id,'
                ' ds.name AS datasource_name, ds.db_name'
                ' FROM c1_load_binding b'
                ' JOIN c1_extract_result r ON r.id=b.extract_result_id'
                ' JOIN c1_extract_rule t ON t.id=r.rule_id'
                ' JOIN c1_doc d ON d.id=b.doc_id'
                ' JOIN c1_load_table lt ON lt.id=b.load_table_id'
                ' JOIN c1_load_datasource ds ON ds.id=lt.datasource_id' + w +
                ' ORDER BY b.doc_id, b.id', args)
            return [_decode_binding(row) for row in _rows(cur)]
    finally:
        conn.close()


def confirm_binding(binding_id):
    """显式确认绑定；确认不等于执行入库。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            raw = _binding_row(cur, binding_id)
            if not raw:
                raise NotFound('入库绑定不存在')
            old = raw
            if old['status'] != 'pending':
                raise Conflict('仅待确认绑定可以确认')
            cur.execute("SELECT status FROM c1_extract_result WHERE id=%s",
                        (old['extract_result_id'],))
            if cur.fetchone()[0] != 'ready':
                raise Conflict('抽取结果尚未完成，不能确认入库')
            _validate_binding(cur, old['extract_result_id'], old['load_table_id'],
                              _j(old['field_map_json']) or {}, old['write_mode'],
                              _j(old['business_keys_json']) or [])
            cur.execute("UPDATE c1_load_binding SET status='confirmed',"
                        ' confirmed_at=NOW(), error=NULL, updated_at=NOW()'
                        ' WHERE id=%s', (binding_id,))
            conn.commit()
    finally:
        conn.close()


def start_binding(binding_id):
    """只有显式确认后的绑定可进入 running。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            raw = _binding_row(cur, binding_id)
            if not raw:
                raise NotFound('入库绑定不存在')
            if raw['status'] != 'confirmed':
                raise Conflict('入库绑定尚未显式确认')
            cur.execute("UPDATE c1_load_binding SET status='running',"
                        ' error=NULL, updated_at=NOW() WHERE id=%s', (binding_id,))
            conn.commit()
    finally:
        conn.close()


def finish_binding(binding_id, status='ready', error=None):
    if status not in ('ready', 'failed'):
        raise BadRequest('结束状态仅支持 ready/failed')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if not _binding_row(cur, binding_id):
                raise NotFound('入库绑定不存在')
            cur.execute('UPDATE c1_load_binding SET status=%s, error=%s,'
                        ' updated_at=NOW() WHERE id=%s',
                        (status, error, binding_id))
            conn.commit()
    finally:
        conn.close()


# ---- 回执：唯一键 (load_binding_id, record_index) ----

def add_receipt(load_binding_id, record_index, target_pk, action):
    """幂等写入单条回执；目标数据源和表从绑定读取。"""
    if action not in ('insert', 'update'):
        raise BadRequest('非法回执动作：{}'.format(action))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if not _binding_row(cur, load_binding_id):
                raise NotFound('入库绑定不存在')
            cur.execute('SELECT id FROM c1_load_receipt'
                        ' WHERE load_binding_id=%s AND record_index=%s',
                        (load_binding_id, record_index))
            if cur.fetchone():
                return False
            cur.execute(
                'INSERT INTO c1_load_receipt (load_binding_id, doc_id,'
                ' record_index, datasource_id, target_table, target_pk, action)'
                ' SELECT b.id, b.doc_id, %s, lt.datasource_id, lt.target_table,'
                ' %s, %s FROM c1_load_binding b'
                ' JOIN c1_load_table lt ON lt.id=b.load_table_id WHERE b.id=%s',
                (record_index, str(target_pk)[:255], action, load_binding_id))
            conn.commit()
            return True
    finally:
        conn.close()


def list_receipts(load_binding_id=None, doc_id=None):
    where, args = [], []
    if load_binding_id is not None:
        where.append('r.load_binding_id=%s')
        args.append(load_binding_id)
    if doc_id is not None:
        where.append('r.doc_id=%s')
        args.append(doc_id)
    w = (' WHERE ' + ' AND '.join(where)) if where else ''
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT r.id, r.load_binding_id, r.doc_id,'
                ' b.extract_result_id, r.record_index, r.datasource_id,'
                ' d.name AS datasource_name, d.db_name, r.target_table,'
                ' r.target_pk, r.action, r.loaded_at'
                ' FROM c1_load_receipt r'
                ' JOIN c1_load_binding b ON b.id=r.load_binding_id'
                ' LEFT JOIN c1_load_datasource d ON d.id=r.datasource_id' + w +
                ' ORDER BY r.doc_id, r.load_binding_id, r.record_index', args)
            rows = _rows(cur)
        for row in rows:
            row['loaded_at'] = str(row['loaded_at'])
        return rows
    finally:
        conn.close()


def purge_receipts(load_binding_id=None, doc_id=None):
    if load_binding_id is None and doc_id is None:
        raise BadRequest('请指定 load_binding_id 或 doc_id')
    where, args = [], []
    if load_binding_id is not None:
        where.append('load_binding_id=%s')
        args.append(load_binding_id)
    if doc_id is not None:
        where.append('doc_id=%s')
        args.append(doc_id)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute('DELETE FROM c1_load_receipt WHERE ' +
                            ' AND '.join(where), args)
            conn.commit()
            return n
    finally:
        conn.close()


def list_loaded_results():
    """按数据源、业务表、文档和绑定汇总已有回执。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT r.datasource_id, r.target_table, r.doc_id,'
                ' b.extract_result_id, r.load_binding_id, COUNT(*) AS row_count,'
                ' d.name FROM c1_load_receipt r'
                ' JOIN c1_load_binding b ON b.id=r.load_binding_id'
                ' JOIN c1_doc d ON d.id=r.doc_id'
                ' GROUP BY r.datasource_id, r.target_table, r.doc_id,'
                ' b.extract_result_id, r.load_binding_id, d.name'
                ' ORDER BY r.datasource_id, r.target_table, row_count DESC,'
                ' r.doc_id, r.load_binding_id')
            return _rows(cur)
    finally:
        conn.close()
