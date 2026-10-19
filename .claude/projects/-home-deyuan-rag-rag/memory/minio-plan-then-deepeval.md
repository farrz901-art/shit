---
name: minio-plan-then-deepeval
description: "After MinIO 12-task plan completes, user wants to start deepeval-replace-llamaindex plan"
metadata: 
  node_type: memory
  type: project
  originSessionId: 20df34db-3217-47b0-9511-2f09132e0f81
---

MinIO 接入 plan (`docs/superpowers/plans/2026-06-16-rag-minio-integration.md`, 12 task) 跑完后, **接着启动** DeepEval 替换 LlamaIndex plan (`docs/superpowers/plans/2026-06-16-deepeval-replace-llamaindex.md`).

**Why:** 用户 2026-06-17 在 MinIO 计划跑 Task 4 时明确: "开发完之后就继续开发这个 [deepeval plan]"

**How to apply:** MinIO Task 1-12 全部 done (含 2-stage review) 后, 不要停在 final commit. 直接 dispatch DeepEval plan 的 implementer subagent. 同样的 subagent-driven-development 流程 (background dispatch + 2-stage review). 任何 commit 前都遵守 删 BFF route 必须跑契约测试, 改前端 URL 顺序 (后端先实现 → 前端改 URL → 最后删 BFF).
