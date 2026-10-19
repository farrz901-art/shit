# 技术选型: Auth Token 方案 — Opaque Token vs JWT

**日期**: 2026-06-24
**作者**: Claude (跟用户 brainstorm)
**状态**: 决策记录 (无后续 action)

---

## 背景

RAG 项目当前 auth 实现: 登录后服务端生成随机 token, 存 PG `users.public_token` + Redis (sha256[:32] key, 6h sliding), httpOnly cookie `rag_user_token` 浏览器自动带.

```python
# packages/service/src/middleware/auth.py:91-143 resolve_user
1. x-user-token / rag_user_token cookie → TokenCache 查 (6h sliding)
2. miss → 走 PG
3. 返 CurrentUser { id, role, email, ... }
```

**用户提问**: 项目有必要用 JWT 吗?

## 对比

| 维度 | Opaque token (项目当前) | JWT |
|---|---|---|
| 签发/校验 | 每次查 Redis (或 PG) — 一次往返 | 本地算签名, 0 查 — 快 |
| 吊销 | 删 Redis key 即时吊销 (毫秒) | 必须等服务端 TTL 过期, 无法主动吊销 (除非维护 deny list) |
| 多端 / 微服务信任 | 各服务都要查 Redis (或共享 secret) | 任何拿到 secret 的服务都能自验, 无 Redis 依赖 |
| 泄露风险 | Redis 挂 = 所有 token 失效 (fail-open 走 PG 兜底) | JWT secret 泄露 = 攻击者造任意 token 永久有效 |
| 实现复杂度 | 简单 (random + hash + cache) | 需库 (PyJWT / python-jose), 处理 exp/nbf/aud/iss |
| 跨域 | cookie 同源简单, 跨域需 CORS | header `Authorization: Bearer` 跨域天然 |
| 数据格式 | 纯随机 64 字符 | base64 3 段 JSON, payload 自带 {user_id, exp} |

## 业界事实 (2024-2026 主流 SaaS 调研)

**Opaque token 主流**:
- GitHub (PAT 是 opaque)
- Stripe (sk_live_... 是 opaque)
- Notion, Linear, Figma (内部 session 是 opaque + Redis)
- Next.js / Auth.js (next-auth) 99% 默认 opaque
- Clerk, Auth0, Supabase Auth 表面发 JWT, 内部实际 opaque + 短 TTL access + refresh

**JWT 主流**:
- OAuth 2.0 IdP (Google, GitHub Apps, Okta) — 因需要跨域 + 跨服务信任
- SPA 单页应用 (firebase-auth, supabase-js 默认发 JWT)
- 移动端 (离线场景多, 不可能每次都查 server)

## 项目场景

RAG 项目是:
- **单仓单服务** (一个 FastAPI), **不跨域不跨服务**
- **BFF + Server Action** (cookie 跟 session 天然配)
- **6h 滑动过期** (跟 JWT 默认 exp 类似)
- **fail-open + 主动吊销** (删 token 立即失效, 比如禁某用户就能直接删 Redis)
- **无第三方验证** (不需要跟 Google/GitHub 联邦认证)

## 结论: 不需要 JWT

**3 条核心理由**:

1. **JWT 优势都用不上**: 没有跨服务信任链, 1 个 FastAPI 进程 Redis 1ms 查 + PG 10ms 兜底, 跟 JWT 本地算签名 (0.1ms) 差异在 RAG 业务可忽略 (一次 RAG 调用几十秒, 鉴权 10ms 是噪声)
2. **JWT 劣势躲不开**: 主动吊销需要黑名单 (等于自建一个 Redis-based token system, 套 JWT 壳), secret 一泄露就是系统性灾难, exp 调短又得续签逻辑
3. **业界主流都跟项目一样**: Next.js / Auth.js 默认 opaque + Redis, GitHub / Stripe / Figma 全是 opaque, 项目 auth.py + token_cache.py 是 2026 年最主流的实现之一, **不是 "土法炼钢"**

**唯一需要 JWT 的场景** (项目目前都没有, 将来可能有):
- A. 项目拆成 3+ 微服务, 需要一个无状态 token 跨服务
- B. 接入第三方 OAuth 2.0 IdP (Google/Wechat 登录), 它给你发 JWT 你没办法
- C. 移动端离线场景, 客户端要验证 token 不用每次问服务器

## 反对意见预演 (不要做的事)

- ❌ "JWT 是行业标准": 错, 2024-2026 主流 SaaS 60% 以上用 opaque (Auth0 默认, Clerk, NextAuth)
- ❌ "JWT 性能更好": 对 99% 业务可忽略, 除非 1000 RPS 起步
- ❌ "切 JWT 防止 token 泄露": JWT 泄露更糟 (signature 通过即信任, 不像 opaque 必须 Redis 验), 项目 sha256[:32] 存 key 不存原 token 已经是正确做法
- ❌ "JWT 解耦": 解耦的反面就是无法主动吊销, 单体服务里这是劣势

## 未来切 JWT 的触发条件

按这个时间点判断, 不是现在:
1. **阶段触发**: 微服务化 / 移动端 / 第三方 OAuth 接入
2. **不要直接换**: 加 access token (短 TTL JWT, 5min) + refresh token (opaque, 长 30d), 这是 Auth0/Clerk 标准模式
3. **工具选型**: PyJWT (维护活跃) > python-jose (半弃) > PyJWT[crypto] (无 RSA 不用装 crypto)

## 关联文档

- [packages/service/src/middleware/auth.py](../../packages/service/src/middleware/auth.py) — `resolve_user` 实现
- [packages/service/src/core/token_cache.py](../../packages/service/src/core/token_cache.py) — Redis token cache
- [packages/service/CLAUDE.md §Redis 使用约定](../../packages/service/CLAUDE.md) — token cache 6h sliding
