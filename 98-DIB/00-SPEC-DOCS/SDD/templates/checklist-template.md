# 宪法自检清单

> 每个任务完成后执行，确保代码符合公共宪法 + 专属宪法规范。

---

## 通用自检（所有模块）

### 分层架构
- [ ] Controller 只做参数校验和调用，不含业务逻辑
- [ ] Aggregate 只调用 Service，不直接操作 Mapper
- [ ] Service 继承 `IService<Entity>`，实现类继承 `ServiceImpl`
- [ ] Mapper 继承 `BaseMapper<Entity>`

### 命名规范
- [ ] 实体类命名：`{表名}Entity`
- [ ] Service 接口命名：`I{模块}{功能}Service`（带 `I` 前缀）
- [ ] Controller 方法命名符合规范（page/list/add/edit/delete/enable/disable）
- [ ] Model 命名符合规范（Req/Resp/Query 后缀）

### 注解规范
- [ ] Controller 类有 `@Api(tags = "...")` 和 `@RestController`
- [ ] Controller 方法有 `@ApiOperation`
- [ ] Entity 有 `@TableName`、`@Data`，继承 `BaseEntity`
- [ ] Service 实现类有 `@Service`
- [ ] Aggregate 有 `@Component` 和 `@Slf4j`
- [ ] Converter 有 `@Mapper(componentModel = "spring")`

### 代码质量
- [ ] 单个方法不超过 50 行
- [ ] 类注释包含 `@author` 和 `@since`
- [ ] 公共方法有 JavaDoc 注释
- [ ] 无 `System.out.println()`
- [ ] 无未使用的 import
- [ ] 无魔法数字（已定义为常量）

### 数据库操作
- [ ] 查询条件包含 `.eq(Entity::getDelFlag, false)`
- [ ] 新增时调用 `entity.setAddUser()`
- [ ] 更新时调用 `entity.setUpdateUser()` 或手动 set 更新字段
- [ ] 无 `SELECT *`
- [ ] 删除使用逻辑删除（`del_flag = 1`）

### 异常处理
- [ ] 业务异常使用 `BizValidateException.of("...")`
- [ ] 无吞掉异常的空 catch 块
- [ ] 日志格式：`【模块名】操作描述：详细信息`

### API 响应
- [ ] 返回 `GeneralResult<T>` 包装
- [ ] 分页返回 `PageResp<T>`

---

## data 模块专属自检

- [ ] Groovy 脚本使用脚本模式（非类模式）
- [ ] 通过 `getBinding().getVariable(DibIndexConst.INDEX_SCRIPT_PARAM_NAME)` 获取 `calcReq`
- [ ] 日志使用 `LoggerFactory.getLogger(this.class)`，不使用 `@Slf4j`
- [ ] 动态参数通过 `IndexSqlUtil` 获取（tableName、dataSourceCode）
- [ ] 使用 `SpringContextUtil.getBean(DataQueryInfrastructure.class).queryMaps(...)` 执行查询
- [ ] SQL 使用 CTE 链式查询，动态字段使用 Groovy 字符串插值
- [ ] 输出字段包含 `dim_report_date`
- [ ] 包声明与文件路径一致

---

## rule 模块专属自检

- [ ] DAG 构建时有环检测逻辑
- [ ] MVEL 表达式执行有异常捕获和日志
- [ ] 新增定时任务有对应配置开关，默认 `false`
- [ ] 缓存变更时同步更新缓存失效逻辑

---

## report 模块专属自检

- [ ] Word 渲染有临时文件清理逻辑
- [ ] 变量计算 DAG 有环检测
- [ ] Aviator 表达式执行有异常捕获和日志
- [ ] toubao 模块代码在 `com.dib.agent.toubao` 包下

---

## extract 模块专属自检

- [ ] Redis Streams 消费者有消息确认逻辑
- [ ] 异步执行器有完整异常捕获，不静默失败
- [ ] 邮件发送失败不影响主业务流程（try-catch 包裹）
- [ ] 新增功能有对应配置开关，默认 `false`
- [ ] 开放接口（`controller/open/`）有鉴权逻辑
