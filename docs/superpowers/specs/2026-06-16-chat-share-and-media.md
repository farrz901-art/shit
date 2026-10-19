# Chat 分享 + 媒体上传 + 图片预览 设计

**日期**: 2026-06-16
**状态**: 设计中
**作者**: 用户需求 + 第一性原理分析
**相关代码**: `packages/web/app/[locale]/chat/` + `packages/web/components/chat/` + `packages/service/src/{approvals,chat,ingest}/`

## Context

### 现状 (2026-06-16 探索)

**Chat 子系统完整且自洽** (零外部数据入口):
- `/[locale]/chat` 唯一 page → `<ChatShell>` 状态机 host
- 状态全在 localStorage (conversations / messagesByConv / streamingByConv)
- `ChatShell` 唯一消费方 (`grep "import.*ChatShell"` 唯一命中)
- `proxy.ts` 不挡 `/chat`, 公开 anon 即可
- `BFF /api/chat/messages` 走 `x-chat-token` 对称验证 (anti-abuse, 非身份)
- `Composer` 62 行, 纯 Textarea, **零媒体上传**
- `MessageFeedback` 128 行, 满意按钮 disabled, "不满意 → 优化" 流走 `optimizeAnswer` server action
- `FileDropzone` 143 行, 通用拖拽, 接受 `accept="image/*"` / `accept=".pdf,.docx"`
- `MessageBubble` 用 `<ReactMarkdown components.img>`, 无 lightbox, 无点击放大
- **无 lightbox / Image 包装 / share 路由** (grep 全空)

### 决策记录 (用户 2026-06-16)

- **Q1: 分享路由是给谁?** → 给**外部普通用户** (内部用户用主 chat). 客户 / 合作伙伴临时看一段对话
- **Q2: 分享页能看到反馈 / 继续聊吗?** → **看不到** (read-only). 跟 ChatGPT / Claude.ai 公开 share 模式一致
- **Q3: 语音输入?** → MediaRecorder 录音 (类似微信长按说话)
- **Q4: 满意按钮 (当前 disabled)?** → 接通, 走 `kind=like` approval
- **Q5: Dify Files API?** → 已支持, 后端去配 upload 端点
- **Q6: 图片预览?** → chat 页面 + 发送前两场景共用一个 `<ImagePreview>` 组件 (shadcn Dialog 包)

## 目标

1. **无头分享路由**: `/[locale]/chat/s/[shareId]` (RSC, 公开, anon 可读), 主 chat 页加 `<ShareDialog>` 生成 / 撤销
2. **媒体上传**: Composer 增图片 / 文件 / 语音 3 类入口, 走 Dify Files API
3. **图片预览**: 消息内点击放大 + 发送前缩略图
4. **满意按钮**: 接通 → `kind=like` approval
5. **统一工程纪律**: 6 commits, 每块 TDD red→绿, 不破现有 chat 流程

## 非目标 (YAGNI)

- **不做 share 时的消息编辑 / 撤回** (share 出去是当时快照, 不可改)
- **不做 share 时 PII 自动脱敏** (B2B 信任用户自审; 真要脱敏放 LLM 层做)
- **不做 share 公开搜索** (noindex, 不进 Google)
- **不做视频 / PDF 预览** (本轮只图片; 视频后置)
- **不做多模态 LLM 后端直连** (走 Dify Files API, 跟现有 Chatflow 协议对齐)
- **不做语音实时转文字** (录音 → 上传 Dify → Dify 转写; 客户端不预转)
- **不做语音可视化波形** (录音状态用 isRecording 提示即可)
- **不做 share 访问统计** (YAGNI; 真要看走 Langfuse 加事件)
- **不做客户端 share link OpenGraph 抓取** (公开页是 chat 内容, 不是营销页)

## 架构总览

