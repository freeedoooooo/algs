import json
import unittest
from unittest import mock

from c1_structure.agent import rule_reuse


DESCRIPTION = '提取设备巡检表中的设备名称、巡检日期和异常描述'
FIELDS = ['设备名称', '巡检日期', '异常描述']


def _doc():
    return {'file': {'name': 'inspection.csv', 'kind': 'csv'},
            'pages': [{'index': 1, 'space': 'source', 'texts': [],
                       'tables': [{
                           'headers': FIELDS,
                           'rows': [['泵机', '2026-11-01', '正常'],
                                    ['风机', '2026-11-02', '异响']],
                           'cells': [], 'page': 1,
                           'coord': {'space': 'source'}}]}],
            'stitched_tables': []}


def _spec(header_contains='设备名称'):
    return {
        'spec_version': 2,
        'tables': [{'ref': 't0', 'role': 'record_source', 'index': 0,
                    'header_contains': header_contains}],
        'records': {'strategy': 'row', 'source_ref': 't0'},
        'fields': [{'target': name, 'type': 'string', 'pipeline': [
            {'op': 'cell', 'source': 't0', 'column': {'name': name},
             'row': 'current'}]} for name in FIELDS],
    }


def _schema():
    return {'fields': [{'name': name, 'type': 'string'} for name in FIELDS]}


def _rule(rule_id=1, description=DESCRIPTION, updated_at='2026-11-28'):
    return {
        'id': rule_id, 'name': '自动规则', 'description': description,
        'output_schema_json': json.dumps(_schema(), ensure_ascii=False),
        'extraction_spec_json': json.dumps(_spec(), ensure_ascii=False),
        'updated_at': updated_at,
    }


