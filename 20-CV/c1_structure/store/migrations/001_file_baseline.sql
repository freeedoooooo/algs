-- 001_file_baseline.sql — 抽取规则与入库配置解耦后的全新空库基线。
-- 用途：仅用于空库建表；存量旧库请使用 007_decouple_extraction_loading.py。
-- 模型：文档拥有多条规则结果；每条结果最多绑定一个目标表；规则不保留版本表。
-- 幂等：CREATE IF NOT EXISTS + INSERT IGNORE。
-- 依据：docs/design-decoupled-extraction-loading.md。
-- 关联完整性沿用既有约定，由应用层维护；本文件不创建外键。

-- ① 文档：只保留文档事实源与汇总状态，规则/目标配置由结果和绑定承担。
CREATE TABLE IF NOT EXISTS `c1_doc` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '文档 ID',
  `name` varchar(255) NOT NULL COMMENT '原始文件名',
  `sha256` char(64) NOT NULL COMMENT '原件内容 SHA-256（仅检索，不唯一）',
  `kind` varchar(16) NOT NULL COMMENT '载体类型：image/pdf/csv/text',
  `size_bytes` bigint NOT NULL COMMENT '文件字节数',
  `content` longblob NOT NULL COMMENT '原件字节（唯一事实源）',
  `tags` varchar(512) DEFAULT NULL COMMENT '标签（逗号分隔，可选）',
  `note` text COMMENT '备注',
  `state` varchar(32) NOT NULL DEFAULT 'pending' COMMENT '文档汇总状态',
  `error` text COMMENT '失败原因',
  `doc_type` varchar(64) DEFAULT NULL COMMENT '单据类型（与载体 kind 解耦）',
  `params_json` json DEFAULT NULL COMMENT '生效解析参数快照',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登记时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_doc_sha` (`sha256`),
  KEY `idx_doc_state` (`state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='文档：原件事实源与文档级汇总状态';

-- ② 抽取规则：一行一条完整规则，不保留版本号或版本表。
CREATE TABLE IF NOT EXISTS `c1_extract_rule` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '抽取规则 ID',
  `name` varchar(128) NOT NULL COMMENT '抽取规则名（唯一）',
  `description` varchar(512) DEFAULT NULL COMMENT '抽取规则说明',
  `output_schema_json` json DEFAULT NULL COMMENT '输出字段契约和记录粒度',
  `extraction_spec_json` json DEFAULT NULL COMMENT '表选择、字段抽取、抽取归一化逻辑',
  `reference_doc_ids_json` json DEFAULT NULL COMMENT '总结规则时使用的参考文档 ID',
  `validation_report_json` json DEFAULT NULL COMMENT '参考附件校验和干跑结果',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rule_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取规则：一条规则一行，无版本表';

-- ③ 当前解析产物：同一文档重新解析时覆盖，不保留解析运行历史。
CREATE TABLE IF NOT EXISTS `c1_parse_artifact` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '产物 ID',
  `doc_id` bigint NOT NULL COMMENT '所属文档 ID（引用 c1_doc.id）',
  `name` varchar(200) NOT NULL COMMENT '文档内相对路径（如 parse.json、pages/p1.png）',
  `kind` varchar(20) NOT NULL COMMENT '产物类别：json/html/md/csv/image/raw',
  `mime` varchar(100) NOT NULL COMMENT 'MIME 类型',
  `size_bytes` int NOT NULL COMMENT '字节数',
  `content` longblob NOT NULL COMMENT '产物字节（唯一事实源，无持久磁盘）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_artifact` (`doc_id`,`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='当前解析产物：文档粒度，不保存 sha256';

-- ④ 文档 × 规则的当前结果：重复执行覆盖，不保留执行历史。
CREATE TABLE IF NOT EXISTS `c1_extract_result` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '抽取结果 ID（RecordSet ID）',
  `doc_id` bigint NOT NULL COMMENT '所属文档 ID',
  `rule_id` bigint NOT NULL COMMENT '使用的抽取规则 ID',
  `rule_snapshot_json` json NOT NULL COMMENT '本次执行使用的完整规则快照',
  `status` varchar(16) NOT NULL COMMENT 'pending/running/ready/failed',
  `record_count` int NOT NULL DEFAULT '0' COMMENT '当前记录数',
  `error` text COMMENT '失败原因',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次创建时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近覆盖执行时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_doc_rule` (`doc_id`,`rule_id`),
  KEY `idx_extract_rule` (`rule_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取结果：同一文档同一规则仅保留当前结果';

