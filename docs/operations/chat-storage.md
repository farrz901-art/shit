# Chat Storage 运维查询 (2026-06-19 chat spec)

> 已登录用户的聊天历史存 PG `conversations` / `messages` 两表, 30d 软删 cron 自动清理.
> anon 用户存客户端 IndexedDB (Dexie), 不进 PG.

## 表结构速览

| 表 | 用途 | 保留 | 索引 |
|---|---|---|---|
| `conversations` | 用户私有会话 | 软删 30d | `(user_id, updated_at DESC) WHERE deleted_at IS NULL` |
| `messages` | 会话消息 | 软删 30d | `(conversation_id, created_at) WHERE deleted_at IS NULL` |
| `chat_shares` | 公开分享 URL | 已有 (2026-06-16) | (已有) |

增量列: `conversations.deleted_at` + `messages.deleted_at` (TIMESTAMPTZ nullable).
迁移: `20260619000000_chat_soft_delete`.

## 实时查询

### 1. 某用户最近 20 段会话

```sql
SELECT id, title, message_count, created_at, updated_at, deleted_at
FROM conversations
WHERE user_id = 42
ORDER BY updated_at DESC
LIMIT 20;
```

### 2. 某用户总消息数 + 总 conv 数

```sql
SELECT
  COUNT(DISTINCT c.id) AS conv_count,
  COUNT(m.id) AS msg_count,
  SUM(c.message_count) AS total_msg_in_conv
FROM conversations c
LEFT JOIN messages m ON m.conversation_id = c.id
WHERE c.user_id = 42 AND c.deleted_at IS NULL;
```

### 3. 30d 软删待清理 (cron 待跑)

```sql
SELECT
  c.id, c.title, c.user_id, c.deleted_at,
  (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) AS msg_count
FROM conversations c
WHERE c.deleted_at IS NOT NULL
  AND c.deleted_at < NOW() - INTERVAL '30 days'
ORDER BY c.deleted_at;
```

### 4. 软删按用户分桶 (谁在大量删)

```sql
SELECT user_id, COUNT(*) AS soft_deleted_count
FROM conversations
WHERE deleted_at IS NOT NULL
  AND deleted_at > NOW() - INTERVAL '7 days'
GROUP BY user_id
ORDER BY soft_deleted_count DESC
LIMIT 20;
```

## Cron 验证

```bash
# 手动跑 cron job (调试用, 会真删 30d 前的软删数据)
cd packages/service
RAG_DB_URL=postgresql+psycopg://postgres:replace-with-strong-password@localhost:5432/rag_test \
  uv run python -c "
from src.chat.service import hard_delete_old_soft_deleted
print(hard_delete_old_soft_deleted(days=30))
"

# Expected output: {'conversations': <int>, 'messages': <int>}
# 服务日志: 'chat hard_delete done: N convs, M msgs older than 30d'

# Dry-run 模式 (只统计, 不真删): 临时改 service 函数 days=99999 → 永远不删, 只验证 SQL 路径
RAG_DB_URL=... uv run python -c "
from src.chat.service import hard_delete_old_soft_deleted
print(hard_delete_old_soft_deleted(days=99999))  # 返 {'conversations': 0, 'messages': 0}
"
```

Cron 注册: `src/scheduler/deletion.py:register_chat_jobs()` → job id `chat_hard_delete_30d`,
每天 03:05 Asia/Hong_Kong 跑 (跟 deletion job 错开 5 分钟).

## 备份导出 (GDPR)

```bash
# 单用户全量导出 JSON (用 cookie 鉴权)
TOKEN=<rag_user_token>
curl -b "rag_user_token=$TOKEN" \
  http://localhost:8000/api/chat/backup | jq .

# Response shape:
# {
#   "exported_at": "2026-06-19T12:00:00Z",
#   "conversations": [
#     {
#       "id": "...",
#       "title": "...",
#       "message_count": 5,
#       "created_at": "...",
#       "updated_at": "...",
#       "messages": [
#         { "role": "user|assistant|system", "content": "...", "meta": null, "created_at": "..." }
#       ]
#     }
#   ]
# }
```

anon 用户数据不进 PG, 客户端 `lib/chat/migration.ts:downloadLocalBackup()` 走浏览器下载 JSON,
无服务端出口.

## 已知限制

1. **anon 数据不存服务端**: 登录后清空, 不可恢复 (A 策略, 跟 ChatGPT 一致)
2. **30d 软删不可撤销**: cron 跑后真删, GDPR "right to erasure" 兜底, 没有 grace / 撤销 UI
3. **跨设备 LWW**: 多设备同时改同一 conv, 后写赢 (本期不接 conflict UI)
4. **Dify chatflow conversation_id**: 已登录用户用服务端 conv.id 当 Dify conversation_id, 切换设备需重新开始 Dify 会话上下文
5. **没接其他 AI 平台导入**: 本期只导出 JSON, 不接 Notion AI / ChatGPT / Claude import
