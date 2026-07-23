-- Source MySQL: 10.0.6.161:3306 / dib_report_copilot.com_check_rule
-- Target openGauss: 192.168.10.141:5432 / c1 / dib_report_copilot.com_check_rule
-- Generated from live metadata on 2026-04-16
--
-- Main differences found:
--   1. openGauss is missing column auto_check_flag
--   2. openGauss.must_pass_flag is varchar, while MySQL uses bit(1)
--   3. Defaults should be explicitly aligned for the columns that require them
--
-- Existing openGauss data check:
--   must_pass_flag currently contains only '0' and '1'

BEGIN;

ALTER TABLE dib_report_copilot.com_check_rule
    ALTER COLUMN must_pass_flag TYPE int2
    USING CASE
    WHEN must_pass_flag IS NULL THEN NULL
    WHEN BTRIM(must_pass_flag) = '' THEN NULL
    ELSE BTRIM(must_pass_flag)::int2
    END;

COMMENT ON COLUMN dib_report_copilot.com_check_rule.must_pass_flag IS 'Must pass validation flag';

-- ALTER TABLE dib_report_copilot.com_check_rule ADD COLUMN auto_check_flag int2 NOT NULL DEFAULT 1;

COMMENT ON COLUMN dib_report_copilot.com_check_rule.auto_check_flag IS 'Auto check flag';

ALTER TABLE dib_report_copilot.com_check_rule
    ALTER COLUMN enable_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_check_rule
    ALTER COLUMN del_flag SET DEFAULT 0;

COMMIT;
