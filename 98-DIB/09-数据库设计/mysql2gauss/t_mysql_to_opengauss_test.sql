-- ============================================================================
-- MySQL迁移目标库兼容性测试表
-- 表名: t_mysql_migration_test
-- 用途: 覆盖MySQL迁移至目标库常见问题清单中的所有场景，验证数据迁移兼容性
-- 创建时间: 2026-08-03
-- ============================================================================

-- --------------------------------------------------------------------------
-- 一、建表语句（精简版：覆盖迁移高频字段类型与典型问题场景）
-- --------------------------------------------------------------------------
DROP TABLE IF EXISTS `t_mysql_migration_test`;

CREATE TABLE `t_mysql_migration_test` (

  -- ===================== 公共字段 =====================
  `id`                    BIGINT        NOT NULL AUTO_INCREMENT  COMMENT '自增主键',

  -- ===================== 场景1.1: TINYINT类型迁移 =====================
  -- 目标库可能不支持TINYINT，需转换为SMALLINT等兼容类型
  -- del_flag同时覆盖场景2.3: TINYINT+DEFAULT→需先DROP DEFAULT再改类型
  `del_flag`              TINYINT       NOT NULL DEFAULT 0       COMMENT '微整型非空带默认值',
  `is_primary`            TINYINT(1)    DEFAULT 0                COMMENT '微整型布尔',

  -- ===================== 场景1.2: BIT类型迁移 =====================
  -- MySQL的BIT(1)在部分目标库中需转换为SMALLINT等兼容类型
  `key_flag`              BIT(1)        DEFAULT b'0'             COMMENT '位类型',

  -- ===================== 场景1.3: VARCHAR长度溢出 =====================
  -- 迁移后VARCHAR长度定义可能与目标库不匹配，需扩容
  `biz_code`              VARCHAR(20)   DEFAULT NULL             COMMENT '变长',

  -- ===================== 场景2.1: NOT NULL约束冲突 =====================
  -- 迁移数据中存在空值，但字段定义为NOT NULL，触发约束冲突
  `table_schema`          VARCHAR(100)  NOT NULL                 COMMENT '变长非空',
  `add_user_id`           BIGINT        NOT NULL                 COMMENT '长整型非空',

  -- ===================== 场景2.2: 默认值迁移 =====================
  -- MySQL中定义的默认值，迁移至目标库后可能丢失
  `api_timeout`           INT           NOT NULL DEFAULT 300000  COMMENT '整型非空默认值',
  `default_str`           VARCHAR(50)   NOT NULL DEFAULT 'N/A'   COMMENT '变长非空默认值',
  `default_json`          JSON          DEFAULT NULL             COMMENT '文档类型可空',

  -- ===================== 场景3: 审计字段 =====================
  `add_time`              DATETIME      DEFAULT CURRENT_TIMESTAMP COMMENT '时间默认值',
  `update_time`           DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '时间默认值自动更新',

  -- ===================== 场景4.1: 大文本类型迁移 =====================
  `big_text`              TEXT          DEFAULT NULL             COMMENT '大文本',
  `long_text`             LONGTEXT      DEFAULT NULL             COMMENT '超大文本',

  -- ===================== 其他常用字段类型迁移 =====================
  `decimal_val`           DECIMAL(18,4) DEFAULT 0.0000           COMMENT '高精度小数',
  `bool_val`              BOOLEAN       DEFAULT FALSE            COMMENT '布尔',

  -- ===================== 主键与索引(场景5) =====================
  PRIMARY KEY (`id`),
  -- 唯一索引：迁移后需在目标库中重建验证
  UNIQUE KEY `uk_schema_add_user` (`table_schema`, `add_user_id`),
  -- 普通索引：验证索引迁移完整性
  KEY `idx_del_flag` (`del_flag`),
  KEY `idx_biz_code` (`biz_code`),
  KEY `idx_add_time` (`add_time`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='迁移目标库兼容性测试表';


-- --------------------------------------------------------------------------
-- 二、插入两条测试数据
-- 数据设计说明:
--   第1条: 各字段尽量填满，用于触发VARCHAR长度溢出和默认值覆盖等场景
--   第2条: 部分字段留NULL或使用DEFAULT，用于触发NOT NULL约束冲突和默认值丢失校验
-- --------------------------------------------------------------------------

INSERT INTO `t_mysql_migration_test` (
  `id`,
  -- 微整型
  `del_flag`, `is_primary`,
  -- 位类型
  `key_flag`,
  -- 变长
  `biz_code`,
  -- 非空
  `table_schema`, `add_user_id`,
  -- 默认值
  `api_timeout`, `default_str`, `default_json`,
  -- 审计字段
  `add_time`, `update_time`,
  -- 大文本
  `big_text`, `long_text`,
  -- 常用类型
  `decimal_val`, `bool_val`
) VALUES
-- ==================== 第1条: 全量填充触发溢出与覆盖场景 ====================
(
  1,
  -- 微整型
  0, 1,
  -- 位类型
  b'1',
  -- 变长(故意用较长值测试长度溢出)
  'BIZ2026080300001TEST',
  -- 非空
  'dib_report_copilot', 10001,
  -- 默认值(显式赋值覆盖默认值)
  600000, 'ACTIVE', '{"key":"value","timeout":300}',
  -- 审计字段
  '2026-07-01 08:00:00', '2026-08-03 10:30:00',
  -- 大文本(填充内容验证完整性)
  '大文本迁移测试验证目标库对文本类型的支持情况',
  '超大文本迁移测试部分表可能包含超长配置数据或模板内容需验证存储完整性',
  -- 常用类型
  12345678901234.5678, TRUE
),

-- ==================== 第2条: 部分空值加默认关键字触发约束与默认值校验 ====================
(
  2,
  -- 微整型
  1, 0,
  -- 位类型
  b'0',
  -- 变长(空值校验)
  NULL,
  -- 非空(必须填值否则导入失败)
  'dib_report_copilot', 0,
  -- 默认关键字(不显式赋值迁移后若默认值丢失将报错)
  DEFAULT, DEFAULT, NULL,
  -- 审计字段(部分留空测试空值校验)
  '2026-08-01 09:00:00', NULL,
  -- 大文本(空值)
  NULL, NULL,
  -- 常用类型
  0.0000, FALSE
);


-- --------------------------------------------------------------------------
-- 三、辅助查询：验证迁移后数据完整性
-- --------------------------------------------------------------------------
SELECT
  id,
  del_flag, is_primary, key_flag,
  biz_code,
  table_schema, add_user_id,
  api_timeout, default_str, default_json,
  LENGTH(big_text)  AS big_text_len,
  LENGTH(long_text) AS long_text_len,
  decimal_val, bool_val,
  add_time, update_time
FROM t_mysql_migration_test
ORDER BY id;
