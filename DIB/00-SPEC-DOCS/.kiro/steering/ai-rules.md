---
inclusion: always
---

# AI 工作规范

## 强制约束

- **禁止**使用 Kiro 内置 Spec 工作流，禁止生成文件到 `.kiro/specs/`
- 所有 spec 文件必须放在 `docs-c1/00 AI-DOCS/specs/{编号}-{模块}-{功能描述}/`
- 收到任何指令前，必须先完成模块确认步骤
- 未收到用户明确确认前，禁止自动进入下一阶段

## 初始化加载（必须）

收到 `START` 指令后，AI 必须立即读取以下文件：

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/workflow.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/commands/reference.md]]

## 模块专属宪法（确认模块后加载）

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-data.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-rule.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-report.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-extract.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-data-dg.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-auth-resource.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-auth-server.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-gateway.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-mdm.md]]

#[[file:docs-c1/00 AI-DOCS/SDD/constitutions/constitution-agent-parent.md]]
