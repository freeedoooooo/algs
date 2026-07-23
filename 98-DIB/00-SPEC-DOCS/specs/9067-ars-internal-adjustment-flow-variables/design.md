# 9067 指标内部调整单审批流程网关变量 技术设计

## 概述
在指标内部调整单提交审批时，向审批流程传递支出事项编码、调增合计金额、调减合计金额三个网关变量。

## 架构设计

### 整体架构
纯后端改动，通过关联查询 `t_scope_expenditure` 表获取 `mattersCode`，无需前端传递。

### 后端架构
- 所属微服务：budget-ms (18613)
- 涉及模块：Mapper XML、Service 层
- 修改文件：
  - `BudgetIndicatorAdjustmentDetailMapper.xml` - 新增查询方法
  - `BudgetIndicatorAdjustmentDetailMapper.java` - 新增接口方法
  - `BudgetIndicatorAdjustmentHeaderServiceImpl.java` - 修改 `buildFlowGatewayVariables` 方法

## 数据模型

### 表关系
```
t_budget_indicator_adjustment_detail (调整明细表)
  └── c_scope_id → t_scope_expenditure.c_id (开支范围表)
                      └── c_matters_code (支出预算事项编码)
```

### 关键字段
| 表名 | 字段 | 说明 |
|------|------|------|
| t_budget_indicator_adjustment_detail | c_scope_id | 开支范围ID |
| t_budget_indicator_adjustment_detail | c_adjust_type | 调整类型（1=调增，2=调减） |
| t_budget_indicator_adjustment_detail | n_adjust_amount | 调整金额 |
| t_scope_expenditure | c_id | 主键 |
| t_scope_expenditure | c_matters_code | 支出预算事项编码 |

## 代码修改设计

### 1. Mapper XML - 新增查询方法

**文件**：`BudgetIndicatorAdjustmentDetailMapper.xml`

**新增 SQL**：
```xml
<!-- 查询调整明细及支出预算事项编码（用于网关变量） -->
<select id="selectDetailWithMattersCodeByHeaderId"
        resultType="map">
    SELECT 
        biad.c_adjust_type as adjustType,
        biad.n_adjust_amount as adjustAmount,
        tse.c_matters_code as mattersCode
    FROM budget.t_budget_indicator_adjustment_detail biad
    LEFT JOIN budget.t_scope_expenditure tse ON biad.c_scope_id = tse.c_id
    WHERE biad.c_header_id = #{headerId}
      AND biad.c_deleted = '0'
</select>
```

### 2. Mapper 接口 - 新增方法

**文件**：`BudgetIndicatorAdjustmentDetailMapper.java`

```java
/**
 * 查询调整明细及支出预算事项编码（用于网关变量）
 * @param headerId 调整单头ID
 * @return 包含 adjustType, adjustAmount, mattersCode 的 Map 列表
 */
List<Map<String, Object>> selectDetailWithMattersCodeByHeaderId(@Param("headerId") String headerId);
```

### 3. Service 层 - 修改 buildFlowGatewayVariables 方法

**文件**：`BudgetIndicatorAdjustmentHeaderServiceImpl.java`

```java
/**
 * 构建流程网关变量
 * 通过关联查询 t_scope_expenditure 表获取 mattersCode
 */
private Map<String, Object> buildFlowGatewayVariables(String headerId) {
    Map<String, Object> variables = new HashMap<>();
    
    // 查询调整明细及支出预算事项编码
    List<Map<String, Object>> details = budgetIndicatorAdjustmentDetailMapper
            .selectDetailWithMattersCodeByHeaderId(headerId);
    
    if (CollUtil.isEmpty(details)) {
        variables.put("increaseMattersCodes", List.of());
        variables.put("decreaseMattersCodes", List.of());
        variables.put("increaseAmount", 0.0);
        variables.put("decreaseAmount", 0.0);
        return variables;
    }
    
    // 调增支出事项编码列表 (adjustType = "1")
    List<String> increaseMattersCodes = details.stream()
            .filter(detail -> "1".equals(detail.get("adjustType")))
            .map(detail -> (String) detail.get("mattersCode"))
            .filter(StrUtil::isNotBlank)
            .distinct()
            .toList();
    variables.put("increaseMattersCodes", increaseMattersCodes);
    
    // 调减支出事项编码列表 (adjustType = "2")
    List<String> decreaseMattersCodes = details.stream()
            .filter(detail -> "2".equals(detail.get("adjustType")))
            .map(detail -> (String) detail.get("mattersCode"))
            .filter(StrUtil::isNotBlank)
            .distinct()
            .toList();
    variables.put("decreaseMattersCodes", decreaseMattersCodes);
    
    // 调增合计金额 (adjustType = "1")
    BigDecimal increaseAmount = details.stream()
            .filter(detail -> "1".equals(detail.get("adjustType")))
            .map(detail -> {
                Object amount = detail.get("adjustAmount");
                if (amount instanceof BigDecimal) return (BigDecimal) amount;
                if (amount instanceof Number) return BigDecimal.valueOf(((Number) amount).doubleValue());
                return BigDecimal.ZERO;
            })
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    variables.put("increaseAmount", NumberUtil.round(increaseAmount, 2).doubleValue());
    
    // 调减合计金额 (adjustType = "2")
    BigDecimal decreaseAmount = details.stream()
            .filter(detail -> "2".equals(detail.get("adjustType")))
            .map(detail -> {
                Object amount = detail.get("adjustAmount");
                if (amount instanceof BigDecimal) return (BigDecimal) amount;
                if (amount instanceof Number) return BigDecimal.valueOf(((Number) amount).doubleValue());
                return BigDecimal.ZERO;
            })
            .reduce(BigDecimal.ZERO, BigDecimal::add);
    variables.put("decreaseAmount", NumberUtil.round(decreaseAmount, 2).doubleValue());
    
    return variables;
}
```

## 影响范围

### 后端
- 需要修改的现有文件：
  - `ars-budget/budget-ms/src/main/resources/mapper/budgetAdjustments/BudgetIndicatorAdjustmentDetailMapper.xml`
  - `ars-budget/budget-ms/src/main/java/com/dibcn/ars/budget/mapper/budgetAdjustments/BudgetIndicatorAdjustmentDetailMapper.java`
  - `ars-budget/budget-ms/src/main/java/com/dibcn/ars/budget/service/budgetAdjustments/impl/BudgetIndicatorAdjustmentHeaderServiceImpl.java`
- 需要新增的文件：无
- 需要更新的配置：无
- 需要执行的 SQL：无

### 前端
- 无需修改

## 网关变量说明

| 变量名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| increaseMattersCodes | List<String> | 调增支出事项编码列表（去重、过滤空值） | ["ZCSX-0001", "ZCSX-0002"] |
| decreaseMattersCodes | List<String> | 调减支出事项编码列表（去重、过滤空值） | ["ZCSX-0003", "ZCSX-0004"] |
| increaseAmount | Double | 调增合计金额（保留2位小数） | 10000.00 |
| decreaseAmount | Double | 调减合计金额（保留2位小数） | 10000.00 |

## 优点
1. 纯后端实现，无需前端配合
2. 无需数据库变更
3. 通过关联查询实时获取 mattersCode，数据准确性高
4. 实现简单，只需修改一个查询和一个方法
