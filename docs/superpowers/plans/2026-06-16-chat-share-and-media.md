# Chat 分享 + 媒体上传 + 图片预览 实施 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal**: 给主 chat 页加 (1) 分享给外部用户的只读链接 + (2) 媒体上传 (图片/文件/语音) + (3) 图片点击放大预览 + (4) 满意按钮接通.

**Reference Spec**: `docs/superpowers/specs/2026-06-16-chat-share-and-media.md`

**Tech Stack**:
- 后端: Python 3.14, FastAPI, SQLAlchemy 2.0, alembic, Pydantic v2, nanoid
- 前端: TypeScript, Next.js 15, React 19, shadcn Dialog, lucide-react, MediaRecorder API, FormData
- 测试: pytest (后端), vitest + @testing-library/react (前端)

---

## File Structure (变更)

### New Files (10)

| 文件 | 职责 |
|------|------|
| `packages/service/src/storage/migrations/versions/20260616_000000_add_chat_shares.py` | 1 张表 `chat_shares` + alembic |
| `packages/service/src/chat_share/__init__.py` | 子包 |
| `packages/service/src/chat_share/schemas.py` | Pydantic (CreateShareRequest, ShareResponse, SharedConversationResponse, SharedMessage) |
| `packages/service/src/chat_share/models.py` | SQLAlchemy ORM (`ChatShare`) |
| `packages/service/src/chat_share/service.py` | 业务核心: 4 方法 (create/get/revoke/upload_file) + Dify 透传 |
| `packages/service/src/chat_share/router.py` | FastAPI 4 端点 |
| `packages/service/src/chat_share/repo.py` | ORM CRUD helpers |
| `packages/web/app/[locale]/chat/s/[shareId]/page.tsx` | RSC 公开页 |
| `packages/web/components/chat/shared-chat-view.tsx` | 只读对话视图 |
| `packages/web/components/chat/share-dialog.tsx` | 主 chat 分享弹框 (创建 + 复制 + 撤销) |
| `packages/web/components/chat/composer-attachments.tsx` | Composer 附件子组件 (图片 / 文件 / 语音入口) |
| `packages/web/components/chat/voice-recorder.tsx` | MediaRecorder 录音 |
| `packages/web/components/common/image-preview.tsx` | shadcn Dialog 包原图 |
| `packages/web/lib/api/chat_share.ts` | chatShareApi (create / get / revoke) |
| `packages/service/tests/chat_share/test_service.py` | 6-8 测试 |
| `packages/service/tests/chat_share/test_router.py` | 4-5 测试 |
| `packages/service/tests/chat_share/test_files_upload.py` | 3 测试 |
| `packages/web/lib/api/chat_share.test.ts` | 3 测试 |
| `packages/web/components/chat/shared-chat-view.test.tsx` | 3 测试 |
| `packages/web/components/chat/share-dialog.test.tsx` | 4 测试 |
| `packages/web/components/chat/composer-attachments.test.tsx` | 4 测试 |
| `packages/web/components/common/image-preview.test.tsx` | 3 测试 |

### Modified Files (12)

