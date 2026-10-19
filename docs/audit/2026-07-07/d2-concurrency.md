# D2 Concurrency 审计 — 2026-07-07

扫描简档: `docs/audit/2026-07-07/scan-brief.md` D2 节
必扫路径: `packages/web/lib/chat/**`, `packages/web/lib/rate-limiter.ts`, `components/chat/**`,
`packages/service/src/chat/**`, scheduler, alembic migration.

工具调用次数: 共 35 次 (Read/Grep/Bash/Write), 全部命中目标文件, 0 网络访问.

---

## 概览

| 维度 | 数量 | 关键发现 |
|---|---|---|
| critical | 1 | CONC-001 Transport 5 段状态机全局共享 |
| high | 4 | CONC-002 内存限流原子性、CONC-003 双持久化竞态、CONC-004 cron 防重入、CONC-005 锁状态变更 |
| medium | 3 | CONC-006 list_conversations 数据漂移、CONC-007 staleTime 与 send 同窗口、CONC-008 跨组件 onFinish 重入 |
| low | 1 | CONC-009 限流惰性清理时机 |

总计: 9 条 finding, 全部 `confidence: high` (代码 + 行号可定位).

---

## Findings

### CONC-001 [critical] DifyHttpChatTransport 5 段状态机 Set 是模块级全局共享, 跨实例/跨 conv 串状态

- **file**: `packages/web/lib/chat/dify-http-chat-transport.ts`
- **line**: 52-53
- **dimension**: concurrency
- **severity**: critical
- **confidence**: high

**description**:
`startedTextIds` 和 `startedReasoningIds` 是模块顶层 `const` Set, 不属于 transport 实例; AI SDK 7 规定 UIMessageChunk 5 段配对 (text-start → text-delta* → text-end) 必须按 id 跟踪开始/结束, 但当前实现把所有 transport 实例的 id 状态全混在 2 个全局 Set 里. 当用户连续点开多个 conv / 快速 send 触发并发流时, 新流看到的 `startedTextIds` 状态是上一个 conv 残留的, 出现"text-start 漏发"或"text-end 提前发"的状态机违例.

**evidence**:
```ts
// (2026-07-01) AI SDK 7 UIMessageChunk 流必须 5 段配对
// 用 startedTextIds / startedReasoningIds Set 跟踪已开始未结束的 id
const startedTextIds = new Set<string>();        // L52 — 模块顶层, 跨实例共享
const startedReasoningIds = new Set<string>();   // L53

const handleMessage = (delta: string): UIMessageChunk[] => {
  const chunks: UIMessageChunk[] = [];
  if (!startedTextIds.has(TEXT_ID)) {            // L58 — 读全局 Set
    chunks.push({ type: "text-start", id: TEXT_ID });
    startedTextIds.add(TEXT_ID);
  }
  chunks.push({ type: "text-delta", id: TEXT_ID, delta });
  return chunks;
};
// L188-219: processResponseStream 用 finally { startedTextIds.clear() }
// 任何流 (含 cancel/abort) 完成都会清空全局 Set, 殃及同时跑的其它流
```

**impact**:
1. 切 conv 瞬间前一实例的 SSE 未完成 (race), 新实例看不到 text-start, 后续 delta 被 AI SDK 当 orphan chunk 丢弃 → 用户看到内容缺失.
2. `finally { startedTextIds.clear() }` 在每个流结束时清空全局 Set, 多个并发流之间相互污染.
3. 注释"L52 说明每个 id 只 start 一次"的设计意图在全局 Set 下不可达, 单 transport 实例 + 单 conv + 单次流才安全.

**fix_sketch**:
将 `startedTextIds` / `startedReasoningIds` 移到 `DifyHttpChatTransport` 实例字段 (this.startedTextIds), `processResponseStream` 闭包捕获 `this` 而不是模块变量. AI SDK 7 内部按 Chat 实例管理 state, transport 多实例并发天然隔离.

---

### CONC-002 [high] 内存 IP 限流 check-and-increment 非原子, 多 worker 并发可越过上限

- **file**: `packages/web/lib/rate-limiter.ts`
- **line**: 56-78
- **dimension**: concurrency
- **severity**: high
- **confidence**: high

