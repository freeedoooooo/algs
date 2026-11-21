"""目录库 · 任务域（extract_task / extract_task_file / extract_quarantine）。

task 表投影是 tasks API 的唯一数据源（无 task.json 附件）；
隔离区按 task 粒度登记校验/入库失败记录。
"""
import json

from .. import db
from ._common import _j, _rows

# ---- extract_task / extract_task_file ----


def create_task(mode, template_version_id, params):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_task (mode, template_version_id,'
                ' params_json, state) VALUES (%s,%s,%s,%s)',
                (mode, template_version_id,
                 json.dumps(params or {}, ensure_ascii=False), 'pending'))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_task_state(task_id, state, error=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_task SET state=%s, error=%s WHERE id=%s',
                        (state, error, task_id))
            conn.commit()
    finally:
        conn.close()


def add_task_file(task_id, file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_task_file (task_id, file_id)'
                ' VALUES (%s,%s)', (task_id, file_id))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_task_file_state(task_file_id, state):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE extract_task_file SET state=%s WHERE id=%s',
                        (state, task_file_id))
            conn.commit()
    finally:
        conn.close()


def _task_doc(cur, task_id):
    """task 表投影（tasks API 的唯一数据源，无 task.json 附件）。"""
    cur.execute(
        'SELECT r.id, r.mode, r.state, r.error, r.params_json,'
        ' r.created_at, r.updated_at, t.name AS tpl_name, tv.version,'
        ' tv.id AS version_id, tv.template_id,'
        ' r.load_datasource_id, r.load_table_id,'
        ' d.name AS datasource_name, d.db_name,'
        ' lt.target_table, lt.write_mode'
        ' FROM extract_task r'
        ' JOIN extract_template_version tv ON tv.id=r.template_version_id'
        ' JOIN extract_template t ON t.id=tv.template_id'
        ' LEFT JOIN extract_load_datasource d ON d.id=r.load_datasource_id'
        ' LEFT JOIN extract_load_table lt ON lt.id=r.load_table_id'
        ' WHERE r.id=%s', (task_id,))
    rows = _rows(cur)
    if not rows:
        return None
    r = rows[0]
    cur.execute(
        'SELECT tf.id, tf.file_id, tf.state, s.name,'
        ' (SELECT COUNT(*) FROM extract_staging_record sr'
        '   WHERE sr.task_file_id=tf.id) AS records_n'
        ' FROM extract_task_file tf'
        ' JOIN extract_file s ON s.id=tf.file_id'
        ' WHERE tf.task_id=%s ORDER BY tf.id', (task_id,))
    files = [{'name': f['name'], 'state': f['state'],
              'file_id': f['file_id'],
              'task_file_id': f['id'], 'records_n': f['records_n']}
             for f in _rows(cur)]
    return {
        'task_id': r['id'], 'mode': r['mode'],
        'template': {'name': r['tpl_name'], 'version': r['version'],
                     'version_id': r['version_id'],
                     'template_id': r['template_id']},
        'params': _j(r['params_json']) or {},
        'state': r['state'], 'error': r['error'],
        'load': ({'datasource_id': r['load_datasource_id'],
                  'load_table_id': r['load_table_id'],
                  'datasource_name': r['datasource_name'],
                  'db_name': r['db_name'],
                  'target_table': r['target_table'],
                  'write_mode': r['write_mode']}
                 if r['load_datasource_id'] else None),
        'files': files,
        'created_at': str(r['created_at']),
        'updated_at': str(r['updated_at']),
    }


def get_task(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            return _task_doc(cur, task_id)
    finally:
        conn.close()


def list_tasks():
    """任务列表（新任务在前）：逐个表投影，P0 规模足够。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_task ORDER BY id DESC')
            ids = [r[0] for r in cur.fetchall()]
            return [_task_doc(cur, i) for i in ids]
    finally:
        conn.close()


def task_file_ids(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM extract_task_file'
                        ' WHERE task_id=%s ORDER BY id', (task_id,))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


# ---- extract_quarantine ----

def add_quarantine(task_id, task_file_id, record_index, stage, reason, payload):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO extract_quarantine (task_id, task_file_id,'
                ' record_index, stage, reason, payload_json)'
                ' VALUES (%s,%s,%s,%s,%s,%s)',
                (task_id, task_file_id, record_index, stage, reason,
                 json.dumps(payload, ensure_ascii=False)))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def list_quarantine(task_id=None, state=None):
    conn = db.connect()
    try:
        where, args = [], []
        if task_id is not None:
            where.append('task_id=%s')
            args.append(task_id)
        if state:
            where.append('state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM extract_quarantine {} ORDER BY id DESC'
                        .format(w), args)
            rows = _rows(cur)
        for r in rows:
            r['payload_json'] = _j(r['payload_json'])
            r['created_at'] = str(r['created_at'])
        return rows
    finally:
        conn.close()