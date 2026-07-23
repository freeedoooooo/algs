# 提取模块Flag字段类型重构 - String → Boolean

**日期：** 2026-06-18  
**版本：** v1.0  
**状态：** ✅ 已完成  
**影响范围：** extract模块（资料提取相关功能）

---

## 📋 一、背景说明

### 1.1 问题描述

原系统中多个标识字段（Flag结尾的字段）使用 `String` 类型存储 `"0"` 和 `"1"` 字符串值，存在以下问题：

1. **类型不安全**：字符串容易出现拼写错误（如 `"01"`, `"1 "` 等）
2. **语义不清晰**：`"1"` 和 `"0"` 不如 `true/false` 直观
3. **性能损耗**：字符串比较比布尔比较效率低
4. **代码冗余**：需要频繁进行字符串到布尔的转换

### 1.2 优化目标

将所有Flag标识字段从 `String` 类型统一改为 `Boolean` 类型，提升代码质量和可维护性。

---

## 🗄️ 二、数据库层修改

### 2.1 涉及的表和字段

| 表名 | 字段名 | 原类型 | 新类型(MySQL) | 新类型(OpenGauss) | 业务含义 |
|------|--------|--------|---------------|-------------------|----------|
| com_extract_doc_type | doc_unique_flag | CHAR(1) | TINYINT(1) | SMALLINT | 是否控制上传唯一性 |
| com_extract_doc_type | extract_flag | CHAR(1) | TINYINT(1) | SMALLINT | 提取标识 |
| com_extract_doc_type | need_authorize_flag | CHAR(1) | TINYINT(1) | SMALLINT | 是否需要授权 |
| com_extract_doc_type | report_date_flag | CHAR(1) | TINYINT(1) | SMALLINT | 是否涉及报告期 |
| com_extract_doc_type | show_flag | CHAR(1) | TINYINT(1) | SMALLINT | 显示标识 |
| com_extract_doc_type | upload_flag | CHAR(1) | TINYINT(1) | SMALLINT | 是否需要上传 |
| com_extract_rule_column | necessary_flag | CHAR(1) | TINYINT(1) | SMALLINT | 是否必须提取 |
| com_extract_doc_type_dir | enable_flag | CHAR/INT | TINYINT(1) | SMALLINT | 是否激活 |
| com_extract_table_column | nullable_flag | INT | TINYINT(1) | SMALLINT | 是否可为空 |

### 2.2 SQL脚本文件

#### MySQL脚本
- **文件路径：** `docs-c1/01 产品部署/SQL脚本/2026-06-18-alter-extract-flag-mysql.sql`
- **特点：** 
  - 使用 `MODIFY COLUMN` 直接修改字段类型
  - MySQL自动进行数据类型转换
  - 兼容原有 `'0'` 和 `'1'` 字符串数据

#### OpenGauss脚本
- **文件路径：** `docs-c1/01 产品部署/SQL脚本/2026-06-18-alter-extract-flag-opengauss.sql`
- **特点：**
  - 使用 `ALTER COLUMN ... TYPE SMALLINT USING CASE WHEN` 显式转换
  - 包含完整的数据备份逻辑（第0部分）
  - 包含数据验证SQL（第5部分）
  - 包含数据恢复方案（第6部分，注释状态）
  - 更安全、更可控

### 2.3 数据兼容性

✅ **完全兼容**：两种数据库都能自动将原有的 `'0'` 和 `'1'` 字符串转换为数字 `0` 和 `1`

```sql
-- MySQL自动转换
'1' → 1
'0' → 0

-- OpenGauss显式转换（更安全）
USING CASE WHEN field = '1' OR field = 1 THEN 1 ELSE 0 END
```

---

## ☕ 三、后端Java代码修改

### 3.1 Entity层（实体类）

#### 修改的文件清单

| 文件路径 | 类名 | 修改字段数量 |
|---------|------|-------------|
| `dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/extract/ComExtractDocTypeEntity.java` | ComExtractDocTypeEntity | 6个字段 |
| `dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/extract/ComExtractRuleColumnEntity.java` | ComExtractRuleColumnEntity | 1个字段 |
| `dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/extract/ComExtractDocTypeDirEntity.java` | ComExtractDocTypeDirEntity | 1个字段 |
| `dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/extract/ComExtractTableColumnEntity.java` | ComExtractTableColumnEntity | 1个字段 |