```
┌────────────────────────────────────────────────────────────────────┐
│ 主 chat 页 (/[locale]/chat) — 内部用户                                │
│   ├─ <ChatShell> 状态机 (现有)                                       │
│   │   ├─ 头部: 现有 Brain 图标 + 新 Share 图标 → <ShareDialog>       │
│   │   ├─ <MessageList> → <MessageBubble>                            │
│   │   │   └─ <MessageFeedback> (满意按钮接通 → kind=like)            │
│   │   ├─ <Composer> 拆分:                                            │
│   │   │   ├─ <ComposerTextarea> (现有 Textarea)                       │
│   │   │   └─ <ComposerAttachments> (新, ≤100 行, 3 类入口)            │
│   │   │       ├─ 图片按钮 → <FileDropzone accept="image/*">          │
│   │   │       ├─ 文件按钮 → <FileDropzone accept=".pdf,.docx,...">  │
│   │   │       └─ 语音按钮 (长按) → <VoiceRecorder> (MediaRecorder)   │
│   │   └─ <MemoryManagementDialog> (Phase 2 已有)                      │
│   └─ <ShareDialog> (新)                                              │
│       ├─ "创建分享" → POST /api/chat/shares → 返 {share_id, url}    │
│       └─ "我的分享" 列表 → DELETE /api/chat/shares/{id}              │
│                                                                       │
│ 公开 share 页 (/[locale]/chat/s/[shareId]) — 外部用户                  │
│   ├─ RSC 调 GET /api/chat/shares/{shareId} → 拉数据                   │
│   ├─ <SharedChatView> (新, 只读)                                     │
│   │   ├─ 极简 Header (项目名 + 标题)                                  │
│   │   ├─ <MessageBubble> 同款, 但 props.disableFeedback=true          │
│   │   └─ 底部品牌区 "via {project name}"                             │
│   └─ <meta name="robots" content="noindex"> 防搜索收录                │
│                                                                       │
│ 后端新增 4 端点:                                                     │
│   POST   /api/chat/shares          (登录, 创建)                        │
│   GET    /api/chat/shares/{id}     (公开, anon 可读)                   │
│   DELETE /api/chat/shares/{id}     (登录, 仅所有者)                    │
│   POST   /api/chat/files           (登录, 透传 Dify Files API)         │
│                                                                       │
│ 后端新表: chat_shares (id, conv_id, user_id, title, messages_json,    │
│                          created_at, expires_at?, password?)          │
│                                                                       │
│ Dify Files API (现有 Dify 实例, 已配 file input 节点):                │
│   POST /files/upload (multipart) → {id: uploadFileId}                  │
└────────────────────────────────────────────────────────────────────┘
```

**关键决策点**:
- **Share 选 RSC + 独立 page** (C 策略): 跟 ChatShell 0 耦合, 不污染主 chat 状态机
- **Composer 拆 2 文件** (CLAUDE.md ≤100 行): `<ComposerTextarea>` + `<ComposerAttachments>` (主 Composer 变容器)
- **Voice 走 Dify**: 录音 webm/opus → 上传 Dify → Dify 用 STT 节点转写, 客户端零解析
- **图片预览零三方依赖**: shadcn Dialog (已有) 包装, 不引 `yet-another-react-lightbox`
- **Like 走 approvals**: 跟"不满意+优化"同 server action 流, 后端 `ApprovalKind` 加 1 值

## 文件清单

### 新增 (7)

| 文件 | 职责 |
|------|------|
| `packages/web/app/[locale]/chat/s/[shareId]/page.tsx` | RSC 公开页, server-side 拉 share 数据, 渲染 SharedChatView |
| `packages/web/components/chat/shared-chat-view.tsx` | 只读对话渲染, 接 `messages: ChatMessage[]` prop, 不挂 Composer / Feedback |
| `packages/web/components/chat/share-dialog.tsx` | 主 chat 页分享弹框, 创建 / 复制 URL / 撤销 |
| `packages/web/components/chat/composer-attachments.tsx` | Composer 附件子组件, 3 类入口 + 预览 + 移除 |
| `packages/web/components/chat/voice-recorder.tsx` | MediaRecorder 长按录音 + 状态指示 |
| `packages/web/components/common/image-preview.tsx` | shadcn Dialog 包原图, 消息点击 + 发送前共用 |
| `packages/service/src/chat_share/{router,service,models,repo}.py` | 后端 share CRUD + messages 快照存储 |

### 修改 (8)

