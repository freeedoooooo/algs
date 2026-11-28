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
_CACHE_TTL = {'tables': 15.0, 'columns': 30.0, 'table_comment': 30.0,
              'schemas': 30.0}


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


def is_business_table(name):
    """c1_ 前缀为平台产品配置/元数据表，不作为业务入库目标。"""
    name = str(name or '').strip()
    return bool(name) and not name.casefold().startswith('c1_')


def list_business_tables(ds):
    return [name for name in list_tables(ds) if is_business_table(name)]


def table_comments(ds, tables):
    """批量读取表注释，同一数据源只建立一次业务库连接。"""
    names = list(dict.fromkeys(tables))
    if not names:
        return {}
    key = _cache_key(ds)
    missing = [name for name in names
               if _cached(key, ('table_comment', name)) is None]
    if missing:
        conn = connect_datasource(ds)
        try:
            placeholders = ','.join(['%s'] * len(missing))
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT table_name,table_comment FROM information_schema.tables'
                    ' WHERE table_schema=%s AND table_name IN ({})'.format(
                        placeholders), [ds['db_name']] + missing)
                found = {row[0]: str(row[1] or '') for row in cur.fetchall()}
        finally:
            conn.close()
        now = time.monotonic()
        for name in missing:
            _INTROSPECT_CACHE[(key, ('table_comment', name))] = (
                now, found.get(name, ''))
    return {name: _cached(key, ('table_comment', name)) or ''
            for name in names}


def table_comment(ds, table):
    return table_comments(ds, [table])[table]


def list_columns(ds, table):
    key, kind = _cache_key(ds), ('columns', table)
    hit = _cached(key, kind)
    if hit is not None:
        return [dict(c) for c in hit]
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT column_name, data_type, column_comment, is_nullable,'
                ' column_default, column_key FROM information_schema.columns'
                ' WHERE table_schema=%s AND table_name=%s'
                ' ORDER BY ordinal_position', (ds['db_name'], table))
            out = [{'name': r[0], 'type': r[1], 'comment': r[2] or '',
                    'nullable': str(r[3]).upper() == 'YES',
                    'default': r[4], 'primary': r[5] == 'PRI'}
                   for r in cur.fetchall()]
    finally:
        conn.close()
    _INTROSPECT_CACHE[(key, kind)] = (time.monotonic(), out)
    return [dict(c) for c in out]


def list_table_schemas(ds, tables=None):
    """批量读取现有表结构，供中文语义推荐/映射使用。"""
    names = (list_business_tables(ds) if tables is None else
             [str(name) for name in tables if is_business_table(name)])
    if not names:
        return []
    key = _cache_key(ds)
    cache_kind = ('schemas', tuple(sorted(names)))
    hit = _cached(key, cache_kind)
    if hit is not None:
        return [dict(s, columns=[dict(c) for c in s.get('columns') or []],
                     indexes=[dict(i, columns=list(i.get('columns') or []))
                              for i in s.get('indexes') or []])
                for s in hit]
    placeholders = ','.join(['%s'] * len(names))
    args = [ds['db_name']] + names
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT table_name, table_comment FROM information_schema.tables'
                ' WHERE table_schema=%s AND table_type=\'BASE TABLE\''
                ' AND table_name IN ({}) ORDER BY table_name'.format(
                    placeholders), args)
            comments = {r[0]: str(r[1] or '') for r in cur.fetchall()}
            cur.execute(
                'SELECT table_name, column_name, data_type, column_comment,'
                ' is_nullable, column_default, column_key'
                ' FROM information_schema.columns WHERE table_schema=%s'
                ' AND table_name IN ({})'
                ' ORDER BY table_name, ordinal_position'.format(placeholders),
                args)
            columns = {}
            for row in cur.fetchall():
                columns.setdefault(row[0], []).append({
                    'name': row[1], 'type': row[2], 'comment': row[3] or '',
                    'nullable': str(row[4]).upper() == 'YES',
                    'default': row[5], 'primary': row[6] == 'PRI',
                    'unique': False})
            cur.execute(
                'SELECT table_name, index_name, non_unique, column_name'
                ' FROM information_schema.statistics WHERE table_schema=%s'
                ' AND table_name IN ({})'
                ' ORDER BY table_name, index_name, seq_in_index'.format(
                    placeholders), args)
            indexes = {}
            for table, index_name, non_unique, column_name in cur.fetchall():
                item = indexes.setdefault(
                    (table, index_name), {'name': index_name,
                                          'unique': not int(non_unique),
                                          'columns': []})
                item['columns'].append(column_name)
            for (table, _index_name), item in indexes.items():
                if item['unique']:
                    for column in item['columns']:
                        for meta in columns.get(table) or []:
                            if meta['name'] == column:
                                meta['unique'] = True
    finally:
        conn.close()
    out = [{'name': name, 'datasource_id': ds.get('id'),
            'comment': comments.get(name, ''),
            'columns': columns.get(name) or [],
            'indexes': [item for (table, _name), item in indexes.items()
                        if table == name]}
           for name in names if name in comments]
    _INTROSPECT_CACHE[(key, cache_kind)] = (time.monotonic(), out)
    return [dict(s, columns=[dict(c) for c in s.get('columns') or []],
                 indexes=[dict(i, columns=list(i.get('columns') or []))
                          for i in s.get('indexes') or []])
            for s in out]


