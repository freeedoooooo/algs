-- V1.0.0__add_extract_fields.sql
-- 描述：新增资料提取相关字段
-- 作者：AI Assistant
-- 日期：2026-05-26

-- ============================================================================
-- 1. com_extract_doc 表新增 SmartOS 相关字段
-- ============================================================================
ALTER TABLE com_extract_doc 
ADD COLUMN os_txt_att_id BIGINT COMMENT '原始文本附件ID(SmartOS转换生成)',
ADD COLUMN os_convert_state VARCHAR(2) DEFAULT 'U' COMMENT 'SmartOS转换状态:U|I|F|Y',
ADD COLUMN os_convert_duration INT DEFAULT 0 COMMENT 'SmartOS转换耗时(秒)';

-- ============================================================================
-- 2. com_extract_result 表新增提取来源字段
-- ============================================================================
ALTER TABLE com_extract_result 
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'NONE' COMMENT '提取来源:NONE|OS|C1';

-- ============================================================================
-- 3. com_extract_result_bak 表新增提取来源字段
-- ============================================================================
ALTER TABLE com_extract_result_bak 
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'NONE' COMMENT '提取来源:NONE|OS|C1';

-- ============================================================================
-- 4. 添加索引（根据查询需求决定是否启用）
-- ============================================================================
-- 如果经常按提取来源统计，可以启用以下索引
-- CREATE INDEX idx_extract_source ON com_extract_result(extract_source);

-- 如果经常按 SmartOS 转换状态查询，可以启用以下索引
-- CREATE INDEX idx_os_convert_state ON com_extract_doc(os_convert_state);
