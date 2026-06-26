-- =====================================================
-- 0011 数据资讯报告功能建表脚本
-- =====================================================

-- 1. 资讯报告目录表
CREATE TABLE `com_di_report_dir` (
  `id`               BIGINT        NOT NULL COMMENT '主键',
  `dir_name`         VARCHAR(100)  NOT NULL COMMENT '目录名称',
  `dir_desc`         VARCHAR(500)           COMMENT '目录说明',
  `parent_id`        BIGINT                 COMMENT '父节点ID（NULL表示一级）',
  `id_path`          VARCHAR(500)           COMMENT 'ID完整层级路径',
  `current_level`    INT                    COMMENT '当前层级（1或2）',
  `order_num`        INT                    COMMENT '排序序号',
  `enable_flag`      TINYINT(1)   DEFAULT 1 COMMENT '是否启用',
  `del_flag`         TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`      VARCHAR(50)            COMMENT '创建人账号',
  `add_user_name`    VARCHAR(100)           COMMENT '创建人姓名',
  `add_time`         DATETIME               COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)            COMMENT '更新人账号',
  `update_user_name` VARCHAR(100)           COMMENT '更新人姓名',
  `update_time`      DATETIME               COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资讯报告目录';

-- 2. 资讯报告表
CREATE TABLE `com_di_report` (
  `id`                  BIGINT        NOT NULL COMMENT '主键',
  `report_title`        VARCHAR(200)  NOT NULL COMMENT '报告标题',
  `report_dir_id`       BIGINT                 COMMENT '所属目录ID',
  `report_dir_id_path`  VARCHAR(500)           COMMENT '目录ID路径',
  `publish_date`        DATE                   COMMENT '发布日期',
  `report_year`         INT                    COMMENT '报告年份',
  `report_date`         DATE                   COMMENT '报告期',
  `att_id`              BIGINT                 COMMENT 'PDF附件ID',
  `txt_att_id`          BIGINT                 COMMENT 'TXT附件ID（AI生成简介用）',
  `cover_att_id`        BIGINT                 COMMENT '封面附件ID',
  `report_intro`        VARCHAR(2000)          COMMENT '报告简介',
  `intro_gen_status`    VARCHAR(20)  DEFAULT 'PENDING' COMMENT '简介生成状态：PENDING/GENERATING/GENERATED/FAILED',
  `enable_flag`         TINYINT(1)   DEFAULT 1 COMMENT '是否启用',
  `del_flag`            TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`         VARCHAR(50)            COMMENT '创建人账号',
  `add_user_name`       VARCHAR(100)           COMMENT '创建人姓名',
  `add_time`            DATETIME               COMMENT '创建时间',
  `update_user_id`      VARCHAR(50)            COMMENT '更新人账号',
  `update_user_name`    VARCHAR(100)           COMMENT '更新人姓名',
  `update_time`         DATETIME               COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_report_dir_id` (`report_dir_id`),
  INDEX `idx_report_dir_id_path` (`report_dir_id_path`(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资讯报告';

-- 3. 报告标签关联表
CREATE TABLE `com_di_report_tag` (
  `id`               BIGINT        NOT NULL COMMENT '主键',
  `report_id`        BIGINT        NOT NULL COMMENT '报告ID',
  `tag_name`         VARCHAR(100)  NOT NULL COMMENT '标签文本',
  `del_flag`         TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`      VARCHAR(50)            COMMENT '创建人账号',
  `add_user_name`    VARCHAR(100)           COMMENT '创建人姓名',
  `add_time`         DATETIME               COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)            COMMENT '更新人账号',
  `update_user_name` VARCHAR(100)           COMMENT '更新人姓名',
  `update_time`      DATETIME               COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_report_id` (`report_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告标签关联';

-- 4. 报告操作日志表
CREATE TABLE `com_di_report_opt_record` (
  `id`               BIGINT        NOT NULL COMMENT '主键',
  `report_id`        BIGINT        NOT NULL COMMENT '报告ID',
  `report_title`     VARCHAR(200)           COMMENT '报告标题',
  `opt_type`         VARCHAR(20)            COMMENT '操作类型：VISIT/DOWNLOAD',
  `del_flag`         TINYINT(1)   DEFAULT 0 COMMENT '删除标识',
  `add_user_id`      VARCHAR(50)            COMMENT '创建人账号',
  `add_user_name`    VARCHAR(100)           COMMENT '创建人姓名',
  `add_time`         DATETIME               COMMENT '创建时间',
  `update_user_id`   VARCHAR(50)            COMMENT '更新人账号',
  `update_user_name` VARCHAR(100)           COMMENT '更新人姓名',
  `update_time`      DATETIME               COMMENT '更新时间',
  PRIMARY KEY (`id`),
  INDEX `idx_report_id_add_time` (`report_id`, `add_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='报告操作日志';
