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
-- Group C: Java entity field type = String
-- Risk:
--   Database conversion is likely safe for current data values,
--   but Java entity / DTO / request / response classes should also be changed.
-- =========================================================

ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN doc_unique_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN doc_unique_flag TYPE int2
    USING CASE
    WHEN doc_unique_flag IS NULL THEN NULL
    WHEN BTRIM(doc_unique_flag) = '' THEN 0
    ELSE BTRIM(doc_unique_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN doc_unique_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN extract_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN extract_flag TYPE int2
    USING CASE
    WHEN extract_flag IS NULL THEN NULL
    WHEN BTRIM(extract_flag) = '' THEN 0
    ELSE BTRIM(extract_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN extract_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN need_authorize_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN need_authorize_flag TYPE int2
    USING CASE
    WHEN need_authorize_flag IS NULL THEN NULL
    WHEN BTRIM(need_authorize_flag) = '' THEN 0
    ELSE BTRIM(need_authorize_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN need_authorize_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN report_date_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN report_date_flag TYPE int2
    USING CASE
    WHEN report_date_flag IS NULL THEN NULL
    WHEN BTRIM(report_date_flag) = '' THEN 0
    ELSE BTRIM(report_date_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN report_date_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN show_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN show_flag TYPE int2
    USING CASE
    WHEN show_flag IS NULL THEN NULL
    WHEN BTRIM(show_flag) = '' THEN 0
    ELSE BTRIM(show_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN show_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN upload_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN upload_flag TYPE int2
    USING CASE
    WHEN upload_flag IS NULL THEN NULL
    WHEN BTRIM(upload_flag) = '' THEN 0
    ELSE BTRIM(upload_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_doc_type
    ALTER COLUMN upload_flag SET DEFAULT 1;

ALTER TABLE dib_report_copilot.com_extract_rule_column
    ALTER COLUMN necessary_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_rule_column
    ALTER COLUMN necessary_flag TYPE int2
    USING CASE
    WHEN necessary_flag IS NULL THEN NULL
    WHEN BTRIM(necessary_flag) = '' THEN 0
    ELSE BTRIM(necessary_flag)::int2
    END;
ALTER TABLE dib_report_copilot.com_extract_rule_column
    ALTER COLUMN necessary_flag SET DEFAULT 1;

-- =========================================================
-- Group D: No matching Java entity field found in the current repo
-- Risk:
--   These columns may still be used by XML mapping, map-based queries,
--   generated code, or services outside the current workspace.
-- =========================================================


ALTER TABLE dib_report_copilot.com_extract_rule_column
    ALTER COLUMN dict_flag DROP DEFAULT;
ALTER TABLE dib_report_copilot.com_extract_rule_column
    ALTER COLUMN dict_flag TYPE int2
    USING CASE
    WHEN dict_flag IS NULL THEN NULL
    WHEN BTRIM(dict_flag) = '' THEN 0
    ELSE BTRIM(dict_flag)::int2
    END;

COMMIT;

