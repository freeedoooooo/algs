-- 001_baseline.sql — 平台库最终态基线（design-task-schema.md，2026-11-21 批准）
-- 由 001–006 历史迁移压缩而成：任务化命名（task/task_file/file/load_dest）、
-- 无外键约束（引用完整性与级联删除归应用层，见设计稿 §2）、表/列注释齐全。
-- MySQL 8.x / InnoDB / utf8mb4，JSON 原生类型，时间 DATETIME（应用层 UTC）。
-- 注意：执行器按半角分号朴素切分，注释与 COMMENT 字符串内不得出现半角分号。

CREATE TABLE IF NOT EXISTS extract_file (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '文件 ID',
  name       VARCHAR(255) NOT NULL COMMENT '原始文件名',
  sha256     CHAR(64)     NOT NULL COMMENT '内容 SHA-256（去重键）',
  kind       VARCHAR(16)  NOT NULL COMMENT '载体类型：image/pdf/csv/text',
  size_bytes BIGINT       NOT NULL COMMENT '文件字节数',
  content    LONGBLOB     NOT NULL COMMENT '原件字节（唯一事实源，sha 去重不重复入库）',
  tags       VARCHAR(512) COMMENT '标签（逗号分隔，可选）',
  note       TEXT COMMENT '备注',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登记时间（UTC）',
  UNIQUE KEY uk_file_sha (sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='源文件登记：sha256 去重，原件字节存 content，无磁盘副本';

CREATE TABLE IF NOT EXISTS extract_template (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '模板 ID',
  name            VARCHAR(128) NOT NULL COMMENT '模板名（唯一）',
  description     VARCHAR(512) COMMENT '模板说明',
  current_version INT NOT NULL DEFAULT 1 COMMENT '当前生效版本号',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  UNIQUE KEY uk_template_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提取模板：目标字段定义/映射/转换的版本容器';

CREATE TABLE IF NOT EXISTS extract_template_version (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '模板版本 ID',
  template_id    BIGINT NOT NULL COMMENT '所属模板 ID（引用 extract_template.id，应用层维护）',
  version        INT NOT NULL COMMENT '版本号（模板内递增）',
  schema_json    JSON COMMENT '目标字段定义（空=透传）',
  mapping_json   JSON COMMENT '源到目标字段映射（空=透传）',
  transform_json JSON COMMENT '字段转换规则（空=透传）',
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  UNIQUE KEY uk_tpl_ver (template_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模板版本：三段 JSON（字段定义/映射/转换）不可变快照';

CREATE TABLE IF NOT EXISTS extract_load_dest (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '入库目的地 ID',
  name       VARCHAR(128) NOT NULL COMMENT '目的地名称（唯一）',
  db_type    VARCHAR(32)  NOT NULL COMMENT '目标库类型：mysql 等',
  conn_ref   VARCHAR(128) NOT NULL COMMENT '凭据引用名（env 或 secrets.json，非密码）',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  UNIQUE KEY uk_dest_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入库目的地：目标库连接引用（凭据引用制，密码不入库）';

CREATE TABLE IF NOT EXISTS extract_load_mapping (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '入库映射 ID',
  load_dest_id      BIGINT NOT NULL COMMENT '目的地 ID（引用 extract_load_dest.id，应用层维护）',
  template_id       BIGINT NOT NULL COMMENT '模板 ID（引用 extract_template.id，应用层维护）',
  target_table      VARCHAR(128) NOT NULL COMMENT '目标业务表名',
  column_map_json   JSON NOT NULL COMMENT '模板字段到目标列映射',
  write_mode        VARCHAR(16) NOT NULL DEFAULT 'upsert' COMMENT '写入模式：upsert/insert/update',
  business_key_json JSON COMMENT '业务键（upsert 去重依据）',
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  UNIQUE KEY uk_dest_tpl_table (load_dest_id, template_id, target_table)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入库映射：模板字段到目标表列的映射与写入策略';

CREATE TABLE IF NOT EXISTS extract_task (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '任务 ID',
  mode                VARCHAR(16) NOT NULL COMMENT '模式：preview 预览 / load 入库',
  template_version_id BIGINT NOT NULL COMMENT '使用的模板版本 ID（引用 extract_template_version.id）',
  load_dest_id        BIGINT COMMENT '入库目的地 ID（preview 为空）',
  load_mapping_id     BIGINT COMMENT '入库映射 ID（preview 为空）',
  params_json         JSON COMMENT '生效提取参数快照',
  state               VARCHAR(24) NOT NULL DEFAULT 'pending' COMMENT '任务状态：pending/extracting/previewed/loaded/failed/partial',
  error               TEXT COMMENT '错误信息（失败时）',
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发起时间（UTC）',
  updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  KEY idx_task_state (state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提取任务：一次上传/提取的登记，状态与参数快照在此，产物按 task_file 粒度';

CREATE TABLE IF NOT EXISTS extract_task_file (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '任务文件 ID',
  task_id    BIGINT NOT NULL COMMENT '所属任务 ID（引用 extract_task.id，应用层维护）',
  file_id    BIGINT NOT NULL COMMENT '源文件 ID（引用 extract_file.id，应用层维护）',
  state      VARCHAR(24) NOT NULL DEFAULT 'pending' COMMENT '文件状态：pending/extracting/previewed/loaded/failed',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登记时间（UTC）',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  UNIQUE KEY uk_task_file (task_id, file_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务文件：任务内每个源文件的处理状态，产物/暂存记录均挂此粒度（重跑不覆盖历史）';

CREATE TABLE IF NOT EXISTS extract_quarantine (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '隔离记录 ID',
  task_id      BIGINT NOT NULL COMMENT '所属任务 ID（引用 extract_task.id，应用层维护）',
  task_file_id BIGINT COMMENT '所属任务文件 ID（引用 extract_task_file.id）',
  record_index INT COMMENT '记录在文件内下标',
  stage        VARCHAR(16) NOT NULL COMMENT '隔离阶段：extract/collect/review/load',
  reason       TEXT NOT NULL COMMENT '隔离原因',
  payload_json JSON NOT NULL COMMENT '问题记录快照',
  state        VARCHAR(16) NOT NULL DEFAULT 'open' COMMENT '处理状态：open/resolved/rejected',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '隔离时间（UTC）',
  resolved_at  DATETIME COMMENT '处理时间（UTC）',
  KEY idx_q_task (task_id, state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='隔离区：校验/入库失败记录，按 (task_file_id,record_index) 引用暂存记录';

CREATE TABLE IF NOT EXISTS extract_load_log (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '入库回执 ID',
  task_id        BIGINT NOT NULL COMMENT '所属任务 ID（引用 extract_task.id，应用层维护）',
  task_file_id   BIGINT NOT NULL COMMENT '所属任务文件 ID（引用 extract_task_file.id）',
  record_index   INT NOT NULL COMMENT '记录在文件内下标',
  load_dest_id   BIGINT NOT NULL COMMENT '目的地 ID（引用 extract_load_dest.id）',
  target_table   VARCHAR(128) NOT NULL COMMENT '目标业务表名',
  target_pk      VARCHAR(255) NOT NULL COMMENT '目标行主键值',
  action         VARCHAR(16) NOT NULL COMMENT '动作：insert/update/upsert/delete',
  loaded_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  UNIQUE KEY uk_load_receipt (task_file_id, record_index, load_dest_id, target_table)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='入库回执：每条记录写入目标库的幂等收据（唯一键防重）';

CREATE TABLE IF NOT EXISTS extract_staging_record (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '暂存记录 ID',
  task_file_id  BIGINT NOT NULL COMMENT '所属任务文件 ID（引用 extract_task_file.id，应用层维护）',
  record_index  INT NOT NULL COMMENT '记录在文件内下标（引用键的一半）',
  review_state  VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '校验状态：pending/edited/confirmed/rejected',
  review_at     DATETIME NULL COMMENT '校验时间（UTC）',
  values_json   MEDIUMTEXT NOT NULL COMMENT '当前值全保真 body（API 重建用）',
  original_json MEDIUMTEXT NOT NULL COMMENT '提取原值，永不覆盖',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC，patch 可追溯）',
  UNIQUE KEY uk_tf_idx (task_file_id, record_index),
  KEY idx_review (review_state)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='暂存记录：每行一条，全保真 JSON＋校验态，记录事实源';

CREATE TABLE IF NOT EXISTS extract_staging_field (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '字段投影 ID',
  record_id     BIGINT NOT NULL COMMENT '所属暂存记录 ID（引用 extract_staging_record.id，删除须应用层先清本表）',
  field_name    VARCHAR(128) NOT NULL COMMENT '模板字段名（动态）',
  value_text    TEXT NOT NULL COMMENT '当前值（含 edited）',
  original_text TEXT NOT NULL COMMENT '提取原值',
  KEY idx_field_value (field_name, value_text(191)),
  KEY idx_record (record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='暂存字段投影：values 的可查询展开（跨任务搜索用），可由 record 全量重建';

CREATE TABLE IF NOT EXISTS extract_staging_lineage (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '血缘 ID',
  record_id   BIGINT NOT NULL COMMENT '所属暂存记录 ID（引用 extract_staging_record.id，删除须应用层先清本表）',
  field_name  VARCHAR(128) NOT NULL COMMENT '模板字段名（动态）',
  region_seq  INT NOT NULL COMMENT '区域保序（同 cv_lineage 约定）',
  page        INT NOT NULL COMMENT '来源页码（1 起）',
  table_index INT NULL COMMENT '来源表下标',
  table_scope VARCHAR(16) NULL COMMENT '表口径：page 本页 / stitched 跨页合并',
  space       VARCHAR(16) NOT NULL COMMENT '坐标空间：source/rectified',
  cell_bbox   VARCHAR(128) NULL COMMENT '单元格框 [x0,y0,x1,y1] json 字符串',
  raw_text    TEXT NULL COMMENT '该格提取原文',
  UNIQUE KEY uk_rec_field_seq (record_id, field_name, region_seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='暂存血缘：逐格回溯锚点（页/表/框/原文），可由 record 全量重建';

CREATE TABLE IF NOT EXISTS extract_artifact (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '附件 ID',
  task_file_id BIGINT NOT NULL COMMENT '所属任务文件 ID（引用 extract_task_file.id，删除须应用层先清本表）',
  name         VARCHAR(200) NOT NULL COMMENT '任务文件内相对路径（正斜杠，如 pages/p1.png、对照报告.html）',
  kind         VARCHAR(20) NOT NULL COMMENT '产物类别：json/html/md/csv/image/raw',
  mime         VARCHAR(100) NOT NULL COMMENT 'MIME 类型（/files 路由回调用）',
  size_bytes   INT NOT NULL COMMENT '字节数',
  sha256       CHAR(64) NOT NULL COMMENT '内容 SHA-256（ETag 与导出校验）',
  content      LONGBLOB NOT NULL COMMENT '产物字节（唯一事实源，无持久磁盘）',
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）',
  UNIQUE KEY uk_artifact (task_file_id, name),
  KEY idx_artifact_sha (sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产物附件：报告/图片/CSV/extract.json 全量 BLOB，键＝任务文件粒度';

CREATE TABLE IF NOT EXISTS schema_version (
  version    INT PRIMARY KEY COMMENT '已应用的迁移编号',
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '应用时间（UTC）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='迁移器版本簿记（非业务表）';

-- 种子：内置模板「原始透传」（三个 JSON 空 = passthrough，不可删）
INSERT IGNORE INTO extract_template (name, description, current_version)
VALUES ('原始透传', '无字段定义 / 无映射 / 无转换：每表每行原样成为记录', 1);

INSERT IGNORE INTO extract_template_version (template_id, version, schema_json, mapping_json, transform_json)
SELECT id, 1, JSON_ARRAY(), JSON_OBJECT(), JSON_ARRAY()
FROM extract_template WHERE name = '原始透传';