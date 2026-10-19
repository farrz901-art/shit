---
name: feedback-debug-stop-after-root-cause-confirmed
description: 调试任务根因已 100% 确认（curl + 代码 + 调用链三连）后不要补跑"更全面"的测试；用户 2026-06-12 因此打断 "在干什么"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 676c65bd-7a50-4699-97de-77c402b8b1d8
---
**根因已 100% 确认后立刻收尾报告, 不要补跑 "更全面" 的测试 / 加更多 instrumentation.** 用户 2026-06-12 因此打断 "在干什么".

**Why:** 调试 /knowledge/qa 404 时:
1. 已经 curl 实测 4 个端点（POST/GET 404, /api/kg/stats 200, /health 200）
2. 已经读完整调用链（QASubmitForm → createQA → postJson → ${API_BASE}/api/knowledge/qa → FastAPI 404）
3. 已经看 FastAPI register_routers 全部 prefix（确认没 /api/knowledge/*）
4. TDD 改测试红 → 改实现 → 12/12 绿

**根因 100% 锁定后**, 我又跑 contract pytest "想更确认" —— 用户打断: "在干什么". uv 装 pymupdf 跑 6 分多钟还 MemoryError, 完全冗余.

**How to apply:**
- 根因三连 (curl + 代码 + 调用链) 已确认 → 直接进 Phase 4 (写 failing test → 改实现 → 验证) → 收尾报告
- 不要加跑:
  - 整套 vitest "确认没破坏" (改的文件相关 vitest 绿就够)
  - contract test "再确认" (FRONTEND_EXPECTS 是直连列表, BFF-only 路径本来就不在里面, 跑也白跑)
  - e2e (Phase 4 验证靠 vitest 单元测试, e2e 是最终阶段才用)
- 修复后跑 `bun run test <我改的文件相关>` + `bun run typecheck` 即可
- 看 git diff + 报告结论

**自检 (根因已锁):**
- [ ] curl 实测坏路径 404? (✓)
- [ ] curl 实测好路径 200? (✓ 排除"全部挂了")
- [ ] 调用的目标服务路由注册表 grep 过了? (✓ register_routers 全部 prefix)
- [ ] 调用链每跳都过代码确认? (✓ QASubmitForm → action → fetch)
→ 满足全部即收尾, 不再补 instrumentation

**关联:** [[feedback-debug-search-before-loop]] — 同源, 不要重复试错
