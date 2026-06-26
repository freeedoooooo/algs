-- Source MySQL: 10.0.6.161:3306 / dib_report_copilot
-- Target openGauss: 192.168.10.141:5432 / c1 / dib_report_copilot
-- Generated from live metadata on 2026-04-16
-- Rule: set defaults only where MySQL has a default and openGauss default is missing
-- Priority: NOT NULL columns are listed first
-- Generated ALTER statements: 334
-- Skipped columns needing manual review: 0

BEGIN;

-- mysql_default=300000 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN api_timeout SET DEFAULT 300000;

-- mysql_default=text | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN api_type SET DEFAULT 'text';

-- mysql_default=all | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN app SET DEFAULT 'all';

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN enable_search SET DEFAULT 0;

-- mysql_default=10000 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN max_input_tokens SET DEFAULT 10000;

-- mysql_default=10000 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN max_tokens SET DEFAULT 10000;

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN order_num SET DEFAULT 1;

-- mysql_default={"type": "json_object"} | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN response_format SET DEFAULT '{"type": "json_object"}';

-- mysql_default=0.1 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN temperature SET DEFAULT 0.1;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_key ALTER COLUMN charging_flag SET DEFAULT 0;

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_ai_key ALTER COLUMN order_num SET DEFAULT 1;

-- mysql_default=b'1' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_check_param ALTER COLUMN source_flag SET DEFAULT '1';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_board_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_board_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=0 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN order_num SET DEFAULT '0';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_board_view_field ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=1 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_board_view_field ALTER COLUMN show_flag SET DEFAULT 1;

-- mysql_default=IN | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_dim_auth_rule ALTER COLUMN dim_compare SET DEFAULT 'IN';

-- mysql_default=NONE | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_dim_auth_rule ALTER COLUMN include_children SET DEFAULT 'NONE';

-- mysql_default=0 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_domain_relation ALTER COLUMN add_user_id SET DEFAULT '0';

-- mysql_default=01 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_domain_relation ALTER COLUMN domain_id_path SET DEFAULT '01';

-- mysql_default=SQL_FUNC | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_info ALTER COLUMN index_formula_type SET DEFAULT 'SQL_FUNC';

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_ref_item ALTER COLUMN master_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_ref_item ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_ref_item_field ALTER COLUMN calc_dim_flag SET DEFAULT 0;

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_ref_item_field ALTER COLUMN target_dimension_depth SET DEFAULT 1;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN cost_time SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN finish_dim_count SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN primary_dim_count SET DEFAULT 0;

-- mysql_default=5 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN task_priority SET DEFAULT 5;

-- mysql_default=NOT_START | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN task_status SET DEFAULT 'NOT_START';

-- mysql_default=AUTO | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN task_type SET DEFAULT 'AUTO';

-- mysql_default=0 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_domain_relation ALTER COLUMN add_user_id SET DEFAULT '0';

-- mysql_default=01 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_domain_relation ALTER COLUMN domain_id_path SET DEFAULT '01';

-- mysql_default=b'0' | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_field ALTER COLUMN key_flag SET DEFAULT 0;

-- mysql_default=b'0' | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_field ALTER COLUMN nullable_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_field_map ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_lineage ALTER COLUMN add_user_id SET DEFAULT '0';

-- mysql_default=01 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_data_metadata_lineage ALTER COLUMN lineage_type SET DEFAULT '01';

-- mysql_default=  | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_dir_table ALTER COLUMN add_user_id SET DEFAULT ' ';

-- mysql_default=01 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_dir_table ALTER COLUMN dir_id_path SET DEFAULT '01';

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_dir_table ALTER COLUMN order_num SET DEFAULT 1;

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN order_num SET DEFAULT 1;

-- mysql_default=无 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_index ALTER COLUMN unit_name SET DEFAULT '无';

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN index_linked_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=b'0' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN key_flag SET DEFAULT '0';

-- mysql_default=b'0' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN nullable_flag SET DEFAULT '0';

