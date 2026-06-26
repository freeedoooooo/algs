# 0016-extract-doc-result-field-enhancement 需求文档

> 编号：`0016` | 模块：`extract` | 服务：`dib-agent-service-extract` | 创建时间：2026-05-26

---

## 背景

当前资料提取和转换流程中，缺乏对以下信息的追踪和管理：
1. **原始文本附件关联**：无法直接关联转换后的TXT文件与原始文本附件ID
2. **转换状态细化**：现有 `convertState` 字段需要扩展以支持更细粒度的转换状态管理
3. **提取来源追溯**：无法区分数据来源（人工录入、自动提取、ETL同步等），影响数据统计和分析

本需求通过新增数据库字段，完善资料提取和转换的数据追踪能力。

## 目标用户

- 系统管理员：需要查看完整的转换链路和数据来源
- 业务人员：需要按来源统计分析提取数据
- 开发人员：需要更清晰的转换状态用于问题排查

## 功能描述

### 1. com_extract_doc 表新增字段

在资料表中增加三个字段，用于追踪原始文本附件、转换状态和转换耗时：

- **os_txt_att_id** (BIGINT)：原始文本附件ID
  - 用途：关联转换后生成的TXT文件对应的原始附件ID
  - 场景：当文档经过OCR或格式转换后，记录生成的TXT文件ID
  
- **os_convert_state** (VARCHAR(2))：操作系统转换状态
  - 用途：记录底层操作系统级别的转换执行状态
  - 状态值定义：参考现有 `convertState` 的状态码体系（U/I/F/Y/Z）
  
- **os_convert_duration** (INT)：操作系统转换耗时（秒）
  - 用途：记录转换操作的实际执行耗时
  - 单位：秒
  - 默认值：0

### 2. com_extract_result 和 com_extract_result_bak 表新增字段

在提取结果表和备份表中增加提取来源字段：

- **extract_source** (VARCHAR(10))：提取来源标识
  - 用途：标识该条提取数据的来源渠道
  - 类型：枚举类（需创建 `ExtractSourceEnum`）
  - 枚举值：
    - `NONE` - 未知/未设置
    - `OS` - SmartOS提取
    - `C1` - 传统路径

### 3. 提取逻辑优化（ComExtractDocAggregate.extractedOneDoc）

**核心变更**：根据 `os_txt_att_id` 和 `txt_att_id` 的存在性判断是否需要转换，分别调用不同的转换器进行资料转换，实现双路径提取并择优入库。

#### 当前逻辑
- 统一从 `txt_att_id` 下载转换后的TXT文件进行提取

#### 优化后逻辑

1. **双路径转换与获取 txtBytes**

   **路径A - SmartOS 转换路径（使用 os_txt_att_id）**：
   - 判断 `os_txt_att_id` 是否存在
   - **如果不存在**：
     - 调用 converter-starter 模块的 `SmartOSConverterFacade` 进行 SmartOS 转换
     - 转换过程中更新 `os_convert_state`（U→I→Y/F）
     - 转换完成后记录 `os_convert_duration`（耗时秒数）
     - 生成并保存 TXT 文件到 MDM，获取 `os_txt_att_id`
   - **如果已存在**：
     - 跳过转换，直接使用现有的 `os_txt_att_id`
   - 从 MDM 根据 `os_txt_att_id` 下载 TXT 文件得到 `txtBytes`

   **路径B - 传统转换路径（使用 txt_att_id）**：
   - 判断 `txt_att_id` 是否存在
   - **如果不存在**：
     - 根据文档类型调用对应的转换器（Word/PDF/Excel等）
     - 转换过程中更新 `convert_state`（U→I→Y/F/Z）
     - 转换完成后记录 `convert_duration`（耗时秒数）
     - 生成并保存 TXT 文件到 MDM，获取 `txt_att_id`
   - **如果已存在**：
     - 跳过转换，直接使用现有的 `txt_att_id`
   - 从 MDM 根据 `txt_att_id` 下载 TXT 文件得到 `txtBytes`

2. **分别执行提取**
   - 对两种路径得到的 txtBytes 分别执行要素提取
   - 分别计算两种路径的**要素提取成功率**

3. **择优入库**
   - 比较两种路径的提取成功率
   - 选择**成功率更高**的结果入库到 `com_extract_result` 表
   - 记录最终采用的提取来源到 `extract_source` 字段