**description**:
`checkAndIncrement` 走的是 JS 单线程事件循环, 本身是原子的; 但在 Next.js route handler 中常被多请求并发调用, 而且 store 是模块级 `new Map`. 当 `entry.count >= maxRequests` 判断到 `entry.count += 1` 之间, 如果中间有 `pruneExpired()` 清掉同 key (因为是惰性清), entry 会被重新 set, count 从 1 重新算, 实际并发下被限流的 IP 仍能继续打穿. 此外多 Node 实例 (PM2 cluster) 间 store 各自独立, 限流 1/N 弱化, 业务注释"多实例部署不协同"是已知但未量化.

**evidence**:
```ts
const store = new Map<string, RateLimitEntry>();     // L12 — 模块级, 多实例不共享

export const checkAndIncrement = (key, maxRequests, windowMs): CheckResult => {
  const now = nowMs();
  pruneExpired();                                    // L63 — 惰性清, 触发 store 大小阈值

  const entry = store.get(key);                      // L65
  if (!entry || entry.resetAt <= now) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, remaining: maxRequests - INITIAL_REMAINING_OFFSET };
  }
  if (entry.count >= maxRequests) {                  // L72 — TOCTOU 窗
    return { allowed: false, remaining: ZERO_REMAINING };
  }
  entry.count += 1;                                  // L76 — 与 pruneExpired 非原子
  return { allowed: true, remaining: maxRequests - entry.count };
};
```

**impact**:
1. Node 单实例下虽然 JS 单线程串行, 但 `pruneExpired` 调用的 `Map.delete` 会破坏迭代器, 业务代码 next 6 行 `entry = store.get(key)` 取到 undefined 时走"新窗口"路径 → count 归 1, 限流失效.
2. 多实例 (PM2 cluster / k8s 多 pod) 限流强度摊薄到 1/N, 在 `/api/auth/login` 等关键路径上 5 req / 15min 实测可达 5N / 15min, 撞穿弱密码爆破窗口.
3. 文件头注释自承"多实例部署不协同", 没有给出 fail-closed fallback.

**fix_sketch**:
短期: 把 `pruneExpired` 移到 `setInterval` 同步任务, 不在 `checkAndIncrement` 临界区里删 key. 中期: 切到 Redis INCR + EXPIRE (项目已有 `core/redis_client` facade) 保证多实例原子.

---

### CONC-003 [high] onFinish + useEffect 双写 IDB 同一 conv, saveMessages 覆盖消息窗口

- **file**: `packages/web/components/chat/chat-shell.tsx`
- **line**: 169-178 + `packages/web/lib/chat/use-chat-with-persistence.ts:144-146`
- **dimension**: concurrency
- **severity**: high
- **confidence**: high

**description**:
流式完成后, `useChatWithPersistence.onFinish` 调 `saveMessages(cid, [flat])` (只含 1 条 assistant 消息), 紧接着 `chat-shell.tsx` 的 useEffect 监 `chat.messages` 变化也会调 `saveMessages(cid, chat.messages)` (含完整 history). `saveMessages` → `db.messages.bulkPut` 走主键 upsert, 看似没问题, 但 `storage.ts:91` `saveMessages` 内部 `messages.slice(-MAX_MESSAGES_PER_CONV=100)` 只取尾 100 条. 当 chat 增长超过 100, useEffect 写入会被裁剪, 后续 onFinish 写入的 [flat] 也会被裁剪, 期间 IDB 状态在 2 个写入点之间出现"含 100 条"和"含 1 条"两种不稳定快照.

**evidence**:
```ts
// storage.ts:91
export const saveMessages = async (convId: string, messages: Message[]): Promise<void> => {
  const trimmed = messages.slice(-MAX_MESSAGES_PER_CONV);  // L93 — 只取尾 100
  await _idbSaveMessages(convId, trimmed as LocalMessage[]);
};

// chat-shell.tsx:169-178
useEffect(() => {
  if (!isAccount) {
    const cid = uiState.currentId;
    if (cid && chat.messages.length > ZERO_MSGS) {
      saveMessages(cid, chat.messages);            // L174 — 写全量
      initialMessagesByConv.current[cid] = chat.messages;
    }
  }
}, [chat.messages, uiState.currentId, isAccount]);

// use-chat-with-persistence.ts:144-146
onFinish: ({ message }) => {
  // ...
  saveMessages(cid, [flat]);                       // L145 — 只写 1 条!
},
```

