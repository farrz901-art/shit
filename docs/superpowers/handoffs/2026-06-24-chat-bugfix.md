# Handoff: 聊天全流程 Bug 修复

**日期**: 2026-06-24
**作者**: Claude

---

## 当前状态

| 检查项 | 状态 |
|---|---|
| `bun run typecheck` | 0 error |
| `bun run lint` | 0 error (2 warning: migration.test.tsx id-length, use-chat-state.ts max-statements) |
| `bun run test:coverage lib/chat/` | 13 files, 92/92 pass |
| `bun run test:e2e` | 需等 dev server 重启 |
| handoff 复盘 (2026-06-24 13:34) | **全部 bug 已修** (Bug 2/3 写"未修"实际已修; Bug 4 复盘时补了 isAccount 跳过 IDB 写的二次 bug) |

## 已修 Bug

### Bug 4 (核心): 登录态发消息后端无 conv 记录 → 刷新就丢

**根因**: `handleSend` 在登录态直接调 `sendRequest` 不先创建服务端 conv, 消息无后端关联, 刷新后端 list 空.

**修复**: `use-chat-state.ts` 新增 `createServerConvIfNeeded()`:
- 登录态 + 新对话 → await `createConvMut.mutateAsync` 拿 server id
- 再走 ensureConversation + sendRequest
- **(2026-06-24 复盘二次修)**: `doCreateServerConv` 加 `isAccount` 参数, 登录态跳过 `persistCb` (upsertConversation) — 否则 storage.ts:48 强制 owner=anon → IDB 永远有 anon 记录 → 迁移弹框永远触发.

**改动文件**:
- `packages/web/lib/chat/use-chat-state.ts` — handleSend 加登录态 createConv 分支 + doCreateServerConv isAccount 跳过 IDB
- `packages/web/lib/api/auth.server.ts` — authHeaders 统一注 x-user-token (后端不认 x-admin-token)
- `packages/web/app/api/[...path]/route.ts` — BFF catch-all 同样修 x-admin-token → x-user-token

### Bug 1: migration hook 空壳, 不弹 toast

**修复**: `migration.ts` `useAnonToLoginMigration` 自驱动, 闭包拿 useTranslations, 5s 防抖

### Bug 2: anon 状态不该调 `/api/chat/conversations`

**根因**: `useServerData` 无条件调 `useConversations()`, 但 anon 不走服务端.

**修复 (handoff 写"未修"但实际已修)**:
- `lib/chat/api.ts:59` `useConversations(enabled = true)` 加 enabled 参数
- `lib/chat/use-chat-state.ts:168` `useConversations(isAccount)` 调用时传入

### Bug 3: `POST /api/chat/conversations` 500

**根因 (handoff 假设)**: BFF 转发时 body/headers 丢字段, 或请求带错误 content-type 导致后端 parse 失败.

**验证 (2026-06-24 13:34)**: `curl -X POST ... -d '{}' http://localhost:3000/api/chat/conversations` 返 201 + 正常 conv, server log 记 `201 in 618ms`. **handoff 写"未修"但实际已修**.

## 未修 Bug (下轮)

### Bug 1 (残余): migration.test.tsx id-length warning

`renderHookInI18n` 参数 `T` 太短, oxlint 报. 不影响功能 (oxlint warning 不阻塞 commit).

## E2E 测试

`packages/web/e2e/chat-full-flow.spec.ts` — 8 个串行 test, 覆盖:
- anon #1-3: 进页面 → 发消息 IDB 落盘 → 刷新保留
- login #1-3: 登录 → 发消息服务端 conv 创建 → 刷新保留
- memory #1: BFF 调 /api/memory/search + /api/memory/add
- 迁移 #1: anon 发消息 → 登录 → toast 弹 → 点"知道了" → IDB 清空

**注意**: E2E 依赖真 Dify API (慢, 60s 超时). Dify 回复 regex 之前匹配到 "Was this helpful?" Next.js link, 已改 `data-role="assistant"` 定位.

## Playwright 运行

```bash
# 先启前后端
cd packages/service && uv run python main.py
cd packages/web && bun run dev

# 跑 E2E (跳过 webServer 检查)
cd packages/web && npx playwright test e2e/chat-full-flow.spec.ts
```
