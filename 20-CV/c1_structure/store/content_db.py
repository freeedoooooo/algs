"""
store/content_db.py — 内容 repo 的 DB 实现。

records 唯一事实源＝staging 三表（自动快照已退役，export_artifacts.py 按需导出）。
键＝task_id（get/patch）与 task_file_id（save 按 doc 内登记）；DB 必选，错误上抛。
无外键约束：重跑覆盖时 field/lineage 子表由本模块显式先删（应用层级联，设计稿 §2）。
"""
import json
import time
from datetime import datetime

from . import db
from .errors import BadRequest, NotFound
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
        ' FROM c1_task_file tf'
        ' JOIN c1_doc_file s ON s.id=tf.file_id'
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
                    ' FROM c1_staging_record WHERE task_file_id=%s'
                    ' ORDER BY record_index', (tf['id'],))
                recs = _rows(cur)
                fmap, lmap = {}, {}
                if recs:
                    ph = ','.join(['%s'] * len(recs))
                    ids = [r['id'] for r in recs]
                    cur.execute(
                        'SELECT record_id, field_name, value_text'
                        ' FROM c1_staging_field WHERE record_id IN ({})'
                        .format(ph), ids)
                    for row in _rows(cur):
                        fmap.setdefault(row['record_id'], {})[
                            row['field_name']] = row['value_text']
                    cur.execute(
                        'SELECT record_id, field_name, page, table_index,'
                        ' table_scope, space, cell_bbox, raw_text'
                        ' FROM c1_staging_lineage WHERE record_id IN ({})'
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
                'SELECT t.name, tv.version, tv.mapping_json FROM c1_task r'
                ' JOIN c1_extract_rule_version tv'
                ' ON tv.id=r.rule_version_id'
                ' JOIN c1_extract_rule t ON t.id=tv.rule_id'
                ' WHERE r.id=%s', (tfs[0]['task_id'],))
            trow = cur.fetchone()
            rule = ({'name': trow[0], 'version': trow[1],
                     'field_sources': _field_sources(trow[2])} if trow
                        else {'name': '原始透传', 'version': 1,
                              'field_sources': {}})
            return {'schema': RECORDS_SCHEMA, 'task_id': tfs[0]['task_id'],
                    'rule': rule, 'files': files}
    finally:
        conn.close()


