# 移除 extract_source 字段
ALTER TABLE com_extract_result DROP COLUMN extract_source;
ALTER TABLE com_extract_result_bak DROP COLUMN extract_source;
