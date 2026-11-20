"""
mvp/migrate_artifacts_to_db.py — 磁盘产物回填 extract_artifact（幂等，
design-artifacts-db.md §6）。

用法（从 20-CV 目录）：
    D:/miniforge3/envs/paddle/python.exe mvp/migrate_artifacts_to_db.py
    （凭据经 data/secrets.json 的 CV_PLATFORM_DB，见 store/db.py）

范围：output/<case>/ 全部文件（含 raw/、pages/）+ sources/ 规范副本。
records.json 不回填 —— records 以三表为事实源（先跑 migrate_records_to_db.py），
导出时由 export_artifacts.py 从 DB 重建。input/ 批次副本不回填（字节已在 sources）。
只增不删：磁盘原件保留，确认无误后由用户自行清理。
"""
import os
import sys
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
artifact_db = importlib.import_module(PKG + '.store.artifact_db')
seam = importlib.import_module(PKG + '.store.artifact')


def _walk(base):
    for root, _, files in os.walk(base):
        for fn in sorted(files):
            if fn.endswith('.tmp'):
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, base).replace(os.sep, '/')
            yield rel, p


def migrate_tree(case_rel, base, skip=()):
    n, nbytes = 0, 0
    for rel, p in _walk(base):
        if rel in skip:
            continue
        with open(p, 'rb') as f:
            data = f.read()
        # 直写 DB（不受 ARTIFACT_STORE 开关影响）；kind/mime 与接缝同规则
        artifact_db.save(case_rel, rel, data,
                         seam.mime_of(rel), seam.kind_of(rel))
        back = artifact_db.get(case_rel, rel)
        if back is None or back['sha'] != hashlib.sha256(data).hexdigest():
            raise RuntimeError('回读校验失败：{}/{}'.format(case_rel, rel))
        n += 1
        nbytes += len(data)
    return n, nbytes


def main():
    print('产物回填 → {}（直写 DB，不受 ARTIFACT_STORE 开关影响）'
          .format(db.safe_detail(config.PLATFORM_DB_REF)))
    total, total_bytes = 0, 0
    for case_dir in sorted(os.listdir(config.OUTPUT_DIR)):
        base = os.path.join(config.OUTPUT_DIR, case_dir)
        if not os.path.isdir(base):
            continue
        n, nb = migrate_tree(case_dir, base, skip=(config.RECORDS_JSON,))
        total += n
        total_bytes += nb
        print('  OK      {} · {} 个文件 · {:.1f} KB'.format(
            case_dir, n, nb / 1024))
    n, nb = migrate_tree('sources', config.SOURCES_DIR)
    total += n
    total_bytes += nb
    print('  OK      sources · {} 个文件 · {:.1f} KB'.format(n, nb / 1024))
    print('完成，共回填 {} 个文件 · {:.1f} MB（records.json 除外，DB 三表为事实源）'
          .format(total, total_bytes / 1024 / 1024))


if __name__ == '__main__':
    main()