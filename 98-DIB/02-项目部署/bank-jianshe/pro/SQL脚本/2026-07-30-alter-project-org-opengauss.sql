-- opengauss版：

-- 1. 先添加列
ALTER TABLE p_mdm_project ADD COLUMN org_id      BIGINT;
ALTER TABLE p_mdm_project ADD COLUMN org_id_path VARCHAR(255);
ALTER TABLE p_mdm_project ADD COLUMN org_name    VARCHAR(255);

-- 2. 再单独添加注释
COMMENT ON COLUMN p_mdm_project.org_id      IS '组织ID';
COMMENT ON COLUMN p_mdm_project.org_id_path IS '组织全路径';
COMMENT ON COLUMN p_mdm_project.org_name    IS '组织名称';