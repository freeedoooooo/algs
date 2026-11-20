-- 002_rename_comment.sql — 业务表统一 extract_ 前缀 + 表/列注释 + 命名审视
-- 9 张业务表加 extract_ 前缀（与平台库内其他业务域隔离）；schema_version 是迁移器
-- 自身的版本簿记表（非业务表），保留原名以保证迁移幂等，不加前缀。
-- RENAME TABLE 为原子操作，InnoDB 自动同步外键引用；随后逐表补注释。
-- 列名审视：source_file_id / run_id / template_version_id 等外键列语义清晰，保持不变。

RENAME TABLE
  source_file      TO extract_source_file,
  template         TO extract_template,
  template_version TO extract_template_version,
  destination      TO extract_destination,
  load_mapping     TO extract_load_mapping,
  run              TO extract_run,
  run_file         TO extract_run_file,
  quarantine       TO extract_quarantine,
  load_log         TO extract_load_log;

ALTER TABLE extract_source_file
  COMMENT='源文件目录：sha256 去重登记，规范副本存 sources/',
  MODIFY COLUMN id         BIGINT AUTO_INCREMENT COMMENT '源文件 ID',
  MODIFY COLUMN name       VARCHAR(255) NOT NULL COMMENT '原始文件名',
  MODIFY COLUMN sha256     CHAR(64) NOT NULL COMMENT '内容 SHA-256（去重键）',
  MODIFY COLUMN kind       VARCHAR(16) NOT NULL COMMENT '载体类型：image/pdf/csv/text',
  MODIFY COLUMN size_bytes BIGINT NOT NULL COMMENT '文件字节数',
  MODIFY COLUMN rel_path   VARCHAR(512) NOT NULL COMMENT 'sources/ 规范副本相对路径',
  MODIFY COLUMN tags       VARCHAR(512) COMMENT '标签（逗号分隔，可选）',
  MODIFY COLUMN note       TEXT COMMENT '备注',
  MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登记时间（UTC）';

ALTER TABLE extract_template
  COMMENT='提取模板：目标字段定义/映射/转换的版本容器',
  MODIFY COLUMN id              BIGINT AUTO_INCREMENT COMMENT '模板 ID',
  MODIFY COLUMN name            VARCHAR(128) NOT NULL COMMENT '模板名（唯一）',
  MODIFY COLUMN description     VARCHAR(512) COMMENT '模板说明',
  MODIFY COLUMN current_version INT NOT NULL DEFAULT 1 COMMENT '当前生效版本号',
  MODIFY COLUMN created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）',
  MODIFY COLUMN updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）';

ALTER TABLE extract_template_version
  COMMENT='模板版本：三段 JSON（字段定义/映射/转换）不可变快照',
  MODIFY COLUMN id             BIGINT AUTO_INCREMENT COMMENT '模板版本 ID',
  MODIFY COLUMN template_id    BIGINT NOT NULL COMMENT '所属模板 ID',
  MODIFY COLUMN version        INT NOT NULL COMMENT '版本号（模板内递增）',
  MODIFY COLUMN schema_json    JSON COMMENT '目标字段定义（空=透传）',
  MODIFY COLUMN mapping_json   JSON COMMENT '源到目标字段映射（空=透传）',
  MODIFY COLUMN transform_json JSON COMMENT '字段转换规则（空=透传）',
  MODIFY COLUMN created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）';

ALTER TABLE extract_destination
  COMMENT='入库目的地：目标库连接引用（凭据引用制，密码不入库）',
  MODIFY COLUMN id         BIGINT AUTO_INCREMENT COMMENT '目的地 ID',
  MODIFY COLUMN name       VARCHAR(128) NOT NULL COMMENT '目的地名称（唯一）',
  MODIFY COLUMN db_type    VARCHAR(32) NOT NULL COMMENT '目标库类型：mysql 等',
  MODIFY COLUMN conn_ref   VARCHAR(128) NOT NULL COMMENT '凭据引用名（env 或 secrets.json，非密码）',
  MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间（UTC）';

ALTER TABLE extract_load_mapping
  COMMENT='入库映射：模板字段到目标表列的映射与写入策略',
  MODIFY COLUMN id                BIGINT AUTO_INCREMENT COMMENT '入库映射 ID',
  MODIFY COLUMN destination_id    BIGINT NOT NULL COMMENT '目的地 ID',
  MODIFY COLUMN template_id       BIGINT NOT NULL COMMENT '模板 ID',
  MODIFY COLUMN target_table      VARCHAR(128) NOT NULL COMMENT '目标业务表名',
  MODIFY COLUMN column_map_json   JSON NOT NULL COMMENT '模板字段到目标列映射',
  MODIFY COLUMN write_mode        VARCHAR(16) NOT NULL DEFAULT 'upsert' COMMENT '写入模式：upsert/insert/update',
  MODIFY COLUMN business_key_json JSON COMMENT '业务键（upsert 去重依据）';

