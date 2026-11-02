-- 删除com_data_dim_auth_rule表的include_self字段
-- 执行日期: 2026-08-13

ALTER TABLE dib_report_copilot.com_data_dim_auth_rule DROP COLUMN include_self;
