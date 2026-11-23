"""
c1_extract/export_artifacts.py — 从 DB 按需导出完整磁盘树
（design-task-schema.md：file:// 直开 / 审计 / 迁移出口）。

用法（从 20-CV 目录）：
    D:/miniforge3/envs/paddle/python.exe c1_extract/export_artifacts.py --out D:/tmp/c1_export
    可选 --task <id> 只导一次任务。

导出布局：<out>/output/task_<id>/<源文件名>/…（产物 BLOB 原字节）
          <out>/output/task_<id>/records.json（DB 三表重建，任务级信封）
          <out>/sources/<源文件名>（原件字节，重名加 _<id> 区分）
报告内相对路径原样成立，file:// 直开 对照报告.html 可用。
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
catalog = importlib.import_module(PKG + '.store.catalog')
artifact_db = importlib.import_module(PKG + '.store.artifact_db')
content_db = importlib.import_module(PKG + '.store.content_db')


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def export_task(task, out_root):
    base = os.path.join(out_root, 'output', 'task_{}'.format(task['task_id']))
    n = 0
    for f in task['files']:
        fdir = os.path.join(base, f['name'])
        for meta in artifact_db.list(f['task_file_id']):
            a = artifact_db.get(f['task_file_id'], meta['name'])
            _write(os.path.join(fdir, meta['name'].replace('/', os.sep)),
                   a['data'])
            n += 1
    try:
        doc = content_db.get_records(task['task_id'])
    except Exception as e:
        print('  WARN    task {} · records 重建失败（{}），跳过 records.json'
              .format(task['task_id'], e))
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
    ap.add_argument('--task', type=int, help='只导指定 task id')
    args = ap.parse_args()
    out_root = os.path.abspath(args.out)
    print('产物导出 ← {} → {}'.format(
        db.safe_detail(config.PLATFORM_DB), out_root))
    tasks = ([catalog.get_task(args.task)] if args.task
             else catalog.list_tasks())
    tasks = [t for t in tasks if t]
    total = 0
    for t in tasks:
        n = export_task(t, out_root)
        total += n
        print('  OK      task_{} · {} 个文件'.format(t['task_id'], n))
    n, used = 0, set()
    page = 1
    while True:
        batch = catalog.list_files(page=page, per_page=100)
        for row in batch['items']:
            s = catalog.get_file_content(row['id'])
            name = row['name']
            if name in used:
                stem, e = os.path.splitext(name)
                name = '{}_{}{}'.format(stem, row['id'], e)
            used.add(name)
            _write(os.path.join(out_root, 'sources', name), s['data'])
            n += 1
        if page * 100 >= batch['total']:
            break
        page += 1
    total += n
    print('  OK      sources · {} 个文件'.format(n))
    print('完成，共导出 {} 个文件。file:// 直开 output/task_<id>/<源名>/对照报告.html'
          .format(total))


if __name__ == '__main__':
    main()