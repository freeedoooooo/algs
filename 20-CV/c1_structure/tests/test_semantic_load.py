import unittest

from c1_structure.store import semantic_load


def _records(values):
    return {'schema': 'c1-structure-records/1', 'files': [{'records': [
        {'index': i, 'values': row, 'original': row, 'lineage': {},
         'review': {'state': 'pending', 'at': None}}
        for i, row in enumerate(values)]}]}


def _table(name='equipment_inspection', comment='设备巡检记录'):
    return {
        'name': name,
        'comment': comment,
        'columns': [
            {'name': 'document_no', 'type': 'varchar', 'comment': '单据编号'},
            {'name': 'equipment_code', 'type': 'varchar', 'comment': '设备编号'},
            {'name': 'equipment_name', 'type': 'varchar', 'comment': '设备名称'},
            {'name': 'inspection_date', 'type': 'date', 'comment': '巡检日期'},
            {'name': 'abnormal_desc', 'type': 'text', 'comment': '异常描述'},
            {'name': 'id', 'type': 'bigint', 'comment': '自增主键', 'primary': True},
        ],
    }


class SemanticLoadTest(unittest.TestCase):
    def setUp(self):
        self.records = _records([{
            '单据编号': 'XC-001',
            '设备编号': 'EQ-001',
            '设备名称': '1号泵',
            '巡检日期': '2026-11-27',
            '异常描述': '轴承温度偏高',
        }])

    def test_maps_chinese_fields_to_physical_columns(self):
        result = semantic_load.map_fields(self.records, _table())
        self.assertTrue(result['complete'])
        self.assertEqual(result['field_map'], {
            '单据编号': 'document_no',
            '设备编号': 'equipment_code',
            '设备名称': 'equipment_name',
            '巡检日期': 'inspection_date',
            '异常描述': 'abnormal_desc',
        })
        self.assertEqual(result['write_mode'], 'insert')

    def test_explicit_mapping_wins(self):
        result = semantic_load.map_fields(
            self.records, _table(), explicit={'设备编号': 'equipment_code'})
        self.assertEqual(result['field_map']['设备编号'], 'equipment_code')
        self.assertEqual(result['confidence']['设备编号'], 1.0)

    def test_explicit_mapping_can_disable_automatic_prefill(self):
        result = semantic_load.map_fields(
            self.records, _table(), explicit={'设备编号': 'equipment_code'},
            auto_map=False)
        self.assertEqual({'设备编号': 'equipment_code'}, result['field_map'])
        self.assertEqual(
            {'单据编号', '设备名称', '巡检日期', '异常描述'},
            set(result['unmapped_fields']))

    def test_mapping_exposes_selectable_database_columns(self):
        result = semantic_load.map_fields(self.records, _table())
        self.assertIn('equipment_name',
                      [column['name'] for column in result['available_columns']])

    def test_trace_columns_are_not_mapping_candidates(self):
        table = _table()
        table['columns'].extend([
            {'name': 'file_id', 'type': 'bigint', 'comment': '资料ID'},
            {'name': 'record_id', 'type': 'bigint', 'comment': '记录ID'},
        ])
        result = semantic_load.map_fields(self.records, table)
        selectable = [column['name'] for column in result['available_columns']]
        self.assertNotIn('file_id', selectable)
        self.assertNotIn('record_id', selectable)
        self.assertNotIn('file_id', result['field_map'].values())
        self.assertNotIn('record_id', result['field_map'].values())

    def test_unmapped_field_blocks_complete_mapping(self):
        records = _records([{'设备编号': 'EQ-001', '不存在的字段': 'x'}])
        result = semantic_load.map_fields(records, _table())
        self.assertFalse(result['complete'])
        self.assertIn('不存在的字段', result['unmapped_fields'])

    def test_recommendation_prefers_matching_table(self):
        tables = [_table(), _table('equipment_repair', '设备维修记录')]
        result = semantic_load.recommend_tables(
            self.records, tables, intent='设备巡检表，写入巡检记录')
        self.assertEqual(result[0]['table'], 'equipment_inspection')
        self.assertGreaterEqual(result[0]['score'], 0.5)

    def test_explicit_table_name_reranks_recommendation(self):
        tables = [_table(), _table('equipment_repair', '设备维修记录')]
        result = semantic_load.recommend_tables(
            self.records, tables, intent='设备巡检，写入 equipment_repair')
        self.assertEqual('equipment_repair', result[0]['table'])
        self.assertIn('需求中明确提到目标表名', result[0]['reasons'])

    def test_complete_mapping_adds_rerank_reason(self):
        partial = _table('equipment_inspection_partial', '设备巡检记录')
        partial['columns'] = [c for c in partial['columns']
                              if c['name'] != 'abnormal_desc']
        result = semantic_load.recommend_tables(
            self.records, [_table(), partial], intent='设备巡检')
        self.assertEqual('equipment_inspection', result[0]['table'])
        self.assertIn('字段可完整映射', result[0]['reasons'])
        self.assertNotIn('字段可完整映射', result[1]['reasons'])

    def test_table_name_match_requires_token_boundary(self):
        self.assertFalse(semantic_load._mentions_table(
            '写入 equipment_repair_log', 'equipment_repair'))
        self.assertTrue(semantic_load._mentions_table(
            '写入 db.equipment_repair', 'equipment_repair'))

    def test_no_fields_means_no_recommendation(self):
        self.assertEqual(semantic_load.recommend_tables(
            _records([]), [_table()], intent='设备巡检'), [])

    def test_infer_common_value_types(self):
        self.assertEqual(semantic_load.infer_value_type(['1', '2']), 'integer')
        self.assertEqual(semantic_load.infer_value_type(['1.5']), 'decimal')
        self.assertEqual(semantic_load.infer_value_type(['2026-11-27']), 'date')
        self.assertEqual(semantic_load.infer_value_type(['2026-11-27T10:00:00']),
                         'datetime')
        self.assertEqual(semantic_load.infer_value_type(['设备A']), 'text')


if __name__ == '__main__':
    unittest.main()
