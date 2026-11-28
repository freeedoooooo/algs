"""已入库资料测试重解析：正式数据隔离与普通重放清理契约。"""
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT = os.path.dirname(ROOT)
for _p in (PARENT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from c1_structure import service
from c1_structure.store import errors


class _Catalog:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def get_file(self, file_id):
        return {'id': file_id, 'state': self.state, 'name': 'a.pdf',
                'params_json': {}, 'created_at': '2026-01-01'}

    def get_file_content(self, file_id):
        return {'data': b'pdf'}

    def set_state(self, *args):
        self.calls.append(('state',) + args)

    def clear_document_results(self, doc_id):
        self.calls.append(('results', doc_id))


class _Artifact:
    def __init__(self):
        self.calls = []

    def delete_all(self, file_id):
        self.calls.append(file_id)


class _TaskLog:
    def __init__(self, *args, **kwargs):
        pass

    def stage(self, *args):
        pass


class _Thread:
    def __init__(self, target, args, daemon):
        self.target, self.args, self.daemon = target, args, daemon

    def start(self):
        pass


class ReparseIsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.catalog = _Catalog('loaded')
        self.artifact = _Artifact()
        self.mods = {'store.catalog': self.catalog,
                     'store.content_db': SimpleNamespace(),
                     'store.artifact': self.artifact,
                     'store.errors': errors,
                     'tasklog': SimpleNamespace(TaskLog=_TaskLog)}
        self.old_running = service.STATE['running']
        service.STATE['running'] = False

    def tearDown(self):
        service.STATE['running'] = self.old_running
        self.tmp.cleanup()

    def launch(self, test_mode):
        with patch.object(service, '_load', side_effect=lambda n: self.mods[n]), \
             patch.object(service.config, 'TMP_INPUT', self.tmp.name), \
             patch.object(service.config, 'LOG_DIR', self.tmp.name), \
             patch.object(service.threading, 'Thread', _Thread):
            return service.reparse(1, test_mode=test_mode)

    def test_loaded_requires_explicit_test_mode(self):
        with self.assertRaises(errors.Conflict):
            self.launch(False)
        self.assertEqual(self.artifact.calls, [])
        self.assertEqual(self.catalog.calls, [])

    def test_loaded_test_mode_preserves_formal_data(self):
        result = self.launch(True)
        self.assertTrue(result['test_mode'])
        self.assertEqual(result['report_url'], '/files/1/test/对照报告.html')
        self.assertEqual(self.artifact.calls, [])
        self.assertEqual(self.catalog.calls, [])
        self.assertTrue(service.STATE['test_mode'])

    def test_regular_reparse_still_clears_old_data(self):
        self.catalog.state = 'to_extract'
        result = self.launch(False)
        self.assertFalse(result['test_mode'])
        self.assertEqual(self.artifact.calls, [1])
        self.assertEqual(self.catalog.calls[0], ('results', 1))
        self.assertIn(('state', 1, 'pending', ''), self.catalog.calls)
        self.assertFalse(any(c[0] == 'rule' for c in self.catalog.calls))


if __name__ == '__main__':
    unittest.main()
