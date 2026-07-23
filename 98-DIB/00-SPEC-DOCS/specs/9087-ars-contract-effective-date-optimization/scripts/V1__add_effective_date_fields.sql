-- ============================================================
-- 需求编号: 9087
-- 需求名称: 合同生效时间优化
-- 描述: 在合同备案表中新增生效时间字段
-- 数据库: PostgreSQL
-- 模式: contract
-- ============================================================

ALTER TABLE contract.t_contract_record
ADD COLUMN IF NOT EXISTS dt_effective_date timestamp(6);

-- 新增计划结束日期字段
ALTER TABLE contract.t_contract_record
ADD COLUMN IF NOT EXISTS dt_plan_end_date timestamp(6);

-- 添加字段注释
COMMENT ON COLUMN contract.t_contract_record.dt_effective_date IS '生效日期';
COMMENT ON COLUMN contract.t_contract_record.dt_plan_end_date IS '计划结束日期';
