-- 为 p_mdm_feedback 表添加 share_flag 字段
-- 执行日期: 2026-10-10
-- 说明: 新增是否分享标识，与 FeedbackEntity.shareFlag 字段对应

ALTER TABLE p_mdm_feedback
ADD COLUMN share_flag SMALLINT DEFAULT 0;

COMMENT ON COLUMN p_mdm_feedback.share_flag IS '是否分享(1|0)';