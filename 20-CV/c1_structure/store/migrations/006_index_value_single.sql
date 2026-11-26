-- 006_index_value_single.sql — 指标结果每个定义只保留最新一行。
-- 执行方式：在停用旧版计算写入后执行一次；本脚本会删除重复历史结果。

DELETE old_value
FROM c1_index_value AS old_value
INNER JOIN c1_index_value AS keep_value
  ON keep_value.index_id = old_value.index_id
 AND keep_value.id > old_value.id;

ALTER TABLE c1_index_value
  ADD UNIQUE KEY uk_index_value_def (index_id);