class RuleReuseTests(unittest.TestCase):
    def test_exact_description_reuses_single_row_rule_json(self):
        candidate = rule_reuse.best_candidate(DESCRIPTION, [_rule()], _doc())
        self.assertIsNotNone(candidate)
        self.assertEqual(1, candidate['id'])
        self.assertEqual(1.0, candidate['reuse_score'])
        self.assertEqual(_schema(), candidate['output_schema'])
        self.assertEqual(_spec(), candidate['extraction_spec'])
        self.assertNotIn('current_version_id', candidate)
        self.assertIsInstance(candidate['extraction_spec_json'], str)

    def test_decoded_json_objects_from_catalog_are_supported(self):
        rule = _rule()
        rule['output_schema_json'] = _schema()
        rule['extraction_spec_json'] = _spec()
        candidate = rule_reuse.best_candidate(
            DESCRIPTION, [rule], _doc(), output_fields=FIELDS)
        self.assertEqual(1, candidate['id'])

    def test_reuse_requires_document_for_dry_run(self):
        with self.assertRaises(ValueError):
            rule_reuse.best_candidate(DESCRIPTION, [_rule()])

    def test_unrelated_description_does_not_reuse(self):
        self.assertIsNone(rule_reuse.best_candidate(
            '提取发票购买方和税号', [_rule()], _doc(), output_fields=FIELDS))

    def test_similarity_threshold_is_unchanged(self):
        self.assertEqual(0.86, rule_reuse.MIN_SIMILARITY)
        candidate = rule_reuse.best_candidate(
            DESCRIPTION, [_rule(description='设备巡检表')], _doc(),
            output_fields=FIELDS)
        self.assertIsNone(candidate)

    def test_best_candidate_prefers_higher_similarity(self):
        other = _rule(rule_id=2, description='设备巡检表')
        candidate = rule_reuse.best_candidate(
            DESCRIPTION, [other, _rule()], _doc(), output_fields=FIELDS)
        self.assertEqual(1, candidate['id'])

    def test_explicit_output_field_set_must_match_exactly(self):
        for fields in (FIELDS[:2], FIELDS + ['处理人']):
            with self.subTest(fields=fields):
                self.assertIsNone(rule_reuse.best_candidate(
                    DESCRIPTION, [_rule()], _doc(), output_fields=fields))

    def test_output_fields_can_be_inferred_from_description(self):
        candidate = rule_reuse.best_candidate(DESCRIPTION, [_rule()], _doc())
        self.assertEqual(1, candidate['id'])
        self.assertIsNone(rule_reuse.best_candidate(
            '提取设备巡检表', [_rule(description='提取设备巡检表')], _doc()))

    def test_output_fields_accept_name_or_target_objects(self):
        candidate = rule_reuse.best_candidate(
            DESCRIPTION, [_rule()], _doc(),
            output_fields=[{'name': FIELDS[0]}, {'target': FIELDS[1]}, FIELDS[2]])
        self.assertIsNotNone(candidate)

    def test_output_schema_and_spec_field_sets_must_match(self):
        rule = _rule()
        schema = _schema()
        schema['fields'].append({'name': '处理人', 'type': 'string'})
        rule['output_schema_json'] = json.dumps(schema, ensure_ascii=False)
        self.assertIsNone(rule_reuse.best_candidate(
            DESCRIPTION, [rule], _doc(), output_fields=FIELDS))

    def test_missing_or_invalid_single_row_json_is_ignored(self):
        invalid = [_rule(), _rule(rule_id=2), _rule(rule_id=3)]
        invalid[0]['output_schema_json'] = '{bad json'
        invalid[1]['extraction_spec_json'] = None
        invalid[2]['output_schema_json'] = json.dumps(_schema())
        invalid[2]['extraction_spec_json'] = json.dumps({'fields': []})
        self.assertIsNone(rule_reuse.best_candidate(
            DESCRIPTION, invalid, _doc(), output_fields=FIELDS))

    def test_legacy_version_only_rule_is_ignored(self):
        legacy = {'id': 1, 'description': DESCRIPTION, 'current_version_id': 11,
                  'schema_json': _schema(), 'mapping_json': _spec()}
        self.assertIsNone(rule_reuse.best_candidate(
            DESCRIPTION, [legacy], _doc(), output_fields=FIELDS))

    def test_record_source_and_source_ref_are_required(self):
        missing_role = _rule()
        spec = json.loads(missing_role['extraction_spec_json'])
        del spec['tables'][0]['role']
        missing_role['extraction_spec_json'] = json.dumps(spec, ensure_ascii=False)
        missing_ref = _rule()
        spec = json.loads(missing_ref['extraction_spec_json'])
        del spec['records']['source_ref']
        missing_ref['extraction_spec_json'] = json.dumps(spec, ensure_ascii=False)
        for rule in (missing_role, missing_ref):
            with self.subTest(rule=rule['id']):
                self.assertIsNone(rule_reuse.best_candidate(
                    DESCRIPTION, [rule], _doc(), output_fields=FIELDS))

    def test_table_header_and_column_structure_must_match(self):
        wrong_header = _rule()
        wrong_header['extraction_spec_json'] = json.dumps(
            _spec(header_contains='故障描述'), ensure_ascii=False)
        wrong_column = _rule()
        spec = _spec()
        spec['fields'][0]['pipeline'][0]['column'] = {'name': '不存在列'}
        wrong_column['extraction_spec_json'] = json.dumps(spec, ensure_ascii=False)
        for rule in (wrong_header, wrong_column):
            with self.subTest(rule=rule['extraction_spec_json']):
                self.assertIsNone(rule_reuse.best_candidate(
                    DESCRIPTION, [rule], _doc(), output_fields=FIELDS))

    def test_index_table_selector_must_exist(self):
        rule = _rule()
        spec = _spec()
        spec['tables'] = [{'ref': 't0', 'role': 'record_source', 'index': 0}]
        rule['extraction_spec_json'] = json.dumps(spec, ensure_ascii=False)
        self.assertIsNotNone(rule_reuse.best_candidate(
            DESCRIPTION, [rule], _doc(), output_fields=FIELDS))
        spec['tables'][0]['index'] = 3
        rule['extraction_spec_json'] = json.dumps(spec, ensure_ascii=False)
        self.assertIsNone(rule_reuse.best_candidate(
            DESCRIPTION, [rule], _doc(), output_fields=FIELDS))

    def test_failed_dry_run_cannot_be_reused(self):
        failed = [
            {'error': 'bad'},
            {'records_n': 0, 'empty_fields': [], 'anchor_coverage': 0.0},
            {'records_n': 2, 'empty_fields': ['日期'], 'anchor_coverage': 1.0},
            {'records_n': 2, 'empty_fields': [], 'anchor_coverage': 0.94},
        ]
        for diag in failed:
            with self.subTest(diag=diag), mock.patch.object(
                    rule_reuse.validate, 'dry_run', return_value=diag):
                self.assertIsNone(rule_reuse.best_candidate(
                    DESCRIPTION, [_rule()], _doc(), output_fields=FIELDS))

    def test_failed_top_candidate_falls_back_to_passed_candidate(self):
        first = _rule(rule_id=1, updated_at='2026-11-30')
        second = _rule(rule_id=2, updated_at='2026-11-29')
        with mock.patch.object(rule_reuse.validate, 'dry_run', side_effect=[
                {'records_n': 0, 'empty_fields': [], 'anchor_coverage': 0.0},
                {'records_n': 2, 'empty_fields': [], 'anchor_coverage': 1.0}]) as run:
            candidate = rule_reuse.best_candidate(
                DESCRIPTION, [second, first], _doc(), output_fields=FIELDS)
        self.assertEqual(2, candidate['id'])
        self.assertEqual(2, run.call_count)

    def test_acceptable_requires_records_fields_and_anchors(self):
        good = {'records_n': 2, 'empty_fields': [], 'anchor_coverage': 0.95}
        self.assertTrue(rule_reuse.acceptable(good))
        self.assertFalse(rule_reuse.acceptable(dict(good, records_n=0)))
        self.assertFalse(rule_reuse.acceptable(dict(good, empty_fields=['日期'])))
        self.assertFalse(rule_reuse.acceptable(dict(good, anchor_coverage=0.94)))
        self.assertFalse(rule_reuse.acceptable({'error': 'bad'}))


if __name__ == '__main__':
    unittest.main()
