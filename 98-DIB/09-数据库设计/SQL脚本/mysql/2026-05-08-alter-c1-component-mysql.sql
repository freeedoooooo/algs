-- dib-agent-parent/dib-agent-field-dim-mapping-starter 组件脚本
-- 建表语句
CREATE TABLE `com_pub_field_dim_mapping` (
`id` bigint NOT NULL COMMENT '主键',
`table_name` varchar(255) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '表名',
`field_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '字段名',
`dim_id` bigint NOT NULL COMMENT '维度元数据主键',
`dim_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '维度名称',
`dim_level` int NOT NULL COMMENT '维度层级',
`remark` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '备注',
`del_flag` tinyint NOT NULL DEFAULT '0' COMMENT '是否删除',
`add_user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '创建人账号',
`add_user_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '创建人姓名',
`add_time` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '创建时间',
`update_user_id` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '更新人账号',
`update_user_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '更新人姓名',
`update_time` datetime DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
PRIMARY KEY (`id`),
UNIQUE KEY `unq_idx_table_name_dim_id` (`table_name`,`dim_id`) USING BTREE COMMENT '维度元数据主键唯一索引',
UNIQUE KEY `unq_idx_table_name_field_name` (`table_name`,`field_name`) USING BTREE COMMENT '字段名唯一索引'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='表扩展字段与维度的映射';

-- 从 com_frame_value_field 写入 com_pub_field_dim_mapping
INSERT INTO com_pub_field_dim_mapping
(
id,
table_name,
field_name,
dim_id,
dim_name,
dim_level,
remark,
del_flag,
add_user_id,
add_user_name,
add_time,
update_user_id,
update_user_name,
update_time
)
SELECT
UUID_SHORT() AS id,
'com_frame_value' AS table_name,
frame_value_field_name AS field_name,
dim_id,
dim_name,
dim_level,
NULL AS remark,
del_flag,
add_user_id,
add_user_name,
add_time,
update_user_id,
update_user_name,
update_time
FROM com_frame_value_field;

-- 从 com_rule_value_field 写入 com_pub_field_dim_mapping
INSERT INTO com_pub_field_dim_mapping
(
id,
table_name,
field_name,
dim_id,
dim_name,
dim_level,
remark,
del_flag,
add_user_id,
add_user_name,
add_time,
update_user_id,
update_user_name,
update_time
)
SELECT
UUID_SHORT() AS id,
'com_rule_biz_value' AS table_name,
rule_value_field_name AS field_name,
dim_id,
dim_name,
dim_level,
NULL AS remark,
del_flag,
add_user_id,
add_user_name,
add_time,
update_user_id,
update_user_name,
update_time
FROM com_rule_value_field;

-- 从 com_data_index_value_field 写入 com_pub_field_dim_mapping
INSERT INTO com_pub_field_dim_mapping
(
id,
table_name,
field_name,
dim_id,
dim_name,
dim_level,
remark,
del_flag,
add_user_id,
add_user_name,
add_time,
update_user_id,
update_user_name,
update_time
)
SELECT
UUID_SHORT() AS id,
'com_data_index_value' AS table_name,
index_value_field_name AS field_name,
dim_id,
dim_name,
dim_level,
remark,
del_flag,
add_user_id,
add_user_name,
add_time,
update_user_id,
update_user_name,
update_time
FROM com_data_index_value_field;