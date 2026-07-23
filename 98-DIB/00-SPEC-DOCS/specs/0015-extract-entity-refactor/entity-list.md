# 需要重构的实体类列表

## 总计：22个实体类

### 1. extract模块（16个）
1. `ComExtractDocDelEntity.java` - 资料删除表
2. `ComExtractDocDirEntity.java` - 资料目录表
3. `ComExtractDocEntity.java` - 资料表（核心）
4. `ComExtractDocTypeBusEntity.java` - 资料类型业务关联表
5. `ComExtractDocTypeDirEntity.java` - 资料类型目录表
6. `ComExtractDocTypeEntity.java` - 资料类型表
7. `ComExtractDocTypeFilterEntity.java` - 资料类型过滤器表
8. `ComExtractDocTypeRelationEntity.java` - 资料类型关系表
9. `ComExtractDocTypeTemplateEntity.java` - 资料类型模板表（已继承BaseEntity）
10. `ComExtractRateBakEntity.java` - 提取率备份表
11. `ComExtractResultBakEntity.java` - 提取结果备份表
12. `ComExtractResultEntity.java` - 提取结果表
13. `ComExtractRuleColumnEntity.java` - 提取规则列表
14. `ComExtractRuleEntity.java` - 提取规则表
15. `ComExtractTableColumnEntity.java` - 提取表列表
16. `ComExtractTableEntity.java` - 提取表表

### 2. etl模块（4个）
17. `ComExtractEtlDocEntity.java` - ETL文档表（已继承BaseEntity）
18. `ComExtractEtlDocTableEntity.java` - ETL文档表关系表（已继承BaseEntity）
19. `ComExtractEtlTableColumnEntity.java` - ETL表列表（已继承BaseEntity）
20. `ComExtractEtlTableEntity.java` - ETL表表（已继承BaseEntity）

### 3. inventory模块（2个）
21. `InventoryDirEntity.java` - 清单目录表（已继承BaseEntity）
22. `InventoryEntity.java` - 清单表（已继承BaseEntity）

## 需要移除的中间类（2个）
1. `CommonEntity.java`
2. `FormCommonEntity.java`

## 需要更新的数据模型类（至少2个）
1. `DocResp.java` - 资料响应模型
2. `EtlDocBO.java` - ETL文档业务对象

## 状态说明
- ✅ 已继承BaseEntity：6个（etl模块4个 + inventory模块2个）
- 🔄 需要重构：16个（extract模块全部16个）
- 🗑️ 需要删除：2个（中间类）
- 📝 需要更新：2+个（数据模型类）