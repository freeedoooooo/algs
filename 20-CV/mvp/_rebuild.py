import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from mvp.report import builder
from mvp import config

OUT = os.path.join(ROOT, 'mvp', 'output')
CASES = sys.argv[1:] or [n for n in sorted(os.listdir(OUT))
                         if os.path.isfile(os.path.join(OUT, n, 'result.json'))]
for name in CASES:
    path = os.path.join(OUT, name, 'result.json')
    if not os.path.isfile(path):
        print('skip', name)
        continue
    with open(path, encoding='utf-8') as f:
        rec = json.load(f)
    if not isinstance(rec.get('pages'), list):
        print('skip(old envelope)', name)
        continue
    out = builder.build([rec], os.path.join(OUT, name, config.EXTRACT_REPORT_NAME),
                        params=rec.get('params_snapshot'))
    print('built', out, os.path.getsize(out))