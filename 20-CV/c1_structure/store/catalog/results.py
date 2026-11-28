"""目录库 · 当前抽取结果（c1_extract_result）。

唯一键为 (doc_id, rule_id)；重抽覆盖结果头，不同规则结果互不影响。
结果清理包含记录、绑定、回执和隔离记录，但不回滚已写入业务库的数据。
"""
from .. import db
from ..errors import BadRequest, NotFound
from ._common import _j, _rows

_COLS = ('id, doc_id, rule_id, rule_snapshot_json, status, record_count,'
         ' error, created_at, updated_at')
_STATUSES = ('pending', 'running', 'ready', 'failed')


def _decode(row):
    if row:
        row['rule_snapshot_json'] = _j(row.get('rule_snapshot_json'))
    return row


def _result(cur, extract_result_id):
    cur.execute('SELECT ' + _COLS +
                ' FROM c1_extract_result WHERE id=%s', (extract_result_id,))
    row = cur.fetchone()
    if not row:
        raise NotFound('抽取结果不存在')
    return row


def list_extract_results(doc_id=None, rule_id=None):
    where, args = [], []
    if doc_id is not None:
        where.append('r.doc_id=%s')
        args.append(doc_id)
    if rule_id is not None:
        where.append('r.rule_id=%s')
        args.append(rule_id)
    w = (' WHERE ' + ' AND '.join(where)) if where else ''
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT ' + ', '.join('r.' + c.strip() for c in _COLS.split(',')) +
                ', t.name AS rule_name, d.name AS doc_name'
                ' FROM c1_extract_result r'
                ' JOIN c1_extract_rule t ON t.id=r.rule_id'
                ' JOIN c1_doc d ON d.id=r.doc_id' + w +
                ' ORDER BY r.doc_id, r.id', args)
            return [_decode(row) for row in _rows(cur)]
    finally:
        conn.close()


def get_extract_result(extract_result_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT ' + ', '.join('r.' + c.strip() for c in _COLS.split(',')) +
                ', t.name AS rule_name, d.name AS doc_name'
                ' FROM c1_extract_result r'
                ' JOIN c1_extract_rule t ON t.id=r.rule_id'
                ' JOIN c1_doc d ON d.id=r.doc_id WHERE r.id=%s',
                (extract_result_id,))
            rows = _rows(cur)
        return _decode(rows[0]) if rows else None
    finally:
        conn.close()


def ensure_extract_result(doc_id, rule_id, snapshot, status='running'):
    """按文档＋规则 upsert 当前结果并返回 extract_result_id。

    仅覆盖结果头。旧记录及绑定在 save_records 替换记录时清除，避免抽取
    尚未成功就丢掉上一份可用结果。
    """
    if status not in _STATUSES:
        raise BadRequest('非法抽取结果状态：{}'.format(status))
    if not isinstance(snapshot, dict):
        raise BadRequest('规则快照须为 JSON 对象')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_doc WHERE id=%s', (doc_id,))
            if not cur.fetchone():
                raise NotFound('文档不存在')
            cur.execute('SELECT id FROM c1_extract_rule WHERE id=%s', (rule_id,))
            if not cur.fetchone():
                raise NotFound('抽取规则不存在')
            import json
            payload = json.dumps(snapshot, ensure_ascii=False)
            cur.execute(
                'INSERT INTO c1_extract_result (doc_id, rule_id,'
                ' rule_snapshot_json, status, record_count, error)'
                " VALUES (%s,%s,%s,%s,0,NULL)"
                ' ON DUPLICATE KEY UPDATE rule_snapshot_json=VALUES'
                ' (rule_snapshot_json), status=VALUES(status),'
                ' error=NULL, updated_at=NOW()',
                (doc_id, rule_id, payload, status))
            cur.execute('SELECT id FROM c1_extract_result'
                        ' WHERE doc_id=%s AND rule_id=%s', (doc_id, rule_id))
            result_id = cur.fetchone()[0]
            conn.commit()
            return result_id
    finally:
        conn.close()


