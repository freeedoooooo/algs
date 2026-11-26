"""
store/loader.py — 目标业务库写入（）。

平台表 SQL 归 catalog；本模块只管目标库：introspection（information_schema
只读）、预检、应用层 upsert 写入。目标库连接来自数据源行显式参数
（connect_direct）——绝不把平台表建进人家库。
数据源密码明文存库（2026-11-21 裁决），但日志永不打印/回显。

纯函数（apply_transform/review_gate/validate_fields/write_record）无 DB 依赖，
单测见 test_load_rules.py。值一律参数化；标识符经 _ident 反引号转义＋
预检时 information_schema 存在性白名单双重防御。
"""
import json
import time

from . import db
from .errors import BadRequest


class LoadRecordError(Exception):
    """单条记录写入失败（隔离 stage=load 的原因），非 HTTP 错误。"""

    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg


def _ident(name):
    return '`{}`'.format(str(name).replace('`', '``'))


def connect_datasource(ds):
    """数据源行 → 目标库连接（显式参数直连）。连接失败原样上抛→503。"""
    return db.connect_direct({
        'host': ds['host'], 'port': ds['port'], 'user': ds['user'],
        'password': ds['password'], 'database': ds['db_name']})


_INTROSPECT_CACHE = {}
_CACHE_TTL = {'tables': 15.0, 'columns': 30.0, 'table_comment': 30.0}


def _cache_key(ds):
    return (ds.get('id'), ds.get('host'), ds.get('port'),
            ds.get('user'), ds.get('db_name'))


def _cached(key, kind):
    ttl_key = kind[0] if isinstance(kind, tuple) else kind
    hit = _INTROSPECT_CACHE.get((key, kind))
    if hit and time.monotonic() - hit[0] < _CACHE_TTL[ttl_key]:
        return hit[1]
    return None


def clear_introspection_cache():
    """业务库连接参数变更时调用，避免短暂沿用旧表结构。"""
    _INTROSPECT_CACHE.clear()


def list_tables(ds):
    key, kind = _cache_key(ds), 'tables'
    hit = _cached(key, kind)
    if hit is not None:
        return list(hit)
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT table_name FROM information_schema.tables'
                " WHERE table_schema=%s AND table_type='BASE TABLE'"
                ' ORDER BY table_name', (ds['db_name'],))
            out = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    _INTROSPECT_CACHE[(key, kind)] = (time.monotonic(), out)
    return list(out)


def table_comment(ds, table):
    key, kind = _cache_key(ds), ('table_comment', table)
    hit = _cached(key, kind)
    if hit is not None:
        return hit
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT table_comment FROM information_schema.tables'
                ' WHERE table_schema=%s AND table_name=%s',
                (ds['db_name'], table))
            row = cur.fetchone()
            out = str(row[0] or '') if row else ''
    finally:
        conn.close()
    _INTROSPECT_CACHE[(key, kind)] = (time.monotonic(), out)
    return out


def list_columns(ds, table):
    key, kind = _cache_key(ds), ('columns', table)
    hit = _cached(key, kind)
    if hit is not None:
        return [dict(c) for c in hit]
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT column_name, data_type FROM information_schema.columns'
                ' WHERE table_schema=%s AND table_name=%s'
                ' ORDER BY ordinal_position', (ds['db_name'], table))
            out = [{'name': r[0], 'type': r[1]} for r in cur.fetchall()]
    finally:
        conn.close()
    _INTROSPECT_CACHE[(key, kind)] = (time.monotonic(), out)
    return [dict(c) for c in out]


