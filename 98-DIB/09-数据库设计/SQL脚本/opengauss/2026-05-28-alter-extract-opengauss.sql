-- 融合C1和OS的提取能力 - OpenGauss适配脚本
-- 为com_extract_doc表添加OS相关字段
ALTER TABLE com_extract_doc
ADD COLUMN os_txt_att_id BIGINT,
ADD COLUMN os_convert_state VARCHAR(10) DEFAULT 'U',
ADD COLUMN os_convert_duration INT DEFAULT 0;

-- 添加字段注释
COMMENT ON COLUMN com_extract_doc.os_txt_att_id IS 'OS转换文件';
COMMENT ON COLUMN com_extract_doc.os_convert_state IS 'OS转换状态';
COMMENT ON COLUMN com_extract_doc.os_convert_duration IS 'OS转换耗时(秒)';

-- 为com_extract_result表添加提取来源字段
ALTER TABLE com_extract_result
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'C1';

-- 添加字段注释
COMMENT ON COLUMN com_extract_result.extract_source IS '提取来源:OS|C1';

-- 为com_extract_result_bak表添加提取来源字段
ALTER TABLE com_extract_result_bak
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'C1';

-- 添加字段注释
COMMENT ON COLUMN com_extract_result_bak.extract_source IS '提取来源:OS|C1';