"""store/content_db.py — 抽取结果记录 repo（MySQL）。

所有记录读写以 extract_result_id 为边界。替换某结果记录时只清理该结果的
记录、绑定和回执，不碰同文档其他规则结果。字段/血缘仍按 record_id 关联。
"""
import json
import time
from datetime import datetime

from . import db
from .errors import BadRequest, NotFound
from ..adapter.base import RECORDS_SCHEMA
from .catalog._common import _j, rule_snapshot_parts
from .catalog.results import purge_result_data

_TS = '%Y-%m-%dT%H:%M:%SZ'


def _now():
    return time.strftime(_TS, time.gmtime())


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def record_id_map(extract_result_id):
    """(extract_result_id, record_index) → extract_record.id。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, record_index FROM c1_extract_record'
                        ' WHERE extract_result_id=%s', (extract_result_id,))
            return {(extract_result_id, row[1]): row[0]
                    for row in cur.fetchall()}
    finally:
        conn.close()


def locate_record(record_id):
    """按记录 ID 反查文档与抽取结果，供业务表溯源跳转。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, record_index, doc_id, extract_result_id'
                        ' FROM c1_extract_record WHERE id=%s', (record_id,))
            row = cur.fetchone()
        if not row:
            return None
        return {'record_id': row[0], 'record_index': row[1],
                'doc_id': row[2], 'file_id': row[2],
                'extract_result_id': row[3]}
    finally:
        conn.close()


def _trace_bbox(value):
    if value in (None, ''):
        return None
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode('utf-8')
        box = json.loads(value) if isinstance(value, str) else value
        return box if isinstance(box, list) and len(box) >= 4 else None
    except (TypeError, ValueError):
        return None


def trace_records(record_ids, columns, extract_result_id=None):
    """批量溯源；可选 extract_result_id 将追溯限制在单个结果内。

    目标列到中文字段的映射来自该记录所属 binding，绝不读取文档级旧标量。
    """
    if not isinstance(record_ids, list) or not record_ids:
        raise BadRequest('record_ids 须为非空数组')
    if len(record_ids) > 200:
        raise BadRequest('单次最多追溯 200 条记录')
    ids = []
    for rid in record_ids:
        if isinstance(rid, bool):
            raise BadRequest('record_id 须为整数')
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            raise BadRequest('record_id 须为整数')
        if rid > 0 and rid not in ids:
            ids.append(rid)
    if not ids:
        raise BadRequest('record_ids 无有效整数')
    if not isinstance(columns, list) or not columns or len(columns) > 200:
        raise BadRequest('columns 须为 1～200 个字段名')
    cols = []
    for col in columns:
        if not isinstance(col, str) or not col.strip():
            raise BadRequest('columns 包含非法字段名')
        if col not in cols:
            cols.append(col)

    conn = db.connect()
    try:
        with conn.cursor() as cur:
            ph = ','.join(['%s'] * len(ids))
            sql = (
                'SELECT sr.id, sr.doc_id, sr.extract_result_id, sr.record_index,'
                ' sr.review_state, d.state, b.field_map_json, sl.field_name,'
                ' sl.page, sl.space, sl.cell_bbox, sl.raw_text, sl.table_index,'
                ' sl.table_scope FROM c1_extract_record sr'
                ' JOIN c1_doc d ON d.id=sr.doc_id'
                ' LEFT JOIN c1_load_binding b ON b.extract_result_id=sr.extract_result_id'
                ' LEFT JOIN c1_extract_record_lineage sl ON sl.record_id=sr.id'
                ' WHERE sr.id IN ({})').format(ph)
            args = list(ids)
            if extract_result_id is not None:
                sql += ' AND sr.extract_result_id=%s'
                args.append(extract_result_id)
            sql += ' ORDER BY sr.id, sl.field_name, sl.region_seq'
            cur.execute(sql, args)
            rows = _rows(cur)
    finally:
        conn.close()

    recs, anchors, maps = {}, {}, {}
    for row in rows:
        rid = row['id']
        recs[rid] = row
        maps[rid] = _j(row.get('field_map_json')) or {}
        if row['field_name'] is None:
            continue
        box = _trace_bbox(row['cell_bbox'])
        anchors.setdefault((rid, row['field_name']), []).append({
            'page': row['page'], 'space': row['space'], 'cell_bbox': box,
            'raw_text': row['raw_text'], 'table_index': row['table_index'],
            'table_scope': row['table_scope'],
        })

    out = []
    for rid in ids:
        row = recs.get(rid)
        if row is None:
            out.append({
                'record_id': rid, 'doc_id': None, 'extract_result_id': None,
                'record_index': None, 'doc_state': None, 'review_state': None,
                'field_map': {},
                'fields': {c: {'field': c, 'mapped': False,
                               'traceable': False, 'reason': 'missing_record',
                               'message': '抽取记录不存在', 'anchors': []}
                           for c in cols},
            })
            continue
        doc_missing = row['state'] is None
        field_map = maps.get(rid, {})
        reverse_map = {column: name for name, column in field_map.items()}
        fields = {}
        for col in cols:
            field = reverse_map.get(col, col)
            mapped = col in reverse_map
            regs = anchors.get((rid, field), [])
            valid = [anchor for anchor in regs
                     if anchor['page'] is not None
                     and anchor['space'] in ('source', 'rectified')
                     and anchor['cell_bbox'] is not None]
            if doc_missing:
                state = {'traceable': False, 'reason': 'missing_doc',
                         'message': '来源文档不存在', 'anchors': []}
            elif valid:
                state = {'traceable': True, 'reason': 'ok', 'message': '',
                         'anchors': valid}
            elif regs:
                state = {'traceable': False, 'reason': 'no_bbox',
                         'message': '来源记录缺少有效图像坐标', 'anchors': []}
            else:
                state = {
                    'traceable': False,
                    'reason': 'unmapped' if not mapped else 'no_anchor',
                    'message': '字段未配置源列映射' if not mapped else '来源记录没有该字段的坐标',
                    'anchors': [],
                }
            fields[col] = {'field': field, 'mapped': mapped, **state}
        out.append({
            'record_id': rid, 'doc_id': row['doc_id'],
            'extract_result_id': row['extract_result_id'],
            'record_index': row['record_index'], 'doc_state': row['state'],
            'review_state': row['review_state'], 'field_map': field_map,
            'fields': fields,
        })
    return out


