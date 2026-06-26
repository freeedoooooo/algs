# LogImport 错误修复 SQL

目标库信息：

- 数据库：`c1`
- Schema：`dib_report_copilot`
- 说明：本文只生成修复 SQL，不执行

## 修复原则

1. 日志中出现 `NOT NULL` 报错的字段，统一去掉非空限制。
2. 日志中出现 `varchar(4)`、`varchar(8)` 长度不足问题的字段，统一改为 `varchar(500)`。
3. 日志中出现 `varchar(50)`、`varchar(255)`、`varchar(500)`、`varchar(900)`、`varchar(1000)`、`varchar(3000)` 长度不足问题的字段，统一改为 `varchar(5000)`。

## 一、去除 NOT NULL 限制

```sql
ALTER TABLE "dib_report_copilot"."com_check_param"
  ALTER COLUMN "table_schema" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_check_param"
  ALTER COLUMN "add_user_id" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_data_board_dir"
  ALTER COLUMN "add_user_id" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_data_board_view"
  ALTER COLUMN "add_user_id" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_data_board_view_field"
  ALTER COLUMN "add_user_id" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_extract_rule"
  ALTER COLUMN "rule_type" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_extract_rule_column"
  ALTER COLUMN "column_comment" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."com_extract_table_column"
  ALTER COLUMN "column_comment" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."p_mdm_project_type_biz"
  ALTER COLUMN "biz_name" DROP NOT NULL;

ALTER TABLE "dib_report_copilot"."p_mdm_project_type_customer"
  ALTER COLUMN "customer_name" DROP NOT NULL;
```

## 二、将 `varchar(4)`、`varchar(8)` 统一扩为 `varchar(500)`

说明：

- 这部分使用动态 SQL。
- 只处理日志中出现过长度报错的表。
- 只修改当前字段类型为 `character varying(4)` 或 `character varying(8)` 的列。

```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT
            table_schema,
            table_name,
            column_name,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'dib_report_copilot'
          AND table_name IN (
              'dib_fin_balance',
              'dib_fin_balance_parent',
              'dib_fin_balance_parent_std',
              'dib_fin_balance_std',
              'dib_fin_cash_flow',
              'dib_fin_cash_flow_parent_std',
              'dib_fin_cash_flow_std',
              'dib_fin_profit_statement_parent_std',
              'dib_fin_profit_statement_std',
              'dib_dwd_poc_bank_account_details_statement'
          )
          AND data_type = 'character varying'
          AND character_maximum_length IN (4, 8)
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE varchar(500);',
            r.table_schema,
            r.table_name,
            r.column_name
        );
    END LOOP;
END $$;
```

## 三、将 `varchar(50)`、`varchar(255)`、`varchar(500)`、`varchar(900)`、`varchar(1000)`、`varchar(3000)` 统一扩为 `varchar(5000)`

说明：

- 这部分同样使用动态 SQL。
- 只处理日志中出现过长度报错的表。
- 只修改当前字段类型为指定长度的 `character varying` 列。

```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT
            table_schema,
            table_name,
            column_name,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'dib_report_copilot'
          AND table_name IN (
              'com_extract_rule',
              'com_extract_rule_column',
              'com_extract_standardization_item',
              'dib_dib_fin_owner_equity_change_item_code_conf_std',
              'dib_dwd_poc_bank_account_details_statement',
              'dib_dwd_poc_bank_monthly_counterparty_summary',
              'dib_fin_balance',
              'dib_fin_balance_item_code_conf_std',
              'dib_fin_balance_parent',
              'dib_fin_balance_parent_std',
              'dib_fin_balance_std',
              'dib_fin_cash_flow',
              'dib_fin_cash_flow_item_code_conf_std',
              'dib_fin_cash_flow_parent',
              'dib_fin_cash_flow_parent_std',
              'dib_fin_cash_flow_std',
              'dib_fin_cash_flow_supplementary_material',
              'dib_fin_cash_flow_supplementary_material_std',
              'dib_fin_profit_statement',
              'dib_fin_profit_statement_parent',
              'dib_poc_bank_account_details_statement',
              'p_mdm_dict_item',
              'p_mdm_sys_param'
          )
          AND data_type = 'character varying'
          AND character_maximum_length IN (50, 255, 500, 900, 1000, 3000)
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE varchar(5000);',
            r.table_schema,
            r.table_name,
            r.column_name
        );
    END LOOP;
END $$;
```

## 三点五、将 `varchar(20)` 统一扩为 `varchar(500)`

说明：

- 这是 `LogImport-2.txt` 新暴露出来的长度问题。
- 当前命中的表为 `dib_fin_cash_flow`、`dib_fin_cash_flow_std`。
- 若你希望更激进，也可以把这里直接改成扩到 `varchar(5000)`。

```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT
            table_schema,
            table_name,
            column_name,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'dib_report_copilot'
          AND table_name IN (
              'dib_fin_cash_flow',
              'dib_fin_cash_flow_std'
          )
          AND data_type = 'character varying'
          AND character_maximum_length = 20
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE varchar(500);',
            r.table_schema,
            r.table_name,
            r.column_name
        );
    END LOOP;
END $$;
```

