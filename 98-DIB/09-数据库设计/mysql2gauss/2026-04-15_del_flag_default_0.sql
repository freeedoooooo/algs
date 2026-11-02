-- Scope:
--   dib_report_copilot schema
--   tables prefixed with p_ or com_
--   del_flag columns with integer-like types
--   only columns whose current default is NULL
--
-- Skipped because default is already 0:
--   p_mdm_project_type
--   p_mdm_project_type_biz
--   p_mdm_project_type_customer
--   p_mdm_project_type_ext

BEGIN;

ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_ai_key ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_ai_log ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_board_dir ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_board_view_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_edge ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_func ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_info ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_ref_item ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_ref_item_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_value ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_value_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_domain_relation ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_info ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_customer_auth ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_index_opt_record ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_table_dir ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_table_opt_record ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_user_search_record ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_doc_type_template ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_standardization_item ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_node ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_node_rule ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_revise_apply ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_revise_item ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_value_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_pub_operation_log ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_report_export_log ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_report_param ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_report_user ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_report_var ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_template_chapter ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_template_var ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_template_var_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_var ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_var_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_var_param ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_var_param_lib ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_biz_value ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_dim ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_domain_relation ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_edge ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_info ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_input ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_node ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_node_history ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_ref_data ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_tree ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rule_value_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_customer ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_customer_ip ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_login_log ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_module ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_module_url ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_password_strategy ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_pwd_log ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_role ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_role_module ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_security_level_config ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_system_config ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_url ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_user_ip_limit ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_user_role ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_user_session ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_auth_user_unlock_apply ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_attachment ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_attachment_biz ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_dict_def ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_dict_item ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_enterprise ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_project ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_project_ext_value ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_project_ext_warehouse ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_project_user ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_sys_param ALTER COLUMN del_flag SET DEFAULT 0;

COMMIT;