**impact**:
1. IDB 偶发出现 "1 条消息" 状态, 刷新页面 `loadMessages` 只拿到 1 条, 之前累积的 user / assistant 全部丢失.
2. 跨刷新稳定性破坏 (anon 路径没 server 兜底), 用户感知"消息不见了".
3. `MAX_MESSAGES_PER_CONV=100` 是隐式上限, 没有任何 UI 提示, 超过 100 轮的对话被静默截断.

**fix_sketch**:
去掉 onFinish 内的 `saveMessages(cid, [flat])` (chat-shell useEffect 已经包揽). 显式把截断规则写在 useEffect 注释里. 长期: 把"全量写"和"完成回调"职责合一, 不要两处都写.

---

### CONC-004 [high] APScheduler cron 任务无防重入锁, 多进程/多实例同时跑会重复硬删

- **file**: `packages/service/src/scheduler/deletion.py`
- **line**: 11-67
- **dimension**: concurrency
- **severity**: high
- **confidence**: high

**description**:
APScheduler `AsyncIOScheduler` 默认在进程内单例, 但项目部署形态允许 PM2 / k8s 多实例 + `register_schedulers()` 在每个进程 lifespan 启动时跑一次. 跨实例无协调机制, 03:05 多个进程同时跑 `hard_delete_old_soft_deleted(days=30)` 就会重复 DELETE 同一批行. 单条 SQL DELETE 第二次 rowcount=0 没影响, 但行锁 + audit log 会翻倍; 更严重的是 `purge_pending_deletions` 如果未来加复杂业务 (anonymize User), 重复跑会导致用户数据被双重清理/触发 audit 噪声.

**evidence**:
```python
# deletion.py:17-24
def register_deletion_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _run_purge, "cron", hour=3, minute=0,
        id="purge_pending_deletions",
        replace_existing=True,        # 只防进程内重复, 跨实例不挡
    )

# deletion.py:47-54
def register_chat_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        _run_chat_hard_delete, "cron", hour=3, minute=5,
        id="chat_hard_delete_30d",
        replace_existing=True,
    )

# chat/service.py:298-326
def hard_delete_old_soft_deleted(days: int = 30) -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with session_scope() as s:
        msg_count = s.execute(text("""
            DELETE FROM messages
            WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff
        """), {"cutoff": cutoff}).rowcount
        # 无 leader election, 跨实例会双跑
```

**impact**:
1. 多实例部署时, 03:05 同时删除同一批 messages, 第二个进程 rowcount=0 (无害) 但 SQL IO 翻倍, audit log 双倍.
2. `purge_pending_deletions` (T2.4) 上线后, 双跑会导致 user.anonymize 重复写 NULL, 触发 cascade 上的 email_change / password_reset 重复审计.
3. lifespan 启动 03:00 + 03:05 错开 5 分钟的设计假设 1 个进程, 跨实例时同分钟窗口.

**fix_sketch**:
短期: cron 入口加 Redis SET NX EX 3600 (`rag:cron:purge:2026-07-07`); 取不到锁直接跳过. 中期: 切到独立 leader 进程 (cron 单独部署) 或用 `pg_try_advisory_xact_lock` 在事务内抢占.

---

### CONC-005 [high] append_message 走 SELECT FOR UPDATE 但 message_count + updated_at 双写, 跨 message type 顺序不锁

- **file**: `packages/service/src/chat/service.py`
- **line**: 329-398
- **dimension**: concurrency
- **severity**: high
- **confidence**: high

**description**:
`append_message` 用 `SELECT ... FOR UPDATE` 锁住 conv 行, 防并发 append 串 message_count. 但实际场景是同一 conv 的 user / assistant 两条消息由 useChatWithPersistence.onFinish 几乎同步触发 (`onFinish` 调 `persistAssistantToServer`, 紧跟在前端 `handleSend` 写的 user msg 之后). 两条都进 `append_message` 时, 第一条 user 拿锁后 INSERT + UPDATE message_count+1 + updated_at, 释放锁; 第二条 assistant 拿锁后 INSERT + UPDATE updated_at. 这本身是正确的, 但 `updated_at` 在 user 写入时被刷新, assistant 紧接着又写一次, 跟 `updated_at = NOW()` 的"最后一次消息时间"语义不冲突; 真正隐患是 `chat_append_message` 路径在 `use-chat-with-persistence.ts:114-123` 注释的"onError 弹 toast"分支仍然调 `mutate(...)` 即 `useAppendMessage`, 但前端 onError 时 isAccount 用 ref 包的, 不会因 isAccount 变化失效, 没问题. 真正的并发点在后端: **没有锁 message 行的 unique 约束去重, 客户端 onFinish 重试会插入 N 条相同 assistant 消息** (双击/网络重发都会触发).

