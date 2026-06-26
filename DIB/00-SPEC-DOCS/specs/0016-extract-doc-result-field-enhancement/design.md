# 0016-extract-doc-result-field-enhancement 技术设计

> 编号：`0016` | 模块：`extract` | 服务：`dib-agent-service-extract` | 创建时间：2026-05-26
> 关联需求：`requirements.md`

---

## 概述

本技术方案通过新增数据库字段和枚举类，实现双路径资料转换与提取功能，支持 SmartOS 和传统路径两种转换方式，并根据提取成功率择优入库。

---

## 架构设计

### 整体架构

```
ComExtractDocAggregate.extractedOneDoc()
    ↓
[双路径转换]
    ├─ 路径A: SmartOS转换 (os_txt_att_id)
    │   ├─ 判断 os_txt_att_id 是否存在
    │   ├─ 不存在 → SmartOSConverterFacade.convert()
    │   ├─ 更新 os_convert_state, os_convert_duration
    │   └─ 上传MDM获取 os_txt_att_id
    │
    └─ 路径B: 传统转换 (txt_att_id)
        ├─ 判断 txt_att_id 是否存在
        ├─ 不存在 → 对应转换器.convert()
        ├─ 更新 convert_state, convert_duration
        └─ 上传MDM获取 txt_att_id
    ↓
[分别提取]
    ├─ 路径A提取 → 计算成功率A
    └─ 路径B提取 → 计算成功率B
    ↓
[择优入库]
    ├─ 比较成功率A vs 成功率B
    ├─ 选择高成功率结果入库
    └─ 设置 extract_source (OS/C1)
```

### 涉及文件

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| 新增 | `config/enums/ExtractSourceEnum.java` | 提取来源枚举类 |
| 修改 | `entity/extract/ComExtractDocEntity.java` | 新增3个字段 |
| 修改 | `entity/extract/ComExtractResultEntity.java` | 新增1个字段 |
| 修改 | `entity/extract/ComExtractResultBakEntity.java` | 继承父类字段 |
| 修改 | `aggregate/extract/ComExtractDocAggregate.java` | 实现双路径转换与择优逻辑 |
| 修改 | `resources/mapper/extract/ComExtractDocMapper.xml` | 新增字段SQL映射 |
| 修改 | `resources/mapper/extract/ComExtractResultMapper.xml` | 新增字段SQL映射 |
| 新增 | `scripts/V1.0.0__add_extract_fields.sql` | 数据库迁移脚本 |

---

## 数据模型

### 输入

| 参数/字段 | 类型 | 来源 | 说明 |
|----------|------|------|------|
| docId | Long | 方法参数 | 资料ID |
| account | String | 方法参数 | 操作用户账号 |

### 输出

无直接输出，为内部业务逻辑优化。

### 涉及数据库表

| 表名 | 操作 | 说明 |
|------|------|------|
| com_extract_doc | ALTER TABLE ADD COLUMN | 新增 os_txt_att_id, os_convert_state, os_convert_duration |
| com_extract_result | ALTER TABLE ADD COLUMN | 新增 extract_source |
| com_extract_result_bak | ALTER TABLE ADD COLUMN | 新增 extract_source |

---

## 接口设计

### API 列表

本次变更不涉及新接口，仅优化现有提取逻辑。

**受影响接口**：
- `POST /api/extract/doc/extract` - 单资料提取（内部逻辑优化）

---

## 核心逻辑设计

### 主流程

```
1. 接收提取请求 (docId, account)
2. 查询资料实体 ComExtractDocEntity
3. 初始化提取结果记录
4. 【路径A】SmartOS转换流程：
   4.1 判断 os_txt_att_id 是否存在
   4.2 若不存在：
       - 更新 os_convert_state = 'I'
       - 调用 SmartOSConverterFacade.convert(attId)
       - 计算耗时 duration
       - 成功：上传MDM → 获取 os_txt_att_id → 更新状态='Y'
       - 失败：更新状态='F'
       - 更新 os_convert_duration
   4.3 从 MDM 下载 txtBytesA
5. 【路径B】传统转换流程：
   5.1 判断 txt_att_id 是否存在
   5.2 若不存在：
       - 更新 convert_state = 'I'
       - 根据文档类型调用对应转换器
       - 计算耗时 duration
       - 成功：上传MDM → 获取 txt_att_id → 更新状态='Y'
       - 失败：更新状态='F'
       - 更新 convert_duration
   5.3 从 MDM 下载 txtBytesB
6. 【分别提取】
   6.1 使用 txtBytesA 执行要素提取 → 得到结果A、成功率A
   6.2 使用 txtBytesB 执行要素提取 → 得到结果B、成功率B
7. 【择优入库】
   7.1 比较成功率A >= 成功率B？
   7.2 是：入库结果A，设置 extract_source = ExtractSourceEnum.OS
   7.3 否：入库结果B，设置 extract_source = ExtractSourceEnum.C1
8. 更新资料状态 (refreshDocState)
9. 返回提取结果
```

