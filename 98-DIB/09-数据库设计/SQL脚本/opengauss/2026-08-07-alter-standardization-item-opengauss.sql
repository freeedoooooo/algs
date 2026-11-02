-- com_extract_standardization_item表新增standard_type字段，match_mode、output_mode允许为空
-- 创建时间: 2026-08-07

-- 1、新增standard_type字段
ALTER TABLE com_extract_standardization_item ADD COLUMN standard_type VARCHAR(60);
COMMENT ON COLUMN com_extract_standardization_item.standard_type IS '标准化类型 ROW|TABLE';

-- 2、设置初始值为ROW
UPDATE com_extract_standardization_item SET standard_type = 'ROW' WHERE standard_type IS NULL;

-- 3、match_mode、output_mode设置为允许空
ALTER TABLE com_extract_standardization_item ALTER COLUMN match_mode DROP NOT NULL;
ALTER TABLE com_extract_standardization_item ALTER COLUMN output_mode DROP NOT NULL;
