"""
store/loader.py — 目标业务库写入（design-p2-load.md ＋ design-p2b-datasource.md）。

平台表 SQL 归 catalog；本模块只管目标库：introspection（information_schema
只读）、预检、应用层 upsert 写入。目标库连接来自数据源行显式参数
（connect_direct）——绝不把平台表建进人家库。
数据源密码明文存库（2026-11-21 裁决），但日志永不打印/回显。

纯函数（apply_transform/review_gate/validate_fields/write_record）无 DB 依赖，
单测见 test_load_rules.py。值一律参数化；标识符经 _ident 反引号转义＋
预检时 information_schema 存在性白名单双重防御。
"""
import json

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


def list_tables(ds):
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT table_name FROM information_schema.tables'
                " WHERE table_schema=%s AND table_type='BASE TABLE'"
                ' ORDER BY table_name', (ds['db_name'],))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def list_columns(ds, table):
    conn = connect_datasource(ds)
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT column_name, data_type FROM information_schema.columns'
                ' WHERE table_schema=%s AND table_name=%s'
                ' ORDER BY ordinal_position', (ds['db_name'], table))
            return [{'name': r[0], 'type': r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def validate_fields(fields, field_rows, write_mode='upsert', columns=None):
    """映射契约校验（建映射/编辑/预检共用）。columns=None 跳过存在性检查。
    field_rows=[{template_field,target_column,is_business_key}]。"""
    if write_mode not in ('insert', 'upsert', 'update'):
        raise BadRequest('非法写入方式：{}'.format(write_mode))
    if not isinstance(field_rows, list) or not field_rows:
        raise BadRequest('字段对齐行不能为空')
    cm, seen_f, seen_c = {}, set(), set()
    for f in field_rows:
        if not isinstance(f, dict):
            raise BadRequest('字段对齐配置格式不正确')
        tf, tc = f.get('template_field'), f.get('target_column')
        if not isinstance(tf, str) or not tf.strip():
            raise BadRequest('模板字段名不能为空')
        if not isinstance(tc, str) or not tc.strip():
            raise BadRequest('字段「{}」的目标列名为空'.format(tf))
        if tf in seen_f:
            raise BadRequest('模板字段重复：{}'.format(tf))
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
    cm = {f['template_field']: f['target_column'] for f in field_rows}
    bk = [f['target_column'] for f in field_rows if f.get('is_business_key')]
    return cm, bk


def preflight(ds, target_table, field_rows, write_mode, fields):
    """预检：目标表/列存在＋映射覆盖（上传预登记与点入库各跑一次）。
    连接级失败（pymysql/OSError）原样上抛→503；配置问题→400。"""
    cols = [c['name'] for c in list_columns(ds, target_table)]
    if not cols:
        raise BadRequest('目标表不存在或无列：{}'.format(target_table))
    validate_fields(fields, field_rows, write_mode, cols)
    return cols


def apply_transform(values, transform_json):
    """入库时消费 transform（暂存 values 永不改）：返回 (副本, 错误列表)。
    规则按序；number 失败→错误条目（值保留原样，调用方隔离跳过）。"""
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


def write_record(cur, table, column_map, values, write_mode, business_key):
    """单条写入→(action, target_pk)。应用层 upsert：SELECT 业务键→
    UPDATE/INSERT，不依赖目标表唯一索引（单任务串行无竞态）。
    update 目标行不存在→LoadRecordError（调用方隔离）。"""
    mapped = {column_map[k]: v for k, v in values.items() if k in column_map}
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