| 文件 | 改动 |
|------|------|
| `packages/web/components/chat/Composer.tsx` | 拆: 留 Textarea + 调 `<ComposerAttachments>`, 仍 ≤100 行 |
| `packages/web/components/chat/MessageBubble.tsx` | `<ReactMarkdown components.img>` 加 onClick → `<ImagePreview>` |
| `packages/web/components/chat/MessageFeedback.tsx` | 满意按钮接通 → `kind=like` approval, 跟 optimize 走同流 |
| `packages/web/components/chat/ChatShell.tsx` | 头部加 Share 图标 + 状态 |
| `packages/web/lib/api/chat_share.ts` | 新 client: create / get / revoke |
| `packages/web/lib/api/chat.ts` | 加 `uploadFile(file): Promise<{uploadFileId}>` 走 Dify Files API |
| `packages/web/messages/{zh,en}.json` | 加 ~12 字符串 (share / upload / voice / image-preview / like) |
| `packages/service/src/approvals/models.py` | `ApprovalKind` 加 `"like"` |
| `packages/service/src/chat_share/router.py` (新) | 4 端点注册 |
| `packages/service/src/__init__.py` | `register_routers` 加 `chat_share_router` |
| `packages/service/src/storage/migrations/versions/20260616_000000_add_chat_shares.py` (新) | 1 张表, ORM + alembic |
| `packages/service/tests/chat_share/test_{service,router}.py` (新) | 8-10 测试 |

## API 设计

### 后端 share 4 端点

```python
# Pydantic schemas (新文件 src/chat_share/schemas.py)
class CreateShareRequest(BaseModel):
    conv_id: str = Field(..., max_length=128)  # 跟 Dify conversationId 对齐
    title: str | None = Field(None, max_length=200)  # 用户可编辑, None 则用首消息前 50 字

class ShareResponse(BaseModel):
    share_id: str
    url: str  # 完整 URL: https://{host}/{locale}/chat/s/{share_id}
    title: str
    expires_at: datetime | None
    created_at: datetime

class SharedConversationResponse(BaseModel):
    share_id: str
    title: str
    messages: list[SharedMessage]  # 不含 metadata.user_id / token
    model: str | None
    created_at: datetime
    # 不含 user_id / share_id 撤销密码 任何内部字段

class SharedMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str  # 纯文本, 不含 thinking / 引用
    timestamp: datetime | None

# router
@router.post("/api/chat/shares", response_model=ShareResponse)
def create_share(req: CreateShareRequest, current: CurrentUser = Depends(resolve_user)):
    """登录用户创建 share. conv_id 是 Dify conversationId.
    1. 拉 conv 全部 messages (从 Dify 查 或 从 localStorage 同步过来)
    2. 生成短 share_id (nanoid 12 字符)
    3. 存 chat_shares 表
    4. 返 share_id + url
    """

@router.get("/api/chat/shares/{share_id}", response_model=SharedConversationResponse)
def get_share(share_id: str):
    """公开端点, anon 可读. 返 messages 快照 + 元数据.
    不返 user_id / token / 任何 PII. 401 share_id 不存在.
    """

@router.delete("/api/chat/shares/{share_id}")
def revoke_share(share_id: str, current: CurrentUser = Depends(resolve_user)):
    """仅所有者可删. 返 204 / 404 (不区分, 防 ID 探测)."""
```

### 后端 files upload 1 端点 (BFF 透传 Dify)

```python
@router.post("/api/chat/files")
async def upload_file(file: UploadFile, current: CurrentUser = Depends(resolve_user)):
    """BFF 透传 Dify /files/upload. 返 {uploadFileId}.
    限制: 单文件 ≤20MB, 类型 image/*|audio/*|application/pdf|...
    """
    # multipart 转发到 DIFY_BASE_URL/files/upload
    # 返 {id: "uploadFileId"}
```

### 前端 memoryApi 扩展 (前端 API client)

```typescript
// lib/api/chat_share.ts
export const chatShareApi = {
  async create(req: { convId: string; title?: string }): Promise<ShareResponse> {
    return apiFetch("/api/chat/shares", { method: "POST", body: req });
  },
  async get(shareId: string): Promise<SharedConversationResponse> {
    return apiFetch(`/api/chat/shares/${shareId}`, { method: "GET" });
  },
  async revoke(shareId: string): Promise<void> {
    await apiFetch(`/api/chat/shares/${shareId}`, { method: "DELETE" });
  },
};

// lib/api/chat.ts 加
async uploadFile(file: File): Promise<{ uploadFileId: string }> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch("/api/chat/files", { method: "POST", body: formData });
}
```

## 数据契约

**后端 → 前端 (Share)**:
- `POST /api/chat/shares` body `{conv_id, title?}` → `{share_id, url, title, expires_at, created_at}`
- `GET /api/chat/shares/{share_id}` → `{share_id, title, messages[], model, created_at}`
- `DELETE /api/chat/shares/{share_id}` → 204 / 403 / 404

