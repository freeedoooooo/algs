import unittest

from c1_structure.agent import rule_reuse


class RuleReuseTests(unittest.TestCase):
    def setUp(self):
        self.description = '提取设备巡检表中的设备名称、巡检日期和异常描述'
        self.rule = {'id': 1, 'name': '自动规则', 'description': self.description,
                     'current_version_id': 11, 'updated_at': '2026-11-28'}

    def test_exact_description_reuses_current_version(self):
        candidate = rule_reuse.best_candidate(self.description, [self.rule])
        self.assertEqual(11, candidate['current_version_id'])
        self.assertEqual(1.0, candidate['reuse_score'])

    def test_unrelated_description_does_not_reuse(self):
        self.assertIsNone(rule_reuse.best_candidate(
            '提取发票购买方和税号', [self.rule]))

    def test_rule_without_current_version_is_ignored(self):
        self.assertIsNone(rule_reuse.best_candidate(
            self.description, [dict(self.rule, current_version_id=None)]))

    def test_best_candidate_prefers_higher_similarity(self):
        other = dict(self.rule, id=2, current_version_id=22,
                     description='设备巡检表')
        candidate = rule_reuse.best_candidate(self.description, [other, self.rule])
        self.assertEqual(11, candidate['current_version_id'])

    def test_acceptable_requires_records_fields_and_anchors(self):
        good = {'records_n': 2, 'empty_fields': [], 'anchor_coverage': 0.95}
        self.assertTrue(rule_reuse.acceptable(good))
        self.assertFalse(rule_reuse.acceptable(dict(good, records_n=0)))
        self.assertFalse(rule_reuse.acceptable(dict(good, empty_fields=['日期'])))
        self.assertFalse(rule_reuse.acceptable(dict(good, anchor_coverage=0.94)))
        self.assertFalse(rule_reuse.acceptable({'error': 'bad'}))


if __name__ == '__main__':
    unittest.main()