def validate_fields(fields, field_rows, write_mode='upsert', columns=None):
    """映射契约校验（建映射/编辑/预检共用）。columns=None 跳过存在性检查。
    field_rows=[{rule_field,target_column,is_business_key}]。"""
    if write_mode not in ('insert', 'upsert', 'update'):
        raise BadRequest('非法写入方式：{}'.format(write_mode))
    if not isinstance(field_rows, list) or not field_rows:
        raise BadRequest('字段对齐行不能为空')
    cm, seen_f, seen_c = {}, set(), set()
    for f in field_rows:
        if not isinstance(f, dict):
            raise BadRequest('字段对齐配置格式不正确')
        tf, tc = f.get('rule_field'), f.get('target_column')
        if not isinstance(tf, str) or not tf.strip():
            raise BadRequest('抽取规则字段名不能为空')
        if not isinstance(tc, str) or not tc.strip():
            raise BadRequest('字段「{}」的目标列名为空'.format(tf))
        if tf in seen_f:
            raise BadRequest('抽取规则字段重复：{}'.format(tf))
        if tc in seen_c:
            raise BadRequest('多个字段指向同一目标列')
        seen_f.add(tf)
        seen_c.add(tc)
        cm[tf] = tc
    missing = [f for f in fields if f not in cm]
    if missing:
        raise BadRequest('以下字段尚未对齐目标列：{}'.format('、'.join(missing)))
    extra = set(cm) - set(fields)
    if extra:
        raise BadRequest('未知字段：{}'.format('、'.join(sorted(extra))))
    bk = [f['target_column'] for f in field_rows if f.get('is_business_key')]
    if write_mode in ('upsert', 'update') and not bk:
        raise BadRequest('{} 方式须至少选择一列作为去重依据'.format(write_mode))
    if columns is not None:
        cols = set(columns)
        bad = [c for c in list(cm.values()) + bk if c not in cols]
        if bad:
            raise BadRequest('目标列不存在：{}'.format('、'.join(sorted(set(bad)))))
    return True


def fields_to_map(field_rows):
    """字段行 → (column_map, business_key)，供 write_record 消费。"""
    cm = {f['rule_field']: f['target_column'] for f in field_rows}
    bk = [f['target_column'] for f in field_rows if f.get('is_business_key')]
    return cm, bk


TRACE_COLS = ('file_id', 'record_id')


def validate_trace_columns(cols, field_rows=None):
    """溯源列预检：目标表须预建 file_id/record_id 两列
    （平台禁止自动 DDL）；规则字段不得占用这些列名。"""
    missing = [c for c in TRACE_COLS if c not in cols]
    if missing:
        raise BadRequest('目标表缺少溯源列：{}（须由业务系统预建，平台不自动建表/改表）'.format(
            '、'.join(missing)))
    if field_rows:
        used = [f.get('target_column') for f in field_rows
                if f.get('target_column') in TRACE_COLS]
        if used:
            raise BadRequest('规则字段不能映射到溯源列：{}'.format(
                '、'.join(sorted(set(used)))))


def preflight(ds, target_table, field_rows, write_mode, fields):
    """预检：目标表/列存在＋溯源列＋映射覆盖（上传预登记与点入库各跑一次）。
    连接级失败（pymysql/OSError）原样上抛→503；配置问题→400。"""
    cols = [c['name'] for c in list_columns(ds, target_table)]
    if not cols:
        raise BadRequest('目标表不存在或无列：{}'.format(target_table))
    validate_trace_columns(cols, field_rows)
    validate_fields(fields, field_rows, write_mode, cols)
    return cols


def apply_transform(values, transform_json):
    """入库时消费 transform（暂存 values 永不改）：返回 (副本, 错误列表)。
    规则按序；number 失败→错误条目（值保留原样，调用方隔离跳过）。
    仅存量 v1 规则仍走此路径；新规则的转换已下沉到抽取阶段。"""
    out = dict(values)
    errors = []
    for rule in (transform_json or {}).get('fields') or []:
        target = rule.get('target')
        if target not in out:
            continue
        v = out[target]
        for name in rule.get('apply') or []:
            if name == 'trim':
                v = str(v).strip()
            elif name == 'number':
                try:
                    v = float(''.join(str(v).split()).replace(',', ''))
                except (TypeError, ValueError):
                    errors.append({'field': target, 'value': out[target],
                                   'reason': '无法转换为数值：{}'.format(out[target])})
                    break
            else:
                errors.append({'field': target, 'value': out[target],
                               'reason': '未知规则：{}'.format(name)})
                break
        else:
            out[target] = v
    return out, errors


def review_gate(records):
    """门禁计数：仅 confirmed 放行，pending/edited/rejected 任一非零即阻止。"""
    counts = {'pending': 0, 'edited': 0, 'confirmed': 0, 'rejected': 0}
    for r in records:
        state = (r.get('review') or {}).get('state') or 'pending'
        counts[state if state in counts else 'pending'] += 1
    return counts


