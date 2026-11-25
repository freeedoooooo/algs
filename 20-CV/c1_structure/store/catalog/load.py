"""目录库 · 入库域（c1_load_datasource / c1_load_table(_field) /
c1_load_log，P2b）。

数据源密码明文存库、API 明文返回（2026-11-21 裁决）；日志永不打印。
审计规则：数据源被映射引用后目标（host/port/db_name）锁定；
映射被任务引用后只读。回执幂等（唯一键防重）。
"""
import hashlib
import json

from ... import config
from .. import db, loader
from ..errors import BadRequest, Conflict, NotFound
from ._common import _j, _rows
from .rules import _tpl_exists

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
                ' (SELECT COUNT(*) FROM c1_load_table lt'
                '   WHERE lt.datasource_id=d.id) AS table_count'
                ' FROM c1_load_datasource d ORDER BY d.id')
            return [_ds_doc(r) for r in _rows(cur)]
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
    name = str(name or '').strip()
    host = str(host or '').strip()
    db_name = str(db_name or '').strip()
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
            cur.execute('SELECT id FROM c1_load_datasource'
                        ' WHERE name=%s', (name,))
            if cur.fetchone():
                raise Conflict('业务库名称已存在')
            cur.execute(
                'INSERT INTO c1_load_datasource (name, db_type, host,'
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
            cur.execute('SELECT id FROM c1_load_datasource WHERE id=%s',
                        (ds_id,))
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
                cur.execute('UPDATE c1_load_datasource SET name=%s'
                            ' WHERE id=%s', (name, ds_id))
            if user is not None:
                cur.execute('UPDATE c1_load_datasource SET user=%s'
                            ' WHERE id=%s', (str(user), ds_id))
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
                    raise Conflict('该业务库已被入库映射引用，主机、端口、库名不可修改；'
                                   '账号与密码可以修改。如需更换目标库，请新建业务库')
                sets = ', '.join('{}=%s'.format(k) for k in target)
                cur.execute('UPDATE c1_load_datasource SET ' + sets +
                            ' WHERE id=%s', list(target.values()) + [ds_id])
            conn.commit()
    finally:
        conn.close()


def delete_datasource(ds_id):
    """被映射引用禁删 Conflict（引用完整性归应用层）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_datasource WHERE id=%s',
                        (ds_id,))
            if not cur.fetchone():
                raise NotFound('业务库不存在')
            cur.execute('SELECT COUNT(*) FROM c1_load_table'
                        ' WHERE datasource_id=%s', (ds_id,))
            if cur.fetchone()[0]:
                raise Conflict('该业务库已被入库映射引用，禁止删除')
            cur.execute('DELETE FROM c1_load_datasource WHERE id=%s',
                        (ds_id,))
            conn.commit()
    finally:
        conn.close()


def ensure_default_datasource():
    """幂等种「产品库」默认行：解析 C1_STRUCTURE_DB 明文落行（升级脚本与
    新库首启共用）。尽力而为：解析/连接/写入失败静默跳过，断库启动不炸。"""
    try:
        p = db._parts(db.resolve_conn(config.PLATFORM_DB))
        conn = db.connect()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM c1_load_datasource'
                            " WHERE name='产品库'")
                row = cur.fetchone()
                if row:
                    return row[0]
                cur.execute(
                    'INSERT INTO c1_load_datasource (name, db_type,'
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
    ' lt.rule_id, lt.rule_version_id, t.name AS tpl_name, lt.target_table,'
    ' lt.write_mode, lt.source_snapshot_json, lt.created_at')
_LT_JOIN = (
    ' FROM c1_load_table lt'
    ' JOIN c1_load_datasource d ON d.id=lt.datasource_id'
    ' LEFT JOIN c1_extract_rule t ON t.id=lt.rule_id')


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
                r['source_snapshot'] = _j(r.pop('source_snapshot_json', None))
                cur.execute(
                    'SELECT target_column, is_business_key'
                    ' FROM c1_load_table_field WHERE load_table_id=%s'
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
            r['source_snapshot'] = _j(r.pop('source_snapshot_json', None))
            cur.execute('SELECT COUNT(*) FROM c1_doc_file'
                        ' WHERE load_table_id=%s', (lt_id,))
            r['file_refs'] = cur.fetchone()[0]
            r['task_refs'] = r['file_refs']
            cur.execute('SELECT rule_field, target_column,'
                        ' is_business_key, sort_order'
                        ' FROM c1_load_table_field WHERE load_table_id=%s'
                        ' ORDER BY sort_order, id', (lt_id,))
            r['fields'] = _rows(cur)
            return r
    finally:
        conn.close()


def _tpl_schema_fields(cur, rule_id):
    cur.execute(
        'SELECT tv.schema_json FROM c1_extract_rule_version tv'
        ' JOIN c1_extract_rule t ON t.id=tv.rule_id'
        ' WHERE tv.rule_id=%s AND tv.version=t.current_version',
        (rule_id,))
    row = cur.fetchone()
    sj = _j(row[0]) if row else None
    fields = ([f.get('name') for f in sj.get('fields') or []]
              if isinstance(sj, dict) else [])
    fields = [f for f in fields if f]
    if not fields:
        raise BadRequest('「原始透传」规则无固定字段，不支持配置入库映射')
    return fields


def _snapshot_names(snapshot):
    names = [f.get('name') for f in (snapshot or {}).get('fields') or []
             if isinstance(f, dict) and f.get('name')]
    if not names:
        raise BadRequest('抽取输出快照没有字段，无法配置入库映射')
    return names


def _build_snapshot(cur, rule_id, rule_version_id=None):
    """仅在用户选择参考抽取规则时生成快照；运行时不再依赖该规则。"""
    sql = ('SELECT tv.id, tv.schema_json, tv.mapping_json, tv.version, t.name'
           ' FROM c1_extract_rule_version tv'
           ' JOIN c1_extract_rule t ON t.id=tv.rule_id'
           ' WHERE tv.rule_id=%s')
    args = [rule_id]
    if rule_version_id:
        sql += ' AND tv.id=%s'
        args.append(rule_version_id)
    else:
        sql += ' AND tv.version=t.current_version'
    cur.execute(sql, args)
    row = cur.fetchone()
    if not row:
        raise NotFound('参考抽取规则版本不存在')
    vid, sj, mj, ver, name = row
    sj, mj = _j(sj), _j(mj)
    fields = []
    if isinstance(sj, dict):
        fields = [{'name': f.get('name'), 'type': f.get('type') or 'text'}
                  for f in sj.get('fields') or []
                  if isinstance(f, dict) and f.get('name')]
    if not fields and isinstance(mj, dict):
        fields = [{'name': f.get('target'), 'type': f.get('type') or 'text'}
                  for f in mj.get('fields') or []
                  if isinstance(f, dict) and f.get('target')]
    if not fields:
        raise BadRequest('该抽取规则没有固定输出字段，不能作为参考')
    snap = {'schema_version': 1, 'rule_id': rule_id, 'rule_version_id': vid,
            'rule_name': name, 'rule_version': ver, 'fields': fields}
    snap['hash'] = hashlib.sha256(json.dumps(
        fields, sort_keys=True, ensure_ascii=False).encode('utf-8')
    ).hexdigest()[:16]
    return snap


def _resolve_snapshot(cur, rule_id, rule_version_id, snapshot):
    snap = snapshot if isinstance(snapshot, dict) else None
    if snap:
        _snapshot_names(snap)
        if rule_id and not snap.get('rule_id'):
            snap['rule_id'] = rule_id
        if rule_version_id and not snap.get('rule_version_id'):
            snap['rule_version_id'] = rule_version_id
        return snap
    if not rule_id:
        raise BadRequest('请选择参考抽取规则，或提供抽取输出快照')
    return _build_snapshot(cur, rule_id, rule_version_id)


def _insert_fields(cur, lt_id, fields, schema_fields):
    order = {f: i for i, f in enumerate(schema_fields)}
    for f in fields:
        cur.execute(
            'INSERT INTO c1_load_table_field (load_table_id,'
            ' rule_field, target_column, is_business_key, sort_order)'
            ' VALUES (%s,%s,%s,%s,%s)',
            (lt_id, f['rule_field'], f['target_column'],
             1 if f.get('is_business_key') else 0,
             order.get(f['rule_field'], 0)))


def create_load_table(datasource_id, rule_id, target_table, write_mode,
                      fields, rule_version_id=None, snapshot=None):
    """映射绑定：业务库×目标表×抽取输出快照。抽取规则仅作配置期参考。
    fields=[{rule_field,target_column,is_business_key}]；契约按快照校验。"""
    target_table = str(target_table or '').strip()
    if not target_table:
        raise BadRequest('目标表名不能为空')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_datasource WHERE id=%s',
                        (datasource_id,))
            if not cur.fetchone():
                raise NotFound('业务库不存在')
            snap = _resolve_snapshot(cur, rule_id, rule_version_id, snapshot)
            schema_fields = _snapshot_names(snap)
            loader.validate_fields(schema_fields, fields, write_mode)
            cur.execute(
                'INSERT INTO c1_load_table (datasource_id, rule_id,'
                ' rule_version_id, target_table, write_mode,'
                ' source_snapshot_json) VALUES (%s,%s,%s,%s,%s,%s)',
                (datasource_id, rule_id, snap.get('rule_version_id'),
                 target_table, write_mode,
                 json.dumps(snap, ensure_ascii=False)))
            lt_id = cur.lastrowid
            _insert_fields(cur, lt_id, fields, schema_fields)
            conn.commit()
            return lt_id
    finally:
        conn.close()


def update_load_table(lt_id, write_mode=None, fields=None,
                      rule_version_id=None, snapshot=None):
    """被资料引用→只读 Conflict；否则整体编辑 write_mode/字段行/输出快照。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT rule_id, rule_version_id, write_mode,'
                        ' source_snapshot_json FROM c1_load_table WHERE id=%s',
                        (lt_id,))
            row = cur.fetchone()
            if not row:
                raise NotFound('入库映射不存在')
            cur.execute('SELECT COUNT(*) FROM c1_doc_file'
                        ' WHERE load_table_id=%s', (lt_id,))
            if cur.fetchone()[0]:
                raise Conflict('该入库映射已被资料引用，只读且不可删除')
            wm = write_mode if write_mode is not None else row[2]
            fs = fields
            if fs is None:
                cur.execute('SELECT rule_field, target_column,'
                            ' is_business_key FROM c1_load_table_field'
                            ' WHERE load_table_id=%s ORDER BY sort_order, id',
                            (lt_id,))
                fs = _rows(cur)
            snap = _resolve_snapshot(cur, row[0],
                                     rule_version_id or row[1],
                                     snapshot or _j(row[3]))
            schema_fields = _snapshot_names(snap)
            loader.validate_fields(schema_fields, fs, wm)
            cur.execute('UPDATE c1_load_table SET write_mode=%s,'
                        ' rule_version_id=%s, source_snapshot_json=%s'
                        ' WHERE id=%s',
                        (wm, snap.get('rule_version_id'),
                         json.dumps(snap, ensure_ascii=False), lt_id))
            cur.execute('DELETE FROM c1_load_table_field'
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
            cur.execute('SELECT id FROM c1_load_table WHERE id=%s',
                        (lt_id,))
            if not cur.fetchone():
                raise NotFound('入库映射不存在')
            cur.execute('SELECT COUNT(*) FROM c1_doc_file'
                        ' WHERE load_table_id=%s', (lt_id,))
            if cur.fetchone()[0]:
                raise Conflict('该入库映射已被资料引用，禁止删除')
            cur.execute('DELETE FROM c1_load_table_field'
                        ' WHERE load_table_id=%s', (lt_id,))
            cur.execute('DELETE FROM c1_load_table WHERE id=%s', (lt_id,))
            conn.commit()
    finally:
        conn.close()


def add_load_log(file_id, record_index, datasource_id,
                 target_table, target_pk, action):
    """幂等回执：唯一键已存在→跳过返回 False（单资料串行，先查后插无竞态）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_load_log'
                        ' WHERE file_id=%s AND record_index=%s'
                        ' AND datasource_id=%s AND target_table=%s',
                        (file_id, record_index, datasource_id, target_table))
            if cur.fetchone():
                return False
            cur.execute(
                'INSERT INTO c1_load_log (file_id, record_index,'
                ' datasource_id, target_table, target_pk, action)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (file_id, record_index, datasource_id,
                 target_table, str(target_pk)[:255], action))
            conn.commit()
            return True
    finally:
        conn.close()


def list_load_logs(file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT l.id, l.file_id, l.record_index,'
                        ' l.datasource_id, d.name AS datasource_name,'
                        ' d.db_name, l.target_table, l.target_pk, l.action,'
                        ' l.loaded_at'
                        ' FROM c1_load_log l'
                        ' LEFT JOIN c1_load_datasource d'
                        ' ON d.id=l.datasource_id'
                        ' WHERE l.file_id=%s'
                        ' ORDER BY l.file_id, l.record_index', (file_id,))
            rows = _rows(cur)
        for r in rows:
            r['loaded_at'] = str(r['loaded_at'])
        return rows
    finally:
        conn.close()


def clear_load_logs(file_id):
    """重放解析前置（D4）：清该资料全部入库回执。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute('DELETE FROM c1_load_log WHERE file_id=%s',
                            (file_id,))
            conn.commit()
        return n
    finally:
        conn.close()