-- 002_index_rule_frame.sql — 计算层增量 DDL：指标 / 规则 / 框架。
-- 前缀：index / rule / frame；后缀：_info（定义）、_value（结果）。
-- 用途：叠加在 001_file_baseline.sql 之上的增量建表（人工执行，无自动迁移器）。
-- 幂等：全 IF NOT EXISTS，重复执行无副作用；不 DROP、不改存量表。
-- 设计依据：docs/design-index-rule-frame.md §5。

-- ① 指标定义：一行 = 一个版本；同名取 MAX(version) 为当前版
CREATE TABLE IF NOT EXISTS `c1_index_info` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '指标定义版本 ID',
  `name` varchar(128) NOT NULL COMMENT '指标名',
  `version` int NOT NULL COMMENT '版本号（同名内递增）',
  `datasource_id` bigint NOT NULL COMMENT '业务库 ID（引用 c1_load_datasource.id）',
  `source_table` varchar(128) NOT NULL COMMENT '业务表名（白名单校验）',
  `source_column` varchar(128) DEFAULT NULL COMMENT '聚合列（NULL/空=COUNT(*)）',
  `aggregate` varchar(24) NOT NULL COMMENT 'sum/count/avg/min/max/count_distinct',
  `filter_json` json DEFAULT NULL COMMENT '可选过滤 [{column,op,value}]，op 限 eq/ne/gt/gte/lt/lte',
  `spec_hash` char(64) NOT NULL COMMENT '定义快照哈希（canonical JSON 的 sha256）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `uk_index_name_ver` (`name`,`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指标定义：每版本一行，旧版本只读';

-- ② 规则定义：业务规则（与抽取规则 c1_extract_rule 无关）
CREATE TABLE IF NOT EXISTS `c1_rule_info` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '规则定义版本 ID',
  `name` varchar(128) NOT NULL COMMENT '规则名',
  `version` int NOT NULL COMMENT '版本号（同名内递增）',
  `index_refs_json` json NOT NULL COMMENT '引用指标 [{index_id,version,alias}]，version=0 取当前版',
  `conditions_json` json NOT NULL COMMENT '条件 [{alias,op,threshold}]，op=gt/gte/lt/lte/eq/ne/between',
  `combine` varchar(16) NOT NULL DEFAULT 'all' COMMENT 'all/any',
  `spec_hash` char(64) NOT NULL COMMENT '定义快照哈希',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `uk_rule_name_ver` (`name`,`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='业务规则定义：指标比较条件，结构化 JSON';

-- ③ 框架定义
CREATE TABLE IF NOT EXISTS `c1_frame_info` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '框架定义版本 ID',
  `name` varchar(128) NOT NULL COMMENT '框架名',
  `version` int NOT NULL COMMENT '版本号（同名内递增）',
  `rule_refs_json` json NOT NULL COMMENT '引用规则 [{rule_id,version,weight,veto}]',
  `combine` varchar(24) NOT NULL DEFAULT 'weighted' COMMENT 'weighted/all_pass/any_pass/veto',
  `threshold` decimal(12,4) DEFAULT NULL COMMENT 'weighted 模式通过阈值',
  `spec_hash` char(64) NOT NULL COMMENT '定义快照哈希',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `uk_frame_name_ver` (`name`,`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='评估框架定义：规则组合口径';

-- ④ 指标结果：携带参与计算的行锚点
CREATE TABLE IF NOT EXISTS `c1_index_value` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '指标结果 ID',
  `index_id` bigint NOT NULL COMMENT '指标定义 ID',
  `index_version` int NOT NULL COMMENT '计算时绑定的指标版本',
  `value_text` varchar(64) NOT NULL COMMENT '指标值（保真文本）',
  `input_rows_json` json NOT NULL COMMENT '输入锚点 {datasource_id,table,column,filter,rows,truncated}',
  `result_hash` char(64) NOT NULL COMMENT 'sha256(def spec + input snapshot)',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_index_value_def` (`index_id`,`index_version`),
  UNIQUE KEY `uk_index_value_hash` (`index_id`,`index_version`,`result_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='指标结果：逐行锚点可回溯到业务表';

-- ⑤ 规则结果：继承指标结果血缘
CREATE TABLE IF NOT EXISTS `c1_rule_value` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '规则结果 ID',
  `rule_id` bigint NOT NULL COMMENT '规则定义 ID',
  `rule_version` int NOT NULL COMMENT '计算时绑定的规则版本',
  `index_value_ids_json` json NOT NULL COMMENT '依赖的指标结果 ID 列表',
  `outcome` varchar(8) NOT NULL COMMENT 'pass/fail',
  `detail_json` json NOT NULL COMMENT '逐条件 {alias,op,threshold,actual,passed}',
  `result_hash` char(64) NOT NULL COMMENT '结果哈希（可重算比对）',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_rule_value_def` (`rule_id`,`rule_version`),
  UNIQUE KEY `uk_rule_value_hash` (`rule_id`,`rule_version`,`result_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='规则结果：继承指标结果血缘';

-- ⑥ 框架结果：继承规则结果血缘，追溯链顶点
CREATE TABLE IF NOT EXISTS `c1_frame_value` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '框架结果 ID',
  `frame_id` bigint NOT NULL COMMENT '框架定义 ID',
  `frame_version` int NOT NULL COMMENT '计算时绑定的框架版本',
  `rule_value_ids_json` json NOT NULL COMMENT '依赖的规则结果 ID 列表',
  `outcome` varchar(8) NOT NULL COMMENT 'pass/fail',
  `score_text` varchar(64) DEFAULT NULL COMMENT '综合得分（weighted 模式）',
  `detail_json` json NOT NULL COMMENT '逐规则 {rule_value_id,outcome,weight,veto,contribution}',
  `result_hash` char(64) NOT NULL COMMENT '结果哈希（可重算比对）',
  `computed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '计算时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_frame_value_def` (`frame_id`,`frame_version`),
  UNIQUE KEY `uk_frame_value_hash` (`frame_id`,`frame_version`,`result_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='框架结果：逐层继承到源文件血缘';
