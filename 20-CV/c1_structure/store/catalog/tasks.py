"""目录库 · 任务域（c1_task / c1_task_file / c1_load_quarantine）。

task 表投影是 tasks API 的唯一数据源（无 task.json 附件）；
隔离区按 task 粒度登记校验/入库失败记录。
"""
import json

from .. import db
from ._common import _j, _rows

# ---- c1_task / c1_task_file ----


def create_task(rule_version_id, params):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_task (rule_version_id,'
                ' params_json, state) VALUES (%s,%s,%s)',
                (rule_version_id,
                 json.dumps(params or {}, ensure_ascii=False), 'pending'))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_task_state(task_id, state, error=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_task SET state=%s, error=%s WHERE id=%s',
                        (state, error, task_id))
            conn.commit()
    finally:
        conn.close()


# 文件态进度序（任务态 = 最落后文件的态；failed 单独短路）。
_STATE_RANK = {'pending': 0, 'parsing': 1, 'to_extract': 2,
               'to_review': 3, 'to_load': 4, 'loading': 5, 'loaded': 6}


def rollup_task_state(task_id):
    """文件态上卷任务态：任一 failed 即 failed，否则取最落后文件态。
    只改 state 不动 error（入库隔离说明由写入方管理）。返回新任务态。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT state FROM c1_task_file WHERE task_id=%s',
                        (task_id,))
            states = [r[0] for r in cur.fetchall()]
            if not states:
                return None
            if 'failed' in states:
                target = 'failed'
            else:
                target = min(states, key=lambda x: _STATE_RANK.get(x, 0))
            cur.execute('UPDATE c1_task SET state=%s WHERE id=%s',
                        (target, task_id))
            conn.commit()
            return target
    finally:
        conn.close()


def add_task_file(task_id, file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_task_file (task_id, file_id)'
                ' VALUES (%s,%s)', (task_id, file_id))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def set_task_file_state(task_file_id, state):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_task_file SET state=%s WHERE id=%s',
                        (state, task_file_id))
            conn.commit()
    finally:
        conn.close()


_HEAD_SQL = (
    'SELECT r.id, r.state, r.error, r.params_json,'
    ' r.created_at, r.updated_at, t.name AS tpl_name, tv.version,'
    ' tv.id AS version_id, tv.rule_id,'
    ' r.load_datasource_id, r.load_table_id,'
    ' d.name AS datasource_name, d.db_name,'
    ' lt.target_table, lt.write_mode'
    ' FROM c1_task r'
    ' JOIN c1_extract_rule_version tv ON tv.id=r.rule_version_id'
    ' JOIN c1_extract_rule t ON t.id=tv.rule_id'
    ' LEFT JOIN c1_load_datasource d ON d.id=r.load_datasource_id'
    ' LEFT JOIN c1_load_table lt ON lt.id=r.load_table_id')

_FILES_SQL_TAIL = (
    ' SELECT tf.task_id, tf.id, tf.file_id, tf.state, s.name,'
    ' (SELECT COUNT(*) FROM c1_staging_record sr'
    '   WHERE sr.task_file_id=tf.id) AS records_n'
    ' FROM c1_task_file tf'
    ' JOIN c1_doc_file s ON s.id=tf.file_id')


def _file_row(f):
    return {'name': f['name'], 'state': f['state'],
            'file_id': f['file_id'],
            'task_file_id': f['id'], 'records_n': f['records_n']}


def _mk_doc(r, files):
    """task 头行＋文件行 → tasks API 投影（_task_doc/list_tasks 共用形状）。"""
    return {
        'task_id': r['id'],
        'rule': {'name': r['tpl_name'], 'version': r['version'],
                     'version_id': r['version_id'],
                     'rule_id': r['rule_id']},
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


def _task_doc(cur, task_id):
    """task 表投影（tasks API 的唯一数据源，无 task.json 附件）。"""
    cur.execute(_HEAD_SQL + ' WHERE r.id=%s', (task_id,))
    rows = _rows(cur)
    if not rows:
        return None
    cur.execute(_FILES_SQL_TAIL + ' WHERE tf.task_id=%s ORDER BY tf.id',
                (task_id,))
    return _mk_doc(rows[0], [_file_row(f) for f in _rows(cur)])


def get_task(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            return _task_doc(cur, task_id)
    finally:
        conn.close()


def list_tasks():
    """任务列表（新任务在前）：2 条批量查询（远端库每往返约 35ms，
    旧版逐任务 2×N 在 44 任务时要 3.7s）。投影与 get_task 逐键一致。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_HEAD_SQL + ' ORDER BY r.id DESC')
            heads = _rows(cur)
            if not heads:
                return []
            ids = [h['id'] for h in heads]
            cur.execute(_FILES_SQL_TAIL + ' WHERE tf.task_id IN ('
                        + ','.join(['%s'] * len(ids)) + ')'
                        + ' ORDER BY tf.task_id, tf.id', ids)
            files = _rows(cur)
    finally:
        conn.close()
    by_task = {}
    for f in files:
        by_task.setdefault(f['task_id'], []).append(_file_row(f))
    return [_mk_doc(h, by_task.get(h['id'], [])) for h in heads]


def task_file_ids(task_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_task_file'
                        ' WHERE task_id=%s ORDER BY id', (task_id,))
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


# ---- c1_load_quarantine ----

def add_quarantine(task_id, task_file_id, record_index, stage, reason, payload):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_load_quarantine (task_id, task_file_id,'
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
            cur.execute('SELECT * FROM c1_load_quarantine {} ORDER BY id DESC'
                        .format(w), args)
            rows = _rows(cur)
        for r in rows:
            r['payload_json'] = _j(r['payload_json'])
            r['created_at'] = str(r['created_at'])
        return rows
    finally:
        conn.close()