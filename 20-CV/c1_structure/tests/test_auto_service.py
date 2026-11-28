import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from c1_structure import auto_service
from c1_structure.store import loader


class AutoServiceTests(unittest.TestCase):
    def setUp(self):
        self.doc = {'pages': []}
        self.intent = {'description': '设备巡检表', 'target_table': 'inspection'}
        self.spec = {'spec_version': 2, 'fields': [
            {'target': '设备名称', 'pipeline': []}]}
        self.schema = {'fields': [{'name': '设备名称', 'type': 'text'}]}
        self.result = SimpleNamespace(spec=self.spec, schema=self.schema)
        self.recs = [{'index': 0, 'values': {'设备名称': '泵机'}}]
        self.tpl = {'name': '自动规则', 'rule_id': 7,
                    'output_schema_json': self.schema,
                    'extraction_spec_json': self.spec, 'transform_json': None}
        self.task_ctx = {'file_id': 1, 'files': [{'file_id': 1, 'name': 'a.pdf'}]}
        self.log = Mock()
        self.state = patch.dict(auto_service.service.STATE,
                                {'running': False, 'started': 1, 'extract_results': []})
        self.state.start()
        self.addCleanup(self.state.stop)

    def _patches(self, plan, *, rules=None, result_ids=None):
        resolved = rules or [self.tpl]
        return [
            patch.object(auto_service.service, 'task_batch'),
            patch.object(auto_service.catalog, 'get_file', return_value={
                'id': 1, 'state': 'to_extract', 'name': 'a.pdf'}),
            patch.object(auto_service.content, 'get_extract', return_value=self.doc),
            patch.object(auto_service.service, 'resolve_rule',
                         side_effect=lambda rule_id: next(
                             t for t in resolved if t['rule_id'] == rule_id)),
            patch.object(auto_service.service, 'extract_records',
                         return_value=self.recs),
            patch.object(auto_service.catalog, 'create_rule',
                         side_effect=[t['rule_id'] for t in resolved]),
            patch.object(auto_service.catalog, 'ensure_extract_result',
                         side_effect=list(result_ids or [31])),
            patch.object(auto_service.content_db, 'save_records'),
            patch.object(auto_service.catalog, 'finish_extract_result'),
            patch.object(auto_service.catalog, 'list_rules', return_value=[]),
            patch.object(auto_service.catalog, 'set_state'),
            (patch.object(auto_service.load_planner, 'plan_for_extract_result',
                          side_effect=plan) if isinstance(plan, list) else
             patch.object(auto_service.load_planner, 'plan_for_extract_result',
                          return_value=plan)),
            patch.object(auto_service.load_planner, 'save_intent'),
            patch.object(auto_service.service, 'launch_load'),
            patch.object(auto_service.catalog, 'create_binding'),
            patch.object(auto_service, '_finish'),
        ]

    def _run(self, plan, generator=None, intent=None, extractor=None, **kwargs):
        patches = self._patches(plan, **kwargs)
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(patches)])
        if extractor is not None:
            auto_service.service.extract_records.side_effect = extractor
        auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                          intent or self.intent,
                          generator or (lambda _doc, _intent: self.result))

    def test_ready_plan_never_writes_automatically(self):
        self._run({'status': 'ready', 'message': 'ready'})
        auto_service.service.launch_load.assert_not_called()
        auto_service.catalog.create_binding.assert_not_called()
        auto_service.content_db.save_records.assert_called_once_with(31, self.recs)
        auto_service.load_planner.plan_for_extract_result.assert_called_once_with(
            31, datasource_code=None, table_intent=self.intent)
        auto_service.catalog.set_state.assert_called_with(1, 'to_review', None)
        self.assertEqual([31], [r['extract_result_id']
                                for r in auto_service.service.STATE['extract_results']])
        auto_service._finish.assert_called_once_with(
            'ready', None, '已生成1个抽取结果；聊天写库须逐条显式确认')

    def test_automatic_flow_produces_independent_results_and_plans(self):
        second = SimpleNamespace(
            spec={'spec_version': 2, 'fields': [
                {'target': '巡检日期', 'pipeline': []}]},
            schema={'fields': [{'name': '巡检日期', 'type': 'date'}]})
        plans = [{'status': 'ready', 'message': '设备表就绪'},
                 {'status': 'waiting_target', 'message': '日期待选表'}]
        rules = [self.tpl, dict(self.tpl, name='日期规则', rule_id=8,
                                extraction_spec_json=second.spec,
                                output_schema_json=second.schema)]
        intent = dict(self.intent, targets=[
            {'target_table': 'equipment'}, {'target_table': 'inspection_log'}])
        equipment_records = [{'index': 0, 'values': {'设备名称': '泵机'}}]
        date_records = [{'index': 0, 'values': {'巡检日期': '2026-11-28'}}]
        self._run(
            plans, generator=lambda _doc, _intent: [self.result, second],
            intent=intent, rules=rules, result_ids=[31, 32],
            extractor=lambda _doc, tpl: (
                equipment_records if tpl['rule_id'] == 7 else date_records))
        planner = auto_service.load_planner.plan_for_extract_result
        self.assertEqual(2, auto_service.content_db.save_records.call_count)
        self.assertEqual([(31, equipment_records), (32, date_records)],
                         [c.args for c in auto_service.content_db.save_records.call_args_list])
        self.assertEqual([7, 8], [c.args[1]
                                   for c in auto_service.catalog.ensure_extract_result.call_args_list])
        self.assertEqual([31, 32], [c.args[0]
                                   for c in planner.call_args_list])
        self.assertEqual('equipment', planner.call_args_list[0].kwargs['table_intent']['target_table'])
        self.assertEqual('inspection_log', planner.call_args_list[1].kwargs['table_intent']['target_table'])
        summaries = auto_service.service.STATE['extract_results']
        self.assertEqual([31, 32], [s['extract_result_id'] for s in summaries])
        self.assertEqual([7, 8], [s['rule_id'] for s in summaries])
        auto_service.service.launch_load.assert_not_called()
        auto_service.catalog.create_binding.assert_not_called()
        self.assertEqual('results_ready', auto_service._finish.call_args.args[0])

    def test_rule_reuse_rejects_candidate_without_resolving(self):
        with patch('c1_structure.agent.rule_reuse.best_candidate', return_value=None), \
                patch.object(auto_service.catalog, 'list_rules', return_value=[]), \
                patch.object(auto_service.service, 'resolve_rule') as resolve:
            self.assertIsNone(auto_service._find_reusable_rule(
                self.doc, self.intent, self.log))
            resolve.assert_not_called()

    def test_rule_reuse_resolves_single_rule_row(self):
        candidate = {'id': 7, 'name': '自动规则', 'reuse_score': 0.9}
        with patch('c1_structure.agent.rule_reuse.best_candidate',
                   return_value=candidate), \
                patch.object(auto_service.catalog, 'list_rules', return_value=[]), \
                patch.object(auto_service.service, 'resolve_rule',
                             return_value=self.tpl) as resolve:
            self.assertIs(auto_service._find_reusable_rule(
                self.doc, self.intent, self.log), self.tpl)
        resolve.assert_called_once_with(7)

    def test_reusable_rule_skips_generation_and_version_creation(self):
        patches = self._patches({'status': 'waiting_target', 'message': 'choose table'})
        for p in patches:
            p.start()
        try:
            generator = Mock()
            with patch.object(auto_service, '_find_reusable_rule',
                              return_value=self.tpl):
                auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                                  self.intent, generator)
            generator.assert_not_called()
            auto_service.catalog.create_rule.assert_not_called()
            auto_service.service.extract_records.assert_called_once_with(
                self.doc, self.tpl)
            auto_service.catalog.ensure_extract_result.assert_called_once()
            events = [c.kwargs.get('event') for c in self.log.stage.call_args_list
                      + self.log.ok.call_args_list]
            self.assertIn('parse_complete', events)
            self.assertIn('extract_complete', events)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_auto_processing_runs_bounded_row_fallback(self):
        patches = self._patches({'status': 'waiting_target', 'message': 'choose'})
        for p in patches:
            p.start()
        try:
            recovered = [{'index': 0, 'values': {'设备名称': '泵机'}}]
            diag = {'attempted': 1, 'filled': 1, 'failed': []}
            with patch('c1_structure.smart_extract.build_row_fallback',
                       return_value=(recovered, diag)) as fallback:
                auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                                  self.intent,
                                  lambda _doc, _intent: self.result)
            fallback.assert_called_once_with(self.doc, self.tpl, self.recs)
            auto_service.content_db.save_records.assert_called_once_with(
                31, recovered)
            self.assertTrue(any('补全1个字段' in str(c)
                                for c in self.log.info.call_args_list))
        finally:
            for p in reversed(patches):
                p.stop()

    def test_v3_rule_does_not_run_row_fallback_again(self):
        self.tpl['extraction_spec_json'] = {'spec_version': 3, 'fields': []}
        patches = self._patches({'status': 'waiting_target', 'message': 'choose'})
        for p in patches:
            p.start()
        try:
            with patch('c1_structure.smart_extract.build_row_fallback') as fallback:
                auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                                  self.intent, lambda _doc, _intent: self.result)
            fallback.assert_not_called()
        finally:
            for p in reversed(patches):
                p.stop()

    def test_stub_rule_stops_before_result_creation(self):
        patches = self._patches({'status': 'ready'})
        for p in patches:
            p.start()
        try:
            empty = SimpleNamespace(
                spec={'spec_version': 2, 'fields': [], '_stub': True},
                schema={'fields': []})
            auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                              self.intent, lambda _doc, _intent: empty)
            auto_service.catalog.create_rule.assert_not_called()
            auto_service.catalog.ensure_extract_result.assert_not_called()
            auto_service.service.extract_records.assert_not_called()
            auto_service.service.launch_load.assert_not_called()
            self.assertEqual('rule_empty', auto_service._finish.call_args.args[0])
            auto_service.catalog.set_state.assert_called_once_with(
                1, 'to_review', '自动规则未生成有效字段')
        finally:
            for p in reversed(patches):
                p.stop()

    def test_apply_plan_requires_literal_explicit_confirmation_before_any_write(self):
        for value in (None, False, 1, 'true', {}, []):
            with self.subTest(confirmed=value), \
                    patch.object(auto_service.load_planner,
                                 'plan_for_extract_result') as planner, \
                    patch.object(auto_service.catalog, 'create_binding') as create, \
                    patch.object(auto_service.content_db, 'set_review') as review, \
                    patch.object(auto_service.service, 'launch_load') as launch:
                with self.assertRaises(auto_service.Conflict):
                    auto_service.apply_plan(31, {'confirmed': value})
                planner.assert_not_called()
                create.assert_not_called()
                review.assert_not_called()
                launch.assert_not_called()

    def test_apply_plan_preserves_partial_mapping_and_confirms_only_result(self):
        ready = {'status': 'ready', 'message': 'ready',
                 'target': {'datasource_id': 2, 'datasource_code': 'biz',
                            'table': 'inspection',
                            'table_code': 'biz.inspection'},
                 'mapping': {'complete': True, 'write_mode': 'upsert',
                             'business_key': ['equipment_code'],
                             'field_map': {'设备编号': 'equipment_code',
                                           '设备名称': 'equipment_name'},
                             'available_columns': [
                                 {'name': 'equipment_code', 'type': 'varchar'},
                                 {'name': 'equipment_name', 'type': 'varchar'},
                                 {'name': 'ignored_note', 'type': 'text'}]}}
        records = [{'index': i, 'values': {}, 'review': {'state': state}}
                   for i, state in enumerate(('pending', 'edited', 'confirmed'))]
        intent = {'confirmed': True, 'target_table': 'inspection',
                  'datasource_id': 2, 'datasource_code': 'biz',
                  'field_map': ready['mapping']['field_map'],
                  'write_mode': 'upsert', 'business_keys': ['equipment_code']}
        with patch.object(auto_service.load_planner, 'plan_for_extract_result',
                          return_value=ready) as planner, \
                patch.object(auto_service.catalog, 'get_extract_result',
                             return_value={'id': 31, 'doc_id': 1}), \
                patch.object(auto_service.catalog, 'get_binding',
                             return_value=None), \
                patch.object(auto_service.catalog, 'list_load_tables',
                             return_value=[{'id': 55, 'datasource_id': 2,
                                            'datasource_code': 'biz',
                                            'target_table': 'inspection',
                                            'fields': ready['mapping']['available_columns']}]), \
                patch.object(auto_service.catalog, 'create_binding',
                             return_value=55) as create, \
                patch.object(auto_service.content_db, 'get_records',
                             return_value={'records': records}), \
                patch.object(auto_service.content_db, 'set_review') as review, \
                patch.object(auto_service.catalog, 'confirm_binding') as confirm, \
                patch.object(auto_service.service, 'launch_load',
                             return_value={'ok': True}) as launch:
            self.assertEqual({'ok': True}, auto_service.apply_plan(31, intent))
        planner.assert_called_once_with(31, datasource_code='biz', table_intent=intent)
        create.assert_called_once_with(
            31, 55, {'设备编号': 'equipment_code', '设备名称': 'equipment_name'},
            'upsert', ['equipment_code'])
        review.assert_called_once_with(31, [0, 1], 'confirmed')
        confirm.assert_called_once_with(55)
        launch.assert_called_once_with(31, background=True)

    def test_apply_plan_blocks_incomplete_or_empty_mapping_before_writes(self):
        for plan in (
            {'status': 'mapping_incomplete', 'message': 'bad'},
            {'status': 'ready', 'message': 'ready',
             'target': {'datasource_id': 2, 'datasource_code': 'biz',
                        'table': 'inspection'},
             'mapping': {'field_map': {}}},
        ):
            with self.subTest(plan=plan), \
                    patch.object(auto_service.load_planner,
                                 'plan_for_extract_result', return_value=plan), \
                    patch.object(auto_service.catalog, 'create_binding') as create, \
                    patch.object(auto_service.service, 'launch_load') as launch:
                with self.assertRaises(auto_service.Conflict):
                    auto_service.apply_plan(31, {'confirmed': True})
                create.assert_not_called()
                launch.assert_not_called()

    def test_apply_plan_cannot_retarget_confirmed_binding(self):
        plan = {'status': 'ready', 'message': 'ready',
                'target': {'datasource_id': 2, 'datasource_code': 'biz',
                           'table': 'other'},
                'mapping': {'field_map': {'设备名称': 'device_name'}}}
        binding = {'id': 55, 'status': 'confirmed'}
        with patch.object(auto_service.load_planner, 'plan_for_extract_result',
                          return_value=plan), \
                patch.object(auto_service.catalog, 'get_extract_result',
                             return_value={'id': 31, 'doc_id': 1}), \
                patch.object(auto_service.catalog, 'get_binding', return_value=binding), \
                patch.object(auto_service, '_target_table', return_value={'id': 55}), \
                patch.object(auto_service.catalog, 'update_binding') as update, \
                patch.object(auto_service.service, 'launch_load') as launch:
            with self.assertRaises(auto_service.Conflict):
                auto_service.apply_plan(31, {'confirmed': True})
            update.assert_not_called()
            launch.assert_not_called()


