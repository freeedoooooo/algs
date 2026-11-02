-- MySQL 数据库字段类型调整脚本
-- 执行日期: 2026-06-18
-- 说明: 将 com_extract_doc_type 表的6个字段和 com_extract_rule_column 表的 necessary_flag 字段从 char 类型调整为 tinyint 类型

-- ========================================
-- 1. com_extract_doc_type 表字段调整
-- ========================================

-- doc_unique_flag: 是否控制上传唯一性标识
ALTER TABLE com_extract_doc_type 
MODIFY COLUMN doc_unique_flag TINYINT(1) DEFAULT 0 COMMENT '是否控制上传唯一性(1|0:是|否)';

-- extract_flag: 提取标识
ALTER TABLE com_extract_doc_type 
MODIFY COLUMN extract_flag TINYINT(1) DEFAULT 1 COMMENT '提取标识(1|0:提取|不提取)';

-- need_authorize_flag: 是否需要授权标识
ALTER TABLE com_extract_doc_type 
MODIFY COLUMN need_authorize_flag TINYINT(1) DEFAULT 0 COMMENT '是否需要授权(1|0:是|否)';

-- report_date_flag: 是否涉及报告期标识
ALTER TABLE com_extract_doc_type 
MODIFY COLUMN report_date_flag TINYINT(1) DEFAULT 0 COMMENT '是否涉及报告期(1|0:是|否)';

-- show_flag: 显示标识
ALTER TABLE com_extract_doc_type 
MODIFY COLUMN show_flag TINYINT(1) DEFAULT 1 COMMENT '显示标识(1|0:显示|隐藏)';

-- upload_flag: 是否需要上传标识
ALTER TABLE com_extract_doc_type 
MODIFY COLUMN upload_flag TINYINT(1) DEFAULT 1 COMMENT '是否需要上传(1|0:是|否)';

-- ========================================
-- 2. com_extract_rule_column 表字段调整
-- ========================================

-- necessary_flag: 是否必须提取标识
ALTER TABLE com_extract_rule_column 
MODIFY COLUMN necessary_flag TINYINT(1) DEFAULT 0 COMMENT '是否必须提取(1|0:是|否)';

-- dict_flag: 删除字典标识字段（已废弃）
ALTER TABLE com_extract_rule_column
DROP COLUMN dict_flag;

-- ========================================
-- 3. com_extract_doc_type_dir 表 enable_flag 字段
-- ========================================
ALTER TABLE com_extract_doc_type_dir
MODIFY COLUMN enable_flag TINYINT(1) DEFAULT 1 COMMENT '是否激活(1|0:是|否)';

-- ========================================
-- 4. com_extract_table_column 表 nullable_flag 字段
-- ========================================
ALTER TABLE com_extract_table_column
MODIFY COLUMN nullable_flag TINYINT(1) DEFAULT 1 COMMENT '是否可为空(1|0:是|否)';