ALTER TABLE extract_run
  COMMENT='运行批次：一次提取/入库的目录登记（内容事实源在 output/records.json）',
  MODIFY COLUMN id                  BIGINT AUTO_INCREMENT COMMENT '运行 ID',
  MODIFY COLUMN batch_tag           VARCHAR(32) NOT NULL COMMENT '批次标签（output 目录前缀，文件留档键）',
  MODIFY COLUMN mode                VARCHAR(16) NOT NULL COMMENT '模式：preview 预览 / load 入库',
  MODIFY COLUMN template_version_id BIGINT NOT NULL COMMENT '使用的模板版本 ID',
  MODIFY COLUMN destination_id      BIGINT COMMENT '入库目的地 ID（preview 为空）',
  MODIFY COLUMN load_mapping_id     BIGINT COMMENT '入库映射 ID（preview 为空）',
  MODIFY COLUMN params_json         JSON COMMENT '生效提取参数快照',
  MODIFY COLUMN state               VARCHAR(24) NOT NULL DEFAULT 'pending' COMMENT '运行状态：pending/extracting/previewed/loaded/failed/partial',
  MODIFY COLUMN error               TEXT COMMENT '错误信息（失败时）',
  MODIFY COLUMN created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发起时间（UTC）',
  MODIFY COLUMN updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间（UTC）',
  ADD KEY idx_run_batch (batch_tag);

ALTER TABLE extract_run_file
  COMMENT='运行文件：批次内每个源文件的处理状态与产物目录',
  MODIFY COLUMN id             BIGINT AUTO_INCREMENT COMMENT '运行文件 ID',
  MODIFY COLUMN run_id         BIGINT NOT NULL COMMENT '所属运行 ID',
  MODIFY COLUMN source_file_id BIGINT NOT NULL COMMENT '源文件 ID',
  MODIFY COLUMN state          VARCHAR(24) NOT NULL DEFAULT 'pending' COMMENT '文件状态：pending/extracting/previewed/loaded/failed',
  MODIFY COLUMN output_rel_dir VARCHAR(512) NOT NULL COMMENT 'output/ 产物目录相对路径';

ALTER TABLE extract_quarantine
  COMMENT='隔离区：校验/入库失败记录，按 (run_file_id,record_index) 引用事实源',
  MODIFY COLUMN id           BIGINT AUTO_INCREMENT COMMENT '隔离记录 ID',
  MODIFY COLUMN run_id       BIGINT NOT NULL COMMENT '所属运行 ID',
  MODIFY COLUMN run_file_id  BIGINT COMMENT '所属运行文件 ID',
  MODIFY COLUMN record_index INT COMMENT '记录序号（records.json 内）',
  MODIFY COLUMN stage        VARCHAR(16) NOT NULL COMMENT '隔离阶段：extract/collect/review/load',
  MODIFY COLUMN reason       TEXT NOT NULL COMMENT '隔离原因',
  MODIFY COLUMN payload_json JSON NOT NULL COMMENT '问题记录快照',
  MODIFY COLUMN state        VARCHAR(16) NOT NULL DEFAULT 'open' COMMENT '处理状态：open/resolved/rejected',
  MODIFY COLUMN created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '隔离时间（UTC）',
  MODIFY COLUMN resolved_at  DATETIME COMMENT '处理时间（UTC）';

ALTER TABLE extract_load_log
  COMMENT='入库回执：每条记录写入目标库的幂等收据（唯一键防重）',
  MODIFY COLUMN id             BIGINT AUTO_INCREMENT COMMENT '入库回执 ID',
  MODIFY COLUMN run_id         BIGINT NOT NULL COMMENT '所属运行 ID',
  MODIFY COLUMN run_file_id    BIGINT NOT NULL COMMENT '所属运行文件 ID',
  MODIFY COLUMN record_index   INT NOT NULL COMMENT '记录序号',
  MODIFY COLUMN destination_id BIGINT NOT NULL COMMENT '目的地 ID',
  MODIFY COLUMN target_table   VARCHAR(128) NOT NULL COMMENT '目标业务表名',
  MODIFY COLUMN target_pk      VARCHAR(255) NOT NULL COMMENT '目标行主键值',
  MODIFY COLUMN action         VARCHAR(16) NOT NULL COMMENT '动作：insert/update/upsert/delete',
  MODIFY COLUMN loaded_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间（UTC）';