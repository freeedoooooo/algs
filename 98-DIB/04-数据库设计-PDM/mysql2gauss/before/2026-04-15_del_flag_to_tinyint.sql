-- Source MySQL: 10.0.6.161:3306 / dib_report_copilot
-- Generated from live metadata on 2026-04-15
-- Goal: normalize p_ / com_ tables del_flag to TINYINT NOT NULL DEFAULT 0

USE `dib_report_copilot`;

ALTER TABLE `dib_report_copilot`.`com_ai_client` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_ai_key` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_ai_log` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_check_param` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_check_rule` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_board` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_board_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_board_view` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_board_view_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_dim_auth_rule` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_data_domain` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_data_domain` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_domain_relation` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_edge` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_func` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_info` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_ref_item` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_ref_item_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_task` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_data_index_value` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_data_index_value` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_index_value_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_domain_relation` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_field_map` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_info` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_lineage` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_model_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_metadata_model_relation` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_data_source` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_customer_auth` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_dir_table` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_index` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_index_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_index_favorite` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_index_opt_record` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_news_flash` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_table` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_table_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_table_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_table_opt_record` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_di_user_search_record` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_extract_doc_type_template` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_extract_etl_doc` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_extract_etl_doc` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_extract_etl_doc_table` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_extract_etl_doc_table` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_extract_etl_table` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_extract_etl_table` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_extract_etl_table_column` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_extract_etl_table_column` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_extract_inventory` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_extract_inventory_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_extract_standardization_item` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_info` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_node` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_node_rule` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_revise_apply` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_revise_item` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_frame_value` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_frame_value` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_value_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_frame_value_snapshot` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_frame_value_snapshot` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_visualization` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_frame_visualization_level` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_pub_operation_log` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rg2_report` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rg2_report` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_report_export_log` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_report_param` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_report_user` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_report_var` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_template` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_template_chapter` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_template_customer` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_template_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_template_var` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_template_var_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_var` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rg2_var_domain` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rg2_var_domain` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_var_domain_relation` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rg2_var_field` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rg2_var_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_var_param` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rg2_var_param_lib` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_biz_value` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_biz_value` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_dim` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_dim` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_domain` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_domain` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rule_domain_relation` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rule_edge` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_info` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_info` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_input` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_input` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rule_node` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rule_node_history` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_ref_data` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_ref_data` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`com_rule_tree` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`com_rule_tree` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_rule_value_field` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_task_dependency` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_task_monitor` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`com_task_schedule` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_customer` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_customer_ip` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_login_log` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_module` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_module_url` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_password_strategy` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_pwd_log` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_role` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_role_module` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_security_level_config` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_system_config` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_url` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_user` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

UPDATE `dib_report_copilot`.`p_auth_user_ip_limit` SET `del_flag` = 0 WHERE `del_flag` IS NULL;
ALTER TABLE `dib_report_copilot`.`p_auth_user_ip_limit` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_user_role` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_user_session` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_auth_user_unlock_apply` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_attachment` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_attachment_biz` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_dict_def` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_dict_item` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_enterprise` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_feedback` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_org` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_org_user` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_dir` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_ext_value` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_ext_warehouse` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_type` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_type_biz` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_type_customer` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_type_ext` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_project_user` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;

ALTER TABLE `dib_report_copilot`.`p_mdm_sys_param` MODIFY COLUMN `del_flag` TINYINT NOT NULL DEFAULT 0;
