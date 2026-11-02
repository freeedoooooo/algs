-- 为 com_extract_rule 表添加 ai_prompt 字段
-- 执行时间：2026-08-20
-- 说明：新增 AI 提示词字段，用于存储 AI 提取规则的提示词配置

-- Add the column
ALTER TABLE com_extract_rule
ADD COLUMN ai_prompt VARCHAR(12000);

-- Add comment to the column
COMMENT ON COLUMN com_extract_rule.ai_prompt IS 'AI 提示词';

UPDATE com_extract_rule set ai_prompt = key_word_in WHERE  doc_reader in ('aiReaderFacade','vlReaderFacade') AND ai_prompt = null;
UPDATE com_extract_rule set key_word_in = null WHERE doc_reader in ('aiReaderFacade','vlReaderFacade') and ai_prompt is not null ;
