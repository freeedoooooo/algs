-- com_rule_ref_data 冗余存储所依赖对象名称
-- 创建时间: 2026-10-15
-- 说明:
--   让 rule 域自包含所依赖指标的 indexCode 与名称，供任务依赖图 RULE→INDEX 边直接读取，
--   避免 rule 服务跨域解析 index id→code（不再依赖 data 域 com_data_index_info）。
--   refType=INDEX 时 ref_code=指标编码 indexCode、ref_name=指标名称；其它类型可留空。
--   历史数据 ref_code 为空时，任务依赖图 RULE→INDEX 边会跳过，需回填后生效。

ALTER TABLE com_rule_ref_data
    ADD COLUMN ref_name VARCHAR(100) DEFAULT NULL COMMENT '依赖数据名称;refType=INDEX时为指标名称';
