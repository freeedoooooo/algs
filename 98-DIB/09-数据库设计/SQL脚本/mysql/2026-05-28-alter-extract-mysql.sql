-- 融合C1和OS的提取能力
ALTER TABLE com_extract_doc
ADD COLUMN os_txt_att_id BIGINT COMMENT 'OS转换文件',
ADD COLUMN os_convert_state VARCHAR(10) DEFAULT 'U' COMMENT 'OS转换状态',
ADD COLUMN os_convert_duration INT DEFAULT 0 COMMENT 'OS转换耗时(秒)';

ALTER TABLE com_extract_result
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'C1' COMMENT '提取来源:OS|C1';

ALTER TABLE com_extract_result_bak
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'C1' COMMENT '提取来源:OS|C1';