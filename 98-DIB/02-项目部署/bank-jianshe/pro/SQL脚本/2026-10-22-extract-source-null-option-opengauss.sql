-- 移除过大的转换双层 pdf 结果附件
update com_extract_doc  set double_pdf_id  = null WHERE  double_pdf_id  is not NULL ;

-- 移除 extract_source 字段
ALTER TABLE com_extract_result DROP COLUMN extract_source;
ALTER TABLE com_extract_result_bak DROP COLUMN extract_source;

-- char 类型修改为 varchar 类型
ALTER TABLE com_extract_doc ALTER COLUMN classify_state TYPE VARCHAR(2);
ALTER TABLE com_extract_doc ALTER COLUMN convert_state TYPE VARCHAR(2);
ALTER TABLE com_extract_doc ALTER COLUMN verify_state TYPE VARCHAR(2);
ALTER TABLE com_extract_doc ALTER COLUMN os_convert_state TYPE VARCHAR(2);
ALTER TABLE com_extract_doc_del ALTER COLUMN classify_state TYPE VARCHAR(2);
ALTER TABLE com_extract_doc_del ALTER COLUMN verify_state TYPE VARCHAR(2);
ALTER TABLE com_extract_doc_type ALTER COLUMN group_type TYPE VARCHAR(2);
ALTER TABLE com_extract_rule ALTER COLUMN rule_type TYPE VARCHAR(2);
ALTER TABLE com_extract_table_column ALTER COLUMN column_group TYPE VARCHAR(2);
ALTER TABLE p_auth_customer ALTER COLUMN customer_type TYPE VARCHAR(2);
ALTER TABLE p_auth_module ALTER COLUMN module_type TYPE VARCHAR(2);
ALTER TABLE p_auth_user ALTER COLUMN lock_flag TYPE VARCHAR(2);
ALTER TABLE p_auth_user_unlock_apply ALTER COLUMN apply_state TYPE VARCHAR(2);
ALTER TABLE p_mdm_attachment ALTER COLUMN storage_type TYPE VARCHAR(2);
ALTER TABLE p_mdm_dict_def ALTER COLUMN dict_type TYPE VARCHAR(2);
ALTER TABLE p_mdm_org ALTER COLUMN org_type TYPE VARCHAR(2);