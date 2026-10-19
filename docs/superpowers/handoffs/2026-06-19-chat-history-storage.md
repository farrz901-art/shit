# RAG 聊天历史存储 Handoff (2026-06-19)

> Spec: `docs/superpowers/specs/2026-06-19-chat-history-storage-design.md`
> Plan: `docs/superpowers/plans/2026-06-19-chat-history-storage.md`
> 实施: 5 task, 5 commit, 38 测试新增

## 完成清单

- [x] T1 chat_router 7 端点 + soft delete + 30d cron (spec §5 §8)
- [x] T2 Dexie IndexedDB 替 localStorage + 5 测试 (spec §4)
- [x] T3 api.ts facade + TanStack Query + isAccount 分支 + 8 测试 (spec §6)
- [x] T4 登录迁移 toast + clearLocalChat + i18n zh/en + E2E 框架 + 3 测试 (spec §7 §9)
- [x] T5 docs/operations/chat-storage.md + handoff + CLAUDE.md 增补 (spec §8 §9 运维文档落地)

## 接手 checklist

- [ ] 跑全 service 测试: `cd packages/service && uv run --no-sync pytest -v` (期望全绿, 含 12 chat router + 6 chat service)
- [ ] 跑全 web 测试: `cd packages/web && bun run test` (期望全绿, 含 5 Dexie + 8 api + 3 migration)
- [ ] alembic upgrade: `cd packages/service && RAG_DB_URL=... uv run alembic upgrade head` (新 revision `20260619000000_chat_soft_delete`)
- [ ] 启服务: `cd packages/service && uv run python main.py`
- [ ] 启前端: `cd packages/web && bun run dev`
- [ ] 端到端: 浏览器 anon 聊 3 条 → 刷新验证 IDB 还在 → 登录 → toast 弹 "本地 3 段聊天将清除" → 点 "下载 JSON 备份" → 浏览器下载 → 点 "知道了" → IDB 清 → 看到空状态 → 创建新 conv → 发消息 → 这次走服务端
- [ ] 切 zh/en 验证提示文案 (10 个新字符串, zh/en.json 同步)
- [ ] 模拟 cron 跑: 手动 `hard_delete_old_soft_deleted(days=99999)` 验 SQL 路径 (返 0 计数即 OK), 再用 `days=0` 跑真实清 (会删所有软删数据, **慎用**)

## 已知限制

1. **anon → 登录后本地聊天清除** (A 策略, 跟 ChatGPT/Claude/Gemini/Poe/Perplexity 5 标杆 100% 一致), 用户有 toast 提示 + 下载备份按钮
2. **30d 软删 + cron hard-delete** (GDPR), 不可撤销, 没有 grace 期 / 撤销 UI
3. **跨设备 LWW** (本期不接 conflict UI, 后写赢, 跟 Notion 一致)
4. **Dify chatflow conversation_id** 用服务端 conv.id 替代本地 IDB conv.id, 切换设备 Dify 会话上下文会重置
5. **没接 Notion AI / ChatGPT / Claude import** (本期不接, 后期单独 spec)

## 下一步 / 后期工作

1. **跨设备实时同步**: WebSocket / SSE push 替换 LWW, 多端实时收消息 (spec §11 YAGNI)
2. **服务端全文搜索**: PG tsvector + GIN 索引, 替换客户端 title LIKE (spec §11 YAGNI)
3. **离线模式**: 登录后 IDB 写优先, 后台同步队列 (spec §11 YAGNI)
4. **E2EE 加密**: 客户端用用户密码派生 key 加密 messages.content (spec §11 YAGNI)
5. **多模态消息**: image / audio / file 附件 (spec §11 YAGNI)
6. **导入其他 AI 平台**: Notion AI / ChatGPT / Claude export JSON 解析入 IDB (spec §11 YAGNI)

## 关键决策记录

- ✅ **范围**: A 丢弃策略 (跟 5 标杆 100% 一致), 不做 anon → 登录自动合并
- ✅ **客户端存储**: IndexedDB + Dexie 4.x (~12KB gzipped), 替换原 localStorage 容量限制
- ✅ **提示形式**: shadcn Sonner toast (轻, 不拦截), 2 按钮 (下载备份 / 知道了)
- ✅ **首次进 /chat**: 空状态 + 开始新对话 (跟 ChatGPT 模式一致)
- ✅ **已登录管理**: 服务端完整列表 (重命名 / 删除 / 搜索), TanStack Query 60s staleTime + window focus refetch
- ✅ **删除策略**: 软删 30d (audit `chat.conv.delete`) + cron 每天 03:05 hard-delete (Asia/Hong_Kong)
- ✅ **冲突解决**: LWW (本期不接 conflict UI, 后写赢)
- ✅ **i18n**: zh + en 2 语, 10 个新增字符串 (toast 文案 + 操作按钮), zh.json 中文作 key (跟项目约定)
- ✅ **触发点**: 登录后返回 /chat 时 (明触发, 用户明确知道会清空本地)
- ✅ **离线模式**: 不支持 (登录用户必须在线, 100% 数据一致性, IDB 只缓存)
- ✅ **复用 2026-06-18 Redis**: token cache 6h 鉴权 + RateLimiter 5/15min (per IP), 0 新基础设施

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-19-chat-history-storage-design.md`
- Plan: `docs/superpowers/plans/2026-06-19-chat-history-storage.md`
- 运维 SQL: `docs/operations/chat-storage.md`
- 前端约定: `packages/web/CLAUDE.md` (增 "聊天历史存储约定" 章节)
- 后端约定: `packages/service/CLAUDE.md` (增 "chat_router" 章节)
- 关联: `docs/superpowers/handoffs/2026-06-18-redis-integration.md` (复用 token cache + RateLimiter)
- 关联: `docs/superpowers/handoffs/2026-06-16-test-isolation.md` (新测试用模式 2 db_session, 跟 100 个现有测试一致)
- 关联: `docs/superpowers/handoffs/2026-06-17-logging-system.md` (3 个危险端点加 @audited 装饰)