**前端 → Dify Files API (经 BFF 透传)**:
- `POST /api/chat/files` multipart `file=...` → `{uploadFileId: string}`

**前端 → 后端 (Chat message 含 files)**:
- `SendMessageRequest.files: ChatFile[]` 字段已存在 (`lib/chat/types.ts:15-20`), 现在真用上
- `ChatFile { type: "image"|"document"|"audio", transferMethod: "local_file", uploadFileId }`

**鉴权矩阵**:

| 端点 | 创建 share | 读 share | 撤销 share | 上传 file |
|------|------|------|------|------|
| 必须登录 | ✅ | ❌ (anon) | ✅ | ✅ |
| 共享外部 | ❌ | ✅ | ❌ | ❌ |

## 测试策略

### 后端 share service (test_service.py, 6-8 用例)

```python
def test_create_share_generates_short_id_and_url
def test_create_share_with_explicit_title
def test_create_share_auto_title_from_first_message
def test_get_share_returns_messages_snapshot
def test_get_share_anon_no_token_required
def test_get_share_returns_404_for_unknown_id
def test_revoke_share_only_owner_succeeds
def test_revoke_share_returns_403_for_non_owner
```

### 后端 share router (test_router.py, 4-5 用例)

```python
def test_create_share_200_dev_mode
def test_create_share_401_without_token
def test_get_share_200_anon  # **关键: anon 可读**
def test_revoke_share_200_owner
def test_revoke_share_403_non_owner
```

### 后端 files upload (test_router.py, 3 用例)

```python
def test_upload_file_200_returns_upload_file_id
def test_upload_file_oversize_413
def test_upload_file_disallowed_type_400
```

### 前端 chatShareApi (test_chat_share.test.ts, 4 用例)

```typescript
memoryApi.create → POST /api/chat/shares
memoryApi.get → GET /api/chat/shares/{id}
memoryApi.revoke → DELETE /api/chat/shares/{id}
chatApi.uploadFile → POST /api/chat/files (multipart)
```

### 前端 SharedChatView (test_shared_chat_view.test.tsx, 3 用例)

```typescript
公开页 渲染 messages
不渲染 MessageFeedback (data-testid 不存在)
不渲染 Composer (data-testid 不存在)
```

### 前端 ShareDialog (test_share_dialog.test.tsx, 4 用例)

```typescript
点创建 → 调 chatShareApi.create → 弹 URL
点复制 → 调 navigator.clipboard
列出现有 shares + 撤销
创建失败 → toast 错误
```

### 前端 ComposerAttachments (test_composer_attachments.test.tsx, 4 用例)

```typescript
点图片 → FileDropzone open
长按语音 → MediaRecorder start
选中文件 → 上传 + 缩略图 + 移除按钮
```

### 前端 ImagePreview (test_image_preview.test.tsx, 3 用例)

```typescript
点击图片 → 弹 Dialog
Dialog 渲染原图
ESC 关闭
```

### 前端 MessageFeedback like (改 test_message_feedback.test.tsx, +2)

```typescript
满意按钮点击 → 调 likeApproval
toast success
```

**总计**: 后端 ~17 测试, 前端 ~20 测试

## 风险与回滚

**风险 1**: Share URL 短 ID 12 字符 (nanoid) 熵 ~71 bits, 但若 `/chat/s/` 路由暴露公网, 攻击者可枚举
- **缓解**: 短 ID 后端生成, rate limit (同 IP 每分钟 60 次), 404 跟 200 响应时间归一 (防 timing attack)
- **回滚**: 删 share 路由, ChatShell 去掉 Share 按钮

**风险 2**: Dify Files API 鉴权是 `Authorization: Bearer {DIFY_API_KEY}`, BFF 透传时必须藏 key 不能漏给前端
- **缓解**: BFF `/api/chat/files` 是 server-side, 走 `apiProxy` 或直接 fetch, 绝不让浏览器拼 Authorization header
- **验证**: 浏览器 devtools 看 `/api/chat/files` 请求, 确认无 Authorization header (key 在 BFF 内)

**风险 3**: VoiceRecorder 走 MediaRecorder, 浏览器需授权麦克风, iOS Safari 兼容性差 (webm/opus 不支持)
- **缓解**: 检测 `MediaRecorder.isTypeSupported`, 不支持时降级到提示"请用 Chrome / Edge"
- **降级**: iOS Safari → 仅文件上传, 无录音 (跟用户说"录音功能仅支持 Chrome")