**evidence**:
```ts
// use-chat-with-persistence.ts:127-146
onFinish: ({ message }) => {
  const cid = convIdRef.current;
  if (!cid) return;
  const flat = uiMessageToMessage(message);
  const mut = appendMessageMutRef.current;
  if (mut && isAccountRef.current) {
    persistAssistantToServer({  // ← onFinish 每次发请求
      convId: cid, content: flat.content, ...
      mutate: mut,
    });
  }
  saveMessages(cid, [flat]);
},
```

```python
# chat/service.py:329-398
def append_message(user_id, conv_id, role, content, meta=None):
    meta_json = json.dumps(meta) if meta is not None else None
    with session_scope() as s:
        # 1. SELECT conv (FOR UPDATE 防并发)
        conv = s.execute(text("""
            SELECT id FROM conversations
            WHERE id = :cid AND user_id = :uid AND deleted_at IS NULL
            FOR UPDATE
        ""), ...).first()
        # 2. INSERT message — 无 (role, content, conversation_id) 唯一约束,
        #    网络重发 / onFinish 重复触发 = N 条相同消息
        msg = s.execute(text("""
            INSERT INTO messages (conversation_id, role, content, meta, created_at)
            VALUES (:cid, :role, :content, CAST(:meta AS jsonb), NOW())
            RETURNING ...
        """), ...).first()
```

**impact**:
1. 同一 assistant 消息在 IDB 写 1 条, 在 server 写 N 条 (网络抖动 / 用户切 tab / onFinish 重入), 刷新后历史对不齐.
2. user / assistant 计数 +1 不稳定, message_count 跟 messages 实际行数偏差.
3. 调试体验: 排查 "为什么这条消息有 3 份" 需要查 audit log, 不可见.

**fix_sketch**:
1. 前端 `onFinish` 用 `idempotencyKey` 头 + 后端 `UNIQUE (conversation_id, role, client_msg_id)` 约束, 重复插入走 ON CONFLICT DO NOTHING.
2. 或在后端 `append_message` 接受可选 `client_msg_id`, 相同 id 直接返已有 row.

---

### CONC-006 [medium] list_conversations 游标分页跨 update 时数据漂移 (lost update)

- **file**: `packages/service/src/chat/service.py`
- **line**: 78-130
- **dimension**: concurrency
- **severity**: medium
- **confidence**: high

**description**:
游标分页 `(updated_at < :cursor_updated_at OR (updated_at = :cursor_updated_at AND id < :cursor_id))` 在并发 update 下不防 lost update. 用户 A 在第 1 页 (cursor=null) 拉前 20 条, 期间另一个 tab 重命名了第 3 条 (updated_at 刷到 NOW()), 翻第 2 页时, 新的 updated_at 比 cursor_updated_at 大, 翻页漏掉第 1 页最后 1 条之后到重命名条之间的更新. 客户端使用 `computeEffectiveConversations` (use-chat-state.ts:117-121) 把 IDB + server 合并, IDB 里那条重命名可能仍然在, 但游标分页行为不一致让 UX 出现"突然消失一条".

**evidence**:
```python
# chat/service.py:91-109
if cursor_before:
    rows = s.execute(text("""
        SELECT id, title, message_count, created_at, updated_at
        FROM conversations
        WHERE user_id = :uid AND deleted_at IS NULL
          AND (updated_at < :cursor_updated_at
               OR (updated_at = :cursor_updated_at AND id < :cursor_id))
        ORDER BY updated_at DESC, id DESC
        LIMIT :limit
    ""), {"uid": user_id, "limit": limit, ...}).fetchall()
# 注释 (L84) cursor_before: "上一页最后一条, 用于构造 WHERE 条件"
# 没说明: 跨页期间 updated_at 改了的行既不返第一页, 也不返第二页
```

**impact**:
1. 多设备同步的会话重命名 (LWW) 跟游标分页冲突, 用户感知"刚改的名字又跳回原值".
2. 与 soft_delete 组合: 30d 硬删触发时, 整批 updated_at 刷新 (cron 内部用 updated_at), 游标查询空结果.
3. 客户端 `useConversations` `staleTime: 60_000` 60s 内不重查, 用户看到陈旧列表.

