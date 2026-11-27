import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from c1_structure import auto_service


class AutoServiceTests(unittest.TestCase):
    def setUp(self):
        self.doc = {'pages': []}
        self.intent = {'description': '设备巡检表', 'target_table': 'inspection'}
        self.spec = {'spec_version': 2, 'fields': [
            {'target': '设备名称', 'pipeline': []}]}
        self.schema = {'fields': [{'name': '设备名称', 'type': 'text'}]}
        self.result = SimpleNamespace(spec=self.spec, schema=self.schema)
        self.recs = [{'index': 0, 'values': {'设备名称': '泵机'}}]
        self.tpl = {'name': '自动规则', 'version': 1, 'version_id': 99,
                    'rule_id': 7, 'mapping_json': self.spec,
                    'transform_json': {}}
        self.task_ctx = {'file_id': 1, 'files': [{'file_id': 1, 'name': 'a.pdf'}]}
        self.log = Mock()

    def _patches(self, plan):
        return [
            patch.object(auto_service.service, 'task_batch'),
            patch.object(auto_service.catalog, 'get_file', return_value={
                'id': 1, 'state': 'to_extract', 'name': 'a.pdf'}),
            patch.object(auto_service.content, 'get_extract',
                         return_value=self.doc),
            patch.object(auto_service.service, 'resolve_rule',
                         return_value=self.tpl),
            patch.object(auto_service.service, 'extract_records',
                         return_value=self.recs),
            patch.object(auto_service.catalog, 'create_rule', return_value=99),
            patch.object(auto_service.catalog, 'clear_load_logs'),
            patch.object(auto_service.catalog, 'list_rules', return_value=[]),
            patch.object(auto_service.content, 'save_records'),
            patch.object(auto_service.catalog, 'set_rule'),
            patch.object(auto_service.catalog, 'set_state'),
            patch.object(auto_service.load_planner, 'plan_for_file',
                         return_value=plan),
            patch.object(auto_service.load_planner, 'get_intent',
                         return_value={}),
            patch.object(auto_service, 'create_and_load'),
            patch.object(auto_service, '_finish'),
        ]

    def test_ready_plan_triggers_automatic_load(self):
        plan = {'status': 'ready', 'message': 'ready'}
        patches = self._patches(plan)
        for p in patches:
            p.start()
        try:
            auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                              self.intent, lambda _doc, _intent: self.result)
            auto_service.create_and_load.assert_called_once_with(1, plan,
                                                                  background=False)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_rule_reuse_rejects_failed_dry_run(self):
        candidate = {'id': 7, 'name': '自动规则', 'current_version_id': 99,
                     'description': self.intent['description']}
        version = dict(self.tpl, mapping_json=self.spec)
        with patch.object(auto_service.catalog, 'list_rules',
                          return_value=[candidate]), \
                patch.object(auto_service.catalog, 'get_rule_version',
                             return_value=version), \
                patch('c1_structure.agent.validate.dry_run',
                      return_value={'records_n': 0, 'empty_fields': [],
                                    'anchor_coverage': 0.0}), \
                patch.object(auto_service.service, 'resolve_rule') as resolve:
            self.assertIsNone(auto_service._find_reusable_rule(
                self.doc, self.intent, self.log))
            resolve.assert_not_called()

    def test_rule_reuse_accepts_passed_dry_run(self):
        candidate = {'id': 7, 'name': '自动规则', 'current_version_id': 99,
                     'description': self.intent['description']}
        version = dict(self.tpl, mapping_json=self.spec)
        with patch.object(auto_service.catalog, 'list_rules',
                          return_value=[candidate]), \
                patch.object(auto_service.catalog, 'get_rule_version',
                             return_value=version), \
                patch('c1_structure.agent.validate.dry_run',
                      return_value={'records_n': 1, 'empty_fields': [],
                                    'anchor_coverage': 1.0}), \
                patch.object(auto_service.service, 'resolve_rule',
                             return_value=self.tpl) as resolve:
            self.assertIs(auto_service._find_reusable_rule(
                self.doc, self.intent, self.log), self.tpl)
            resolve.assert_called_once_with(99)

    def test_reusable_rule_skips_generation_and_new_version(self):
        plan = {'status': 'waiting_target', 'message': 'choose table'}
        patches = self._patches(plan)
        for p in patches:
            p.start()
        generator = Mock()
        try:
            with patch.object(auto_service, '_find_reusable_rule',
                              return_value=self.tpl):
                auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                                  self.intent, generator)
            generator.assert_not_called()
            auto_service.catalog.create_rule.assert_not_called()
            auto_service.catalog.set_rule.assert_called_once_with(1, 99)
            auto_service.service.extract_records.assert_called_once_with(
                self.doc, self.tpl)
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
            self.assertTrue(any('v3 逐行兜底' in str(call)
                                for call in self.log.info.call_args_list))
        finally:
            for p in reversed(patches):
                p.stop()

    def test_v3_rule_does_not_run_row_fallback_again(self):
        self.tpl['mapping_json'] = {'spec_version': 3, 'fields': []}
        patches = self._patches({'status': 'waiting_target', 'message': 'choose'})
        for p in patches:
            p.start()
        try:
            with patch('c1_structure.smart_extract.build_row_fallback') as fallback:
                auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                                  self.intent,
                                  lambda _doc, _intent: self.result)
            fallback.assert_not_called()
        finally:
            for p in reversed(patches):
                p.stop()

    def test_chat_ready_plan_waits_for_confirmation(self):
        plan = {'status': 'ready', 'message': 'ready'}
        patches = self._patches(plan)
        for p in patches:
            p.start()
        try:
            auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                              dict(self.intent, auto_load=False),
                              lambda _doc, _intent: self.result)
            auto_service.create_and_load.assert_not_called()
            auto_service._finish.assert_called_once_with(
                'ready', None, '规划已就绪，等待你确认后写入数据库')
        finally:
            for p in reversed(patches):
                p.stop()

    def test_apply_plan_preserves_confirmed_mapping(self):
        ready = {'status': 'ready', 'message': 'ready'}
        intent = {'target_table': 'inspection', 'auto_load': False,
                  'mapping': {'field_map': {'设备名称': 'device_name'}}}
        with patch.object(auto_service.load_planner, 'plan_for_file',
                          return_value=ready) as plan_for_file, \
                patch.object(auto_service, 'create_and_load',
                             return_value={'ok': True}) as create:
            auto_service.apply_plan(1, intent)
        self.assertEqual({'设备名称': 'device_name'},
                         plan_for_file.call_args.args[1]['field_map'])
        self.assertTrue(create.call_args.args[1]['confirmed'])

    def test_waiting_target_stops_before_load(self):
        plan = {'status': 'waiting_target', 'message': 'choose table'}
        patches = self._patches(plan)
        for p in patches:
            p.start()
        try:
            auto_service._run(['a.pdf'], {}, self.log, self.task_ctx,
                              self.intent, lambda _doc, _intent: self.result)
            auto_service.create_and_load.assert_not_called()
            auto_service._finish.assert_called_once_with(
                'waiting_target', None, 'choose table')
        finally:
            for p in reversed(patches):
                p.stop()

    def test_stub_rule_stops_before_extract(self):
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
            auto_service.service.extract_records.assert_not_called()
            auto_service.create_and_load.assert_not_called()
        finally:
            for p in reversed(patches):
                p.stop()

    def test_create_and_load_rejects_unconfirmed_chat_plan(self):
        plan = {'status': 'ready', 'target': {'datasource_id': 2,
                'table': 'inspection'},
                'mapping': {'complete': True, 'field_map': {}, 'fields': []}}
        with patch.object(auto_service.load_planner, 'get_intent',
                          return_value={'auto_load': False}), \
                patch.object(auto_service.catalog, 'get_file', return_value={
                    'state': 'to_review'}), \
                patch.object(auto_service.service, 'launch_load') as launch:
            with self.assertRaises(auto_service.Conflict):
                auto_service.create_and_load(1, plan, background=True)
            launch.assert_not_called()

    def test_bound_target_cannot_be_silently_changed(self):
        plan = {
            'status': 'ready',
            'target': {'datasource_id': 2, 'table': 'new_table'},
            'mapping': {'complete': True, 'field_map': {}, 'fields': []},
        }
        with patch.object(auto_service.load_planner, 'get_intent',
                          return_value={}), \
                patch.object(auto_service.catalog, 'get_file', return_value={
                'state': 'to_load', 'load_table_id': 55}), \
                patch.object(auto_service.catalog, 'get_load_table',
                             return_value={'datasource_id': 2,
                                           'target_table': 'old_table'}), \
                patch.object(auto_service.service, 'launch_load') as launch:
            with self.assertRaises(auto_service.Conflict):
                auto_service.create_and_load(1, plan, background=False)
            launch.assert_not_called()

    def test_create_and_load_builds_mapping_and_uses_auto_gate(self):
        plan = {
            'status': 'ready',
            'target': {'datasource_id': 2, 'table': 'inspection'},
            'mapping': {
                'complete': True, 'write_mode': 'upsert',
                'business_key': ['equipment_code'],
                'field_map': {'设备编号': 'equipment_code',
                              '设备名称': 'equipment_name'},
                'fields': [{'name': '设备编号', 'type': 'text'},
                           {'name': '设备名称', 'type': 'text'}],
            },
        }
        with patch.object(auto_service.load_planner, 'get_intent',
                          return_value={}), \
                patch.object(auto_service.catalog, 'get_file', return_value={
                'state': 'to_review', 'rule_version_id': 99}), \
                patch.object(auto_service.service, 'resolve_rule',
                             return_value=self.tpl), \
                patch.object(auto_service.catalog, 'create_load_table',
                             return_value=55) as create, \
                patch.object(auto_service.service, 'launch_load',
                             return_value={'ok': True}) as launch:
            auto_service.create_and_load(1, plan, background=False)
        fields = create.call_args.args[4]
        self.assertEqual('equipment_code', fields[0]['target_column'])
        self.assertTrue(fields[0]['is_business_key'])
        launch.assert_called_once_with(
            1, {'datasource_id': 2, 'load_table_id': 55},
            auto=True, background=False)


if __name__ == '__main__':
    unittest.main()