def _field_sources(mapping_json):
    """映射 JSON → {目标字段: 源列描述}，供校验台表头显示「目标 ← 源列」。
    列选择器 name 直接用原文；index 用「第N列」；未配置列＝未映射（空描述）。"""
    try:
        mapping = json.loads(mapping_json or '{}')
    except (TypeError, ValueError):
        return {}
    out = {}
    for f in mapping.get('fields') or []:
        target = f.get('target')
        if not target:
            continue
        col = f.get('column') or {}
        if col.get('name') is not None:
            out[target] = str(col['name'])
        elif isinstance(col.get('index'), int):
            out[target] = '第 {} 列'.format(col['index'] + 1)
        else:
            out[target] = ''
    return out


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
                    'DELETE FROM c1_staging_field WHERE record_id IN'
                    ' (SELECT id FROM c1_staging_record'
                    '   WHERE task_file_id=%s)', (tf_id,))
                cur.execute(
                    'DELETE FROM c1_staging_lineage WHERE record_id IN'
                    ' (SELECT id FROM c1_staging_record'
                    '   WHERE task_file_id=%s)', (tf_id,))
                cur.execute(
                    'DELETE FROM c1_staging_record WHERE task_file_id=%s',
                    (tf_id,))
                for rec in f.get('records') or []:
                    values = rec.get('values') or {}
                    original = rec.get('original') or {}
                    review = rec.get('review') or {}
                    at = review.get('at')
                    cur.execute(
                        'INSERT INTO c1_staging_record (task_file_id,'
                        ' record_index, review_state, review_at, values_json,'
                        ' original_json) VALUES (%s,%s,%s,%s,%s,%s)',
                        (tf_id, rec['index'], review.get('state') or 'pending',
                         datetime.strptime(at, _TS) if at else None,
                         json.dumps(values, ensure_ascii=False),
                         json.dumps(original, ensure_ascii=False)))
                    rid = cur.lastrowid
                    for k, v in values.items():
                        cur.execute(
                            'INSERT INTO c1_staging_field (record_id,'
                            ' field_name, value_text, original_text)'
                            ' VALUES (%s,%s,%s,%s)',
                            (rid, k, v, original.get(k, '')))
                    for k, regs in (rec.get('lineage') or {}).items():
                        for seq, g in enumerate(regs):
                            cur.execute(
                                'INSERT INTO c1_staging_lineage'
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
    """校验改值：差量合并→edited，original 永不覆盖；返回更新后的记录。
    越界抛 NotFound，未知键抛 BadRequest（事务回滚）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            tfs = _task_files(cur, task_id)
            if file_index >= len(tfs):
                raise NotFound('文件序号超出范围')
            cur.execute(
                'SELECT id, values_json FROM c1_staging_record'
                ' WHERE task_file_id=%s AND record_index=%s FOR UPDATE',
                (tfs[file_index]['id'], index))
            row = cur.fetchone()
            if row is None:
                raise NotFound('记录序号超出范围')
            rid, vj = row
            vals = json.loads(vj)
            unknown = set(values) - set(vals)
            if unknown:
                raise BadRequest('未知字段：{}'.format('、'.join(sorted(unknown))))
            vals.update(values)
            cur.execute(
                'UPDATE c1_staging_record SET values_json=%s,'
                ' review_state=%s, review_at=%s WHERE id=%s',
                (json.dumps(vals, ensure_ascii=False), 'edited',
                 datetime.strptime(_now(), _TS), rid))
            for k, v in values.items():
                cur.execute(
                    'UPDATE c1_staging_field SET value_text=%s'
                    ' WHERE record_id=%s AND field_name=%s', (v, rid, k))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    doc = get_records(task_id)
    return next((r for r in doc['files'][file_index]['records']
                 if r['index'] == index), None)


def set_review(task_id, file_index, indexes, state):
    """批量确认/拒绝（P1 校验台）：单事务置 review_state/review_at，
    返回更新条数。state 仅 confirmed/rejected；original/lineage 不动。
    非法入参抛 BadRequest，文件越界抛 NotFound。"""
    if state not in ('confirmed', 'rejected'):
        raise BadRequest('非法校验状态：{}'.format(state))
    if not indexes:
        raise BadRequest('未选择任何记录')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            tfs = _task_files(cur, task_id)
            if file_index >= len(tfs):
                raise NotFound('文件序号超出范围')
            ph = ','.join(['%s'] * len(indexes))
            cur.execute(
                'UPDATE c1_staging_record SET review_state=%s,'
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
    return n


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
                ' FROM c1_staging_field f'
                ' JOIN c1_staging_record rec ON rec.id=f.record_id'
                ' JOIN c1_task_file tf ON tf.id=rec.task_file_id'
                ' JOIN c1_task r ON r.id=tf.task_id'
                ' JOIN c1_doc_file s ON s.id=tf.file_id {}'
                ' ORDER BY r.id DESC, rec.record_index LIMIT %s'
                .format(w), args + [limit])
            return _rows(cur)
    finally:
        conn.close()


def gate_counts(task_id, task_file_id=None):
    """门禁四态计数（性能轮）：1 条 GROUP BY，不拉记录内容。

    供任务详情/入库目标抽屉显示「还差几条没校验」——旧版为此全量拉
    /staging（~150KB）。不存在的任务返回全 0（只读端点，无副作用）。
    task_file_id 指定时收敛到单文件（派生 to_load 用）。
    """
    sql = ('SELECT COUNT(sr.id),'
           " SUM(sr.review_state='pending'),"
           " SUM(sr.review_state='edited'),"
           " SUM(sr.review_state='confirmed'),"
           " SUM(sr.review_state='rejected')"
           ' FROM c1_staging_record sr'
           ' JOIN c1_task_file tf ON tf.id=sr.task_file_id'
           ' WHERE tf.task_id=%s')
    args = [task_id]
    if task_file_id is not None:
        sql += ' AND sr.task_file_id=%s'
        args.append(task_file_id)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            r = cur.fetchone()
    finally:
        conn.close()
    return {'records_n': int(r[0] or 0), 'pending': int(r[1] or 0),
            'edited': int(r[2] or 0), 'confirmed': int(r[3] or 0),
            'rejected': int(r[4] or 0)}


def ledger():
    """校验台账（只读）：按 task 聚合记录数与四态校验进度，新任务在前。

    每个任务带 files 子列表（task_file 粒度的同款计数），供前端展开选文件。
    只列有暂存记录的任务（INNER JOIN record）；failed/无记录任务不出现。
    """
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT tf.id AS task_file_id, tf.task_id,'
                ' s.name, t.state AS task_state, t.created_at,'
                ' tpl.name AS tpl_name, tv.version,'
                ' COUNT(sr.id) AS records_n,'
                " SUM(sr.review_state='pending') AS pending_n,"
                " SUM(sr.review_state='edited') AS edited_n,"
                " SUM(sr.review_state='confirmed') AS confirmed_n,"
                " SUM(sr.review_state='rejected') AS rejected_n"
                ' FROM c1_task_file tf'
                ' JOIN c1_task t ON t.id=tf.task_id'
                ' JOIN c1_doc_file s ON s.id=tf.file_id'
                ' JOIN c1_extract_rule_version tv'
                ' ON tv.id=t.rule_version_id'
                ' JOIN c1_extract_rule tpl ON tpl.id=tv.rule_id'
                ' JOIN c1_staging_record sr ON sr.task_file_id=tf.id'
                ' GROUP BY tf.id, tf.task_id, s.name, t.state, t.created_at,'
                ' tpl.name, tv.version'
                ' ORDER BY tf.id DESC')
            tasks = {}
            for r in _rows(cur):
                f = {
                    'task_file_id': r['task_file_id'],
                    'name': r['name'],
                    'records_n': int(r['records_n']),
                    'pending_n': int(r['pending_n'] or 0),
                    'edited_n': int(r['edited_n'] or 0),
                    'confirmed_n': int(r['confirmed_n'] or 0),
                    'rejected_n': int(r['rejected_n'] or 0),
                }
                t = tasks.get(r['task_id'])
                if t is None:
                    t = tasks[r['task_id']] = {
                        'task_id': r['task_id'],
                        'task_state': r['task_state'],
                        'rule': {'name': r['tpl_name'],
                                     'version': r['version']},
                        'records_n': 0, 'pending_n': 0, 'edited_n': 0,
                        'confirmed_n': 0, 'rejected_n': 0,
                        'created_at': str(r['created_at']),
                        'files': [],
                    }
                for k in ('records_n', 'pending_n', 'edited_n',
                          'confirmed_n', 'rejected_n'):
                    t[k] += f[k]
                t['files'].append(f)
            return list(tasks.values())
    finally:
        conn.close()