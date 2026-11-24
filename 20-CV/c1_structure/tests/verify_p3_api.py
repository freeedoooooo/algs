"""P3 API 冒烟：对 8799 验证库跑资料全流程 API；跑完清理。

用法：python tests/verify_p3_api.py [base_url]
"""
import base64
import os
import sys
import time
import json
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8799'


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def main():
    raw = b'%PDF-1.4 P3 api smoke ' + os.urandom(5)
    b64 = base64.b64encode(raw).decode()
    code, j = call('POST', '/api/sources', {'name': 'p3.pdf', 'data': b64})
    print('register:', code, j)
    assert code == 200 and j['ok'] and j['dedup'] is False
    fid = j['id']

    try:
        # 流程追踪（无产物也应 200）
        code, j = call('GET', '/api/sources/{}/pipeline'.format(fid))
        print('pipeline:', code, j.get('pipeline', {}).get('state'))
        assert code == 200 and j['ok']
        assert set(j['pipeline'].keys()) >= {
            'file_id', 'state', 'parse_artifacts', 'review_counts',
            'load', 'load_actions'}

        # gate（无记录全 0）
        code, j = call('GET', '/api/sources/{}/gate'.format(fid))
        print('gate empty:', code, j)
        assert code == 200 and j['records_n'] == 0

        # staging 空信封（资料存在但无记录）→ 200 且 files[0].records 为空
        code, j = call('GET', '/api/sources/{}/staging'.format(fid))
        print('staging empty:', code, len(j.get('files', [{}])[0].get('records', [])))
        assert code == 200 and j['file_id'] == fid
        assert len(j['files'][0]['records']) == 0

        # parse 不存在 → 404
        code, j = call('GET', '/api/sources/{}/parse'.format(fid))
        print('parse empty:', code)
        assert code == 404

        # 从资料发起解析（真 OCR 需模型；这里只验证入口参数与 STATE 启动）
        # 为避免等模型，跳过实际解析，直接手工把 parse.json 产物写进去走抽取
        # —— 用已有的 service 自测覆盖抽取；API 层只验端点存在与错误码语义。
        code, j = call('POST', '/api/sources/{}/extract'.format(fid), {})
        print('extract no parse:', code, j.get('error'))
        assert code == 409 and '解析产物' in (j.get('error') or '')

        # 重放（to_extract 之外的初始态 pending 也可：无产物时拒绝解析）
        code, j = call('POST', '/api/sources/{}/reparse'.format(fid))
        print('reparse:', code, j.get('ok'))
        assert code == 200 and j['ok']

        # 等解析线程起来后确认 STATE（不深等完成，避免模型耗时）
        for _ in range(5):
            code, st = call('GET', '/api/status')
            if st.get('file_id') == fid:
                break
            time.sleep(0.3)
        print('status file_id:', st.get('file_id'))
        assert st.get('file_id') == fid

        # 旧端点确认 404
        for old in ('/api/tasks', '/api/tasks/{}/gate'.format(fid),
                    '/api/tasks/{}/staging'.format(fid)):
            code, _ = call('GET', old)
            print('old endpoint', old, code)
            assert code == 404
    finally:
        # 清理资料（若解析线程还在跑，稍等）
        time.sleep(1)
        from urllib.parse import quote
        req = urllib.request.Request(BASE + '/api/sources/{}'.format(fid),
                                     method='DELETE')
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print('cleanup note:', e)

    print('P3 API SMOKE PASS')


if __name__ == '__main__':
    main()
