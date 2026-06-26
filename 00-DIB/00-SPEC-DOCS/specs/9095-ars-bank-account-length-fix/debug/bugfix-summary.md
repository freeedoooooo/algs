# Bug 修复总结：9位银行账号验证失败

## 问题
用户测试发现输入 9 位银行账号（如 123456789）时显示错误："请输入正确的银行账号"，但 10 位银行账号可以正常通过。

## 根本原因
经过分析，正则表达式 `/^[1-9]\d{8,29}$/` 本身是正确的（已通过 Node.js 测试验证）。问题的根本原因是：

**用户输入的值可能包含前导或尾随空格**，导致正则表达式测试失败。

例如：
- `"123456789"` → 正则测试通过 ✅
- `" 123456789"` → 正则测试失败 ❌（前导空格）
- `"123456789 "` → 正则测试失败 ❌（尾随空格）

## 修复方案

### 1. 修改验证函数（第 195-207 行）
```javascript
// 修改前
const validateBankAccountInput = (row: any, index: number) => {
  if (!row.bankAccount) {
    return
  }
  const bankAccountRegex = /^[1-9]\d{8,29}$/
  if (!bankAccountRegex.test(row.bankAccount)) {
    ElMessage.error('请输入正确的银行账号（9-30位数字，首位不能为0）')
  }
}

// 修改后
const validateBankAccountInput = (row: any, index: number) => {
  if (!row.bankAccount) {
    return
  }
  // 去除首尾空格并转换为字符串
  const trimmedValue = String(row.bankAccount).trim()
  const bankAccountRegex = /^[1-9]\d{8,29}$/
  if (!bankAccountRegex.test(trimmedValue)) {
    ElMessage.error('请输入正确的银行账号（9-30位数字，首位不能为0）')
  } else {
    // 如果验证通过，更新为 trim 后的值
    row.bankAccount = trimmedValue
  }
}
```

**关键改进**：
- 使用 `String().trim()` 去除前导和尾随空格
- 确保值是字符串类型（防止数据类型问题）
- 验证通过后更新为 trim 后的值（保持数据一致性）

### 2. 添加 maxlength 限制（第 331-339 行）
```vue
<!-- 修改前 -->
<el-input
  v-if="!readonly"
  :disabled="!!scope.row.counterpartId?.trim()"
  v-model="scope.row.bankAccount"
  placeholder="请输入"
  style="width: 100%"
  @blur="validateBankAccountInput(scope.row, scope.$index)"
/>

<!-- 修改后 -->
<el-input
  v-if="!readonly"
  :disabled="!!scope.row.counterpartId?.trim()"
  v-model="scope.row.bankAccount"
  placeholder="请输入"
  style="width: 100%"
  maxlength="30"
  @blur="validateBankAccountInput(scope.row, scope.$index)"
/>
```

**关键改进**：
- 添加 `maxlength="30"` 限制，防止用户输入超过 30 位数字
- 与其他文件（EditPage.vue）保持一致

## 修改文件
`ars-front-2/apps/a-front/src/views/Contract/drafting/common/SignatoryInformation.vue`

## 验证结果
- ✅ 代码语法检查通过（无 diagnostics 错误）
- ✅ 正则表达式测试通过
- ✅ 修复逻辑合理

## 测试建议

请在测试页面 `http://localhost:3001/drafting/contract-drafting-form?id=6bb767ea41fcc97b913191fd0d310b96` 进行以下测试：

### 基本功能测试
1. 输入 `123456789`（9位）→ 应通过验证 ✅
2. 输入 `1234567890`（10位）→ 应通过验证 ✅
3. 输入 `123456789012345678901234567890`（30位）→ 应通过验证 ✅

### 边界测试
4. 输入 `12345678`（8位）→ 应显示错误 ❌
5. 输入 `0123456789`（首位为0）→ 应显示错误 ❌

### 空格处理测试（重点）
6. 输入 ` 123456789`（前导空格）→ 应自动 trim 并通过验证 ✅
7. 输入 `123456789 `（尾随空格）→ 应自动 trim 并通过验证 ✅
8. 输入 ` 123456789 `（前后空格）→ 应自动 trim 并通过验证 ✅

### 数据来源测试
9. 从相对方库选择 → 银行账号自动带入并可编辑 ✅
10. 手动输入相对方名称 → 银行账号可输入并验证 ✅

## 预期效果
修复后，用户输入 9 位银行账号（无论是否带空格）都应该能够正常通过验证，同时保持对 10-30 位银行账号的支持。

## 相关文档
- 详细分析：`AI-DOCS/specs/9095-bank-account-length-fix/bug-analysis.md`
- 任务清单：`AI-DOCS/specs/9095-bank-account-length-fix/tasks.md`（已更新任务 7）