### 关键技术点

#### 1. ExtractSourceEnum 枚举类

```java
package com.dib.agent.extract.web.config.enums;

import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 提取来源枚举
 *
 * @author AI Assistant
 * @since 2026-05-26
 */
@Getter
@AllArgsConstructor
public enum ExtractSourceEnum {
    
    /**
     * 未知/未设置
     */
    NONE("NONE", "未知"),
    
    /**
     * SmartOS提取
     */
    OS("OS", "SmartOS提取"),
    
    /**
     * 传统路径
     */
    C1("C1", "传统路径");
    
    private final String code;
    private final String desc;
    
    /**
     * 根据code获取枚举
     */
    public static ExtractSourceEnum fromCode(String code) {
        if (code == null) {
            return NONE;
        }
        for (ExtractSourceEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return NONE;
    }
}
```

#### 2. Entity 字段映射

**ComExtractDocEntity 新增字段**：
```java
/**
 * 原始文本附件ID (SmartOS转换生成)
 */
private Long osTxtAttId;

/**
 * SmartOS转换状态：U|I|F|Y:待转换|转换中|转换失败|转换成功
 */
private String osConvertState;

/**
 * SmartOS转换耗时（秒）
 */
private Integer osConvertDuration;
```

**ComExtractResultEntity 新增字段**：
```java
@Schema(description = "提取来源")
private ExtractSourceEnum extractSource;
```

#### 3. 双路径转换实现

在 `ComExtractDocAggregate` 中新增私有方法：

```java
/**
 * SmartOS路径转换并获取txtBytes
 */
private byte[] convertBySmartOS(ComExtractDocEntity docEntity, String account) {
    // 判断是否已有 os_txt_att_id
    if (docEntity.getOsTxtAttId() != null && docEntity.getOsTxtAttId() > 0) {
        // 直接下载
        return downloadFromMdm(docEntity.getOsTxtAttId());
    }
    
    // 需要转换
    docService.updateOsConvertState(docEntity.getId(), "I");
    long startTime = System.currentTimeMillis();
    
    try {
        ConvertResult result = smartOSConverterFacade.convert(docEntity.getAttId());
        long duration = (System.currentTimeMillis() - startTime) / 1000;
        
        if (result.isSuccess()) {
            // 上传到MDM
            Long osTxtAttId = mdmService.upload(result.getTxtBytes(), account);
            docService.update(docEntity.getId(), "os_txt_att_id", osTxtAttId);
            docService.updateOsConvertState(docEntity.getId(), "Y");
            docService.update(docEntity.getId(), "os_convert_duration", duration);
            return result.getTxtBytes();
        } else {
            docService.updateOsConvertState(docEntity.getId(), "F");
            docService.update(docEntity.getId(), "os_convert_duration", duration);
            throw new BizValidateException("SmartOS转换失败: " + result.getErrorMessage());
        }
    } catch (Exception e) {
        long duration = (System.currentTimeMillis() - startTime) / 1000;
        docService.updateOsConvertState(docEntity.getId(), "F");
        docService.update(docEntity.getId(), "os_convert_duration", duration);
        log.error("SmartOS转换异常", e);
        throw e;
    }
}

/**
 * 传统路径转换并获取txtBytes
 */
private byte[] convertByTraditional(ComExtractDocEntity docEntity, String account) {
    // 类似逻辑，调用原有转换逻辑
    // ...
}
```

#### 4. 成功率计算（复用现有方法）

**复用方法**：`ComExtractDocAggregate.calcElementCompletionRate()`

**方法签名**：
```java
private double calcElementCompletionRate(String tableName, List<Map<String, Object>> dataMapList, TableCheckResult checkResult)
```

