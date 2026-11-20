"""
mvp/export_artifacts.py — 从 extract_artifact 按需导出完整磁盘树
（design-artifacts-db.md §6：db 模式的 file:// 直开 / 审计 / 迁移出口）。

用法（从 20-CV 目录）：
    D:/miniforge3/envs/paddle/python.exe mvp/export_artifacts.py --out D:/tmp/cv_export
    可选 --case <目录名> 只导一个 case。

导出布局与 DATA_ROOT 一致：<out>/output/<case>/… + <out>/sources/…，
报告内相对路径原样成立，file:// 直开 对照报告.html 可用。
records.json 不在 BLOB 里（DB 三表为事实源），导出时经 content_db 重建；
其余文件按 BLOB 原字节落盘（sha256 与库内一致）。
"""
import os
import sys
import json
import argparse
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
content_db = importlib.import_module(PKG + '.store.content_db')


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def export_case(case_rel, out_root):
    base = os.path.join(out_root, 'output', case_rel)
    n = 0
    for meta in artifact_db.list(case_rel):
        a = artifact_db.get(case_rel, meta['name'])
        _write(os.path.join(base, meta['name'].replace('/', os.sep)),
               a['data'])
        n += 1
    try:
        doc = content_db.get_records(case_rel)
    except Exception as e:
        print('  WARN    {} · records 重建失败（{}），跳过 records.json'
              .format(case_rel, e))
        doc = None
    if doc is not None:
        _write(os.path.join(base, config.RECORDS_JSON),
               json.dumps(doc, ensure_ascii=False,
                          separators=(',', ':')).encode('utf-8'))
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, help='导出根目录（绝对路径）')
    ap.add_argument('--case', help='只导指定 case 目录名')
    args = ap.parse_args()
    out_root = os.path.abspath(args.out)
    print('产物导出 ← {} → {}'.format(
        db.safe_detail(config.PLATFORM_DB_REF), out_root))
    cases = ([args.case] if args.case
             else [c for c in artifact_db.cases() if c != 'sources'])
    total = 0
    for c in cases:
        n = export_case(c, out_root)
        total += n
        print('  OK      {} · {} 个文件'.format(c, n))
    n = 0
    for meta in artifact_db.list('sources'):
        a = artifact_db.get('sources', meta['name'])
        _write(os.path.join(out_root, 'sources',
                            meta['name'].replace('/', os.sep)), a['data'])
        n += 1
    total += n
    print('  OK      sources · {} 个文件'.format(n))
    print('完成，共导出 {} 个文件。file:// 直开 output/<case>/对照报告.html 即可'
          .format(total))


if __name__ == '__main__':
    main()