-- mysql_default=b'1' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN search_flag SET DEFAULT '1';

-- mysql_default=b'1' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN show_flag SET DEFAULT '1';

-- mysql_default=无 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN unit_name SET DEFAULT '无';

-- mysql_default=-1 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN att_id SET DEFAULT -1;

-- mysql_default=05 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN classify_state SET DEFAULT '05';

-- mysql_default=0.00 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN completion_rate SET DEFAULT 0.00;

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN convert_duration SET DEFAULT 1;

-- mysql_default=05 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN convert_state SET DEFAULT '05';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN doc_size SET DEFAULT 0;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN extract_state SET DEFAULT 'U';

-- mysql_default=0.00 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN machine_completion_rate SET DEFAULT 0.00;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN scanned_copy_flag SET DEFAULT 0;

-- mysql_default=-1 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN att_id SET DEFAULT -1;

-- mysql_default=05 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN classify_state SET DEFAULT '05';

-- mysql_default=0.000000 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN completion_rate SET DEFAULT 0.000000;

-- mysql_default=1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN convert_duration SET DEFAULT 1;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN convert_state SET DEFAULT 'U';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN doc_size SET DEFAULT 0;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN extract_state SET DEFAULT 'U';

-- mysql_default=0.000000 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN machine_completion_rate SET DEFAULT 0.000000;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN scanned_copy_flag SET DEFAULT 0;

-- mysql_default=-1 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_dir ALTER COLUMN parent_id SET DEFAULT -1;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_dir ALTER COLUMN sort_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN dir_id SET DEFAULT 0;

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN doc_unique_flag SET DEFAULT '1';

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN extract_flag SET DEFAULT '1';

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN need_authorize_flag SET DEFAULT '1';

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN report_date_flag SET DEFAULT '1';

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN show_flag SET DEFAULT '1';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN sort_num SET DEFAULT 0;

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN upload_flag SET DEFAULT '1';

-- mysql_default=-1 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type_bus ALTER COLUMN doc_type_id SET DEFAULT -1;

-- mysql_default=-1 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type_dir ALTER COLUMN parent_id SET DEFAULT -1;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type_dir ALTER COLUMN sort_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type_template ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_doc_type_template ALTER COLUMN template_att_id SET DEFAULT 0;

-- mysql_default=doris | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_etl_table ALTER COLUMN src_data_source_code SET DEFAULT 'doris';

-- mysql_default=default | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_etl_table ALTER COLUMN target_data_source_code SET DEFAULT 'default';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=0.000000 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_rate_bak ALTER COLUMN completion_rate SET DEFAULT 0.000000;

-- mysql_default=0.000000 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_rate_bak ALTER COLUMN machine_completion_rate SET DEFAULT 0.000000;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN audit_duration SET DEFAULT 0;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN audit_state SET DEFAULT 'U';

-- mysql_default=0.00 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN completion_rate SET DEFAULT 0.00;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN entry_duration SET DEFAULT 0;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN extract_state SET DEFAULT 'U';

-- mysql_default=4102415999999 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN lock_time SET DEFAULT 4102415999999;

-- mysql_default=0.00 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN machine_completion_rate SET DEFAULT 0.00;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN audit_duration SET DEFAULT 0;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN audit_state SET DEFAULT 'U';

-- mysql_default=0.00 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN completion_rate SET DEFAULT 0.00;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN entry_duration SET DEFAULT 0;

-- mysql_default=U | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN extract_state SET DEFAULT 'U';

-- mysql_default=4102415999999 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN lock_time SET DEFAULT 4102415999999;

-- mysql_default=0.00 | og_type=numeric | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN machine_completion_rate SET DEFAULT 0.00;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_rule ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=varchar | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_rule_column ALTER COLUMN column_type SET DEFAULT 'varchar';

