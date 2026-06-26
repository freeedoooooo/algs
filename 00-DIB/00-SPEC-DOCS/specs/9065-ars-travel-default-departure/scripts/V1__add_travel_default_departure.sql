-- ============================================================
-- 功能：9065 差旅默认出发地点配置
-- 说明：新增系统参数 ft_travel_default_departure
-- 编码规则：省级2位 + 市级4位 + 区级6位（系统自定义编码，非国标）
-- ============================================================

-- ============================================================
-- 方式1：INSERT 新增配置（首次配置使用）
-- ============================================================
INSERT INTO common.t_base_data (
    c_id, 
    c_status, 
    c_description, 
    dt_crt_tm, 
    c_crt_usr, 
    c_upd_usr, 
    dt_upd_tm, 
    c_deleted, 
    c_name, 
    c_key, 
    c_value, 
    n_type, 
    c_category, 
    c_unit_name, 
    n_seq, 
    n_window_width, 
    n_window_height, 
    n_maintain
) VALUES (
    REPLACE(uuid_generate_v4()::text, '-', ''),  -- c_id: UUID格式
    1,                                            -- c_status: 启用状态
    '差旅费申请默认出发地点，格式：省级代码,市级代码,区级代码。当前配置：浙江省温州市鹿城区',
    NOW(),                                        -- dt_crt_tm: 创建时间
    '系统管理员',                                  -- c_crt_usr: 创建人
    '系统管理员',                                  -- c_upd_usr: 更新人
    NOW(),                                        -- dt_upd_tm: 更新时间
    '0',                                          -- c_deleted: 未删除
    '差旅默认出发地点',                            -- c_name: 参数名称
    'ft_travel_default_departure',                -- c_key: 参数键
    '33,3303,330302',                             -- c_value: 浙江省温州市鹿城区
    4,                                            -- n_type: 参数类型
    '',                                           -- c_category: 分类
    '',                                           -- c_unit_name: 单位名称
    0,                                            -- n_seq: 排序
    NULL,                                         -- n_window_width
    NULL,                                         -- n_window_height
    1                                             -- n_maintain: 可维护
);

-- ============================================================
-- 方式2：UPDATE 更新配置（已有配置时使用）
-- ============================================================
UPDATE common.t_base_data 
SET c_value = '33,3303,330302',
    c_description = '差旅费申请默认出发地点，格式：省级代码,市级代码,区级代码。当前配置：浙江省温州市鹿城区',
    c_upd_usr = '系统管理员',
    dt_upd_tm = NOW()
WHERE c_key = 'ft_travel_default_departure';

-- ============================================================
-- 编码规则说明（ARS 系统专用，非国标编码）
-- 
-- 省级：2位数字（如 33 = 浙江省）
-- 市级：4位数字（如 3303 = 温州市）
-- 区级：6位数字（如 330302 = 鹿城区）
--
-- 获取编码方法：
-- SELECT c_region_code, c_region_name, c_parent_code 
-- FROM fin_track.t_region_info_config 
-- WHERE c_region_name LIKE '%目标地区%';
-- ============================================================
