-- 005_c1_storage.sql — C1 存储演进（design-c1-storage.md，用户 2026-11-20 批准）。
-- 1) 原件字节进 source_file.content（从 extract_artifact 'sources' 行按 sha8_name 搬入），
--    rel_path 退役；无字节且未被运行引用的幽灵登记行清除。
-- 2) extract_artifact 重建为 run_file 粒度：case_rel 行经 output_rel_dir 映射搬入
--    （FK 级联删，重跑不覆盖旧 run 产物）；无主孤儿行丢弃。
-- 3) run_file.output_rel_dir / run.batch_tag 退役（run id 天然唯一）。
-- 搬数在删列之前完成；迁移前已整库备份到 data/backup/。全新库上各搬数语句为空操作。

ALTER TABLE extract_source_file ADD COLUMN content LONGBLOB NULL AFTER size_bytes;

UPDATE extract_source_file s
  JOIN extract_artifact a
    ON a.case_rel='sources'
   AND a.name=CONCAT(LEFT(s.sha256,8),'_',s.name)
  SET s.content=a.content;

DELETE s FROM extract_source_file s
  LEFT JOIN extract_run_file rf ON rf.source_file_id=s.id
  WHERE s.content IS NULL AND rf.id IS NULL;

ALTER TABLE extract_source_file
  MODIFY COLUMN content LONGBLOB NOT NULL,
  DROP COLUMN rel_path;

CREATE TABLE extract_artifact_v2 (
  id INT AUTO_INCREMENT PRIMARY KEY,
  run_file_id BIGINT NOT NULL,
  name VARCHAR(200) NOT NULL,
  kind VARCHAR(20) NOT NULL,
  mime VARCHAR(100) NOT NULL,
  size_bytes INT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  content LONGBLOB NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_artifact (run_file_id, name),
  KEY idx_artifact_sha (sha256),
  CONSTRAINT fk_art_rf FOREIGN KEY (run_file_id)
    REFERENCES extract_run_file(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO extract_artifact_v2
  (run_file_id, name, kind, mime, size_bytes, sha256, content, created_at)
  SELECT rf.id, a.name, a.kind, a.mime, a.size_bytes, a.sha256, a.content,
         a.created_at
  FROM extract_artifact a
  JOIN extract_run_file rf
    ON rf.output_rel_dir=CONCAT('output/', a.case_rel)
  WHERE a.case_rel<>'sources';

DROP TABLE extract_artifact;

RENAME TABLE extract_artifact_v2 TO extract_artifact;

ALTER TABLE extract_run_file DROP COLUMN output_rel_dir;

ALTER TABLE extract_run DROP COLUMN batch_tag;