**计算逻辑**：
```java
private double calcElementCompletionRate(String tableName, List<Map<String, Object>> dataMapList, TableCheckResult checkResult) {
    if (!ExtractConstant.VERIFY_STATE_OF_NOT_PASS.contains(checkResult.getVerifyState())) {
        // 如果校验通过，完成率为 100
        return 100;
    }

    List<String> busColumnNames = tableColumnService.listColumnNames(tableName, true);

    // 计算总单元格数
    int totalCellCount = dataMapList.parallelStream()
        .mapToInt(map -> (int) busColumnNames.stream().filter(x -> null != map.get(x)).count())
        .sum();

    // 总单元格数减去错误数量，得到正确单元格数
    double completionRate = totalCellCount == 0 ? 0 : 
        Math.max(0, totalCellCount - checkResult.computeFailTraceDataCount()) * 100.00 / totalCellCount;

    return completionRate;
}
```

**使用方式**：
```java
// 在 extractedOneDoc 方法中
byte[] txtBytesA = convertBySmartOS(docEntity, account);
byte[] txtBytesB = convertByTraditional(docEntity, account);

// 执行提取，获取结果和校验结果
ReaderResult resultA = extractWithTxtBytes(txtBytesA, docEntity, tableListOfExtracting, account);
TableCheckResult checkResultA = validateExtractResult(resultA);

ReaderResult resultB = extractWithTxtBytes(txtBytesB, docEntity, tableListOfExtracting, account);
TableCheckResult checkResultB = validateExtractResult(resultB);

// 复用现有方法计算成功率
double successRateA = calcElementCompletionRate(tableName, resultA.getDataMapList(), checkResultA);
double successRateB = calcElementCompletionRate(tableName, resultB.getDataMapList(), checkResultB);

// 择优入库
if (successRateA >= successRateB) {
    saveExtractResult(resultA, ExtractSourceEnum.OS);
    log.info("【择优入库】选择SmartOS路径，成功率A={}%, 成功率B={}%", successRateA, successRateB);
} else {
    saveExtractResult(resultB, ExtractSourceEnum.C1);
    log.info("【择优入库】选择传统路径，成功率A={}%, 成功率B={}%", successRateA, successRateB);
}
```

**优势**：
1. 复用现有成熟逻辑，减少重复代码
2. 保证成功率计算的一致性
3. 考虑了校验状态和业务字段
4. 已处理边界情况（如总单元格数为0）

#### 5. 择优入库逻辑

```java
// 在 extractedOneDoc 方法中
byte[] txtBytesA = convertBySmartOS(docEntity, account);
byte[] txtBytesB = convertByTraditional(docEntity, account);

ReaderResult resultA = extractWithTxtBytes(txtBytesA, docEntity, tableListOfExtracting, account);
ReaderResult resultB = extractWithTxtBytes(txtBytesB, docEntity, tableListOfExtracting, account);

double successRateA = calculateSuccessRate(resultA);
double successRateB = calculateSuccessRate(resultB);

// 择优入库
if (successRateA >= successRateB) {
    saveExtractResult(resultA, ExtractSourceEnum.OS);
    log.info("【择优入库】选择SmartOS路径，成功率A={}%, 成功率B={}% ", successRateA, successRateB);
} else {
    saveExtractResult(resultB, ExtractSourceEnum.C1);
    log.info("【择优入库】选择传统路径，成功率A={}%, 成功率B={}% ", successRateA, successRateB);
}
```

---

## 数据库变更

### 1. com_extract_doc 表新增字段

```sql
-- 新增 SmartOS 相关字段
ALTER TABLE com_extract_doc 
ADD COLUMN os_txt_att_id BIGINT COMMENT '原始文本附件ID(SmartOS转换生成)',
ADD COLUMN os_convert_state VARCHAR(2) DEFAULT 'U' COMMENT 'SmartOS转换状态:U|I|F|Y',
ADD COLUMN os_convert_duration INT DEFAULT 0 COMMENT 'SmartOS转换耗时(秒)';

-- 添加索引（可选，根据查询需求决定）
-- CREATE INDEX idx_os_convert_state ON com_extract_doc(os_convert_state);
```

### 2. com_extract_result 表新增字段

```sql
-- 新增提取来源字段
ALTER TABLE com_extract_result 
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'NONE' COMMENT '提取来源:NONE|OS|C1';

-- 添加索引（如果经常按来源统计）
CREATE INDEX idx_extract_source ON com_extract_result(extract_source);
```

### 3. com_extract_result_bak 表新增字段

```sql
-- 备份表同步新增字段
ALTER TABLE com_extract_result_bak 
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'NONE' COMMENT '提取来源:NONE|OS|C1';
```

