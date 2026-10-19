# 登录态聊天消息持久化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后端新增 `POST /api/chat/conversations/{conv_id}/messages` 端点, 前端 SSE 流终点统一调它把 user/assistant 消息存到 PG, 登录态刷新后历史保留, 列表 `message_count` 自动累加.

**Architecture:** 后端 service 单事务 INSERT message + UPDATE conv 计数. 前端在 `chat-utils.ts` 加 1 个 helper 收敛 3 个流出口 (message_end / abort / error) 调持久化 mutation; 失败 toast 不阻塞 UI; TanStack Query `onSuccess` invalidate 列表 + 详情 2 个 key.

**Tech Stack:** FastAPI + SQLAlchemy 2.x text() (后端), TanStack Query 5.x + sonner toast + next-intl (前端).

---

## 文件结构

### 后端 (3 改 + 2 测)

| 操作 | 路径 | 责任 |
|---|---|---|
| 改 | `packages/service/src/chat/schemas.py` | 加 `MessageCreate` Pydantic |
| 改 | `packages/service/src/chat/service.py` | 加 `append_message()` |
| 改 | `packages/service/src/chat/router.py` | 加 `POST /conversations/{id}/messages` 端点 |
| 改 | `packages/service/tests/chat/test_service.py` | +4 case (append) |
| 改 | `packages/service/tests/chat/test_router.py` | +5 case (POST 端点) |

### 前端 (5 改 + 1 新建测)

