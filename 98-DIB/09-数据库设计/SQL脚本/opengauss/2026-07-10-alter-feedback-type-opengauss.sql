-- 为p_mdm_feedback表添加反馈分类字段，用于区分问题反馈和试用申请
ALTER TABLE p_mdm_feedback
ADD COLUMN feedback_category VARCHAR(50) NULL;

COMMENT ON COLUMN p_mdm_feedback.feedback_category IS '反馈分类;FEEDBACK|TRIAL:问题反馈|试用申请';

-- 将现有记录的feedback_category设置为默认值'FEEDBACK'
UPDATE p_mdm_feedback SET feedback_category = 'FEEDBACK' WHERE feedback_category IS NULL;