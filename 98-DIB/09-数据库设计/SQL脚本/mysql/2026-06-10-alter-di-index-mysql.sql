-- 为com_di_index表添加报告日期类型字段
ALTER TABLE com_di_index
ADD COLUMN report_date_type VARCHAR(20) DEFAULT 'NONE' COMMENT '报告日期类型:NONE|REGULAR|DAILY|ZIPPER';