def _field_sources(mapping):
    """抽取定义 → {目标字段: 源列描述}，兼容 v1 column 与 v2 pipeline。"""
    if isinstance(mapping, (str, bytes)):
        try:
            mapping = json.loads(mapping or '{}')
        except (TypeError, ValueError):
            return {}
    mapping = mapping if isinstance(mapping, dict) else {}
    out = {}
    for field in mapping.get('fields') or []:
        target = field.get('target')
        if not target:
            continue
        col = field.get('column') or {}
        for step in field.get('pipeline') or []:
            if not isinstance(step, dict) or step.get('op') != 'cell':
                continue
            source_col = step.get('column') or {}
            if source_col.get('name') is not None:
                col = source_col
                break
            if not col and isinstance(source_col.get('index'), int):
                col = source_col
        if col.get('name') is not None:
            out[target] = str(col['name'])
        elif isinstance(col.get('index'), int):
            out[target] = '第 {} 列'.format(col['index'] + 1)
        else:
            out[target] = ''
    return out


def get_records(extract_result_id):
    """单个抽取结果的 records 信封；规则定义优先取结果快照。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT r.doc_id, r.rule_snapshot_json, d.name, t.name AS rule_name'
                ' FROM c1_extract_result r JOIN c1_doc d ON d.id=r.doc_id'
                ' JOIN c1_extract_rule t ON t.id=r.rule_id WHERE r.id=%s',
                (extract_result_id,))
            frow = cur.fetchone()
            if not frow:
                return None
            cur.execute(
                'SELECT id, record_index, review_state, review_at, values_json,'
                ' original_json, review_reason_json FROM c1_extract_record'
                ' WHERE extract_result_id=%s ORDER BY record_index',
                (extract_result_id,))
            recs = _rows(cur)
            lineage_map = {}
            if recs:
                ph = ','.join(['%s'] * len(recs))
                ids = [rec['id'] for rec in recs]
                cur.execute(
                    'SELECT record_id, field_name, page, table_index, table_scope,'
                    ' space, cell_bbox, raw_text FROM c1_extract_record_lineage'
                    ' WHERE record_id IN ({}) ORDER BY region_seq'.format(ph), ids)
                for row in _rows(cur):
                    lineage_map.setdefault(
                        (row['record_id'], row['field_name']), []).append(row)
            out = []
            for rec in recs:
                values = _j(rec['values_json']) or {}
                lineage = {}
                for key in values:
                    lineage[key] = [{
                        'page': row['page'], 'table_index': row['table_index'],
                        'table_scope': row['table_scope'],
                        'cell_bbox': _j(row['cell_bbox'])
                        if row['cell_bbox'] else None,
                        'space': row['space'], 'raw_text': row['raw_text'],
                    } for row in lineage_map.get((rec['id'], key), [])]
                item = {
                    'index': rec['record_index'], 'values': values,
                    'original': _j(rec['original_json']) or {},
                    'lineage': lineage,
                    'review': {'state': rec['review_state'],
                               'at': rec['review_at'].strftime(_TS)
                               if rec['review_at'] else None},
                }
                if rec.get('review_reason_json'):
                    item['review']['reason'] = _j(rec['review_reason_json'])
                out.append(item)
        snapshot = _j(frow[1]) or {}
        _schema, spec, _ = rule_snapshot_parts(snapshot)
        rule = {'name': snapshot.get('name') or frow[3],
                'field_sources': _field_sources(spec),
                'output_schema': _schema}
        return {'schema': RECORDS_SCHEMA, 'doc_id': frow[0],
                'file_id': frow[0],
                'extract_result_id': extract_result_id, 'rule': rule,
                'records': out,
                'files': [{'doc_id': frow[0], 'file_id': frow[0],
                           'name': frow[2], 'records': out}]}
    finally:
        conn.close()


def purge_records(extract_result_id):
    """清空单结果记录及其绑定/回执，保留结果头供再次写入。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_extract_result WHERE id=%s',
                        (extract_result_id,))
            if not cur.fetchone():
                raise NotFound('抽取结果不存在')
            purge_result_data(cur, extract_result_id)
            conn.commit()
    finally:
        conn.close()


