# Chat 分享功能补完 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**: 把 spec [2026-06-16-chat-share-and-media.md](../specs/2026-06-16-chat-share-and-media.md) §"API 设计" 段里"创建 share 携带 messages 快照 + 列已创建 share + anon 隐藏入口"3 块没实施完的子能力补完, 让 share 功能从 UI → 后端真能跑通.

**Architecture**:
- 前端 share 时序列化当前 `state.messagesByConv[currentId]` → 后端 Pydantic 收 `messages` 必填 → 写 `chat_shares.messages_json`
- 后端加 `GET /api/chat/shares?conv_id=` 列表端点 (仅当前用户的 share, 按时间倒序) → 前端 mount 拉取填充 ShareDialog "我的分享" 列表
- anon 态 Share 按钮跟 Brain 按钮对称 (`isAccount` gating), 避免本地 UUID 当 conv_id 给后端 FK miss

**Tech Stack**:
- 后端: Python 3.14, FastAPI, SQLAlchemy 2.0, Pydantic v2
- 前端: TypeScript, Next.js 15, React 19, lucide-react, sonner, next-intl

**Spec 引用**: `docs/superpowers/specs/2026-06-16-chat-share-and-media.md`
**前置 plan**: `docs/superpowers/plans/2026-06-16-chat-share-and-media.md` (任务 1-3 + 4 大部分已落地, 本 plan 是补完 4 的尾巴)

---

## File Structure (变更)

### Modified Files (8)

| 文件 | 改动 |
|------|------|
| `packages/service/src/chat_share/schemas.py` | `CreateShareRequest` 加必填 `messages: list[SharedMessageInput]`; 加 `ListSharesResponse` + `SharedSnapshot` |
| `packages/service/src/chat_share/service.py` | `create_share` 接 `messages` 参数 + 入库 `messages_json`; 加 `list_shares(user_id, conv_id)` 方法 |
| `packages/service/src/chat_share/router.py` | `create_share` 端点把 `messages` 透传给 service; 新增 `GET /shares?conv_id=` 端点 (登录, 仅返当前用户) |
| `packages/service/tests/chat_share/test_router.py` | +2 测试: 携带 messages 返 200 + 200 + list 端点按用户隔离 |
| `packages/service/tests/chat_share/test_service.py` | +2 测试: create_share 持久化 messages_json + list_shares 按 user_id 隔离 |
| `packages/web/lib/api/chat-share.ts` | `createShare` body 加 `messages`; 加 `listShares(convId)` |
| `packages/web/components/chat/share-dialog.tsx` | 创建时序列化 `state.messagesByConv[convId]`; mount `useEffect` 拉 `listShares` 填充列表 |
| `packages/web/components/chat/chat-header.tsx` | Share 按钮加 `isAccount` gate (`{isAccount && <ShareButton/>}`) |

### Tests (新加 4 个)

| 文件 | 加测试 |
|------|------|
| `packages/service/tests/chat_share/test_service.py` | +2: messages 落库 + list_shares 隔离 |
| `packages/service/tests/chat_share/test_router.py` | +2: 创建带 messages 200 + list 端点 200 |
| `packages/web/lib/api/chat-share.test.ts` | +1: listShares 调 GET ?conv_id= |
| `packages/web/components/chat/share-dialog.test.tsx` | +2: mount 调 listShares 拉已有 + 创建传 messages |

---

## Task 1: 后端 `CreateShareRequest` 加 `messages` 必填字段

**Files:**
- Modify: `packages/service/src/chat_share/schemas.py:18-22`

- [ ] **Step 1: TDD red — 写失败的 schema 测试**

修改 `packages/service/tests/chat_share/test_router.py`, 在 `test_create_share_200_with_auth_override` 后加:

```python
def test_create_share_requires_messages(client, mock_service):
    """messages 字段必填; 缺 → 422"""
    resp = client.post(
        "/api/chat/shares",
        json={"conv_id": "c1", "title": "t"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "messages" in str(body).lower()


def test_create_share_persists_messages_snapshot(client, mock_service):
    """携带 messages → 200 + service.create_share 收到 messages 参数"""
    resp = client.post(
        "/api/chat/shares",
        json={
            "conv_id": "c1",
            "title": "t",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        },
    )
    assert resp.status_code == 200
    call_args = mock_service.create_share.call_args
    assert call_args.kwargs["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
```

- [ ] **Step 2: 跑测试, 确认 red**

Run: `cd packages/service && uv run pytest tests/chat_share/test_router.py::test_create_share_requires_messages tests/chat_share/test_router.py::test_create_share_persists_messages_snapshot -v`
Expected: FAIL — `test_create_share_requires_messages` 期望 422 实际 200 (schema 当前不校验); `test_create_share_persists_messages_snapshot` 期望 kwargs 里有 `messages` 实际是 `messages=None` 默认值.