class PartialWriteTests(unittest.TestCase):
    def test_write_record_excludes_unmapped_fields(self):
        class Cursor:
            lastrowid = 7

            def __init__(self):
                self.sql = None
                self.params = None

            def execute(self, sql, params):
                self.sql, self.params = sql, params

        cur = Cursor()
        action, pk = loader.write_record(
            cur, 'inspection', {'设备名称': 'device_name'},
            {'设备名称': '泵机', '忽略字段': '不写入'}, 'insert', [],
            extra_values={'file_id': 1, 'record_id': 2})
        self.assertEqual('insert', action)
        self.assertEqual('7', pk)
        self.assertIn('`device_name`,`file_id`,`record_id`', cur.sql)
        self.assertNotIn('忽略字段', cur.sql)
        self.assertEqual(['泵机', 1, 2], cur.params)

    def test_preflight_accepts_partial_mapping_with_all_source_fields(self):
        from c1_structure.store import loader as loader_mod
        fields = ['设备名称', '设备编号', '备注']
        mapping = {'设备名称': 'device_name'}
        with patch.object(loader_mod, 'list_columns', return_value=[
                {'name': 'device_name'}, {'name': 'equipment_code'},
                {'name': 'note'}, {'name': 'file_id'}, {'name': 'record_id'}]):
            self.assertEqual(
                ['device_name', 'equipment_code', 'note', 'file_id', 'record_id'],
                loader_mod.preflight({'id': 2}, 'inspection', mapping,
                                     'insert', fields))
            with self.assertRaises(loader_mod.BadRequest):
                loader_mod.preflight({'id': 2}, 'inspection',
                                     {'设备名称': 'device_name',
                                      '设备编号': 'equipment_code'},
                                     'upsert', fields)


if __name__ == '__main__':
    unittest.main()
