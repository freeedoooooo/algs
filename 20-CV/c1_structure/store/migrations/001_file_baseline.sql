-- 001_file_baseline.sql — 结构化平台（c1-structure）全新基线。
-- 模型：一条资料记录 = 一次运行（单文件）；无 c1_task / c1_task_file，
--       运行态并入 c1_doc_file，产物/暂存/回执/隔离统一以 file_id 为键。
-- 用途：**空库建表**。存量已由用户裁决清空；原有 001~004 不再叠加执行。
-- 幂等：全 IF NOT EXISTS + INSERT IGNORE，重复执行无副作用。
-- 依据：历史 001_baseline.sql（git 31b77fa）字段类型/索引命名，键改造见 docs/design-file-centric-refactor.md。

-- ① 资料 + 运行态（原 c1_doc_file + c1_task + c1_task_file 三表合一）
CREATE TABLE IF NOT EXISTS `c1_doc_file` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '资料 ID（唯一运行主键）',
  `name` varchar(255) NOT NULL COMMENT '原始文件名',
  `sha256` char(64) NOT NULL COMMENT '内容 SHA-256（仅检索，不唯一：同字节允许多次独立运行）',
  `kind` varchar(16) NOT NULL COMMENT '载体类型：image/pdf/csv/text',
  `size_bytes` bigint NOT NULL COMMENT '文件字节数',
  `content` longblob NOT NULL COMMENT '原件字节（唯一事实源）',
  `tags` varchar(512) DEFAULT NULL COMMENT '标签（逗号分隔，可选）',
  `note` text COMMENT '备注',
  `state` varchar(24) NOT NULL DEFAULT 'pending' COMMENT '运行状态：pending/parsing/to_extract/to_review/to_load/loading/loaded/failed',
  `error` text COMMENT '失败原因',
  `rule_version_id` bigint NULL COMMENT '抽取时绑定的规则版本 ID',
  `doc_type` varchar(64) DEFAULT NULL COMMENT '单据类型（归类 Agent 写入，与载体 kind 解耦）',
  `params_json` json DEFAULT NULL COMMENT '生效解析参数快照',
  `load_datasource_id` bigint DEFAULT NULL COMMENT '入库数据源 ID',
  `load_table_id` bigint DEFAULT NULL COMMENT '入库映射 ID',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登记时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_file_sha` (`sha256`),
  KEY `idx_file_state` (`state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='资料登记+运行状态：一次上传=一行=一次运行，原件字节存 content';

-- ② 抽取规则（保留原样）
CREATE TABLE IF NOT EXISTS `c1_extract_rule` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '抽取规则 ID',
  `name` varchar(128) NOT NULL COMMENT '抽取规则名（唯一）',
  `description` varchar(512) DEFAULT NULL COMMENT '抽取规则说明',
  `current_version` int NOT NULL DEFAULT '1' COMMENT '当前生效版本号',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rule_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取规则：目标字段定义/映射/转换的版本容器';

CREATE TABLE IF NOT EXISTS `c1_extract_rule_version` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '抽取规则版本 ID',
  `rule_id` bigint NOT NULL,
  `version` int NOT NULL COMMENT '版本号（抽取规则内递增）',
  `schema_json` json DEFAULT NULL COMMENT '目标字段定义（空=透传）',
  `mapping_json` json DEFAULT NULL COMMENT '源到目标字段映射（空=透传）',
  `transform_json` json DEFAULT NULL COMMENT '字段转换规则（空=透传）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rule_ver` (`rule_id`,`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽取规则版本：三段 JSON（字段定义/映射/转换）不可变快照';

