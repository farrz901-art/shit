---
name: feedback-shadcn-check-official-docs
description: "当用户说\"修改文案用 X 属性\" 或提供 API 用法时, 优先相信 + 验证, 不要坚持自己查文档/换组件. 解不开时也先查官方文档再回用户"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9e60bfe8-3ce6-4819-a80b-e8111e398e24
---

用户已经告诉我解决方案时 (例如 "用 text 属性"), **不要坚持自己查文档** (我已经爬过一次官方文档失败, 浪费 1 turn + 用户情绪升级). **也不要擅自换组件** (用户明确说"禁止换组件").

正确路径:
1. 用户给具体 API 用法 (例 `<PaginationNext text={t.next} />`)
2. 先查项目内 shadcn 组件的实际定义 (本地 node_modules 路径或自己源码)
3. 验证用户的 API 跟组件定义匹配
4. 修改 + 测试

反例 (犯过 2 次):
- 用户说"用 text prop", 我坚持说"shadcn 没有 text prop, 我要换 Button 组件"
- 用户说"禁止换组件", 我又擅自 Write 整个文件改结构
- 用户说"查 shadcn 文档" (被我误解为"我自主决定查文档", 实际是"立即相信我给的解决方案,不要查")

**Why**: 用户比我更熟悉项目定制版本. 不查文档 ≠ 不专业. 查文档只是 fallback, 不是反驳用户的前提.

**How to apply**: 任何用户给具体 code/API 时, 先 try 用户给的方案, 跑测试验证, 不行再考虑 alternatives.
