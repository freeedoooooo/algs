-- =====================================================
-- V0007 新增数据资讯快讯表 com_di_news_flash
-- =====================================================
CREATE TABLE `com_di_news_flash`
(
    `id`               BIGINT       NOT NULL COMMENT '主键',
    `news_topic_type`  VARCHAR(50)  NOT NULL COMMENT '主题标签（NEW_DB/NEW_TABLE/NEW_REPORT/NEW_FUNC）',
    `title`            VARCHAR(200) NOT NULL COMMENT '标题',
    `start_date`       DATE         NOT NULL COMMENT '开始日期',
    `end_date`         DATE         NOT NULL COMMENT '结束日期',
    `important_flag`   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否重大资讯（0-否，1-是）',
    `link_url`         VARCHAR(500)          COMMENT '跳转链接',
    `description`      TEXT                  COMMENT '描述',
    `enable_flag`      TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '激活状态（0-禁用，1-启用）',
    `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识（0-正常，1-已删除）',
    `add_user_id`      VARCHAR(50)           COMMENT '创建人账号',
    `add_user_name`    VARCHAR(100)          COMMENT '创建人姓名',
    `add_time`         DATETIME              COMMENT '创建时间',
    `update_user_id`   VARCHAR(50)           COMMENT '更新人账号',
    `update_user_name` VARCHAR(100)          COMMENT '更新人姓名',
    `update_time`      DATETIME              COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_news_topic_type` (`news_topic_type`),
    INDEX `idx_start_date` (`start_date`),
    INDEX `idx_end_date` (`end_date`),
    INDEX `idx_enable_flag` (`enable_flag`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT = '数据资讯快讯表';
