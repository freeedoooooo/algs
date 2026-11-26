-- 003_simplify_value.sql — 计算层简化：去版本 / 去哈希 / 去配置快照副本。
-- 变更依据：用户裁决 2026-11-26（简化设计）。
--   · 定义表 c1_*_info：去掉 version、spec_hash；同名唯一（name 为 UK），保存即覆盖更新。
--   · 结果表 c1_*_value：去掉 *_version、result_hash；input_rows_json 只留血缘锚点
--     {rows:[{file_id,record_id,value}], matched_rows, truncated}；
--     detail_json 只留实际值/结论，不留阈值、权重等配置副本。
-- 注意：本脚本会 DROP 并重建 002 建的 6 张表（均为本次实验性新表，无历史业务数据）。
--       执行前请确认：这 6 表中的演示数据将清空，需按 demo 脚本 §6 重建。
-- 幂等：DROP IF EXISTS + CREATE IF NOT EXISTS，重复执行无副作用。

DROP TABLE IF EXISTS `c1_frame_value`;
DROP TABLE IF EXISTS `c1_rule_value`;
DROP TABLE IF EXISTS `c1_index_value`;
DROP TABLE IF EXISTS `c1_frame_info`;
DROP TABLE IF EXISTS `c1_rule_info`;
DROP TABLE IF EXISTS `c1_index_info`;

-- ① 指标定义：同名唯一，无版本、无哈希
CREATE TABLE IF NOT EXISTS `c1_index_info` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '指标名（唯一）',
  `datasource_id` bigint NOT NULL COMMENT '业务库 ID',
  `source_table` varchar(128) NOT NULL COMMENT '业务表名（白名单校验）',
  `source_column` varchar(128) DEFAULT NULL COMMENT '聚合列（NULL=COUNT(*)）',
  `aggregate` varchar(24) NOT NULL COMMENT 'sum/count/avg/min/max/count_distinct',
  `filter_json` json DEFAULT NULL COMMENT '可选过滤 [{column,op,value}]',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_index_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指标定义：同名唯一，保存即更新';

-- ② 规则定义
CREATE TABLE IF NOT EXISTS `c1_rule_info` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '规则名（唯一）',
  `index_refs_json` json NOT NULL COMMENT '引用指标 [{index_id,alias}]',
  `conditions_json` json NOT NULL COMMENT '条件 [{alias,op,threshold}]',
  `combine` varchar(16) NOT NULL DEFAULT 'all' COMMENT 'all/any',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rule_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='业务规则定义：同名唯一';

-- ③ 框架定义
CREATE TABLE IF NOT EXISTS `c1_frame_info` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL COMMENT '框架名（唯一）',
  `rule_refs_json` json NOT NULL COMMENT '引用规则 [{rule_id,weight,veto}]',
  `combine` varchar(24) NOT NULL DEFAULT 'weighted' COMMENT 'weighted/all_pass/any_pass/veto',
  `threshold` decimal(12,4) DEFAULT NULL COMMENT '加权通过阈值',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_frame_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='框架定义：同名唯一';

-- ④ 指标结果：只留血缘锚点，无版本、无哈希、无配置副本
CREATE TABLE IF NOT EXISTS `c1_index_value` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `index_id` bigint NOT NULL COMMENT '指标定义 ID',
  `value_text` varchar(64) NOT NULL COMMENT '指标值',
  `input_rows_json` json NOT NULL COMMENT '血缘锚点 {rows:[{file_id,record_id,value}],matched_rows,truncated}',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_index_value_def` (`index_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指标结果：仅血缘锚点';
CREATE TABLE IF NOT EXISTS `c1_rule_value` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `rule_id` bigint NOT NULL COMMENT '规则定义 ID',
  `index_value_ids_json` json NOT NULL COMMENT '依赖的指标结果 ID',
  `outcome` varchar(8) NOT NULL COMMENT 'pass/fail',
  `detail_json` json NOT NULL COMMENT '逐条件实际值 [{alias,actual,passed}]',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_rule_value_def` (`rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='规则结果：仅依赖 ID + 实际值';
CREATE TABLE IF NOT EXISTS `c1_frame_value` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `frame_id` bigint NOT NULL COMMENT '框架定义 ID',
  `rule_value_ids_json` json NOT NULL COMMENT '依赖的规则结果 ID',
  `outcome` varchar(8) NOT NULL COMMENT 'pass/fail',
  `score_text` varchar(64) DEFAULT NULL COMMENT '综合得分',
  `detail_json` json NOT NULL COMMENT '逐规则结论 [{rule_value_id,outcome,contribution}]',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_frame_value_def` (`frame_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='框架结果：仅依赖 ID + 结论';
