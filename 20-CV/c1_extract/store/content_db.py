"""
store/content_db.py — 内容 repo 的 DB 实现（design-task-schema.md）。

records 唯一事实源＝staging 三表（自动快照已退役，export_artifacts.py 按需导出）。
键＝task_id（get/patch）与 task_file_id（save 按 doc 内登记）；DB 必选，错误上抛。
无外键约束：重跑覆盖时 field/lineage 子表由本模块显式先删（应用层级联，设计稿 §2）。
"""
import json
import time
from datetime import datetime

from . import db
from ..adapter.base import RECORDS_SCHEMA

_TS = '%Y-%m-%dT%H:%M:%SZ'


def _now():
    return time.strftime(_TS, time.gmtime())


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _task_files(cur, task_id):
    cur.execute(
        'SELECT tf.id, tf.task_id, tf.file_id,'
        ' s.name AS source_name'
        ' FROM extract_task_file tf'
        ' JOIN extract_file s ON s.id=tf.file_id'
        ' WHERE tf.task_id=%s ORDER BY tf.id',
        (task_id,))
    return _rows(cur)


def get_records(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            tfs = _task_files(cur, task_id)
            if not tfs:
                return None
            files = []
            for tf in tfs:
                cur.execute(
                    'SELECT id, record_index, review_state, review_at,'
                    ' values_json, original_json'
                    ' FROM extract_staging_record WHERE task_file_id=%s'
                    ' ORDER BY record_index', (tf['id'],))
                recs = _rows(cur)
                fmap, lmap = {}, {}
                if recs:
                    ph = ','.join(['%s'] * len(recs))
                    ids = [r['id'] for r in recs]
                    cur.execute(
                        'SELECT record_id, field_name, value_text'
                        ' FROM extract_staging_field WHERE record_id IN ({})'
                        .format(ph), ids)
                    for row in _rows(cur):
                        fmap.setdefault(row['record_id'], {})[
                            row['field_name']] = row['value_text']
                    cur.execute(
                        'SELECT record_id, field_name, page, table_index,'
                        ' table_scope, space, cell_bbox, raw_text'
                        ' FROM extract_staging_lineage WHERE record_id IN ({})'
                        ' ORDER BY region_seq'.format(ph), ids)
                    for row in _rows(cur):
                        lmap.setdefault(
                            (row['record_id'], row['field_name']), []).append(row)
                out = []
                for r in recs:
                    values = json.loads(r['values_json'])
                    lineage = {}
                    for k in values:
                        lineage[k] = [{
                            'page': g['page'], 'table_index': g['table_index'],
                            'table_scope': g['table_scope'],
                            'cell_bbox': json.loads(g['cell_bbox'])
                            if g['cell_bbox'] else None,
                            'space': g['space'], 'raw_text': g['raw_text'],
                        } for g in lmap.get((r['id'], k), [])]
                    out.append({
                        'index': r['record_index'], 'values': values,
                        'original': json.loads(r['original_json']),
                        'lineage': lineage,
                        'review': {'state': r['review_state'],
                                   'at': r['review_at'].strftime(_TS)
                                   if r['review_at'] else None},
                    })
                files.append({
                    'task_file_id': tf['id'],
                    'file_id': tf['file_id'],
                    'name': tf['source_name'],
                    'records': out,
                })
            cur.execute(
                'SELECT t.name, tv.version FROM extract_task r'
                ' JOIN extract_template_version tv'
                ' ON tv.id=r.template_version_id'
                ' JOIN extract_template t ON t.id=tv.template_id'
                ' WHERE r.id=%s', (tfs[0]['task_id'],))
            trow = cur.fetchone()
            template = ({'name': trow[0], 'version': trow[1]} if trow
                        else {'name': '原始透传', 'version': 1})
            return {'schema': RECORDS_SCHEMA, 'task_id': tfs[0]['task_id'],
                    'template': template, 'files': files}
    finally:
        conn.close()


def save_records(doc):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for f in doc.get('files') or []:
                tf_id = f.get('task_file_id')
                if not tf_id:
                    raise ValueError(
                        'task_file_id 缺失：须先目录登记成功')
                # 应用层级联：无 FK，重跑覆盖须显式先清 field/lineage 子表
                cur.execute(
                    'DELETE FROM extract_staging_field WHERE record_id IN'
                    ' (SELECT id FROM extract_staging_record'
                    '   WHERE task_file_id=%s)', (tf_id,))
                cur.execute(
                    'DELETE FROM extract_staging_lineage WHERE record_id IN'
                    ' (SELECT id FROM extract_staging_record'
                    '   WHERE task_file_id=%s)', (tf_id,))
                cur.execute(
                    'DELETE FROM extract_staging_record WHERE task_file_id=%s',
                    (tf_id,))
                for rec in f.get('records') or []:
                    values = rec.get('values') or {}
                    original = rec.get('original') or {}
                    review = rec.get('review') or {}
                    at = review.get('at')
                    cur.execute(
                        'INSERT INTO extract_staging_record (task_file_id,'
                        ' record_index, review_state, review_at, values_json,'
                        ' original_json) VALUES (%s,%s,%s,%s,%s,%s)',
                        (tf_id, rec['index'], review.get('state') or 'pending',
                         datetime.strptime(at, _TS) if at else None,
                         json.dumps(values, ensure_ascii=False),
                         json.dumps(original, ensure_ascii=False)))
                    rid = cur.lastrowid
                    for k, v in values.items():
                        cur.execute(
                            'INSERT INTO extract_staging_field (record_id,'
                            ' field_name, value_text, original_text)'
                            ' VALUES (%s,%s,%s,%s)',
                            (rid, k, v, original.get(k, '')))
                    for k, regs in (rec.get('lineage') or {}).items():
                        for seq, g in enumerate(regs):
                            cur.execute(
                                'INSERT INTO extract_staging_lineage'
                                ' (record_id, field_name, region_seq, page,'
                                ' table_index, table_scope, space, cell_bbox,'
                                ' raw_text) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                                (rid, k, seq, g.get('page'),
                                 g.get('table_index'), g.get('table_scope'),
                                 g.get('space') or 'source',
                                 json.dumps(g['cell_bbox'])
                                 if g.get('cell_bbox') is not None else None,
                                 g.get('raw_text')))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def patch_record(task_id, file_index, index, values):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            tfs = _task_files(cur, task_id)
            if file_index >= len(tfs):
                return False, '文件下标越界'
            cur.execute(
                'SELECT id, values_json FROM extract_staging_record'
                ' WHERE task_file_id=%s AND record_index=%s FOR UPDATE',
                (tfs[file_index]['id'], index))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return False, '记录下标越界'
            rid, vj = row
            vals = json.loads(vj)
            unknown = set(values) - set(vals)
            if unknown:
                conn.rollback()
                return False, '未知字段：{}'.format('、'.join(sorted(unknown)))
            vals.update(values)
            cur.execute(
                'UPDATE extract_staging_record SET values_json=%s,'
                ' review_state=%s, review_at=%s WHERE id=%s',
                (json.dumps(vals, ensure_ascii=False), 'edited',
                 datetime.strptime(_now(), _TS), rid))
            for k, v in values.items():
                cur.execute(
                    'UPDATE extract_staging_field SET value_text=%s'
                    ' WHERE record_id=%s AND field_name=%s', (v, rid, k))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    doc = get_records(task_id)
    rec = next((r for r in doc['files'][file_index]['records']
                if r['index'] == index), None)
    return True, rec


