# P1 — 错误处理弹性 修复 spec 草稿 (2026-07-07)

> ⚠️ 草稿, 未实施. 来源: [AUDIT-REPORT.md §D3](../AUDIT-REPORT.md)

## 范围
- **ERR-001** (high, verified) — 后端 7+ 路由 `str(e)` 拼 HTTPException detail
- **ERR-002** (high, verified) — `/decode` 无鉴权 + 暴露 yaml 绝对路径
- **ERR-003** (high, verified) — chat_share Dify 内部错误透传
- **ERR-005** (high, verified) — chat BFF SSE error 事件原样转 provider message
- D3 其余 6 条 medium/low (ERR-004/006/007/008/009/010)

## 修复策略

### 1. 全局错误装饰器 (ERR-001/003)
- 在 `core/errors.py` 加 `@safe_detail` 装饰器, 自动把 `str(e)` 替换成 `"内部错误"` + log full exception
- 全路由统一使用, `chat_share/router.py` / `product_decoders/router.py` 4 处优先

### 2. /decode 鉴权 + 错误脱敏 (ERR-002)
- 加 `Depends(resolve_user)` + admin 角色校验
- catch 块把 yaml 路径写进 log, HTTP detail 仅返 generic 500

### 3. SSE Error Event 类型化 (ERR-005)
- `app/api/chat/messages/route.ts:155-160` 改用 Zod 校验 provider error message
- 限制最大长度 (e.g., 200 字符), 脱敏邮箱/token
- 客户端增加 toast 错误 fallback

### 4. 全局 fetch 超时 (ERR-006/007)
- apiFetch 包装统一加 `AbortController.timeout(10s)`
- 25+ 个 fetch 调用零超时 → 抽 lib/api/fetch.ts 统一封装

## 不在本文范围
- 实施代码
- 其他 P 维度
