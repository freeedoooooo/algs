"""目录库 · 文档域（c1_doc ＋ 原件字节 ＋ 多抽取结果/绑定聚合）。

文档不再保存单规则版本或单入库目标标量。列表/详情通过 c1_extract_result
和 c1_load_binding 聚合；重解析与删除按 doc_id 清理整条结果链。
"""
import json

from .. import db
from ..errors import BadRequest, Conflict
from ._common import _j, _rows
from .results import purge_document_results

_FILE_COLS = ('d.id, d.name, d.sha256, d.kind, d.size_bytes, d.tags, d.note,'
              ' d.doc_type, d.created_at, d.state, d.error, d.params_json,'
              ' d.updated_at')


def register_file(name, kind, size_bytes, sha256, content):
    """登记新文档（不去重，恒返回 (doc_id, False)）。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO c1_doc (name, sha256, kind, size_bytes, content)'
                ' VALUES (%s,%s,%s,%s,%s)',
                (name, sha256, kind, size_bytes, content))
            doc_id = cur.lastrowid
            conn.commit()
            return doc_id, False
    finally:
        conn.close()


def _attach_results(cur, doc_id):
    cur.execute(
        'SELECT r.id, r.doc_id, r.rule_id, r.rule_snapshot_json, r.status,'
        ' r.record_count, r.error, r.created_at, r.updated_at,'
        ' t.name AS rule_name, b.id AS load_binding_id, b.status AS binding_status,'
        ' b.field_map_json, b.write_mode, b.business_keys_json,'
        ' b.confirmed_at, lt.id AS load_table_id, lt.target_table,'
        ' ds.id AS datasource_id, ds.name AS datasource_name'
        ' FROM c1_extract_result r'
        ' JOIN c1_extract_rule t ON t.id=r.rule_id'
        ' LEFT JOIN c1_load_binding b ON b.extract_result_id=r.id'
        ' LEFT JOIN c1_load_table lt ON lt.id=b.load_table_id'
        ' LEFT JOIN c1_load_datasource ds ON ds.id=lt.datasource_id'
        ' WHERE r.doc_id=%s ORDER BY r.id', (doc_id,))
    results, bindings = [], []
    for row in _rows(cur):
        row['rule_snapshot_json'] = _j(row.get('rule_snapshot_json'))
        binding_id = row.pop('load_binding_id')
        binding_status = row.pop('binding_status')
        field_map = _j(row.pop('field_map_json'))
        write_mode = row.pop('write_mode')
        business_keys = _j(row.pop('business_keys_json'))
        confirmed_at = row.pop('confirmed_at')
        lt_id = row.pop('load_table_id')
        target_table = row.pop('target_table')
        ds_id = row.pop('datasource_id')
        ds_name = row.pop('datasource_name')
        binding = None
        if binding_id is not None:
            binding = {
                'id': binding_id, 'doc_id': row['doc_id'],
                'extract_result_id': row['id'], 'load_table_id': lt_id,
                'target_table': target_table, 'datasource_id': ds_id,
                'datasource_name': ds_name, 'status': binding_status,
                'field_map_json': field_map or {},
                'business_keys_json': business_keys or [],
                'write_mode': write_mode,
                'confirmed_at': str(confirmed_at) if confirmed_at else None,
            }
            bindings.append(binding)
        row['load_binding'] = binding
        results.append(row)
    return results, bindings


def list_files(q=None, kind=None, tag=None, page=1, per_page=20, state=None):
    conn = db.connect()
    try:
        where, args = [], []
        if q:
            where.append('d.name LIKE %s')
            args.append('%{}%'.format(q))
        if kind:
            where.append('d.kind=%s')
            args.append(kind)
        if tag:
            where.append('d.tags LIKE %s')
            args.append('%{}%'.format(tag))
        if state:
            where.append('d.state=%s')
            args.append(state)
        w = ('WHERE ' + ' AND '.join(where)) if where else ''
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM c1_doc d ' + w, args)
            total = cur.fetchone()[0]
            cur.execute('SELECT ' + _FILE_COLS + ' FROM c1_doc d ' + w +
                        ' ORDER BY d.id DESC LIMIT %s OFFSET %s',
                        args + [per_page, (max(1, page) - 1) * per_page])
            items = _rows(cur)
            for item in items:
                item['file_id'] = item['id']
                results, bindings = _attach_results(cur, item['id'])
                item['extract_results'] = results
                item['load_bindings'] = bindings
        for item in items:
            for key in ('created_at', 'updated_at'):
                item[key] = str(item[key])
            item['params_json'] = _j(item.get('params_json')) or {}
        return {'items': items, 'total': total}
    finally:
        conn.close()


def get_file(file_id):
    """按 doc_id 读取文档；参数名保留 file_id 兼容路由。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT ' + _FILE_COLS + ' FROM c1_doc d WHERE d.id=%s',
                        (file_id,))
            rows = _rows(cur)
            if not rows:
                return None
            row = rows[0]
            row['file_id'] = row['id']
            results, bindings = _attach_results(cur, row['id'])
            row['extract_results'] = results
            row['load_bindings'] = bindings
        row['params_json'] = _j(row.get('params_json')) or {}
        row['created_at'] = str(row['created_at'])
        row['updated_at'] = str(row['updated_at'])
        return row
    finally:
        conn.close()


def get_file_content(file_id):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT name, kind, sha256, content FROM c1_doc'
                        ' WHERE id=%s', (file_id,))
            row = cur.fetchone()
        if not row:
            return None
        return {'name': row[0], 'kind': row[1], 'sha': row[2], 'data': row[3]}
    finally:
        conn.close()


