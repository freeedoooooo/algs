-- Source openGauss: 192.168.10.141:5432 / c1 / dib_report_copilot
-- Generated from live metadata on 2026-04-16
-- openGauss does not provide MySQL TINYINT; int2 is used as the equivalent target type.
-- Goal: normalize p_ / com_ tables enable_flag and enable to int2 NOT NULL DEFAULT 1

BEGIN;

ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_ai_key ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_ai_key ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_check_rule ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_check_rule ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_check_rule ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_board ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_board ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_board_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_board_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_domain ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_data_domain ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_domain ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_index_func ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_data_index_func ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_index_func ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_metadata_field ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_metadata_field ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_metadata_info ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_metadata_info ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_metadata_model_field ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_data_metadata_model_field ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_metadata_model_field ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_metadata_model_relation ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_data_metadata_model_relation ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_metadata_model_relation ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN enable_flag TYPE int2 USING CASE WHEN enable_flag IS NULL THEN 1 WHEN enable_flag THEN 1 ELSE 0 END;
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_di_table ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_di_table ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_di_table ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_di_table_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_di_table_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_extract_doc_type_dir ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_extract_doc_type_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_doc_type_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_extract_doc_type_template ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_doc_type_template ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_extract_etl_table ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_etl_table ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_extract_inventory SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_extract_inventory ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_inventory ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_extract_standardization_item ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_standardization_item ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_extract_table ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_extract_table ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_extract_table ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_frame_node ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_frame_node ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_frame_revise_apply ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_frame_revise_apply ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_rg2_template SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_rg2_template ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rg2_template ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rg2_var ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rg2_var ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rg2_var_domain ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_rg2_var_domain ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rg2_var_domain ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rg2_var_param_lib ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rg2_var_param_lib ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_rule_dim SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_rule_dim ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_dim ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rule_domain ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.com_rule_domain ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_domain ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rule_edge ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_edge ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_rule_info SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_rule_info ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_info ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_rule_input SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_rule_input ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_input ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.com_rule_node ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_node ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_rule_ref_data SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_rule_ref_data ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_ref_data ALTER COLUMN enable_flag SET NOT NULL;

UPDATE dib_report_copilot.com_rule_tree SET enable_flag = 1 WHERE enable_flag IS NULL;
ALTER TABLE dib_report_copilot.com_rule_tree ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.com_rule_tree ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.p_auth_module ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.p_auth_module ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN enable TYPE int2 USING COALESCE(NULLIF(BTRIM(enable), ''), '1')::int2;
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN enable SET DEFAULT 1;
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN enable SET NOT NULL;

ALTER TABLE dib_report_copilot.p_auth_user_ip_limit ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.p_auth_user_ip_limit ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.p_mdm_org ALTER COLUMN enable_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(enable_flag), ''), '1')::int2;
ALTER TABLE dib_report_copilot.p_mdm_org ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.p_mdm_org ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN enable_flag SET NOT NULL;

ALTER TABLE dib_report_copilot.p_mdm_project_type ALTER COLUMN enable_flag SET DEFAULT 1;
ALTER TABLE dib_report_copilot.p_mdm_project_type ALTER COLUMN enable_flag SET NOT NULL;

COMMIT;