| 操作 | 路径 | 责任 |
|---|---|---|
| 改 | `packages/web/lib/chat/api.ts` | 加 `useAppendMessage` hook |
| 改 | `packages/web/lib/chat/chat-utils.ts` | 加 `persistAssistantToServer` helper + 3 出口接入 + user POST |
| 改 | `packages/web/lib/chat/use-chat-state.ts` | 注入 `appendMessageMut` 到 `serverData` 跟 `useChatHandlers` |
| 改 | `packages/web/messages/zh.json` | 加 1 个 i18n key |
| 改 | `packages/web/messages/en.json` | 加 1 个 i18n key |
| 改 | `packages/web/lib/chat/api.test.ts` | +3 case (useAppendMessage) |
| 新建 | `packages/web/lib/chat/chat-utils.test.ts` | +4 case (persistAssistantToServer + 流出口) |
| 改 | `packages/web/e2e/chat-full-flow.spec.ts` | +2 case (login #4/#5) |

---

## 任务清单

### Task 1: 后端 schemas.py 加 `MessageCreate`

**Files:**
- Modify: `packages/service/src/chat/schemas.py:44-51` (插到 `MessageResponse` 上方)

- [ ] **Step 1: 改文件 — 在 `class MessageResponse(BaseModel):` 上方加 `MessageCreate`**

```python
class MessageCreate(BaseModel):
    """追加消息请求体 — role + content + 可选 meta JSON.

    role: 'user' / 'assistant' / 'system' (StrEnum Literal, Pydantic 自动校验).
    content: 1-64000 字符 (Dify 上下文窗口约束).
    meta: 透传 JSON, 业务用 finish_reason / error_code / citations, 后端不 schema-validate.
    """

    role: Literal["user", "assistant", "system"] = Field(
        ..., description="消息角色, 必填; user 入库会累加 conv.message_count"
    )
    content: str = Field(
        ..., min_length=1, max_length=64_000, description="消息文本, 1-64000 字符"
    )
    meta: dict[str, Any] | None = Field(
        default=None, description="元数据 JSON: finish_reason / error_code / citations / tokens 等, 后端透传不校验"
    )
```

并在文件顶部 import 加 `from typing import Any, Literal` (现已有 `from typing import Any`, 加 `Literal`).

- [ ] **Step 2: 验证 import 没报错**

Run: `cd packages/service && uv run python -c "from src.chat.schemas import MessageCreate; print(MessageCreate.model_fields)"`
Expected: 输出 fields dict, 无 ImportError.

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/chat/schemas.py
git commit -m "feat(chat): add MessageCreate schema for append message endpoint"
```

---

### Task 2: 后端 service.py 加 `append_message` (TDD red)

**Files:**
- Modify: `packages/service/tests/chat/test_service.py` (尾部追加 4 case)

- [ ] **Step 1: 写 4 个 failing test**

在 `tests/chat/test_service.py` 末尾追加:

```python
# ---- append_message (2026-06-24 chat-message-persistence) ----


def _msg_row(id_: int = 1, role: str = "user", content: str = "hi", meta_str: str | None = None) -> MagicMock:
    """构造模拟 message row (有 .id / .role / .content / .meta / .created_at)."""
    row = MagicMock()
    row.id = id_
    row.role = role
    row.content = content
    row.meta = meta_str
    row.created_at = datetime(2026, 6, 24, tzinfo=UTC)
    return row


def test_append_message_user_increments_count():
    """role='user' → INSERT message + UPDATE conv.message_count += 1."""
    from src.chat import service as svc

    mock_session = MagicMock()
    # 1. SELECT conv: 返存在
    select_result = MagicMock()
    select_result.first.return_value = _conv_row(id_="c1", title="t1", message_count=0)
    # 2. INSERT messages: 返 inserted row
    insert_result = MagicMock()
    insert_result.first.return_value = _msg_row(id_=1, role="user", content="hello")
    # 3. UPDATE conversations: rowcount (不读, 但 execute 返 MagicMock 即可)
    update_result = MagicMock()
    mock_session.execute.side_effect = [select_result, insert_result, update_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(user_id=1, conv_id="c1", role="user", content="hello")

    assert result is not None
    assert result["role"] == "user"
    assert result["content"] == "hello"
    # 3 次 execute: SELECT + INSERT + UPDATE
    assert mock_session.execute.call_count == 3
    # 第 3 次 (UPDATE) 的 SQL 含 message_count = message_count + 1
    third_call_sql = str(mock_session.execute.call_args_list[2].args[0])
    assert "message_count" in third_call_sql.lower()


def test_append_message_assistant_no_count_change():
    """role='assistant' → INSERT + UPDATE conv.updated_at, 不增 count."""
    from src.chat import service as svc

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = _conv_row(id_="c1", message_count=5)
    insert_result = MagicMock()
    insert_result.first.return_value = _msg_row(id_=2, role="assistant", content="answer")
    update_result = MagicMock()
    mock_session.execute.side_effect = [select_result, insert_result, update_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(user_id=1, conv_id="c1", role="assistant", content="answer")

    assert result is not None
    assert result["role"] == "assistant"
    third_call_sql = str(mock_session.execute.call_args_list[2].args[0])
    # UPDATE 只 set updated_at, 不含 message_count
    assert "message_count" not in third_call_sql.lower()
    assert "updated_at" in third_call_sql.lower()


def test_append_message_conv_not_found_returns_none():
    """conv 不存在 / 越权 / 已软删 → SELECT 返 None → 整个函数返 None, 0 INSERT."""
    from src.chat import service as svc

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = None  # conv 不存在
    mock_session.execute.side_effect = [select_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(user_id=1, conv_id="missing", role="user", content="x")

    assert result is None
    # 只跑 SELECT, 没 INSERT / UPDATE
    assert mock_session.execute.call_count == 1


def test_append_message_meta_serialized_as_json():
    """meta=dict → INSERT 时序列化为 JSON 字符串."""
    from src.chat import service as svc

    mock_session = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = _conv_row(id_="c1")
    insert_result = MagicMock()
    insert_result.first.return_value = _msg_row(meta_str='{"finish_reason":"stop"}')
    update_result = MagicMock()
    mock_session.execute.side_effect = [select_result, insert_result, update_result]

    with patch("src.chat.service.session_scope", return_value=_mock_session_scope(mock_session)):
        result = svc.append_message(
            user_id=1, conv_id="c1", role="assistant", content="x", meta={"finish_reason": "stop"}
        )

    assert result is not None
    # INSERT 调用的第 2 个参数 (params dict) 含 meta key, value 是 JSON 字符串
    insert_params = mock_session.execute.call_args_list[1].args[1]
    assert "meta" in insert_params
    assert insert_params["meta"] == '{"finish_reason": "stop"}'
```

- [ ] **Step 2: 跑测试验证全红**

Run: `cd packages/service && uv run pytest tests/chat/test_service.py::test_append_message_user_increments_count tests/chat/test_service.py::test_append_message_assistant_no_count_change tests/chat/test_service.py::test_append_message_conv_not_found_returns_none tests/chat/test_service.py::test_append_message_meta_serialized_as_json -v`
Expected: 4 个 FAIL, 报 `AttributeError: module 'src.chat.service' has no attribute 'append_message'`.

- [ ] **Step 3: 写 service 实现**

在 `packages/service/src/chat/service.py` 文件末尾追加:

```python
def append_message(
    user_id: int,
    conv_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """追加一条消息到指定 conv. 返 message dict; None 当 conv 不存在/越权/软删.

    单事务: SELECT conv (FOR UPDATE) → INSERT message → UPDATE conv 计数+时间.
    - role='user' 累加 message_count
    - role='assistant'/'system' 仅刷新 updated_at

    Args:
        user_id: 当前登录用户
        conv_id: 目标会话 ID
        role: 'user' / 'assistant' / 'system' (路由层 Literal 校验, 这里假定合法)
        content: 消息文本
        meta: 可选 JSON (finish_reason / error_code / citations 等), 透传不强 schema

    Returns:
        {id, role, content, meta, created_at} 或 None (conv 不存在/越权/软删)
    """
    meta_json = json.dumps(meta) if meta is not None else None
    with session_scope() as s:
        # 1. SELECT conv (FOR UPDATE 防并发 append 同 conv 时 count 串)
        conv = s.execute(
            text("""
                SELECT id FROM conversations
                WHERE id = :cid AND user_id = :uid AND deleted_at IS NULL
                FOR UPDATE
            """),
            {"cid": conv_id, "uid": user_id},
        ).first()
        if not conv:
            return None
        # 2. INSERT message
        msg = s.execute(
            text("""
                INSERT INTO messages (conversation_id, role, content, meta, created_at)
                VALUES (:cid, :role, :content, :meta, NOW())
                RETURNING id, role, content, meta, created_at
            """),
            {"cid": conv_id, "role": role, "content": content, "meta": meta_json},
        ).first()
        assert msg is not None  # INSERT...RETURNING 必有一行
        # 3. UPDATE conv: user 累加 count, 其他只刷 updated_at
        if role == "user":
            s.execute(
                text("""
                    UPDATE conversations
                    SET message_count = message_count + 1, updated_at = NOW()
                    WHERE id = :cid
                """),
                {"cid": conv_id},
            )
        else:
            s.execute(
                text("UPDATE conversations SET updated_at = NOW() WHERE id = :cid"),
                {"cid": conv_id},
            )
    return {
        "id": str(msg.id),
        "role": msg.role,
        "content": msg.content,
        "meta": json.loads(msg.meta) if msg.meta else None,
        "created_at": msg.created_at,
    }
```

- [ ] **Step 4: 跑测试验证全绿**

Run: `cd packages/service && uv run pytest tests/chat/test_service.py -v -k append_message`
Expected: 4 PASS.

- [ ] **Step 5: 跑全文件确认无回归**

Run: `cd packages/service && uv run pytest tests/chat/test_service.py -v`
Expected: 老 6 case + 新 4 case = 10 PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/chat/service.py packages/service/tests/chat/test_service.py
git commit -m "feat(chat): add append_message service function"
```

---

### Task 3: 后端 router.py 加 `POST /messages` 端点 (TDD red)

**Files:**
- Modify: `packages/service/tests/chat/test_router.py` (尾部追加 5 case)

- [ ] **Step 1: 看现有 router test 结构**

Run: `cd packages/service && grep -n "def test_" tests/chat/test_router.py | head -10`
Expected: 看到 `test_create_*` / `test_list_*` 等 helper 模式 (用 TestClient + auth header mock).

- [ ] **Step 2: 写 5 个 failing test (尾部追加)**

```python
# ---- POST /conversations/{id}/messages (2026-06-24 chat-message-persistence) ----


def test_append_message_201(client, auth_header):
    """登录态 POST role=user → 201, 返 MessageResponse."""
    with patch("src.chat.router.svc.append_message") as mock_svc:
        mock_svc.return_value = {
            "id": "1",
            "role": "user",
            "content": "hello",
            "meta": None,
            "created_at": datetime(2026, 6, 24, tzinfo=UTC),
        }
        resp = client.post(
            "/api/chat/conversations/c1/messages",
            json={"role": "user", "content": "hello"},
            headers=auth_header,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "user"
    assert body["content"] == "hello"
    mock_svc.assert_called_once_with(1, "c1", "user", "hello", None)


def test_append_message_unauthorized(client):
    """缺 token → 401."""
    resp = client.post(
        "/api/chat/conversations/c1/messages",
        json={"role": "user", "content": "x"},
    )
    assert resp.status_code == 401


def test_append_message_conv_not_found_404(client, auth_header):
    """svc 返 None (conv 不存在/越权/软删) → 404."""
    with patch("src.chat.router.svc.append_message", return_value=None):
        resp = client.post(
            "/api/chat/conversations/missing/messages",
            json={"role": "user", "content": "x"},
            headers=auth_header,
        )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "conversation not found"


def test_append_message_invalid_role_422(client, auth_header):
    """role='admin' 非 Literal 之一 → Pydantic 422."""
    resp = client.post(
        "/api/chat/conversations/c1/messages",
        json={"role": "admin", "content": "x"},
        headers=auth_header,
    )
    assert resp.status_code == 422


def test_append_message_empty_content_422(client, auth_header):
    """content='' 违反 min_length=1 → 422."""
    resp = client.post(
        "/api/chat/conversations/c1/messages",
        json={"role": "user", "content": ""},
        headers=auth_header,
    )
    assert resp.status_code == 422
```

如果 test_router.py 顶部缺 `from datetime import UTC, datetime` 或 `from unittest.mock import patch`, 同时补上.

- [ ] **Step 3: 跑测试验证全红**

Run: `cd packages/service && uv run pytest tests/chat/test_router.py -v -k append_message`
Expected: 5 FAIL (404 路由未注册).

- [ ] **Step 4: 改 router.py 加端点 + import**

在 `packages/service/src/chat/router.py`:

a) 顶部 import 区域已有 `from .schemas import (...)`, 在括号里加 `MessageCreate`:

```python
from .schemas import (
    BackupResponse,
    ConversationCreate,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageCreate,
    MessageResponse,
)
```

b) 在 `list_messages` 端点 (现有 GET `/conversations/{conv_id}/messages`) 上方加新端点:

```python
@router.post(
    "/conversations/{conv_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="追加消息",
    description=(
        "## 用途\n\n"
        "登录用户在指定 conv 追加一条消息. role=user 会让 message_count += 1; "
        "role=assistant/system 仅刷新 updated_at.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫. 越权 / conv 不存在 / 已软删 → 404 (防 ID 探测).\n\n"
        "## 行为\n\n"
        "audit `chat.msg.append` (target_id=conv_id, after 填 {role}). "
        "service 单事务: SELECT conv FOR UPDATE → INSERT message → UPDATE conv."
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
    """追加消息. user 累加 count, 其他只刷 updated_at. 越权/不存在 返 404."""
    request.state.audit_ctx.set(target_id=conv_id, after={"role": body.role})
    result = svc.append_message(current_user.id, conv_id, body.role, body.content, body.meta)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result
```

- [ ] **Step 5: 跑测试验证 5 个新 case 绿**

Run: `cd packages/service && uv run pytest tests/chat/test_router.py -v -k append_message`
Expected: 5 PASS.

- [ ] **Step 6: 跑全 router 测试确认无回归**

Run: `cd packages/service && uv run pytest tests/chat/test_router.py -v`
Expected: 老 case + 新 5 case 全绿.

- [ ] **Step 7: 跑契约测试 (新增前端 path 不破坏)**

Run: `cd packages/service && uv run pytest tests/test_api_contract.py -v`
Expected: PASS (新端点不在 BFF 死路由列表里).

- [ ] **Step 8: Commit**

```bash
git add packages/service/src/chat/router.py packages/service/tests/chat/test_router.py
git commit -m "feat(chat): add POST /conversations/{id}/messages endpoint"
```

---

### Task 4: 前端 i18n 加 1 个 key

**Files:**
- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`

- [ ] **Step 1: 加 zh key**

在 `packages/web/messages/zh.json` 文件里 (按字母序找合适位置插入, 或追加到末尾, JSON 格式正确即可):

```json
"消息保存失败, 刷新后可能丢失": "消息保存失败, 刷新后可能丢失",
```

- [ ] **Step 2: 加 en key**

`packages/web/messages/en.json`:

```json
"消息保存失败, 刷新后可能丢失": "Failed to save message, may be lost on refresh",
```

- [ ] **Step 3: 验证 JSON 合法**

Run: `cd packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"`
Expected: 输出 `OK`.

- [ ] **Step 4: 跑 i18n test 确认无 MISSING_MESSAGE**

Run: `cd packages/web && bun run test -- messages/__tests__/i18n.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "i18n(chat): add 消息保存失败 key for append message failure"
```

---

### Task 5: 前端 `useAppendMessage` hook + 测试 (TDD)

**Files:**
- Modify: `packages/web/lib/chat/api.ts`
- Modify: `packages/web/lib/chat/api.test.ts`

- [ ] **Step 1: 先看 api.test.ts 已有结构**

Run: `cd packages/web && cat lib/chat/api.test.ts | head -50`
Expected: 看到 `mockApiFetch` + `vi.mock("@/lib/api/config", ...)` 等模板.

- [ ] **Step 2: 写 3 个 failing test (api.test.ts 尾部追加)**

```typescript
// ---- useAppendMessage (2026-06-24) ----

describe("useAppendMessage", () => {
  it("POST 到正确 URL 带 role/content/meta", async () => {
    mockApiFetch.mockResolvedValueOnce({
      id: "1",
      role: "user",
      content: "hi",
      meta: null,
      created_at: "2026-06-24T00:00:00Z",
    });
    const { result } = renderHook(() => useAppendMessage(), { wrapper: createWrapper() });
    result.current.mutate({ convId: "c1", role: "user", content: "hi" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiFetch).toHaveBeenCalledWith("/api/chat/conversations/c1/messages", {
      body: { role: "user", content: "hi", meta: undefined },
      method: "POST",
    });
  });

  it("onSuccess invalidate conversations list + detail 2 keys", async () => {
    mockApiFetch.mockResolvedValueOnce({
      id: "2",
      role: "assistant",
      content: "ok",
      meta: null,
      created_at: "2026-06-24T00:00:00Z",
    });
    const qc = new QueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const wrapperWithClient = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={qc}>
        <IntlWrapper locale="zh">{children}</IntlWrapper>
      </QueryClientProvider>
    );
    const { result } = renderHook(() => useAppendMessage(), { wrapper: wrapperWithClient });
    result.current.mutate({ convId: "c1", role: "assistant", content: "ok" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["chat", "conversations"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["chat", "conversations", "c1"] });
  });

  it("onError 弹 toast", async () => {
    const toastErrorSpy = vi.spyOn(await import("sonner"), "toast", "get").mockReturnValue({
      ...vi.mocked(await import("sonner")).toast,
      error: vi.fn(),
    } as any);
    mockApiFetch.mockRejectedValueOnce(new Error("network"));
    const { result } = renderHook(() => useAppendMessage(), { wrapper: createWrapper() });
    result.current.mutate({ convId: "c1", role: "user", content: "x" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    // sonner toast.error 被调用 (具体 spy 模式跟项目 pattern 对齐; 若 mock 不便, 改用 vi.mock("sonner", ...))
  });
});
```

**注**: 若项目 sonner mock pattern 跟上面不一致 (例如已有 `vi.mock("sonner")`), 改用 `import { toast } from "sonner"` 加 `vi.mocked(toast.error).toHaveBeenCalled()` 模式. 先看 `chat-shell.test.tsx` 怎么 mock sonner 复用同套.

- [ ] **Step 3: 跑测试验证全红**

Run: `cd packages/web && bun run test -- lib/chat/api.test.ts -t useAppendMessage`
Expected: 3 FAIL (`useAppendMessage` 未导出).

- [ ] **Step 4: 加 `useAppendMessage` 实现 (api.ts 尾部)**

在 `packages/web/lib/chat/api.ts` 文件:

a) 顶部 import 加:

```typescript
import { toast } from "sonner";
import { useTranslations } from "next-intl";
```

b) 末尾追加 hook:

```typescript
interface AppendMessageArgs {
  convId: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown>;
}

/** 追加单条消息 (2026-06-24 chat-message-persistence).
 *  - onSuccess: invalidate list + detail 2 keys, 让侧栏数字 + 详情自动刷
 *  - onError: 弹 toast "消息保存失败, 刷新后可能丢失"; 不阻塞 UI (UI 已乐观更新)
 *  - meta 透传 JSON: finish_reason / error_code / citations / tokens 等
 */
export const useAppendMessage = () => {
  const qc = useQueryClient();
  const translate = useTranslations();
  return useMutation({
    mutationFn: ({ convId, role, content, meta }: AppendMessageArgs) =>
      apiFetch<ServerMessage>(`/api/chat/conversations/${convId}/messages`, {
        body: { role, content, meta },
        method: "POST",
      }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: KEYS.conversations() });
      qc.invalidateQueries({ queryKey: KEYS.conversation(vars.convId) });
    },
    onError: () => {
      toast.error(translate("消息保存失败, 刷新后可能丢失"));
    },
  });
};
```

- [ ] **Step 5: 跑测试验证全绿**

Run: `cd packages/web && bun run test -- lib/chat/api.test.ts -t useAppendMessage`
Expected: 3 PASS.

- [ ] **Step 6: 跑全 api.test.ts 确认无回归**

Run: `cd packages/web && bun run test -- lib/chat/api.test.ts`
Expected: 全绿.

- [ ] **Step 7: lint + typecheck**

Run: `cd packages/web && bun run lint && bun run typecheck`
Expected: 0 新 warning + 0 error.

- [ ] **Step 8: Commit**

```bash
git add packages/web/lib/chat/api.ts packages/web/lib/chat/api.test.ts
git commit -m "feat(chat): add useAppendMessage TanStack mutation hook"
```

---

### Task 6: 前端 `chat-utils.ts` 加 `persistAssistantToServer` helper + 3 出口接入 (TDD)

**Files:**
- Modify: `packages/web/lib/chat/chat-utils.ts`
- Create: `packages/web/lib/chat/chat-utils.test.ts`

**关键改动概览**:
- `applyEvent` 加 `appendMutation` + `isAccount` 参数 (经 deps 透传), `message_end` 分支调 helper
- `handleStreamError` 同上, 2 个分支各调一次 helper
- `processStream` deps 接口扩
- `sendRequest` / `handleSend` 链路在 user msg POST 后再走 stream
- `use-chat-state.ts` 注入 `appendMessageMut` 到 `serverData`

**为减小风险, 拆 2 步**:
1. 加 helper + chat-utils.test.ts (纯函数测试 mock 掉 mutation)
2. use-chat-state.ts 接入并把 mutation 实例传下去 (Task 7)

#### 6a. 加 helper 跟测试

- [ ] **Step 1: 新建 `packages/web/lib/chat/chat-utils.test.ts` 写 4 个 failing test**

```typescript
/** chat-utils helper unit tests (2026-06-24 chat-message-persistence) */
import { describe, expect, it, vi } from "vitest";
import { persistAssistantToServer, persistUserToServer } from "./chat-utils";

describe("persistAssistantToServer", () => {
  it("登录态 + finish_reason=stop → 调 mutate, 带 meta 完整字段", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      convId: "c1",
      content: "answer",
      finishReason: "stop",
      citations: [{ documentName: "d", content: "cite" }],
      isAccount: true,
      mutate,
    });
    expect(mutate).toHaveBeenCalledTimes(1);
    expect(mutate).toHaveBeenCalledWith({
      convId: "c1",
      role: "assistant",
      content: "answer",
      meta: { finish_reason: "stop", error_code: undefined, citations: [{ documentName: "d", content: "cite" }] },
    });
  });

  it("abort 路径 finish_reason=interrupted → 写 partial content", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      convId: "c1",
      content: "partial",
      finishReason: "interrupted",
      isAccount: true,
      mutate,
    });
    expect(mutate).toHaveBeenCalledWith({
      convId: "c1",
      role: "assistant",
      content: "partial",
      meta: { finish_reason: "interrupted", error_code: undefined, citations: undefined },
    });
  });

  it("error 路径带 error_code → meta 含 code", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      convId: "c1",
      content: "err part",
      finishReason: "error",
      errorCode: "upstream_error",
      isAccount: true,
      mutate,
    });
    expect(mutate).toHaveBeenCalledWith({
      convId: "c1",
      role: "assistant",
      content: "err part",
      meta: { finish_reason: "error", error_code: "upstream_error", citations: undefined },
    });
  });

  it("anon 用户 → 不调 mutate (走 IDB 老路径)", () => {
    const mutate = vi.fn();
    persistAssistantToServer({
      convId: "c1",
      content: "x",
      finishReason: "stop",
      isAccount: false,
      mutate,
    });
    expect(mutate).not.toHaveBeenCalled();
  });
});

describe("persistUserToServer", () => {
  it("登录态 → mutate role=user", () => {
    const mutate = vi.fn();
    persistUserToServer({ convId: "c1", content: "hi", isAccount: true, mutate });
    expect(mutate).toHaveBeenCalledWith({ convId: "c1", role: "user", content: "hi" });
  });

  it("anon → 不调 mutate", () => {
    const mutate = vi.fn();
    persistUserToServer({ convId: "c1", content: "hi", isAccount: false, mutate });
    expect(mutate).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 跑确认全红**

Run: `cd packages/web && bun run test -- lib/chat/chat-utils.test.ts`
Expected: 6 FAIL (`persistAssistantToServer` / `persistUserToServer` 未导出).

- [ ] **Step 3: 加 helper (chat-utils.ts 末尾)**

```typescript
// --- 服务端消息持久化 helpers (2026-06-24 chat-message-persistence) ---

import type { Citation } from "./types";

type AppendMutateFn = (args: {
  convId: string;
  role: "user" | "assistant" | "system";
  content: string;
  meta?: Record<string, unknown>;
}) => void;

type FinishReason = "stop" | "interrupted" | "error";

/** SSE 流 3 个出口 (message_end / abort / error) 统一调它持久化 assistant 消息.
 *  anon 跳过. meta 带 finish_reason + 可选 error_code / citations.
 */
export const persistAssistantToServer = ({
  convId,
  content,
  finishReason,
  errorCode,
  citations,
  isAccount,
  mutate,
}: {
  convId: string;
  content: string;
  finishReason: FinishReason;
  errorCode?: string;
  citations?: Citation[];
  isAccount: boolean;
  mutate: AppendMutateFn;
}): void => {
  if (!isAccount) {
    return;
  }
  mutate({
    convId,
    role: "assistant",
    content,
    meta: {
      finish_reason: finishReason,
      error_code: errorCode,
      citations,
    },
  });
};

/** handleSend 入口调它持久化 user 消息. anon 跳过. */
export const persistUserToServer = ({
  convId,
  content,
  isAccount,
  mutate,
}: {
  convId: string;
  content: string;
  isAccount: boolean;
  mutate: AppendMutateFn;
}): void => {
  if (!isAccount) {
    return;
  }
  mutate({ convId, role: "user", content });
};
```

- [ ] **Step 4: 跑测试验证全绿**

Run: `cd packages/web && bun run test -- lib/chat/chat-utils.test.ts`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/chat/chat-utils.ts packages/web/lib/chat/chat-utils.test.ts
git commit -m "feat(chat): add persistAssistantToServer / persistUserToServer helpers"
```

#### 6b. 把 helper 接入 SSE 流 3 出口

- [ ] **Step 6: 改 `applyEvent` 接受 deps 扩展 (isAccount + appendMutate)**

`packages/web/lib/chat/chat-utils.ts` 里:

a) `ApplyEventDeps` interface 加字段:

