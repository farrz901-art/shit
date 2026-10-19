---
name: feedback-never-delete-local-data-files-without-explicit-permission
description: "禁止删用户本地数据文件 (.db / .sqlite / .jsonl / .csv 等), 即便 handoff plan 说\"全删\", 必须用户手操作"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d365816f-f987-4fea-93d9-5415bde993bf
---

**禁止 AI 删用户本地数据文件**, 即便:
- handoff plan 写"全删"
- task label 包含 "delete"
- 备份已存在 (.archive)
- 用户选了 "A: 全部清理"

适用文件类型:
- SQLite (.db / .sqlite / .sqlite3)
- 数据库 dump (.sql / .dump)
- 数据集文件 (.csv / .jsonl / .parquet)
- 用户本地生成的大文件 (.log / .out / .tmp)

**Why**: 2026-06-15 SQLite→PG 迁移, 用户选 A "全部清理 (删测试残留 + 删 SQLite)", 我执行了 DELETE FROM accounts (成功, 测试残留清掉), 但接下来 `rm app.db ingest_tasks.db kg_audit.db` 被 auto mode 拦. 用户明确说 "我自己删, 记住你自己不能删这种文件, 需要我操作".

**How to apply**:
- DELETE FROM / DROP TABLE 这种 SQL 删库操作也谨慎, 报"已执行"前先核对用户授权
- 数据搬迁 / 数据删除 / 文件清理 类操作: AI 只做"准备 + 验证", 不做"最终删除"
- 如必须删, 走 AskUserQuestion 显式二选 (用户原话含"可以删 / 我授权")
- 同理: 删 .gitignore 内文件, 删 git tracked 文件, 改用户 .env / config, 都走显式授权
- 跟 [[feedback-never-revert-user-edits]] 配套: 用户的本地文件, 我都只读不写不删
