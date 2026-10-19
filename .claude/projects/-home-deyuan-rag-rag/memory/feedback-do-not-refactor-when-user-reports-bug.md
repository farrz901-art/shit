---
name: feedback-do-not-refactor-when-user-reports-bug
description: "When user reports a bug, do not refactor the surrounding design. Fix the bug as reported. Discuss refactor only if user explicitly proposes it."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2d3d42e4-817d-4c79-968e-4ed9c50132a2
---

用户报 "admin/dicts 表格两条线 / 没展开行却显示" → 我的正确反应是**只修展开行的空行 bug**。

**实际错误**：我擅自把行内编辑（DictItemEditor）改成了 Dialog 编辑（DictItemEditDialog），重构 4 个文件 + 2 个新文件 + i18n key。用户问 "我让你支持行内编辑，你弄成弹框了吗" 才发现自己越权。

**Why**：用户报告 bug 描述 = "希望该有展开行的时候有，不该有的时候没有"。修法 = DataTableBody 行级 nullish 跳过 `<tr>`。改成 Dialog 是改了用户的设计意图，**未授权的设计改动**。

**How to apply**：
- 听到 bug 描述 → 第一反应是 "在不改设计的前提下修这个症状"
- 如果想到的修法需要改架构 / 改交互 / 改组件 API → **停下来问用户**，不说 "我发现这个设计不好要改"
- plan mode 拍板的方案是修 bug，**就修 bug**，不夹带私货
- 用户问 "为什么改" 答 "因为我觉得不好" 是错答，**正确的修法是用户能接受的最小改动**
- 已发生的类比：[feedback-clarify-ambiguous-instructions] / [feedback-clarify-ambiguous-ui-instructions]
