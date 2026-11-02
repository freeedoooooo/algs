-- 修改p_mdm_sys_param表的param_value字段长度为4000
ALTER TABLE p_mdm_sys_param
ALTER COLUMN param_value TYPE VARCHAR(16000);

COMMENT ON COLUMN p_mdm_sys_param.param_value IS '参数值';
