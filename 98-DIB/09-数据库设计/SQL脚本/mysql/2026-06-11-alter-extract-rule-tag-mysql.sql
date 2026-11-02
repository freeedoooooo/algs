-- 为com_extract_rule表添加规则标签字段
ALTER TABLE com_extract_rule
ADD COLUMN `rule_tag` VARCHAR(500) NULL COMMENT '规则标签' AFTER `rule_name`;

-- 为com_extract_rule表添加文档类型编码字段
ALTER TABLE com_extract_rule
ADD COLUMN `doc_type_code` VARCHAR(255) NULL COMMENT '文档类型编码' AFTER `rule_tag`;

-- 为com_extract_rule_column表添加规则标签字段
ALTER TABLE com_extract_rule_column
ADD COLUMN `rule_tag` VARCHAR(500) NULL COMMENT '规则标签' AFTER `rule_id`;

-- 为com_extract_doc_type表添加文档类型编码字段
ALTER TABLE com_extract_doc_type
ADD COLUMN `doc_type_code` VARCHAR(255) NULL COMMENT '文档类型编码' AFTER `type_name`;