def save_records(extract_result_id, records):
    """原子替换单结果记录；只清当前结果及其 binding/receipt。"""
    if not isinstance(records, list):
        raise BadRequest('records 须为数组')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT doc_id FROM c1_extract_result WHERE id=%s',
                        (extract_result_id,))
            row = cur.fetchone()
            if not row:
                raise NotFound('抽取结果不存在')
            doc_id = row[0]
            purge_result_data(cur, extract_result_id)
            for rec in records:
                values = rec.get('values') or {}
                original = rec.get('original') or {}
                review = rec.get('review') or {}
                at = review.get('at')
                reason = review.get('reason')
                cur.execute(
                    'INSERT INTO c1_extract_record (doc_id, extract_result_id,'
                    ' record_index, review_state, review_at, values_json,'
                    ' original_json, review_reason_json)'
                    ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                    (doc_id, extract_result_id, rec['index'],
                     review.get('state') or 'pending',
                     datetime.strptime(at, _TS) if at else None,
                     json.dumps(values, ensure_ascii=False),
                     json.dumps(original, ensure_ascii=False),
                     json.dumps(reason, ensure_ascii=False) if reason else None))
                rid = cur.lastrowid
                signals = rec.get('signals') or {}
                for key, value in values.items():
                    signal = signals.get(key) or {}
                    cur.execute(
                        'INSERT INTO c1_extract_record_field (record_id,'
                        ' field_name, value_text, original_text, confidence, reason)'
                        ' VALUES (%s,%s,%s,%s,%s,%s)',
                        (rid, key, value, original.get(key, ''),
                         signal.get('confidence'), signal.get('reason')))
                for key, regs in (rec.get('lineage') or {}).items():
                    for seq, geo in enumerate(regs):
                        cur.execute(
                            'INSERT INTO c1_extract_record_lineage (record_id,'
                            ' field_name, region_seq, page, table_index, table_scope,'
                            ' space, cell_bbox, raw_text)'
                            ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                            (rid, key, seq, geo.get('page'), geo.get('table_index'),
                             geo.get('table_scope'), geo.get('space') or 'source',
                             json.dumps(geo['cell_bbox'])
                             if geo.get('cell_bbox') is not None else None,
                             geo.get('raw_text')))
            cur.execute('UPDATE c1_extract_result SET record_count=%s,'
                        ' updated_at=NOW() WHERE id=%s', (len(records), extract_result_id))
        conn.commit()
        return len(records)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def patch_record(extract_result_id, index, values):
    """差量合并单结果记录；original/lineage 不变，未知字段回滚。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id, values_json FROM c1_extract_record'
                ' WHERE extract_result_id=%s AND record_index=%s FOR UPDATE',
                (extract_result_id, index))
            row = cur.fetchone()
            if row is None:
                raise NotFound('记录序号超出范围')
            rid, raw = row
            current = _j(raw) or {}
            unknown = set(values) - set(current)
            if unknown:
                raise BadRequest('未知字段：{}'.format('、'.join(sorted(unknown))))
            current.update(values)
            cur.execute(
                'UPDATE c1_extract_record SET values_json=%s, review_state=%s,'
                ' review_at=%s WHERE id=%s',
                (json.dumps(current, ensure_ascii=False), 'edited',
                 datetime.strptime(_now(), _TS), rid))
            for key, value in values.items():
                cur.execute('UPDATE c1_extract_record_field SET value_text=%s'
                            ' WHERE record_id=%s AND field_name=%s',
                            (value, rid, key))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    doc = get_records(extract_result_id)
    return next((rec for rec in doc['files'][0]['records']
                 if rec['index'] == index), None)


def set_review(extract_result_id, indexes, state):
    """批量确认/拒绝单结果记录，返回更新条数。"""
    if state not in ('confirmed', 'rejected'):
        raise BadRequest('非法校验状态：{}'.format(state))
    if not indexes:
        raise BadRequest('未选择任何记录')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            ph = ','.join(['%s'] * len(indexes))
            cur.execute(
                'UPDATE c1_extract_record SET review_state=%s, review_at=%s'
                ' WHERE extract_result_id=%s AND record_index IN ({})'.format(ph),
                [state, datetime.strptime(_now(), _TS), extract_result_id]
                + list(indexes))
            n = cur.rowcount
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_fields(field=None, q=None, task=None, state=None, limit=200,
                 extract_result_id=None, doc_id=None):
    """跨结果只读查询；task 保留为 doc_id 旧别名。"""
    conn = db.connect()
    try:
        where, args = [], []
        if field:
            where.append('f.field_name=%s')
            args.append(field)
        if q:
            where.append('f.value_text LIKE %s')
            args.append('%{}%'.format(q))
        doc_id = doc_id if doc_id is not None else task
        if doc_id is not None:
            where.append('rec.doc_id=%s')
            args.append(doc_id)
        if extract_result_id is not None:
            where.append('rec.extract_result_id=%s')
            args.append(extract_result_id)
        if state:
            where.append('rec.review_state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute(
                'SELECT rec.doc_id, rec.extract_result_id, d.name AS source_name,'
                ' rec.record_index, rec.review_state, f.field_name, f.value_text'
                ' FROM c1_extract_record_field f'
                ' JOIN c1_extract_record rec ON rec.id=f.record_id'
                ' JOIN c1_doc d ON d.id=rec.doc_id ' + w +
                ' ORDER BY rec.doc_id DESC, rec.extract_result_id,'
                ' rec.record_index LIMIT %s', args + [limit])
            return _rows(cur)
    finally:
        conn.close()


def gate_counts(extract_result_id):
    """单结果门禁四态计数，不拉取记录内容。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT COUNT(id), SUM(review_state=\'pending\'),'
                ' SUM(review_state=\'edited\'), SUM(review_state=\'confirmed\'),'
                ' SUM(review_state=\'rejected\') FROM c1_extract_record'
                ' WHERE extract_result_id=%s', (extract_result_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    return {'records_n': int(row[0] or 0), 'pending': int(row[1] or 0),
            'edited': int(row[2] or 0), 'confirmed': int(row[3] or 0),
            'rejected': int(row[4] or 0)}


def ledger():
    """校验台账：一条抽取结果一行，同文档多规则自然展开。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT r.id AS extract_result_id, r.doc_id, d.name, d.state,'
                ' r.created_at, t.name AS rule_name, COUNT(sr.id) AS records_n,'
                " SUM(sr.review_state='pending') AS pending_n,"
                " SUM(sr.review_state='edited') AS edited_n,"
                " SUM(sr.review_state='confirmed') AS confirmed_n,"
                " SUM(sr.review_state='rejected') AS rejected_n"
                ' FROM c1_extract_result r JOIN c1_doc d ON d.id=r.doc_id'
                ' JOIN c1_extract_rule t ON t.id=r.rule_id'
                ' JOIN c1_extract_record sr ON sr.extract_result_id=r.id'
                ' GROUP BY r.id, r.doc_id, d.name, d.state, r.created_at, t.name'
                ' ORDER BY r.doc_id DESC, r.id DESC')
            out = []
            for row in _rows(cur):
                out.append({
                    'extract_result_id': row['extract_result_id'],
                    'doc_id': row['doc_id'], 'task_id': row['doc_id'],
                    'task_file_id': row['doc_id'], 'name': row['name'],
                    'file_state': row['state'], 'task_state': row['state'],
                    'rule': {'name': row['rule_name']},
                    'records_n': int(row['records_n']),
                    'pending_n': int(row['pending_n'] or 0),
                    'edited_n': int(row['edited_n'] or 0),
                    'confirmed_n': int(row['confirmed_n'] or 0),
                    'rejected_n': int(row['rejected_n'] or 0),
                    'created_at': str(row['created_at']), 'files': [],
                })
            return out
    finally:
        conn.close()
