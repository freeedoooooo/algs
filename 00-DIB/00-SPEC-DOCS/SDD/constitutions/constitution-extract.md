# DIB Agent Service Extract 项目宪法

> 本文档是 dib-agent-service-extract（资料提取服务）项目的开发规范，所有 AI 助手在本项目中工作时必须严格遵守。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录 extract 服务的专属规范。

---

## 一、项目概述

dib-agent-service-extract 是 DIB Agent 微服务体系中的资料提取服务，负责文档资料提取、ETL 数据同步、清单管理、项目管理、文档定位等核心功能。

### 项目结构
- **dib-agent-service-extract-web**: Web 服务模块（主要实现）

### 端口号
- **30001** - 资料提取服务端口（固定，禁止修改）

### context-path
- `/api/extract`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，extract 服务额外使用：

- **Redis Streams 消息队列**: `RedisStreamsListener` / `RedisStreamsPublisher`，用于异步提取任务调度
- **邮件发送**: `EmailSender`（Spring Mail），用于提取结果通知
- **异步执行器**: `AsyncExtractExecutor`（提取）、`AsyncDataSyncExecutor`（数据同步）
- **文档分类**: `tb-classify-starter`，用于文档自动分类
- **ETL 数据同步**: 支持从外部 FTP 数据源同步数据
- **Nacos 服务注册**: 服务注册与发现（`spring.cloud.nacos`）
- **OpenFeign 负载均衡**: Nacos 负载均衡（`spring.cloud.loadbalancer.nacos.enabled: true`）

---

## 三、包结构规范

### 基础包路径
```
com.dib.agent.extract.web
```

### 标准包结构
```
com.dib.agent.extract.web/
├── aggregate/              # 聚合服务层（业务编排）
│   ├── doclocation/        # 文档定位聚合
│   ├── etl/                # ETL 聚合
│   ├── extract/            # 提取聚合
│   │   └── tool/           # 提取工具（文档名校验、Reader 执行器）
│   ├── inventory/          # 清单聚合
│   └── project/            # 项目聚合
├── async/                  # 异步执行器
│   ├── AsyncExtractExecutor.java    # 异步提取执行器
│   └── AsyncDataSyncExecutor.java   # 异步数据同步执行器
├── config/                 # 配置类
│   ├── constant/           # 常量定义
│   ├── email/              # 邮件配置
│   ├── enums/              # 枚举定义
│   └── redis/              # Redis Streams 配置
├── controller/             # 控制器层（REST API）
│   ├── doclocation/        # 文档定位接口
│   ├── etl/                # ETL 接口
│   ├── extract/            # 提取接口
│   ├── inventory/          # 清单接口
│   ├── metadata/           # 元数据接口
│   ├── open/               # 开放接口
│   └── project/            # 项目接口
├── converter/              # 对象转换器（MapStruct）
├── entity/                 # 实体类（数据库映射）
│   ├── etl/                # ETL 实体
│   ├── extract/            # 提取实体
│   └── inventory/          # 清单实体
├── mapper/                 # MyBatis Mapper 接口
├── model/                  # 数据模型（DTO/VO/Req/Resp）
│   ├── etl/
│   ├── extract/
│   ├── inventory/
│   └── project/
├── service/                # 服务层
│   ├── etl/                # ETL 服务
│   ├── extract/            # 提取服务
│   └── inventory/          # 清单服务
└── util/                   # 工具类
```

---

## 四、命名规范（专属部分）

### Service 接口命名
- **格式**: `I{业务模块}{功能}Service`（带 `I` 前缀）
- **示例**:
  - `IComExtractXxxService`（提取相关）
  - `IInventoryXxxService`（清单相关）

### 核心业务域
| 业务域 | 说明 |
|--------|------|
| `extract` | 资料提取（核心业务） |
| `etl` | ETL 数据同步 |
| `inventory` | 清单管理 |
| `project` | 项目管理 |
| `doclocation` | 文档定位 |

### 异步执行器命名
- `AsyncExtractExecutor` - 异步提取执行器
- `AsyncDataSyncExecutor` - 异步数据同步执行器

---

## 五、专属技术规范

### Redis Streams 消息队列

- Redis Streams 配置放在 `config/redis/` 包下
- 监听器：`RedisStreamsListener`，发布器：`RedisStreamsPublisher`
- Stream key 命名规范：`extract:{业务域}:{操作}`，如 `extract:task:submit`
- 消费者组命名规范：`{服务名}-{业务域}-group`
- 消息处理失败时必须记录日志并进入死信处理，不得静默丢弃

### 异步执行器

- 异步执行器放在 `async/` 包下，使用 `@Async` 注解
- 提取任务通过 `AsyncExtractExecutor` 异步执行，避免阻塞 HTTP 请求
- 数据同步通过 `AsyncDataSyncExecutor` 异步执行
- 异步方法必须有完整的异常捕获，日志格式：`【异步提取】任务执行失败，任务ID：{}，错误：{}`

### 邮件发送

- 邮件配置放在 `config/email/` 包下，发送器为 `EmailSender`
- 邮件发送失败不得影响主业务流程，必须 try-catch 并记录日志
- 收件人列表通过配置注入：`dib.extract.mail-to`
- 日志格式：`【邮件通知】发送失败，收件人：{}，主题：{}`

### 功能开关配置

extract 服务有多个功能开关，新增功能时必须添加对应开关，默认值为 `false`：

```yaml
dib:
  extract:
    enable: false           # 提取功能总开关
    auto-test: false        # 提取自动化测试开关
  data-sync:
    enable: false           # 数据同步开关
  etl:
    enable: false           # ETL 数据同步开关
  tb:
    classify:
      enable: false         # 文档分类开关
```

### 文件上传限制

extract 服务支持大文件上传（最大 300MB），禁止修改此配置：

```yaml
spring:
  servlet:
    multipart:
      max-file-size: 300MB
      max-request-size: 300MB
```

### Nacos 服务注册

extract 服务使用 Nacos 进行服务注册，命名空间为 `dev-c1`：

```yaml
spring:
  cloud:
    nacos:
      discovery:
        namespace: dev-c1
        service: ${spring.application.name}
```

### 开放接口（open）

`controller/open/` 下的接口为对外开放接口，需特别注意：
- 必须有接口鉴权或 token 校验
- 参数校验必须严格
- 日志记录必须完整

---

## 六、无 Groovy 脚本

extract 服务**不使用** Groovy 脚本，所有计算逻辑通过 Java 组件实现。

---

## 七、AI 特别约束（专属）

- 修改 Redis Streams 相关代码时，必须保留消费者组和消息确认逻辑
- 修改异步执行器时，必须保留完整的异常捕获，不得让异步任务静默失败
- 新增功能时，必须添加对应的配置开关，默认值为 `false`
- 修改邮件发送逻辑时，必须确保发送失败不影响主业务流程
- 开放接口（`controller/open/`）的修改必须特别谨慎，需确认鉴权逻辑完整

---

**本宪法最终解释权归 DIB Agent 项目团队所有。**
