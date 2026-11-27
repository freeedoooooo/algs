-- 005_compute_graph_layout.sql — 计算流程图工作台节点坐标。
-- 关系仍以 c1_rule_info.index_refs_json / c1_frame_info.rule_refs_json 为唯一事实源；
-- 本表只保存 (scope, def_id) 对应的画布坐标，删除定义时由仓储同事务清理。
-- 幂等：CREATE IF NOT EXISTS；不清空已有布局。

CREATE TABLE IF NOT EXISTS `c1_compute_graph_layout` (
  `scope` varchar(8) NOT NULL COMMENT '节点域：document/source/index/rule/frame',
  `def_id` bigint NOT NULL COMMENT '资料ID、数据表锚点指标ID或定义表 ID',
  `pos_x` double NOT NULL COMMENT '画布逻辑坐标 X',
  `pos_y` double NOT NULL COMMENT '画布逻辑坐标 Y',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '坐标更新时间（UTC）',
  PRIMARY KEY (`scope`,`def_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='计算流程图节点布局';
