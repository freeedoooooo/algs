"""store/index_repo.py — 指标域（c1_index_info / c1_index_value）。

定义版本行同表不可变（create 生成新版本）；值行带输入锚点与 result_hash，
由上层 compute 引擎写入；唯一键 (index_id,index_version,result_hash) 防重复。
无外键：引用完整性归应用层（删除定义须先查值引用）。
"""
import json

from . import db
from .errors import BadRequest, Conflict, NotFound
from .value_common import (rows, unjson, dump, spec_hash as _spec_hash,
                           value_hash as _value_hash)

_AGG = ('sum', 'count', 'avg', 'min', 'max', 'count_distinct')
_FILTER_OP = ('eq', 'ne', 'gt', 'gte', 'lt', 'lte')

_INFO_COLS = ('id', 'name', 'version', 'datasource_id', 'source_table',
              'source_column', 'aggregate', 'filter_json', 'spec_hash',
              'created_at')
_VALUE_COLS = ('id', 'index_id', 'index_version', 'value_text',
               'input_rows_json', 'result_hash', 'computed_at')


def _spec(datasource_id, source_table, source_column, aggregate, filter_json):
    return {'datasource_id': datasource_id, 'source_table': source_table,
            'source_column': source_column, 'aggregate': aggregate,
            'filter_json': filter_json or []}


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
    """定义列表：同名只展示最大版本（当前版）+ 版本数。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT i.id, i.name, i.version, i.datasource_id,'
                ' i.source_table, i.source_column, i.aggregate,'
                ' i.filter_json, i.spec_hash, i.created_at,'
                ' (SELECT MAX(x.version) FROM c1_index_info x'
                '   WHERE x.name=i.name) AS latest_version,'
                ' (SELECT COUNT(*) FROM c1_index_info x'
                '   WHERE x.name=i.name) AS version_count'
                ' FROM c1_index_info i'
                ' WHERE i.version=(SELECT MAX(x.version) FROM c1_index_info x'
                '                  WHERE x.name=i.name)'
                ' ORDER BY i.id')
            out = rows(cur)
        for r in out:
            r['filter_json'] = unjson(r['filter_json'])
        return out
    finally:
        conn.close()


def get_def(index_id=None, name=None, version=None):
    """按 id / 名字取定义；version=None 取当前版；name 不存在返回 None。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if index_id is not None:
                cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                            ' FROM c1_index_info WHERE id=%s', (index_id,))
            elif name:
                if version is not None:
                    cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                                ' FROM c1_index_info WHERE name=%s AND version=%s',
                                (name, version))
                else:
                    cur.execute('SELECT ' + ','.join(_INFO_COLS) +
                                ' FROM c1_index_info WHERE name=%s'
                                ' ORDER BY version DESC LIMIT 1', (name,))
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


def list_versions(name):
    cur_def = get_def(name=name)
    if cur_def is None:
        raise NotFound('指标定义不存在')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, version, created_at, spec_hash'
                        ' FROM c1_index_info WHERE name=%s ORDER BY version DESC',
                        (name,))
            return rows(cur)
    finally:
        conn.close()


def create_def(name, datasource_id, source_table, source_column, aggregate,
               filter_json=None):
    """新建定义：同名 version 递增；语义相同（spec_hash 相同）拒绝建版本。"""
    name, filter_json = _validate(name, datasource_id, source_table,
                                  aggregate, filter_json)
    spec = _spec(datasource_id, source_table, source_column, aggregate,
                 filter_json)
    sh = _spec_hash(spec)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT MAX(version) FROM c1_index_info WHERE name=%s',
                        (name,))
            v = (cur.fetchone()[0] or 0) + 1
            cur.execute('SELECT id FROM c1_index_info WHERE name=%s'
                        ' AND spec_hash=%s', (name, sh))
            if cur.fetchone():
                raise Conflict('指标定义未变化，无需新建版本')
            cur.execute(
                'INSERT INTO c1_index_info'
                ' (name,version,datasource_id,source_table,source_column,'
                '  aggregate,filter_json,spec_hash)'
                ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                (name, v, datasource_id, str(source_table or '').strip(),
                 (str(source_column).strip() if source_column else None),
                 aggregate, dump(filter_json), sh))
            did = cur.lastrowid
            conn.commit()
            return did
    finally:
        conn.close()


def delete_def(index_id):
    """有值引用禁删（409）；否则连版本一并删除。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name FROM c1_index_info WHERE id=%s', (index_id,))
            got = cur.fetchone()
            if not got:
                raise NotFound('指标定义不存在')
            name = got[0]
            cur.execute('SELECT COUNT(*) FROM c1_index_value WHERE index_id=%s',
                        (index_id,))
            if cur.fetchone()[0]:
                raise Conflict('该指标已有计算结果，禁止删除')
            # 两步式：MySQL 禁止 DELETE 目标表出现在同表子查询中
            cur.execute('DELETE FROM c1_index_info WHERE name=%s', (name,))
            conn.commit()
    finally:
        conn.close()


def add_value(index_id, index_version, def_hash, value_text, input_rows):
    """写指标值：唯一键防重，重复计算回已有 id（幂等）。"""
    vh = _value_hash(def_hash, input_rows)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_index_info WHERE id=%s AND version=%s',
                        (index_id, index_version))
            if not cur.fetchone():
                raise NotFound('指标定义版本不存在')
            cur.execute(
                'INSERT IGNORE INTO c1_index_value'
                ' (index_id,index_version,value_text,input_rows_json,result_hash)'
                ' VALUES (%s,%s,%s,%s,%s)',
                (index_id, index_version, str(value_text),
                 dump(input_rows), vh))
            if cur.rowcount:
                vid = cur.lastrowid
                conn.commit()
                return vid, vh, True
            cur.execute('SELECT id FROM c1_index_value WHERE index_id=%s'
                        ' AND index_version=%s AND result_hash=%s',
                        (index_id, index_version, vh))
            return cur.fetchone()[0], vh, False
    finally:
        conn.close()


def get_value(value_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + ','.join(_VALUE_COLS) +
                        ' FROM c1_index_value WHERE id=%s', (value_id,))
            got = rows(cur)
        if not got:
            return None
        r = got[0]
        r['input_rows_json'] = unjson(r['input_rows_json'])
        return r
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
            out = rows(cur)
        for r in out:
            r['input_rows_json'] = unjson(r['input_rows_json'])
        return out
    finally:
        conn.close()