-- ⑤ 抽取记录及字段/血缘投影。
CREATE TABLE IF NOT EXISTS `c1_extract_record` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '抽取记录 ID',
  `extract_result_id` bigint NOT NULL COMMENT '所属抽取结果 ID',
  `doc_id` bigint NOT NULL COMMENT '所属文档 ID（方便按文档查询）',
  `record_index` int NOT NULL COMMENT '抽取结果内的记录下标',
  `review_state` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '校验状态：pending/edited/confirmed/rejected',
  `review_at` datetime DEFAULT NULL COMMENT '校验时间（UTC）',
  `values_json` mediumtext NOT NULL COMMENT '当前值全保真 body',
  `original_json` mediumtext NOT NULL COMMENT '抽取原值，永不覆盖',
  `review_reason_json` json DEFAULT NULL COMMENT '校验标记（字段→issue 列表）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_extract_result_record` (`extract_result_id`,`record_index`),
  KEY `idx_record_doc_result` (`doc_id`,`extract_result_id`),
  KEY `idx_review` (`review_state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取记录：每条记录归属一个抽取结果';

CREATE TABLE IF NOT EXISTS `c1_extract_record_field` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '字段投影 ID',
  `record_id` bigint NOT NULL COMMENT '所属抽取记录 ID（引用 c1_extract_record.id）',
  `field_name` varchar(128) NOT NULL COMMENT '抽取规则字段名（动态）',
  `value_text` text NOT NULL COMMENT '当前值（含 edited）',
  `original_text` text NOT NULL COMMENT '抽取原值',
  `confidence` float DEFAULT NULL COMMENT '字段级置信度',
  `reason` varchar(255) DEFAULT NULL COMMENT '字段级判定理由',
  PRIMARY KEY (`id`),
  KEY `idx_field_value` (`field_name`,`value_text`(191)),
  KEY `idx_record` (`record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取记录字段投影：可由记录全量重建';

CREATE TABLE IF NOT EXISTS `c1_extract_record_lineage` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '血缘 ID',
  `record_id` bigint NOT NULL COMMENT '所属抽取记录 ID（引用 c1_extract_record.id）',
  `field_name` varchar(128) NOT NULL COMMENT '抽取规则字段名（动态）',
  `region_seq` int NOT NULL COMMENT '区域保序',
  `page` int NOT NULL COMMENT '来源页码（1 起）',
  `table_index` int DEFAULT NULL COMMENT '来源表下标',
  `table_scope` varchar(16) DEFAULT NULL COMMENT '表口径：page/stitched',
  `space` varchar(16) NOT NULL COMMENT '坐标空间：source/rectified',
  `cell_bbox` varchar(128) DEFAULT NULL COMMENT '单元格框 [x0,y0,x1,y1] JSON 字符串',
  `raw_text` text COMMENT '该格原文',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rec_field_seq` (`record_id`,`field_name`,`region_seq`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取记录血缘：逐格回溯锚点';

-- ⑥ 目标库/目标表配置：不持有抽取规则、来源映射或写入方式。
CREATE TABLE IF NOT EXISTS `c1_load_datasource` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '数据源 ID',
  `name` varchar(100) NOT NULL COMMENT '显示名（唯一）',
  `db_type` varchar(20) NOT NULL DEFAULT 'mysql' COMMENT '目标库类型',
  `host` varchar(255) NOT NULL COMMENT '目标库主机',
  `port` int NOT NULL DEFAULT '3306' COMMENT '目标库端口',
  `user` varchar(100) NOT NULL COMMENT '目标库账号',
  `password` varchar(255) NOT NULL DEFAULT '' COMMENT '目标库密码（日志永不打印）',
  `db_name` varchar(100) NOT NULL COMMENT '目标库名',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ds_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库数据源：一行一个目标库';

CREATE TABLE IF NOT EXISTS `c1_load_table` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '入库表配置 ID',
  `datasource_id` bigint NOT NULL COMMENT '目标数据源 ID',
  `target_table` varchar(128) NOT NULL COMMENT '目标业务表名',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_load_table_target` (`datasource_id`,`target_table`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库表配置：仅描述目标库和目标表';

CREATE TABLE IF NOT EXISTS `c1_load_mapping_field` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '目标字段元数据 ID',
  `load_table_id` bigint NOT NULL COMMENT '所属入库表配置 ID',
  `field_name` varchar(128) NOT NULL COMMENT '目标数据库列名',
  `data_type` varchar(64) NOT NULL COMMENT '目标列类型',
  `is_primary` tinyint NOT NULL DEFAULT '0' COMMENT '是否目标表物理主键',
  `has_default` tinyint NOT NULL DEFAULT '0' COMMENT '目标列是否有默认值',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '展示顺序',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_mapping_field` (`load_table_id`,`field_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='目标字段元数据：不保存来源字段映射或业务键';

-- ⑦ 入库绑定：一个抽取结果最多一个目标；映射、写入方式和业务键按绑定隔离。
CREATE TABLE IF NOT EXISTS `c1_load_binding` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '入库绑定 ID',
  `doc_id` bigint NOT NULL COMMENT '所属文档 ID',
  `extract_result_id` bigint NOT NULL COMMENT '输入抽取结果 ID',
  `load_table_id` bigint NOT NULL COMMENT '目标入库表配置 ID',
  `field_map_json` json NOT NULL COMMENT '来源字段→目标列映射',
  `write_mode` varchar(16) NOT NULL COMMENT 'insert/upsert/update',
  `business_keys_json` json DEFAULT NULL COMMENT 'upsert/update 的目标业务键列表',
  `status` varchar(16) NOT NULL COMMENT 'pending/confirmed/running/ready/failed',
  `confirmed_at` datetime DEFAULT NULL COMMENT '用户确认时间（UTC）',
  `error` text COMMENT '失败原因',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_extract_result_binding` (`extract_result_id`),
  KEY `idx_binding_doc` (`doc_id`),
  KEY `idx_binding_load_table` (`load_table_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库绑定：单个抽取结果如何写入单个目标表';

CREATE TABLE IF NOT EXISTS `c1_load_receipt` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '入库回执 ID',
  `load_binding_id` bigint NOT NULL COMMENT '所属入库绑定 ID',
  `doc_id` bigint NOT NULL COMMENT '所属文档 ID',
  `record_index` int NOT NULL COMMENT '入库绑定内的记录下标',
  `datasource_id` bigint NOT NULL COMMENT '目标数据源 ID（身份锁定）',
  `target_table` varchar(128) NOT NULL COMMENT '目标业务表名',
  `target_pk` varchar(255) NOT NULL COMMENT '目标行主键值',
  `action` varchar(16) NOT NULL COMMENT '动作：insert/update/upsert/delete',
  `loaded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_load_binding_record` (`load_binding_id`,`record_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库回执：按入库绑定和记录下标隔离';

-- ⑧ 隔离记录：抽取和入库阶段的问题均可追溯，两类引用允许为空。
CREATE TABLE IF NOT EXISTS `c1_quarantine_record` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '隔离记录 ID',
  `doc_id` bigint NOT NULL COMMENT '所属文档 ID',
  `extract_result_id` bigint DEFAULT NULL COMMENT '抽取阶段所属结果 ID',
  `load_binding_id` bigint DEFAULT NULL COMMENT '入库阶段所属绑定 ID',
  `record_index` int DEFAULT NULL COMMENT '对应结果或绑定内的记录下标',
  `stage` varchar(16) NOT NULL COMMENT '隔离阶段：extract/collect/review/load',
  `reason` text NOT NULL COMMENT '隔离原因',
  `payload_json` json NOT NULL COMMENT '问题记录快照',
  `state` varchar(16) NOT NULL DEFAULT 'open' COMMENT '处理状态：open/resolved/rejected',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '隔离时间（UTC）',
  `resolved_at` datetime DEFAULT NULL COMMENT '处理时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_q_doc_state` (`doc_id`,`state`),
  KEY `idx_q_result` (`extract_result_id`),
  KEY `idx_q_binding` (`load_binding_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='隔离记录：可关联抽取结果或入库绑定';

-- 内置兜底规则：完整定义直接保存在规则行内。
INSERT IGNORE INTO c1_extract_rule
  (name, description, output_schema_json, extraction_spec_json,
   reference_doc_ids_json, validation_report_json)
SELECT '原始透传', '内置兜底规则：整页文本原样透传，不做字段抽取。',
       JSON_OBJECT('fields', JSON_ARRAY()), JSON_OBJECT(),
       JSON_ARRAY(), JSON_OBJECT()
WHERE NOT EXISTS (SELECT 1 FROM c1_extract_rule WHERE name = '原始透传');