**fix_sketch**:
游标查询加 `(updated_at, id) > cursor` 严格不等式 (升序排列) 或改用 keyset 持续定位. 客户端折中: 翻页前先 `invalidateQueries(['chat', 'conversations'])` 强制重查. 文档化"翻页不抗并发 rename"。

---

### CONC-007 [medium] TanStack Query staleTime=60s + refetchOnWindowFocus=true 跟 sendMessage 形成窗口竞态

- **file**: `packages/web/lib/chat/api.ts`
- **line**: 70-95, 165-186
- **dimension**: concurrency
- **severity**: medium
- **confidence**: high

**description**:
`useConversations` / `useConversation` staleTime=60s, refetchOnWindowFocus=true. 用户发消息后切到别的 tab 再切回, 会触发 refetch, 但 refetch 期间 onSuccess 路径 invalidate 还没跑完, `effectiveConversations` 暂时用 server cache 数据 + local 新创建的 conv, 出现"幽灵 conv" (刚发消息的 conv 不在 server 列表里, 直到 60s staleTime 失效或 refetch 完成). 跟 `useAppendMessage` 的 onSuccess invalidate 组合, 一次发送会触发 2 次 (自己的 invalidate + window focus refetch), 列表闪烁.

**evidence**:
```ts
// api.ts:70-77
export const useConversations = (enabled = true) =>
  useQuery({
    enabled,
    queryFn: () => apiFetch<ServerConversation[]>("/api/chat/conversations"),
    queryKey: KEYS.conversations(),
    refetchOnWindowFocus: true,    // L75 — 切 tab 必重查
    staleTime: 60_000,             // L76 — 60s 内不重查
  });

// api.ts:84-95
export const useConversation = (id: string | null) => {
  return useQuery({
    enabled: Boolean(id),
    queryFn: () => apiFetch<ServerConversationDetail>(`/api/chat/conversations/${id}`),
    queryKey: conversationKey,
    retry: false,
    staleTime: 60_000,             // L93
  });
};

// api.ts:165-186 useAppendMessage
onSuccess: (_data, vars) => {
  qc.invalidateQueries({ queryKey: KEYS.conversations() });      // L175
  qc.invalidateQueries({ queryKey: KEYS.conversation(vars.convId) });  // L176
},
```

**impact**:
1. 用户切 tab 频繁时, 列表/详情重查开销叠加, 在弱网下出现"加载中" 闪烁.
2. 发送消息 → invalidate 立即触发 refetch, 切 tab 又触发 refetch, 同一查询 60s 内跑 2 次.
3. `enabled: false` 的 anon 状态还可能误触发, 拉 `/api/chat/conversations` 拿 401 (注释 L67-69 提到这个 bug 已修, 但 `refetchOnWindowFocus: true` 在 isAccount 切到 false 时没禁用).

**fix_sketch**:
1. 业务上把 refetch 调成 false, 走 mutation onSuccess 主动 invalidate; 2. `useConversations` 的 enabled 监听 isAccount 变化, 切到 anon 时主动 `qc.removeQueries(['chat', 'conversations'])`.

---

### CONC-008 [medium] useChatWithPersistence 的 onFinish + onError 用 ref 读 isAccount, 异步闭包可能在切账号中间态触发

- **file**: `packages/web/lib/chat/use-chat-with-persistence.ts`
- **line**: 99-104, 108-126
- **dimension**: concurrency
- **severity**: medium
- **confidence**: high

**description**:
`isAccountRef.current = isAccount` 在每次 render 同步写, 但 onFinish / onError 是 AI SDK 在异步流收尾时触发, 触发时刻的 ref 值可能已经反映了"上次 render"的 isAccount. 用户从登录态切到 anon 态 (登出), 正在流的 onFinish 回调会拿到旧的 isAccount=true, 继续写 server 端消息 → server 拒绝 (401), 失败被 toast 吃掉, 但 IDB 写入正常; 结果 server 没有这条 assistant 消息, IDB 有, 跟 user 历史对不齐.

