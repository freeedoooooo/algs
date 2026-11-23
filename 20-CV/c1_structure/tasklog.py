"""
c1_structure/tasklog.py — 结构化运行日志（唯一真相源）。

设计要点：
  · 一个 TaskLog 实例对应「一次任务（task）」，同时服务三处消费方：
      - STATE['logs']：页面轮询 /api/status 时拿到结构化数组（带级别/阶段/耗时）
      - logs/task_<id>.log：落盘纯文本，一次任务一份，可单独清理 / 归档
      - 控制台：同格式实时打印，终端启动时也能直接看进度
  · pipeline 只认一个 emit(level, stage, msg) 回调，不 import app / tasklog，
    避免解析层反向依赖 Web 层，也方便以后换成别的日志后端。
  · level: info / ok / warn / error / stage；stage 是短阶段名（ocr/table/…）。
  · t 是相对运行开始的秒数，ms 是本条相对上一条的耗时，页面直接显示。
"""
import os
import time
import threading

LEVEL_ORDER = {'info': 0, 'ok': 1, 'stage': 2, 'warn': 3, 'error': 4}
_LEVEL_TAG = {'info': 'INFO', 'ok': ' OK ', 'stage': 'STAGE',
              'warn': 'WARN', 'error': 'ERROR'}


class TaskLog:
    """一次任务的日志收集器；线程安全（后台线程写、主线程读状态）。"""

    def __init__(self, label, log_path=None, on_emit=None):
        self.label = label
        self.t0 = time.time()
        self._last = self.t0
        self._lock = threading.Lock()
        self._rows = []
        self._on_emit = on_emit            # app 注入：同步更新 STATE
        self.path = None
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self.path = log_path
            with open(self.path, 'w', encoding='utf-8') as f:
                f.write('# task {}\n'.format(label))

    def emit(self, level, stage, msg, **extra):
        now = time.time()
        with self._lock:
            row = {
                't': round(now - self.t0, 2),
                'ms': int((now - self._last) * 1000),
                'level': level if level in LEVEL_ORDER else 'info',
                'stage': stage or '-',
                'msg': str(msg),
            }
            row.update(extra)
            self._rows.append(row)
            self._last = now
            line = '[{:>7}s +{:>5}ms] [{:<5}] [{:<9}] {}'.format(
                row['t'], row['ms'], _LEVEL_TAG.get(row['level'], 'INFO'),
                row['stage'], row['msg'])
            print(line, flush=True)
            if self.path:
                try:
                    with open(self.path, 'a', encoding='utf-8') as f:
                        f.write(line + '\n')
                except OSError:
                    pass
        if self._on_emit:
            self._on_emit(row)
        return row

    # 语义化快捷方法，调用点更直观
    def info(self, stage, msg, **kw):
        return self.emit('info', stage, msg, **kw)

    def ok(self, stage, msg, **kw):
        return self.emit('ok', stage, msg, **kw)

    def stage(self, stage, msg, **kw):
        return self.emit('stage', stage, msg, **kw)

    def warn(self, stage, msg, **kw):
        return self.emit('warn', stage, msg, **kw)

    def error(self, stage, msg, **kw):
        return self.emit('error', stage, msg, **kw)

    def rows(self):
        with self._lock:
            return list(self._rows)

    def make_emit(self):
        """返回给 pipeline 用的回调（只暴露 emit，避免解析层拿到整个对象）。"""
        return self.emit