- [ ] **Step 3: 改 schema 加 `messages` 必填**

修改 `packages/service/src/chat_share/schemas.py:18-22`:

```python
class SharedMessageInput(BaseModel):
    """创建 share 时携带的单条消息 (客户端序列化, 不含内部 id / meta)"""

    role: Literal["user", "assistant"] = Field(..., description="'user' = 用户消息, 'assistant' = AI 回复")
    content: str = Field(..., min_length=1, description="消息文本内容")
    timestamp: datetime | None = Field(None, description="ISO 8601 时间字符串, 可选")


class CreateShareRequest(BaseModel):
    """创建 share 请求体: conv_id 必填, messages 必填, title 可选"""

    conv_id: str = Field(..., max_length=36, description="已登录用户 conv_id (server 端 UUID, String(36))")
    title: str | None = Field(default=None, max_length=200, description="分享标题, None 则前端可编辑")
    messages: list[SharedMessageInput] = Field(
        ...,
        min_length=1,
        max_length=200,  # spec §风险 5: 截断到 200 轮
        description="客户端当前会话全部消息快照 (role + content + timestamp), 至少 1 条",
    )
```

- [ ] **Step 4: 跑测试, 确认 green**

Run: `cd packages/service && uv run pytest tests/chat_share/test_router.py -v`
Expected: PASS — `test_create_share_requires_messages` 422 ✓ + `test_create_share_persists_messages_snapshot` kwargs 通过 ✓

- [ ] **Step 5: 跑 lint + 类型检查**

Run: `cd packages/service && uv run ruff check src/chat_share/schemas.py && uv run pyright src/chat_share/schemas.py`
Expected: 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/chat_share/schemas.py packages/service/tests/chat_share/test_router.py
git commit -m "feat(chat-share): CreateShareRequest 必填 messages 字段, 客户端传消息快照"
```

---

## Task 2: 后端 `service.create_share` 接 `messages` 参数 + 落库

**Files:**
- Modify: `packages/service/src/chat_share/service.py:83-117`

- [ ] **Step 1: TDD red — 写 service 落库测试**

修改 `packages/service/tests/chat_share/test_service.py`, 加:

```python
def test_create_share_persists_messages_json_to_repo():
    """create_share(messages=...) → repo.save 收到 JSON 序列化的 messages"""
    from datetime import UTC, datetime
    from src.chat_share.service import ChatShareService

    repo = MagicMock()
    svc_inst = ChatShareService(repo=repo, locale="zh")
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "你好"}]
    result = svc_inst.create_share(
        conv_id="c1",
        user_id=42,
        title="t",
        messages=msgs,
    )
    # 关键: repo.save 收到的 messages_json 是包含两条消息的 JSON 字符串, 不是 "[]"
    call_kwargs = repo.save.call_args.kwargs
    import json

    decoded = json.loads(call_kwargs["messages_json"])
    assert decoded == msgs
    assert "share_id" in result
    assert result["url"].endswith(f"/zh/chat/s/{result['share_id']}")
```

- [ ] **Step 2: 跑测试, 确认 red**

Run: `cd packages/service && uv run pytest tests/chat_share/test_service.py::test_create_share_persists_messages_json_to_repo -v`
Expected: FAIL — 当前 `service.create_share` 调用时 `messages=None` 强制默认, 测试传了 `messages` 但 service 旧签名不支持 (`TypeError: unexpected keyword argument`).

- [ ] **Step 3: 改 service.create_share 接 messages**

修改 `packages/service/src/chat_share/service.py:83-117`:

```python
def create_share(
    self,
    conv_id: str,
    user_id: int,
    title: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """创建 share: 短 ID + URL + TTL + 存消息快照.

    Args:
        messages: 客户端序列化的消息列表, 元素含 role/content/[timestamp].
                  至少 1 条; service 不二次校验 (Pydantic schema 已校验).

    Returns:
        {share_id, url, title, expires_at, created_at}
    """
    if not messages:
        # 防御性兜底: 调用方漏传时不让"空快照"入库, 跟 Pydantic 422 行为对齐
        raise ValueError("messages 至少 1 条, 不允许空快照")
    share_id = self._gen_share_id()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=defaults.DEFAULT_CHAT_SHARE_TTL_DAYS)
    messages_json = json.dumps(messages, ensure_ascii=False)

    self._repo.save(
        share_id=share_id,
        conv_id=conv_id,
        user_id=user_id,
        title=title,
        messages_json=messages_json,
        model=model,
        expires_at=expires_at,
    )

    return {
        "share_id": share_id,
        "url": self._build_url(share_id),
        "title": title,
        "expires_at": expires_at,
        "created_at": now,
    }