## 三点六、`varchar(5000)` 仍然不足时的处理建议

说明：

- `LogImport-2.txt` 中 `com_extract_rule` 已出现 `varchar(5000)` 仍超长的情况。
- 对这类“规则文本 / 提示词 / 配置大字段”，建议直接改为 `text`，不要继续机械扩 `varchar(n)`。

```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT
            table_schema,
            table_name,
            column_name
        FROM information_schema.columns
        WHERE table_schema = 'dib_report_copilot'
          AND table_name = 'com_extract_rule'
          AND data_type = 'character varying'
          AND character_maximum_length = 5000
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE text;',
            r.table_schema,
            r.table_name,
            r.column_name
        );
    END LOOP;
END $$;
```

## 三点七、超长表名冲突的排查与处理 SQL

说明：

- `dib_fin_structure_current_assets_of_trading_financial_assets_std` 建表失败，并不是字段问题，而是对象名过长后被数据库截断，和已有对象重名。
- openGauss/PostgreSQL 的对象名存在有效长度限制，过长名称会被截断。
- 下面 SQL 只用于排查和生成处理建议，不会自动删除对象。

### 1. 排查当前 schema 下疑似冲突对象

```sql
SELECT
    n.nspname AS schema_name,
    c.relname AS object_name,
    c.relkind AS object_type
FROM pg_class c
JOIN pg_namespace n
  ON n.oid = c.relnamespace
WHERE n.nspname = 'dib_report_copilot'
  AND c.relname LIKE 'dib_fin_structure_current_assets_of_trading_financial_assets_st%';
```

### 2. 如果确认是旧表占位，可先手工改名

```sql
ALTER TABLE "dib_report_copilot"."dib_fin_structure_current_assets_of_trading_financial_assets_st"
RENAME TO "dib_fin_structure_curr_assets_trading_fin_assets_std_bak";
```

### 3. 推荐直接改用更短的新表名

```sql
-- 推荐短表名示例，请按实际建表语句替换
CREATE TABLE "dib_report_copilot"."dib_fin_struct_curr_trading_fin_assets_std" (
    -- 原建表字段定义放这里
);
```

### 4. 如需删除旧的冲突对象，先确认再执行

```sql
-- 请先确认对象用途后再执行
DROP TABLE "dib_report_copilot"."dib_fin_structure_current_assets_of_trading_financial_assets_st";
```

## 三点八、第三轮日志对应的补充 SQL

说明：

- `LogImport-3.txt` 说明部分修复可能尚未在目标库生效。
- 这一节补充“核查 SQL”和“更短命名方案 SQL”。

### 1. 核查 `com_check_param.add_user_id` 是否仍为 NOT NULL

```sql
SELECT
    table_schema,
    table_name,
    column_name,
    is_nullable,
    data_type,
    character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'dib_report_copilot'
  AND table_name = 'com_check_param'
  AND column_name = 'add_user_id';
```

### 2. 如仍未生效，重新执行去约束

```sql
ALTER TABLE "dib_report_copilot"."com_check_param"
  ALTER COLUMN "add_user_id" DROP NOT NULL;
```

### 3. 单独补强第三轮仍报 `varchar(4)` 的表

```sql
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT
            table_schema,
            table_name,
            column_name
        FROM information_schema.columns
        WHERE table_schema = 'dib_report_copilot'
          AND table_name IN (
              'dib_fin_cash_flow_parent',
              'dib_fin_profit_statement',
              'dib_fin_profit_statement_parent'
          )
          AND data_type = 'character varying'
          AND character_maximum_length = 4
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ALTER COLUMN %I TYPE varchar(500);',
            r.table_schema,
            r.table_name,
            r.column_name
        );
    END LOOP;
END $$;
```

### 4. 排查当前超长表名冲突对象是否仍存在

```sql
SELECT
    n.nspname AS schema_name,
    c.relname AS object_name,
    c.relkind AS object_type
FROM pg_class c
JOIN pg_namespace n
  ON n.oid = c.relnamespace
WHERE n.nspname = 'dib_report_copilot'
  AND c.relname LIKE 'dib_fin_structure_current_assets_of_trading_financial_assets_st%';
```

### 5. 推荐使用“前部即缩短”的新表名，而不是在尾部追加 `_2`

```sql
-- 不推荐：
-- dib_fin_structure_current_assets_of_trading_financial_assets_std_2

-- 推荐示例：
-- dib_fin_struct_curr_trading_fin_assets_std2

CREATE TABLE "dib_report_copilot"."dib_fin_struct_curr_trading_fin_assets_std2" (
    -- 将原 CREATE TABLE 字段定义复制到这里
);
```

### 6. 如需清理旧冲突对象，先确认再删

```sql
-- 高风险操作，执行前请先确认该表是否已无业务用途
DROP TABLE IF EXISTS "dib_report_copilot"."dib_fin_structure_current_assets_of_trading_financial_assets_st";
```