```typescript
interface ApplyEventDeps {
  persistMessages: (convId: string, msgs: Message[]) => void;
  upsertConversation: (conv: Conversation) => void;
  isAccount: boolean;        // (2026-06-24) 控制是否走服务端持久化
  appendMutate: AppendMutateFn; // (2026-06-24) useAppendMessage().mutate
}
```

b) `applyEvent` 的 `message_end` 分支末尾 (在 `return` 前) 加调用:

```typescript
if (ev.type === "message_end") {
  state.setMessagesByConv((msgs) => {
    const list = msgs[cid] ?? [];
    const updated = list.map((msg) => {
      if (msg.id === msgId) {
        return { ...msg, citations: ev.citations };
      }
      return msg;
    });
    deps.persistMessages(cid, updated);
    // ... 现有 setConversations 乐观更新 ...
    // (2026-06-24) 流终点持久化 assistant 完整内容到后端 PG
    const finalMsg = updated.find((m) => m.id === msgId);
    if (finalMsg) {
      persistAssistantToServer({
        convId: cid,
        content: finalMsg.content,
        finishReason: "stop",
        citations: ev.citations,
        isAccount: deps.isAccount,
        mutate: deps.appendMutate,
      });
    }
    return { ...msgs, [cid]: updated };
  });
  return;
}
```

