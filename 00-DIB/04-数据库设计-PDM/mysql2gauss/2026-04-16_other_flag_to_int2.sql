-- Source openGauss: 192.168.10.141:5432 / c1 / dib_report_copilot
-- Generated from live metadata on 2026-04-16
-- Scope: *_flag columns that are NOT int2, excluding del_flag and enable_flag
-- Goal: normalize them to int2
--
-- Grouped by corresponding Java-side field type to support phased execution.
--
-- Conversion rule for varchar/char:
--   NULL stays NULL
--   blank string becomes 0
--   other values are trimmed and cast to int2

BEGIN;

-- =========================================================
-- Group A: Java entity field type = Boolean / boolean
-- Risk:
--   DB conversion may succeed, but Java write-paths can still be risky
--   if ORM or JDBC binds these values as Boolean instead of numeric.
-- =========================================================

ALTER TABLE dib_report_copilot.com_check_param
  ALTER COLUMN source_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_check_param
  ALTER COLUMN source_flag TYPE int2
  USING CASE
    WHEN source_flag IS NULL THEN NULL
    WHEN BTRIM(source_flag) = '' THEN 0
    ELSE BTRIM(source_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_check_param
  ALTER COLUMN source_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_check_rule
  ALTER COLUMN must_pass_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_check_rule
  ALTER COLUMN must_pass_flag TYPE int2
  USING CASE
    WHEN must_pass_flag IS NULL THEN NULL
    WHEN BTRIM(must_pass_flag) = '' THEN 0
    ELSE BTRIM(must_pass_flag)::int2
  END;

ALTER TABLE dib_report_copilot.com_check_rule_result
  ALTER COLUMN must_pass_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_check_rule_result
  ALTER COLUMN must_pass_flag TYPE int2
  USING must_pass_flag::int2;

ALTER TABLE dib_report_copilot.com_check_rule_result
  ALTER COLUMN pass_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_check_rule_result
  ALTER COLUMN pass_flag TYPE int2
  USING CASE
    WHEN pass_flag IS NULL THEN NULL
    WHEN BTRIM(pass_flag) = '' THEN 0
    ELSE BTRIM(pass_flag)::int2
  END;

ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN key_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN key_flag TYPE int2
  USING CASE
    WHEN key_flag IS NULL THEN NULL
    WHEN BTRIM(key_flag) = '' THEN 0
    ELSE BTRIM(key_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN key_flag SET DEFAULT 0;

ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN nullable_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN nullable_flag TYPE int2
  USING CASE
    WHEN nullable_flag IS NULL THEN NULL
    WHEN BTRIM(nullable_flag) = '' THEN 0
    ELSE BTRIM(nullable_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN nullable_flag SET DEFAULT 0;

ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN search_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN search_flag TYPE int2
  USING CASE
    WHEN search_flag IS NULL THEN NULL
    WHEN BTRIM(search_flag) = '' THEN 0
    ELSE BTRIM(search_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN search_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN show_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN show_flag TYPE int2
  USING CASE
    WHEN show_flag IS NULL THEN NULL
    WHEN BTRIM(show_flag) = '' THEN 0
    ELSE BTRIM(show_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_di_table_field
  ALTER COLUMN show_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_task_monitor
  ALTER COLUMN ready_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_task_monitor
  ALTER COLUMN ready_flag TYPE int2
  USING CASE
    WHEN ready_flag IS NULL THEN NULL
    WHEN BTRIM(ready_flag) = '' THEN 0
    ELSE BTRIM(ready_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_task_monitor
  ALTER COLUMN ready_flag SET DEFAULT 0;

ALTER TABLE dib_report_copilot.p_auth_user
  ALTER COLUMN lock_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.p_auth_user
  ALTER COLUMN lock_flag TYPE int2
  USING CASE
    WHEN lock_flag IS NULL THEN NULL
    WHEN BTRIM(lock_flag) = '' THEN 0
    ELSE BTRIM(lock_flag)::int2
  END;
ALTER TABLE dib_report_copilot.p_auth_user
  ALTER COLUMN lock_flag SET DEFAULT 0;

-- =========================================================
-- Group B: Java entity field type = Integer
-- Risk:
--   Usually the safest group because Java numeric type is already aligned.
-- =========================================================

ALTER TABLE dib_report_copilot.com_extract_table_column
  ALTER COLUMN nullable_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_table_column
  ALTER COLUMN nullable_flag TYPE int2
  USING CASE
    WHEN nullable_flag IS NULL THEN NULL
    WHEN BTRIM(nullable_flag) = '' THEN 0
    ELSE BTRIM(nullable_flag)::int2
  END;
ALTER TABLE dib_report_copilot.com_extract_table_column
  ALTER COLUMN nullable_flag SET DEFAULT 1;