#### 字段修改详情

**ComExtractDocTypeEntity.java**
```java
// 修改前
private String docUniqueFlag;
private String extractFlag;
private String needAuthorizeFlag;
private String reportDateFlag;
private String showFlag;
private String uploadFlag;

// 修改后
private Boolean docUniqueFlag;
private Boolean extractFlag;
private Boolean needAuthorizeFlag;
private Boolean reportDateFlag;
private Boolean showFlag;
private Boolean uploadFlag;
```

**ComExtractRuleColumnEntity.java**
```java
// 修改前
private String necessaryFlag;

// 修改后
private Boolean necessaryFlag;
```

**ComExtractDocTypeDirEntity.java**
```java
// 修改前
private String enableFlag; // 或 Integer

// 修改后
private Boolean enableFlag;
```

**ComExtractTableColumnEntity.java**
```java
// 修改前
private Integer nullableFlag;

// 修改后
private Boolean nullableFlag;
```

---

### 3.2 Model层（请求/响应对象）

#### Req（请求对象）

**文件：** `DocTypePageReq.java`

```java
// 修改前
private String showFlag;
private String extractFlag;
private String reportDateFlag;
private String uploadFlag;
private String needAuthorizeFlag;
private String docUniqueFlag;

// 修改后
private Boolean showFlag;
private Boolean extractFlag;
private Boolean reportDateFlag;
private Boolean uploadFlag;
private Boolean needAuthorizeFlag;
private Boolean docUniqueFlag;
```

#### Resp（响应对象）

**文件：** `DocTypeOfNotUploadResp.java`

```java
// 修改前
private String extractFlag;
private String showFlag;
private String reportDateFlag;
private String uploadFlag;

// 修改后
private Boolean extractFlag;
private Boolean showFlag;
private Boolean reportDateFlag;
private Boolean uploadFlag;
```

**其他响应对象：**
- `DocClassifyResp.java` - reportDateFlag: String → Boolean
- `DocTypeTemplateResp.java` - enableFlag: 已是Boolean（无需修改）

---

### 3.3 Converter层（MapStruct转换器）

#### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `DocTypeDirEntityConverter.java` | constant值从 `"0"` 改为 `false` |
| `ExtractRuleColumnEntityConverter.java` | necessaryFlag赋值逻辑改为 `Boolean.TRUE.equals()` |
| `ExtractRuleColumnRespConverter.java` | 表达式调整为Boolean比较 |
| `ComExtractTableColumnEntityConverter.java` | nullableFlag直接使用Boolean值 |

#### 示例代码

```java
// 修改前
@Mapping(target = "enableFlag", constant = "0")

// 修改后
@Mapping(target = "enableFlag", constant = "false")
```

```java
// 修改前
.necessaryFlag(StringUtils.isNotBlank(entity.getNecessaryFlag()) ? entity.getNecessaryFlag() : "0")

// 修改后
.necessaryFlag(Boolean.TRUE.equals(entity.getNecessaryFlag()))
```

---

### 3.4 枚举类移除

#### 已删除的枚举类

| 枚举类 | 原用途 | 替换方式 |
|--------|--------|---------|
| `EnableFlagEnum` | 启用/禁用标识 | 直接使用 `Boolean.TRUE/FALSE` |
| `ExtractFlagEnum` | 提取标识 | 直接使用 `Boolean.TRUE/FALSE` |

#### 替换示例

```java
// 修改前
if (EnableFlagEnum.ENABLED.getCode().equals(entity.getEnableFlag())) {
    // ...
}

// 修改后
if (Boolean.TRUE.equals(entity.getEnableFlag())) {
    // ...
}
```

---

## 💻 四、前端Vue代码修改

### 4.1 TypeScript类型定义

**文件：** `c1-app/apps/app-report/src/types/index.ts`

```typescript
// 修改前
export interface FileUpload {
  // ...
  reportDateFlag?: string;
}

// 修改后
export interface FileUpload {
  // ...
  reportDateFlag?: boolean;
}
```

---

### 4.2 表单配置文件

#### 文件1：baseInfoFields.ts

