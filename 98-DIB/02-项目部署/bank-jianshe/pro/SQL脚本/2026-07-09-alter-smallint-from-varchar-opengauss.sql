-- OpenGauss 数据库 varchar 类型字段调整为 smallint 类型脚本
-- source_flag: 来源标识
ALTER TABLE com_check_param
ALTER COLUMN source_flag TYPE SMALLINT
USING CASE
    WHEN source_flag = '1' OR source_flag = 1 THEN 1
    WHEN source_flag = '0' OR source_flag = 0 THEN 0
    ELSE 0
END;

COMMENT ON COLUMN com_check_param.source_flag IS '来源标识(1|0)';

-- must_pass_flag: 必须通过标识
ALTER TABLE com_check_rule
ALTER COLUMN must_pass_flag TYPE SMALLINT
USING CASE
    WHEN must_pass_flag = '1' OR must_pass_flag = 1 THEN 1
    WHEN must_pass_flag = '0' OR must_pass_flag = 0 THEN 0
    ELSE NULL
END;

COMMENT ON COLUMN com_check_rule.must_pass_flag IS '必须通过标识(1|0)';

-- pass_flag: 通过标识(NOT NULL)
ALTER TABLE com_check_rule_result
ALTER COLUMN pass_flag TYPE SMALLINT
USING CASE
    WHEN pass_flag = '1' OR pass_flag = 1 THEN 1
    WHEN pass_flag = '0' OR pass_flag = 0 THEN 0
    ELSE 0
END;

COMMENT ON COLUMN com_check_rule_result.pass_flag IS '通过标识(1|0)';

-- key_flag: 主键标识(NOT NULL, 默认值 '0')
-- 先删除默认值
ALTER TABLE com_data_metadata_field
ALTER COLUMN key_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_data_metadata_field
ALTER COLUMN key_flag TYPE SMALLINT
USING CASE
    WHEN key_flag = '1' OR key_flag = 1 THEN 1
    WHEN key_flag = '0' OR key_flag = 0 THEN 0
    ELSE 0
END;

-- 设置新的默认值
ALTER TABLE com_data_metadata_field
ALTER COLUMN key_flag SET DEFAULT 0;

COMMENT ON COLUMN com_data_metadata_field.key_flag IS '主键标识(1|0)';

-- nullable_flag: 可空标识(NOT NULL, 默认值 '0')
-- 先删除默认值
ALTER TABLE com_data_metadata_field
ALTER COLUMN nullable_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_data_metadata_field
ALTER COLUMN nullable_flag TYPE SMALLINT
USING CASE
    WHEN nullable_flag = '1' OR nullable_flag = 1 THEN 1
    WHEN nullable_flag = '0' OR nullable_flag = 0 THEN 0
    ELSE 0
END;

-- 设置新的默认值
ALTER TABLE com_data_metadata_field
ALTER COLUMN nullable_flag SET DEFAULT 0;

COMMENT ON COLUMN com_data_metadata_field.nullable_flag IS '可空标识(1|0)';

-- key_flag: 主键标识(NOT NULL, 默认值 '0')
-- 先删除默认值
ALTER TABLE com_di_table_field
ALTER COLUMN key_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_di_table_field
ALTER COLUMN key_flag TYPE SMALLINT
USING CASE
    WHEN key_flag = '1' OR key_flag = 1 THEN 1
    WHEN key_flag = '0' OR key_flag = 0 THEN 0
    ELSE 0
END;

-- 设置新的默认值
ALTER TABLE com_di_table_field
ALTER COLUMN key_flag SET DEFAULT 0;

COMMENT ON COLUMN com_di_table_field.key_flag IS '主键标识(1|0)';

-- nullable_flag: 可空标识(NOT NULL, 默认值 '0')
-- 先删除默认值
ALTER TABLE com_di_table_field
ALTER COLUMN nullable_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_di_table_field
ALTER COLUMN nullable_flag TYPE SMALLINT
USING CASE
    WHEN nullable_flag = '1' OR nullable_flag = 1 THEN 1
    WHEN nullable_flag = '0' OR nullable_flag = 0 THEN 0
    ELSE 0
END;

-- 设置新的默认值
ALTER TABLE com_di_table_field
ALTER COLUMN nullable_flag SET DEFAULT 0;

COMMENT ON COLUMN com_di_table_field.nullable_flag IS '可空标识(1|0)';

-- search_flag: 搜索标识(NOT NULL, 默认值 '1')
-- 先删除默认值
ALTER TABLE com_di_table_field
ALTER COLUMN search_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_di_table_field
ALTER COLUMN search_flag TYPE SMALLINT
USING CASE
    WHEN search_flag = '1' OR search_flag = 1 THEN 1
    WHEN search_flag = '0' OR search_flag = 0 THEN 0
    ELSE 1
END;

-- 设置新的默认值
ALTER TABLE com_di_table_field
ALTER COLUMN search_flag SET DEFAULT 1;

COMMENT ON COLUMN com_di_table_field.search_flag IS '搜索标识(1|0)';

-- show_flag: 显示标识(NOT NULL, 默认值 '1')
-- 先删除默认值
ALTER TABLE com_di_table_field
ALTER COLUMN show_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_di_table_field
ALTER COLUMN show_flag TYPE SMALLINT
USING CASE
    WHEN show_flag = '1' OR show_flag = 1 THEN 1
    WHEN show_flag = '0' OR show_flag = 0 THEN 0
    ELSE 1
END;

-- 设置新的默认值
ALTER TABLE com_di_table_field
ALTER COLUMN show_flag SET DEFAULT 1;

COMMENT ON COLUMN com_di_table_field.show_flag IS '显示标识(1|0)';

-- ready_flag: 就绪标识(NOT NULL, 默认值 '0')
-- 先删除默认值
ALTER TABLE com_task_monitor
ALTER COLUMN ready_flag DROP DEFAULT;

-- 修改字段类型
ALTER TABLE com_task_monitor
ALTER COLUMN ready_flag TYPE SMALLINT
USING CASE
    WHEN ready_flag = '1' OR ready_flag = 1 THEN 1
    WHEN ready_flag = '0' OR ready_flag = 0 THEN 0
    ELSE 0
END;

-- 设置新的默认值
ALTER TABLE com_task_monitor
ALTER COLUMN ready_flag SET DEFAULT 0;

COMMENT ON COLUMN com_task_monitor.ready_flag IS '就绪标识(1|0)';

-- 检查所有修改后的字段类型
SELECT
    table_name AS "表名",
    column_name AS "字段名",
    data_type AS "数据类型",
    numeric_precision AS "数值精度",
    is_nullable AS "是否可空",
    column_default AS "默认值"
FROM information_schema.columns
WHERE table_schema = 'dib_report_copilot'
  AND table_name IN (
      'com_check_param',
      'com_check_rule',
      'com_check_rule_result',
      'com_data_dim_auth_rule',
      'com_data_metadata_field',
      'com_di_table_field',
      'com_task_monitor'
  )
  AND column_name IN (
      'source_flag',
      'must_pass_flag',
      'pass_flag',
      'include_self',
      'key_flag',
      'nullable_flag',
      'search_flag',
      'show_flag',
      'ready_flag'
  )
ORDER BY table_name, ordinal_position;