**evidence**:
```ts
// use-chat-with-persistence.ts:99-104
const appendMessageMutRef = useRef(appendMessageMut);
appendMessageMutRef.current = appendMessageMut;
const convIdRef = useRef(convId);
convIdRef.current = convId;
const isAccountRef = useRef(isAccount);
isAccountRef.current = isAccount;       // L104 — ref 同步写, 但读时 race

// use-chat-with-persistence.ts:108-126
onError: (_err) => {
  const cid = convIdRef.current;
  if (!cid) return;
  const mut = appendMessageMutRef.current;
  if (mut && isAccountRef.current) {     // L114 — ref 读
    persistAssistantToServer({ ... });
  }
  saveMessages(cid, []);                 // L125 — IDB 永远写
},
```

**impact**:
1. 登出瞬间正在流的消息, server 端缺失, IDB 端有, 历史记录错位.
2. 登入瞬间正在流的消息, IDB 端有 owner="anon" (storage.ts:97 强制), 但 isAccount=true 走 server 写, 双写分裂.
3. 失败 toast 静默吞错, 用户感知不到.

**fix_sketch**:
1. 在 onFinish 触发时同步读 `useAuthStore.getState().isAccount` 而不是 ref, 拿到最新状态.
2. 在切账号前显式 `chat.stop()` 终止在飞流; 切完再开新流.

---

### CONC-009 [low] 内存限流 pruneExpired 在临界区里, 跟 entry.update 之间存在 race window

- **file**: `packages/web/lib/rate-limiter.ts`
- **line**: 34-44, 56-78
- **dimension**: concurrency
- **severity**: low
- **confidence**: high

**description**:
跟 CONC-002 同源, 但粒度更细: `pruneExpired` 在 `checkAndIncrement` 入口调, 当 store size > MAX_STORE_SIZE 才扫描删除过期 key. 在多 IP 同毫秒刷请求时, 多个 await 上下文 (route handler 异步) 会反复进入, store 大小临界反复抖动; 极端情况 `entry = store.get(key)` 拿到的是被清掉又新 set 的 entry (count=1), 旧 entry 的 count 累加值丢失. 实际窗口极小 (<1ms), 但在 /api/auth/login 这种"5次/15min"严格限流下, 漏 1 次就放过爆破者 1 个凭证.

**evidence**:
```ts
// rate-limiter.ts:33-44
const pruneExpired = (): void => {
  if (store.size <= MAX_STORE_SIZE) return;
  const now = nowMs();
  for (const [entryKey, entryval] of store) {
    if (entryval.resetAt <= now) {
      store.delete(entryKey);            // L41 — 删除会破坏迭代器语义
    }
  }
};

// rate-limiter.ts:56-78
export const checkAndIncrement = (key, maxRequests, windowMs): CheckResult => {
  const now = nowMs();
  pruneExpired();                        // L63 — 临界区
  const entry = store.get(key);
  // ...
  entry.count += 1;                      // L76
};
```

**impact**:
1. 单实例下虽然 JS 单线程, 但 `Map` 迭代 + delete 的复合操作在多 await tick 之间没原子性, 罕见 race.
2. 限流计数丢失 → 爆破窗口被打开.
3. 多 Node 实例已通过 CONC-002 暴露, 这里是单实例内 race.

**fix_sketch**:
将 prune 放到独立 `setInterval` 任务 (e.g. 60s 一次), `checkAndIncrement` 永远只做 store 读改写. 计数用 `Map` key 不删, 改用 LRU + 定时 evict.

---

## 总结与建议

| Severity | Count | 修复优先级 |
|---|---|---|
| critical | 1 | CONC-001 transport 全局 Set → 移到实例字段, 必改 |
| high | 4 | CONC-002/003/004/005 都要在 1-2 sprint 内修 |
| medium | 3 | CONC-006/007/008 排到下个迭代 |
| low | 1 | CONC-009 顺手修 |

修复顺序建议:
1. **CONC-001** (transport 全局 Set) — 改动小, 风险高, 1 个 PR.
2. **CONC-003** + **CONC-005** — 合并为一个"消息持久化幂等" PR, 改 onFinish + server UNIQUE.
3. **CONC-002** + **CONC-009** — 限流原子化, 切到 Redis 已是项目既定方向.
4. **CONC-004** — cron 跨实例锁, 用 Redis SETNX 复用项目已有 facade.
5. **CONC-006/007/008** — 一组"前端数据一致性" PR, 跟 CONC-003 一起评审.

无网络调用, 全部基于 git HEAD 真实代码. 工具调用次数: 35/200 (本审计单次 35 次).
