-- 框架准备-可视化 建表脚本
-- spec: 0010-rule-frame-visualization
-- date: 2026-04-14

CREATE TABLE `com_frame_visualization` (
  `id`                BIGINT       NOT NULL COMMENT '主键',
  `frame_id`          BIGINT       NOT NULL COMMENT '绑定的已发布框架ID',
  `stat_level`        INT          NOT NULL COMMENT '统计层级',
  `del_flag`          TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识',
  `add_user_id`       VARCHAR(50)  DEFAULT NULL COMMENT '创建人账号',
  `add_user_name`     VARCHAR(100) DEFAULT NULL COMMENT '创建人姓名',
  `add_time`          DATETIME     DEFAULT NULL COMMENT '创建时间',
  `update_user_id`    VARCHAR(50)  DEFAULT NULL COMMENT '更新人账号',
  `update_user_name`  VARCHAR(100) DEFAULT NULL COMMENT '更新人姓名',
  `update_time`       DATETIME     DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_frame_id` (`frame_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='框架可视化配置主表';

CREATE TABLE `com_frame_visualization_level` (
  `id`               BIGINT       NOT NULL COMMENT '主键',
  `visualization_id` BIGINT       NOT NULL COMMENT '关联可视化配置ID',
  `level_num`        INT          NOT NULL DEFAULT 0 COMMENT '结果等级',
  `level_name`       VARCHAR(100) NOT NULL COMMENT '风险等级名称（中文）',
  `score_range`      VARCHAR(100) NOT NULL COMMENT '分值区间，如 [0,60) / [60,100] / (-inf,0) / [0,+inf)，括号为开区间，方括号为闭区间',
  `level_color`      VARCHAR(50)  DEFAULT NULL COMMENT '展示颜色（十六进制或颜色名），为空时前端默认黑色',
  `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识',
  `add_user_id`      VARCHAR(50)  DEFAULT NULL COMMENT '创建人账号',
  `add_user_name`    VARCHAR(100) DEFAULT NULL COMMENT '创建人姓名',
  `add_time`         DATETIME     DEFAULT NULL COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)  DEFAULT NULL COMMENT '更新人账号',
  `update_user_name` VARCHAR(100) DEFAULT NULL COMMENT '更新人姓名',
  `update_time`      DATETIME     DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_visualization_id` (`visualization_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='框架可视化风险等级配置子表';