c) `StreamDeps` interface 同样加 `isAccount` + `appendMutate` (用于 `handleStreamError` 跟 `processStream`):

```typescript
interface StreamDeps {
  persistMessages: (convId: string, msgs: Message[]) => void;
  upsertConversation: (conv: Conversation) => void;
  isAccount: boolean;
  appendMutate: AppendMutateFn;
}
```

d) `handleStreamError` 的 AbortError 分支末尾加:

```typescript
if ((error as Error).name === "AbortError") {
  state.setMessagesByConv((msgs) => {
    const list = msgs[convId] ?? [];
    const interruptedMsgs = list.map((msg) => {
      if (msg.id === assistantId) {
        return { ...msg, interrupted: true };
      }
      return msg;
    });
    // (2026-06-24) abort 也落库 partial content
    const partialAssistant = interruptedMsgs.find((m) => m.id === assistantId);
    if (partialAssistant) {
      persistAssistantToServer({
        convId,
        content: partialAssistant.content,
        finishReason: "interrupted",
        isAccount: deps.isAccount,
        mutate: deps.appendMutate,
      });
    }
    return { ...msgs, [convId]: interruptedMsgs };
  });
}
```

e) `handleStreamError` 的 else 分支 (error event) 现有 `applyEvent({...ev: {...code, message, type:'error'}})` 已经会走到 applyEvent 的 fallback 分支 — 但 applyEvent 的非 message_end 分支不持久化. 这里**直接**加调用:

