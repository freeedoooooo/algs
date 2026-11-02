-- 1. 添加字段（OpenGauss 不支持 AFTER，新字段默认追加到末尾）
ALTER TABLE com_data_board_view_field ADD COLUMN field_precision integer;

-- 2. 单独添加字段注释
COMMENT ON COLUMN com_data_board_view_field.field_precision IS '字段精度';