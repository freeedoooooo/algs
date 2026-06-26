# 重构所有实体类继承BaseEntity 需求文档

> 编号：`0014` | 模块：`extract` | 服务：`dib-agent-service-extract` | 创建时间：2026-05-13
> 关联 Issue：无

---

## 背景

当前dib-agent-service-extract服务中的实体类存在以下问题：
1. **继承不一致**：部分实体类继承BaseEntity，部分没有继承
2. **字段名不统一**：BaseEntity使用`addUserId`/`addUserName`/`updateUserId`/`updateUserName`，而非继承实体使用`addBy`/`updateBy`
3. **存在冗余中间类**：CommonEntity和FormCommonEntity作为中间层存在，增加了复杂度
4. **数据库字段名不一致**：需要确保数据库字段名与BaseEntity中的字段名一致

这些问题导致代码维护困难，违反了宪法中的数据库规范。

## 目标用户

- 后端开发人员
- 数据库管理员
- 代码维护人员

## 功能描述

重构dib-agent-service-extract服务中的所有实体类和相关的数据模型，使其：
1. 所有实体类都继承BaseEntity
2. 移除实体类中重复的`addBy`、`addTime`、`updateBy`、`updateTime`字段
3. 统一使用BaseEntity中的字段名规范
4. 移除CommonEntity和FormCommonEntity中间类
5. 确保数据库字段名与BaseEntity中的字段名一致
6. 兼容model包下的数据模型，如果涉及这些字段名变更，也同步重构

## 所属模块

- 服务：`dib-agent-service-extract`（端口 `30001`）
- 模块：`entity`（实体层）和`model`（数据模型层）
- 业务域：`extract`（资料提取）
- 涉及文件/目录：
  - `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/`
  - 所有实体类文件（约26个）
  - `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/model/`
  - 相关的数据模型类（如`DocResp.java`、`EtlDocBO.java`等）
  - 相关的Converter类
  - 相关的Service类
  - 数据库表结构

## 核心业务规则

1. **继承规则**：所有实体类必须继承BaseEntity
2. **字段命名规则**：统一使用BaseEntity中的字段名：
   - `addUserId`（创建人账号）
   - `addUserName`（创建人姓名）
   - `addTime`（创建时间）
   - `updateUserId`（更新人账号）
   - `updateUserName`（更新人姓名）
   - `updateTime`（更新时间）
   - `delFlag`（删除标识）
   - `id`（主键）
3. **数据模型兼容规则**：所有相关的数据模型类（DTO/VO/Req/Resp/BO等）中的字段名也需要与BaseEntity保持一致
4. **数据库映射规则**：数据库表字段名必须与BaseEntity字段名一致（使用MyBatis-Plus的默认映射规则）
5. **数据库脚本规则**：生成数据库脚本时，对于相似字段尽量使用字段重命名（RENAME COLUMN）而不是删除后重新创建，以保留数据

## 输入参数

| 参数名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| 现有实体类 | Java类文件 | 代码库 | 需要重构的实体类文件 |
| 现有数据模型类 | Java类文件 | 代码库 | 需要兼容重构的数据模型文件 |
| 数据库表结构 | SQL表定义 | 数据库 | 需要调整字段名的数据库表 |

## 输出结果

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 重构后的实体类 | Java类文件 | 继承BaseEntity的实体类 |
| 更新后的数据模型类 | Java类文件 | 字段名与BaseEntity一致的数据模型类 |
| 数据库迁移脚本 | SQL脚本文件 | 使用字段重命名的数据库迁移脚本 |
| 更新后的数据库表 | SQL表结构 | 字段名与BaseEntity一致的数据库表 |
| 移除的中间类 | 无 | CommonEntity和FormCommonEntity被移除 |

## 用户故事

- 作为后端开发人员，我希望所有实体类都继承BaseEntity，以便统一管理公共字段
- 作为代码维护人员，我希望移除重复的字段定义，以便减少代码冗余和维护成本
- 作为数据库管理员，我希望数据库字段名与实体类字段名一致，以便减少映射错误

## 验收标准

- [ ] 所有26个实体类都继承BaseEntity
- [ ] 所有实体类中重复的`addBy`、`addTime`、`updateBy`、`updateTime`字段被移除
- [ ] 所有相关的数据模型类（如`DocResp.java`、`EtlDocBO.java`等）字段名与BaseEntity一致
- [ ] CommonEntity和FormCommonEntity类被移除
- [ ] 数据库表字段名与BaseEntity字段名一致
- [ ] 数据库迁移脚本使用字段重命名（RENAME COLUMN）而不是删除后重新创建
- [ ] 所有相关的Converter类正常工作
- [ ] 所有相关的Service类正常工作
- [ ] 编译通过，无编译错误
- [ ] 现有功能测试通过

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| 当实体类已经继承BaseEntity时 | 保持不变，只检查字段名一致性 |
| 当实体类有自定义的公共字段逻辑时 | 评估是否需要保留，或迁移到BaseEntity中 |
| 当数据模型类涉及字段名变更时 | 同步更新数据模型类中的字段名 |
| 当数据库字段名不一致时 | 优先使用字段重命名（RENAME COLUMN）而不是删除后重新创建 |
| 当数据库字段类型或长度需要调整时 | 使用ALTER COLUMN修改，避免数据丢失 |
| 当其他服务引用这些实体类时 | 需要评估影响范围，可能需要同步修改 |
| 当数据模型类被其他服务引用时 | 需要评估影响范围，可能需要同步修改 |

## 非功能需求

- **性能**：重构不应影响现有性能
- **可维护性**：代码更简洁，减少重复代码
- **安全性**：保持现有的安全控制不变
- **兼容性**：确保向后兼容，现有API接口不受影响

## 待确认问题

- [ ] 数据库表字段名修改是否需要数据迁移？如果需要，迁移策略是什么？
- [ ] 是否有其他服务或模块依赖这些实体类？影响范围如何？
- [ ] 是否有其他服务或模块依赖这些数据模型类？影响范围如何？
- [ ] 是否需要修改MyBatis-Plus的全局配置来适应字段名变化？
- [ ] 重构过程中是否需要暂停服务？
- [ ] 数据库字段重命名是否会影响现有索引、约束和外键关系？

---

**状态**：草稿


## 数据库脚本示例

### 字段重命名示例（推荐）
```sql
-- 将 add_by 重命名为 add_user_id
ALTER TABLE com_extract_doc RENAME COLUMN add_by TO add_user_id;

-- 将 update_by 重命名为 update_user_id  
ALTER TABLE com_extract_doc RENAME COLUMN update_by TO update_user_id;

-- 添加缺失的字段（如果不存在）
ALTER TABLE com_extract_doc ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_doc ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';
```

### 字段类型调整示例
```sql
-- 调整字段类型（如果需要）
ALTER TABLE com_extract_doc ALTER COLUMN add_time TYPE TIMESTAMP;
ALTER TABLE com_extract_doc ALTER COLUMN update_time TYPE TIMESTAMP;
```

### 不推荐的做法（会导致数据丢失）
```sql
-- 不推荐：删除字段后重新创建（会丢失数据）
ALTER TABLE com_extract_doc DROP COLUMN add_by;
ALTER TABLE com_extract_doc ADD COLUMN add_user_id VARCHAR(50) COMMENT '创建人账号';
```