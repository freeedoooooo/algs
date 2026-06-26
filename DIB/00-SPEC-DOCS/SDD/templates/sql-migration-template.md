-- ============================================================
-- 功能名：{功能名}
-- 模块：{模块标识} | 服务：{服务名}
-- 创建时间：{YYYY-MM-DD}
-- 说明：{本脚本的用途说明}
-- ============================================================

-- ============================================================
-- 新增表（如有）
-- ============================================================
CREATE TABLE IF NOT EXISTS `{table_name}` (
    `id`               BIGINT       NOT NULL COMMENT '主键',
    -- 业务字段
    `{field_name}`     VARCHAR(255) NOT NULL COMMENT '{字段说明}',
    -- 基础字段（必须包含）
    `del_flag`         TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '删除标识',
    `add_user_id`      VARCHAR(50)  NULL COMMENT '创建人账号',
    `add_user_name`    VARCHAR(100) NULL COMMENT '创建人姓名',
    `add_time`         DATETIME     NULL COMMENT '创建时间',
    `update_user_id`   VARCHAR(50)  NULL COMMENT '更新人账号',
    `update_user_name` VARCHAR(100) NULL COMMENT '更新人姓名',
    `update_time`      DATETIME     NULL COMMENT '更新时间',
    PRIMARY KEY (`id`),
    -- 索引
    INDEX `idx_{field_name}` (`{field_name}`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COMMENT = '{表说明}';


-- ============================================================
-- 修改表（如有）
-- ============================================================
-- ALTER TABLE `{table_name}` ADD COLUMN `{field_name}` VARCHAR(255) NULL COMMENT '{字段说明}' AFTER `{after_field}`;
-- ALTER TABLE `{table_name}` ADD INDEX `idx_{field_name}` (`{field_name}`);


-- ============================================================
-- 初始化数据（如有）
-- ============================================================
-- INSERT INTO `{table_name}` (...) VALUES (...);
