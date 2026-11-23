-- 004_nullable_rule_binding.sql — 方案A：解析不绑抽取规则
-- c1_task.rule_version_id 改为可空：上传只解析时 NULL，「执行抽取」时刻回写绑定。
-- 可重跑（MODIFY 幂等）。存量行均有 rule_version_id（历史＝抽取时写入），无需回填。

ALTER TABLE `c1_task`
  MODIFY COLUMN `rule_version_id` BIGINT NULL;