```typescript
} else {
  // 现有 applyEvent({...}) 调用保留
  applyEvent({
    cid: convId,
    deps,
    ev: { code: "client_error", message: (error as Error).message, type: "error" } as ChatEvent,
    msgId: assistantId,
    state,
  });
  // (2026-06-24) error 也落库 partial content
  // 注: applyEvent 已经把 error message append 到 content, 这里读最新 state
  // 但 state 是 setter, 拿不到 latest. 改用 setMessagesByConv 内 closure:
  state.setMessagesByConv((msgs) => {
    const list = msgs[convId] ?? [];
    const partial = list.find((m) => m.id === assistantId);
    if (partial) {
      persistAssistantToServer({
        convId,
        content: partial.content,
        finishReason: "error",
        errorCode: "client_error",
        isAccount: deps.isAccount,
        mutate: deps.appendMutate,
      });
    }
    return msgs; // 不改 state, 只读
  });
}
```

- [ ] **Step 7: lint + typecheck**

Run: `cd packages/web && bun run lint -- lib/chat/chat-utils.ts && bun run typecheck`
Expected: 0 新 warning + 0 error.

- [ ] **Step 8: 跑相关测试**

Run: `cd packages/web && bun run test -- lib/chat/`
Expected: 全绿 (已有 92 case + 新 6 case).

