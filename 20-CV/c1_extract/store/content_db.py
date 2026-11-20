"""
store/content_db.py — 内容 repo 的 DB 实现（design-c1-storage.md）。

records 唯一事实源＝staging 三表（自动快照已退役，export_artifacts.py 按需导出）。
键＝run_id（get/patch）与 run_file_id（save 按 doc 内登记）；DB 必选，错误上抛。
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


def _run_files(cur, run_id):
    cur.execute(
        'SELECT rf.id, rf.run_id, rf.source_file_id,'
        ' s.name AS source_name'
        ' FROM extract_run_file rf'
        ' JOIN extract_source_file s ON s.id=rf.source_file_id'
        ' WHERE rf.run_id=%s ORDER BY rf.id',
        (run_id,))
    return _rows(cur)


def get_records(run_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            rfs = _run_files(cur, run_id)
            if not rfs:
                return None
            files = []
            for rf in rfs:
                cur.execute(
                    'SELECT id, record_index, review_state, review_at,'
                    ' values_json, original_json'
                    ' FROM extract_staging_record WHERE run_file_id=%s'
                    ' ORDER BY record_index', (rf['id'],))
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
                    'run_file_id': rf['id'],
                    'source_file_id': rf['source_file_id'],
                    'name': rf['source_name'],
                    'records': out,
                })
            cur.execute(
                'SELECT t.name, tv.version FROM extract_run r'
                ' JOIN extract_template_version tv'
                ' ON tv.id=r.template_version_id'
                ' JOIN extract_template t ON t.id=tv.template_id'
                ' WHERE r.id=%s', (rfs[0]['run_id'],))
            trow = cur.fetchone()
            template = ({'name': trow[0], 'version': trow[1]} if trow
                        else {'name': '原始透传', 'version': 1})
            return {'schema': RECORDS_SCHEMA, 'run_id': rfs[0]['run_id'],
                    'template': template, 'files': files}
    finally:
        conn.close()


def save_records(doc):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            for f in doc.get('files') or []:
                rf_id = f.get('run_file_id')
                if not rf_id:
                    raise ValueError(
                        'run_file_id 缺失：db 模式须先目录登记成功')
                cur.execute(
                    'DELETE FROM extract_staging_record WHERE run_file_id=%s',
                    (rf_id,))
                for rec in f.get('records') or []:
                    values = rec.get('values') or {}
                    original = rec.get('original') or {}
                    review = rec.get('review') or {}
                    at = review.get('at')
                    cur.execute(
                        'INSERT INTO extract_staging_record (run_file_id,'
                        ' record_index, review_state, review_at, values_json,'
                        ' original_json) VALUES (%s,%s,%s,%s,%s,%s)',
                        (rf_id, rec['index'], review.get('state') or 'pending',
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


def patch_record(run_id, file_index, index, values):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            rfs = _run_files(cur, run_id)
            if file_index >= len(rfs):
                return False, '文件下标越界'
            cur.execute(
                'SELECT id, values_json FROM extract_staging_record'
                ' WHERE run_file_id=%s AND record_index=%s FOR UPDATE',
                (rfs[file_index]['id'], index))
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                return False, '记录下标越界'
            rid, vj = row
            vals = json.loads(vj)
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
    doc = get_records(run_id)
    rec = next((r for r in doc['files'][file_index]['records']
                if r['index'] == index), None)
    return True, rec


def query_fields(field=None, q=None, run=None, state=None, limit=200):
    """跨 run 暂存查询（只读）：field 表投影 + 目录 join，普通 SQL 普通索引。"""
    conn = db.connect()
    try:
        where, args = [], []
        if field:
            where.append('f.field_name=%s')
            args.append(field)
        if q:
            where.append('f.value_text LIKE %s')
            args.append('%{}%'.format(q))
        if run:
            where.append('r.id=%s')
            args.append(run)
        if state:
            where.append('rec.review_state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute(
                'SELECT r.id AS run_id, rf.id AS run_file_id,'
                ' s.name AS source_name, rec.record_index,'
                ' rec.review_state, f.field_name, f.value_text'
                ' FROM extract_staging_field f'
                ' JOIN extract_staging_record rec ON rec.id=f.record_id'
                ' JOIN extract_run_file rf ON rf.id=rec.run_file_id'
                ' JOIN extract_run r ON r.id=rf.run_id'
                ' JOIN extract_source_file s ON s.id=rf.source_file_id {}'
                ' ORDER BY r.id DESC, rec.record_index LIMIT %s'
                .format(w), args + [limit])
            return _rows(cur)
    finally:
        conn.close()