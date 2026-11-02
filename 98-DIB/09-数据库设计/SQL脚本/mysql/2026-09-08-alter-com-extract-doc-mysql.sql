-- 为 com_extract_doc 表添加自动提取失败重试次数字段
-- 执行日期：2026-09-08

-- ========================================
-- 1. com_extract_doc 表添加 extract_retry_count 字段
-- ========================================
ALTER TABLE com_extract_doc ADD COLUMN extract_retry_count INTEGER DEFAULT 0 COMMENT '自动提取失败重试次数';
