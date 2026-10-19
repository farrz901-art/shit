---
name: feedback-vitest-unhandled-rejection-mock-rejected-value
description: "vitest test 用 mockRejectedValueOnce + React 19 use(promise) 模式会触发 unhandled rejection, 改 mockImplementationOnce 同步 throw"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

在 vitest test 里 mock 一个被 React 19 `use(promise)` 消费的 promise, 用 `mockRejectedValueOnce` 创建 rejected promise, **会触发 unhandled rejection** (vitest 报 1 error, 不是 fail, 但污染测试输出). 改用 `mockImplementationOnce(() => { throw new Error(...) })` 同步 throw 消除.

**Why:** Sprint 1.6 改 use(promise) 模式后, dataset-documents `page.test.tsx` 有个 case mock `difyListDocuments` rejected. Page() 内部 `use(promise)` 还没消费, promise 一直 rejected 无人 observe → unhandled rejection. 之前 4 unhandled rejection (commit 9f4af4d 时还有), 修复时漏了 dataset-documents 这 1 个, commit `8221378` 补修. 用户 2026-06-14 反馈 "为什么留一个 error 不处理" 指出我之前偷懒 (说成"已知 Sprint 1.6 同型" 跳过).

**How to apply:**
1. vitest 报 "X unhandled error" 找不到 fail test → 看 stack 找 `mockRejectedValueOnce` 用法
2. 改 `mockImplementationOnce(() => { throw new Error("msg") })` 同步 throw
3. 调用方 Page() 同步 throw 也被 try/catch 包, 测试 expect err toBeInstanceOf(Error) 仍通过
4. 不要说"已知"跳过 unhandled rejection — per `feedback-debug-distinguish-root-causes` 区分根因, 修就修干净
5. 跑全量 vitest 期望 0 error (只 1 todo 占位, 0 unhandled), 才算干净

**Related:** [[feedback-asyncio-sem-needs-peak-test]] 类似 — async 错误未消费触发静默问题; 跟 `feedback-debug-distinguish-root-causes` 同型 — 不能把 unhandled 归"已知"跳过.
