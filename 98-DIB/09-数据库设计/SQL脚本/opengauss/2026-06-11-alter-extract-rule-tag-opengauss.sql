
-- 为com_extract_rule表添加规则标签字段
ALTER TABLE com_extract_rule ADD COLUMN rule_tag VARCHAR(500);
COMMENT ON COLUMN com_extract_rule.rule_tag IS '规则标签';

-- 为com_extract_rule表添加文档类型编码字段
ALTER TABLE com_extract_rule ADD COLUMN doc_type_code VARCHAR(255);
COMMENT ON COLUMN com_extract_rule.doc_type_code IS '文档类型编码';

-- 为com_extract_rule_column表添加规则标签字段
ALTER TABLE com_extract_rule_column ADD COLUMN rule_tag VARCHAR(500);
COMMENT ON COLUMN com_extract_rule_column.rule_tag IS '规则标签';

-- 为com_extract_doc_type表添加文档类型编码字段
ALTER TABLE com_extract_doc_type ADD COLUMN doc_type_code VARCHAR(255);
COMMENT ON COLUMN com_extract_doc_type.doc_type_code IS '文档类型编码';
