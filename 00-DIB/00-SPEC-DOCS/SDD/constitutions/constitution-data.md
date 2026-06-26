# DIB Agent Service Data 项目宪法

> 本文档是 dib-agent-service-data（数据资源服务）项目的开发规范，所有 AI 助手在本项目中工作时必须严格遵守。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录 data 服务的专属规范。

---

## 一、项目概述

dib-agent-service-data 是 DIB Agent 微服务体系中的数据资源服务，负责数据指标计算、数据集成、元数据管理等核心功能。

### 项目结构
- **dib-agent-service-data-core**: 核心模块（当前为空）
- **dib-agent-service-data-web**: Web 服务模块（主要实现）
- **dib-agent-service-data-feign**: Feign 客户端模块（SDK）

### 端口号
- **30003** - 数据服务端口（固定，禁止修改）

### context-path
- `/api/data`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，data 服务额外使用：

- **脚本引擎**: Groovy（用于指标计算算子）

---

## 三、包结构规范

### 基础包路径
```
com.dib.agent.data.web
```

### 标准包结构
```
com.dib.agent.data.web/
├── aggregate/
│   ├── common/
│   ├── databoard/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
├── aspect/
│   └── log/
├── component/
│   ├── di/
│   └── indexcalc/
├── config/
│   ├── constant/
│   └── enums/
├── controller/
│   ├── common/
│   ├── databoard/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
├── converter/
│   ├── common/
│   ├── databoard/
│   ├── datamodel/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
├── entity/
│   ├── common/
│   ├── databoard/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
├── mapper/
│   ├── common/
│   ├── databoard/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
├── model/
│   ├── data/
│   ├── databoard/
│   ├── datadomain/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
├── schedule/
│   ├── di/
│   └── index/
├── service/
│   ├── common/
│   ├── databoard/
│   ├── datasource/
│   ├── di/
│   ├── index/
│   └── metadata/
└── util/
```

---

## 四、Groovy 脚本规范

### 脚本存放位置

```
src/main/resources/indexFunc/
├── common/                  # 通用算子
├── industry/                # 行业算子
├── internalControl/         # 内控评级算子
├── qualityEvaluation/       # 质量评价算子
└── toubao/                  # 投保算子
```

### 脚本结构

Groovy 脚本采用**脚本模式**（非类模式），直接定义顶层函数，通过 `getBinding()` 获取运行时参数。

```groovy
package indexFunc.qualityEvaluation

import cn.hutool.db.sql.SqlUtil
import com.dib.agent.data.source.DataQueryInfrastructure
import com.dib.agent.data.web.config.constant.DibIndexConst
import com.dib.agent.data.web.model.index.req.DataIndexCalcReq
import com.dib.agent.data.web.util.DibSqlBuilder
import com.dib.agent.data.web.util.IndexSqlUtil
import com.dib.agent.data.web.util.SpringContextUtil
import org.slf4j.Logger
import org.slf4j.LoggerFactory

/**
 * 示例算子
 *
 * @author xxx
 * @since 2026-03-17
 */
List<Map<String, Object>> calc(String measureField, String companyDimField) {
    Logger log = LoggerFactory.getLogger(this.class)
    DataIndexCalcReq calcReq = getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME) as DataIndexCalcReq

    log.info("【算子】开始计算，指标 = {}", calcReq.getIndexCode())

    try {
        String dataSourceCode = IndexSqlUtil.getDataSourceCode(calcReq)
        DibSqlBuilder dibSqlBuilder = IndexSqlUtil.generateSqlBuilder(calcReq)
        String tableName = dibSqlBuilder.getTableName()
        String reportDate = calcReq.getDimReportDate()

        String sql = buildSql(tableName, measureField, companyDimField, reportDate)
        log.debug("【算子】SQL = {}", SqlUtil.formatSql(sql))

        List<Map<String, Object>> resultList = SpringContextUtil
            .getBean(DataQueryInfrastructure.class)
            .queryMaps(dataSourceCode, sql)

        log.info("【算子】计算完成，返回 {} 条记录", resultList.size())
        return resultList

    } catch (Exception e) {
        log.error("【算子】计算失败：{}", e.getMessage(), e)
        throw e
    }
}

/**
 * 构建计算 SQL
 */
private static String buildSql(
        String tableName, String measureField,
        String companyDimField, String reportDate) {
    def baseCte = "base_data AS (" +
        "SELECT report_date, ${companyDimField}, ${measureField} AS origin_value " +
        "FROM ${tableName} " +
        "WHERE report_date = '${reportDate}' AND ${measureField} IS NOT NULL" +
        ")"
    return "WITH ${baseCte} " +
        "SELECT report_date, report_date AS dim_report_date, " +
        "${companyDimField}, origin_value AS index_value " +
        "FROM base_data ORDER BY ${companyDimField}"
}
```

