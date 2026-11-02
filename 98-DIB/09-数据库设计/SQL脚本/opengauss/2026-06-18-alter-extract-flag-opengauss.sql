-- OpenGauss 数据库字段类型调整脚本
-- 执行日期: 2026-06-18
-- 说明: 将 com_extract_doc_type 表的6个字段和 com_extract_rule_column 表的 necessary_flag 字段从 char 类型调整为 smallint 类型

-- ========================================
-- 0. 数据备份（重要！执行前请先备份）
-- ========================================

-- 备份 com_extract_doc_type 表
CREATE TABLE com_extract_doc_type_backup_20260618 AS 
SELECT * FROM com_extract_doc_type;

-- 备份 com_extract_rule_column 表
CREATE TABLE com_extract_rule_column_backup_20260618 AS 
SELECT * FROM com_extract_rule_column;

-- 备份 com_extract_doc_type_dir 表
CREATE TABLE com_extract_doc_type_dir_backup_20260618 AS 
SELECT * FROM com_extract_doc_type_dir;

-- 备份 com_extract_table_column 表
CREATE TABLE com_extract_table_column_backup_20260618 AS 
SELECT * FROM com_extract_table_column;

-- 验证备份数据量
SELECT 'com_extract_doc_type' as table_name, COUNT(*) as row_count FROM com_extract_doc_type
UNION ALL
SELECT 'com_extract_doc_type_backup_20260618', COUNT(*) FROM com_extract_doc_type_backup_20260618
UNION ALL
SELECT 'com_extract_rule_column', COUNT(*) FROM com_extract_rule_column
UNION ALL
SELECT 'com_extract_rule_column_backup_20260618', COUNT(*) FROM com_extract_rule_column_backup_20260618
UNION ALL
SELECT 'com_extract_doc_type_dir', COUNT(*) FROM com_extract_doc_type_dir
UNION ALL
SELECT 'com_extract_doc_type_dir_backup_20260618', COUNT(*) FROM com_extract_doc_type_dir_backup_20260618
UNION ALL
SELECT 'com_extract_table_column', COUNT(*) FROM com_extract_table_column
UNION ALL
SELECT 'com_extract_table_column_backup_20260618', COUNT(*) FROM com_extract_table_column_backup_20260618;

-- ========================================
-- 1. com_extract_doc_type 表字段调整
-- ========================================

-- doc_unique_flag: 是否控制上传唯一性标识

ALTER TABLE com_extract_doc_type
    ALTER COLUMN doc_unique_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type 
ALTER COLUMN doc_unique_flag TYPE SMALLINT 
USING CASE WHEN doc_unique_flag = '1' OR doc_unique_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type.doc_unique_flag IS '是否控制上传唯一性(1|0:是|否)';

-- extract_flag: 提取标识

ALTER TABLE com_extract_doc_type
    ALTER COLUMN extract_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type 
ALTER COLUMN extract_flag TYPE SMALLINT 
USING CASE WHEN extract_flag = '1' OR extract_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type.extract_flag IS '提取标识(1|0:提取|不提取)';

-- need_authorize_flag: 是否需要授权标识

ALTER TABLE com_extract_doc_type
    ALTER COLUMN need_authorize_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type 
ALTER COLUMN need_authorize_flag TYPE SMALLINT 
USING CASE WHEN need_authorize_flag = '1' OR need_authorize_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type.need_authorize_flag IS '是否需要授权(1|0:是|否)';

-- report_date_flag: 是否涉及报告期标识

ALTER TABLE com_extract_doc_type
    ALTER COLUMN report_date_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type 
ALTER COLUMN report_date_flag TYPE SMALLINT 
USING CASE WHEN report_date_flag = '1' OR report_date_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type.report_date_flag IS '是否涉及报告期(1|0:是|否)';

-- show_flag: 显示标识

ALTER TABLE com_extract_doc_type
    ALTER COLUMN show_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type 
ALTER COLUMN show_flag TYPE SMALLINT 
USING CASE WHEN show_flag = '1' OR show_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type.show_flag IS '显示标识(1|0:显示|隐藏)';

-- upload_flag: 是否需要上传标识

ALTER TABLE com_extract_doc_type
    ALTER COLUMN upload_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type 
ALTER COLUMN upload_flag TYPE SMALLINT 
USING CASE WHEN upload_flag = '1' OR upload_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type.upload_flag IS '是否需要上传(1|0:是|否)';

-- ========================================
-- 2. com_extract_rule_column 表字段调整
-- ========================================

-- necessary_flag: 是否必须提取标识

ALTER TABLE com_extract_rule_column
    ALTER COLUMN necessary_flag DROP DEFAULT;

ALTER TABLE com_extract_rule_column 
ALTER COLUMN necessary_flag TYPE SMALLINT 
USING CASE WHEN necessary_flag = '1' OR necessary_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_rule_column.necessary_flag IS '是否必须提取(1|0:是|否)';

-- dict_flag: 删除字典标识字段（已废弃）
ALTER TABLE com_extract_rule_column 
DROP COLUMN dict_flag;

-- ========================================
-- 3. com_extract_doc_type_dir 表 enable_flag 字段
-- ========================================

ALTER TABLE com_extract_rule_column
    ALTER COLUMN enable_flag DROP DEFAULT;

ALTER TABLE com_extract_doc_type_dir
ALTER COLUMN enable_flag TYPE SMALLINT
USING CASE WHEN enable_flag = '1' OR enable_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_doc_type_dir.enable_flag IS '是否激活(1|0:是|否)';

-- ========================================
-- 4. com_extract_table_column 表 nullable_flag 字段
-- ========================================
-- 先删除默认值
ALTER TABLE com_extract_table_column
ALTER COLUMN nullable_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_extract_table_column
ALTER COLUMN nullable_flag TYPE SMALLINT
USING CASE WHEN nullable_flag = '1' OR nullable_flag = 1 THEN 1 ELSE 0 END;

COMMENT ON COLUMN com_extract_table_column.nullable_flag IS '是否可为空(1|0:是|否)';