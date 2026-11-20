-- 001_init.sql — 平台目录库初始 schema（设计稿 §5.3，10 表）
-- MySQL 8.x / InnoDB / utf8mb4；JSON 原生类型；时间 DATETIME（应用层 UTC）。
-- DB 只管目录元数据：记录内容在 output/<批次>/records.json（事实源），
-- quarantine / load_log 用 (run_file_id, record_index) 引用。

CREATE TABLE source_file (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  sha256      CHAR(64)     NOT NULL,
  kind        VARCHAR(16)  NOT NULL,
  size_bytes  BIGINT       NOT NULL,
  rel_path    VARCHAR(512) NOT NULL,
  tags        VARCHAR(512),
  note        TEXT,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_source_sha (sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE template (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  name            VARCHAR(128) NOT NULL,
  description     VARCHAR(512),
  current_version INT NOT NULL DEFAULT 1,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_template_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE template_version (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  template_id    BIGINT NOT NULL,
  version        INT NOT NULL,
  schema_json    JSON,
  mapping_json   JSON,
  transform_json JSON,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tpl_ver (template_id, version),
  CONSTRAINT fk_tv_template FOREIGN KEY (template_id) REFERENCES template(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE destination (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  name       VARCHAR(128) NOT NULL,
  db_type    VARCHAR(32)  NOT NULL,
  conn_ref   VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_dest_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE load_mapping (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  destination_id    BIGINT NOT NULL,
  template_id       BIGINT NOT NULL,
  target_table      VARCHAR(128) NOT NULL,
  column_map_json   JSON NOT NULL,
  write_mode        VARCHAR(16) NOT NULL DEFAULT 'upsert',
  business_key_json JSON,
  UNIQUE KEY uk_dest_tpl_table (destination_id, template_id, target_table),
  CONSTRAINT fk_lm_dest FOREIGN KEY (destination_id) REFERENCES destination(id),
  CONSTRAINT fk_lm_tpl  FOREIGN KEY (template_id) REFERENCES template(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE run (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  batch_tag           VARCHAR(32) NOT NULL,
  mode                VARCHAR(16) NOT NULL,
  template_version_id BIGINT NOT NULL,
  destination_id      BIGINT,
  load_mapping_id     BIGINT,
  params_json         JSON,
  state               VARCHAR(24) NOT NULL DEFAULT 'pending',
  error               TEXT,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_run_state (state),
  CONSTRAINT fk_run_tv   FOREIGN KEY (template_version_id) REFERENCES template_version(id),
  CONSTRAINT fk_run_dest FOREIGN KEY (destination_id) REFERENCES destination(id),
  CONSTRAINT fk_run_lm   FOREIGN KEY (load_mapping_id) REFERENCES load_mapping(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE run_file (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id         BIGINT NOT NULL,
  source_file_id BIGINT NOT NULL,
  state          VARCHAR(24) NOT NULL DEFAULT 'pending',
  output_rel_dir VARCHAR(512) NOT NULL,
  UNIQUE KEY uk_run_file (run_id, source_file_id),
  CONSTRAINT fk_rf_run  FOREIGN KEY (run_id) REFERENCES run(id),
  CONSTRAINT fk_rf_file FOREIGN KEY (source_file_id) REFERENCES source_file(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE quarantine (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id       BIGINT NOT NULL,
  run_file_id  BIGINT,
  record_index INT,
  stage        VARCHAR(16) NOT NULL,
  reason       TEXT NOT NULL,
  payload_json JSON NOT NULL,
  state        VARCHAR(16) NOT NULL DEFAULT 'open',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at  DATETIME,
  KEY idx_q_run (run_id, state),
  CONSTRAINT fk_q_run FOREIGN KEY (run_id) REFERENCES run(id),
  CONSTRAINT fk_q_rf  FOREIGN KEY (run_file_id) REFERENCES run_file(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE load_log (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id         BIGINT NOT NULL,
  run_file_id    BIGINT NOT NULL,
  record_index   INT NOT NULL,
  destination_id BIGINT NOT NULL,
  target_table   VARCHAR(128) NOT NULL,
  target_pk      VARCHAR(255) NOT NULL,
  action         VARCHAR(16) NOT NULL,
  loaded_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_load_receipt (run_file_id, record_index, destination_id, target_table),
  CONSTRAINT fk_ll_run  FOREIGN KEY (run_id) REFERENCES run(id),
  CONSTRAINT fk_ll_rf   FOREIGN KEY (run_file_id) REFERENCES run_file(id),
  CONSTRAINT fk_ll_dest FOREIGN KEY (destination_id) REFERENCES destination(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS schema_version (
  version    INT PRIMARY KEY,
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 种子：内置模板「原始透传」（三个 JSON 空 = passthrough，不可删）
INSERT INTO template (name, description, current_version)
VALUES ('原始透传', '无字段定义 / 无映射 / 无转换：每表每行原样成为记录', 1);

INSERT INTO template_version (template_id, version, schema_json, mapping_json, transform_json)
SELECT id, 1, JSON_ARRAY(), JSON_OBJECT(), JSON_ARRAY()
FROM template WHERE name = '原始透传';