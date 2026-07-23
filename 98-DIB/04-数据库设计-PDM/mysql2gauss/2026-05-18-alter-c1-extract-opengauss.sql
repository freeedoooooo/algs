-- Entity refactor migration for extract service
-- openGauss version
-- Align table audit columns with BaseEntity fields.

ALTER TABLE com_extract_doc RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_del RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_del RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_del ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_del ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_del ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_del.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_del.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_del.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_dir RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_dir RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_dir ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_dir ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_dir ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_dir.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_dir.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_dir.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_type RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_type ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_type.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_type.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_type.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_type_bus RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type_bus RENAME COLUMN updated_by TO update_user_id;
ALTER TABLE com_extract_doc_type_bus RENAME COLUMN updated_time TO update_time;
ALTER TABLE com_extract_doc_type_bus ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_bus ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_bus ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_type_bus.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_type_bus.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_type_bus.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_type_dir RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type_dir RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_type_dir ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_dir ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_dir ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_type_dir.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_type_dir.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_type_dir.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_type_filter RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type_filter RENAME COLUMN updated_by TO update_user_id;
ALTER TABLE com_extract_doc_type_filter RENAME COLUMN updated_time TO update_time;
ALTER TABLE com_extract_doc_type_filter ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_filter ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_filter ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_type_filter.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_type_filter.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_type_filter.del_flag IS '删除标识';

ALTER TABLE com_extract_doc_type_relation RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type_relation RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_type_relation ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_relation ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_doc_type_relation ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_doc_type_relation.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_doc_type_relation.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_doc_type_relation.del_flag IS '删除标识';

ALTER TABLE com_extract_rule RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_rule RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_rule ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_rule ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_rule ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_rule.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_rule.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_rule.del_flag IS '删除标识';

ALTER TABLE com_extract_rule_column RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_rule_column RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_rule_column ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_rule_column ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_rule_column ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_rule_column.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_rule_column.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_rule_column.del_flag IS '删除标识';

ALTER TABLE com_extract_table RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_table RENAME COLUMN updated_by TO update_user_id;
ALTER TABLE com_extract_table RENAME COLUMN updated_time TO update_time;
ALTER TABLE com_extract_table ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_table ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_table ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_table.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_table.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_table.del_flag IS '删除标识';

ALTER TABLE com_extract_table_column RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_table_column RENAME COLUMN updated_by TO update_user_id;
ALTER TABLE com_extract_table_column RENAME COLUMN updated_time TO update_time;
ALTER TABLE com_extract_table_column ADD COLUMN add_user_name VARCHAR(100);
ALTER TABLE com_extract_table_column ADD COLUMN update_user_name VARCHAR(100);
ALTER TABLE com_extract_table_column ADD COLUMN del_flag INT2 NOT NULL DEFAULT 0;
COMMENT ON COLUMN com_extract_table_column.add_user_name IS '新增人姓名';
COMMENT ON COLUMN com_extract_table_column.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_table_column.del_flag IS '删除标识';
