-- Source MySQL: 10.0.6.161:3306 / dib_report_copilot
-- Generated from live metadata on 2026-04-16
-- Goal: normalize p_ / com_ tables enable_flag and enable to TINYINT NOT NULL DEFAULT 1

USE `dib_report_copilot`;

ALTER TABLE `dib_report_copilot`.`com_ai_client` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_ai_key` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_check_rule` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_board` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_board_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_board_view` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_data_domain` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_data_domain` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_index_func` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_field` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_info` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_model_field` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_model_relation` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_data_source` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_di_index` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_di_index_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_di_news_flash` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_di_report` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_di_report` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_di_report_dir` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_di_report_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_di_table` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_di_table_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_extract_doc_type_dir` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL OR TRIM(`enable_flag`) = '';
ALTER TABLE `dib_report_copilot`.`com_extract_doc_type_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_extract_doc_type_template` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_extract_etl_table` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_extract_inventory` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_extract_inventory` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_extract_inventory_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_extract_standardization_item` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_extract_table` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_frame_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_frame_info` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_frame_node` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_frame_revise_apply` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rg2_template` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rg2_template` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_rg2_template_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_rg2_var` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rg2_var_domain` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rg2_var_domain` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_rg2_var_param_lib` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rule_dim` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_dim` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rule_domain` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_domain` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_rule_edge` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rule_info` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_info` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rule_input` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_input` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`com_rule_node` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rule_ref_data` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_ref_data` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

UPDATE `dib_report_copilot`.`com_rule_tree` SET `enable_flag` = 1 WHERE `enable_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_tree` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`p_auth_module` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`p_auth_user` MODIFY COLUMN `enable` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`p_auth_user_ip_limit` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`p_mdm_org` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_dir` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_type` MODIFY COLUMN `enable_flag` TINYINT NOT NULL DEFAULT 1;
