-- SmartOS 表映射表
-- 创建时间: 2026-05-28

CREATE TABLE IF NOT EXISTS `com_extract_table_smartos_mapping` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `table_name` VARCHAR(255) DEFAULT NULL COMMENT '表名',
    `smartos_table_code` VARCHAR(255) DEFAULT NULL COMMENT 'SmartOS表编码',
    `del_flag` TINYINT(1) DEFAULT 0 COMMENT '删除标识(0:未删除,1:已删除)',
    `add_user_id` VARCHAR(64) DEFAULT NULL COMMENT '创建人账号',
    `add_user_name` VARCHAR(128) DEFAULT NULL COMMENT '创建人姓名',
    `add_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_user_id` VARCHAR(64) DEFAULT NULL COMMENT '更新人账号',
    `update_user_name` VARCHAR(128) DEFAULT NULL COMMENT '更新人姓名',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_table_name` (`table_name`),
    KEY `idx_smartos_table_code` (`smartos_table_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SmartOS表映射表';

-- 插入初始数据
INSERT INTO `com_extract_table_smartos_mapping` (`id`, `table_name`, `smartos_table_code`, `del_flag`, `add_time`, `update_time`) VALUES
(1, 'dib_fin_owner_equity_change_parent', 'parentEquityChangeStatementLast', 0, NOW(), NOW()),
(2, 'dib_fin_profit_statement', 'consolidatedIncomeStatement', 0, NOW(), NOW()),
(3, 'dib_fin_cash_flow', 'consolidatedCashFlowStatement', 0, NOW(), NOW()),
(4, 'dib_fin_owner_equity_change', 'consolidatedEquityChangeStatement', 0, NOW(), NOW()),
(5, 'dib_fin_account_receivable_by_aging', 'accountsReceivableAgingDisclosure', 0, NOW(), NOW()),
(6, 'dib_fin_capital_reserve', 'capitalReserve', 0, NOW(), NOW()),
(7, 'dib_fin_balance', 'consolidatedBalanceSheet', 0, NOW(), NOW()),
(8, 'dib_fin_cash_flow_parent', 'parentCashFlowStatement', 0, NOW(), NOW()),
(9, 'dib_fin_revenue_expenditure', 'operatingRevenueDisclosure', 0, NOW(), NOW()),
(10, 'dib_intervening_y_auditreport_jh', 'financialStatements', 0, NOW(), NOW()),
(11, 'dib_fin_other_account_receivable_by_aging', 'otherReceivablesAgingDisclosure', 0, NOW(), NOW()),
(12, 'dib_fin_trading_financial_assets', 'tradingFinancialAssetsDisclosure', 0, NOW(), NOW()),
(13, 'dib_fin_owner_equity_change_last', 'consolidatedEquityChangeStatementLast', 0, NOW(), NOW()),
(14, 'dib_fin_assets_impairment_loss', 'assetImpairmentLossDisclosure', 0, NOW(), NOW()),
(15, 'dib_fin_cash_equivalent', 'cashAndCashEquivalentsDisclosure', 0, NOW(), NOW()),
(16, 'dib_fin_available_sale_financial_assets', 'availableForSaleFinancialAssetsDisclosure', 0, NOW(), NOW()),
(17, 'dib_fin_other_current_asset', 'otherCurrentAssets', 0, NOW(), NOW()),
(18, 'dib_fin_balance_parent', 'parentBalanceSheet', 0, NOW(), NOW()),
(19, 'dib_fin_profit_statement_parent', 'parentIncomeStatement', 0, NOW(), NOW()),
(20, 'dib_fin_stock', 'inventoryDisclosure', 0, NOW(), NOW()),
(21, 'dib_fin_cash_flow_supplementary_material', 'cashFlowSupplementaryInfo', 0, NOW(), NOW()),
(22, 'dib_fin_owner_equity_change_parent', 'parentEquityChangeStatement', 0, NOW(), NOW());
