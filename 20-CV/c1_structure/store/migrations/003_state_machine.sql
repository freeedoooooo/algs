-- 003_state_machine.sql — 任务状态机重构（2026-11-23 裁决）：解析/抽取解耦。
--   新枚举 pending/parsing/to_extract/to_review/to_load/loading/loaded/failed；
--   退役 extracting/previewed/partial/reviewed。to_load 为派生态：
--   文件全部记录已定论（无 pending/edited/rejected 且有记录）。
--   任务态 = 文件态 rank 上卷（任一 failed→failed，否则最落后）。
-- 执行：人工惯例（store/db.py 不自动迁移）。先备份两表行像 →
--   分流 → 上卷精修 → 列注释（001 基线同步）。备份：data/backup/c1_dev_pre003_*.sql

-- 1) 文件态分流：previewed 有暂存记录→to_review（待校验），无记录→to_extract
UPDATE c1_task_file tf
  JOIN (SELECT sr.task_file_id AS id FROM c1_staging_record sr
        GROUP BY sr.task_file_id) x ON x.id = tf.id
   SET tf.state = 'to_review'
 WHERE tf.state = 'previewed';
UPDATE c1_task_file SET state = 'to_extract' WHERE state = 'previewed';
-- 历史残留兜底（当前盘点均为 0，保幂等）
UPDATE c1_task_file SET state = 'to_review' WHERE state = 'reviewed';
UPDATE c1_task_file SET state = 'parsing'   WHERE state = 'extracting';
UPDATE c1_task_file SET state = 'to_load'   WHERE state = 'partial';

-- 2) 任务态上卷精修（含仍是旧词的任务头）
UPDATE c1_task t
  JOIN (SELECT task_id,
               CASE WHEN SUM(state='failed') > 0 THEN 'failed'
                    ELSE ELT(MIN(FIELD(state,'pending','parsing','to_extract',
                      'to_review','to_load','loading','loaded')),
                      'pending','parsing','to_extract','to_review',
                      'to_load','loading','loaded') END AS ns
          FROM c1_task_file GROUP BY task_id) x ON x.task_id = t.id
   SET t.state = x.ns
 WHERE t.state <> x.ns
    OR t.state IN ('previewed','partial','reviewed','extracting');

-- 3) 列注释更新为新枚举
ALTER TABLE c1_task MODIFY COLUMN state varchar(24) NOT NULL DEFAULT 'pending'
  COMMENT '任务状态：pending/parsing/to_extract/to_review/to_load/loading/loaded/failed（文件态上卷）';
ALTER TABLE c1_task_file MODIFY COLUMN state varchar(24) NOT NULL DEFAULT 'pending'
  COMMENT '文件状态：pending/parsing/to_extract/to_review/to_load/loading/loaded/failed';
