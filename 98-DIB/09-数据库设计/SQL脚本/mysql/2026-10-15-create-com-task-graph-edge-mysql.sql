-- 任务依赖图（设计态统一依赖图）+ 任务依赖表拓扑序号
-- 创建时间: 2026-10-15
-- 说明:
--   1. 新建共享表 com_task_graph_edge，记录 FRAME→RULE→INDEX→INDEX 依赖关系；
--      边方向 source=前置(上游), target=依赖方(下游)；节点ID: frameId/ruleId/indexCode。
--   2. com_task_dependency 新增 order_num（拓扑排序序号，1 表示最先算）。

-- =============================================================
-- 1. 任务依赖图的边
-- =============================================================
CREATE TABLE IF NOT EXISTS `com_task_graph_edge` (
    `id` BIGINT NOT NULL COMMENT '主键',
    `source_node_type` VARCHAR(16) DEFAULT NULL COMMENT '前置(上游)节点类型;FRAME|RULE|INDEX',
    `source_node_id` VARCHAR(128) DEFAULT NULL COMMENT '前置(上游)节点ID;frameId/ruleId/indexCode',
    `source_node_name` VARCHAR(255) DEFAULT NULL COMMENT '前置(上游)节点名称',
    `target_node_type` VARCHAR(16) DEFAULT NULL COMMENT '依赖方(下游)节点类型;FRAME|RULE|INDEX',
    `target_node_id` VARCHAR(128) DEFAULT NULL COMMENT '依赖方(下游)节点ID;frameId/ruleId/indexCode',
    `target_node_name` VARCHAR(255) DEFAULT NULL COMMENT '依赖方(下游)节点名称',
    `order_num` INT DEFAULT 0 COMMENT '顺序码;同一target下前置节点排序',
    `enable_flag` TINYINT(1) DEFAULT 1 COMMENT '是否启用(0:禁用,1:启用)',
    `del_flag` TINYINT(1) DEFAULT 0 COMMENT '删除标识(0:未删除,1:已删除)',
    `add_user_id` VARCHAR(64) DEFAULT NULL COMMENT '创建人账号',
    `add_user_name` VARCHAR(128) DEFAULT NULL COMMENT '创建人姓名',
    `add_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_user_id` VARCHAR(64) DEFAULT NULL COMMENT '更新人账号',
    `update_user_name` VARCHAR(128) DEFAULT NULL COMMENT '更新人姓名',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_task_graph_edge_target` (`target_node_type`, `target_node_id`),
    KEY `idx_task_graph_edge_source` (`source_node_type`, `source_node_id`),
    KEY `idx_task_graph_edge_partition` (`source_node_type`, `target_node_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务依赖图的边(设计态统一依赖图)';

-- =============================================================
-- 2. com_task_dependency 新增拓扑排序序号
-- =============================================================
ALTER TABLE `com_task_dependency`
ADD COLUMN `order_num` INT DEFAULT 0 COMMENT '拓扑排序序号;前置任务执行先后,1表示最先算';
