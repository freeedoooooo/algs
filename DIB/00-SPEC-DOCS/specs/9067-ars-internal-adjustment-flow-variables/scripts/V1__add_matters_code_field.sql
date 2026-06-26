-- 9067 指标内部调整单审批流程网关变量
-- 在调整明细表新增支出预算事项编码字段

-- 新增字段
ALTER TABLE budget.t_budget_indicator_adjustment_detail 
ADD COLUMN c_matters_code VARCHAR(100);

-- 添加字段注释
COMMENT ON COLUMN budget.t_budget_indicator_adjustment_detail.c_matters_code IS '支出预算事项编码';
