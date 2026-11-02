-- 用户API密钥表
-- 创建时间: 2026-08-06

CREATE TABLE IF NOT EXISTS `p_auth_user_api_key` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    `account` VARCHAR(64) DEFAULT NULL COMMENT '账号',
    `api_key` VARCHAR(128) DEFAULT NULL COMMENT 'API密钥',
    `enable_flag` TINYINT(1) DEFAULT 1 COMMENT '是否启用(0:禁用,1:启用)',
    `expire` DATE DEFAULT NULL COMMENT '过期时间',
    `del_flag` TINYINT(1) DEFAULT 0 COMMENT '删除标识(0:未删除,1:已删除)',
    `add_user_id` VARCHAR(64) DEFAULT NULL COMMENT '创建人账号',
    `add_user_name` VARCHAR(128) DEFAULT NULL COMMENT '创建人姓名',
    `add_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_user_id` VARCHAR(64) DEFAULT NULL COMMENT '更新人账号',
    `update_user_name` VARCHAR(128) DEFAULT NULL COMMENT '更新人姓名',
    `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_account` (`account`),
    UNIQUE KEY `uk_api_key` (`api_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户API密钥表';