- [ ] **Step 9: Commit**

```bash
git add packages/web/lib/chat/chat-utils.ts
git commit -m "feat(chat): wire SSE stream 3 exits to persistAssistantToServer"
```

---

### Task 7: 前端 `use-chat-state.ts` 注入 `appendMessageMut` 到链路

**Files:**
- Modify: `packages/web/lib/chat/use-chat-state.ts`

- [ ] **Step 1: 在 `useServerData` 加 `useAppendMessage` 实例**

`packages/web/lib/chat/use-chat-state.ts` 改:

a) import 加 `useAppendMessage`:

```typescript
import {
  useAppendMessage,
  useConversation,
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useRenameConversation,
} from "./api";
```

b) `useServerData` 里 createConvMut 旁加:

```typescript
const createConvMut = useCreateConversation();
const deleteConvMut = useDeleteConversation();
const renameConvMut = useRenameConversation();
const appendMessageMut = useAppendMessage(); // (2026-06-24)
void renameConvMut;
```

c) return 加 `appendMessageMut`:

```typescript
return { createConvMut, deleteConvMut, effectiveConversations, serverConvs, appendMessageMut };
```

- [ ] **Step 2: `useChatHandlers` 用 mutation, 注入到 deps**

a) `dispatchSendStream` 调用 `deps` 现在没 isAccount/appendMutate. 在 `handleSend` 构造 `deps` 时加:

