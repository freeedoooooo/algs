-- 修改p_mdm_sys_param表的param_value字段长度为2000
ALTER TABLE p_mdm_sys_param
MODIFY COLUMN `param_value` VARCHAR(4000) NULL COMMENT '参数值';
