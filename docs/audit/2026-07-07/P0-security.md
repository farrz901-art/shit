# P0 — 鉴权 & 并发 修复 spec 草稿 (2026-07-07)

> ⚠️ 草稿, 未实施. 真正实施需走: brainstorm → spec → plan → implement 循环.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D1 §D2

## 范围
- **SEC-002** (high, verified) — 4 BFF 路由漏注 x-user-token
- **SEC-005** (high, verified) — catch-all `/api/[...path]` 无 origin/referrer 校验
- **SEC-009** (high, verified) — chat_share create_share 无 @audited
- **CONC-001** (critical, verified) — DifyHttpChatTransport 5 段状态机 Set 全局共享
- 加 D1 全 13 条 (10 verified)

## 修复策略

### 1. BFF 鉴权加固 (SEC-002)
- 全部 BFF route.ts 强制要求 `await serverAuthHeaders()` 注入
- 加 husky pre-commit 检查: grep 拦截裸 `apiProxy(...)` 调用
- 给 `apiProxy` 包装默认注入 serverAuthHeaders (作为 opt-out 强 API)

### 2. Catch-all 守卫 (SEC-005)
- `/api/[...path]/route.ts` `buildForwardHeaders` 加 `req.headers.get('origin')` 白名单校验
- 不在白名单的 origin → 直接 403

### 3. 审计日志 (SEC-009)
- `chat_share/router.py:create_share` 加 `@audited(action="share.create")`
- 同步: `revoke_share`, `view_share` 加对应 audit

### 4. Transport 状态机重构 (CONC-001) — 关键
- `startedTextIds` / `startedReasoningIds` 从模块顶层 `const` 移到 `DifyHttpChatTransport` 实例字段
- `processResponseStream` 闭包捕获 `this` 而非模块变量
- `finally { clear() }` 改成 `finally { this.startedTextIds.clear() }`
- 单元测试: 模拟 2 个 conv 并发流, 验证 5 段配对不串扰

## 不在本文范围
- 实施代码 (留到 plan + implement 阶段)
- D2 中等及以下 finding (CONC-002/003 已 refuted, 余 6 条 medium/low)
- D3-D6 finding (在 P1-P4 spec)