**路径：** `c1-app/apps/app-report/src/views/settings/DocsType/components/AutoCreateDocType/config/baseInfoFields.ts`

**修改内容（共6个字段配置）：**

```typescript
// 修改前
{
  label: '是否提取',
  prop: 'extractFlag',
  widget: 'radio',
  props: {
    options: [
      { label: '是', value: '1' },
      { label: '否', value: '0' },
    ],
  },
}

// 修改后
{
  label: '是否提取',
  prop: 'extractFlag',
  widget: 'radio',
  props: {
    options: [
      { label: '是', value: true },
      { label: '否', value: false },
    ],
  },
}
```

**showRule表达式修改：**
```typescript
// 修改前
showRule: `model.showFlag == '1'`

// 修改后
showRule: `model.showFlag === true`
```

**涉及字段：**
- extractFlag
- showFlag
- uploadFlag（含showRule）
- reportDateFlag（含showRule）
- docUniqueFlag

---

#### 文件2：formFields.ts

**路径：** `c1-app/apps/app-report/src/views/settings/DocsType/components/DocsConfig/config/formFields.ts`

**修改内容（共7个字段配置）：**

与baseInfoFields.ts类似，额外包含：
- needAuthorizeFlag

**涉及字段：**
- extractFlag
- showFlag
- uploadFlag（含showRule）
- reportDateFlag（含showRule）
- needAuthorizeFlag
- docUniqueFlag

---

### 4.3 表格配置和表达式

**文件：** `dialogSchemaConfig.ts`

**路径：** `c1-app/apps/app-report/src/views/reportTabs/components/DocBench/config/dialogSchemaConfig.ts`

**修改内容（共5处）：**

```typescript
// 1. prefixComponentShowRule表达式
// 修改前
prefixComponentShowRule: `!authBook?.attId && row.needAuthorizeFlag == ${EnableState.Enabled}`

// 修改后
prefixComponentShowRule: `!authBook?.attId && row.needAuthorizeFlag === true`

// 2. fieldMap函数
// 修改前
fieldMap: ({ row }) => (row.needAuthorizeFlag == '1' ? '是' : '否')

// 修改后
fieldMap: ({ row }) => (row.needAuthorizeFlag === true ? '是' : '否')

// 3. 请求参数
// 修改前
params: {
  showFlag: '1',
  // ...
}

// 修改后
params: {
  showFlag: true,
  // ...
}

// 4. injectData表达式
// 修改前
{
  express: 'data.reportDateFlag == "1"',
  // ...
}

// 修改后
{
  express: 'data.reportDateFlag === true',
  // ...
}

// 5. forbidRowSelected rule
// 修改前
rule: `row.needAuthorizeFlag == '1'`

// 修改后
rule: `row.needAuthorizeFlag === true`
```

---

## 📊 五、修改统计

### 5.1 总体统计

| 层级 | 修改文件数 | 修改项数 | 涉及字段数 |
|------|-----------|---------|-----------|
| 数据库 | 2个SQL脚本 | 9个字段 | 9 |
| Entity层 | 4个文件 | 9个字段 | 9 |
| Model层 | 2个文件 | 10个字段 | 7 |
| Converter层 | 4个文件 | 4处逻辑 | - |
| 枚举类 | 2个文件（已删除） | - | - |
| 前端TypeScript | 1个文件 | 1个类型 | 1 |
| 前端表单配置 | 2个文件 | 13个字段配置 | 7 |
| 前端表达式 | 1个文件 | 5处表达式 | 2 |
| **合计** | **16个文件** | **51处修改** | **9个字段** |

### 5.2 字段映射关系

| 字段名 | 原值 | 新值 | 业务含义 |
|--------|------|------|---------|
| - | `"1"` | `true` | 是/启用/显示/提取 |
| - | `"0"` | `false` | 否/禁用/隐藏/不提取 |
| - | `""` (空) | `false` | 默认否 |
| - | `null` | `false` | 默认否 |

---

## ✅ 六、测试检查点

### 6.1 后端测试