4. **涉及模块**
   - **dib-agent-service-extract**：提取逻辑优化
   - **dib-agent-converter-starter**：SmartOS 转换器支持

## 所属模块

- 服务：`dib-agent-service-extract`（端口 `30001`）
- 模块：`extract`
- 业务域：`资料提取与转换`
- 涉及文件/目录：
  - **extract 模块**：
    - Entity: `entity/extract/ComExtractDocEntity.java`
    - Entity: `entity/extract/ComExtractResultEntity.java`
    - Entity: `entity/extract/ComExtractResultBakEntity.java`
    - Aggregate: `aggregate/extract/ComExtractDocAggregate.java`
    - Mapper XML: `resources/mapper/extract/` 下对应XML文件
    - Converter: `converter/` 下相关转换器
    - Model: `model/extract/` 下相关Req/Resp对象
  - **converter-starter 模块**：
    - `dib-agent-parent/dib-agent-converter-starter/src/main/java/com/dib/agent/converter/core/SmartOSConverterFacade.java`
  - 数据库脚本: `specs/0016-extract-doc-result-field-enhancement/scripts/`

## 核心业务规则

### 字段赋值时机

1. **os_txt_att_id**：
   - 赋值时机：SmartOS 转换完成后，记录生成的 TXT 文件 ID
   - 允许为空：是（非 SmartOS 提取器时为 NULL）
   
2. **os_convert_state**：
   - 状态流转：U(待转换) → I(转换中) → Y(成功)/F(失败)
   - 与现有 `convertState` 的关系：补充关系，`os_convert_state` 专门记录 SmartOS 转换状态
   - 默认值：'U'
   
3. **os_convert_duration**：
   - 赋值时机：SmartOS 转换完成后，记录实际耗时
   - 单位：秒
   - 默认值：0
   
4. **extract_source**：
   - 赋值时机：提取完成后，根据择优结果记录最终采用的来源
   - 枚举值：`NONE`（未知）、`OS`（SmartOS路径）、`C1`（传统路径）
   - 默认值：`NONE`
   - 需要创建枚举类：`ExtractSourceEnum`

### 双路径提取成功率计算

**成功率计算公式**：
```
成功率 = 成功提取的字段数 / 应提取的总字段数 * 100%
```

**比较逻辑**：
- 如果 SmartOS 路径成功率 >= 传统路径成功率：采用 SmartOS 结果
- 如果传统路径成功率 > SmartOS 路径成功率：采用传统路径结果
- 如果两者都为空或失败：记录失败状态

### 转换逻辑伪代码

```java
// 路径A - SmartOS 转换
if (docEntity.getOsTxtAttId() == null || docEntity.getOsTxtAttId() <= 0) {
    // 需要转换
    docService.updateConvertState(docId, "os_convert_state", "I");
    long startTime = System.currentTimeMillis();
    
    // 调用 SmartOSConverterFacade 进行转换
    ConvertResult result = smartOSConverterFacade.convert(docEntity.getAttId());
    
    long duration = (System.currentTimeMillis() - startTime) / 1000;
    if (result.isSuccess()) {
        // 上传到 MDM，获取 os_txt_att_id
        Long osTxtAttId = mdmService.upload(result.getTxtBytes());
        docService.update(docId, "os_txt_att_id", osTxtAttId);
        docService.updateConvertState(docId, "os_convert_state", "Y");
    } else {
        docService.updateConvertState(docId, "os_convert_state", "F");
    }
    docService.update(docId, "os_convert_duration", duration);
}
// 从 MDM 下载 txtBytes
txtBytesA = mdmService.download(docEntity.getOsTxtAttId());

// 路径B - 传统转换（类似逻辑）
if (docEntity.getTxtAttId() == null || docEntity.getTxtAttId() <= 0) {
    // 根据文档类型调用对应转换器
    // ...
}
txtBytesB = mdmService.download(docEntity.getTxtAttId());
```

### ExtractSourceEnum 枚举类定义

**存放位置**：`com.dib.agent.extract.web.config.enums.ExtractSourceEnum`

**枚举值定义**：
```java
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
    
    // 构造函数、getter方法等
}
```

