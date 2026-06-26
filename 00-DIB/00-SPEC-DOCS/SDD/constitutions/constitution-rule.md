# DIB Agent Service Rule 项目宪法

> 本文档是 dib-agent-service-rule（规则服务）项目的开发规范，所有 AI 助手在本项目中工作时必须严格遵守。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录 rule 服务的专属规范。

---

## 一、项目概述

dib-agent-service-rule 是 DIB Agent 微服务体系中的规则引擎服务，负责评分框架管理、业务规则配置、AI 规则计算等核心功能。

### 项目结构
- **dib-agent-service-rule-core**: 核心模块
- **dib-agent-service-rule-web**: Web 服务模块（主要实现）
- **dib-agent-service-rule-feign**: Feign 客户端模块（SDK）

### 端口号
- **30004** - 规则服务端口（固定，禁止修改）

### context-path
- `/api/rule`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，rule 服务额外使用：

- **DAG 有向无环图**: 用于 AI 规则计算的依赖关系管理
- **MVEL 表达式引擎**: 用于业务规则条件计算
- **Redis 缓存**: `RedisCacheConfig`，用于规则/框架数据缓存（`dib.cache: redis`）
- **定时任务**: 框架计算、业务规则计算相关定时任务

---

## 三、包结构规范

### 基础包路径
```
com.dib.agent.rule.web
```

### 标准包结构
```
com.dib.agent.rule.web/
├── aggregate/              # 聚合服务层（业务编排）
├── component/              # 组件（可复用的业务组件）
│   ├── aiRuleCalc/         # AI 规则计算（含 DAG）
│   ├── bizRuleCalc/        # 业务规则计算（含 MVEL 表达式）
│   └── frameCalc/          # 框架计算
├── config/                 # 配置类
│   ├── constant/           # 常量定义
│   └── enums/
│       ├── frame/          # 框架相关枚举
│       └── rule/           # 规则相关枚举
├── controller/             # 控制器层（REST API）
├── converter/              # 对象转换器（MapStruct）
├── entity/                 # 实体类（数据库映射）
│   ├── frame/              # 框架实体
│   └── rule/               # 规则实体
├── mapper/                 # MyBatis Mapper 接口
├── model/                  # 数据模型（DTO/VO/Req/Resp）
│   └── ruleDAG/            # DAG 相关模型
├── schedule/               # 定时任务
├── service/                # 服务层
│   ├── domain/             # 领域服务
│   ├── frame/              # 框架服务
│   ├── rule/               # 规则服务
│   └── task/               # 任务服务
└── util/
    └── graph/              # 图计算工具（DAG）
```

---

## 四、命名规范（专属部分）

### Service 接口命名
- **格式**: `I{业务模块}{功能}Service`（带 `I` 前缀）
- **示例**:
  - `IComFrameXxxService`（框架相关）
  - `IComRuleXxxService`（规则相关）

### 核心业务域
| 业务域 | 说明 |
|--------|------|
| `frame` | 评分框架管理 |
| `rule` | 规则配置与管理 |
| `domain` | 领域管理 |

### 组件命名
- `AiRuleCalcXxx` - AI 规则计算组件
- `BizRuleCalcXxx` - 业务规则计算组件（MVEL）
- `FrameCalcXxx` - 框架计算组件

---

## 五、专属技术规范

### DAG 有向无环图

- DAG 相关模型放在 `model/ruleDAG/` 包下
- 图工具类放在 `util/graph/` 包下
- AI 规则计算组件（`component/aiRuleCalc/`）负责构建和执行 DAG
- DAG 节点依赖关系必须在构建时做环检测，发现环路抛出 `BizValidateException`

### MVEL 表达式引擎

- 业务规则计算组件（`component/bizRuleCalc/`）负责 MVEL 表达式的编译和执行
- 表达式字符串存储在数据库中，运行时动态编译
- 表达式执行异常必须捕获并记录详细日志，格式：`【业务规则计算】表达式执行失败，规则ID：{}，表达式：{}`

### Redis 缓存

- 缓存配置类：`RedisCacheConfig`
- 缓存 key 命名规范：`rule:{业务域}:{标识}`，如 `rule:frame:123`
- 缓存更新策略：规则/框架数据变更时主动失效缓存

### 定时任务

定时任务开关通过配置控制（`dib.schedule`），禁止硬编码 cron 表达式：

```yaml
dib:
  schedule:
    biz-rule:
      calc-enabled: false        # 业务规则计算开关
      task-create-enabled: false # 任务创建开关
    frame:
      calc-enabled: false        # 框架计算开关
      auto-create-enabled: false # 自动创建开关
      cron-refresh-enabled: false
      node-code-refresh-enabled: false
      value-gc-enabled: false
```

- 定时任务类放在 `schedule/` 包下
- 任务执行前必须检查对应开关是否开启
- 任务执行日志格式：`【定时任务-{任务名}】开始执行` / `【定时任务-{任务名}】执行完成，耗时：{}ms`

---

## 六、无 Groovy 脚本

rule 服务**不使用** Groovy 脚本，所有计算逻辑通过 Java 组件实现。

---

## 七、AI 特别约束（专属）

- 修改 DAG 相关代码时，必须确保环检测逻辑完整
- 修改 MVEL 表达式相关代码时，必须保留异常捕获和日志记录
- 新增定时任务时，必须添加对应的配置开关，默认值为 `false`
- 修改缓存相关代码时，必须同步更新缓存失效逻辑

---

**本宪法最终解释权归 DIB Agent 项目团队所有。**
