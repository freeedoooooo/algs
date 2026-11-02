-- 为com_di_index表添加报告日期类型字段 - OpenGauss适配脚本
ALTER TABLE com_di_index
ADD COLUMN report_date_type VARCHAR(20) DEFAULT 'NONE';

-- 添加字段注释
COMMENT ON COLUMN com_di_index.report_date_type IS '报告日期类型:NONE|REGULAR|DAILY|ZIPPER';
