-- 删除com_extract_result和com_extract_result_bak表的suitable字段
-- 执行日期: 2026-08-03

-- ========================================
-- 1. com_extract_result 表删除 suitable 字段
-- ========================================
ALTER TABLE com_extract_result DROP COLUMN suitable;

-- ========================================
-- 2. com_extract_result_bak 表删除 suitable 字段
-- ========================================
ALTER TABLE com_extract_result_bak DROP COLUMN suitable;
