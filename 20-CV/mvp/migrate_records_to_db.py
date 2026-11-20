"""
mvp/migrate_records_to_db.py — 旧 case 回填 DB（选项 B，幂等，design-records-db.md §4）。

用法（从 20-CV 目录）：
    CV_PLATFORM_DB=mysql://user:pass@host:port/db \\
        D:/miniforge3/envs/paddle/python.exe mvp/migrate_records_to_db.py
    （凭据也可放 data/secrets.json，见 store/db.py）

扫 output/*/records.json → 以 (batch_tag, 文件名) 自然键幂等登记
template_version / run / source_file / run_file → content_db.save_records
单事务写三表 + 重导快照 → run.json 回填 id。可重复跑、可中断续跑。
源字节取 input/ 批次副本，缺失时回落 sources/ 规范副本。
"""
import os
import sys
import json
import glob
import hashlib
import importlib

ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
config = importlib.import_module(PKG + '.config')
db = importlib.import_module(PKG + '.store.db')
catalog = importlib.import_module(PKG + '.store.catalog')
content = importlib.import_module(PKG + '.store.content')
content_db = importlib.import_module(PKG + '.store.content_db')


def _kind_of(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in config.PDF_EXTS:
        return 'pdf'
    return 'text' if ext in config.TEXT_EXTS else 'image'


def _read_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def ensure_template_version(conn, name, version):
    with conn.cursor() as cur:
        cur.execute(
            'SELECT tv.id FROM extract_template_version tv'
            ' JOIN extract_template t ON t.id=tv.template_id'
            ' WHERE t.name=%s AND tv.version=%s', (name, version))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute('SELECT id FROM extract_template WHERE name=%s', (name,))
        row = cur.fetchone()
        if row:
            tid = row[0]
        else:
            cur.execute(
                'INSERT INTO extract_template (name, description,'
                ' current_version) VALUES (%s,%s,%s)',
                (name, '迁移回填', version))
            tid = cur.lastrowid
        cur.execute(
            'INSERT INTO extract_template_version (template_id, version,'
            ' schema_json, mapping_json, transform_json)'
            ' VALUES (%s,%s,%s,%s,%s)', (tid, version, '[]', '{}', '[]'))
        conn.commit()
        return cur.lastrowid


def ensure_run(conn, tag, mode, tv_id, params):
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM extract_run WHERE batch_tag=%s'
                    ' ORDER BY id LIMIT 1', (tag,))
        row = cur.fetchone()
    if row:
        return row[0]
    return catalog.create_run(tag, mode, tv_id, params)


def ensure_run_file(conn, run_id, sid, case_dir):
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM extract_run_file'
                    ' WHERE run_id=%s AND source_file_id=%s', (run_id, sid))
        row = cur.fetchone()
    if row:
        return row[0]
    return catalog.add_run_file(run_id, sid, 'output/' + case_dir)


def migrate_case(conn, case_dir):
    case_abs = os.path.join(config.OUTPUT_DIR, case_dir)
    doc = _read_json(os.path.join(case_abs, config.RECORDS_JSON))
    if not doc:
        return None
    tag = case_dir[:14]
    if not tag.isdigit():
        print('  SKIP    {}（目录前缀非批次戳）'.format(case_dir))
        return None
    run_doc = _read_json(os.path.join(case_abs, config.RUN_JSON)) or {}
    tpl = doc.get('template') or {'name': '原始透传', 'version': 1}
    tv_id = ensure_template_version(conn, tpl['name'], tpl['version'])
    run_id = ensure_run(conn, tag, run_doc.get('mode') or 'preview',
                        tv_id, run_doc.get('params') or {})
    n = 0
    for f in doc.get('files') or []:
        uploaded = f.get('name') or ''
        orig = uploaded[len(tag) + 1:] if uploaded.startswith(tag + '_') \
            else uploaded
        src = os.path.join(config.INPUT_DIR, uploaded)
        if not os.path.isfile(src):
            cands = glob.glob(os.path.join(config.SOURCES_DIR, '*_' + orig))
            src = cands[0] if cands else None
        if not src:
            print('  SKIP    {} · {}（源字节缺失，无法登记）'.format(
                case_dir, orig))
            continue
        with open(src, 'rb') as fh:
            data = fh.read()
        sha = hashlib.sha256(data).hexdigest()
        rel = 'sources/{}_{}'.format(sha[:8], orig)
        if not os.path.isfile(config.to_abs(rel)):
            with open(config.to_abs(rel), 'wb') as fh:
                fh.write(data)
        sid, _dedup = catalog.register_source(
            orig, _kind_of(orig), len(data), sha, rel)
        rf_id = ensure_run_file(conn, run_id, sid, case_dir)
        catalog.set_run_file_state(rf_id, 'previewed')
        f['run_file_id'] = rf_id
        f['source_file_id'] = sid
        n += len(f.get('records') or [])
    doc['run_id'] = run_id
    content_db.save_records(case_dir, doc)
    catalog.set_run_state(run_id, 'previewed')
    if run_doc:
        run_doc['run_id'] = run_id
        for rf in run_doc.get('files') or []:
            match = next(
                (f for f in doc['files']
                 if f.get('name') == '{}_{}'.format(tag, rf.get('name'))
                 or f.get('name') == rf.get('name')), None)
            if match:
                rf['run_file_id'] = match.get('run_file_id')
                rf['source_file_id'] = match.get('source_file_id')
        content.save_run(case_dir, run_doc)
    return n


def main():
    print('records 回填 → {}（RECORDS_STORE 开关不影响本脚本，直写 DB）'
          .format(db.safe_detail(config.PLATFORM_DB_REF)))
    conn = db.connect()
    total = 0
    try:
        for case_dir in sorted(os.listdir(config.OUTPUT_DIR)):
            if not os.path.isdir(os.path.join(config.OUTPUT_DIR, case_dir)):
                continue
            n = migrate_case(conn, case_dir)
            if n is not None:
                total += n
                print('  OK      {} · {} 条记录'.format(case_dir, n))
    finally:
        conn.close()
    print('完成，共回填 {} 条记录'.format(total))


if __name__ == '__main__':
    main()