def finish_extract_result(extract_result_id, status='ready', record_count=None,
                          error=None):
    """结束当前抽取；record_count=None 时以实际记录数为准。"""
    if status not in ('ready', 'failed'):
        raise BadRequest('结束状态仅支持 ready/failed')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _result(cur, extract_result_id)
            if record_count is None:
                cur.execute('SELECT COUNT(*) FROM c1_extract_record'
                            ' WHERE extract_result_id=%s', (extract_result_id,))
                record_count = cur.fetchone()[0]
            cur.execute(
                'UPDATE c1_extract_result SET status=%s, record_count=%s,'
                ' error=%s, updated_at=NOW() WHERE id=%s',
                (status, int(record_count), error, extract_result_id))
            conn.commit()
    finally:
        conn.close()


def purge_result_data(cur, extract_result_id, delete_result=False):
    """事务内清理一个结果；content_db 与文档级重解析共享同一级联边界。"""
    cur.execute('SELECT id FROM c1_load_binding'
                ' WHERE extract_result_id=%s', (extract_result_id,))
    row = cur.fetchone()
    if row:
        binding_id = row[0]
        cur.execute('DELETE FROM c1_load_receipt'
                    ' WHERE load_binding_id=%s', (binding_id,))
        cur.execute('DELETE FROM c1_quarantine_record'
                    ' WHERE load_binding_id=%s', (binding_id,))
        cur.execute('DELETE FROM c1_load_binding WHERE id=%s', (binding_id,))
    cur.execute('DELETE FROM c1_quarantine_record'
                ' WHERE extract_result_id=%s', (extract_result_id,))
    cur.execute(
        'DELETE FROM c1_extract_record_field WHERE record_id IN'
        ' (SELECT id FROM c1_extract_record WHERE extract_result_id=%s)',
        (extract_result_id,))
    cur.execute(
        'DELETE FROM c1_extract_record_lineage WHERE record_id IN'
        ' (SELECT id FROM c1_extract_record WHERE extract_result_id=%s)',
        (extract_result_id,))
    cur.execute('DELETE FROM c1_extract_record'
                ' WHERE extract_result_id=%s', (extract_result_id,))
    if delete_result:
        cur.execute('DELETE FROM c1_extract_result WHERE id=%s',
                    (extract_result_id,))
        return 1
    cur.execute('UPDATE c1_extract_result SET record_count=0,'
                ' updated_at=NOW() WHERE id=%s', (extract_result_id,))
    return 0


def purge_document_results(cur, doc_id):
    """事务内清理文档全部结果及其绑定/回执/隔离记录。"""
    cur.execute('SELECT id FROM c1_extract_result WHERE doc_id=%s', (doc_id,))
    ids = [row[0] for row in cur.fetchall()]
    for result_id in ids:
        purge_result_data(cur, result_id, delete_result=True)
    # 应用层无外键：即使结果头已缺失，也要清掉文档域遗留的绑定链。
    cur.execute('SELECT id FROM c1_load_binding WHERE doc_id=%s', (doc_id,))
    for (binding_id,) in cur.fetchall():
        cur.execute('DELETE FROM c1_load_receipt WHERE load_binding_id=%s',
                    (binding_id,))
        cur.execute('DELETE FROM c1_quarantine_record WHERE load_binding_id=%s',
                    (binding_id,))
        cur.execute('DELETE FROM c1_load_binding WHERE id=%s', (binding_id,))
    cur.execute('DELETE FROM c1_load_receipt WHERE doc_id=%s', (doc_id,))
    cur.execute('DELETE FROM c1_quarantine_record WHERE doc_id=%s', (doc_id,))
    return len(ids)


def purge_extract_result(extract_result_id):
    """删除结果本身（重抽应使用 save_records，仅替换记录并保留结果 ID）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            _result(cur, extract_result_id)
            purge_result_data(cur, extract_result_id, delete_result=True)
            conn.commit()
    finally:
        conn.close()
