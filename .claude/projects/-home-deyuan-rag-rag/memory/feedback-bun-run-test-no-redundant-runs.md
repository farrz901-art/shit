---
name: feedback-bun-run-test-no-redundant-runs
description: "跑 `bun run test` 必须一次定位到具体 error + 文件，不要发现失败后再次重跑找 detail；每次 task 完成才能跑全量 test，禁止为了确认反复重跑"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c0af4e04-e5b9-4a48-b332-19f579a3ee44
---

跑 `bun run test` 时：**单次运行**必须能从输出直接拿到 (1) 失败的具体文件路径 (2) 失败的具体测试名 (3) assertion 错误原因 / 堆栈。**禁止**在第一次看到 "X failed" 后再跑一遍来"找具体哪个 test 挂了"。

具体操作：

1. **第一次跑全量前**，用 `vitest run --reporter=verbose` 或先一次 single-pass 默认 reporter。`bun run test` 默认就是 verbose（带 `⎯⎯⎯⎯` 失败框、文件路径:行号、expected/received）。如果默认输出不够，先用 `bunx vitest run <path-to-suspect>` 缩小到单文件，**不要**重跑全量。
2. **拿到 fail 列表后**，用 `Read` 工具直接打开失败文件对应行（不需要再跑 test）。vitest 错误已经给了 `app/path/file.test.tsx:98:35` 这种行号。
3. **判定 pre-existing**：对比 git 改动范围 — 如果失败文件不在本次改动的 import 依赖图里，直接归为 pre-existing（参考 [code-quality spec baseline 14 fail](packages/web/CLAUDE.md#代码质量清理总结-2026-06-19-code-quality-spec)），不要试图修复。
4. **修复后**才重跑，且只跑受影响的子集：
   ```bash
   bunx vitest run app/[locale]/admin/users   # 单目录
   bunx vitest run app/[locale]/admin/users/page.test.tsx  # 单文件
   ```
5. **最终全量验证**只在 task 收尾时跑一次 `bun run test` 确认无新增 fail。

**反例**（浪费时间的典型操作）：

- ❌ 跑全量看到 "5 failed" → 再跑全量想看具体哪个 test
- ❌ 跑全量看到 assertion 失败 → 再跑全量想看堆栈完整
- ❌ 修了一个文件 → 跑全量 test → 又发现 fail → 再跑全量

**Why**: 单次 `bun run test` 跑 156 文件 ~700 tests 约 30-60s（开了 coverage instrumentation 慢 2-3 倍，到 90-155s）。在 719 测试 + 14 pre-existing fail 的规模下，"跑全量找 fail" 一个回合浪费 90-155s，2-3 个回合 = 5 分钟。叠在 156 file 项目上，**LSP 抓红 / Read 单文件 / 修后再跑单文件** 远比反复全量快。

**How to apply**: 任何包含 `bun run test` / `bunx vitest run` 的任务，复盘执行计划时问自己"我即将跑几次？"——超过 1 次的必须先 Read 失败文件再决定下一次跑什么。
