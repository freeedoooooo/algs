"""
c1_structure/accept_artifacts_db.py — 产物全量入库六项验收（资料化契约，
DB 唯一事实源，产物键＝file_id，无外键）。

模型：一条资料 = 一次运行（file_id）；无 task 概念。
前置：C1_STRUCTURE_DB 已配置。用法（从 20-CV）：
    D:/miniforge3/envs/paddle/python.exe -u c1_structure/accept_artifacts_db.py

1 连接零副作用+读回 sha 自洽 · 2 真链路无持久磁盘+BLOB · 3 /files 路由/ETag/raw403 ·
4 资料 API/报告/暂存全查库 · 5 导出字节一致 · 6 断库显式 503。
上传字节取自 c1_doc_file.content；断库用不可达 DSN 的临时服务模拟。
破坏性操作只落本次合成的资料行，验完按 id 清理；用户既有资料只读。
用户的 8765 全程不动。临时服务 8799(真库)/8797(不可达 DSN)。两套脚本严禁并行。
"""
import os
import sys
import json
import time
import base64
import shutil
import socket
import hashlib
import tempfile
import subprocess
import importlib
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(ROOT)
PKG = os.path.basename(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault('PYTHONUTF8', '1')
config = importlib.import_module(PKG + '.config')
db = importlib.import_module(PKG + '.store.db')
catalog = importlib.import_module(PKG + '.store.catalog')
content_db = importlib.import_module(PKG + '.store.content_db')
artifact_db = importlib.import_module(PKG + '.store.artifact_db')

BAD_DSN = 'mysql://nobody:unused@127.0.0.1:3399/c1_structure_dev'
FAILS = []
BASE_FID = 9_000_000   # 合成资料从 900 万起，避让真实数据


def check(name, ok, detail=''):
    print('  {}  {}{}'.format('PASS' if ok else 'FAIL', name,
                              (' · ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


def http(port, path, body=None, headers=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    h = {'Content-Type': 'application/json'}
    if headers:
        h.update(headers)
    req = urllib.request.Request('http://127.0.0.1:{}{}'.format(port, path),
                                 data=data, headers=h,
                                 method='POST' if body is not None else 'GET')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        # 4xx/304 都是待测的合法响应，urllib 当异常抛，统一转成状态元组
        try:
            body = e.read()
        except Exception:
            body = b''
        return e.code, dict(e.headers), body


def http_json(port, path, body=None, timeout=60):
    st, _h, b = http(port, path, body, timeout=timeout)
    return st, json.loads(b or b'{}')


def wait_http(port, secs=30):
    end = time.time() + secs
    while time.time() < end:
        try:
            urllib.request.urlopen(
                'http://127.0.0.1:{}/healthz'.format(port), timeout=2).read()
            return True
        except Exception:
            time.sleep(0.3)
    return False


def wait_db(secs=60):
    end = time.time() + secs
    while time.time() < end:
        try:
            db.connect().close()
            return True
        except Exception:
            time.sleep(0.5)
    return False


def art_counts():
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*), COALESCE(SUM(size_bytes),0)'
                        ' FROM c1_parse_artifact')
            return tuple(cur.fetchone())
    finally:
        conn.close()


def start_service(port, dsn=None):
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
    except OSError:
        raise RuntimeError('端口 {} 已被占用，先停掉占用者再跑'.format(port))
    finally:
        s.close()
    env = dict(os.environ, C1_STRUCTURE_PORT=str(port), C1_STRUCTURE_WARMUP='0')
    # 不传 dsn 时保留继承的 C1_STRUCTURE_DB（验收可能指定验证库），
    # 只有显式传 dsn 才覆盖；断库场景传 BAD_DSN。
    if dsn:
        env['C1_STRUCTURE_DB'] = dsn
    p = subprocess.Popen(
        [sys.executable, '-m', 'uvicorn', PKG + '.app:app',
         '--host', '127.0.0.1', '--port', str(port)],
        cwd=PARENT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_http(port) or p.poll() is not None:
        p.kill()
        raise RuntimeError('服务 {} 启动失败'.format(port))
    return p


def upload(port, src_bytes, name):
    st, j = http_json(port, '/api/upload',
                      {'files': [{'name': name,
                                  'data': base64.b64encode(src_bytes).decode()}]},
                      timeout=120)
    if st != 200 or not j.get('ok'):
        raise RuntimeError('upload 失败：{} {}'.format(st, j))
    file_id = j['file_id']
    for _ in range(300):
        _, s = http_json(port, '/api/status')
        if not s.get('running'):
            return file_id, s
        time.sleep(0.5)
    raise RuntimeError('upload 超时')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def find_pdf_file():
    """优先取真实 PDF 原件；清库后无原件时造一份最小 PDF 并登记合成行。

    合成行 id 从 BASE_FID 起，验完由 main() 的 cleanup_file 清理。
    """
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name, content FROM c1_doc_file'
                        ' WHERE kind=%s AND size_bytes>1024 AND id<%s'
                        ' ORDER BY id DESC LIMIT 1', ('pdf', BASE_FID))
            r = cur.fetchone()
        if r:
            return {'id': r[0], 'name': r[1], 'sha': sha(r[2]), 'data': r[2]}
    finally:
        conn.close()
    # 最小可解析 PDF：一页 + 一行文本（paddle 走文本层路线，模型可解析）
    pdf = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
           b'2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n'
           b'3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]'
           b'/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n'
           b'4 0 obj<</Length 58>>stream\nBT /F1 12 Tf 72 700 Td '
           b'(accept 123.45) Tj ET\nendstream endobj\n'
           b'5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n'
           b'trailer<</Root 1 0 R>>\n%%EOF\n')
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            # 先清上一轮可能残留的同 id 合成行（无外键，先清子表）
            for t in ('c1_load_log', 'c1_load_quarantine',
                      'c1_staging_record', 'c1_parse_artifact'):
                cur.execute('DELETE FROM ' + t + ' WHERE file_id=%s',
                            (BASE_FID,))
            cur.execute('DELETE FROM c1_doc_file WHERE id=%s', (BASE_FID,))
            cur.execute('INSERT INTO c1_doc_file'
                        ' (id, name, sha256, kind, size_bytes, content)'
                        ' VALUES (%s,%s,%s,%s,%s,%s)',
                        (BASE_FID, 'accept_synth.pdf', sha(pdf), 'pdf',
                         len(pdf), pdf))
            conn.commit()
        return {'id': BASE_FID, 'name': 'accept_synth.pdf',
                'sha': sha(pdf), 'data': pdf}
    finally:
        conn.close()


def scratch_clean(wait=5):
    for _ in range(wait * 2):
        if not any(n.startswith(('in_', 'case_'))
                   for d in (config.TMP_INPUT, config.TMP_WORK)
                   for n in os.listdir(d)):
            return True
        time.sleep(0.5)
    return False


def cleanup_file(file_id):
    """先子后父（无外键）：field/lineage→record→artifact→quarantine→
    load_log→doc_file。"""
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM c1_staging_field WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id=%s)',
                        (file_id,))
            cur.execute('DELETE FROM c1_staging_lineage WHERE record_id IN'
                        ' (SELECT id FROM c1_staging_record WHERE file_id=%s)',
                        (file_id,))
            for t in ('c1_staging_record', 'c1_parse_artifact',
                      'c1_load_quarantine', 'c1_load_log'):
                cur.execute('DELETE FROM ' + t + ' WHERE file_id=%s',
                            (file_id,))
            cur.execute('DELETE FROM c1_doc_file WHERE id=%s AND id>=%s',
                        (file_id, BASE_FID))
        conn.commit()
    finally:
        conn.close()


