"""聊天阶段结果摘要：只返回轻量统计与少量样例，不传输完整产物。"""


def _display_value(value, limit=160):
    if value is None:
        return ''
    if isinstance(value, bytes):
        return '<二进制 {} bytes>'.format(len(value))
    if hasattr(value, 'isoformat'):
        value = value.isoformat(sep=' ')
    text = str(value)
    return text if len(text) <= limit else text[:limit - 1] + '…'


def parse_summary(doc, artifacts=None):
    if not doc:
        return {'status': 'missing', 'message': '尚无解析产物'}
    pages = doc.get('pages') or []
    texts = sum(len(p.get('texts') or []) for p in pages)
    blocks = sum(len(p.get('blocks') or []) for p in pages)
    tables = sum(len(p.get('tables') or []) for p in pages)
    tables += len(doc.get('stitched_tables') or [])
    chars = sum(len(str(t.get('text') or '')) for p in pages
                for t in (p.get('texts') or []))
    report = next((name for name in (artifacts or [])
                   if name == '对照报告.html'), None)
    return {
        'status': 'ready',
        'file_name': (doc.get('file') or {}).get('name'),
        'kind': (doc.get('file') or {}).get('kind'),
        'page_count': (doc.get('file') or {}).get('page_count') or len(pages),
        'text_fragments': texts,
        'blocks': blocks,
        'text_chars': chars,
        'table_count': tables,
        'report_available': bool(report),
    }


def extract_summary(record_set):
    if not record_set:
        return {'status': 'missing', 'message': '尚无抽取记录'}
    records = [r for f in (record_set.get('files') or [])
               for r in (f.get('records') or [])]
    if not records:
        return {'status': 'empty', 'record_count': 0, 'fields': [], 'samples': []}
    fields = []
    for rec in records:
        for name in (rec.get('values') or {}):
            if name not in fields:
                fields.append(name)
    samples = []
    for rec in records[:3]:
        samples.append({name: _display_value((rec.get('values') or {}).get(name))
                        for name in fields})
    anchored = sum(1 for rec in records if rec.get('lineage'))
    review_counts = {}
    for rec in records:
        state = (rec.get('review') or {}).get('state') or 'pending'
        review_counts[state] = review_counts.get(state, 0) + 1
    return {
        'status': 'ready',
        'record_count': len(records),
        'fields': fields,
        'samples': samples,
        'anchored_records': anchored,
        'review_counts': review_counts,
        'rule': record_set.get('rule') or {},
    }
