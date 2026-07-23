# 地区编码获取说明

> ⚠️ **重要提示**：本系统使用**自定义简化编码**，不是国家标准6位编码！

---

## 编码规则（ARS 系统专用）

本系统的地区编码存储在 `fin_track.t_region_info_config` 表中，采用简化编码格式：

| 层级 | 编码位数 | 示例 |
|------|---------|------|
| 省级 | 2位 | `33`（浙江省） |
| 市级 | 4位 | `3303`（温州市） |
| 区级 | 6位 | `330302`（鹿城区） |

---

## 如何获取正确的地区编码

### 方法1：查询数据库（推荐）

```sql
-- 查询指定地区的编码
SELECT c_region_code, c_region_name, c_parent_code 
FROM fin_track.t_region_info_config 
WHERE c_region_name LIKE '%浙江%' 
   OR c_region_name LIKE '%温州%' 
   OR c_region_name LIKE '%鹿城%'
ORDER BY c_region_code;

-- 查询所有省份
SELECT c_region_code, c_region_name 
FROM fin_track.t_region_info_config 
WHERE c_parent_code = '0'
ORDER BY c_region_code;

-- 查询某省下的所有市
SELECT c_region_code, c_region_name 
FROM fin_track.t_region_info_config 
WHERE c_parent_code = '33'  -- 浙江省
ORDER BY c_region_code;

-- 查询某市下的所有区
SELECT c_region_code, c_region_name 
FROM fin_track.t_region_info_config 
WHERE c_parent_code = '3303'  -- 温州市
ORDER BY c_region_code;
```

### 方法2：查看前端控制台

刷新差旅费申请页面，查看控制台 `[kaiao] 浙江省数据:` 的输出。

---

## 配置格式

参数值格式：`省级代码,市级代码,区级代码`（逗号分隔，无空格）

**示例**：`33,3303,330302`（浙江省温州市鹿城区）

---

## 配置到系统参数

### 方法1：通过系统管理界面

在系统参数管理中配置：

| 参数 Key | 参数值 |
|---------|--------|
| `ft_travel_default_departure` | `33,3303,330302` |

### 方法2：通过 SQL 更新

```sql
-- 更新已有配置
UPDATE common.t_base_data 
SET c_value = '33,3303,330302',
    c_description = '差旅费申请默认出发地点，当前配置：浙江省温州市鹿城区'
WHERE c_key = 'ft_travel_default_departure';
```

---

## 注意事项

1. **编码必须从数据库查询**：不能使用国标编码，必须使用系统实际存储的编码
2. **三级完整**：必须配置完整的省-市-区三级编码，否则级联选择器无法正确显示
3. **编码格式**：省级2位、市级4位、区级6位（具体以数据库为准）
4. **多个默认地点**：暂不支持，只能配置一个
