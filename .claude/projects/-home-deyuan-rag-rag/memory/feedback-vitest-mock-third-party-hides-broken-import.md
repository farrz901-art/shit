---
name: feedback-vitest-mock-third-party-hides-broken-import
description: "vitest 单元测试能抓坏 import 靠真 module load, 不要 mock 第三方库, 只 mock 自己控的 wrapper"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e14df16a-a6ec-4603-b9f3-e9386f9c08e5
---

vitest 单元测试能抓 broken import 的关键: **只 mock 自己控的 wrapper, 不 mock 第三方库**.

**Why**: 2026-06-17 登录页 bug. 我写了 `vi.mock("next-intl/navigation", () => ({ useRouter: ... }))`, 实际 next-intl 4.x 不再直接导出 useRouter, 但 mock 自己造了一个 useRouter → 真模块根本没被 load, 测试绿, dev server 跑才暴 "Export useRouter doesn't exist". 等于 mock 替代码绕过了 bug 检查.

**How to apply**:
- 业务代码 import 第三方 (next-intl, next/navigation, 各种 SDK) → vitest 不 mock 第三方
- 把第三方包一层本地 wrapper (例 `i18n/navigation.ts` 用 `createNavigation(routing)` 导出 useRouter) → mock 这个本地 wrapper
- 这样第三方升级/破坏 API 时, 真模块 load 阶段就抛 TypeError, 测试红 — 不需要专门的 import guard 测试
- 同理: 任何"为了控制副作用而 mock 第三方"的做法, 都在用 mock 绕开类型/导入检查, 风险 > 收益

**反模式**:
- `vi.mock("第三方模块", () => ({...fake exports...}))` → 跟生产代码用了假的同一份 API
- `readFileSync + 正则` 静态 import guard → 字符串匹配, 不能验证 import 真能解析
- 专门的 "import guard" 单测 → 没必要, 上面那个 wrapper 模式已经隐式保证

**真实反证 (2026-06-17 login page.test.tsx)**:
- mock `next-intl/navigation` + 坏 import → 测试 3/3 绿 (mock 替掉坏模块)
- 改 mock 到本地 `@/i18n/navigation` + 真模块 `next-intl/navigation` + 坏 import → 测试 3/3 红 (TypeError: useRouter is not a function, 真模块 load 失败)
- 同样的 broken import, mock 策略不同结果不同 — 证明 mock 策略是关键