| 文件 | 改动 |
|------|------|
| `packages/service/src/approvals/models.py` | `ApprovalKind` 加 `"like"` |
| `packages/service/src/__init__.py` | `register_routers` 加 `chat_share_router` |
| `packages/service/src/common/defaults.py` | 加 share 短 ID 长度 + 默认 TTL 常量 |
| `packages/service/tests/test_api_contract.py` | `FRONTEND_EXPECTS` 加 4 行 (chat/share/* + chat/files) |
| `packages/web/components/chat/Composer.tsx` | 拆: 留 Textarea 容器, 调 `<ComposerAttachments>` |
| `packages/web/components/chat/MessageBubble.tsx` | `<ReactMarkdown components.img>` 加 onClick → ImagePreview |
| `packages/web/components/chat/MessageFeedback.tsx` | 满意按钮接通 → `kind=like` approval |
| `packages/web/components/chat/ChatShell.tsx` | 头部加 Share 图标 + 状态 |
| `packages/web/lib/api/chat.ts` | 加 `chatApi.uploadFile(file)` |
| `packages/web/messages/{zh,en}.json` | 加 ~12 字符串 (share / upload / voice / image / like) |
| `packages/web/components/chat/MessageFeedback.test.tsx` | +2 测试 (满意按钮接通) |
| `packages/web/components/chat/Composer.test.tsx` | 改 import: 用 `<ComposerTextarea>` + 加 Composer 集成测试 |

---

## Task 1: 后端 share 数据层 (migration + ORM + service)

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260616_000000_add_chat_shares.py`
- Create: `packages/service/src/chat_share/{__init__,schemas,models,repo,service}.py`

- [ ] **Step 1: TDD red — 写 share service 6-8 测试**

创建 `tests/chat_share/test_service.py`:

```python
"""ChatShare service 单测 (2026-06-16)"""
from __future__ import annotations
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# ---- create_share ----

def test_create_share_generates_short_id():
    """create_share 返 share_id 长度 12 (nanoid 默认), 跟 url 拼成完整链接"""
    from src.chat_share.service import ChatShareService
    svc = ChatShareService(repo=MagicMock())
    result = svc.create_share(conv_id="conv-1", user_id="42", title="标题")
    assert len(result["share_id"]) == 12
    assert result["url"].endswith(f"/chat/s/{result['share_id']}")


def test_create_share_uses_explicit_title():
    """用户传 title 优先; 不传 → 用 conv 第一条消息前 50 字"""
    from src.chat_share.service import ChatShareService
    svc = ChatShareService(repo=MagicMock())
    # 显式 title
    r1 = svc.create_share(conv_id="c", user_id="u", title="我的对话")
    assert r1["title"] == "我的对话"
    # 缺 title 时不崩, 返 None 或空字符串
    r2 = svc.create_share(conv_id="c", user_id="u", title=None)
    assert r2["title"] is None or r2["title"] == ""


def test_create_share_sets_default_ttl_7_days():
    """默认 expires_at = now + 7d"""
    from src.common import defaults
    from src.chat_share.service import ChatShareService
    svc = ChatShareService(repo=MagicMock())
    result = svc.create_share(conv_id="c", user_id="u", title="t")
    # expires_at 距 now 应在 6-8 天之间
    delta = result["expires_at"] - datetime.utcnow()
    assert timedelta(days=6) < delta < timedelta(days=8)


def test_create_share_messages_snapshot_stored_as_json():
    """messages 序列化为 JSON 字符串存 DB"""
    from src.chat_share.service import ChatShareService
    repo = MagicMock()
    svc = ChatShareService(repo=repo)
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    svc.create_share(conv_id="c", user_id="u", title="t", messages=msgs)
    # 验证 repo.save 收到的 messages_json 字段
    call_kwargs = repo.save.call_args.kwargs
    import json
    parsed = json.loads(call_kwargs["messages_json"])
    assert len(parsed) == 2


# ---- get_share (公开, anon) ----

def test_get_share_returns_messages_deserialized():
    """get_share 返 messages 数组 (从 JSON 反序列化)"""
    from src.chat_share.service import ChatShareService
    import json
    msgs = [{"role": "user", "content": "hi"}]
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(
        share_id="abc123", title="t", messages_json=json.dumps(msgs),
        model="gpt-4o-mini", created_at=datetime.utcnow(),
    )
    svc = ChatShareService(repo=repo)
    result = svc.get_share("abc123")
    assert result["messages"] == msgs
    assert result["share_id"] == "abc123"


def test_get_share_raises_404_for_unknown():
    """share_id 不存在 → 抛 ShareNotFound (router 翻译 404)"""
    from src.chat_share.service import ChatShareService, ShareNotFound
    repo = MagicMock()
    repo.get_by_id.return_value = None
    svc = ChatShareService(repo=repo)
    with pytest.raises(ShareNotFound):
        svc.get_share("nope")


def test_get_share_excludes_sensitive_fields():
    """get_share 返 SharedConversationResponse, 不含 user_id / share_password / token"""
    from src.chat_share.service import ChatShareService
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(
        share_id="x", title="t", messages_json="[]",
        model="gpt-4o-mini", created_at=datetime.utcnow(),
        user_id="42",  # **不应泄漏**
    )
    svc = ChatShareService(repo=repo)
    result = svc.get_share("x")
    assert "user_id" not in result


# ---- revoke_share ----

def test_revoke_share_only_owner():
    """仅所有者能撤销, 否则抛 NotShareOwner"""
    from src.chat_share.service import ChatShareService, NotShareOwner
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(user_id="99")  # 别人的
    svc = ChatShareService(repo=repo)
    with pytest.raises(NotShareOwner):
        svc.revoke_share("x", current_user_id="42")


def test_revoke_share_owner_succeeds():
    """所有者撤销 → repo.delete 调用"""
    from src.chat_share.service import ChatShareService
    repo = MagicMock()
    repo.get_by_id.return_value = MagicMock(user_id="42")
    svc = ChatShareService(repo=repo)
    svc.revoke_share("x", current_user_id="42")
    repo.delete.assert_called_once_with("x")
```

- [ ] **Step 2: 跑测试验证全红**

```bash
cd packages/service
uv run pytest tests/chat_share/test_service.py -v
```

Expected: 9 FAIL.

- [ ] **Step 3: 写 migration**

创建 `packages/service/src/storage/migrations/versions/20260616_000000_add_chat_shares.py`:

```python
"""add chat_shares (2026-06-16)
存储 chat 对话分享快照, anon 公开读, 所有者撤销.
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "20260616_000000"
down_revision = "20260615_000000"  # 接 consolidated_pg_init
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_shares",
        sa.Column("share_id", sa.String(12), primary_key=True),  # nanoid 12
        sa.Column("conv_id", sa.String(128), nullable=False, index=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),  # 所有者
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("messages_json", sa.Text, nullable=False),  # 快照 JSON
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_chat_shares_conv_id_user_id", "chat_shares", ["conv_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_shares_conv_id_user_id", table_name="chat_shares")
    op.drop_table("chat_shares")
```

- [ ] **Step 4: 写 ORM + schemas + service + repo**

创建 5 个新文件, 按 spec §"API 设计" 实现. `service.py` 包含:
- `create_share(conv_id, user_id, title=None, messages=None) → {share_id, url, title, expires_at, created_at}`
- `get_share(share_id) → dict` (raises `ShareNotFound`)
- `revoke_share(share_id, current_user_id) → None` (raises `NotShareOwner` 或 `ShareNotFound` — 统一 404 防 ID 探测)
- `ChatShareService.__init__(repo)` — 接受 repo 注入 (测 mock)

`repo.py`: `save(share_id, conv_id, user_id, title, messages_json, model, expires_at)` / `get_by_id(share_id)` / `delete(share_id)`

URL 构造: 用 `os.getenv("WEB_BASE_URL", "http://localhost:3000")` + `f"/{locale}/chat/s/{share_id}"`

nanoid 12 字符: `import secrets; secrets.token_urlsafe(9)[:12]` (9 字节 base64 = 12 字符)

- [ ] **Step 5: 跑测试验证绿**

```bash
cd packages/service
uv run pytest tests/chat_share/test_service.py -v
```

Expected: 9 PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/chat_share/ \
        packages/service/src/storage/migrations/versions/20260616_000000_add_chat_shares.py \
        packages/service/tests/chat_share/test_service.py
git commit -m "feat(chat-share): data layer (migration + ORM + 9 service tests)"
```

---

## Task 2: 后端 share 路由 + files upload + approvals kind=like

**Files:**
- Create: `packages/service/src/chat_share/router.py`
- Create: `packages/service/tests/chat_share/test_router.py` + `test_files_upload.py`
- Modify: `packages/service/src/approvals/models.py` (`ApprovalKind` + "like")
- Modify: `packages/service/src/__init__.py` (register_routers)
- Modify: `packages/service/tests/test_api_contract.py` (`FRONTEND_EXPECTS` +4)

- [ ] **Step 1: 写 router 失败测试 (5 用例)**

`tests/chat_share/test_router.py`:

```python
def test_create_share_200_dev_mode(client, mock_service):
    """dev mode + 有效 body → 200 + share_id"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.create_share.return_value = {
            "share_id": "abc123456789",
            "url": "http://localhost:3000/zh/chat/s/abc123456789",
            "title": "t",
            "expires_at": None,
            "created_at": "2026-06-16T00:00:00Z",
        }
        resp = client.post("/api/chat/shares", json={"conv_id": "c1", "title": "t"})
        assert resp.status_code == 200
        assert resp.json()["share_id"] == "abc123456789"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_get_share_200_anon_no_token_required(client, mock_service):
    """**关键**: get_share 公开, anon 可读 (无 cookie)"""
    import os
    os.environ.pop("RAG_DEV_AUTH", None)
    mock_service.get_share.return_value = {
        "share_id": "x", "title": "t", "messages": [],
        "model": "gpt-4o-mini", "created_at": "2026-06-16T00:00:00Z",
    }
    resp = client.get("/api/chat/shares/abc123456789")
    assert resp.status_code == 200
    assert resp.json()["share_id"] == "x"


def test_get_share_404_for_unknown(client, mock_service):
    """**关键**: 不存在返 404 (公开, 不能返 401 否则暴露 ID 探测)"""
    from src.chat_share.service import ShareNotFound
    mock_service.get_share.side_effect = ShareNotFound("nope")
    resp = client.get("/api/chat/shares/nope")
    assert resp.status_code == 404


def test_revoke_share_200_owner(client, mock_service):
    """所有者撤销 → 204"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.delete("/api/chat/shares/abc123456789")
        assert resp.status_code == 204
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_revoke_share_403_non_owner(client, mock_service):
    """非所有者撤销 → 404 (跟不存在同异常, 防 ID 探测)"""
    from src.chat_share.service import ShareNotFound
    mock_service.revoke_share.side_effect = ShareNotFound("not owner")
    resp = client.delete("/api/chat/shares/abc123456789")
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试验证红**

Expected: 5 FAIL.

- [ ] **Step 3: 写 router**

```python
"""Chat share 路由 (2026-06-16) — 公开 share + 文件上传透传 Dify

POST   /api/chat/shares         (登录, 创建)
GET    /api/chat/shares/{id}    (公开, anon 可读)
DELETE /api/chat/shares/{id}    (登录, 所有者撤销)
POST   /api/chat/files          (登录, 透传 Dify Files API)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile, File
from ..middleware.auth import CurrentUser, resolve_user
from . import service as _service_mod
from .schemas import CreateShareRequest, ShareResponse, SharedConversationResponse

router = APIRouter(prefix="/api/chat", tags=["chat share"])


def _get_service():
    return _service_mod.ChatShareService()


@router.post("/shares", response_model=ShareResponse)
def create_share(req: CreateShareRequest, current: CurrentUser = Depends(resolve_user)):
    result = _get_service().create_share(
        conv_id=req.conv_id, user_id=str(current.id), title=req.title,
    )
    return ShareResponse(**result)


@router.get("/shares/{share_id}", response_model=SharedConversationResponse)
def get_share(share_id: str):
    """公开端点, anon 可读."""
    try:
        result = _get_service().get_share(share_id)
    except _service_mod.ShareNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SharedConversationResponse(**result)


@router.delete("/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(share_id: str, current: CurrentUser = Depends(resolve_user)):
    try:
        _get_service().revoke_share(share_id, current_user_id=str(current.id))
    except _service_mod.ShareNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(resolve_user),
):
    """透传 Dify /files/upload. 返 {uploadFileId}."""
    return await _get_service().upload_to_dify(file)
```

- [ ] **Step 4: 写 files upload 失败测试 (3 用例)**

`tests/chat_share/test_files_upload.py`:

```python
def test_upload_file_200_returns_upload_file_id(client, mock_service):
    """上传有效文件 → 200 + {uploadFileId: ...}"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        mock_service.upload_to_dify.return_value = {"uploadFileId": "file-abc-123"}
        resp = client.post(
            "/api/chat/files",
            files={"file": ("test.png", b"fake-png-bytes", "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["uploadFileId"] == "file-abc-123"
    finally:
        del os.environ["RAG_DEV_AUTH"]


def test_upload_file_oversize_413(client, mock_service):
    """>20MB → 413"""
    mock_service.upload_to_dify.side_effect = ValueError("oversize")
    resp = client.post(
        "/api/chat/files",
        files={"file": ("big.pdf", b"x" * 21_000_000, "application/pdf")},
    )
    assert resp.status_code == 413


def test_upload_file_disallowed_type_400(client):
    """.exe 等不允许类型 → 400"""
    import os
    os.environ["RAG_DEV_AUTH"] = "true"
    try:
        resp = client.post(
            "/api/chat/files",
            files={"file": ("hack.exe", b"MZ\x00\x00", "application/octet-stream")},
        )
        assert resp.status_code == 400
    finally:
        del os.environ["RAG_DEV_AUTH"]
```

- [ ] **Step 5: 改 approvals ApprovalKind**

`packages/service/src/approvals/models.py` 找 `class ApprovalKind`:

```python
class ApprovalKind(str, Enum):
    QA = "qa"
    TRIPLE = "triple"
    BATCH = "batch"
    OPTIMIZE = "optimize"
    LIKE = "like"  # (2026-06-16) 满意按钮接通
```

- [ ] **Step 6: 改 contract test FRONTEND_EXPECTS**

`tests/test_api_contract.py` 末尾加:

```python
# --- chat share + files (2026-06-16) ---
("POST", "/api/chat/shares"),
("GET", "/api/chat/shares/{share_id}"),
("DELETE", "/api/chat/shares/{share_id}"),
("POST", "/api/chat/files"),
```

- [ ] **Step 7: 跑全量测试 + commit**

```bash
cd packages/service
uv run pytest tests/chat_share/ tests/test_api_contract.py -v
git add packages/service/src/chat_share/router.py \
        packages/service/src/approvals/models.py \
        packages/service/src/__init__.py \
        packages/service/tests/chat_share/ \
        packages/service/tests/test_api_contract.py
git commit -m "feat(chat-share): 4 routes + Dify files upload + kind=like approval"
```

---

## Task 3: 前端 share dialog + 公开页 + chatShareApi

**Files:**
- Create: `packages/web/lib/api/chat_share.ts` + `.test.ts`
- Create: `packages/web/components/chat/shared-chat-view.tsx` + `.test.tsx`
- Create: `packages/web/components/chat/share-dialog.tsx` + `.test.tsx`
- Create: `packages/web/app/[locale]/chat/s/[shareId]/page.tsx`
- Modify: `packages/web/components/chat/ChatShell.tsx` (头部 Share 图标 + 状态)
- Modify: `packages/web/components/chat/ChatShell.test.tsx` (+1 测试)
- Modify: `packages/web/messages/{zh,en}.json` (+6 字符串)

- [ ] **Step 1: 写 chatShareApi 失败测试 (3 用例)**

`lib/api/chat_share.test.ts`:

```typescript
import { apiFetch } from "./config";
vi.mock("./config", () => ({ apiFetch: vi.fn() }));
import { chatShareApi } from "./chat_share";
const mocked = vi.mocked(apiFetch);

describe("chatShareApi", () => {
  afterEach(() => vi.clearAllMocks());
  it("create → POST /api/chat/shares", async () => {
    mocked.mockResolvedValue({ share_id: "abc", url: "http://.../abc", title: "t", expires_at: null, created_at: "2026-06-16T00:00:00Z" });
    await chatShareApi.create({ convId: "c1", title: "t" });
    expect(mocked).toHaveBeenCalledWith("/api/chat/shares", expect.objectContaining({ method: "POST", body: { conv_id: "c1", title: "t" } }));
  });
  it("get → GET /api/chat/shares/{id} (公开, anon)", async () => {
    mocked.mockResolvedValue({ share_id: "abc", title: "t", messages: [], model: null, created_at: "" });
    await chatShareApi.get("abc");
    expect(mocked).toHaveBeenCalledWith("/api/chat/shares/abc", expect.objectContaining({ method: "GET" }));
  });
  it("revoke → DELETE /api/chat/shares/{id}", async () => {
    mocked.mockResolvedValue(undefined);
    await chatShareApi.revoke("abc");
    expect(mocked).toHaveBeenCalledWith("/api/chat/shares/abc", expect.objectContaining({ method: "DELETE" }));
  });
});
```

- [ ] **Step 2: 跑测试红 → 写 chatShareApi 实现**

`lib/api/chat_share.ts`:

```typescript
import { apiFetch } from "./config";
export interface ShareResponse {
  share_id: string; url: string; title: string;
  expires_at: string | null; created_at: string;
}
export interface SharedMessage { role: "user" | "assistant"; content: string; timestamp?: string; }
export interface SharedConversationResponse {
  share_id: string; title: string; messages: SharedMessage[];
  model: string | null; created_at: string;
}
export const chatShareApi = {
  async create(req: { convId: string; title?: string }): Promise<ShareResponse> {
    return apiFetch("/api/chat/shares", { method: "POST", body: { conv_id: req.convId, title: req.title } });
  },
  async get(shareId: string): Promise<SharedConversationResponse> {
    return apiFetch(`/api/chat/shares/${shareId}`, { method: "GET" });
  },
  async revoke(shareId: string): Promise<void> {
    await apiFetch(`/api/chat/shares/${shareId}`, { method: "DELETE" });
  },
};
```

- [ ] **Step 3: 加 i18n 字符串 (zh + en 同步)**

zh.json 加:

```json
"分享": "分享",
"分享对话": "分享对话",
"复制链接": "复制链接",
"已复制": "已复制",
"撤销分享": "撤销分享",
"我的分享": "我的分享"
```

- [ ] **Step 4: 写 shared-chat-view 失败测试 (3 用例)**

`components/chat/shared-chat-view.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { SharedChatView } from "./shared-chat-view";
describe("SharedChatView", () => {
  it("渲染 messages", () => {
    render(<SharedChatView shareId="x" title="t" messages={[{role: "user", content: "hi"}, {role: "assistant", content: "hello"}]} model="gpt-4o-mini" createdAt="2026-06-16" />);
    expect(screen.getByText("hi")).toBeInTheDocument();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
  it("不渲染 MessageFeedback (data-testid 不存在)", () => {
    render(<SharedChatView shareId="x" title="t" messages={[{role: "assistant", content: "x"}]} model="" createdAt="" />);
    expect(screen.queryByTestId(/message-feedback/)).not.toBeInTheDocument();
  });
  it("不渲染 Composer", () => {
    render(<SharedChatView shareId="x" title="t" messages={[]} model="" createdAt="" />);
    expect(screen.queryByTestId("composer-textarea")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 5: 写 SharedChatView 实现**

`components/chat/shared-chat-view.tsx`:

```tsx
"use client";
// 公开 share 页只读对话视图 (2026-06-16)
import type { SharedMessage } from "@/lib/api/chat_share";
import { MessageBubble } from "./MessageBubble";

export interface SharedChatViewProps {
  shareId: string;
  title: string;
  messages: SharedMessage[];
  model: string | null;
  createdAt: string;
}

export function SharedChatView({ title, messages, model, createdAt }: SharedChatViewProps) {
  return (
    <div className="max-w-3xl mx-auto py-8 px-4" data-testid="shared-chat-view">
      <header className="border-b pb-4 mb-6">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <div className="text-sm text-muted-foreground mt-1">
          {model && <span>{model}</span>}
          {createdAt && <span className="ml-3">{new Date(createdAt).toLocaleDateString()}</span>}
        </div>
      </header>
      <div className="space-y-4">
        {messages.map((m, i) => (
          <MessageBubble
            key={i}
            message={{ id: `shared-${i}`, role: m.role, content: m.content }}
            // 关键: 不传 pairedQuestion → MessageBubble 内部不会渲染 MessageFeedback
          />
        ))}
      </div>
      <footer className="mt-12 pt-4 border-t text-center text-xs text-muted-foreground">
        via RAG Project
      </footer>
    </div>
  );
}
```

- [ ] **Step 6: 写 RSC 公开页**

`app/[locale]/chat/s/[shareId]/page.tsx`:

```tsx
import { chatShareApi } from "@/lib/api/chat_share";
import { SharedChatView } from "@/components/chat/shared-chat-view";

export default async function SharedChatPage({ params }: { params: Promise<{ locale: string; shareId: string }> }) {
  const { shareId } = await params;
  try {
    const data = await chatShareApi.get(shareId);
    return (
      <>
        <meta name="robots" content="noindex" />
        <SharedChatView {...data} />
      </>
    );
  } catch {
    return <div className="text-center py-12">分享链接无效或已过期</div>;
  }
}
```

> **鉴权**: RSC 调 `apiFetch` 跟客户端同链路, anon 走 AuthBootstrap 自动拿 token. `GET /api/chat/shares/{id}` 是公开端点, 鉴权通过.

- [ ] **Step 7: 写 share-dialog 失败测试 (4 用例)**

`components/chat/share-dialog.test.tsx`:

```tsx
vi.mock("lucide-react", () => ({ Share2: () => <span data-testid="icon-share" />, Copy: () => <span data-testid="icon-copy" />, Trash2: () => <span data-testid="icon-trash" /> }));
vi.mock("@/lib/api/chat_share", () => ({ chatShareApi: { create: vi.fn(), get: vi.fn(), revoke: vi.fn() } }));
vi.mock("next-intl", () => ({ useTranslations: () => (k: string) => k }));
// 4 测试: 打开 → 弹创建; 调 create 返 URL; 复制; 撤销
```

- [ ] **Step 8: 写 ShareDialog 实现**

`components/chat/share-dialog.tsx` (~150 行, 创建 + URL 显示 + 复制 + 列表 + 撤销)

- [ ] **Step 9: 改 ChatShell 头部加 Share 图标 + 状态 + 测试**

`ChatShell.tsx`:
- import `Share2` from lucide-react
- import `ShareDialog`
- 加 `shareOpen` state
- 头部 Brain 图标旁加 Share 图标按钮
- 末尾挂 `<ShareDialog open={shareOpen} onOpenChange={setShareOpen} convId={currentId} />`

`ChatShell.test.tsx` +1: 渲染 Share 按钮 + 点击弹 Dialog

- [ ] **Step 10: 跑前端全量测试 + commit**

```bash
cd packages/web
bun run test -- chat_share shared-chat-view share-dialog ChatShell
git add packages/web/lib/api/chat_share.ts packages/web/lib/api/chat_share.test.ts \
        packages/web/components/chat/shared-chat-view.tsx packages/web/components/chat/shared-chat-view.test.tsx \
        packages/web/components/chat/share-dialog.tsx packages/web/components/chat/share-dialog.test.tsx \
        packages/web/app/[locale]/chat/s/[shareId]/page.tsx \
        packages/web/components/chat/ChatShell.tsx packages/web/components/chat/ChatShell.test.tsx \
        packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(chat): ShareDialog + SharedChatView + /chat/s/[shareId] public page"
```

---

## Task 4: 前端 ImagePreview + MessageBubble 集成

**Files:**
- Create: `packages/web/components/common/image-preview.tsx` + `.test.tsx`
- Modify: `packages/web/components/chat/MessageBubble.tsx` (改 ReactMarkdown components.img)
- Modify: `packages/web/messages/{zh,en}.json` (+1 字符串: "点击图片放大")

- [ ] **Step 1: 写 ImagePreview 失败测试 (3 用例)**

`components/common/image-preview.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ImagePreview } from "./image-preview";
describe("ImagePreview", () => {
  it("open=true 渲染 src", () => { render(<ImagePreview open={true} onOpenChange={() => {}} src="https://x/y.png" alt="test" />); expect(screen.getByAltText("test")).toBeInTheDocument(); });
  it("点击外部关闭", () => { const fn = vi.fn(); render(<ImagePreview open={true} onOpenChange={fn} src="x" alt="" />); fireEvent.click(screen.getByRole("dialog")); expect(fn).toHaveBeenCalledWith(false); });
  it("ESC 关闭", () => { const fn = vi.fn(); render(<ImagePreview open={true} onOpenChange={fn} src="x" alt="" />); fireEvent.keyDown(document, { key: "Escape" }); expect(fn).toHaveBeenCalledWith(false); });
});
```

- [ ] **Step 2: 写 ImagePreview 实现**

`components/common/image-preview.tsx`:

```tsx
"use client";
import { Dialog, DialogContent } from "@/components/ui/dialog";
export interface ImagePreviewProps { open: boolean; onOpenChange: (open: boolean) => void; src: string; alt?: string; }
export function ImagePreview({ open, onOpenChange, src, alt = "" }: ImagePreviewProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl p-0 bg-transparent border-none">
        <img src={src} alt={alt} className="w-full h-auto max-h-[90vh] object-contain" />
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: 改 MessageBubble 集成**

`MessageBubble.tsx` 找 `<ReactMarkdown>{answer}</ReactMarkdown>`, 改为:

```tsx
const [previewSrc, setPreviewSrc] = useState<string | null>(null);
const components = {
  img: ({ src, alt }: { src?: string; alt?: string }) => (
    <img src={src} alt={alt} className="cursor-zoom-in max-w-full rounded" onClick={() => src && setPreviewSrc(src)} />
  ),
};
// JSX:
<ReactMarkdown components={components}>{answer}</ReactMarkdown>
{previewSrc && <ImagePreview open={true} onOpenChange={(o) => !o && setPreviewSrc(null)} src={previewSrc} />}
```

- [ ] **Step 4: 加 i18n 字符串**

zh.json: `"点击图片放大": "点击图片放大"`, en.json: `"点击图片放大": "Click to zoom"`

- [ ] **Step 5: 跑测试 + commit**

```bash
cd packages/web
bun run test -- image-preview MessageBubble
git add packages/web/components/common/image-preview.tsx packages/web/components/common/image-preview.test.tsx \
        packages/web/components/chat/MessageBubble.tsx \
        packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(chat): ImagePreview + clickable images in MessageBubble"
```

---

## Task 5: 前端媒体上传 (Composer 拆 + 3 子组件)

**Files:**
- Create: `packages/web/components/chat/composer-attachments.tsx` + `.test.tsx`
- Create: `packages/web/components/chat/voice-recorder.tsx` (含录音测试可能 mock MediaRecorder)
- Modify: `packages/web/components/chat/Composer.tsx` (拆: 留 Textarea + 调 attachments)
- Modify: `packages/web/components/chat/Composer.test.tsx` (改 import 路径 + 加集成测试)
- Modify: `packages/web/lib/api/chat.ts` (加 `uploadFile`)
- Modify: `packages/web/messages/{zh,en}.json` (+4 字符串: "图片"/"文件"/"语音"/"录音中...")

- [ ] **Step 1: 加 chatApi.uploadFile**

`lib/api/chat.ts` 加:

```typescript
async uploadFile(file: File): Promise<{ uploadFileId: string }> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/api/chat/files", { method: "POST", body: formData });
}
```

- [ ] **Step 2: 写 ComposerAttachments 失败测试 (4 用例)**

`composer-attachments.test.tsx`:
- 渲染 3 个按钮 (图片/文件/语音)
- 点图片 → FileDropzone open
- 选中文件 → 上传调 chatApi.uploadFile
- 显示上传中缩略图

- [ ] **Step 3: 写 ComposerAttachments 实现**

`composer-attachments.tsx` (~100 行, 3 类入口 + 缩略图 + 移除)

- [ ] **Step 4: 写 VoiceRecorder 实现**

`voice-recorder.tsx` (~80 行, 长按 start/stop, MediaRecorder → blob → onRecorded 回调)

- [ ] **Step 5: 改 Composer 拆 2 文件**

Composer.tsx 留 Textarea 容器 + 调 `<ComposerAttachments>`. 现有 5 个 Composer 测试改 import 路径.

- [ ] **Step 6: 跑测试 + commit**

```bash
cd packages/web
bun run test -- composer-attachments Composer
git add packages/web/components/chat/composer-attachments.tsx packages/web/components/chat/composer-attachments.test.tsx \
        packages/web/components/chat/voice-recorder.tsx \
        packages/web/components/chat/Composer.tsx packages/web/components/chat/Composer.test.tsx \
        packages/web/lib/api/chat.ts \
        packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(chat): Composer split + 3 media upload entry points (image/file/voice)"
```

---

## Task 6: 前端满意按钮接通 (kind=like approval)

**Files:**
- Modify: `packages/web/components/chat/MessageFeedback.tsx` (满意按钮接通)
- Modify: `packages/web/components/chat/MessageFeedback.test.tsx` (+2 测试)
- Modify: `packages/web/app/[locale]/_actions/knowledge.ts` (加 `likeAnswer` server action)
- Modify: `packages/web/messages/{zh,en}.json` (+1 字符串: "已点赞")

- [ ] **Step 1: 改 server action 加 likeAnswer**

`app/[locale]/_actions/knowledge.ts` 加:

```typescript
export async function likeAnswer(input: { question: string; answer: string; messageId: string }): Promise<{ id: number } | { error: string }> {
  const approvals = await getServerApprovals();
  const r = await approvals.submit("like", { question: input.question, answer: input.answer, message_id: input.messageId });
  return r.ok ? { id: r.id } : { error: r.error };
}
```

- [ ] **Step 2: 改 MessageFeedback 满意按钮**

`MessageFeedback.tsx` 找 "满意" 按钮 (现 disabled), 改为:

```tsx
<Button onClick={async () => {
  setSubmitting(true);
  const r = await likeAnswer({ question, answer: originalAnswer, messageId });
  if ("id" in r) { toast.success(t("已点赞")); setLiked(true); } else { toast.error(r.error); }
  setSubmitting(false);
}} disabled={liked || submitting}>
  <ThumbsUp /> 满意
</Button>
```

- [ ] **Step 3: +2 测试**

`MessageFeedback.test.tsx`:
- 满意点击 → 调 likeAnswer → toast success → 按钮变 liked
- likeAnswer 失败 → toast error, 按钮不变

- [ ] **Step 4: 跑测试 + commit**

```bash
cd packages/web
bun run test -- MessageFeedback
git add packages/web/components/chat/MessageFeedback.tsx packages/web/components/chat/MessageFeedback.test.tsx \
        packages/web/app/[locale]/_actions/knowledge.ts \
        packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(chat): MessageFeedback 满意按钮接通 kind=like approval"
```

---

## Task 7: 端到端验证 + handoff

- [ ] **Step 1: 全量测试**

```bash
cd packages/service
uv run pytest tests/chat_share/ tests/test_api_contract.py tests/approvals/ -v
cd packages/web
bun run test
bun run lint
bun run typecheck
```

- [ ] **Step 2: 写 handoff doc**

`docs/superpowers/handoffs/2026-06-16-chat-share-and-media.md`

- [ ] **Step 3: Commit handoff**

```bash
git add docs/superpowers/handoffs/2026-06-16-chat-share-and-media.md
git commit -m "docs(handoff): chat share + media upload + image preview complete"
```

---

## 验证清单

- [ ] 后端 17 测试全绿
- [ ] 前端 20 测试全绿
- [ ] lint / typecheck 全 PASS
- [ ] 手测 E2E:
  1. 主 chat 点 Share → 弹 Dialog → 点创建 → 看到 URL → 复制
  2. 复制 URL 开新 incognito → 看到公开页 → 看不到反馈/Composer/Brain
  3. 主 chat 上传图片 → 发送 → 消息列表点图片 → 弹 lightbox
  4. 主 chat 长按语音 → 录音 → 发送
  5. 主 chat 满意某条 → toast → 按钮变 liked → 撤销不了 (一次性)
  6. 主页 → 撤销分享 → 公开 URL 失效 (404)
