# 分支管理规范

> 适用服务：parent / auth-server / gateway / auth-resource / mdm / extract / report / data / rule / dg

---

## 分支命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 功能开发 | `feature/{编号}-{功能描述-kebab-case}` | `feature/0001-data-qe-industry-deviation` |
| Bug 修复 | `fix/{编号}-{问题描述-kebab-case}` | `fix/9095-bank-account-length-fix` |
| 紧急修复 | `hotfix/{编号}-{问题描述-kebab-case}` | `hotfix/9087-contract-effective-date` |

分支编号与 `specs/` 目录编号保持一致。

---

## 分支生命周期

```
main（或 master）
  └── develop
        └── feature/{编号}-{功能描述}   ← 开发分支
              ↓ PR / MR
        develop
              ↓ 测试通过后合并
        main
```

1. 从 `develop` 切出功能分支
2. 开发完成后提 PR/MR 合并回 `develop`
3. 测试通过后由负责人合并到 `main`
4. 合并后删除功能分支

---

## 提交信息规范

格式：`{type}-{编号}: {描述}`

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不影响功能） |
| `docs` | 文档变更 |
| `chore` | 构建/配置变更 |
| `perf` | 性能优化 |
| `test` | 测试相关 |

示例：
```
feat-0001: 新增行业算子 IndustryOperator
feat-0003: 实现同比变动率算子 calc 主函数
fix-9095: 修复银行账号长度校验问题
refactor-0002: 重构内控调整因子计算逻辑
docs-0003: 更新同比变动率算子需求文档
chore-0001: 更新 pom 依赖版本
```

### 多任务提交建议

一个功能通常包含多次提交，建议每完成一个 tasks.md 中的子任务提交一次：

```
feat-0005: 新增 QeYoyChangeRate 脚本文件及包结构
feat-0005: 实现 calc 主函数和参数获取逻辑
feat-0005: 实现 buildSql CTE 链式查询
feat-0005: 完成宪法自检和边界条件验证
```

---

## AI 操作约束

- AI 不负责创建或切换 Git 分支，由开发者手动操作
- AI 生成的代码直接修改工程文件，不需要额外的分支操作
- 如需说明影响范围，在 `design.md` 的"影响范围"章节中列出涉及文件
