-- com_extract_standardization_item表新增standard_type字段，match_mode、output_mode允许为空
-- 创建时间: 2026-08-07

-- 1、新增standard_type字段
ALTER TABLE `com_extract_standardization_item`
ADD COLUMN `standard_type` VARCHAR(20) NULL COMMENT '标准化类型;ROW|TABLE' AFTER `table_comment`;

-- 2、设置初始值为ROW
UPDATE `com_extract_standardization_item` SET `standard_type` = 'ROW' WHERE `standard_type` IS NULL;

-- 3、match_mode、output_mode设置为允许空
ALTER TABLE `com_extract_standardization_item`
MODIFY COLUMN `match_mode` VARCHAR(200) NULL COMMENT '匹配方式;REGEX|AVIATOR|NONE';

ALTER TABLE `com_extract_standardization_item`
MODIFY COLUMN `output_mode` VARCHAR(200) NULL COMMENT '输出方式;CONSTANT|AVIATOR';
