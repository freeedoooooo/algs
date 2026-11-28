import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from c1_structure import logging_config, stage_summary, tasklog
from c1_structure.store import loader


class StageSummaryTests(unittest.TestCase):
    def test_parse_summary_counts_lightweight_metadata(self):
        doc = {
            'file': {'name': 'sample.csv', 'kind': 'csv', 'page_count': 1},
            'pages': [{'texts': [{'text': 'abc'}, {'text': 'de'}],
                       'blocks': [{'text': 'abc'}],
                       'tables': [{'headers': ['日期'], 'rows': []}]}],
            'stitched_tables': [{'headers': ['日期']}],
        }
        result = stage_summary.parse_summary(doc, ['parse.json', '对照报告.html'])
        self.assertEqual(1, result['page_count'])
        self.assertEqual(2, result['text_fragments'])
        self.assertEqual(2, result['table_count'])
        self.assertEqual(5, result['text_chars'])
        self.assertTrue(result['report_available'])

    def test_extract_summary_caps_samples_and_counts_lineage(self):
        records = {'files': [{'records': [
            {'index': i, 'values': {'金额': i, '编码': '001'},
             'lineage': {'金额': {'page': 1}} if i == 0 else {},
             'review': {'state': 'confirmed'}}
            for i in range(5)]}]}
        result = stage_summary.extract_summary(records)
        self.assertEqual(5, result['record_count'])
        self.assertEqual(['金额', '编码'], result['fields'])
        self.assertEqual(3, len(result['samples']))
        self.assertEqual(1, result['anchored_records'])
        self.assertEqual({'confirmed': 5}, result['review_counts'])

    def test_missing_stage_results_are_explicit(self):
        self.assertEqual('missing', stage_summary.parse_summary(None)['status'])
        self.assertEqual('empty', stage_summary.extract_summary(
            {'files': [{'records': []}]})['status'])


class BusinessTableTests(unittest.TestCase):
    def test_platform_tables_are_excluded(self):
        with patch.object(loader, 'list_tables', return_value=[
                'biz_order', 'c1_doc_file', 'C1_RULE_INFO', 'biz_customer']):
            self.assertEqual(['biz_order', 'biz_customer'],
                             loader.list_business_tables({'id': 1}))

    def test_explicit_schema_list_also_excludes_platform_tables(self):
        with patch.object(loader, 'connect_datasource') as connect:
            self.assertEqual([], loader.list_table_schemas(
                {'id': 1, 'db_name': 'platform'}, ['c1_doc_file']))
        connect.assert_not_called()


class LoggingTests(unittest.TestCase):
    def test_console_configuration_is_idempotent_and_standard(self):
        logger = logging_config.configure_logging()
        again = logging_config.configure_logging()
        handlers = [h for h in logger.handlers
                    if h.name == logging_config._HANDLER_NAME]
        self.assertIs(logger, again)
        self.assertEqual(1, len(handlers))
        self.assertEqual(logging_config._FORMAT,
                         handlers[0].formatter._fmt)

    def test_task_log_keeps_rows_and_uses_standard_logger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'task.log'
            log = tasklog.TaskLog('test', log_path=str(path))
            with self.assertLogs('c1_structure.tasklog', level='INFO') as logs:
                row = log.ok('extract', '抽取完成', event='extract_complete')
            self.assertEqual('extract_complete', row['event'])
            self.assertEqual([row], log.rows())
            self.assertIn('c1_structure.tasklog', logs.output[0])
            self.assertIn('抽取完成', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
