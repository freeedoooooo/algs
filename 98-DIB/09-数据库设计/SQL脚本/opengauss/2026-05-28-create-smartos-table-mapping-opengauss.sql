-- SmartOS 表映射表
-- 创建时间: 2026-05-28

CREATE TABLE IF NOT EXISTS com_extract_table_smartos_mapping (
    id BIGINT NOT NULL,
    table_name VARCHAR(255) DEFAULT NULL,
    smartos_table_code VARCHAR(255) DEFAULT NULL,
    del_flag SMALLINT DEFAULT 0,
    add_user_id VARCHAR(64) DEFAULT NULL,
    add_user_name VARCHAR(128) DEFAULT NULL,
    add_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_user_id VARCHAR(64) DEFAULT NULL,
    update_user_name VARCHAR(128) DEFAULT NULL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

-- 创建索引
CREATE INDEX idx_table_name ON com_extract_table_smartos_mapping(table_name);
CREATE INDEX idx_smartos_table_code ON com_extract_table_smartos_mapping(smartos_table_code);

-- 添加注释
COMMENT ON TABLE com_extract_table_smartos_mapping IS 'SmartOS表映射表';
COMMENT ON COLUMN com_extract_table_smartos_mapping.id IS '主键';
COMMENT ON COLUMN com_extract_table_smartos_mapping.table_name IS '表名';
COMMENT ON COLUMN com_extract_table_smartos_mapping.smartos_table_code IS 'SmartOS表编码';
COMMENT ON COLUMN com_extract_table_smartos_mapping.del_flag IS '删除标识(0:未删除,1:已删除)';
COMMENT ON COLUMN com_extract_table_smartos_mapping.add_user_id IS '创建人账号';
COMMENT ON COLUMN com_extract_table_smartos_mapping.add_user_name IS '创建人姓名';
COMMENT ON COLUMN com_extract_table_smartos_mapping.add_time IS '创建时间';
COMMENT ON COLUMN com_extract_table_smartos_mapping.update_user_id IS '更新人账号';
COMMENT ON COLUMN com_extract_table_smartos_mapping.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_extract_table_smartos_mapping.update_time IS '更新时间';

-- 创建序列（用于主键自增）
CREATE SEQUENCE IF NOT EXISTS seq_smartos_table_mapping_id
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- 设置默认值使用序列
ALTER TABLE com_extract_table_smartos_mapping ALTER COLUMN id SET DEFAULT nextval('seq_smartos_table_mapping_id');

-- 插入初始数据
INSERT INTO com_extract_table_smartos_mapping (id, table_name, smartos_table_code, del_flag, add_time, update_time) VALUES
(1, 'dib_fin_owner_equity_change_parent', 'parentEquityChangeStatementLast', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(2, 'dib_fin_profit_statement', 'consolidatedIncomeStatement', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(3, 'dib_fin_cash_flow', 'consolidatedCashFlowStatement', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(4, 'dib_fin_owner_equity_change', 'consolidatedEquityChangeStatement', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(5, 'dib_fin_account_receivable_by_aging', 'accountsReceivableAgingDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(6, 'dib_fin_capital_reserve', 'capitalReserve', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(7, 'dib_fin_balance', 'consolidatedBalanceSheet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(8, 'dib_fin_cash_flow_parent', 'parentCashFlowStatement', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(9, 'dib_fin_revenue_expenditure', 'operatingRevenueDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(10, 'dib_intervening_y_auditreport_jh', 'financialStatements', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(11, 'dib_fin_other_account_receivable_by_aging', 'otherReceivablesAgingDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(12, 'dib_fin_trading_financial_assets', 'tradingFinancialAssetsDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(13, 'dib_fin_owner_equity_change_last', 'consolidatedEquityChangeStatementLast', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(14, 'dib_fin_assets_impairment_loss', 'assetImpairmentLossDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(15, 'dib_fin_cash_equivalent', 'cashAndCashEquivalentsDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(16, 'dib_fin_available_sale_financial_assets', 'availableForSaleFinancialAssetsDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(17, 'dib_fin_other_current_asset', 'otherCurrentAssets', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(18, 'dib_fin_balance_parent', 'parentBalanceSheet', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(19, 'dib_fin_profit_statement_parent', 'parentIncomeStatement', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(20, 'dib_fin_stock', 'inventoryDisclosure', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(21, 'dib_fin_cash_flow_supplementary_material', 'cashFlowSupplementaryInfo', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(22, 'dib_fin_owner_equity_change_parent', 'parentEquityChangeStatement', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);

-- 插入示例数据
INSERT INTO com_extract_table_smartos_mapping (id, table_name, smartos_table_code, del_flag, add_time, update_time) VALUES
(1, 'example_table_1', 'SMARTOS_CODE_001', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
(2, 'example_table_2', 'SMARTOS_CODE_002', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
