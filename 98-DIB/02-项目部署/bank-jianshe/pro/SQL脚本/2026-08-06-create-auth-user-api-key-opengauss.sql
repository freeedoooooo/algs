-- 用户API密钥表
-- 创建时间: 2026-08-06

CREATE TABLE IF NOT EXISTS p_auth_user_api_key (
    id BIGINT NOT NULL,
    account VARCHAR(64) DEFAULT NULL,
    api_key VARCHAR(128) DEFAULT NULL,
    enable_flag SMALLINT DEFAULT 1,
    expire DATE DEFAULT NULL,
    del_flag SMALLINT DEFAULT 0,
    add_user_id VARCHAR(64) DEFAULT NULL,
    add_user_name VARCHAR(128) DEFAULT NULL,
    add_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_user_id VARCHAR(64) DEFAULT NULL,
    update_user_name VARCHAR(128) DEFAULT NULL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

-- 创建索引
CREATE INDEX idx_api_key_account ON p_auth_user_api_key(account);
CREATE UNIQUE INDEX uk_api_key_api_key ON p_auth_user_api_key(api_key);

-- 添加注释
COMMENT ON TABLE p_auth_user_api_key IS '用户API密钥表';
COMMENT ON COLUMN p_auth_user_api_key.id IS '主键';
COMMENT ON COLUMN p_auth_user_api_key.account IS '账号';
COMMENT ON COLUMN p_auth_user_api_key.api_key IS 'API密钥';
COMMENT ON COLUMN p_auth_user_api_key.enable_flag IS '是否启用(0:禁用,1:启用)';
COMMENT ON COLUMN p_auth_user_api_key.expire IS '过期时间';
COMMENT ON COLUMN p_auth_user_api_key.del_flag IS '删除标识(0:未删除,1:已删除)';
COMMENT ON COLUMN p_auth_user_api_key.add_user_id IS '创建人账号';
COMMENT ON COLUMN p_auth_user_api_key.add_user_name IS '创建人姓名';
COMMENT ON COLUMN p_auth_user_api_key.add_time IS '创建时间';
COMMENT ON COLUMN p_auth_user_api_key.update_user_id IS '更新人账号';
COMMENT ON COLUMN p_auth_user_api_key.update_user_name IS '更新人姓名';
COMMENT ON COLUMN p_auth_user_api_key.update_time IS '更新时间';
