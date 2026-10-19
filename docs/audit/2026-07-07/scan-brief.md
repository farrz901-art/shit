# Scan Brief — 全栈代码体检 2026-07-07

## Finding Schema
```yaml
id: "{DIM}-NNN"
dimension: "security|concurrency|error|data|frontend|architecture"
severity: "critical|high|medium|low|info"
confidence: "high|medium|low"
title: "一句话 ≤ 80 字符"
file: "相对项目根路径"
line: N
description: "≥ 2 句中文说明"
evidence: "≥ 3 行真实代码引用 (Read 后复制)"
impact: "影响范围说明"
fix_sketch: "修复思路 1-3 句"
references: []
```

## 维度和必扫路径

### D1 Security
- 网络: ✅ WebSearch/WebFetch 允许 (查 deps CVE)
- 前端: `packages/web/app/[locale]/**` BFF routes, `lib/chat/**`, `lib/api/**`, `middleware.ts`
- 后端: `packages/service/src/auth/**`, `middleware/auth.py`, `src/models/user.py`
- 注意: CORS, SSRF(Neo4j Aura URL rewrite), IDOR(跨用户 data access), XSS(streamdown markdown 渲染), 依赖 CVE

### D2 Concurrency
- 网络: ❌
- 前端: `lib/chat/**` (SSE 双发射), `lib/rate-limiter.ts`, components/chat
- 后端: `packages/service/src/chat/**`, cron jobs, alembic migration
- 注意: TOCTOU, 双写, cron 重入, 锁, 缓存一致性

### D3 Error handling
- 网络: ❌
- 前端: `lib/api/**`, components/** error boundaries, RSC fetch
- 后端: `packages/service/src/**`
- 注意: bare except, 超时, retry, stacktrace 泄露, PII 进日志

### D4 Data integrity
- 网络: ❌
- 后端: `packages/service/src/models/**`, alembic migration, lookup 模块
- 注意: alembic 可回滚, FK 错配, enum 硬编, JSONB schema 漂移

### D5 Frontend
- 网络: ❌
- 前端: `packages/web/**` (排除 node_modules, e2e, .test.*)
- 注意: React 19 误用, useRouter bug, TanStack Query staleTime, next-intl, a11y

### D6 Architecture
- 网络: ❌
- 全域: `packages/**` (排除 node_modules, tests, e2e, migrations)
- 注意: 重复代码, 模块边界, 规约违反, 测试缺口, 可观测性

## 质量门禁
- evidence ≥ 3 行代码引用 (必须用 Read 读取, 禁止编造)
- file:line 必须存在于 git HEAD
- severity 必填
- 每条 finding 工具调用 ≤ 5 次