## 三点九、第四轮日志的字段级精确修复 SQL

说明：

- `LogImport-4.txt` 已明确指出 `com_data_board_view` 的超长字段是 `view_name`。
- 这类情况建议直接下字段级 DDL，而不是仅依赖动态 SQL 扫描。

### 1. 先检查当前字段定义

```sql
SELECT
    table_schema,
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'dib_report_copilot'
  AND table_name = 'com_data_board_view'
  AND column_name = 'view_name';
```

### 2. 直接扩容 `view_name`

```sql
ALTER TABLE "dib_report_copilot"."com_data_board_view"
  ALTER COLUMN "view_name" TYPE varchar(500);
```

### 3. 如果希望与前面长文本策略保持一致，也可以直接扩到 `varchar(5000)`

```sql
ALTER TABLE "dib_report_copilot"."com_data_board_view"
  ALTER COLUMN "view_name" TYPE varchar(5000);
```

### 4. 顺手检查同表中其他可能仍为 `varchar(50)` 的文本列

```sql
SELECT
    table_schema,
    table_name,
    column_name,
    character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'dib_report_copilot'
  AND table_name = 'com_data_board_view'
  AND data_type = 'character varying'
  AND character_maximum_length = 50
ORDER BY column_name;
```

## 四、执行前建议先预览影响范围

```sql
SELECT
    table_schema,
    table_name,
    column_name,
    data_type,
    character_maximum_length,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'dib_report_copilot'
  AND (
        (table_name IN (
            'dib_fin_balance',
            'dib_fin_balance_parent',
            'dib_fin_balance_parent_std',
            'dib_fin_balance_std',
            'dib_fin_cash_flow',
            'dib_fin_cash_flow_parent_std',
            'dib_fin_cash_flow_std',
            'dib_fin_profit_statement_parent_std',
            'dib_fin_profit_statement_std',
            'dib_dwd_poc_bank_account_details_statement'
        ) AND character_maximum_length IN (4, 8))
     OR (table_name IN (
            'dib_fin_cash_flow',
            'dib_fin_cash_flow_std'
        ) AND character_maximum_length IN (20))
     OR (table_name IN (
            'com_extract_rule',
            'com_extract_rule_column',
            'com_extract_standardization_item',
            'dib_dib_fin_owner_equity_change_item_code_conf_std',
            'dib_dwd_poc_bank_account_details_statement',
            'dib_dwd_poc_bank_monthly_counterparty_summary',
            'dib_fin_balance',
            'dib_fin_balance_item_code_conf_std',
            'dib_fin_balance_parent',
            'dib_fin_balance_parent_std',
            'dib_fin_balance_std',
            'dib_fin_cash_flow',
            'dib_fin_cash_flow_item_code_conf_std',
            'dib_fin_cash_flow_parent',
            'dib_fin_cash_flow_parent_std',
            'dib_fin_cash_flow_std',
            'dib_fin_cash_flow_supplementary_material',
            'dib_fin_cash_flow_supplementary_material_std',
            'dib_fin_profit_statement',
            'dib_fin_profit_statement_parent',
            'dib_poc_bank_account_details_statement',
            'p_mdm_dict_item',
            'p_mdm_sys_param'
        ) AND character_maximum_length IN (50, 255, 500, 900, 1000, 3000))
     OR (table_name, column_name) IN (
            ('com_check_param', 'table_schema'),
            ('com_check_param', 'add_user_id'),
            ('com_data_board_dir', 'add_user_id'),
            ('com_data_board_view', 'add_user_id'),
            ('com_data_board_view_field', 'add_user_id'),
            ('com_extract_rule', 'rule_type'),
            ('com_extract_rule_column', 'column_comment'),
            ('com_extract_table_column', 'column_comment'),
            ('p_mdm_project_type_biz', 'biz_name'),
            ('p_mdm_project_type_customer', 'customer_name')
        )
      )
ORDER BY table_name, column_name;
```

## 五、建议执行顺序

```sql
BEGIN;

-- 1. 去掉 NOT NULL
-- 执行“第一部分 SQL”

-- 2. 扩容 4/8 到 500
-- 执行“第二部分 SQL”

-- 3. 扩容 20 到 500
-- 执行“第三点五部分 SQL”

-- 4. 扩容 50/255/500/900/1000/3000 到 5000
-- 执行“第三部分 SQL”

-- 5. 对 com_extract_rule 中仍超长的大字段改成 text
-- 执行“第三点六部分 SQL”

-- 6. 如存在超长表名冲突，先执行“第三点七部分 SQL”排查后处理

COMMIT;
```

## 六、补充说明

- 这里采用“按日志命中的表 + 按当前字段长度筛选”的方式生成 SQL，能尽量避免误改整个 schema 中所有 varchar 字段。
- 如果你想更稳一点，下一步我可以继续帮你把这份 SQL 再细化成“每张表每个字段的最终 ALTER 语句明细版”，这样 DBA 审核会更直观。