### 4. Flyway 迁移脚本

文件位置：`specs/0016-extract-doc-result-field-enhancement/scripts/V1.0.0__add_extract_fields.sql`

```sql
-- V1.0.0__add_extract_fields.sql
-- 描述：新增资料提取相关字段

-- 1. com_extract_doc 表新增字段
ALTER TABLE com_extract_doc 
ADD COLUMN os_txt_att_id BIGINT COMMENT '原始文本附件ID(SmartOS转换生成)',
ADD COLUMN os_convert_state VARCHAR(2) DEFAULT 'U' COMMENT 'SmartOS转换状态:U|I|F|Y',
ADD COLUMN os_convert_duration INT DEFAULT 0 COMMENT 'SmartOS转换耗时(秒)';

-- 2. com_extract_result 表新增字段
ALTER TABLE com_extract_result 
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'NONE' COMMENT '提取来源:NONE|OS|C1';

-- 3. com_extract_result_bak 表新增字段
ALTER TABLE com_extract_result_bak 
ADD COLUMN extract_source VARCHAR(10) DEFAULT 'NONE' COMMENT '提取来源:NONE|OS|C1';

-- 4. 添加索引
CREATE INDEX idx_extract_source ON com_extract_result(extract_source);
```

---

## 错误处理

| 场景 | 处理方式 | 错误信息 |
|------|---------|---------|
| SmartOS转换失败 | 记录日志，状态设为'F'，继续执行传统路径 | "SmartOS转换失败: {errorMessage}" |
| 传统转换失败 | 记录日志，状态设为'F'，返回错误 | "传统转换失败: {errorMessage}" |
| 两种路径都失败 | 记录失败状态，返回错误结果 | "双路径转换均失败" |
| MDM上传失败 | 捕获异常，记录日志，返回失败 | "文件上传MDM失败" |
| MDM下载失败 | 捕获异常，记录日志，返回失败 | "文件下载失败" |
| 提取执行异常 | 捕获异常，记录日志，返回失败 | "提取执行异常: {errorMessage}" |

---

## 影响范围

### 新增文件
- `config/enums/ExtractSourceEnum.java` - 提取来源枚举类
- `scripts/V1.0.0__add_extract_fields.sql` - 数据库迁移脚本

### 修改文件
- `entity/extract/ComExtractDocEntity.java` - 新增3个字段及getter/setter
- `entity/extract/ComExtractResultEntity.java` - 新增extractSource字段
- `aggregate/extract/ComExtractDocAggregate.java` - 实现双路径转换与择优逻辑
- `resources/mapper/extract/ComExtractDocMapper.xml` - 新增字段SQL映射
- `resources/mapper/extract/ComExtractResultMapper.xml` - 新增字段SQL映射
- `converter/extract/ComExtractDocConverter.java` - 新增字段映射（如有）
- `model/extract/*Resp.java` - 响应对象新增字段（如需要返回）

### 无需修改
- Controller 层 - 接口签名不变
- Service 层 - CRUD 由 MyBatis-Plus 自动处理
- 其他业务模块 - 不受影响

---

## 风险点

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 双路径转换耗时增加 | 单次提取时间可能翻倍 | 1. 异步执行 2. 缓存已转换结果 3. 监控性能指标 |
| SmartOS服务不可用 | SmartOS路径全部失败 | 降级到传统路径，记录告警日志 |
| MDM存储压力增加 | 每个文档多存一份TXT | 1. 评估存储成本 2. 考虑清理策略 3. 压缩存储 |
| 历史数据兼容性 | 旧数据新字段为NULL | 迁移脚本设置默认值，代码做空值判断 |
| 成功率计算不准确 | 择优逻辑失效 | 1. 单元测试验证 2. 灰度发布观察 3. 提供配置开关 |
| converter-starter模块依赖 | 可能需要调整SmartOSConverterFacade | 提前沟通，确认API兼容性 |

---

## 测试建议

### 单元测试
1. ExtractSourceEnum 枚举类测试
2. 成功率计算方法测试
3. 择优逻辑测试（各种边界情况）

### 集成测试
1. SmartOS转换完整流程测试
2. 传统转换完整流程测试
3. 双路径同时执行测试
4. 择优入库验证测试

### 性能测试
1. 单文档双路径转换耗时
2. 批量文档提取性能
3. MDM上传下载性能

---

**状态**：草稿（待用户确认）