-- mysql_default=1 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_rule_column ALTER COLUMN necessary_flag SET DEFAULT '1';

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_rule_column ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=b'1' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_extract_table_column ALTER COLUMN nullable_flag SET DEFAULT '1';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=1 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN apply_flag SET DEFAULT 1;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN calc_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN major_version SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN minor_version SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN patch_version SET DEFAULT 0;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN schedule_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_info ALTER COLUMN version_seq SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_node ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_revise_item ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=-1 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_frame_value ALTER COLUMN node_level SET DEFAULT -1;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_report_export_log ALTER COLUMN first_gen_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_report_var ALTER COLUMN lock_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=SUCCESS | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_template_var ALTER COLUMN template_var_status SET DEFAULT 'SUCCESS';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var_domain_relation ALTER COLUMN add_user_id SET DEFAULT '0';

-- mysql_default=01 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var_domain_relation ALTER COLUMN domain_id_path SET DEFAULT '01';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var_field ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var_param ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var_param_lib ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rg2_var_param_lib ALTER COLUMN readonly_flag SET DEFAULT 0;

-- mysql_default=01 | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rule_domain_relation ALTER COLUMN domain_id_path SET DEFAULT '01';

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_rule_tree ALTER COLUMN default_dim_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN cost_time SET DEFAULT 0;

-- mysql_default=b'0' | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN ready_flag SET DEFAULT '0';

-- mysql_default=AUTO | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN task_category SET DEFAULT 'AUTO';

-- mysql_default=5 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN task_priority SET DEFAULT 5;

-- mysql_default=0 | og_type=float8 | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN task_progress SET DEFAULT 0;

-- mysql_default=NOT_START | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN task_status SET DEFAULT 'NOT_START';

-- mysql_default=AUTO | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN task_type SET DEFAULT 'AUTO';



-- mysql_default=9999-12-31 | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.dim_area ALTER COLUMN end_date SET DEFAULT '9999-12-31';

-- mysql_default=1900-01-01 | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.dim_area ALTER COLUMN start_date SET DEFAULT '1900-01-01';

-- mysql_default=9999-12-31 | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.dim_report_date ALTER COLUMN end_date SET DEFAULT '9999-12-31';

-- mysql_default=1900-01-01 | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.dim_report_date ALTER COLUMN start_date SET DEFAULT '1900-01-01';

-- mysql_default=0 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_customer ALTER COLUMN customer_state SET DEFAULT '0';

-- mysql_default=01 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_customer ALTER COLUMN customer_type SET DEFAULT '01';

-- mysql_default=LEFT | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_customer ALTER COLUMN menu_layout SET DEFAULT 'LEFT';

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_login_log ALTER COLUMN login_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_module ALTER COLUMN admin_flag SET DEFAULT 0;

-- mysql_default= | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_module ALTER COLUMN alias SET DEFAULT '';

-- mysql_default=01 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_module ALTER COLUMN module_type SET DEFAULT '01';

-- mysql_default=1 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_auth_user_session ALTER COLUMN online_flag SET DEFAULT 1;

-- mysql_default=1 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_attachment ALTER COLUMN active_flag SET DEFAULT 1;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_attachment ALTER COLUMN security_level SET DEFAULT 0;

-- mysql_default=05 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_attachment ALTER COLUMN storage_type SET DEFAULT '05';

-- mysql_default=01 | og_type=bpchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_dict_def ALTER COLUMN dict_type SET DEFAULT '01';

-- mysql_default=0 | og_type=int2 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_org_user ALTER COLUMN belong_flag SET DEFAULT 0;

-- mysql_default= | og_type=varchar | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_org_user ALTER COLUMN user_name SET DEFAULT '';

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_project_type ALTER COLUMN order_num SET DEFAULT 0;

-- mysql_default=1 | og_type=int8 | og_nullable=NO
ALTER TABLE dib_report_copilot.p_mdm_project_type_ext ALTER COLUMN project_type_id SET DEFAULT 1;

-- mysql_default=0 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN enable_thinking SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_ai_client ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_ai_key ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=0 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_check_rule_result ALTER COLUMN verify_duration SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_board ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_board_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_board_view ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=0 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_board_view_field ALTER COLUMN explicit_filter_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_board_view_field ALTER COLUMN implicit_filter_flag SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_board_view_field ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=b'1' | og_type=varchar | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_dim_auth_rule ALTER COLUMN include_self SET DEFAULT '1';

