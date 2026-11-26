"""M2 校验算子与 review.reason：只标记不改值，未知算子拒绝。"""
import unittest

from c1_structure.collect_logic.ops.validate import VALIDATORS, run_validates
from c1_structure.collect_logic.engine import build_logic


def _doc(headers, rows):
    return {
        'file': {'name': 't.csv', 'kind': 'csv'},
        'pages': [{'index': 1, 'space': 'source', 'tables': [{
            'headers': headers, 'rows': rows, 'cells': [],
            'page': 1, 'coord': {'space': 'source'},
        }]}],
        'stitched_tables': [],
    }


class ValidateOpsTest(unittest.TestCase):
    def test_operator_set(self):
        self.assertEqual(set(VALIDATORS), {
            'required', 'regex', 'enum', 'range', 'cross_field'})

    def test_field_level_issues(self):
        f = {'target': '金额', 'validate': [
            {'op': 'required'}, {'op': 'range', 'min': 0},
            {'op': 'regex', 'pattern': '^[0-9]+$'}]}
        ctx = {'values': {}}
        self.assertEqual(run_validates(f, ctx, ''), ['required'])
        self.assertEqual(run_validates(f, ctx, '-1'), ['range', 'regex'])
        self.assertEqual(run_validates(f, ctx, 'abc'), ['range', 'regex'])
        self.assertEqual(run_validates(f, ctx, '123'), [])

    def test_enum_and_cross_field_cmp(self):
        self.assertEqual(run_validates(
            {'validate': [{'op': 'enum', 'values': ['A', 'B']}]}, {}, 'C'),
            ['enum'])
        f = {'validate': [
            {'op': 'cross_field', 'other': 'B', 'cmp': '>'}]}
        self.assertEqual(run_validates(f, {'values': {'B': 5}}, 10), [])
        self.assertEqual(
            run_validates(f, {'values': {'B': 5}}, 3), ['cross_field'])

    def test_unknown_operator_rejected(self):
        with self.assertRaises(ValueError):
            run_validates({'validate': [{'op': 'bogus'}]}, {}, 'x')

    def test_reason_only_when_issue_no_value_change(self):
        doc = _doc(['金额'], [['10'], ['abc']])
        tpl = {'mapping_json': {'spec_version': 2,
                                'records': {'strategy': 'row'},
                                'fields': [{'target': '金额',
                                            'pipeline': [
                                                {'op': 'cell', 'source': 'main',
                                                 'column': {'name': '金额'},
                                                 'row': 'current'}],
                                            'validate': [
                                                {'op': 'range', 'min': 0}]}]}}
        recs = build_logic(doc, tpl)
        self.assertEqual([r['values']['金额'] for r in recs], ['10', 'abc'])
        self.assertNotIn('reason', recs[0]['review'])
        self.assertEqual(recs[1]['review']['reason'], {'金额': ['range']})

    def test_legacy_rule_records_unchanged(self):
        doc = _doc(['金额'], [['10']])
        tpl = {'mapping_json': {'spec_version': 2,
                                'records': {'strategy': 'row'},
                                'fields': [{'target': '金额',
                                            'pipeline': [
                                                {'op': 'cell', 'source': 'main',
                                                 'column': {'name': '金额'},
                                                 'row': 'current'}]}]}}
        rec = build_logic(doc, tpl)[0]
        self.assertEqual(rec['review'], {'state': 'pending', 'at': None})
        self.assertEqual(rec['values'], {'金额': '10'})
        self.assertEqual(rec['original'], {'金额': '10'})
        self.assertEqual(rec['index'], 0)
        self.assertEqual(len(rec['lineage']['金额']), 1)


if __name__ == '__main__':
    unittest.main()