```

- [ ] **Step 4: 跑测试, 确认 green**

Run: `cd packages/service && uv run pytest tests/chat_share/test_service.py -v`
Expected: PASS — `test_create_share_persists_messages_json_to_repo` 通过; 老测试 (无 messages 的) 改为传空列表触发 ValueError, 调整测试见下

> 注: 老测试 (如果有) 不传 messages 会触发 ValueError. 检查 `test_service.py` 现有测试, 必要时改为传 `messages=[{"role": "user", "content": "x"}]` 让所有测试继续 green.

- [ ] **Step 5: 跑全量 chat_share 测试 + lint + 类型**

Run:
```bash
cd packages/service && uv run pytest tests/chat_share/ -v
cd packages/service && uv run ruff check src/chat_share/service.py && uv run pyright src/chat_share/service.py
```
Expected: 全 pass, 0 lint error, 0 pyright error

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/chat_share/service.py packages/service/tests/chat_share/test_service.py
git commit -m "feat(chat-share): service.create_share 接 messages 参数 + 入库 messages_json"
```

---

## Task 3: 后端 router 透传 `messages` 到 service

**Files:**
- Modify: `packages/service/src/chat_share/router.py:148-157`

- [ ] **Step 1: 跑 Task 1 测试, 确认 router 层还 red**

Run: `cd packages/service && uv run pytest tests/chat_share/test_router.py::test_create_share_persists_messages_snapshot -v`
Expected: FAIL — 当前 router 调 `service.create_share(conv_id, user_id, title)` 不传 messages, 即使 schema 通过 Pydantic 校验了 messages 字段, router 也会把它丢弃.

- [ ] **Step 2: 改 router 端点透传 messages**

修改 `packages/service/src/chat_share/router.py:148-157`:

```python
def create_share(
    req: CreateShareRequest,
    current: CurrentUser = Depends(resolve_user),
) -> ShareResponse:
    messages_payload = [msg.model_dump(mode="json") for msg in req.messages]
    result = _get_service().create_share(
        conv_id=req.conv_id,
        user_id=current.id,
        title=req.title,
        messages=messages_payload,
    )
    return ShareResponse(**result)
```

> 用 `model_dump(mode="json")` 把 Pydantic 模型序列化成 dict (含 ISO 8601 字符串的 timestamp), service 端再 `json.dumps` 一次入 `messages_json`. 跟现有 storage 模式一致.

- [ ] **Step 3: 跑测试, 确认 green**

Run: `cd packages/service && uv run pytest tests/chat_share/test_router.py -v`
Expected: PASS — 4 测试全过: 200_with_auth_override + requires_messages + persists_messages_snapshot + 其它

- [ ] **Step 4: 跑 lint + 类型**

Run: `cd packages/service && uv run ruff check src/chat_share/router.py && uv run pyright src/chat_share/router.py`
Expected: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/chat_share/router.py
git commit -m "feat(chat-share): router 透传 messages 字段到 service"
```

---

## Task 4: 后端 `GET /api/chat/shares?conv_id=` 列表端点

**Files:**
- Modify: `packages/service/src/chat_share/schemas.py` (加 `ShareListResponse`)
- Modify: `packages/service/src/chat_share/repo.py` (加 `list_by_conv_and_user`)
- Modify: `packages/service/src/chat_share/service.py` (加 `list_shares`)
- Modify: `packages/service/src/chat_share/router.py` (加新端点)
- Modify: `packages/service/tests/chat_share/test_*.py` (+2 测试)

- [ ] **Step 1: TDD red — 加 repo + service + router 3 层测试**

修改 `packages/service/tests/chat_share/test_service.py` 加:

```python
def test_list_shares_filters_by_user_id_and_conv_id():
    """list_shares(conv_id, user_id) 只返当前用户对应该 conv 的 share, 按 created_at DESC"""
    from datetime import UTC, datetime
    from src.chat_share.service import ChatShareService

    repo = MagicMock()
    share_row = MagicMock()
    share_row.share_id = "abc123"
    share_row.title = "t"
    share_row.url = "http://x/zh/chat/s/abc123"
    share_row.expires_at = None
    share_row.created_at = datetime(2026, 6, 30, tzinfo=UTC)
    repo.list_by_conv_and_user = MagicMock(return_value=[share_row])

    svc_inst = ChatShareService(repo=repo, locale="zh")
    result = svc_inst.list_shares(conv_id="c1", user_id=42)

    repo.list_by_conv_and_user.assert_called_once_with(conv_id="c1", user_id=42)
    assert len(result) == 1
    assert result[0]["share_id"] == "abc123"