def validate_fields(fields, field_map, write_mode='insert', business_keys=None,
                   columns=None):
    """校验 binding 的部分字段映射。

    field_map={中文字段: 目标列}，只要求是抽取字段的子集；额外抽取字段
    自动忽略。columns=None 跳过目标列存在性检查。
    """
    if write_mode not in ('insert', 'upsert', 'update'):
        raise BadRequest('非法写入方式：{}'.format(write_mode))
    if not isinstance(field_map, dict) or not field_map:
        raise BadRequest('字段映射不能为空')
    cm = {}
    for source, target in field_map.items():
        if not isinstance(source, str) or not source.strip():
            raise BadRequest('抽取字段名不能为空')
        if not isinstance(target, str) or not target.strip():
            raise BadRequest('字段「{}」的目标列名为空'.format(source))
        cm[source] = target
    if len(set(cm.values())) != len(cm):
        raise BadRequest('多个字段不能指向同一目标列')
    extra = set(cm) - set(fields or [])
    if extra:
        raise BadRequest('未知抽取字段：{}'.format('、'.join(sorted(extra))))
    if business_keys is None:
        business_keys = []
    if not isinstance(business_keys, (list, tuple)):
        raise BadRequest('业务键须为目标列数组')
    raw_keys = list(business_keys)
    if any(not isinstance(key, str) or not key for key in raw_keys):
        raise BadRequest('业务键须为目标列数组')
    bk = list(dict.fromkeys(raw_keys))
    unmapped_keys = set(bk) - set(cm.values())
    if unmapped_keys:
        raise BadRequest('业务键不在字段映射中：{}'.format(
            '、'.join(sorted(unmapped_keys))))
    if write_mode in ('upsert', 'update') and not bk:
        raise BadRequest('{} 方式须至少选择一列作为去重依据'.format(write_mode))
    validate_trace_columns(list(cm.values()))
    if columns is not None:
        cols = set(columns)
        bad = set(cm.values()) - cols
        if bad:
            raise BadRequest('目标列不存在：{}'.format('、'.join(sorted(bad))))
    return True


def binding_to_map(binding):
    """binding → (column_map, business_keys)；写模式与业务键来自 binding。"""
    binding = binding or {}
    return dict(binding.get('field_map_json') or {}), \
        list(binding.get('business_keys_json') or [])


TRACE_COLS = ('file_id', 'record_id')


def validate_trace_columns(targets):
    """溯源列由平台写入，任何抽取字段（含业务键）都不得占用。"""
    if isinstance(targets, dict):
        targets = targets.values()
    used = [target for target in targets if target in TRACE_COLS]
    if used:
        raise BadRequest('抽取字段不能映射到溯源列：{}'.format(
            '、'.join(sorted(set(used)))))


def preflight(ds, target_table, field_map, write_mode, fields,
              business_keys=None):
    """预检现有业务表、溯源列和 binding 的部分映射，不自动建表/改表。"""
    if not is_business_table(target_table):
        raise BadRequest('只能选择现有业务表，不能写入平台 c1_ 表')
    cols = [c['name'] for c in list_columns(ds, target_table)]
    if not cols:
        raise BadRequest('目标表不存在或无列：{}'.format(target_table))
    missing = [c for c in TRACE_COLS if c not in cols]
    if missing:
        raise BadRequest('目标表缺少溯源列：{}（须由业务系统预建，平台不自动建表/改表）'.format(
            '、'.join(missing)))
    validate_fields(fields, field_map, write_mode, business_keys, cols)
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
    if write_mode not in ('insert', 'upsert', 'update'):
        raise BadRequest('非法写入方式：{}'.format(write_mode))
    if not is_business_table(table):
        raise BadRequest('只能写入现有业务表，不能写入平台 c1_ 表')
    validate_fields(list(column_map or {}), column_map, write_mode, business_key)
    validate_trace_columns(column_map)
    mapped = {column_map[k]: v for k, v in values.items() if k in column_map}
    if not mapped:
        raise LoadRecordError('没有可写入的抽取字段')
    mapped.update(extra_values or {})
    if write_mode == 'insert':
        _insert(cur, table, mapped)
        return 'insert', str(cur.lastrowid)
    bk = list(business_key or [])
    if not bk:
        raise BadRequest('{} 方式须由 binding 提供业务键'.format(write_mode))
    missing = [key for key in bk if key not in mapped or mapped[key] in (None, '')]
    if missing:
        raise LoadRecordError('业务键缺少映射值：{}'.format('、'.join(missing)))
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
    if not is_business_table(table):
        raise BadRequest('只能查询现有业务表，不能查询平台 c1_ 表')
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