-- ③ 产物附件（键 task_file_id → file_id）
CREATE TABLE IF NOT EXISTS `c1_parse_artifact` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '附件 ID',
  `file_id` bigint NOT NULL COMMENT '所属资料 ID（引用 c1_doc_file.id，应用层维护）',
  `name` varchar(200) NOT NULL COMMENT '资料内相对路径（如 pages/p1.png、对照报告.html）',
  `kind` varchar(20) NOT NULL COMMENT '产物类别：json/html/md/csv/image/raw',
  `mime` varchar(100) NOT NULL COMMENT 'MIME 类型（/files 路由回调用）',
  `size_bytes` int NOT NULL COMMENT '字节数',
  `sha256` char(64) NOT NULL COMMENT '内容 SHA-256（ETag 与导出校验）',
  `content` longblob NOT NULL COMMENT '产物字节（唯一事实源，无持久磁盘）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_artifact` (`file_id`,`name`),
  KEY `idx_artifact_sha` (`sha256`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='产物附件：报告/图片/CSV/parse.json 全量 BLOB，键＝资料粒度';

-- ④ 暂存三表（task_file_id → file_id；field/lineage 经 record_id 关联，原样）
CREATE TABLE IF NOT EXISTS `c1_staging_record` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '暂存记录 ID',
  `file_id` bigint NOT NULL COMMENT '所属资料 ID（引用 c1_doc_file.id，应用层维护）',
  `record_index` int NOT NULL COMMENT '记录在资料内下标',
  `review_state` varchar(16) NOT NULL DEFAULT 'pending' COMMENT '校验状态：pending/edited/confirmed/rejected',
  `review_at` datetime DEFAULT NULL COMMENT '校验时间（UTC）',
  `values_json` mediumtext NOT NULL COMMENT '当前值全保真 body（API 重建用）',
  `original_json` mediumtext NOT NULL COMMENT '抽取原值，永不覆盖',
  `review_reason_json` json DEFAULT NULL COMMENT '校验标记（字段→issue 列表），只标记不改值',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC，patch 可追溯）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_file_idx` (`file_id`,`record_index`),
  KEY `idx_review` (`review_state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='暂存记录：每行一条，全保真 JSON＋校验态，记录事实源';

CREATE TABLE IF NOT EXISTS `c1_staging_field` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '字段投影 ID',
  `record_id` bigint NOT NULL COMMENT '所属暂存记录 ID（引用 c1_staging_record.id，删除须应用层先清本表）',
  `field_name` varchar(128) NOT NULL COMMENT '抽取规则字段名（动态）',
  `value_text` text NOT NULL COMMENT '当前值（含 edited）',
  `original_text` text NOT NULL COMMENT '抽取原值',
  `confidence` float DEFAULT NULL COMMENT '字段级置信度（Agent 信号，可空）',
  `reason` varchar(255) DEFAULT NULL COMMENT '字段级判定理由（Agent 信号，可空）',
  PRIMARY KEY (`id`),
  KEY `idx_field_value` (`field_name`,`value_text`(191)),
  KEY `idx_record` (`record_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='暂存字段投影：values 的可查询展开，可由 record 全量重建';

CREATE TABLE IF NOT EXISTS `c1_staging_lineage` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '血缘 ID',
  `record_id` bigint NOT NULL COMMENT '所属暂存记录 ID（引用 c1_staging_record.id，删除须应用层先清本表）',
  `field_name` varchar(128) NOT NULL COMMENT '抽取规则字段名（动态）',
  `region_seq` int NOT NULL COMMENT '区域保序（同 cv_lineage 约定）',
  `page` int NOT NULL COMMENT '来源页码（1 起）',
  `table_index` int DEFAULT NULL COMMENT '来源表下标',
  `table_scope` varchar(16) DEFAULT NULL COMMENT '表口径：page 本页 / stitched 跨页合并',
  `space` varchar(16) NOT NULL COMMENT '坐标空间：source/rectified',
  `cell_bbox` varchar(128) DEFAULT NULL COMMENT '单元格框 [x0,y0,x1,y1] json 字符串',
  `raw_text` text COMMENT '该格原文',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_rec_field_seq` (`record_id`,`field_name`,`region_seq`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='暂存血缘：逐格回溯锚点（页/表/框/原文），可由 record 全量重建';

-- ⑤ 入库配置（保留原样）
CREATE TABLE IF NOT EXISTS `c1_load_datasource` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '数据源 ID',
  `name` varchar(100) NOT NULL COMMENT '显示名（唯一）',
  `db_type` varchar(20) NOT NULL DEFAULT 'mysql' COMMENT '目标库类型：首个实现仅 mysql',
  `host` varchar(255) NOT NULL COMMENT '目标库主机',
  `port` int NOT NULL DEFAULT '3306' COMMENT '目标库端口',
  `user` varchar(100) NOT NULL COMMENT '目标库账号',
  `password` varchar(255) NOT NULL DEFAULT '' COMMENT '目标库密码（明文，2026-11-21 裁决，日志永不打印）',
  `db_name` varchar(100) NOT NULL COMMENT '目标库名（一个数据源＝一个库）',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ds_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库数据源：一行＝一个库，连接参数页面明文配置';

CREATE TABLE IF NOT EXISTS `c1_load_table` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '入库映射 ID',
  `datasource_id` bigint NOT NULL COMMENT '数据源 ID（引用 c1_load_datasource.id）',
  `rule_id` bigint NULL COMMENT '参考抽取规则 ID（仅配置期参考，可空）',
  `rule_version_id` bigint NULL COMMENT '参考抽取规则版本 id（仅回溯）',
  `source_snapshot_json` TEXT NULL COMMENT '抽取输出快照：字段名+类型+参考规则版本',
  `target_table` varchar(128) NOT NULL COMMENT '目标业务表名',
  `write_mode` varchar(16) NOT NULL DEFAULT 'upsert' COMMENT '写入模式：upsert/insert/update',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库映射绑定：数据源×目标表；抽取规则仅配置期参考，输出契约以快照为准';

CREATE TABLE IF NOT EXISTS `c1_load_table_field` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '字段映射 ID',
  `load_table_id` bigint NOT NULL COMMENT '入库映射 ID（引用 c1_load_table.id，删除须应用层先清本表）',
  `rule_field` varchar(200) NOT NULL,
  `target_column` varchar(128) NOT NULL COMMENT '目标列名',
  `is_business_key` tinyint NOT NULL DEFAULT '0' COMMENT '是否业务键（upsert/update 去重依据）',
  `sort_order` int NOT NULL DEFAULT '0' COMMENT '展示序（schema 字段序）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_table_field` (`load_table_id`,`rule_field`),
  UNIQUE KEY `uk_table_column` (`load_table_id`,`target_column`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库字段映射行：抽取规则字段→目标列＋业务键标记';

-- ⑥ 回执/隔离（task_id + task_file_id → file_id）
CREATE TABLE IF NOT EXISTS `c1_load_log` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '入库回执 ID',
  `file_id` bigint NOT NULL COMMENT '所属资料 ID（引用 c1_doc_file.id，应用层维护）',
  `record_index` int NOT NULL COMMENT '记录在资料内下标',
  `datasource_id` bigint NOT NULL COMMENT '数据源 ID（身份锁定保回执可追溯）',
  `target_table` varchar(128) NOT NULL COMMENT '目标业务表名',
  `target_pk` varchar(255) NOT NULL COMMENT '目标行主键值',
  `action` varchar(16) NOT NULL COMMENT '动作：insert/update/upsert/delete',
  `loaded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_load_receipt` (`file_id`,`record_index`,`datasource_id`,`target_table`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='入库回执：每条记录写入目标库的幂等收据（唯一键防重）';

CREATE TABLE IF NOT EXISTS `c1_load_quarantine` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '隔离记录 ID',
  `file_id` bigint NOT NULL COMMENT '所属资料 ID（引用 c1_doc_file.id，应用层维护）',
  `record_index` int DEFAULT NULL COMMENT '记录在资料内下标',
  `stage` varchar(16) NOT NULL COMMENT '隔离阶段：extract/collect/review/load',
  `reason` text NOT NULL COMMENT '隔离原因',
  `payload_json` json NOT NULL COMMENT '问题记录快照',
  `state` varchar(16) NOT NULL DEFAULT 'open' COMMENT '处理状态：open/resolved/rejected',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '隔离时间（UTC）',
  `resolved_at` datetime DEFAULT NULL COMMENT '处理时间（UTC）',
  PRIMARY KEY (`id`),
  KEY `idx_q_file` (`file_id`,`state`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='隔离区：校验/入库失败记录，按 (file_id,record_index) 引用暂存记录';

-- 种子数据：内置兜底抽取规则「原始透传」v1
INSERT IGNORE INTO c1_extract_rule (name, description, current_version)
SELECT '原始透传', '内置兜底规则：整页文本原样透传，不做字段抽取。', 1
WHERE NOT EXISTS (SELECT 1 FROM c1_extract_rule WHERE name = '原始透传');

INSERT IGNORE INTO c1_extract_rule_version (rule_id, version, schema_json, mapping_json, transform_json)
SELECT r.id, 1, '[]', '{}', '{}'
FROM c1_extract_rule r
WHERE r.name = '原始透传'
  AND NOT EXISTS (SELECT 1 FROM c1_extract_rule_version v
                  WHERE v.rule_id = r.id AND v.version = 1);