def set_review(task_id, file_index, indexes, state):
    """批量确认/拒绝（P1 校验台）：单事务置 review_state/review_at。

    state 仅 confirmed/rejected；original/lineage 不动。
    返回 (ok, 更新条数或错误信息)。
    """
    if state not in ('confirmed', 'rejected'):
        return False, '非法校验状态：{}'.format(state)
    if not indexes:
        return False, '未选择记录'
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            tfs = _task_files(cur, task_id)
            if file_index >= len(tfs):
                return False, '文件下标越界'
            ph = ','.join(['%s'] * len(indexes))
            cur.execute(
                'UPDATE extract_staging_record SET review_state=%s,'
                ' review_at=%s WHERE task_file_id=%s'
                ' AND record_index IN ({})'.format(ph),
                [state, datetime.strptime(_now(), _TS),
                 tfs[file_index]['id']] + list(indexes))
            n = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return True, n


def query_fields(field=None, q=None, task=None, state=None, limit=200):
    """跨任务暂存查询（只读）：field 表投影 + 目录 join，普通 SQL 普通索引。"""
    conn = db.connect()
    try:
        where, args = [], []
        if field:
            where.append('f.field_name=%s')
            args.append(field)
        if q:
            where.append('f.value_text LIKE %s')
            args.append('%{}%'.format(q))
        if task:
            where.append('r.id=%s')
            args.append(task)
        if state:
            where.append('rec.review_state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute(
                'SELECT r.id AS task_id, tf.id AS task_file_id,'
                ' s.name AS source_name, rec.record_index,'
                ' rec.review_state, f.field_name, f.value_text'
                ' FROM extract_staging_field f'
                ' JOIN extract_staging_record rec ON rec.id=f.record_id'
                ' JOIN extract_task_file tf ON tf.id=rec.task_file_id'
                ' JOIN extract_task r ON r.id=tf.task_id'
                ' JOIN extract_file s ON s.id=tf.file_id {}'
                ' ORDER BY r.id DESC, rec.record_index LIMIT %s'
                .format(w), args + [limit])
            return _rows(cur)
    finally:
        conn.close()