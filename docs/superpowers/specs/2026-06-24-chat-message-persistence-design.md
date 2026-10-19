# Spec: 登录态聊天消息持久化

**日期**: 2026-06-24
**作者**: Claude (跟用户 brainstorm)
**状态**: Design (待 plan)

---

## 背景

### 现状

后端 `packages/service/src/chat/router.py` 已实现 7 个 conv 维度端点 (CRUD + 软删 + backup), 但 **0 个 message-write 端点**. 数据库 `messages` 表 ([packages/service/src/chat/models.py:63-96](../../../packages/service/src/chat/models.py#L63-L96)) 已建好 (role/content/meta/created_at/deleted_at), 字段够用, 就是没人写入.

前端 SSE 流终点 `applyEvent` ([packages/web/lib/chat/chat-utils.ts:91-119](../../../packages/web/lib/chat/chat-utils.ts#L91-L119)) 的 `message_end` 分支只调 `persistMessages(cid, msgs)` 写 IndexedDB. 登录态本来不该写 IDB, 但即便写了, 后端 PG 仍然空.

### 用户报告 bug

登录 `http://localhost:3000/zh/chat`:

1. 对话后左侧对话历史的数字没有增加, 且切换对话没有历史对话记录
2. 刷新后对话记录丢失, 没有通过接口保存

### 根因

两个症状根因相同: **后端没有"保存消息"的端点, 前端也从未调用任何持久化接口写后端 PG**.

- 左侧数字不增加 — 后端 `list_conversations` SELECT `message_count` 永远是 0 (创建时初始化 0, 从没被 UPDATE)
- 刷新丢消息 — `useConversation(id)` GET 后端, 后端 `messages` 表里没记录, 返 `{messages: []}`

之前 2026-06-24 修复的 `useServerData` useEffect "本地非空不覆盖" 只解决了发消息当下 UI 闪空的问题. 一旦刷新页面, React state 清掉, 后端又是空 → 还是丢.

---

## 目标

- 补后端 `POST /api/chat/conversations/{conv_id}/messages` 端点 + 配套 service
- 前端 SSE 流终点 (成功 / 中断 / 错误 3 出口) 收敛到 1 个 helper 调后端持久化 user + assistant 双消息
- 登录态对话刷新后消息保留, 列表 `message_count` 跟 `updated_at` 准
- anon 路径行为零变化 (走 IDB 老路径)

## 非目标 (本 spec 不做)

- 消息维度软删 / 编辑 (用户编辑历史消息) — 后端 schema 留好 `deleted_at`, 本 spec 不接 UI
- 流式增量保存 (按 SSE delta 频率 PATCH) — 本 spec 用 "流终点一次写入" (行业默认)
- 多端实时同步 (设备 A 发消息 → 设备 B 实时收到) — WebSocket/SSE push 是另起 spec
- Dify `conversation_id` 跟项目 `conv_id` 双向同步策略 — 现状 Dify 维护自家历史, 前端 `difyConversationId` 已存关联, 本 spec 不动

---

## 5 个关键设计决策 (brainstorm 共识)

| Q | 选项 | 决策 | 理由 |
|---|---|---|---|
| 1 | 持久化时机 | **B 预写 user + 终写 assistant** | 行业标准 (ChatGPT/Claude.ai/Gemini/Perplexity/Vercel AI SDK 5/5 一致), 用户输入绝不丢 |
| 2 | 中断/错误怎么落 | **A 全落, `meta` 区分 finish_reason** | 跟标杆一致, 中断的部分文本保留, 3 出口收敛到 1 helper 方便测试 |
| 3 | `message_count` 算法 | **B 只算 user 消息** | "对话轮数"语义清晰, 前端 [chat-utils.ts:101](../../../packages/web/lib/chat/chat-utils.ts#L101) 已按此算 |
| 4 | 失败 UX | **B toast 提示 + 不阻塞 UI** | 跟 `feedback-bff-must-propagate-502-not-silently-zero` 一致, 失败不静默 |
| 5 | 列表刷新策略 | **A 乐观更新 + B 后端 invalidate (混合)** | 即时反馈 + 最终一致, TanStack Query 标准模式 |

---

## 架构

### 数据流 (登录态发消息)

```
[user 点 send]
  ↓
handleSend (use-chat-state.ts)
  ↓
createServerConvIfNeeded (登录态 + 新对话 → POST /conversations)        ◀ 已有
  ↓
appendMutation.mutate({ convId, role: "user", content: text })           ◀ 新增 (Q1 B)
  ↓
initMessages (本地 state 写 user + assistant 空壳)                       ◀ 已有
  ↓
sendRequest (SSE 流) → applyEvent (累积 delta 到本地 assistant.content)  ◀ 已有
  ↓
流终点 3 出口任一:
  - message_end → persistAssistantToServer(cid, content, "stop", citations)
  - abort       → persistAssistantToServer(cid, partial, "interrupted")
  - error       → persistAssistantToServer(cid, partial, "error", code)
  ↓
appendMutation.mutate({ convId, role: "assistant", content, meta })      ◀ 新增 (Q2 A)
  ↓
onSuccess: invalidateQueries(conversations list + detail)                ◀ 新增 (Q5 B)
onError:   toast.error("消息保存失败, 刷新后可能丢失")                    ◀ 新增 (Q4 B)
  ↓
applyEvent 已有乐观更新: setConversations[i].messageCount/updatedAt       ◀ 已有 (Q5 A)
```

### 数据流 (anon 发消息)

**0 变化**. 全部 `appendMutation.mutate` 调用前判断 `isAccount`, anon → 跳过, 走 IDB 老路径.

---

## 后端组件

### 1. `svc.append_message()` (新)

位置: [packages/service/src/chat/service.py](../../../packages/service/src/chat/service.py)

```python
def append_message(
    user_id: int,
    conv_id: str,
    role: str,         # "user" | "assistant" | "system"
    content: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """追加一条消息. 返 message dict, None 当 conv 不存在/越权/软删."""
    # 单事务:
    # 1. SELECT conv WHERE id=:cid AND user_id=:uid AND deleted_at IS NULL FOR UPDATE
    # 2. 若 None → return None
    # 3. INSERT messages (conversation_id, role, content, meta as JSON)
    #    RETURNING id, role, content, meta, created_at
    # 4. UPDATE conversations:
    #    - role == "user" → message_count = message_count + 1, updated_at = NOW()
    #    - role != "user" → updated_at = NOW()
    # 5. return {id, role, content, meta, created_at}
```

约束:
- `FOR UPDATE` 防并发 (多 tab 同时 append 同一 conv 时 count 不串)
- `meta` 透传不强 schema-validate, 业务用 `JSON.dumps` 序列化存 `messages.meta TEXT` (跟现 `get_conversation` 读 `json.loads(m.meta)` 兼容)
- role 校验放路由层 Pydantic, service 不再二次校验

### 2. `POST /api/chat/conversations/{conv_id}/messages` (新)

位置: [packages/service/src/chat/router.py](../../../packages/service/src/chat/router.py)

```python
class MessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=64_000)
    meta: dict[str, Any] | None = None

@router.post(
    "/conversations/{conv_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="追加消息",
    description=(
        "## 用途\n\n"
        "登录用户在指定 conv 追加一条消息 (user / assistant / system). "
        "user 消息 +1 message_count; assistant / system 仅更新 updated_at.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / 不存在 / 软删 → 404.\n\n"
        "## 行为\n\n"
        "audit `chat.msg.append` (target_id=conv_id, after 填 {role}). "
        "service 单事务 INSERT + UPDATE."
    ),
    responses={
        201: {"description": "返 MessageResponse"},
        401: {"description": "未登录"},
        404: {"description": "conv 不存在 / 越权 / 已软删"},
        422: {"description": "Pydantic 校验失败 (role 非法 / content 越界)"},
    },
)
@audited("chat.msg.append", target_type="message")
async def append_message(
    conv_id: str,
    body: MessageCreate,
    request: Request,
    current_user: CurrentUser = Depends(resolve_user),
):
    request.state.audit_ctx.set(target_id=conv_id, after={"role": body.role})
    result = svc.append_message(current_user.id, conv_id, body.role, body.content, body.meta)
    if result is None:
        raise HTTPException(404, "conversation not found")
    return result
```

### 3. schemas

位置: [packages/service/src/chat/schemas.py](../../../packages/service/src/chat/schemas.py)

新增 `MessageCreate` Pydantic 模型 (上 §2 代码块). 复用现有 `MessageResponse`.

---

## 前端组件

### 1. `useAppendMessage` mutation hook (新)

位置: [packages/web/lib/chat/api.ts](../../../packages/web/lib/chat/api.ts)

```ts
interface AppendArgs {
  convId: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown>;
}

export const useAppendMessage = () => {
  const qc = useQueryClient();
  const t = useTranslations();
  return useMutation({
    mutationFn: ({ convId, role, content, meta }: AppendArgs) =>
      apiFetch<ServerMessage>(`/api/chat/conversations/${convId}/messages`, {
        body: { role, content, meta },
        method: "POST",
      }),
    onSuccess: (_data, vars) => {
      // (Q5 B) 服务端最终一致兜底, 列表 message_count + detail messages 双 invalidate
      qc.invalidateQueries({ queryKey: KEYS.conversations() });
      qc.invalidateQueries({ queryKey: KEYS.conversation(vars.convId) });
    },
    onError: () => {
      // (Q4 B) 失败不阻塞 UI, 只 toast
      toast.error(t("消息保存失败, 刷新后可能丢失"));
    },
  });
};
```

i18n:
- zh.json: `"消息保存失败, 刷新后可能丢失": "消息保存失败, 刷新后可能丢失"`
- en.json: `"消息保存失败, 刷新后可能丢失": "Failed to save message, may be lost on refresh"`

### 2. `chat-utils.ts` 改造

新增 helper `persistAssistantToServer(convId, content, finishReason, extra?)` 收敛 3 个流出口的持久化调用:

```ts
type FinishReason = "stop" | "interrupted" | "error";

interface PersistAssistantArgs {
  convId: string;
  content: string;
  finishReason: FinishReason;
  errorCode?: string;
  citations?: Citation[];
  isAccount: boolean;
  appendMutation: ReturnType<typeof useAppendMessage>;
}

export const persistAssistantToServer = (args: PersistAssistantArgs): void => {
  if (!args.isAccount) return;  // anon 跳过
  args.appendMutation.mutate({
    convId: args.convId,
    role: "assistant",
    content: args.content,
    meta: {
      finish_reason: args.finishReason,
      error_code: args.errorCode,
      citations: args.citations,
    },
  });
};
```

调用点:
- `applyEvent` 收到 `message_end` 事件 → `persistAssistantToServer(cid, finalContent, "stop", citations)`
- `handleStreamError` AbortError 分支 → `persistAssistantToServer(cid, partialContent, "interrupted")`
- `handleStreamError` 其他 error 分支 → `persistAssistantToServer(cid, partialContent, "error", errCode)`

**user msg 持久化** — 在 `handleSend` 创建 conv 后立刻调:
```ts
if (isAccount) {
  appendMutation.mutate({ convId, role: "user", content: text });
  // 失败 toast 已在 hook 里, 不阻塞流
}
```

### 3. 沿用上轮 `useServerData` useEffect 守卫

[packages/web/lib/chat/use-chat-state.ts](../../../packages/web/lib/chat/use-chat-state.ts) 已修过的"本地非空不覆盖". 配合本 spec 后, 刷新页面后端真有数据, 走"本地空 → 填后端历史"分支, 正常显示对话历史.

### 4. 依赖注入

`useAppendMessage` hook 在 `useServerData` 内 `useMutation()` 一次, 通过 `serverData.appendMessageMut` 传到 `useChatHandlers`, handler 再传给 `chat-utils.ts` 各 helper.

---

## 错误 / 边界

| 场景 | 行为 |
|---|---|
| user POST 失败 (网络 / 401 / 502) | toast "保存失败", UI 保留 user msg, 流照走 |
| 流到一半 abort | applyEvent 累积的 partial content 走 `persistAssistantToServer(..., "interrupted")` |
| Dify 上游 error 事件 | partial content 走 `persistAssistantToServer(..., "error", code)` |
| `createServerConvIfNeeded` 失败 | 上轮 spec 已修, `handleSend` 直接 return, 不走 append |
| anon 用户 | 全部 append 调用前 `isAccount` 守卫, 跳过走 IDB 老路径 (跟今天行为一致) |
| 并发 abort + new send | append mutation 没 cancel 语义 (TanStack 默认), 旧 mutation 写完旧 partial, 新 mutation 写新 user; UI 不混 (两个 conv id) |
| 同 conv 短时多次 send | invalidate 串行去重 (TanStack 内部 debounce), 不会刷屏 |

---

## 测试

### 后端 (模式 1 mock + 模式 2 db_session)

| 文件 | 新增 case 数 | 覆盖 |
|---|---|---|
| `tests/chat/test_service.py` | 4 | append success (role=user count+1) / role=assistant 不增 count / 越权返 None / 软删返 None |
| `tests/chat/test_router.py` | 5 | POST 201 / 401 未登录 / 404 越权 / 404 不存在 / 422 校验失败 |

### 前端 (vitest + jsdom)

| 文件 | 新增 case 数 | 覆盖 |
|---|---|---|
| `lib/chat/api.test.ts` | 3 | useAppendMessage 调对 URL / onSuccess invalidate 2 keys / onError toast |
| `lib/chat/chat-utils.test.ts` (新建) | 4 | 登录态 user POST / message_end POST assistant / abort interrupted POST / anon 不 POST |

### E2E (Playwright)

[packages/web/e2e/chat-full-flow.spec.ts](../../../packages/web/e2e/chat-full-flow.spec.ts) 已写:
- `login #2`: 登录态发消息后 `serverConvs.length >= 1` ✓ (本 spec 前已绿 — conv 创建已实现)
- `login #3`: 登录态发消息后刷新, conv 仍在侧栏 ✓ (本 spec 前已绿 — list 接口已实现)

**新增 E2E assertion** (本 spec 实施后翻绿):
- `login #4` (新): 登录态发消息后刷新, **消息内容仍在 (走 GET /conversations/{id} 拉历史)**
- `login #5` (新): 登录态发消息后, 列表 `message_count >= 1`

---

## 实施顺序

按 [.claude/CLAUDE.md "重构规则"](../../../.claude/CLAUDE.md): 先后端 → 后前端, 先加端点 → 后调用.

1. 后端 `svc.append_message` + 测试 (模式 1 + 模式 2)
2. 后端 `POST /messages` router + Pydantic + 测试
3. 前端 `useAppendMessage` hook + 测试
4. 前端 `chat-utils.ts` 改造 + 测试 (helper + 3 出口接入 + user POST)
5. 前端 i18n zh/en 同步加 1 key
6. E2E `login #4` + `login #5` 新增, 跑过

---

## 验收清单

- [ ] 后端 `POST /api/chat/conversations/{id}/messages` 端点存在 (跑 contract test)
- [ ] 登录态发消息 → 后端 `messages` 表里有 2 条记录 (user + assistant)
- [ ] 登录态发消息 → 后端 `conversations.message_count` += 1
- [ ] 登录态发消息 → 左侧侧栏数字立即跳 (乐观)
- [ ] 登录态发消息 → 流结束 ~200ms 内列表 GET 一次 (兜底)
- [ ] 登录态刷新页面 → 历史消息保留, GET /conversations/{id} 返非空 messages
- [ ] 登录态 abort 流 → 后端有 1 条 assistant msg, `meta.finish_reason="interrupted"`
- [ ] anon 路径不变 (IDB 写, 后端 messages 表 0 记录)
- [ ] `bun run lint` 0 新 warning
- [ ] `bun run typecheck` 0 error
- [ ] `bun run test` 全绿
- [ ] `uv run pytest tests/chat/` 全绿
- [ ] `bun run test:e2e -- chat-full-flow` login #2-5 全绿

---

## 关联文档

- [packages/service/src/chat/router.py](../../../packages/service/src/chat/router.py) — 现有 7 端点
- [packages/service/src/chat/service.py](../../../packages/service/src/chat/service.py) — 现有 CRUD
- [packages/service/src/chat/models.py](../../../packages/service/src/chat/models.py) — Message / Conversation ORM
- [packages/web/lib/chat/chat-utils.ts](../../../packages/web/lib/chat/chat-utils.ts) — SSE 流处理
- [packages/web/lib/chat/use-chat-state.ts](../../../packages/web/lib/chat/use-chat-state.ts) — chat state hooks
- [packages/web/lib/chat/api.ts](../../../packages/web/lib/chat/api.ts) — TanStack Query hooks
- 上轮修复 handoff: `docs/superpowers/handoffs/2026-06-24-chat-bugfix.md`
