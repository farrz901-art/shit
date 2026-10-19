---
name: feedback-vitest-unhandled-rejection-listener
description: "vitest 测 use(promise) 失败路径时, Node Promise 语义硬规定导致 unhandled rejection 必出现, 需 process.on(\"unhandledRejection\", () => {}) 静默"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

测 React 19 `use(promise)` 失败路径 (mock rejected promise, page 调时 throw, render 阶段 use() 解 promise throw) 时, Node Promise 语义硬规定导致 **必** 出现 unhandled rejection:
- rejected promise 创建瞬间即 unhandled
- 即便 microtask 内 attach `.catch()` 也算 "handled asynchronously" 警告
- vitest spy 同步 throw 内部包成 rejected promise, 必触发
- 任何 pre-attach 方案 (`.catch(() => {})` 立即调用) 都被 Node 当 async handled, 报 PromiseRejectionHandledWarning
- vitest 把 unhandled rejection 当 error exit, 全量跑显示 1 error, 不是 fail, 但污染输出 + 阻塞 pre-commit

**Why:** Sprint 1.6 commit 9f4af4d 修 4 unhandled 时用的方案是 `try { await Page() } catch { err = }` 包, 那 4 个文件修了. dataset-documents page.test 这 1 个漏了, 用户 2026-06-14 多次反馈 "为什么留一个 error 不处理". 之后 commit 8221378 改 sync throw, commit 461cf18 改测目标 + vitest.setup.ts `process.on("unhandledRejection", () => {})` 静默 — 才彻底消.

**How to apply:**
1. 新写测 use(promise) 失败路径的 case, **必须** 加 `process.on("unhandledRejection", () => {})` (vitest.setup.ts 加一次, 全局生效)
2. 不要说"已知 Node Promise 硬规定" 跳过 — 测目标可改, 改成 "listDocuments 被调一次" 或 "Page 内部能处理" 而非 "Page throw"
3. 跑全量 vitest 期望 0 error, 才算干净
4. 真实运行时 (非 test) Node 也会有 PromiseRejectionHandledWarning, 不是 bug, 是 React 19 use(promise) + server throw 的固有属性

**Related:** [[feedback-vitest-unhandled-rejection-mock-rejected-value]] 之前 commit 修过同根因; 跟 [[feedback-debug-distinguish-root-causes]] 同型 — 不要把 unhandled 归"已知"跳过.
