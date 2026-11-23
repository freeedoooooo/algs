"""P2 入库规则单测（无 DB）：transform / 门禁 / 映射校验 / 写入语句构造。
运行：python -m unittest c1_structure.test_load_rules -v
"""
import unittest

from c1_structure.store import loader
from c1_structure.store.errors import BadRequest


class FakeCur:
    def __init__(self, exists=False, lastrowid=7):
        self.calls = []
        self._exists = exists
        self.lastrowid = lastrowid

    def execute(self, sql, args=None):
        self.calls.append((sql, args))

    def fetchone(self):
        return (1,) if self._exists else None


CM = {'账号': 'account_no', '金额': 'amount'}
VALS = {'账号': '6227001', '金额': '1,200.50'}
ROWS = [{'template_field': '账号', 'target_column': 'account_no',
         'is_business_key': 1},
        {'template_field': '金额', 'target_column': 'amount',
         'is_business_key': 0}]


class TestTransform(unittest.TestCase):
    def test_trim(self):
        out, errs = loader.apply_transform(
            {'a': '  x  '}, {'fields': [{'target': 'a', 'apply': ['trim']}]})
        self.assertEqual(out['a'], 'x')
        self.assertEqual(errs, [])

    def test_number_thousands_and_spaces(self):
        out, errs = loader.apply_transform(
            {'a': ' 1,234.56 ', 'b': '1 200'},
            {'fields': [{'target': 'a', 'apply': ['trim', 'number']},
                        {'target': 'b', 'apply': ['number']}]})
        self.assertEqual(out['a'], 1234.56)
        self.assertEqual(out['b'], 1200.0)
        self.assertEqual(errs, [])

    def test_number_failure_keeps_original(self):
        src = {'a': 'abc'}
        out, errs = loader.apply_transform(
            src, {'fields': [{'target': 'a', 'apply': ['trim', 'number']}]})
        self.assertEqual(out['a'], 'abc')
        self.assertEqual(src['a'], 'abc')
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0]['field'], 'a')
        self.assertEqual(errs[0]['value'], 'abc')

    def test_empty_number_fails(self):
        _, errs = loader.apply_transform(
            {'a': '  '}, {'fields': [{'target': 'a', 'apply': ['number']}]})
        self.assertEqual(len(errs), 1)

    def test_unknown_rule_and_absent_target(self):
        out, errs = loader.apply_transform(
            {'a': '1'}, {'fields': [{'target': 'a', 'apply': ['cast']},
                                    {'target': 'zz', 'apply': ['trim']}]})
        self.assertEqual(out['a'], '1')
        self.assertEqual(len(errs), 1)
        self.assertIn('未知规则', errs[0]['reason'])

    def test_no_transform_passthrough(self):
        out, errs = loader.apply_transform(VALS, None)
        self.assertEqual(out, VALS)
        self.assertEqual(errs, [])


class TestGate(unittest.TestCase):
    def test_counts(self):
        recs = [{'review': {'state': s}} for s in
                ('confirmed', 'confirmed', 'pending', 'edited', 'rejected')]
        recs.append({})  # 无 review 视为 pending
        c = loader.review_gate(recs)
        self.assertEqual(c, {'pending': 2, 'edited': 1,
                             'confirmed': 2, 'rejected': 1})

    def test_all_confirmed(self):
        c = loader.review_gate([{'review': {'state': 'confirmed'}}] * 3)
        self.assertEqual(c['confirmed'], 3)
        self.assertEqual(c['pending'] + c['edited'] + c['rejected'], 0)


