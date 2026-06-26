-- =====================================================
-- V0008 新增数据资讯指标收藏表 com_di_index_favorite
-- =====================================================
CREATE TABLE `com_di_index_favorite`
(
    `id`               BIGINT       NOT NULL COMMENT '主键',
    `index_id`         BIGINT       NOT NULL COMMENT '指标ID（关联 com_di_index.id）',
    `user_id`          VARCHAR(50)  NOT NULL COMMENT '用户账号',
    `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识（0-正常，1-已删除）',
    `add_user_id`      VARCHAR(50)           COMMENT '创建人账号',
    `add_user_name`    VARCHAR(100)          COMMENT '创建人姓名',
    `add_time`         DATETIME              COMMENT '创建时间',
    `update_user_id`   VARCHAR(50)           COMMENT '更新人账号',
    `update_user_name` VARCHAR(100)          COMMENT '更新人姓名',
    `update_time`      DATETIME              COMMENT '更新时间',
    PRIMARY KEY (`id`),
    INDEX `idx_user_id_index_id` (`user_id`, `index_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4 COMMENT = '数据资讯指标收藏表';
