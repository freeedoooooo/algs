-- 004_result_value_only.sql — 结果表极简：只存「定义 ID + 结果值 + 时间」。
-- 变更依据：用户裁决 2026-11-26——结果表不需要行锚点、依赖 ID、输入明细；
--   参与计算的对象从定义表（rule_info.index_refs / frame_info.rule_refs）推导；
--   结果字段统一命名为 index_value / rule_value / frame_value。
-- 影响：仅重建 3 张结果表；3 张定义表（c1_*_info）不动；001 基线表不动。
-- 幂等：DROP IF EXISTS + CREATE IF NOT EXISTS。执行会清空既有计算结果。

DROP TABLE IF EXISTS `c1_frame_value`;
DROP TABLE IF EXISTS `c1_rule_value`;
DROP TABLE IF EXISTS `c1_index_value`;

CREATE TABLE IF NOT EXISTS `c1_index_value` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '结果 ID',
  `index_id` bigint NOT NULL COMMENT '指标定义 ID',
  `index_value` varchar(64) NOT NULL COMMENT '指标结果值',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_index_value_def` (`index_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指标结果：仅定义 ID + 结果值';

CREATE TABLE IF NOT EXISTS `c1_rule_value` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '结果 ID',
  `rule_id` bigint NOT NULL COMMENT '规则定义 ID',
  `rule_value` varchar(64) NOT NULL COMMENT '规则结果（pass/fail）',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_rule_value_def` (`rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='规则结果：仅定义 ID + 结果值';

CREATE TABLE IF NOT EXISTS `c1_frame_value` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '结果 ID',
  `frame_id` bigint NOT NULL COMMENT '框架定义 ID',
  `frame_value` varchar(64) NOT NULL COMMENT '框架结果（得分或结论）',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_frame_value_def` (`frame_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='框架结果：仅定义 ID + 结果值';
