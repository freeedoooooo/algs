"""store/index_repo.py — 指标域（c1_index_info / c1_index_value）。

简化设计（2026-11-26）：定义同名唯一、无版本、无哈希；结果只存血缘锚点。
"""
from . import db
from .errors import BadRequest, NotFound
from .value_common import rows, unjson, dump

_AGG = ('sum', 'count', 'avg', 'min', 'max', 'count_distinct')
_FILTER_OP = ('eq', 'ne', 'gt', 'gte', 'lt', 'lte')
_INFO_COLS = ('id', 'name', 'datasource_id', 'source_table',
              'source_column', 'aggregate', 'filter_json',
              'created_at', 'updated_at')
_VALUE_COLS = ('id', 'index_id', 'index_value', 'computed_at')


def _validate(name, datasource_id, source_table, aggregate, filter_json):
    name = str(name or '').strip()
    if not name:
        raise BadRequest('指标名不能为空')
    if datasource_id is None:
        raise BadRequest('须指定业务库 datasource_id')
    if not str(source_table or '').strip():
        raise BadRequest('须指定业务表 source_table')
    if aggregate not in _AGG:
        raise BadRequest('聚合方式仅支持：' + '/'.join(_AGG))
    if filter_json in (None, '', {}):
        filter_json = []
    if not isinstance(filter_json, list):
        raise BadRequest('filter_json 须为数组')
    for item in filter_json:
        if not isinstance(item, dict) or item.get('op') not in _FILTER_OP:
            raise BadRequest('过滤条件 op 仅支持：' + '/'.join(_FILTER_OP))
        if not item.get('column'):
            raise BadRequest('过滤条件缺 column')
    return name, filter_json


def list_defs():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                        ' FROM c1_index_info ORDER BY id')
            out = rows(cur)
        for r in out:
            r['filter_json'] = unjson(r['filter_json'])
        return out
    finally:
        conn.close()


def get_def(index_id=None, name=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if index_id is not None:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_index_info WHERE id=%s', (index_id,))
            elif name:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_index_info WHERE name=%s', (name,))
            else:
                return None
            got = rows(cur)
        if not got:
            return None
        r = got[0]
        r['filter_json'] = unjson(r['filter_json'])
        return r
    finally:
        conn.close()


def save_def(name, datasource_id, source_table, source_column, aggregate,
             filter_json=None, index_id=None):
    """新建或覆盖更新（同名唯一）；返回定义 ID。"""
    name, filter_json = _validate(name, datasource_id, source_table,
                                  aggregate, filter_json)
    vals = (datasource_id, str(source_table).strip(),
            (str(source_column).strip() if source_column else None),
            aggregate, dump(filter_json))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if index_id:
                cur.execute('SELECT id FROM c1_index_info WHERE id=%s',
                            (index_id,))
                if not cur.fetchone():
                    raise NotFound('指标定义不存在')
                cur.execute('UPDATE c1_index_info SET datasource_id=%s,'
                            ' source_table=%s,source_column=%s,aggregate=%s,'
                            ' filter_json=%s WHERE id=%s', vals + (index_id,))
                did = index_id
            else:
                cur.execute('SELECT id FROM c1_index_info WHERE name=%s',
                            (name,))
                hit = cur.fetchone()
                if hit:
                    did = hit[0]
                    cur.execute('UPDATE c1_index_info SET datasource_id=%s,'
                                ' source_table=%s,source_column=%s,'
                                ' aggregate=%s,filter_json=%s WHERE id=%s',
                                vals + (did,))
                else:
                    cur.execute(
                        'INSERT INTO c1_index_info'
                        ' (name,datasource_id,source_table,source_column,'
                        '  aggregate,filter_json) VALUES (%s,%s,%s,%s,%s,%s)',
                        (name,) + vals)
                    did = cur.lastrowid
            conn.commit()
            return did
    finally:
        conn.close()


create_def = save_def


def delete_def(index_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_index_info WHERE id=%s', (index_id,))
            if not cur.fetchone():
                raise NotFound('指标定义不存在')
            cur.execute('DELETE FROM c1_index_value WHERE index_id=%s',
                        (index_id,))
            cur.execute('DELETE FROM c1_index_info WHERE id=%s', (index_id,))
            from .compute_layout_repo import delete_for_def
            delete_for_def(cur, 'index', index_id)
            conn.commit()
    finally:
        conn.close()


def add_value(index_id, index_value):
    """覆盖指标结果：同一事务先删旧值，再写入唯一新值。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_index_info WHERE id=%s', (index_id,))
            if not cur.fetchone():
                raise NotFound('指标定义不存在')
            cur.execute('DELETE FROM c1_index_value WHERE index_id=%s',
                        (index_id,))
            cur.execute('INSERT INTO c1_index_value (index_id,index_value)'
                        ' VALUES (%s,%s)', (index_id, str(index_value)))
            vid = cur.lastrowid
            conn.commit()
            return vid
    finally:
        conn.close()


def get_value(value_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_VALUE_COLS) +
                        ' FROM c1_index_value WHERE id=%s', (value_id,))
            got = rows(cur)
        return got[0] if got else None
    finally:
        conn.close()


def list_values(index_id=None, limit=200):
    sql = 'SELECT ' + ','.join(_VALUE_COLS) + ' FROM c1_index_value'
    args = []
    if index_id is not None:
        sql += ' WHERE index_id=%s'
        args.append(index_id)
    sql += ' ORDER BY id DESC LIMIT %s'
    args.append(max(1, min(500, int(limit or 200))))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return rows(cur)
    finally:
        conn.close()