**使用场景**：
- Entity 字段类型：`private ExtractSourceEnum extractSource;`
- 数据库存储值：`'NONE'` / `'OS'` / `'C1'`
- 择优入库时设置：
  ```java
  if (smartOSSuccessRate >= traditionalSuccessRate) {
      resultEntity.setExtractSource(ExtractSourceEnum.OS);
  } else {
      resultEntity.setExtractSource(ExtractSourceEnum.C1);
  }
  ```

## 输入参数

| 参数名 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| os_txt_att_id | BIGINT | 转换流程 | TXT附件ID，可为空 |
| os_convert_state | VARCHAR(2) | 转换流程 | 转换状态码 |
| os_convert_duration | INT | 转换流程 | 转换耗时（秒），默认0 |
| extract_source | VARCHAR(10) | 提取任务 | 提取来源标识，枚举值：NONE/OS/C1 |

## 输出结果

无直接输出，为数据库结构变更。

## 用户故事

- 作为 **系统管理员**，我希望 **查看文档的原始文本附件ID**，以便 **追溯转换链路和定位问题**
- 作为 **业务分析师**，我希望 **按提取来源统计数据**，以便 **分析不同渠道的数据质量和效率**
- 作为 **开发人员**，我希望 **查看详细的转换状态**，以便 **快速定位转换失败的原因**

## 验收标准

- [ ] 标准1：com_extract_doc 表成功添加 `os_txt_att_id`、`os_convert_state` 和 `os_convert_duration` 字段
- [ ] 标准2：com_extract_result 表成功添加 `extract_source` 字段
- [ ] 标准3：com_extract_result_bak 表成功添加 `extract_source` 字段
- [ ] 标准4：Entity 类正确映射新字段
- [ ] 标准5：Mapper XML 包含新字段的查询和更新语句
- [ ] 标准6：Converter 正确处理新字段的转换
- [ ] 标准6.1：创建 ExtractSourceEnum 枚举类（NONE/OS/C1）
- [ ] 标准7：Model 对象（Req/Resp）包含新字段（如需要）
- [ ] 标准8：提供数据库迁移脚本（Flyway格式）
- [ ] 标准9：历史数据的默认值处理正确
- [ ] 标准10：ComExtractDocAggregate.extractedOneDoc 方法实现双路径转换与提取逻辑
- [ ] 标准11：根据 os_txt_att_id 和 txt_att_id 的存在性判断是否需要转换
- [ ] 标准12：SmartOS 路径正确调用 SmartOSConverterFacade 进行转换
- [ ] 标准13：传统路径正确调用对应的转换器进行转换
- [ ] 标准14：分别计算两种路径的提取成功率
- [ ] 标准15：择优选择成功率更高的结果入库
- [ ] 标准16：正确记录 extract_source 字段值
- [ ] 标准17：SmartOS 转换时正确更新 os_convert_state 和 os_convert_duration
- [ ] 标准18：传统转换时正确更新 convert_state 和 convert_duration
- [ ] 标准19：converter-starter 模块的 SmartOSConverterFacade 支持新功能

## 边界条件

| 场景 | 处理方式 |
|------|---------|
| 当 os_txt_att_id 为空时 | 允许为NULL，表示未关联TXT附件 |
| 当 os_convert_state 未初始化时 | 设置默认值为 'U'（待转换） |
| 当 os_convert_duration 未初始化时 | 设置默认值为 0 |
| 当 extract_source 为空时 | 设置默认值为 'NONE' |
| 当历史数据不存在这些字段时 | 迁移脚本需设置合理的默认值 |

## 非功能需求

- **性能**：新增字段不影响现有查询性能，如需频繁查询考虑添加索引
- **可维护性**：遵循项目命名规范和编码规范，添加必要的注释
- **兼容性**：确保向后兼容，不影响现有业务流程
- **安全性**：无特殊安全要求

## 待确认问题

- [ ] **是否需要为这些字段建立索引**：特别是 extract_source 如果经常用于筛选统计
- [ ] **前端/API 是否需要展示或接收这些字段**：是否需要修改接口？
- [ ] **是否需要数据迁移脚本填充历史数据**：还是仅对新数据生效？
- [ ] **成功率计算的具体实现细节**：如何定义"成功提取的字段"？是否有现成的计算方法？
- [ ] **converter-starter 模块需要哪些调整**：SmartOSConverterFacade 是否需要新增方法或修改现有逻辑？

---

**状态**：草稿（待用户确认）