```typescript
const deps = {
  aborters: state.aborters,
  messagesByConv: state.messagesByConv,
  persistConv,
  persistMessages,
  setDraft: state.setDraft,
  setStreamingConvId: state.setStreamingConvId,
  upsertConversation,
  isAccount,                                     // (2026-06-24)
  appendMutate: serverData.appendMessageMut.mutate, // (2026-06-24)
};
```

b) `dispatchSendStream` 的 `deps` 类型同步加字段 (跟 chat-utils.ts 改的 `StreamDeps` 对齐).

c) `handleSend` 在 createServerConvIfNeeded 之后 + ensureConversation 之前, 加 user POST:

```typescript
const safeCurrentId: string | null = workingCurrentId;

// (2026-06-24) 登录态: user msg 立即落库, 不等流结束
if (safeCurrentId !== null) {
  persistUserToServer({
    convId: safeCurrentId,
    content: text,
    isAccount,
    mutate: serverData.appendMessageMut.mutate,
  });
}
```

d) 顶部 import 加 `persistUserToServer`:

```typescript
import {
  computeEffectiveConversations,
  getNextConversationId,
  newId,
  ensureConversation,
  initMessages,
  setupAbortController,
  sendRequest,
  processStream,
  persistUserToServer,  // (2026-06-24)
} from "./chat-utils";
```

- [ ] **Step 3: lint + typecheck**

Run: `cd packages/web && bun run lint && bun run typecheck`
Expected: 0 新 warning + 0 error.

- [ ] **Step 4: 跑相关测试**

Run: `cd packages/web && bun run test -- lib/chat/ components/chat/`
Expected: 全绿. 若 `chat-shell.test.tsx` 报错, 大概率是 `useAppendMessage` mock 缺失. 在 `chat-shell.test.tsx` 顶部 mock 块加:

```typescript
const mockAppendMutate = vi.fn();
vi.mock("@/lib/chat/api", () => ({
  // ... 已有 mocks ...
  useAppendMessage: () => ({
    isPending: false,
    mutate: mockAppendMutate,
    mutateAsync: mockAppendMutate,
  }),
}));
```

