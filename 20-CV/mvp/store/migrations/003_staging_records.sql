-- 003_staging_records.sql — records 事实源迁库（选项 B，design-records-db.md §1）
-- 三表：record 行（全保真 JSON + review）/ field 行（可查询投影）/ lineage 行（逐格血缘）。
-- (run_file_id, record_index) 唯一键 = quarantine / load_log / review 的既有引用键。
-- field / lineage 是 values 的同事务查询投影（可全量重建），非独立事实源。

CREATE TABLE extract_staging_record (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_file_id   BIGINT NOT NULL COMMENT '引用 extract_run_file.id',
  record_index  INT    NOT NULL COMMENT '记录在文件内下标（引用键的一半）',
  review_state  VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/edited/confirmed',
  review_at     DATETIME NULL COMMENT '校验时间（UTC）',
  values_json   MEDIUMTEXT NOT NULL COMMENT '当前值全保真 body（API 重建用）',
  original_json MEDIUMTEXT NOT NULL COMMENT '提取原值，永不覆盖',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_rf_idx (run_file_id, record_index),
  KEY idx_review (review_state),
  CONSTRAINT fk_sr_rf FOREIGN KEY (run_file_id) REFERENCES extract_run_file (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE extract_staging_field (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  record_id     BIGINT NOT NULL,
  field_name    VARCHAR(128) NOT NULL COMMENT '模板字段名（动态）',
  value_text    TEXT NOT NULL COMMENT '当前值（含 edited）',
  original_text TEXT NOT NULL COMMENT '提取原值',
  KEY idx_field_value (field_name, value_text(191)),
  KEY idx_record (record_id),
  CONSTRAINT fk_sf_rec FOREIGN KEY (record_id)
    REFERENCES extract_staging_record (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE extract_staging_lineage (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  record_id   BIGINT NOT NULL,
  field_name  VARCHAR(128) NOT NULL,
  region_seq  INT NOT NULL COMMENT '区域保序（同 cv_lineage 约定）',
  page        INT NOT NULL,
  table_index INT NULL,
  table_scope VARCHAR(16) NULL,
  space       VARCHAR(16) NOT NULL COMMENT 'source/rectified',
  cell_bbox   VARCHAR(128) NULL COMMENT '[x0,y0,x1,y1] json 字符串',
  raw_text    TEXT NULL,
  UNIQUE KEY uk_rec_field_seq (record_id, field_name, region_seq),
  CONSTRAINT fk_sl_rec FOREIGN KEY (record_id)
    REFERENCES extract_staging_record (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;