---
name: feedback-asyncio-sem-needs-peak-test
description: "asyncio + Semaphore 限流的代码必须专门测并发峰值，漏写 async with sem: 块不会被功能测试发现"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 312b3b8d-ff70-492c-b82a-f9c6dba4f2c7
---

asyncio.Semaphore 限流必须配专门的"并发峰值"测试, 漏写 `async with sem:` 块时:

- 9/10 功能测试照过 (测的是结果对, 不是同时跑几个)
- 实际跑 6 题时 peak=6 而非 2, 等于没限流
- 没警告没异常, 默默 0 限流

**Why:** 2026-06-05 写 `scripts/rag_eval/batch_eval.py` 时, 第一次重构加了 `asyncio.Semaphore(concurrency)` 但忘了把 Dify+RAGAS 调用包到 `async with sem:` 块里. 9 个功能测试都过, 第 10 个测峰值的测试发现 peak=6 才暴出来. (测试代码: `tests/test_rag_eval.py::test_run_batch_concurrency_limits_simultaneous_calls`)

**How to apply:** 凡是 `asyncio.Semaphore` / `asyncio.Lock` / `asyncio.BoundedSemaphore` 限流的并发代码, 单测必须包含:
1. mock 异步函数, 在入口/出口对一个计数器 `in_flight` 增减
2. 跑 N 个任务 (N > 限流数), 断言 `max(in_flight) == 限流数` 且 `max(in_flight) <= 限流数`
3. 不能只测"全部跑完"或"结果对"

具体模式见 [[project-rag-pdf-pipeline]] 里的 `scripts/rag_eval/batch_eval.py` + `tests/test_rag_eval.py` 的 slow_achat 实现.
