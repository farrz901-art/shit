---
name: feedback-clarify-ambiguous-ui-instructions
description: "模糊的 UI 改法指令 (如\"在表格里\" / \"加弹框\") 必须先问清: 哪个表格? 弹框/展开? 触发方式?, 不能凭\"听起来差不多\"就动手"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

模糊的 UI 改法指令必须先问清细节再动手, 不能凭"听起来差不多"实现.

**Why:** 2026-06-10 用户让我"点击失败弹框显示失败原因", 我理解成在 `/evaluate` 列表页弹 Dialog, 实现完后用户说"改错了, 应该是详情页表格里表格内展开". 我的改动还让失败评估跳不进详情页.

**How to apply:** 接到 UI 改法指令时, 先问:
1. **具体位置**: 哪个组件 / 哪个表格 / 哪个 tab?
2. **交互方式**: Dialog 弹框 / Popover / Tooltip / 表格内展开 / 抽屉?
3. **触发方式**: 点击 / hover / 自动展开?
4. **跟现有交互的冲突**: 会不会破坏别的流程 (如"展开"跟"跳详情"冲突)?

涉及以下组件时尤其要先问: SampleTable, EvalListRow, StatusBadge, 任何列表/表格/详情页.

**关联:** [[feedback-clarify-ambiguous-instructions]] (通用规则)