```

修改 `packages/service/tests/chat_share/test_router.py` 加:

```python
def test_list_shares_returns_only_current_user_shares(client, mock_service):
    """GET /api/chat/shares?conv_id= → 200 + 返当前用户的 share 列表"""
    mock_service.list_shares = MagicMock(
        return_value=[
            {
                "share_id": "abc",
                "url": "http://localhost:3000/zh/chat/s/abc",
                "title": "t",
                "expires_at": None,
                "created_at": datetime(2026, 6, 30, tzinfo=UTC),
            }
        ]
    )
    resp = client.get("/api/chat/shares?conv_id=c1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["share_id"] == "abc"
    # service 收到当前 user_id (mock 是 42) + conv_id
    call_args = mock_service.list_shares.call_args
    assert call_args.kwargs["conv_id"] == "c1"
    assert call_args.kwargs["user_id"] == 42
```

- [ ] **Step 2: 跑测试, 确认 red**

Run: `cd packages/service && uv run pytest tests/chat_share/ -v -k "list_shares"`
Expected: FAIL — repo 没有 `list_by_conv_and_user` 方法 + service 没有 `list_shares` 方法 + router 没有端点.

- [ ] **Step 3: 改 repo 加 `list_by_conv_and_user`**

修改 `packages/service/src/chat_share/repo.py`:

```python
class ChatShareRepo(Protocol):
    # ... 既有 3 个方法保持不变 ...

    def list_by_conv_and_user(
        self,
        conv_id: str,
        user_id: int,
        limit: int = 20,
    ) -> list[ChatShare]:
        """按 (conv_id, user_id) 查 share 列表, 按 created_at DESC, 分页.

        Returns:
            list[ChatShare]: 空时返 [], 顺序最新在前
        """
        ...


class SqlAlchemyChatShareRepo:
    # ... 既有 3 个方法保持不变 ...

    def list_by_conv_and_user(
        self,
        conv_id: str,
        user_id: int,
        limit: int = 20,
    ) -> list[ChatShare]:
        """按 (conv_id, user_id) 查 share 列表."""
        return (
            self._session.query(ChatShare)
            .filter_by(conv_id=conv_id, user_id=user_id)
            .order_by(ChatShare.created_at.desc())
            .limit(limit)
            .all()
        )
```

- [ ] **Step 4: 改 service 加 `list_shares`**

修改 `packages/service/src/chat_share/service.py`, 在 `revoke_share` 后加:

```python
def list_shares(
    self,
    conv_id: str,
    user_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """按 (conv_id, user_id) 列 share 元数据 (不含 messages 快照).

    Returns:
        list[{share_id, url, title, expires_at, created_at}]: 顺序最新在前
    """
    rows = self._repo.list_by_conv_and_user(conv_id=conv_id, user_id=user_id, limit=limit)
    return [
        {
            "share_id": row.share_id,
            "url": self._build_url(row.share_id),
            "title": row.title,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]
```

- [ ] **Step 5: 加 schema response model**

修改 `packages/service/src/chat_share/schemas.py`, 在 `ShareResponse` 后加:

```python
class ShareListItem(BaseModel):
    """share 列表项: 不含 messages 快照 (避免大 JSON 进列表响应)"""

    share_id: str
    url: str
    title: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
```

- [ ] **Step 6: 加 router 端点**

修改 `packages/service/src/chat_share/router.py`, 在 `revoke_share` 后加:

```python
@router.get(
    "/shares",
    response_model=list[ShareListItem],
    summary="列某会话已创建的 share",
    description=(
        "## 用途\n\n"
        "登录用户列自己创建的 share (按 conv_id 过滤, 时间倒序). "
        "用于 ShareDialog '我的分享' 列表. **不含 messages 快照** (避免大 JSON), 只返元数据. "
        "非当前用户的 share 永不返 (user_id 强过滤).\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫, 必须登录. "
        "跨用户隔离: 仅返当前 user 自己的.\n\n"
        "## 行为\n\n"
        "走 `idx_chat_shares_conv_id_user_id` 复合索引. "
        "`?conv_id=` 必填, 不传 → 422. "
        "limit 默认 20, 上限 100."
    ),
    responses={
        200: {"description": "share 元数据列表, 最新在前"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "conv_id 缺失"},
    },
)
def list_shares(
    conv_id: str = Query(..., max_length=36, description="已登录用户 conv_id"),
    limit: int = Query(20, ge=1, le=100, description="分页大小, 1-100"),
    current: CurrentUser = Depends(resolve_user),
) -> list[ShareListItem]:
    rows = _get_service().list_shares(conv_id=conv_id, user_id=current.id, limit=limit)
    return [ShareListItem(**row) for row in rows]
```

> 需要在 router.py 顶部加 `Query` import: `from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status`

- [ ] **Step 7: 跑测试, 确认 green**

Run: `cd packages/service && uv run pytest tests/chat_share/ -v`
Expected: PASS — 4 service 测试 + 5 router 测试全过

- [ ] **Step 8: 跑 lint + 类型**

Run:
```bash
cd packages/service && uv run ruff check src/chat_share/ && uv run pyright src/chat_share/
```
Expected: 0 error

- [ ] **Step 9: Commit**

```bash
git add packages/service/src/chat_share/
git commit -m "feat(chat-share): GET /api/chat/shares 列表端点 (按 conv_id + user_id 隔离)"
```

---

## Task 5: 前端 `createShare` API client 携带 `messages`

**Files:**
- Modify: `packages/web/lib/api/chat-share.ts:28-32`
- Modify: `packages/web/lib/api/chat-share.test.ts`

- [ ] **Step 1: TDD red — 写失败测试**

修改 `packages/web/lib/api/chat-share.test.ts`, 加:

```typescript
import { createShare, listShares } from "./chat-share";

it("createShare 携带 messages 字段 POST 到 /api/chat/shares", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () =>
      JSON.stringify({
        share_id: "x",
        url: "http://x",
        title: null,
        expires_at: null,
        created_at: "2026-06-30T00:00:00Z",
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await createShare({
    convId: "c1",
    messages: [
      { role: "user", content: "hi" },
      { role: "assistant", content: "hello" },
    ],
  });

  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toContain("/api/chat/shares");
  const body = JSON.parse(init.body);
  expect(body.conv_id).toBe("c1");
  expect(body.messages).toEqual([
    { role: "user", content: "hi" },
    { role: "assistant", content: "hello" },
  ]);
});

it("listShares GET /api/chat/shares?conv_id=", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    text: async () => JSON.stringify([]),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listShares("c1");

  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toContain("/api/chat/shares?conv_id=c1");
  expect(init.method).toBe("GET");
});
```

- [ ] **Step 2: 跑测试, 确认 red**

Run: `cd packages/web && bun run test lib/api/chat-share.test.ts`
Expected: FAIL — `createShare` 当前只传 `conv_id` + `title`; `listShares` 函数不存在.

- [ ] **Step 3: 改 API client**

修改 `packages/web/lib/api/chat-share.ts`:

```typescript
export interface CreateShareInput {
  convId: string;
  title?: string | null;
  messages: Array<{ role: "user" | "assistant"; content: string; timestamp?: string | null }>;
}

export const createShare = (req: CreateShareInput): Promise<ShareResponse> =>
  apiFetch("/api/chat/shares", {
    body: {
      conv_id: req.convId,
      title: req.title ?? null,
      messages: req.messages,
    },
    method: "POST",
  });

export const listShares = (convId: string): Promise<ShareResponse[]> =>
  apiFetch(`/api/chat/shares?conv_id=${encodeURIComponent(convId)}`, { method: "GET" });

// 既有 getShare / revokeShare 保持不变
```

- [ ] **Step 4: 跑测试, 确认 green**

Run: `cd packages/web && bun run test lib/api/chat-share.test.ts`
Expected: PASS — 4 测试全过 (新 2 + 旧 2)

- [ ] **Step 5: 跑 typecheck**

Run: `cd packages/web && bun run typecheck`
Expected: 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/api/chat-share.ts packages/web/lib/api/chat-share.test.ts
git commit -m "feat(chat-share): 前端 createShare 携带 messages + listShares 列表 API"
```

---

## Task 6: 前端 `ShareDialog` 序列化 messages + mount 拉列表

**Files:**
- Modify: `packages/web/components/chat/share-dialog.tsx`
- Modify: `packages/web/components/chat/share-dialog.test.tsx`

- [ ] **Step 1: TDD red — 加 2 测试**

修改 `packages/web/components/chat/share-dialog.test.tsx`, 加:

```typescript
it("mount 时调 listShares 拉已分享列表", async () => {
  const listSpy = vi.spyOn(chatShareApi, "listShares").mockResolvedValue([
    {
      share_id: "abc",
      url: "http://x/abc",
      title: "t",
      expires_at: null,
      created_at: "2026-06-30T00:00:00Z",
    },
  ]);
  renderShareDialog({ open: true, onOpenChange: vi.fn(), convId: "c1" });
  await waitFor(() => {
    expect(listSpy).toHaveBeenCalledWith("c1");
    expect(screen.getByTestId("share-row-abc")).toBeInTheDocument();
  });
});

it("点创建时调 createShare 携带当前 messages", async () => {
  const createSpy = vi.spyOn(chatShareApi, "createShare").mockResolvedValue({
    share_id: "new",
    url: "http://x/new",
    title: null,
    expires_at: null,
    created_at: "2026-06-30T00:00:00Z",
  });
  renderShareDialog({
    open: true,
    onOpenChange: vi.fn(),
    convId: "c1",
    // 业务代码应当能从某 prop 或 hook 拿到 messages 列表
    messages: [
      { role: "user", content: "hi", createdAt: Date.now() },
      { role: "assistant", content: "hello", createdAt: Date.now() },
    ],
  });
  fireEvent.click(screen.getByTestId("share-dialog-create"));
  await waitFor(() => {
    const callArg = createSpy.mock.calls[0][0];
    expect(callArg.convId).toBe("c1");
    expect(callArg.messages).toEqual([
      { role: "user", content: "hi", timestamp: expect.any(String) },
      { role: "assistant", content: "hello", timestamp: expect.any(String) },
    ]);
  });
});
```

需要给 `ShareDialogProps` 加可选 `messages` 字段 (在 Task 7 接入到 ChatShell 之前, 测试用 prop 直传).

- [ ] **Step 2: 跑测试, 确认 red**

Run: `cd packages/web && bun run test components/chat/share-dialog.test.tsx`
Expected: FAIL — `chatShareApi.listShares` 不存在 (Task 5 加了, 但 ShareDialog 没用); `createShare` 当前不传 messages.

- [ ] **Step 3: 改 ShareDialog 加 mount useEffect + 创建带 messages**

修改 `packages/web/components/chat/share-dialog.tsx`:

```typescript
// 顶部 import 调整 (2026-06-30) 加 listShares + useEffect
import { useEffect, useState } from "react";
import { type ShareResponse, createShare, listShares, revokeShare } from "@/lib/api/chat-share";

interface ShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  convId: string | null;
  messages?: Array<{ role: "user" | "assistant"; content: string; createdAt: number }>;  // 业务侧注入
}

// useShareActions 加 messages 参数, 跟 convId 一起传 createShare
const useShareActions = (
  convId: string | null,
  messages: ShareDialogProps["messages"],
  setShares: React.Dispatch<React.SetStateAction<ShareResponse[]>>,
  translation: ReturnType<typeof useTranslations>,
) => {
  // ... 既有 state ...

  const handleCreate = async () => {
    if (!convId || !messages || messages.length === 0) {
      toast.error(translation("当前会话没有消息, 无法分享"));
      return;
    }
    setCreating(true);
    try {
      const res = await createShare({
        convId,
        messages: messages.map((m) => ({
          role: m.role,
          content: m.content,
          timestamp: new Date(m.createdAt).toISOString(),
        })),
      });
      setShares((prev) => [res, ...prev]);
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setCreating(false);
    }
  };
  // ... 既有 handleCopy / confirmRevoke 不变 ...
};

// 组件本体
export const ShareDialog = ({ open, onOpenChange, convId, messages = [] }: ShareDialogProps) => {
  const translation = useTranslations();
  const [shares, setShares] = useState<ShareResponse[]>([]);

  // mount 时拉已有 share 列表 (跟 convId 切换时刷新)
  useEffect(() => {
    if (!open || !convId) {
      return;
    }
    listShares(convId)
      .then(setShares)
      .catch((error) => toast.error((error as Error).message));
  }, [open, convId]);

  // ... 既有 render 函数, useShareActions 调用改成传 messages ...
  const { confirmRevoke, creating, handleCopy, handleCreate, pendingRevoke, setPendingRevoke } =
    useShareActions(convId, messages, setShares, translation);

  // 创建按钮 disabled 加 messages.length === 0 守卫
  // 改 renderCreateButton 内 Button.disabled 为: !convId || messages.length === 0 || creating
  // 改 renderEmpty: convId 切换到无消息时, hint 是 "当前会话没有消息"
}
```

> 完整代码片段较长 (整体 ~180 行), 上面是骨架. 实施时把 `useShareActions` 的 4 处调用点同步更新 (新增 `messages` 参数).

- [ ] **Step 4: 跑测试, 确认 green**

Run: `cd packages/web && bun run test components/chat/share-dialog.test.tsx`
Expected: PASS — 老 2 测试 + 新 2 测试全过

- [ ] **Step 5: 跑 typecheck**

Run: `cd packages/web && bun run typecheck`
Expected: 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/web/components/chat/share-dialog.tsx packages/web/components/chat/share-dialog.test.tsx
git commit -m "feat(chat-share): ShareDialog mount 拉列表 + 创建时序列化 messages"
```

---

## Task 7: ChatShell 注入 messages + Share 按钮加 `isAccount` gate

**Files:**
- Modify: `packages/web/components/chat/chat-shell.tsx:130-134`
- Modify: `packages/web/components/chat/chat-header.tsx:14-23`
- Modify: `packages/web/components/chat/chat-shell.test.tsx` (+1 测试 anon 不渲染 Share)

- [ ] **Step 1: TDD red — 写 anon 不渲染 Share 测试**

修改 `packages/web/components/chat/chat-shell.test.tsx`, 在"记忆与分享" describe 块加:

```typescript
it("anon (isAccount=false) → 不渲染 Share 按钮", () => {
  renderInI18n(<ChatShell isAccount={false} />);
  expect(screen.queryByTestId("share-button")).not.toBeInTheDocument();
});
```

> 现有测试 `"anon (isAccount=false) → 不渲染 Brain 按钮"` (chat-shell.test.tsx:339) 已经存在, 把它扩展 1 行 Share 断言 — 复用同一组断言. 上面的 it 是独立用例, 1 行就行.

- [ ] **Step 2: 跑测试, 确认 red**

Run: `cd packages/web && bun run test components/chat/chat-shell.test.tsx -t "anon (isAccount=false) → 不渲染 Share"`
Expected: FAIL — 当前 Share 按钮在 anon 态也会渲染 (`chat-header.tsx:14-23` 无 `isAccount` gate).

- [ ] **Step 3: 改 chat-header.tsx 加 isAccount gate**

修改 `packages/web/components/chat/chat-header.tsx`:

```typescript
// 顶部已有 isAccount prop (chat-header.tsx:7-11), 但 Share 按钮没 gate. 改为:
export const ChatHeader = ({ isAccount, onShareOpen, onMemoryOpen }: ChatHeaderProps) => (
  <div className="flex items-center justify-end gap-1 border-b px-3 py-1.5">
    {/* (2026-06-30) Share 按钮 anon 不显示 — anon 本地 conv (crypto.randomUUID) 不在
        后端 conversations 表, create_share 会 FK miss. 等未来 anon 也支持再开. */}
    {isAccount && (
      <Button
        size="icon"
        variant="ghost"
        onClick={onShareOpen}
        aria-label="分享对话"
        data-testid="share-button"
      >
        <Share2 className="h-5 w-5" />
      </Button>
    )}
    {isAccount && (
      <Button
        size="icon"
        variant="ghost"
        onClick={onMemoryOpen}
        aria-label="记忆管理"
        data-testid="memory-management-button"
      >
        <Brain className="h-5 w-5" />
      </Button>
    )}
  </div>
);
```

- [ ] **Step 4: 改 chat-shell.tsx 注入 messages 到 ShareDialog**

修改 `packages/web/components/chat/chat-shell.tsx:130-134`:

```typescript
const currentMessages: Message[] = state.currentId
  ? (state.messagesByConv[state.currentId] ?? [])
  : [];

// ... 既有结构, 把 ShareDialog 改成:
<ShareDialog
  open={state.shareOpen}
  onOpenChange={state.setShareOpen}
  convId={state.currentId}
  messages={currentMessages}
/>
```

- [ ] **Step 5: 跑测试, 确认 green**

Run: `cd packages/web && bun run test components/chat/chat-shell.test.tsx components/chat/share-dialog.test.tsx`
Expected: PASS — chat-shell 既有 4 测试 + 新 1 测试全过; share-dialog 既有 2 测试 + Task 6 新 2 测试全过

- [ ] **Step 6: 跑 typecheck + lint**

Run:
```bash
cd packages/web && bun run typecheck
cd packages/web && bun run lint:fix
```
Expected: 0 error

- [ ] **Step 7: Commit**

```bash
git add packages/web/components/chat/chat-shell.tsx packages/web/components/chat/chat-shell.test.tsx packages/web/components/chat/chat-header.tsx
git commit -m "feat(chat-share): ChatShell 注入 messages + Share 按钮 anon 隐藏"
```

---

## Task 8: 端到端验证 + 收尾

**Files:**
- Modify: `packages/web/messages/zh.json` (新增 toast 文案)
- Modify: `packages/web/messages/en.json` (翻译)

- [ ] **Step 1: 加 i18n 文案**

`packages/web/messages/zh.json` 加:

```json
"当前会话没有消息, 无法分享": "当前会话没有消息, 无法分享"
```

`packages/web/messages/en.json` 加:

```json
"当前会话没有消息, 无法分享": "Current conversation has no messages to share"
```

- [ ] **Step 2: 跑全量 web + service 测试**

Run:
```bash
cd packages/web && bun run test
cd packages/service && uv run pytest
```
Expected: 全 pass, 0 新 fail

- [ ] **Step 3: 跑全量 lint + typecheck**

Run:
```bash
cd packages/web && bun run lint && bun run typecheck
cd packages/service && uv run ruff check && uv run pyright
```
Expected: 0 error

- [ ] **Step 4: E2E 验证 (手动)**

1. 后端启动 `uv run python main.py`, 前端启动 `bun run dev`
2. 登录账号, 发 2 条对话 ("hi" → AI 答 "你好")
3. 点 Share 图标 → ShareDialog 打开, 提示"无分享记录" (首次)
4. 点"分享"按钮 → 弹 toast "已复制" (测试用) 或新行出现 (列表)
5. 复制 URL, 在浏览器隐身窗口打开 → 看到完整对话 ("hi" + "你好") + 标题
6. 回主 chat 页 → 点 Share 图标 → 列表里看到刚生成的 share row
7. 点列表的"撤销"按钮 → 确认 → 行消失
8. 再用之前 URL 打开 → 看到 "分享链接无效或已过期"

- [ ] **Step 5: Commit**

```bash
git add packages/web/messages/
git commit -m "feat(chat-share): i18n 加 '当前会话没有消息' 文案 (zh + en)"
```

---

## Self-Review Checklist

**Spec coverage** (spec §API 设计 + §文件清单 + §测试策略):
- ✅ CreateShareRequest 必填 messages — Task 1
- ✅ service.create_share 接 messages — Task 2
- ✅ router 透传 messages — Task 3
- ✅ GET /shares 列表端点 — Task 4
- ✅ 前端 createShare API 携带 messages — Task 5
- ✅ ShareDialog mount 拉列表 + 创建带 messages — Task 6
- ✅ anon 隐藏 Share + ChatShell 注入 messages — Task 7
- ✅ i18n + 端到端验证 — Task 8

**Placeholder scan**: 全 plan 0 处 "TBD"/"TODO"/"implement later". 全部代码 + 命令具体可执行.

**Type consistency**:
- `ShareDialogProps.messages` 定义在 Task 6, Task 7 沿用同一 type — ✓
- `CreateShareInput.messages` 在 Task 5 定义, Task 6 沿用 — ✓
- `SharedMessageInput` (后端 schema) ↔ `{role, content, timestamp}` (前端 API client) — 字段名一致, timestamp 都是 ISO 8601 字符串 — ✓

**Dependencies**:
- Task 1 (schema) → Task 2 (service) → Task 3 (router) 是后端 3 层串联
- Task 4 (新端点) 独立, 不依赖 Task 1-3
- Task 5 (前端 API client) 不依赖后端代码, 可独立
- Task 6 (ShareDialog) 依赖 Task 5 的 `listShares` API
- Task 7 (ChatShell/header) 依赖 Task 6 的 `ShareDialogProps.messages` 字段
- Task 8 收尾, 依赖全部

**Commit 数量**: 8 commits, 符合 `feedback-commit-in-batches-for-large-changes` (< 10 commits / spec).

**风险**:
- Pydantic `min_length=1` 强制前端传至少 1 条消息 — 对应"创建空对话直接分享"的 UX 错误, ShareDialog 创建按钮 `disabled={messages.length === 0}` 已守
- 后端 `conv_id: String(36)` 严格对齐前端 `crypto.randomUUID()` 格式 — anon 隐藏后只允许登录态, 登录态 `state.currentId` 是后端 UUID 格式, OK
- `chat_shares.messages_json` 单行 Text 列, 200 条消息估算 ~50-200KB, PG Text 上限 1GB — 风险 5 缓解, 不在本 plan 范围

---

## 后续 work (本 plan 不做, 留 handoff)

1. **anon 态支持 share**: anon local uuid 跟后端 conversations FK 不兼容, 需要后端放宽 (e.g. 用 conv_id 当 string 标记, 不强制 FK) 或前端匿名 ID 上传服务器存档. spec 没强制, 留后续.
2. **share 链接 access 限流**: spec §风险 1 提到的 IP rate limit, 后端没做 (Goose: 短 ID 71 bits 熵够).
3. **share 撤销后前端 memory cache**: 撤销后前端 `shares` state 立即移除 (Task 6 已实现), 后端需保证 revoke 后 `GET /shares/{id}` 返 404 (ShareNotFound 已实现).
4. **share UI 动画**: Task 6 是功能性补完, 动效 (复制 toast 渐隐 / 列表 fade in) 留给后续 UI spec.