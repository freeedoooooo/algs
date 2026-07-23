-- dib-agent-parent/dib-agent-field-dim-mapping-starter 组件脚本
-- 建表语句
CREATE TABLE com_pub_field_dim_mapping (
    id bigint NOT NULL,
    table_name varchar(255),
    field_name varchar(255) NOT NULL,
    dim_id bigint NOT NULL,
    dim_name varchar(50) NOT NULL,
    dim_level int NOT NULL,
    remark varchar(255),
    del_flag smallint NOT NULL DEFAULT 0,
    add_user_id varchar(50),
    add_user_name varchar(50),
    add_time timestamp NULL,
    update_user_id varchar(50),
    update_user_name varchar(50),
    update_time timestamp NULL,
    CONSTRAINT pk_com_pub_field_dim_mapping PRIMARY KEY (id),
    CONSTRAINT unq_idx_table_name_dim_id UNIQUE (table_name, dim_id),
    CONSTRAINT unq_idx_table_name_field_name UNIQUE (table_name, field_name)
);

COMMENT ON TABLE com_pub_field_dim_mapping IS '表扩展字段与维度的映射';
COMMENT ON COLUMN com_pub_field_dim_mapping.id IS '主键';
COMMENT ON COLUMN com_pub_field_dim_mapping.table_name IS '表名';
COMMENT ON COLUMN com_pub_field_dim_mapping.field_name IS '字段名';
COMMENT ON COLUMN com_pub_field_dim_mapping.dim_id IS '维度元数据主键';
COMMENT ON COLUMN com_pub_field_dim_mapping.dim_name IS '维度名称';
COMMENT ON COLUMN com_pub_field_dim_mapping.dim_level IS '维度层级';
COMMENT ON COLUMN com_pub_field_dim_mapping.remark IS '备注';
COMMENT ON COLUMN com_pub_field_dim_mapping.del_flag IS '是否删除';
COMMENT ON COLUMN com_pub_field_dim_mapping.add_user_id IS '创建人账号';
COMMENT ON COLUMN com_pub_field_dim_mapping.add_user_name IS '创建人姓名';
COMMENT ON COLUMN com_pub_field_dim_mapping.add_time IS '创建时间';
COMMENT ON COLUMN com_pub_field_dim_mapping.update_user_id IS '更新人账号';
COMMENT ON COLUMN com_pub_field_dim_mapping.update_user_name IS '更新人姓名';
COMMENT ON COLUMN com_pub_field_dim_mapping.update_time IS '更新时间';

CREATE SEQUENCE seq_com_pub_field_dim_mapping
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

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
nextval('seq_com_pub_field_dim_mapping') AS id,
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
nextval('seq_com_pub_field_dim_mapping') AS id,
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
nextval('seq_com_pub_field_dim_mapping') AS id,
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