def _insert(cur, table, mapped):
    cols = list(mapped)
    cur.execute(
        'INSERT INTO {} ({}) VALUES ({})'.format(
            _ident(table), ','.join(_ident(c) for c in cols),
            ','.join(['%s'] * len(cols))),
        [mapped[c] for c in cols])
    return 'insert'


def write_record(cur, table, column_map, values, write_mode, business_key,
                 extra_values=None):
    """单条写入→(action, target_pk)。应用层 upsert：SELECT 业务键→
    UPDATE/INSERT，不依赖目标表唯一索引（单任务串行无竞态）。
    update 目标行不存在→LoadRecordError（调用方隔离）。
    extra_values＝溯源列（file_id/record_id），非业务键，
    upsert 时随其余非键列一起覆盖为最近写入者。"""
    mapped = {column_map[k]: v for k, v in values.items() if k in column_map}
    mapped.update(extra_values or {})
    if write_mode == 'insert':
        _insert(cur, table, mapped)
        return 'insert', str(cur.lastrowid)
    bk = list(business_key or [])
    where = ' AND '.join('{}=%s'.format(_ident(c)) for c in bk)
    bvals = [mapped[c] for c in bk]
    cur.execute('SELECT 1 FROM {} WHERE {} LIMIT 1'.format(
        _ident(table), where), bvals)
    pk = json.dumps(bvals, ensure_ascii=False)
    if cur.fetchone() is not None:
        sets = {c: v for c, v in mapped.items() if c not in bk}
        if sets:
            cur.execute(
                'UPDATE {} SET {} WHERE {}'.format(
                    _ident(table),
                    ','.join('{}=%s'.format(_ident(c)) for c in sets), where),
                list(sets.values()) + bvals)
        return 'update', pk
    if write_mode == 'update':
        raise LoadRecordError('目标行不存在（去重依据：{}）'.format(pk))
    _insert(cur, table, mapped)
    return 'insert', pk


def query_rows(ds, table, page=1, per_page=100, trace_cols=None, file_id=None):
    """只读分页查询目标业务表（数据看板）。

    表名经 information_schema 白名单校验，列名经 list_columns 白名单＋
    _ident 转义，值/分页参数一律参数化；绝不拼接用户输入进 SQL 标识符。
    trace_cols＝溯源列白名单（默认 TRACE_COLS），查询时优先置顶。
    file_id＝按平台溯源列 file_id 精确过滤（值参数化），避免多文件数据混杂。
    返回 {'items':[dict], 'total':int, 'columns':[str], 'page', 'per_page'}。
    """
    if table not in list_tables(ds):
        raise BadRequest('表不在白名单内：{}'.format(table))
    cols = [c['name'] for c in list_columns(ds, table)]
    if not cols:
        raise BadRequest('目标表不存在或无列：{}'.format(table))
    trace = [c for c in (trace_cols or TRACE_COLS) if c in cols]
    ordered = trace + [c for c in cols if c not in trace]
    where, args = '', []
    if file_id not in (None, ''):
        if 'file_id' not in cols:
            raise BadRequest('该业务表没有 file_id 列，无法按资料ID筛选')
        try:
            fid = int(file_id)
        except (TypeError, ValueError):
            raise BadRequest('资料ID须为整数')
        where = ' WHERE {}=%s'.format(_ident('file_id'))
        args = [fid]
    per_page = max(1, min(200, int(per_page or 100)))
    page = max(1, int(page or 1))
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM {}{}'.format(
                _ident(table), where), args)
            total = cur.fetchone()[0]
            sel = ','.join(_ident(c) for c in ordered)
            cur.execute(
                'SELECT {} FROM {}{} LIMIT %s OFFSET %s'.format(
                    sel, _ident(table), where),
                args + [per_page, (page - 1) * per_page])
            rows = cur.fetchall()
        items = [dict(zip(ordered, r)) for r in rows]
        for it in items:
            for k, v in list(it.items()):
                if hasattr(v, 'isoformat'):
                    it[k] = v.isoformat(sep=' ')
                elif isinstance(v, bytes):
                    it[k] = '<binary {} bytes>'.format(len(v))
        return {'items': items, 'total': total, 'columns': ordered,
                'page': page, 'per_page': per_page, 'file_id': args[0] if args else None,
                'has_trace': bool(trace)}
    finally:
        conn.close()