### 脚本规范

#### 1. 包声明
- 必须声明包名，与文件路径一致

#### 2. 脚本模式（重要）
- 采用**顶层函数模式**，不定义类
- 通过 `getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME)` 获取 `DataIndexCalcReq`
- 主函数返回类型为 `List<Map<String, Object>>`
- 推荐使用多行字符串（`""" """`）保持 SQL 可读性

#### 3. 动态参数获取
- 表名：`IndexSqlUtil.generateSqlBuilder(calcReq).getTableName()`
- 数据源：`IndexSqlUtil.getDataSourceCode(calcReq)`
- 报告期：`calcReq.getDimReportDate()`

#### 4. 执行查询
- 使用 `SpringContextUtil.getBean(DataQueryInfrastructure.class).queryMaps(dataSourceCode, sql)`

#### 5. 日志规范
- 使用 `LoggerFactory.getLogger(this.class)` 获取 Logger（脚本模式不支持 `@Slf4j`）
- INFO：开始/完成，WARN：空结果，DEBUG：SQL 内容，ERROR：异常

#### 6. CTE SQL 构建规范（重要）

**禁止在 SQL 字符串中写 `--` 注释**，AnyLine 执行时不会报错但行为异常，注释内容应写在方法的 JavaDoc 上。

每个 CTE 步骤**单独定义为一个 `private static String` 方法**，方法内使用多行字符串（`""" """`）保持 SQL 可读性，方法上加 JavaDoc 注释说明该步骤的业务含义。`buildXxxSql` 方法只负责将各 CTE 方法串联为完整 SQL。

```groovy
// ❌ 禁止：SQL 字符串内写 -- 注释
private static String cteStep1(String tableName, String measureField, String reportDate) {
    return """
step1 AS (
    -- 过滤空值
    SELECT company_code, ${measureField} AS val
    FROM ${tableName}
    WHERE report_date = '${reportDate}'
      AND ${measureField} IS NOT NULL
)"""
}

// ✅ 正确：注释写在方法上，SQL 用多行字符串保持可读性，每个 CTE 独立方法
/**
 * 构建完整计算 SQL
 */
private static String buildSql(String tableName, String measureField, String reportDate) {
    return "WITH " +
        cteStep1(tableName, measureField, reportDate) + ", " +
        cteStep2() + " " +
        selectFinal()
}

/**
 * step1：从源表取原始数据，过滤空值
 */
private static String cteStep1(String tableName, String measureField, String reportDate) {
    return """step1 AS (
    SELECT company_code, ${measureField} AS val
    FROM ${tableName}
    WHERE report_date = '${reportDate}'
      AND ${measureField} IS NOT NULL
)"""
}

/**
 * step2：计算全样本均值
 */
private static String cteStep2() {
    return """step2 AS (
    SELECT company_code, val, AVG(val) OVER() AS avg_val
    FROM step1
)"""
}

private static String selectFinal() {
    return "SELECT company_code, val, avg_val FROM step2"
}
```

规则总结：
- 每个 CTE 对应一个 `private static String cteXxx(...)` 方法，方法上必须有 JavaDoc 注释说明业务含义
- `buildXxxSql` 只负责串联各 CTE 方法，不写具体 SQL 片段
- 方法内可使用多行字符串（`"""`）保持 SQL 可读性
- **禁止**在 SQL 字符串内写 `--` 注释，注释统一写在方法 JavaDoc 上

---

## 五、AI 特别约束（专属）

- 修改 Groovy 脚本时必须保持原有脚本模式结构
- Groovy 脚本中的 CTE SQL 推荐使用多行字符串（`""" """`）保持可读性，每个 CTE 独立方法
- 新增算子时，脚本文件放在对应业务分类目录下

---

**本宪法最终解释权归 DIB Agent 项目团队所有。**
