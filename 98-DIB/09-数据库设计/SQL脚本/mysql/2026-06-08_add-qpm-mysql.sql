-- 为com_ai_client表添加qpm字段（每分钟请求数限制）
-- qpm: Queries Per Minute，用于控制API调用频率

ALTER TABLE com_ai_client
ADD COLUMN qpm INT NULL DEFAULT 0 COMMENT '每分钟请求数限制（Queries Per Minute）' AFTER model_name;