- [ ] 资料类型新增接口 - Flag字段正确保存为Boolean
- [ ] 资料类型编辑接口 - Flag字段正确更新
- [ ] 资料类型分页查询 - Flag字段筛选条件正常工作
- [ ] 资料类型详情查询 - Flag字段正确返回Boolean值
- [ ] MapStruct转换器 - 所有转换逻辑正常
- [ ] 数据库迁移脚本 - 在MySQL和OpenGauss上执行成功
- [ ] 历史数据转换 - 原有 `'0'/'1'` 数据正确转换为 `0/1`

### 6.2 前端测试

- [ ] 资料类型新增表单 - Radio控件绑定正常
- [ ] 资料类型编辑表单 - 数据回显正确
- [ ] 表单提交 - Boolean值正确传递给后端
- [ ] 条件显示逻辑 - showRule表达式工作正常
- [ ] 文档工作台 - 列表展示和筛选正常
- [ ] 报告期条件显示 - 依赖showFlag的逻辑正常
- [ ] 授权书字段显示 - 依赖needAuthorizeFlag的逻辑正常
- [ ] TypeScript编译 - 无类型错误

### 6.3 集成测试

- [ ] 前后端联调 - 数据类型匹配
- [ ] API接口文档 - Swagger/Knife4j显示正确
- [ ] 浏览器控制台 - 无类型警告或错误
- [ ] 不同环境测试 - dev/test/prod环境均正常

---

## ⚠️ 七、注意事项

### 7.1 部署顺序

1. **先执行数据库脚本**
   - MySQL: 执行 `2026-06-18-alter-extract-flag-mysql.sql`
   - OpenGauss: 执行 `2026-06-18-alter-extract-flag-opengauss.sql`
   
2. **再部署后端代码**
   - 确保后端服务重启完成
   
3. **最后部署前端代码**
   - 清除浏览器缓存
   - 重新构建前端资源

### 7.2 回滚方案

如果出现问题，可以按以下顺序回滚：

1. **前端回滚**：恢复到修改前的版本
2. **后端回滚**：恢复到修改前的版本
3. **数据库回滚**：
   - OpenGauss：执行脚本第6部分的恢复SQL（需取消注释）
   - MySQL：从备份表恢复数据

### 7.3 兼容性说明

- ✅ **向后兼容**：数据库层面完全兼容原有数据
- ✅ **API兼容**：JSON序列化时Boolean会自动转为 `true/false`
- ⚠️ **前端适配**：必须同步更新前端代码，否则会出现类型不匹配

### 7.4 常见问题

**Q1: 为什么OpenGauss脚本比MySQL复杂？**  
A: OpenGauss使用显式的 `USING` 子句进行数据转换，更加安全和可控，避免隐式转换可能带来的问题。

**Q2: 为什么要移除枚举类？**  
A: 对于只有两个值的标识字段，直接使用Boolean更简洁，减少不必要的抽象层。

**Q3: 前端为什么要用 `===` 而不是 `==`？**  
A: 严格相等运算符避免类型转换，提高代码安全性和可读性。

---

## 📝 八、相关文件索引

### 8.1 数据库脚本
- `docs-c1/01 产品部署/SQL脚本/2026-06-18-alter-extract-flag-mysql.sql`
- `docs-c1/01 产品部署/SQL脚本/2026-06-18-alter-extract-flag-opengauss.sql`

### 8.2 后端代码
- `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/entity/extract/`
- `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/model/extract/`
- `dib-agent-service-extract/dib-agent-service-extract-web/src/main/java/com/dib/agent/extract/web/converter/extract/`

### 8.3 前端代码
- `c1-app/apps/app-report/src/types/index.ts`
- `c1-app/apps/app-report/src/views/settings/DocsType/components/AutoCreateDocType/config/baseInfoFields.ts`
- `c1-app/apps/app-report/src/views/settings/DocsType/components/DocsConfig/config/formFields.ts`
- `c1-app/apps/app-report/src/views/reportTabs/components/DocBench/config/dialogSchemaConfig.ts`

---

## 🔗 九、相关文档

- [数据库设计规范](../98 架构设计/数据库设计规范.md)
- [前端开发规范](../00 AI-DOCS/frontend-development-guide.md)
- [API接口文档](../../dib-agent-service-extract/API文档.md)

---

**文档维护者：** AI Assistant  
**最后更新：** 2026-06-18  
**审核状态：** 待审核