def main():
    print('== 产物入库验收（资料化）· {} =='.format(
        db.safe_detail(config.PLATFORM_DB)))
    try:
        if not wait_db():
            print('配置库不可达，检查 C1_STRUCTURE_DB')
            return 1
    except LookupError as e:
        print(str(e))
        return 1
    db.connect().close()
    up = []
    try:
        rc = _main(up)
    finally:
        print('清理临时资料')
        for fid in up:
            cleanup_file(fid)
    print('\n结论：{}'.format('六项全部 PASS' if not FAILS
                            else 'FAIL {} 项：{}'.format(len(FAILS), FAILS)))
    return rc


def _main(up):
    print('[1/6] 连接零副作用 + 读回 sha 自洽')
    c0 = art_counts()
    db.connect().close()
    db.connect().close()
    check('连接重开行数/字节不变', art_counts() == c0,
          '{} vs {}'.format(c0, art_counts()))
    conn = db.connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT DISTINCT file_id FROM c1_parse_artifact')
            fids = [r[0] for r in cur.fetchall()]
            cur.execute('SELECT id, sha256, size_bytes, content FROM c1_doc_file')
            files = cur.fetchall()
            cur.execute('SELECT COUNT(*) FROM c1_parse_artifact a'
                        ' LEFT JOIN c1_doc_file f ON f.id=a.file_id'
                        ' WHERE f.id IS NULL')
            orphan_art = cur.fetchone()[0]
    finally:
        conn.close()
    check('无孤儿 artifact（反查=0）', orphan_art == 0,
          '悬空={}'.format(orphan_art))
    bad, n = [], 0
    for fid in fids:
        for m in artifact_db.list(fid):
            n += 1
            a = artifact_db.get(fid, m['name'])
            if a is None or a['sha'] != m['sha'] \
                    or sha(a['data']) != m['sha'] \
                    or len(a['data']) != m['size']:
                bad.append('{}/{}'.format(fid, m['name']))
    check('附件全量读回 sha/size 自洽', not bad,
          '{} 个文件'.format(n) if not bad else '不一致：{}'.format(bad[:5]))
    bad_src = [r[0] for r in files
               if sha(r[3]) != r[1] or len(r[3]) != r[2]]
    check('c1_doc_file.content sha/size 自洽', not bad_src,
          '{} 个原件'.format(len(files)) if not bad_src
          else '不一致 id：{}'.format(bad_src))

    print('[2/6] 真链路：无持久磁盘 + BLOB（临时服务 8799）')
    src = find_pdf_file()
    if src is None:
        print('  FAIL  c1_doc_file 无 PDF 原件，无法真链路验收')
        return 1
    svc = start_service(8799)
    try:
        file_id, st = upload(8799, src['data'], src['name'])
        up.append(file_id)
        time.sleep(1)
        f = catalog.get_file(file_id)
        check('真链路仅解析=待抽取', st.get('error') is None
              and f['state'] == 'to_extract',
              'err={} state={}'.format(st.get('error'), f['state']))
        check('tmp/input+tmp/work 无 scratch 残留', scratch_clean())
        names = {m['name'] for m in artifact_db.list(file_id)}
        check('产物入 BLOB', {config.PARSE_JSON,
                             config.PARSE_REPORT_NAME} <= names,
              '{} 个文件'.format(len(names)))

        print('[3/6] /files 路由：mime / ETag 304 / raw 403 / records 404')
        q = urllib.request.quote
        st1, h1, b1 = http(8799, '/files/{}/{}'.format(
            file_id, q(config.PARSE_JSON)))
        check('/files extract 200+mime', st1 == 200
              and h1.get('content-type', '').startswith('application/json')
              and json.loads(b1.decode()).get('schema'))
        st2, h2, _b2 = http(8799, '/files/{}/{}'.format(
            file_id, q(config.PARSE_REPORT_NAME)))
        check('/files 报告 200+html', st2 == 200
              and h2.get('content-type', '').startswith('text/html'))
        etag = h1.get('etag')
        st3, _h3, _b3 = http(8799, '/files/{}/{}'.format(
            file_id, q(config.PARSE_JSON)),
            headers={'If-None-Match': etag} if etag else None)
        check('ETag 304', bool(etag) and st3 == 304, 'etag={}'.format(etag))
        st4, _h4, _b4 = http(8799, '/files/{}/raw/pdfplumber.json'.format(
            file_id))
        check('raw 403', st4 == 403)
        st5, _h5, _b5 = http(8799, '/files/{}/records.json'.format(file_id))
        check('records.json 404（DB 三表为事实源）', st5 == 404)
        st6, _h6, b6 = http(8799, '/srcfiles/{}'.format(src['id']))
        check('/srcfiles 200 + sha 一致', st6 == 200 and sha(b6) == src['sha'])

        print('[4/6] 资料 API / 报告重定向 / 暂存全查库')
        st, j = http_json(8799, '/api/sources/state')
        check('资料列表含新资料', st == 200
              and any(r.get('id') == file_id for r in j['items']))
        st, j = http_json(8799, '/api/sources/{}/pipeline'.format(file_id))
        check('pipeline 单链路待抽取', st == 200
              and j['pipeline']['state'] == 'to_extract',
              'state={}'.format(j['pipeline']['state']))
        codes = []
        for u in ('/preview', '/review'):
            with urllib.request.urlopen(
                    urllib.request.Request('http://127.0.0.1:8799' + u),
                    timeout=30) as rp:
                codes.append(rp.status)
        check('页面路由 /preview ＋ /review 壳页 200', codes == [200, 200])
        req = urllib.request.Request('http://127.0.0.1:8799/parse-report')
        with urllib.request.urlopen(req, timeout=30) as r:
            check('报告重定向落 /files/', r.status == 200
                  and '/files/' in r.url and r.url.endswith(
                      q(config.PARSE_REPORT_NAME)))
        ste, je = http_json(8799, '/api/sources/{}/extract'.format(file_id),
                            {})
        f = catalog.get_file(file_id)
        check('执行抽取→待校验', ste == 200 and je.get('ok')
              and f['state'] == 'to_review',
              'st={} state={}'.format(ste, f['state']))
        # 合成 PDF 无表格 → 透传产出 0 条；注入合成 records 验暂存 API 与跨资料查询
        # （抽取引擎本身的产出由 [4/6] 的「执行抽取→待校验」断言覆盖）
        injected = {'schema': 'c1-structure-records/1', 'file_id': file_id,
                    'rule': {'name': '验收', 'version': 1},
                    'files': [{'file_id': file_id, 'name': 'accept',
                               'records': [{
                                   'index': 0,
                                   'values': {'验收列': 'ACCEPT_STAGE'},
                                   'original': {'验收列': 'ACCEPT_STAGE'},
                                   'lineage': {},
                                   'review': {'state': 'pending', 'at': None}}]}]}
        content_db.save_records(injected)
        st, j = http_json(8799, '/api/sources/{}/staging'.format(file_id))
        check('暂存 API 记录数一致', st == 200
              and len(j['files'][0]['records']) == 1
              and j['files'][0]['records'][0]['values']['验收列']
              == 'ACCEPT_STAGE',
              '{} 条'.format(len(j['files'][0]['records'])))
        st, j = http_json(8799, '/api/staging/query?q=' + q('ACCEPT_STAGE'))
        check('跨资料查询 200', st == 200 and j.get('ok')
              and len(j.get('items', [])) > 0)
    finally:
        svc.kill()

    print('[5/6] 导出字节一致 + records 重建')
    out_dir = tempfile.mkdtemp(prefix='c1_export_')
    try:
        p = subprocess.run(
            [sys.executable, os.path.join(PKG, 'export_artifacts.py'),
             '--file', str(up[0]), '--out', out_dir],
            cwd=PARENT, env=dict(os.environ, PYTHONUTF8='1'),
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=600)
        if p.returncode != 0:
            print(p.stdout[-2000:], p.stderr[-2000:])
        check('导出脚本退出 0', p.returncode == 0)
        f = catalog.get_file(up[0])
        base = os.path.join(out_dir, 'output', 'file_{}'.format(up[0]))
        bad = []
        for m in artifact_db.list(up[0]):
            fp = os.path.join(base, f['name'], m['name'].replace('/', os.sep))
            if not os.path.isfile(fp):
                bad.append('缺 ' + f['name'] + '/' + m['name'])
                continue
            with open(fp, 'rb') as fh:
                if sha(fh.read()) != m['sha']:
                    bad.append('sha ' + f['name'] + '/' + m['name'])
        rp = os.path.join(base, config.RECORDS_JSON)
        want = content_db.get_records(up[0])
        if want is not None:
            if not os.path.isfile(rp):
                bad.append('缺 records.json')
            else:
                with open(rp, encoding='utf-8') as fh:
                    if json.load(fh) != want:
                        bad.append('records 语义')
        check('导出逐文件字节一致 + records 语义一致', not bad,
              '1 个资料' if not bad else '问题：{}'.format(bad[:5]))
        check('导出报告可 file:// 直开（文件在树内）',
              os.path.isfile(os.path.join(base, f['name'],
                                          config.PARSE_REPORT_NAME)))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    print('[6/6] 断库显式 503（临时服务 8797，不可达 DSN）')
    svc = start_service(8797, dsn=BAD_DSN)
    try:
        st, j = http_json(8797, '/api/upload',
                          {'files': [{'name': src['name'],
                                      'data': base64.b64encode(
                                          src['data']).decode()}]})
        check('断库上传 503', st == 503, 'st={} err={}'.format(
            st, j.get('error')))
        st, _j = http_json(8797, '/api/sources')
        check('断库资料列表 503', st == 503)
        st, _h, _b = http(8797, '/files/{}/{}'.format(
            file_id, urllib.request.quote(config.PARSE_JSON)))
        check('断库 /files 503', st == 503)
        st, _h, _b = http(8797, '/parse-report')
        check('断库报告入口 503', st == 503)
        st, _j = http_json(8797, '/api/sources/{}/staging'.format(up[0]))
        check('断库暂存 503', st == 503)
    finally:
        svc.kill()


if __name__ == '__main__':
    sys.exit(main())