def delete_file(file_id):
    """处理中/已入库文档禁删；否则按文档清理结果链、产物和原件。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT state FROM c1_doc WHERE id=%s', (file_id,))
            row = cur.fetchone()
            if row and row[0] in ('parsing', 'loading', 'loaded'):
                raise Conflict('该资料正在处理或已入库，为保证血缘可追溯，不可删除')
            purge_document_results(cur, file_id)
            cur.execute('DELETE FROM c1_parse_artifact WHERE doc_id=%s', (file_id,))
            from ..compute_layout_repo import delete_for_def
            delete_for_def(cur, 'document', file_id)
            cur.execute('DELETE FROM c1_doc WHERE id=%s', (file_id,))
            conn.commit()
    finally:
        conn.close()


def clear_document_results(doc_id):
    """重解析前置：按文档清除全部抽取结果、绑定、回执及隔离记录。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM c1_doc WHERE id=%s', (doc_id,))
            if not cur.fetchone():
                raise Conflict('文档不存在')
            n = purge_document_results(cur, doc_id)
            conn.commit()
            return n
    finally:
        conn.close()


def update_file_meta(file_id, tags=None, note=None):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_doc SET tags=%s, note=%s WHERE id=%s',
                        (tags, note, file_id))
            conn.commit()
    finally:
        conn.close()


def set_state(file_id, state, error=None):
    """更新文档汇总状态；error=None 表示保留原错误。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if error is None:
                cur.execute('UPDATE c1_doc SET state=%s WHERE id=%s',
                            (state, file_id))
            else:
                cur.execute('UPDATE c1_doc SET state=%s, error=%s WHERE id=%s',
                            (state, error, file_id))
            conn.commit()
    finally:
        conn.close()


def set_params(file_id, params):
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('UPDATE c1_doc SET params_json=%s WHERE id=%s',
                        (json.dumps(params or {}, ensure_ascii=False), file_id))
            conn.commit()
    finally:
        conn.close()


# ---- 隔离记录：抽取阶段挂 result，入库阶段挂 binding ----

def add_quarantine(doc_id, record_index, stage, reason, payload,
                   extract_result_id=None, load_binding_id=None):
    if stage not in ('extract', 'collect', 'review', 'load'):
        raise BadRequest('隔离阶段仅支持 extract/collect/review/load')
    if stage == 'extract' and extract_result_id is None:
        raise BadRequest('抽取隔离须关联抽取结果')
    if stage == 'load' and load_binding_id is None:
        raise BadRequest('入库隔离须关联入库绑定')
    if stage == 'extract' and load_binding_id is not None:
        raise BadRequest('抽取隔离不能关联入库绑定')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            if extract_result_id is not None:
                cur.execute('SELECT doc_id FROM c1_extract_result WHERE id=%s',
                            (extract_result_id,))
                row = cur.fetchone()
                if not row or row[0] != doc_id:
                    raise BadRequest('抽取结果不属于该文档')
            if load_binding_id is not None:
                cur.execute('SELECT doc_id, extract_result_id FROM c1_load_binding'
                            ' WHERE id=%s', (load_binding_id,))
                row = cur.fetchone()
                if not row or row[0] != doc_id:
                    raise BadRequest('入库绑定不属于该文档')
                if extract_result_id is None:
                    extract_result_id = row[1]
                elif row[1] != extract_result_id:
                    raise BadRequest('入库绑定不属于该抽取结果')
            cur.execute(
                'INSERT INTO c1_quarantine_record (doc_id, extract_result_id,'
                ' load_binding_id, record_index, stage, reason, payload_json)'
                ' VALUES (%s,%s,%s,%s,%s,%s,%s)',
                (doc_id, extract_result_id, load_binding_id, record_index, stage,
                 reason, json.dumps(payload, ensure_ascii=False)))
            quarantine_id = cur.lastrowid
            conn.commit()
            return quarantine_id
    finally:
        conn.close()


def clear_quarantine(doc_id=None, extract_result_id=None, load_binding_id=None):
    if doc_id is None and extract_result_id is None and load_binding_id is None:
        raise BadRequest('请指定文档、抽取结果或入库绑定')
    where, args = [], []
    for key, value in (('doc_id', doc_id),
                       ('extract_result_id', extract_result_id),
                       ('load_binding_id', load_binding_id)):
        if value is not None:
            where.append(key + '=%s')
            args.append(value)
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            n = cur.execute('DELETE FROM c1_quarantine_record WHERE ' +
                            ' AND '.join(where), args)
            conn.commit()
            return n
    finally:
        conn.close()


def list_quarantine(doc_id=None, state=None, extract_result_id=None,
                    load_binding_id=None):
    where, args = [], []
    for key, value in (('doc_id', doc_id),
                       ('extract_result_id', extract_result_id),
                       ('load_binding_id', load_binding_id)):
        if value is not None:
            where.append(key + '=%s')
            args.append(value)
    if state:
        where.append('state=%s')
        args.append(state)
    w = ('WHERE ' + ' AND '.join(where)) if where else ''
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM c1_quarantine_record ' + w +
                        ' ORDER BY id DESC', args)
            rows = _rows(cur)
        for row in rows:
            row['payload_json'] = _j(row.get('payload_json'))
            row['created_at'] = str(row['created_at'])
        return rows
    finally:
        conn.close()
