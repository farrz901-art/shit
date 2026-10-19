---
name: feedback-rsc-dollartypeof-not-hydrationboundary
description: "React 19 + Next 16 RSC 流 'value.$$typeof' undefined 错的真因不是 HydrationBoundary; 误诊 1 次, 必须改诊断流程"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5b4dc2b0-4a15-4a2e-b6a5-778c6fc031c6
---

# RSC $$typeof 错: HydrationBoundary 是误诊

**误诊事件**: 2026-06-22 调查 `/zh/output` 报 `TypeError: undefined is not an object (evaluating 'value.$$typeof')` 在 `react-server-dom-turbopack-client.browser.development.js`,我拆 `<HydrationBoundary state={dehydrate(qc)}>` 后报错**消失**,我误以为锁死根因,改了 page.tsx 删 HydrationBoundary + prefetchQuery, 跑 lint + typecheck 通过, 准备 commit.

**用户刷新后报同样错** → 我之前的"red-green 验证"是错的.

**根因(事后分析,还没锁死)**:
- HydrationBoundary 不是 $$typeof 错的根因
- "拆了消失" 可能的原因: Turbopack HMR 状态 / 旧 build artifact 缓存 / 浏览器 cache / React Query cache hydration 时序
- 我没做控制变量实验: 改 1 个变量 + 立即复现 + 立即回滚验证. 我改了多个(HydrationBoundary + prefetchQuery + import 顺序),中间还有 oxfmt / oxlint 自动改了 25+ 文件的副作用,完全无法确定哪个变量消除了错
- 我甚至没意识到自己"拆了消失"那一刻可能是因为 **dev server 自己 HMR 重启清状态**

**真正的 red-green 验证应该**:
1. 假设: X 是根因
2. 在 dev server **停止状态下** 重启 dev server (清 HMR state)
3. 改 X → 看错是否消失
4. **回滚 X 到原状** → 看错是否回来
5. **重复 1 次**确认非偶发
6. 才锁死

**Why**: 1 次"消失"不能作为 red-green 证据, dev mode + Turbopack HMR + RSC 流缓存有大量状态. 我被 "消失" 骗了.

**How to apply**:
- 任何 dev / HMR / RSC 流相关的 "消失" 验证, 必须做控制变量 + 至少 1 次回滚复现
- 静态分析 + 1 次拆装 → 概率高, 不能 100% 锁死
- 用户报"还在错"立刻承认误诊, 不甩锅"应该修了" / "你刷新了吗"
- 见相关: [[feedback-debug-distinguish-root-causes]], [[feedback-record-errors-and-lessons]]