class TestValidateFields(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(loader.validate_fields(
            ['账号', '金额'], ROWS, 'upsert', ['account_no', 'amount']))

    def test_fields_to_map(self):
        cm, bk = loader.fields_to_map(ROWS)
        self.assertEqual(cm, CM)
        self.assertEqual(bk, ['account_no'])

    def test_missing_coverage(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(['账号', '金额', '户名'], ROWS)

    def test_extra_field(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(['账号'], ROWS)

    def test_empty_column_name(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(
                ['账号'], [{'template_field': '账号', 'target_column': ' '}])

    def test_duplicate_target_column(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(
                ['a', 'b'],
                [{'template_field': 'a', 'target_column': 'x'},
                 {'template_field': 'b', 'target_column': 'x'}], 'insert')

    def test_duplicate_template_field(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(
                ['a'],
                [{'template_field': 'a', 'target_column': 'x'},
                 {'template_field': 'a', 'target_column': 'y'}], 'insert')

    def test_bad_write_mode(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(
                ['账号'], [{'template_field': '账号', 'target_column': 'x'}],
                'merge')

    def test_upsert_requires_business_key(self):
        no_bk = [{'template_field': '账号', 'target_column': 'x',
                  'is_business_key': 0}]
        with self.assertRaises(BadRequest):
            loader.validate_fields(['账号'], no_bk, 'upsert')
        with self.assertRaises(BadRequest):
            loader.validate_fields(['账号'], no_bk, 'update')

    def test_insert_no_business_key_ok(self):
        self.assertTrue(loader.validate_fields(
            ['账号'], [{'template_field': '账号', 'target_column': 'x'}],
            'insert'))

    def test_empty_rows_rejected(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(['账号'], [], 'insert')
        with self.assertRaises(BadRequest):
            loader.validate_fields(['账号'], None, 'insert')

    def test_column_existence(self):
        with self.assertRaises(BadRequest):
            loader.validate_fields(
                ['账号'], [{'template_field': '账号', 'target_column': 'nope'}],
                'insert', ['x'])
        self.assertTrue(loader.validate_fields(
            ['账号'],
            [{'template_field': '账号', 'target_column': 'x',
              'is_business_key': 1}], 'upsert', ['x']))


class TestWriteRecord(unittest.TestCase):
    def test_insert(self):
        cur = FakeCur(lastrowid=42)
        action, pk = loader.write_record(
            cur, 't1', CM, VALS, 'insert', None)
        self.assertEqual((action, pk), ('insert', '42'))
        sql, args = cur.calls[0]
        self.assertTrue(sql.startswith('INSERT INTO `t1`'))
        self.assertEqual(args, ['6227001', '1,200.50'])
        self.assertNotIn('6227001', sql)  # 值只走参数

    def test_upsert_existing_updates(self):
        cur = FakeCur(exists=True)
        action, pk = loader.write_record(
            cur, 't1', CM, VALS, 'upsert', ['account_no'])
        self.assertEqual(action, 'update')
        self.assertEqual(pk, '["6227001"]')
        self.assertTrue(cur.calls[0][0].startswith('SELECT 1 FROM `t1`'))
        self.assertTrue(cur.calls[1][0].startswith('UPDATE `t1` SET'))
        self.assertEqual(cur.calls[1][1], ['1,200.50', '6227001'])

    def test_upsert_missing_inserts(self):
        cur = FakeCur(exists=False)
        action, pk = loader.write_record(
            cur, 't1', CM, VALS, 'upsert', ['account_no'])
        self.assertEqual(action, 'insert')
        self.assertEqual(pk, '["6227001"]')
        self.assertTrue(cur.calls[1][0].startswith('INSERT INTO `t1`'))

    def test_update_missing_quarantines(self):
        cur = FakeCur(exists=False)
        with self.assertRaises(loader.LoadRecordError):
            loader.write_record(cur, 't1', CM, VALS, 'update', ['account_no'])
        self.assertEqual(len(cur.calls), 1)  # 只 SELECT，未写

    def test_ident_escaping(self):
        self.assertEqual(loader._ident('a`b'), '`a``b`')
        cur = FakeCur()
        loader.write_record(cur, 't`1', {'x': 'c`ol'}, {'x': 'v'},
                            'insert', None)
        self.assertIn('`t``1`', cur.calls[0][0])
        self.assertIn('`c``ol`', cur.calls[0][0])


if __name__ == '__main__':
    unittest.main()