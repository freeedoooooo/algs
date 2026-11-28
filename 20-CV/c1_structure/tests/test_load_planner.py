import unittest

from c1_structure.store.load_planner import (build_plan, normalize_intent,
                                             snapshot_from_mapping)


def records(fields):
    return {'files': [{'records': [
        {'index': i, 'values': values}
        for i, values in enumerate(fields)]}]}


def schema(name='inspection_record', datasource_id=1):
    return {
        'name': name, 'datasource_id': datasource_id, 'comment': '设备巡检记录',
        'columns': [
            {'name': 'id', 'type': 'bigint', 'comment': '编号', 'primary': True},
            {'name': 'device_name', 'type': 'varchar', 'comment': '设备名称'},
            {'name': 'inspection_date', 'type': 'date', 'comment': '巡检日期'},
            {'name': 'abnormal_desc', 'type': 'varchar', 'comment': '异常描述'},
        ],
        'indexes': [],
    }


class LoadPlannerTests(unittest.TestCase):
    def setUp(self):
        self.record_set = records([
            {'编号': '1', '设备名称': '泵机', '巡检日期': '2026-11-27',
             '异常描述': '无'},
        ])

    def test_nested_load_intent_is_normalized(self):
        intent = normalize_intent({
            'description': '设备巡检表',
            'load': {'table': 'inspection_record', 'datasource_id': 3},
        })
        self.assertEqual('inspection_record', intent['target_table'])
        self.assertEqual(3, intent['datasource_id'])

    def test_no_target_recommends_existing_table(self):
        plan = build_plan(self.record_set, {'description': '设备巡检记录'},
                          [schema()])
        self.assertEqual('waiting_target', plan['status'])
        self.assertEqual('inspection_record', plan['recommendations'][0]['table'])

    def test_recommendations_exclude_platform_configuration_tables(self):
        plan = build_plan(self.record_set, {'description': '设备巡检记录'},
                          [schema('c1_doc_file'), schema('biz_inspection')])
        self.assertEqual('waiting_target', plan['status'])
        self.assertEqual(['biz_inspection'],
                         [r['table'] for r in plan['recommendations']])

    def test_platform_table_cannot_be_selected_as_business_target(self):
        plan = build_plan(self.record_set, {'target_table': 'c1_doc_file'},
                          [schema('c1_doc_file')])
        self.assertEqual('target_missing', plan['status'])
        self.assertIsNone(plan['mapping'])

    def test_missing_target_does_not_plan_load(self):
        plan = build_plan(self.record_set, {'target_table': 'missing'}, [schema()])
        self.assertEqual('target_missing', plan['status'])
        self.assertIsNone(plan['mapping'])

    def test_complete_mapping_is_ready(self):
        plan = build_plan(self.record_set,
                          {'target_table': 'inspection_record', 'datasource_id': 1},
                          [schema()])
        self.assertEqual('ready', plan['status'])
        self.assertTrue(plan['mapping']['complete'])
        self.assertEqual('device_name', plan['mapping']['field_map']['设备名称'])

    def test_partial_mapping_is_ready_and_skips_unmapped_fields(self):
        partial = schema('other')
        partial['columns'] = partial['columns'][:2]
        plan = build_plan(self.record_set,
                          {'target_table': 'other', 'datasource_id': 1},
                          [partial])
        self.assertEqual('ready', plan['status'])
        self.assertTrue(plan['mapping']['complete'])
        self.assertEqual({'编号', '设备名称'},
                         set(plan['mapping']['field_map']))
        self.assertEqual({'巡检日期', '异常描述'},
                         set(plan['mapping']['unmapped_fields']))

    def test_saved_mapping_is_authoritative_and_does_not_autofill(self):
        plan = build_plan(
            self.record_set,
            {'target_table': 'inspection_record', 'datasource_id': 1,
             'field_map': {'设备名称': 'device_name'}},
            [schema()])
        self.assertEqual('ready', plan['status'])
        self.assertEqual({'设备名称': 'device_name'},
                         plan['mapping']['field_map'])

    def test_empty_mapping_still_blocks_load(self):
        plan = build_plan(
            self.record_set,
            {'target_table': 'inspection_record', 'datasource_id': 1,
             'field_map': {}},
            [schema()])
        self.assertEqual('mapping_incomplete', plan['status'])
        self.assertEqual({}, plan['mapping']['field_map'])

    def test_duplicate_table_requires_datasource(self):
        plan = build_plan(self.record_set,
                          {'target_table': 'inspection_record'},
                          [schema(datasource_id=1), schema(datasource_id=2)])
        self.assertEqual('target_ambiguous', plan['status'])

    def test_invalid_explicit_mapping_blocks_load(self):
        plan = build_plan(
            self.record_set,
            {'target_table': 'inspection_record', 'datasource_id': 1,
             'field_map': {'设备名称': 'not_a_column'}},
            [schema()])
        self.assertEqual('mapping_incomplete', plan['status'])
        self.assertIn('设备名称', plan['mapping']['invalid_explicit'])

    def test_explicit_mapping_to_trace_column_is_rejected(self):
        target = schema()
        target['columns'].append(
            {'name': 'file_id', 'type': 'bigint', 'comment': '资料ID'})
        plan = build_plan(
            self.record_set,
            {'target_table': 'inspection_record', 'datasource_id': 1,
             'field_map': {'设备名称': 'file_id'}},
            [target])
        self.assertEqual('mapping_incomplete', plan['status'])
        self.assertEqual({'设备名称': 'file_id'},
                         plan['mapping']['invalid_explicit'])

    def test_snapshot_contains_semantic_fields(self):
        plan = build_plan(self.record_set,
                          {'target_table': 'inspection_record', 'datasource_id': 1},
                          [schema()])
        snap = snapshot_from_mapping(plan['mapping'])
        self.assertEqual(['编号', '设备名称', '巡检日期', '异常描述'],
                         [f['name'] for f in snap['fields']])
        self.assertEqual(16, len(snap['hash']))

    def test_partial_snapshot_contains_only_selected_fields(self):
        plan = build_plan(
            self.record_set,
            {'target_table': 'inspection_record', 'datasource_id': 1,
             'field_map': {'设备名称': 'device_name'}},
            [schema()])
        snap = snapshot_from_mapping(plan['mapping'])
        self.assertEqual(['设备名称'], [f['name'] for f in snap['fields']])


if __name__ == '__main__':
    unittest.main()
