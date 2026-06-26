# 重构所有实体类继承BaseEntity 技术设计

> 编号：`0014` | 模块：`extract` | 服务：`dib-agent-service-extract` | 创建时间：2026-05-13
> 关联需求：`requirements.md` | 关联 Issue：无

---

## 概述

通过系统性的代码重构，统一dib-agent-service-extract服务中所有实体类的继承结构，使其都继承BaseEntity，移除重复字段定义，统一字段命名规范，并同步更新相关的数据模型类和数据库表结构。

---

## 架构设计

### 整体架构

```
代码重构流程：
1. 分析现有实体类 → 2. 修改继承关系 → 3. 移除重复字段 → 4. 统一字段名 → 
5. 更新数据模型类 → 6. 移除中间类 → 7. 生成数据库迁移脚本 → 8. 验证和测试
```

### 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 修改 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/extract/*.java` | extract模块实体类（约16个） |
| 修改 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/etl/*.java` | etl模块实体类（4个） |
| 修改 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/inventory/*.java` | inventory模块实体类（2个） |
| 删除 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/CommonEntity.java` | 移除中间类 |
| 删除 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/FormCommonEntity.java` | 移除中间类 |
| 修改 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/model/extract/resp/DocResp.java` | 更新数据模型字段名 |
| 修改 | `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/model/etl/bo/EtlDocBO.java` | 更新数据模型字段名 |
| 新增 | `docs-c1/00 AI-DOCS/specs/0014-extract-entity-refactor/scripts/V0014__entity_refactor.sql` | 数据库迁移脚本 |

---

## 数据模型

### 输入

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| 现有实体类 | Java类文件 | 代码库 | 22个需要重构的实体类 |
| 现有数据模型类 | Java类文件 | 代码库 | 需要同步更新的数据模型类 |
| 数据库表结构 | SQL表定义 | 数据库 | 需要调整字段名的数据库表 |

### 输出

| 字段名 | 类型 | 说明 |
|--------|------|------|
| 重构后的实体类 | Java类文件 | 继承BaseEntity的实体类 |
| 更新后的数据模型类 | Java类文件 | 字段名与BaseEntity一致的数据模型类 |
| 数据库迁移脚本 | SQL脚本文件 | 使用字段重命名的数据库迁移脚本 |

### 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| `com_extract_doc` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_doc_dir` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_doc_type` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_doc_type_dir` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_doc_type_relation` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_rule` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_rule_column` | 字段重命名 | `add_by`→`add_user_id`, `update_by`→`update_user_id`, 添加`add_user_name`和`update_user_name` |
| `com_extract_table` | 字段重命名 | `add_by`→`add_user_id`, 添加`add_user_name` |
| `com_extract_table_column` | 字段重命名 | `add_by`→`add_user_id`, 添加`add_user_name` |
| 其他相关表 | 字段检查 | 确保所有表都有BaseEntity要求的8个基础字段 |

---

## 核心逻辑设计

### 主流程

```
1. 分析阶段：
   - 识别所有需要重构的实体类（22个）
   - 识别已经继承BaseEntity的实体类
   - 识别需要更新的数据模型类
   - 分析数据库表结构差异

2. 代码重构阶段：
   - 为每个实体类添加`extends BaseEntity`
   - 移除重复的`addBy`、`addTime`、`updateBy`、`updateTime`字段
   - 更新数据模型类中的字段名
   - 移除CommonEntity和FormCommonEntity

3. 数据库迁移阶段：
   - 生成数据库迁移脚本
   - 使用RENAME COLUMN进行字段重命名
   - 添加缺失的字段

4. 验证测试阶段：
   - 编译验证
   - 功能测试
   - 数据库连接测试
```

### 关键技术点

1. **继承关系修改**：
   - 在类声明中添加`extends BaseEntity`
   - 移除`implements Serializable`（BaseEntity已经实现）
   - 移除重复的`serialVersionUID`定义

2. **字段映射关系**：
   ```
   旧字段 → 新字段
   ---------------
   addBy → addUserId
   addTime → addTime（保持不变，但使用BaseEntity中的定义）
   updateBy → updateUserId
   updateTime → updateTime（保持不变，但使用BaseEntity中的定义）
   ```

3. **数据库字段重命名策略**：
   - 优先使用`RENAME COLUMN`保留数据
   - 对于缺失的字段使用`ADD COLUMN IF NOT EXISTS`
   - 对于类型不一致的字段使用`ALTER COLUMN TYPE`

4. **数据模型类更新**：
   - `DocResp.java`：`addBy`→`addUserId`, `updateBy`→`updateUserId`, 添加`addUserName`和`updateUserName`
   - `EtlDocBO.java`：已经使用`addUserId`和`addUserName`，保持现状

---

## 数据库变更

```sql
-- 文件：V0014__entity_refactor.sql
-- 描述：重构实体类继承BaseEntity的数据库迁移脚本

-- 1. com_extract_doc 表字段重命名和补充
ALTER TABLE com_extract_doc RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_doc ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 2. com_extract_doc_dir 表字段重命名和补充
ALTER TABLE com_extract_doc_dir RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_dir RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_dir ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_doc_dir ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 3. com_extract_doc_type 表字段重命名和补充
ALTER TABLE com_extract_doc_type RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_type ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_doc_type ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 4. com_extract_doc_type_dir 表字段重命名和补充
ALTER TABLE com_extract_doc_type_dir RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type_dir RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_type_dir ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_doc_type_dir ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 5. com_extract_doc_type_relation 表字段重命名和补充
ALTER TABLE com_extract_doc_type_relation RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_doc_type_relation RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_doc_type_relation ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_doc_type_relation ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 6. com_extract_rule 表字段重命名和补充
ALTER TABLE com_extract_rule RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_rule RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_rule ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_rule ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 7. com_extract_rule_column 表字段重命名和补充
ALTER TABLE com_extract_rule_column RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_rule_column RENAME COLUMN update_by TO update_user_id;
ALTER TABLE com_extract_rule_column ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';
ALTER TABLE com_extract_rule_column ADD COLUMN IF NOT EXISTS update_user_name VARCHAR(100) COMMENT '更新人姓名';

-- 8. com_extract_table 表字段重命名和补充
ALTER TABLE com_extract_table RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_table ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';

-- 9. com_extract_table_column 表字段重命名和补充
ALTER TABLE com_extract_table_column RENAME COLUMN add_by TO add_user_id;
ALTER TABLE com_extract_table_column ADD COLUMN IF NOT EXISTS add_user_name VARCHAR(100) COMMENT '创建人姓名';

-- 10. 检查其他表是否包含BaseEntity要求的8个基础字段
-- 注意：需要根据实际表结构进行调整
```

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| 实体类编译错误 | 检查import语句和字段引用 | "无法解析符号addBy"等 |
| 数据库字段重命名失败 | 检查字段是否存在，使用IF EXISTS | "列不存在" |
| 数据模型类字段不匹配 | 更新Converter类中的映射关系 | "字段类型不匹配" |
| 数据库连接失败 | 检查数据库配置和权限 | "连接被拒绝" |

---

## 影响范围

### 新增文件
- `docs-c1/00 AI-DOCS/specs/0014-extract-entity-refactor/scripts/V0014__entity_refactor.sql` - 数据库迁移脚本

### 修改文件
- **实体类（22个）**：
  - `ComExtractDocEntity.java` - 添加继承，移除重复字段
  - `ComExtractDocDirEntity.java` - 添加继承，移除重复字段
  - `ComExtractDocTypeEntity.java` - 添加继承，移除重复字段
  - `ComExtractDocTypeDirEntity.java` - 添加继承，移除重复字段
  - `ComExtractDocTypeRelationEntity.java` - 添加继承，移除重复字段
  - `ComExtractRuleEntity.java` - 添加继承，移除重复字段
  - `ComExtractRuleColumnEntity.java` - 添加继承，移除重复字段
  - `ComExtractTableEntity.java` - 添加继承，移除重复字段
  - `ComExtractTableColumnEntity.java` - 添加继承，移除重复字段
  - 其他13个实体类类似修改

- **数据模型类（至少2个）**：
  - `DocResp.java` - 更新字段名：`addBy`→`addUserId`, `updateBy`→`updateUserId`, 添加`addUserName`和`updateUserName`
  - `EtlDocBO.java` - 保持现状（已经使用正确字段名）

- **中间类（2个）**：
  - `CommonEntity.java` - 删除文件
  - `FormCommonEntity.java` - 删除文件

### 无需修改
- 已经继承BaseEntity的实体类（如`ComExtractEtlDocEntity.java`等）
- BaseEntity类本身
- 不涉及字段名变更的其他数据模型类

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 数据库字段重命名影响现有数据 | 数据丢失或损坏 | 使用RENAME COLUMN而不是DROP/ADD，先备份数据 |
| 编译错误导致服务不可用 | 服务启动失败 | 分批次修改，每次修改后立即编译验证 |
| 字段名变更影响其他服务 | 接口调用失败 | 评估影响范围，必要时同步修改其他服务 |
| 数据库迁移脚本执行失败 | 数据库结构不一致 | 提供回滚脚本，分步骤执行 |
| 索引和约束受影响 | 查询性能下降 | 检查并更新相关索引和约束定义 |

---

## 实施建议

1. **分阶段实施**：
   - 第一阶段：修改实体类继承关系
   - 第二阶段：更新数据模型类
   - 第三阶段：执行数据库迁移
   - 第四阶段：全面测试

2. **备份策略**：
   - 代码备份：使用git分支进行修改
   - 数据备份：执行数据库迁移前备份相关表

3. **测试策略**：
   - 单元测试：验证每个实体类的修改
   - 集成测试：验证数据库连接和CRUD操作
   - 回归测试：确保现有功能不受影响

4. **回滚方案**：
   - 代码回滚：使用git revert
   - 数据库回滚：提供反向迁移脚本

---

**状态**：草稿