-- mysql_default=GLOBAL | og_type=varchar | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_dim_auth_rule ALTER COLUMN scope_type SET DEFAULT 'GLOBAL';

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN finish_count SET DEFAULT 0;

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_index_task ALTER COLUMN total_count SET DEFAULT 0;

-- mysql_default=1 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_metadata_field ALTER COLUMN dimension_max_depth SET DEFAULT 1;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_metadata_tag ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_metadata_tag ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=30000 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN connection_timeout SET DEFAULT 30000;

-- mysql_default=60000 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN idle_timeout SET DEFAULT 60000;

-- mysql_default=10 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN max_pool_size SET DEFAULT 10;

-- mysql_default=5 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_data_source ALTER COLUMN min_pool_size SET DEFAULT 5;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_customer_auth ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_index_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_index_opt_record ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_table_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=1 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_table_field ALTER COLUMN dimension_max_depth SET DEFAULT 1;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_table_opt_record ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_di_user_search_record ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=U | og_type=bpchar | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN audit_state SET DEFAULT 'U';

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN dir_id SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=U | og_type=bpchar | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN audit_state SET DEFAULT 'U';

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_del ALTER COLUMN dir_id SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_type ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_type_bus ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_type_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_type_relation ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_doc_type_template ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_inventory ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_inventory_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=U | og_type=bpchar | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_result ALTER COLUMN verify_state SET DEFAULT 'U';

-- mysql_default=U | og_type=bpchar | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_result_bak ALTER COLUMN verify_state SET DEFAULT 'U';

-- mysql_default=1 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_extract_rule_column ALTER COLUMN sort_num SET DEFAULT 1;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_frame_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=0 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_report ALTER COLUMN test_flag SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_report ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=1 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_report_export_log ALTER COLUMN success_flag SET DEFAULT 1;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_report_export_log ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_report_user ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_report_var ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=1 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template ALTER COLUMN report_date_necessary_flag SET DEFAULT 1;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=1 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_chapter ALTER COLUMN level SET DEFAULT 1;

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_chapter ALTER COLUMN parent_id SET DEFAULT 0;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_chapter ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_customer ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_var ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_var_field ALTER COLUMN add_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_template_var_field ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_var ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_var_field ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_var_param ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.com_rg2_var_param_lib ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN completion_volume SET DEFAULT 0;

-- mysql_default=-1 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN retry_count SET DEFAULT -1;

-- mysql_default=0 | og_type=int8 | og_nullable=YES
ALTER TABLE dib_report_copilot.com_task_monitor ALTER COLUMN task_volume SET DEFAULT 0;



-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_customer_ip ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_login_log ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_pwd_log ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default=0 | og_type=bpchar | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN lock_flag SET DEFAULT '0';

-- mysql_default=0 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN login_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN pwd_reset_flag SET DEFAULT 0;

-- mysql_default=0 | og_type=int4 | og_nullable=YES
ALTER TABLE dib_report_copilot.p_auth_user ALTER COLUMN security_level SET DEFAULT 0;

-- mysql_default=1 | og_type=int2 | og_nullable=YES
ALTER TABLE dib_report_copilot.p_mdm_dict_item ALTER COLUMN active_flag SET DEFAULT 1;

-- mysql_default=2000-01-01 | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.p_mdm_org ALTER COLUMN enable_date SET DEFAULT '2000-01-01';

-- mysql_default=CURRENT_TIMESTAMP | og_type=timestamp | og_nullable=YES
ALTER TABLE dib_report_copilot.p_mdm_project_dir ALTER COLUMN update_time SET DEFAULT CURRENT_TIMESTAMP;

-- mysql_default= | og_type=varchar | og_nullable=YES
ALTER TABLE dib_report_copilot.p_mdm_sys_param ALTER COLUMN param_desc SET DEFAULT '';

COMMIT;