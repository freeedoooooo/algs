-- Scope:
--   dib_report_copilot schema
--   tables prefixed with p_ or com_
--   del_flag columns whose type is not int2
--
-- This script converts del_flag to int2 and sets default 0.
--
-- Conversion rules:
--   varchar/char -> int2: COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2
--   boolean      -> int2: CASE WHEN del_flag THEN 1 ELSE 0 END

BEGIN;

ALTER TABLE dib_report_copilot.com_check_param ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_check_param ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_check_rule ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_check_rule ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_board ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_board ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_dim_auth_rule ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_dim_auth_rule ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_domain ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_domain ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_index_domain_relation ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_index_domain_relation ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_field_map ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_metadata_field_map ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_lineage ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_metadata_lineage ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_model_field ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_metadata_model_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_metadata_model_relation ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_data_metadata_model_relation ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN del_flag TYPE int2 USING CASE WHEN del_flag THEN 1 ELSE 0 END;
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_dir_table ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_di_dir_table ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_table ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_di_table ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_etl_doc ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_extract_etl_doc ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_etl_doc_table ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_extract_etl_doc_table ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_etl_table ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_extract_etl_table ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_etl_table_column ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_extract_etl_table_column ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_inventory ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_extract_inventory ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_value ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_frame_value ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_frame_value_snapshot ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_frame_value_snapshot ALTER COLUMN del_flag SET DEFAULT 0;

ALTER TABLE dib_report_copilot.com_rg2_report ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rg2_report ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_template ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rg2_template ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_template_customer ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rg2_template_customer ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_var_domain ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rg2_var_domain ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_rg2_var_domain_relation ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rg2_var_domain_relation ALTER COLUMN del_flag SET DEFAULT 0;

ALTER TABLE dib_report_copilot.com_rule_domain ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_rule_domain ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_task_dependency ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_task_dependency ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.com_task_schedule ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.com_task_schedule ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_org ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.p_mdm_org ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_org_user ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.p_mdm_org_user ALTER COLUMN del_flag SET DEFAULT 0;
ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN del_flag TYPE int2 USING COALESCE(NULLIF(BTRIM(del_flag), ''), '0')::int2;
ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN del_flag SET DEFAULT 0;

COMMIT;
