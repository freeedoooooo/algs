# DIB Agent Data DG 项目宪法

> 本文档是 dib-agent-data-dg（数据治理服务）的开发规范。
> 公共规范请同时参阅 `constitution.md`，本文档仅记录专属规范。

---

## 一、项目概述

dib-agent-data-dg 是 DIB Agent 微服务体系中的数据治理服务，负责外部数据源（如天眼查）的数据同步、数据转换、数据清洗等数据治理功能。

### 项目结构
- **dib-agent-data-dg-web**: Web 服务模块（主要实现）

### 端口号
- **30005** - 数据治理服务端口（固定，禁止修改）

### context-path
- `/api/dg`

---

## 二、技术栈（专属部分）

在公共技术栈基础上，data-dg 服务额外使用：

- **分布式 ID**: 雪花算法（`dib.distribute.datacenterId`、`dib.distribute.workerId`）
- **异步处理**: Spring 异步任务（`@Async`）
- **外部 API 集成**: 天眼查（TYC）等第三方数据源

---

## 三、包结构规范

### 基础包路径
```
com.dib.agent.data.dg.web
```

### 标准包结构
```
com.dib.agent.data.dg.web/
├── aggregate/
│   └── TycDataAggregate            # 天眼查数据聚合
├── component/
│   └── TaskConsumerService         # 任务消费服务
├── config/
│   ├── constant/
│   └── enums/
│       ├── TycApiEnum              # 天眼查 API 类型枚举
│       └── TransferFlagEnum        # 转换标志枚举
├── controller/
│   └── TestTycDataGovController    # 测试控制器（仅开发环境）
├── converter/
├── entity/
├── mapper/
├── model/
│   ├── req/
│   └── resp/
├── service/
└── util/
```

---

## 四、业务域规范

### 核心业务域

| 业务域 | 说明 | 关键组件 |
|--------|------|---------|
| 数据同步 | 从外部 API 拉取数据到缓存表 | TycDataAggregate |
| 数据转换 | 缓存表数据转换到治理表 | TaskConsumerService |
| 任务管理 | 同步任务的调度和状态管理 | - |

### 数据流向
```
外部 API（天眼查等）
    ↓ 同步
缓存表（raw data）
    ↓ 转换/清洗
治理表（governed data）
    ↓ 提供
下游服务消费
```

### 表命名前缀
- 缓存表（原始数据）：`dg_cache_`
- 治理表（清洗后数据）：`dg_gov_`
- 任务表：`dg_task_`

---

## 五、数据同步规范

- 同步任务必须有幂等性保证（相同数据重复同步不产生脏数据）
- 同步失败必须记录失败原因，支持重试
- 重试次数有上限，超过上限后告警并停止重试
- 同步任务执行状态必须持久化（不依赖内存状态）
- 大批量同步使用分页拉取，禁止一次性拉取全量数据

---

## 六、外部 API 集成规范

### 天眼查（TYC）API
- API 类型通过 `TycApiEnum` 枚举管理，禁止硬编码 API 路径
- 调用外部 API 必须有超时配置
- 外部 API 调用失败必须有降级处理，不影响主业务
- API 密钥通过环境变量注入，禁止硬编码

### 通用外部 API 规范
- 外部 API 调用封装在独立的 component 或 util 中
- 调用前后必须有日志记录（请求参数、响应状态、耗时）
- 响应数据必须做空值和异常格式校验

---

## 七、异步处理规范

- 数据转换任务使用 `@Async` 异步执行
- 异步方法必须有完整的异常捕获，禁止静默失败
- 异步任务完成后更新任务状态
- 异步线程池配置在 `config/` 下，禁止使用默认线程池

```java
// 异步任务示例
@Async("dgTaskExecutor")
public void processTransfer(Long taskId) {
    try {
        log.info("【数据治理】开始转换任务：{}", taskId);
        // 业务逻辑
        updateTaskStatus(taskId, TransferFlagEnum.SUCCESS);
    } catch (Exception e) {
        log.error("【数据治理】转换任务失败：taskId={}, error={}", taskId, e.getMessage(), e);
        updateTaskStatus(taskId, TransferFlagEnum.FAILED);
    }
}
```

---

## 八、分布式 ID 规范

- 使用雪花算法生成分布式 ID
- `datacenterId` 和 `workerId` 通过配置文件注入，禁止硬编码
- 不同部署实例必须配置不同的 `workerId`

---

## 九、测试控制器规范

- `TestTycDataGovController` 仅用于开发和测试环境
- 生产环境必须通过配置开关禁用测试接口
- 测试接口不得暴露敏感数据

---

## 十、AI 特别约束（专属）

- 新增外部 API 集成时，必须在 `TycApiEnum`（或对应枚举）中注册
- 数据同步逻辑必须有幂等性设计
- 异步任务必须有完整的异常处理和状态更新
- 修改数据转换逻辑时，确认缓存表和治理表的字段映射
- 测试接口必须有环境开关保护

---

**本宪法最终解释权归 DIB 项目团队所有。**
