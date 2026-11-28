"""计算域表重命名迁移单测（不连真实数据库）。"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(ROOT))
migration = __import__(os.path.basename(ROOT) + '.store.migrations.008_rename_calc_tables',
                       fromlist=['run'])


class FakeCursor:
    def __init__(self, tables, counts):
        self.tables = set(tables)
        self.counts = dict(counts)
        self.result = None
        self.renames = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, args=None):
        if sql == 'SHOW TABLES':
            self.result = [(table,) for table in sorted(self.tables)]
            return
        if sql.startswith('SELECT COUNT(*) FROM `'):
            table = sql.rsplit('`', 2)[1]
            self.result = (self.counts[table],)
            return
        if sql.startswith('ALTER TABLE `'):
            old, new = sql.split('`')[1::2]
            if old not in self.tables or new in self.tables:
                raise RuntimeError('invalid rename')
            self.tables.remove(old)
            self.tables.add(new)
            self.counts[new] = self.counts.pop(old)
            self.renames.append((old, new))
            return
        raise AssertionError('unexpected SQL: ' + sql)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


class FakeConnection:
    def __init__(self, cursor):
        self.cur = cursor
        self.closed = False

    def cursor(self):
        return self.cur

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class CalcTableMigrationTest(unittest.TestCase):
    def setUp(self):
        self.old_tables = [old for old, _ in migration.RENAMES]
        self.new_tables = [new for _, new in migration.RENAMES]
        self.counts = {table: index + 1 for index, table in enumerate(self.old_tables)}
        self.cur = FakeCursor(self.old_tables, self.counts)
        self.conn = FakeConnection(self.cur)

    def test_dry_run_does_not_rename_or_backup(self):
        with tempfile.TemporaryDirectory() as root, \
                patch.object(migration.db, 'connect', return_value=self.conn), \
                patch.object(migration.config, 'DATA_ROOT', root), \
                patch.object(migration, '_dump_sql') as dump:
            self.assertEqual(migration.run(confirm=False), 0)
        self.assertEqual(self.cur.renames, [])
        dump.assert_not_called()
        self.assertTrue(self.conn.closed)

    def test_confirm_preserves_rows_and_is_idempotent(self):
        backups = []

        def dump(conn, tables, path):
            backups.append((set(tables), path))
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('-- backup')
            return sum(self.counts[table] for table in tables)

        with tempfile.TemporaryDirectory() as root, \
                patch.object(migration.db, 'connect', return_value=self.conn), \
                patch.object(migration.config, 'DATA_ROOT', root), \
                patch.object(migration, '_dump_sql', side_effect=dump):
            self.assertEqual(migration.run(confirm=True), 0)
            self.assertEqual(migration.run(confirm=True), 0)

        self.assertEqual(self.cur.tables, set(self.new_tables))
        self.assertEqual(self.cur.counts, dict(zip(self.new_tables, range(1, 8))))
        self.assertEqual(len(self.cur.renames), len(migration.RENAMES))
        self.assertEqual(len(backups), 1)

    def test_old_and_new_collision_is_rejected(self):
        self.cur.tables.add(self.new_tables[0])
        with self.assertRaises(RuntimeError):
            migration._plan(self.cur.tables)


if __name__ == '__main__':
    unittest.main()