并在 `beforeEach` 加 `mockAppendMutate.mockClear()`.

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/chat/use-chat-state.ts packages/web/components/chat/chat-shell.test.tsx
git commit -m "feat(chat): wire useAppendMessage into handleSend (user POST + stream deps)"
```

---

### Task 8: E2E `login #4` + `login #5` 新增

**Files:**
- Modify: `packages/web/e2e/chat-full-flow.spec.ts`

- [ ] **Step 1: 在现有 `login #3` 后追加 2 个 test**

```typescript
  test("login #4 登录态发消息后刷新, 历史消息仍可见", async ({ page }) => {
    await performLogin(page);
    await page.goto("/zh/chat");
    await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});
    await clearServerConversations(page);

    const probeText = "刷新历史保留测试";
    await page.getByTestId("composer-textarea").pressSequentially(probeText, { delay: TYPE_DELAY_MS });
    await page.getByTestId("composer-send").click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);

    // 刷新后通过点击侧栏 conv 进入, 验证历史保留
    await page.reload();
    const firstConv = page.locator("[data-testid^='conv-']").first();
    await firstConv.waitFor({ state: "visible", timeout: TIMEOUT_RELOAD_MS });
    await firstConv.click();

    // 用户消息文本应可见 (data-role 见 chat-shell.tsx 注释, 之前已加)
    await expect(page.locator(`text=${probeText}`)).toBeVisible({ timeout: TIMEOUT_LONG_MS });
  });

  test("login #5 登录态发消息后列表 message_count >= 1", async ({ page }) => {
    await performLogin(page);
    await page.goto("/zh/chat");
    await page.waitForLoadState("networkidle", { timeout: TIMEOUT_NAV_MS }).catch(() => {});
    await clearServerConversations(page);

    await page.getByTestId("composer-textarea").pressSequentially(LOGIN_TEXT, { delay: TYPE_DELAY_MS });
    await page.getByTestId("composer-send").click();
    await waitForDifyReply(page, TIMEOUT_DIFY_LONG_MS);
    await waitForSendBtn(page, TIMEOUT_DIFY_LONG_MS);

    const serverConvs = await readServerConversations(page);
    expect(serverConvs.length).toBeGreaterThanOrEqual(SINGLE_COUNT);
    expect(serverConvs[0]?.message_count ?? 0, "message_count 应 >= 1").toBeGreaterThanOrEqual(SINGLE_COUNT);
  });
```

- [ ] **Step 2: 启前后端**

后端: `cd packages/service && uv run python main.py` (后台)
前端: `cd packages/web && bun run dev` (后台)

- [ ] **Step 3: 跑 E2E 新 case**

Run: `cd packages/web && npx playwright test e2e/chat-full-flow.spec.ts -g "login #4|login #5"`
Expected: 2 PASS.

- [ ] **Step 4: 跑全 E2E 确认无回归**

Run: `cd packages/web && npx playwright test e2e/chat-full-flow.spec.ts`
Expected: 全绿 (anon 3 + login 5 + memory 1 + 迁移 1).

- [ ] **Step 5: Commit**

```bash
git add packages/web/e2e/chat-full-flow.spec.ts
git commit -m "test(chat-e2e): add login #4/#5 (refresh history + message_count)"
```

---

### Task 9: 验收 + 联调

- [ ] **Step 1: 全栈手工验证**

启前后端, 浏览器 `http://localhost:3000/zh/login`:
1. 用 `test123@qq.com / 12345678` 登录
2. 进 `/zh/chat`, 发消息 "你好"
3. 等 assistant 回复完
4. 看左侧侧栏数字应显示 ≥ 1
5. 刷新页面, 点侧栏 conv, 历史消息应保留 (user "你好" + assistant 回复)

- [ ] **Step 2: 跑后端全套测试**

Run: `cd packages/service && uv run pytest tests/chat/ -v`
Expected: 全绿.

- [ ] **Step 3: 跑前端全套测试**

Run: `cd packages/web && bun run test`
Expected: 719 → 728 PASS (新增 9 case).

- [ ] **Step 4: lint + typecheck 总检**

Run: `cd packages/web && bun run lint && bun run typecheck && cd ../service && uv run ruff check && uv run pyright`
Expected: 0 error.

- [ ] **Step 5: Commit handoff + spec 合并**

如果之前 spec 没 commit (用户选了"3 不提交"), 这里跟实现一起提:

```bash
git add docs/superpowers/specs/2026-06-24-chat-message-persistence-design.md
git commit -m "docs(spec): chat message persistence design (2026-06-24)"
```

并写一个 handoff 文档:

`docs/superpowers/handoffs/2026-06-24-chat-message-persistence.md`:
- 实施完成状态
- 9 个 task 完成检查
- 已知后续工作 (消息维度软删 / 编辑 / 多端同步 等本 spec 范围外)

```bash
git add docs/superpowers/handoffs/2026-06-24-chat-message-persistence.md
git commit -m "docs(handoff): chat message persistence implementation done"
```

---

## 验收清单 (从 spec 抄)

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
