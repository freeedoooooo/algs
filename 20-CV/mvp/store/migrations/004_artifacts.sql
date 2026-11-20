-- 004_artifacts.sql — 产物附件入库（design-artifacts-db.md，选项 1 全量）。
-- case_rel='<case目录名>' 或 'sources'；name=case 内相对路径（正斜杠）。
-- 重跑＝同 (case_rel,name) upsert 替换；raw  kind 不对外（路由 403）。
CREATE TABLE IF NOT EXISTS extract_artifact (
  id INT AUTO_INCREMENT PRIMARY KEY,
  case_rel VARCHAR(160) NOT NULL,
  name VARCHAR(200) NOT NULL,
  kind VARCHAR(20) NOT NULL,
  mime VARCHAR(100) NOT NULL,
  size_bytes INT NOT NULL,
  sha256 CHAR(64) NOT NULL,
  content LONGBLOB NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_artifact (case_rel, name),
  KEY idx_artifact_sha (sha256)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;