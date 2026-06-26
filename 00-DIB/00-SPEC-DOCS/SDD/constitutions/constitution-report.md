# DIB Agent Service Report 项目宪法

> 本文档是 dib-agent-service-report（报告服务）项目的开发规范，所有 AI 助手在本项目中工作时必须严格遵守。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录 report 服务的专属规范。

---

## 一、项目概述

dib-agent-service-report 是 DIB Agent 微服务体系中的报告生成服务，负责报告生成、模板管理、变量计算、Word 文档渲染等核心功能，同时包含投保（toubao）子模块。

### 项目结构
- **dib-agent-service-report-core**: 核心模块
- **dib-agent-service-report-web**: Web 服务模块（主要实现）
- **dib-agent-service-report-feign**: Feign 客户端模块（SDK）

### 端口号
- **30002** - 报告服务端口（固定，禁止修改）

### context-path
- `/api/report`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，report 服务额外使用：

- **Word 文档渲染**: `WordRenderUtil` / `WordResolveUtil`，用于报告 Word 文档生成
- **DAG 变量依赖计算**: 变量之间存在依赖关系，通过 DAG 确定计算顺序
- **Aviator 表达式引擎**: 用于变量计算中的公式求值
- **TYC（天眼查）数据接口**: 外部数据源集成
- **AIGC 集成**: AI 生成内容能力集成
- **Redis 缓存**: 用于报告/变量数据缓存

---

## 三、包结构规范

### 基础包路径

report 服务包含两个顶级包：

```
com.dib.agent.report      # 主包（报告、模板、变量）
com.dib.agent.toubao      # 投保子模块包
```

### 标准包结构
```
com.dib.agent.report/
├── aggregate/              # 聚合服务层（业务编排）
├── component/
│   └── varCalc/            # 变量计算组件
│       ├── ai/             # AI 计算器
│       ├── aviator/        # Aviator 表达式计算器
│       ├── sql/            # SQL 计算器
│       └── tyc/            # 天眼查数据计算器
├── config/                 # 配置类
│   ├── annotation/         # 自定义注解
│   ├── constant/           # 常量定义
│   └── enums/              # 枚举定义
├── controller/             # 控制器层（REST API）
├── converter/              # 对象转换器（MapStruct）
├── entity/                 # 实体类（数据库映射）
│   ├── dws/                # 数据仓库实体
│   ├── report/             # 报告实体
│   ├── template/           # 模板实体
│   └── var/                # 变量实体
├── mapper/                 # MyBatis Mapper 接口
├── model/                  # 数据模型（DTO/VO/Req/Resp）
│   ├── dws/
│   ├── report/
│   ├── template/
│   └── varconfig/          # 变量配置模型
├── schedule/               # 定时任务
├── service/                # 服务层
│   ├── report/             # 报告服务
│   ├── template/           # 模板服务
│   └── var/                # 变量服务
└── util/
    ├── graph/              # 图计算工具（DAG）
    └── word/               # Word 文档工具

com.dib.agent.toubao/       # 投保子模块（独立包结构）
```

---

## 四、命名规范（专属部分）

### Service 接口命名
- **格式**: `I{业务模块}{功能}Service`（带 `I` 前缀）
- **示例**:
  - `IReportXxxService`（报告相关）
  - `ITemplateXxxService`（模板相关）
  - `IVarXxxService`（变量相关）

### 核心业务域
| 业务域 | 说明 |
|--------|------|
| `report` | 报告生成与管理 |
| `template` | 报告模板管理 |
| `var` | 变量配置与计算 |
| `toubao` | 投保业务（独立子模块） |
| `dws` | 数据仓库相关 |

### 变量计算器命名
- `AiVarCalcXxx` - AI 变量计算器
- `AviatorVarCalcXxx` - Aviator 表达式计算器
- `SqlVarCalcXxx` - SQL 变量计算器
- `TycVarCalcXxx` - 天眼查数据计算器

---

## 五、专属技术规范

### Word 文档渲染

- Word 渲染工具类放在 `util/word/` 包下
- 核心工具：`WordRenderUtil`（渲染）、`WordResolveUtil`（解析）
- 临时文件路径通过配置注入：`dib.converter.tmp-path`
- 渲染过程中的异常必须捕获，日志格式：`【Word渲染】渲染失败，报告ID：{}，模板ID：{}`

### DAG 变量依赖计算

- 图工具类放在 `util/graph/` 包下
- 变量计算前必须通过 DAG 拓扑排序确定计算顺序
- 循环依赖检测：发现环路时抛出 `BizValidateException`，提示信息包含循环变量列表

### Aviator 表达式引擎

- Aviator 计算器放在 `component/varCalc/aviator/` 包下
- 表达式字符串存储在数据库变量配置中，运行时求值
- 表达式执行异常必须捕获，日志格式：`【变量计算-Aviator】表达式执行失败，变量ID：{}，表达式：{}`

### 报告自动生成

报告自动生成通过配置开关控制，默认关闭：

```yaml
dib:
  report:
    auto-generate-enabled: false          # 自动生成报告
    area-report-generate-enabled: false   # 辖区报告自动生成
    sync-area-report-to-doc-enabled: false # 同步辖区报告到文档库
```

- 自动生成任务放在 `schedule/` 包下
- 执行前必须检查对应开关

### 双包扫描配置

Swagger 扫描两个包：

```yaml
knife4j:
  openapi:
    group:
      default:
        api-rule-resources:
          - com.dib.agent.report
          - com.dib.agent.toubao
```

新增 Controller 时，确认放在上述两个包之一。

---

## 六、无 Groovy 脚本

report 服务**不使用** Groovy 脚本，所有计算逻辑通过 Java 组件实现。

---

## 七、AI 特别约束（专属）

- 修改 Word 渲染相关代码时，必须保留临时文件清理逻辑，防止磁盘泄漏
- 修改变量计算组件时，必须保持各计算器的接口一致性
- 新增变量计算器类型时，必须在 `component/varCalc/` 下创建对应子包
- 投保（toubao）模块代码放在 `com.dib.agent.toubao` 包下，不得混入主包
- 修改 DAG 相关代码时，必须确保环检测逻辑完整

---

**本宪法最终解释权归 DIB Agent 项目团队所有。**
