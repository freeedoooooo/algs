-- 002_rename_rules.sql — 全局命名收敛（2026-11-23 裁决）：
--   extract_* 表前缀 → c1_*；extract_template* → c1_rule*；
--   template_* 列 → rule_*；索引/注释同步；产物名 extract.json → parse.json。
-- 已对 co_dev 执行（2026-11-23 10:07）。备份：data/backup/co_dev_pre002_*.sql。新装直接跑 001。

RENAME TABLE `extract_template_version` TO `c1_rule_version`, `extract_template` TO `c1_rule`, `extract_staging_lineage` TO `c1_staging_lineage`, `extract_staging_record` TO `c1_staging_record`, `extract_staging_field` TO `c1_staging_field`, `extract_task_file` TO `c1_task_file`, `extract_task` TO `c1_task`, `extract_load_datasource` TO `c1_load_datasource`, `extract_load_table_field` TO `c1_load_table_field`, `extract_load_table` TO `c1_load_table`, `extract_load_log` TO `c1_load_log`, `extract_quarantine` TO `c1_quarantine`, `extract_artifact` TO `c1_artifact`, `extract_file` TO `c1_file`;
ALTER TABLE `c1_task` CHANGE COLUMN `template_version_id` `rule_version_id` bigint NOT NULL;
ALTER TABLE `c1_rule_version` CHANGE COLUMN `template_id` `rule_id` bigint NOT NULL;
ALTER TABLE `c1_load_table` CHANGE COLUMN `template_id` `rule_id` bigint NOT NULL;
ALTER TABLE `c1_load_table_field` CHANGE COLUMN `template_field` `rule_field` varchar(200) NOT NULL;
ALTER TABLE `c1_load_table` RENAME INDEX `uk_ds_tpl_table` TO `uk_ds_rule_table`;
ALTER TABLE `c1_rule` RENAME INDEX `uk_template_name` TO `uk_rule_name`;
ALTER TABLE `c1_rule_version` RENAME INDEX `uk_tpl_ver` TO `uk_rule_ver`;
ALTER TABLE `c1_artifact` MODIFY COLUMN `task_file_id` bigint NOT NULL COMMENT '所属任务文件 ID（引用 c1_task_file.id，删除须应用层先清本表）';
ALTER TABLE `c1_load_log` MODIFY COLUMN `datasource_id` bigint NOT NULL COMMENT '数据源 ID（引用 c1_load_datasource.id，身份锁定保回执可追溯）';
ALTER TABLE `c1_load_log` MODIFY COLUMN `task_file_id` bigint NOT NULL COMMENT '所属任务文件 ID（引用 c1_task_file.id）';
ALTER TABLE `c1_load_log` MODIFY COLUMN `task_id` bigint NOT NULL COMMENT '所属任务 ID（引用 c1_task.id，应用层维护）';
ALTER TABLE `c1_load_table` MODIFY COLUMN `datasource_id` bigint NOT NULL COMMENT '数据源 ID（引用 c1_load_datasource.id，应用层维护）';
ALTER TABLE `c1_load_table_field` MODIFY COLUMN `load_table_id` bigint NOT NULL COMMENT '入库映射 ID（引用 c1_load_table.id，删除须应用层先清本表）';
ALTER TABLE `c1_quarantine` MODIFY COLUMN `task_file_id` bigint NULL COMMENT '所属任务文件 ID（引用 c1_task_file.id）';
ALTER TABLE `c1_quarantine` MODIFY COLUMN `task_id` bigint NOT NULL COMMENT '所属任务 ID（引用 c1_task.id，应用层维护）';
ALTER TABLE `c1_rule` MODIFY COLUMN `description` varchar(512) NULL COMMENT '抽取规则说明';
ALTER TABLE `c1_rule` MODIFY COLUMN `id` bigint NOT NULL auto_increment COMMENT '抽取规则 ID';
ALTER TABLE `c1_rule` MODIFY COLUMN `name` varchar(128) NOT NULL COMMENT '抽取规则名（唯一）';
ALTER TABLE `c1_rule_version` MODIFY COLUMN `id` bigint NOT NULL auto_increment COMMENT '抽取规则版本 ID';
ALTER TABLE `c1_rule_version` MODIFY COLUMN `version` int NOT NULL COMMENT '版本号（抽取规则内递增）';
ALTER TABLE `c1_staging_field` MODIFY COLUMN `field_name` varchar(128) NOT NULL COMMENT '抽取规则字段名（动态）';
ALTER TABLE `c1_staging_field` MODIFY COLUMN `record_id` bigint NOT NULL COMMENT '所属暂存记录 ID（引用 c1_staging_record.id，删除须应用层先清本表）';
ALTER TABLE `c1_staging_lineage` MODIFY COLUMN `field_name` varchar(128) NOT NULL COMMENT '抽取规则字段名（动态）';
ALTER TABLE `c1_staging_lineage` MODIFY COLUMN `record_id` bigint NOT NULL COMMENT '所属暂存记录 ID（引用 c1_staging_record.id，删除须应用层先清本表）';
ALTER TABLE `c1_staging_record` MODIFY COLUMN `task_file_id` bigint NOT NULL COMMENT '所属任务文件 ID（引用 c1_task_file.id，应用层维护）';
ALTER TABLE `c1_task_file` MODIFY COLUMN `file_id` bigint NOT NULL COMMENT '源文件 ID（引用 c1_file.id，应用层维护）';
ALTER TABLE `c1_task_file` MODIFY COLUMN `task_id` bigint NOT NULL COMMENT '所属任务 ID（引用 c1_task.id，应用层维护）';
ALTER TABLE `c1_load_table` COMMENT='入库映射绑定：数据源×表×抽取规则，同物理表可被不同抽取规则各建一行';
ALTER TABLE `c1_load_table_field` COMMENT='入库字段映射行：抽取规则字段→目标列＋业务键标记';
ALTER TABLE `c1_rule` COMMENT='抽取规则：目标字段定义/映射/转换的版本容器';
ALTER TABLE `c1_rule_version` COMMENT='抽取规则版本：三段 JSON（字段定义/映射/转换）不可变快照';
UPDATE c1_artifact SET name='parse.json' WHERE name='extract.json';
