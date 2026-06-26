# DIB Agent 微服务公共基础宪法

> 本文档是 DIB Agent 微服务体系的公共开发规范，适用于所有服务。
> 各服务的专属规范请参阅对应的子宪法文档：
> - `constitution-agent-parent.md` - 父 POM 与基础设施（dib-agent-parent）
> - `constitution-auth-server.md` - OAuth2 认证服务器（data-cloud-auth-server）
> - `constitution-gateway.md` - API 网关（data-cloud-gateway）
> - `constitution-auth-resource.md` - 权限资源管理服务（data-cloud-auth-resource）
> - `constitution-mdm.md` - 主数据管理服务（data-cloud-mdm）
> - `constitution-extract.md` - 资料提取服务（dib-agent-service-extract）
> - `constitution-report.md` - 报告生成服务（dib-agent-service-report）
> - `constitution-data.md` - 数据资源服务（dib-agent-service-data）
> - `constitution-rule.md` - 规则引擎服务（dib-agent-service-rule）
> - `constitution-data-dg.md` - 数据治理服务（dib-agent-data-dg）

---

## 一、服务概览

| 服务 | 端口 | context-path | 基础包路径 |
|------|------|-------------|-----------|
| data-cloud-auth-server | 9090 | `/`（根路径） | `com.dib.data.cloud.auth.server` |
| data-cloud-gateway | 20000 | `/`（根路径） | `com.dib.data.cloud.gateway` |
| data-cloud-auth-resource | 20001 | `/api/auth` | `com.dib.data.cloud.auth.resource` |
| data-cloud-mdm | 20002 | `/api/mdm` | `com.dib.data.cloud.mdm` |
| dib-agent-service-extract | 30001 | `/api/extract` | `com.dib.agent.extract.web` |
| dib-agent-service-report | 30002 | `/api/report` | `com.dib.agent.report` |
| dib-agent-service-data | 30003 | `/api/data` | `com.dib.agent.data.web` |
| dib-agent-service-rule | 30004 | `/api/rule` | `com.dib.agent.rule.web` |
| dib-agent-data-dg | 30005 | `/api/dg` | `com.dib.agent.data.dg.web` |

**端口号固定，禁止修改。**

---

## 二、公共技术栈

- **语言**: Java 8
- **框架**: Spring Boot 2.7.x
- **ORM**: MyBatis-Plus 3.x
- **数据库**: MySQL 8.0
- **连接池**: Druid
- **服务注册**: Nacos（部分服务）
- **服务调用**: OpenFeign
- **对象转换**: MapStruct 1.5.2
- **工具库**: Lombok, Hutool
- **API 文档**: Knife4j（Swagger 2.x）
- **缓存**: Redis
- **构建工具**: Maven（多模块）
- **父 POM**: dib-agent-parent 2.7.1-SNAPSHOT

---

## 三、公共包结构规范

所有服务遵循以下标准分层结构：

```
{基础包路径}/
├── aggregate/      # 聚合服务层（业务编排）
├── component/      # 可复用业务组件
├── config/         # 配置类
│   ├── constant/   # 常量定义
│   └── enums/      # 枚举定义
├── controller/     # 控制器层（REST API）
├── converter/      # 对象转换器（MapStruct）
├── entity/         # 实体类（数据库映射）
├── mapper/         # MyBatis Mapper 接口
├── model/          # 数据模型（DTO/VO/Req/Resp）
├── schedule/       # 定时任务
├── service/        # 服务层（MyBatis-Plus Service）
└── util/           # 工具类
```

各层职责详见下方"分层架构规范"章节。

---

## 四、命名规范

### 类命名规则

| 类型 | 格式 | 示例 |
|------|------|------|
| 实体类 | `{表名}Entity` | `ComDataIndexFuncEntity` |
| Controller | `{业务模块}{功能}Controller` | `ComDataIndexFuncController` |
| Aggregate | `{业务模块}{功能}Aggregate` | `ComDataIndexFuncAggregate` |
| Service 接口 | `I{业务模块}{功能}Service` | `IComDataIndexFuncService` |
| Mapper | `{业务模块}{功能}Mapper` | `ComDataIndexFuncMapper` |
| Converter | `{业务模块}{功能}Converter` | `ComDataIndexFuncConverter` |

> 所有服务的 Service 接口均带 `I` 前缀。

### 方法命名规则

#### Controller 层
- `get()` - 单个查询
- `page()` - 分页查询
- `list()` - 列表查询
- `listOfEnable()` - 查询激活列表
- `add()` - 新增
- `edit()` - 编辑
- `delete()` - 删除
- `enable()` / `disable()` - 激活/禁用

#### Model 命名
- 请求对象: `{功能}{操作}Req`（如 `DataIndexFuncAddReq`）
- 响应对象: `{功能}Resp`（如 `DataIndexFuncResp`）
- 查询对象: `{功能}Query`（如 `DataIndexFuncQuery`）

### 变量命名
- 局部变量: camelCase
- 常量: UPPER_SNAKE_CASE
- 成员变量: camelCase

---

## 五、编码规范

### 代码质量
- 单个方法不超过 50 行，复杂逻辑拆分为私有方法
- 单个类不超过 500 行，职责单一
- 类注释必须包含 `@author` 和 `@since`
- 公共方法必须有 JavaDoc 注释
- 复杂逻辑必须有行内注释说明"为什么"

### 异常处理
- 使用 `BizValidateException` 抛出业务异常
- 异常信息清晰明确，不要吞掉异常

### 日志规范
- 使用 `@Slf4j` 注解
- 日志格式: `【模块名】操作描述：详细信息`
- 禁止使用 `System.out.println()`
- 禁止打印敏感信息（密码、密钥）
- 禁止在循环中打印日志

