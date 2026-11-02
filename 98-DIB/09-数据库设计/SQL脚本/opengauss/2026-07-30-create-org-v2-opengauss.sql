-- org_2
CREATE TABLE "dib_report_copilot"."p_mdm_org_2"
(
    "id"                bigint                  NOT NULL,
    "parent_id"         bigint                  NOT NULL,
    "id_path"           character varying(1020) NOT NULL,
    "org_name"          character varying(200)  NOT NULL,
    "org_type"          character varying(200)  NOT NULL,
    "manager_user_id"   character varying(200),
    "manager_user_name" character varying(200),
    "remark"            character varying(2000),
    "order_num"         integer,
    "enable_flag"       smallint                NOT NULL DEFAULT 1,
    "del_flag"          smallint                NOT NULL DEFAULT 0,
    "add_user_id"       character varying(200),
    "add_user_name"     character varying(200),
    "add_time"          timestamp without time zone,
    "update_user_id"    character varying(200),
    "update_time"       timestamp without time zone,
    "update_user_name"  character varying(200),
    PRIMARY KEY ("id")
);

COMMENT ON TABLE "dib_report_copilot"."p_mdm_org_2" IS '组织单位表';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."id" IS '主键';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."parent_id" IS '父节点ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."id_path" IS '组织ID全路径';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."org_name" IS '组织名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."org_type" IS '组织类型';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."manager_user_id" IS '负责人ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."manager_user_name" IS '负责人名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."remark" IS '备注';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."order_num" IS '排序码';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."enable_flag" IS '激活标识';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."del_flag" IS '删除标识';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."add_user_id" IS '创建人ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."add_user_name" IS '创建人名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."add_time" IS '创建时间';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."update_user_id" IS '更新人ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."update_time" IS '更新时间';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_2"."update_user_name" IS '更新人名称';


-- org_user_2
CREATE TABLE "dib_report_copilot"."p_mdm_org_user_2"
(
    "id"               bigint                  NOT NULL,
    "account"          character varying(200)  NOT NULL,
    "user_name"        character varying(200)  NOT NULL,
    "org_id"           bigint                  NOT NULL,
    "org_name"         character varying(1020) NOT NULL,
    "org_id_path"      character varying(1020) NOT NULL,
    "belong_flag"      smallint                NOT NULL DEFAULT 0,
    "del_flag"         smallint                NOT NULL DEFAULT 0,
    "add_user_id"      character varying(200),
    "add_user_name"    character varying(200),
    "add_time"         timestamp without time zone,
    "update_user_id"   character varying(200),
    "update_user_name" character varying(200),
    "update_time"      timestamp without time zone,
    PRIMARY KEY ("id")
);

COMMENT ON TABLE "dib_report_copilot"."p_mdm_org_user_2" IS '用户组织授权表';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."id" IS '主键';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."account" IS '用户账号';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."user_name" IS '用户名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."org_id" IS '组织ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."org_name" IS '组织名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."org_id_path" IS '组织全路径';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."belong_flag" IS '所属标识';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."del_flag" IS '删除标识';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."add_user_id" IS '创建人ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."add_user_name" IS '创建人名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."add_time" IS '创建时间';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."update_user_id" IS '更新人ID';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."update_user_name" IS '更新人名称';
COMMENT ON COLUMN "dib_report_copilot"."p_mdm_org_user_2"."update_time" IS '更新时间';