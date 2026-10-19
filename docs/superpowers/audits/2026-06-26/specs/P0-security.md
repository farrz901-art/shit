# P0 - 安全修复 spec 草稿 (2026-06-26)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Security (D1) + Concurrency (D2 安全相关)
> 关联 checklist: [docs/audit/2026-06-26-findings.md](../../../../docs/audit/2026-06-26-findings.md)

## 范围

### 已验证 finding
- SEC-001 (high) — xlsx@0.18.5 存在 Prototype Pollution + ReDoS CVE

### 未 verify (保持原 confidence)
- SEC-002 (medium) — Cookie Secure 仅在 production 设置, dev/staging 明文
- SEC-003 (medium) — CORS 跨环境配置不一致
- SEC-004 (medium) — seed-admin 端点无频率限制
- SEC-005 (low) — NEXT_PUBLIC_CHAT_TOKEN 暴露抗滥用密钥到客户端
- SEC-006 (low) — user_hash 仅取 SHA256 前 8 hex (32 位熵)
- SEC-007 (info) — BFF catch-all 无上游超时控制
- SEC-008 (low) — 前端 authGuard 仅检查 cookie 存在性
- CONC-003 (high) — 账号注销时未失效 Redis token cache (安全 + 数据交叉)

### Refuted (排除)
- (无 refuted 在安全维度)

## 修复策略

### 1. xlsx 依赖漏洞
- xlsx@0.18.5 → xlsx@0.19.3+ 或迁移到 `xlsx-js-style` (社区兼容 fork)
- 验证: `bun audit --production` 无 xlsx CVE

### 2. Cookie 安全
- 将 Secure 标记改为"所有环境启用"而非仅 production
- 验证: curl 返回的 Set-Cookie 含 `Secure;`

### 3. CORS 加固
- 统一 CORS 配置, 不允许 `*`, 按 ENV 分离白名单
- 验证: OPTIONS 预检返回正确的 Access-Control-Allow-Origin

### 4. seed-admin 频率限制
- 加 Redis rate limit (60 次/1 min)
- 验证: 超过后返回 429

### 5. Token 与熵
- user_hash 改为取 16 hex (64 位熵)
- NEXT_PUBLIC_CHAT_TOKEN → 加 server-side proxy 避免暴露到客户端

### 6. Redis cache 失效
- request_deletion() 加 `invalidate_token()` 调用
- 验证: 注销后 immediately 返回 401

## 不在本文范围
- 实施代码 — 留到 plan + implement 阶段
- P1-P4 其他维度 finding
- 已 refuted 的 finding