### 注解使用规范

```java
// Lombok
@Data @Slf4j @NoArgsConstructor @AllArgsConstructor

// Spring
@RestController @Component @Service @Autowired
@RequestMapping @PostMapping @GetMapping @DeleteMapping
@RequestBody @Validated

// MyBatis-Plus
@TableName("table_name") @TableId @TableField

// Swagger
@Api(tags = "模块名") @ApiOperation("操作说明")
@ApiModel("模型说明") @ApiModelProperty("字段说明")

// 校验
@NotNull @NotEmpty @NotBlank @Size @Pattern
```

---

## 六、数据库规范

### 表命名
- 格式: `{模块前缀}_{业务名}_{表名}`，全小写，下划线分隔，单数形式

### 基础字段（BaseEntity）

所有业务表必须包含：

```sql
id BIGINT PRIMARY KEY COMMENT '主键',
del_flag TINYINT(1) DEFAULT 0 COMMENT '删除标识',
add_user_id VARCHAR(50) COMMENT '创建人账号',
add_user_name VARCHAR(100) COMMENT '创建人姓名',
add_time DATETIME COMMENT '创建时间',
update_user_id VARCHAR(50) COMMENT '更新人账号',
update_user_name VARCHAR(100) COMMENT '更新人姓名',
update_time DATETIME COMMENT '更新时间'
```

### SQL 规范
- 禁止使用 `SELECT *`
- 使用逻辑删除（`del_flag = 1`），禁止物理删除
- 更新时必须有 WHERE 条件
- 查询必须有索引，避免全表扫描

---

## 七、分层架构规范

```
Controller → Aggregate（可选）→ Service → Mapper → 数据库
```

### 各层职责

**Controller**: 接收请求、参数校验、调用 Aggregate 或 Service、返回 `GeneralResult<T>`

**Aggregate**: 业务编排、调用多个 Service、业务校验、对象转换。禁止直接操作数据库。

**Service**: 继承 `IService<Entity>`，提供 CRUD。禁止编写复杂业务逻辑。

**Mapper**: 继承 `BaseMapper<Entity>`，复杂查询在 XML 中定义。

### 层间调用规则
- 允许: Controller→Aggregate, Controller→Service（简单场景）, Aggregate→Service, Service→Mapper
- 禁止: Controller→Mapper, Aggregate→Mapper, Service→Aggregate, 跨层调用

---

## 八、API 设计规范

### 响应格式
统一使用 `GeneralResult<T>` 包装：

```json
{ "code": 200, "message": "success", "data": {}, "timestamp": 1234567890 }
```

### 分页规范
- 请求: `pageNum`（从 1 开始）、`pageSize`
- 响应: `PageResp<T>` 包含 `total` 和 `records`

---

## 九、MyBatis-Plus 使用规范

```java
// 单条查询
service.lambdaQuery()
    .eq(Entity::getId, id)
    .eq(Entity::getDelFlag, false)
    .one();

// 分页查询
service.lambdaQuery()
    .like(StrUtil.isNotBlank(keyword), Entity::getField, keyword)
    .eq(Entity::getDelFlag, false)
    .orderByDesc(Entity::getUpdateTime)
    .page(Page.of(query.getPageNum(), query.getPageSize()));

// 批量更新
service.lambdaUpdate()
    .in(Entity::getId, idList)
    .set(Entity::getEnableFlag, true)
    .set(Entity::getUpdateTime, new Date())
    .update();
```

---

## 十、对象转换规范（MapStruct）

```java
@Mapper(componentModel = "spring")
public interface XxxConverter {
    XxxConverter INSTANCE = Mappers.getMapper(XxxConverter.class);
    XxxEntity fromAddReqToEntity(XxxAddReq req);
    XxxResp fromEntityToResp(XxxEntity entity);
    List<XxxResp> fromEntityListToRespList(List<XxxEntity> list);
}
```

---

## 十一、事务管理规范

```java
@Transactional(rollbackFor = Exception.class)
public void batchSave(List<XxxEntity> list) { ... }
```

- 多表操作、批量操作必须使用事务
- 事务方法不能是 private
- 避免长事务，避免在事务中调用外部服务

---

## 十二、配置管理规范

- 敏感信息使用环境变量注入（`${DB_USERNAME}`），禁止硬编码
- 功能开关默认值为 `false`，通过配置文件启用
- 各环境配置通过 `application-{profile}.yml` 隔离

---

## 十三、AI 特别约束（公共）

- 不确定的需求先问，不要猜测
- 改动现有代码前，先说明影响范围
- 生成代码后必须自检是否符合本宪法
- 发现宪法与需求冲突时，优先遵守宪法并提出
- 修改文件前必须先读取完整内容
- 大文件修改使用 `strReplace` 而不是重写
- 新建文件必须放在正确的目录
- 修改 Mapper XML 时必须保持 namespace 正确
- 修改 Entity 时必须同步更新 Converter
- 新增 API 时必须添加 Swagger 注解

---

## 十四、如何新增一个业务模块

1. 在 `entity` 包下创建实体类（继承 `BaseEntity`）
2. 在 `mapper` 包下创建 Mapper 接口（继承 `BaseMapper<Entity>`）
3. 在 `service` 包下创建 Service 接口（`I` 前缀）和实现类
4. 在 `model` 包下创建 Req/Resp/Query 对象
5. 在 `converter` 包下创建 Converter 接口
6. 在 `aggregate` 包下创建 Aggregate 类
7. 在 `controller` 包下创建 Controller 类
8. 在 `resources/mapper` 下创建 XML 文件（如需复杂查询）

---

**本宪法最终解释权归 DIB Agent 项目团队所有。**
