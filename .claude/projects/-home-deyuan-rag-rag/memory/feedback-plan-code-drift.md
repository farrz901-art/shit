---
name: feedback-plan-code-drift
description: "Plan 文档 跟实施 必须同步维护, checkbox 0 完成不一定意味着 0 实施, 也可能实施完整但 plan 没人打勾"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

**实施 Plan checkbox 0 完成不一定意味着 0 实施**, 也可能实施完整但 plan 文档没人维护. 反之亦然.

**Why:** 用户 2026-06-15 反馈 "审批功能去哪了, 没看到页面". 我快速扫发现: `docs/superpowers/plans/2026-06-13-approval-system.md` 119 个 checkbox 全部未勾选 (`[ ]`), 以为功能没实施. 但实际查 git log: 14+ commit 完整实施 (后端 4 文件 + 前端 964 行 + 5 测试文件 + approvalsApi client). 入口不可见根因: `header.tsx` nav 漏了 `<NavLink href="/submissions">`, i18n "审核中心" 翻译已就位但 UI 入口未暴露.

Plan 漏写 nav 任务 (P2 阶段 "前端 /submissions/* UI" 漏 nav 链接), 实施时没人核对 plan 跟代码. 文档跟实施脱节 → 用户以为功能缺失.

**How to apply:**
1. **读 plan 时先看 git log**, 不要因为 0 checkbox 就断定没实施
2. **plan checkbox 维护是工程实践**: 每 commit 实施时同步勾选对应 plan task, 别累积
3. **plan 应包含"端到端集成"任务**: 入口 (nav) / middleware / 权限 / 跨组件 wiring, 不能漏
4. **完成 plan 时跑自我检查**: "用户从 UI 怎么找到这个功能?" 每个 P2/P3 阶段 plan 必有"入口暴露"任务
5. **如果 plan 跟代码脱节**: 优先补 plan (加 nav 任务, 标完成), 再写新功能, 别让 plan 永远是历史快照

**Related:** [[feedback-check-old-code-before-refactor]] 同型 — 改之前先看现有状态; 跟 `feedback-debug-distinguish-root-causes` 配对 — "没看到页面" 的根因可能是入口/权限/状态, 不一定是功能缺失.