**风险 4**: Composer 拆 2 文件改动面大, 现有 5 个测试可能破
- **缓解**: `<ComposerTextarea>` 保持跟旧 Composer 行为一致 (value/onChange/onSend), 现有测试只改 import 路径
- **回滚**: 还原 Composer 单文件

**风险 5**: Share messages 快照存 JSON 字段, 大对话 (100+ 轮) JSONB 体积大
- **缓解**: 截断到 200 轮, 加 `truncated: bool` 字段告知
- **后续**: 真要存大对话改 row-per-message + 单独表

**风险 6**: 图片 lightbox 弹窗在移动端体验差
- **缓解**: shadcn Dialog 自带响应式, 限制 max-w
- **回滚**: 还原 `<ReactMarkdown components.img>` 默认渲染

**风险 7**: Dify Chatflow 当前是否真接了 file input 节点, 跑通后端之前不能确认
- **缓解**: 跟用户在 commit 后 E2E 验证; 失败则保留后端 upload 端点, 但 Dify 侧 bypass
- **决策**: 按 `feedback-check-official-docs-before-coding` 规则, 实施时先 curl 测 Dify `/files/upload` 通不通, 不通则 plan 调整

## 实施切片 (见 plan, 不在本 spec)

按依赖分 7 个 task, 写 `plans/2026-06-16-chat-share-and-media.md` 时细化:

1. **后端 share 数据层**: migration + ORM + repo + 4 个 service 方法 (TDD)
2. **后端 share 路由**: 4 端点 + 契约测试
3. **后端 files upload**: 1 BFF 端点 + Dify 透传
4. **前端 share dialog + 公开页**: 2 新组件 + ChatShell 头部 + share client
5. **前端图片预览**: ImagePreview + MessageBubble 改 + 发送前缩略
6. **前端媒体上传 (图片/文件/语音)**: Composer 拆 + 3 子组件 + upload 集成
7. **前端满意按钮接通**: kind=like approval + toast

每 task 走 TDD 红→绿, commit 前跑 lint-staged + 全量测试. 总共预计 7-9 commits (按 `feedback-commit-in-batches-for-large-changes`).

## 参考

- [lib/chat/types.ts](../../../packages/web/lib/chat/types.ts) — `ChatFile` 协议已定义 (`type`, `transferMethod`, `uploadFileId`)
- [components/common/file-dropzone.tsx](../../../packages/web/components/common/file-dropzone.tsx) — 通用拖拽, 直接复用
- [app/[locale]/_actions/knowledge.ts](../../../packages/web/app/[locale]/_actions/knowledge.ts) — `optimizeAnswer` server action 范本
- [lib/api/approvals.ts](../../../packages/web/lib/api/approvals.ts) — 5 端点 wrapper 范本
- [approvals/models.py ApprovalKind](../../../packages/service/src/approvals/models.py) — 加 `"like"` 位置
- [components/header.tsx](../../../packages/web/components/header.tsx) — 全站 NavLink, 公开页不挂
- [proxy.ts](../../../packages/web/proxy.ts) — `isProtected` 判定, `/chat/s/*` 不应进 protected
- ChatGPT 公开 share 模式 (chatgpt.com/share/{uuid}): 公开 URL, 标题自动生成, 元数据 header, 纯 read-only, 底部品牌
- Claude.ai 公开 share 模式 (claude.ai/share/{id}): 类似 ChatGPT, 无 "继续聊" 按钮
- [feedback-check-official-docs-before-coding](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-check-official-docs-before-coding.md) — Dify Files API 实施前先 curl 验
- [feedback-filename-kebab-case-strict](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-filename-kebab-case-strict.md) — 文件名 kebab-case
- [feedback-react-file-size-and-dialog-naming](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-react-file-size-and-dialog-naming.md) — Dialog kebab-case, 文件 ≤300 行
- [feedback-no-shim-no-minimal-changes](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-no-shim-no-minimal-changes.md) — 严禁 shim
- [feedback-commit-in-batches-for-large-changes](../../../.claude/projects/c--doc-Code-worktrees-rag-refactor/memory/feedback-commit-in-batches-for-large-changes.md) — 大改动按逻辑单元拆 commit
