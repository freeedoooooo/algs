-- MySQL 数据库 bit 类型字段调整为 smallint 类型脚本
-- 执行日期: 2026-07-09
-- 说明: 将 MySQL 中的 bit(1) 类型字段统一调整为 smallint 类型，便于后续迁移到 OpenGauss

-- ========================================
-- 1. com_check_param 表 source_flag 字段调整
-- ========================================

-- source_flag: 来源标识
ALTER TABLE com_check_param 
MODIFY COLUMN source_flag SMALLINT DEFAULT NULL COMMENT '来源标识(1|0)';

-- ========================================
-- 2. com_check_rule 表 must_pass_flag 字段调整
-- ========================================

-- must_pass_flag: 必须通过标识
ALTER TABLE com_check_rule 
MODIFY COLUMN must_pass_flag SMALLINT DEFAULT NULL COMMENT '必须通过标识(1|0)';

-- ========================================
-- 3. com_check_rule_result 表 pass_flag 字段调整
-- ========================================

-- pass_flag: 通过标识(NOT NULL)
ALTER TABLE com_check_rule_result 
MODIFY COLUMN pass_flag SMALLINT NOT NULL DEFAULT 0 COMMENT '通过标识(1|0)';

-- ========================================
-- 4. com_data_dim_auth_rule 表 include_self 字段调整
-- ========================================

-- include_self: 包含自身标识
ALTER TABLE com_data_dim_auth_rule 
MODIFY COLUMN include_self SMALLINT DEFAULT 1 COMMENT '包含自身标识(1|0)';

-- ========================================
-- 5. com_data_metadata_field 表字段调整
-- ========================================

-- key_flag: 主键标识(NOT NULL, 默认值 0)
ALTER TABLE com_data_metadata_field 
MODIFY COLUMN key_flag SMALLINT NOT NULL DEFAULT 0 COMMENT '主键标识(1|0)';

-- nullable_flag: 可空标识(NOT NULL, 默认值 0)
ALTER TABLE com_data_metadata_field 
MODIFY COLUMN nullable_flag SMALLINT NOT NULL DEFAULT 0 COMMENT '可空标识(1|0)';

-- ========================================
-- 6. com_di_table_field 表字段调整
-- ========================================

-- key_flag: 主键标识(NOT NULL, 默认值 0)
ALTER TABLE com_di_table_field 
MODIFY COLUMN key_flag SMALLINT NOT NULL DEFAULT 0 COMMENT '主键标识(1|0)';

-- nullable_flag: 可空标识(NOT NULL, 默认值 0)
ALTER TABLE com_di_table_field 
MODIFY COLUMN nullable_flag SMALLINT NOT NULL DEFAULT 0 COMMENT '可空标识(1|0)';

-- search_flag: 搜索标识(NOT NULL, 默认值 1)
ALTER TABLE com_di_table_field 
MODIFY COLUMN search_flag SMALLINT NOT NULL DEFAULT 1 COMMENT '搜索标识(1|0)';

-- show_flag: 显示标识(NOT NULL, 默认值 1)
ALTER TABLE com_di_table_field 
MODIFY COLUMN show_flag SMALLINT NOT NULL DEFAULT 1 COMMENT '显示标识(1|0)';

-- ========================================
-- 7. com_task_monitor 表 ready_flag 字段调整
-- ========================================

-- ready_flag: 就绪标识(NOT NULL, 默认值 0)
ALTER TABLE com_task_monitor 
MODIFY COLUMN ready_flag SMALLINT NOT NULL DEFAULT 0 COMMENT '就绪标识(1|0)';

-- ========================================
-- 8. 验证转换结果
-- ========================================
