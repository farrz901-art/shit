---
name: feedback-fix-root-cause-not-remove-feature
description: 修 bug 不能通过去掉功能来回避，要找到真因修复，保留功能完整
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

修 bug 时不能通过"去掉导致问题的功能"来回避问题。用户要求的是 hover 效果保留但不改变布局导致滚动条闪现。

**错误做法**：直接删掉 `hover:shadow` 效果 → "问题消失了" → 但功能也丢了
**正确做法**：找到为什么 box-shadow（不影响布局）会触发滚动条 → 修复根因

这次的真因可能是：
1. 页面 `overflow-y: auto` + 某些边界条件
2. 或者浏览器渲染 bug（shadow 抗锯齿导致 subpixel 溢出）
3. 或者有其他 CSS 规则在 hover 时影响了布局

**How to apply**: 遇到 UI bug 时，先用 DevTools 检查 hover 前后的 layout 变化（Computed → 宽高），找到真正变化的属性，再针对性修复。不要直接删功能。
