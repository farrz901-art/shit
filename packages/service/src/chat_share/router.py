"""chat_share 路由 (2026-06-16) — 7 端点

POST   /api/chat/shares         (登录, 创建 share)
GET    /api/chat/shares         (登录, 按 conv_id 列当前用户的 share 元数据)
GET    /api/chat/shares/{id}    (公开, anon 可读, 不含 user_id)
DELETE /api/chat/shares/{id}    (登录, 所有者撤销; 非所有者 → 404 防 ID 探测)
POST   /api/chat/files          (登录, multipart 透传 Dify Files API; 20MB + 类型白名单)
POST   /api/chat/files/presign  (登录, 签 PUT URL 直传 MinIO; 同 20MB + 白名单)
POST   /api/chat/files/finalize (登录, 浏览器 PUT 完通知后端拉 bytes → Dify /files/upload)

鉴权:
- 创建 / 撤销 / 列表 / 上传 → Depends(resolve_user)
- 公开读 → 无鉴权依赖, anon 可直接 GET (跟 ChatGPT 公开 share 同模式)

文件上传限制:
- max 20MB (跟 Dify Files API 对齐)
- 允许类型: image/* / audio/* / application/pdf / text/*
- 禁用: application/octet-stream 等通用二进制 (跟潜在可执行混淆)
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from loguru import logger  # noqa: F401  跟 logging spec contract test (test_loguru_migration.py) 一致
from sqlalchemy.orm import Session

from ..common import defaults
from ..middleware.auth import CurrentUser, resolve_user
from ..storage import ObjectStoreError, get_object_store
from ..storage.session import get_session
from . import service as _service_mod  # noqa: F401  保留模块引用 (向后兼容 + 异常类改名)
from .repo import SqlAlchemyChatShareRepo
from .schemas import (
    CreateShareRequest,
    FinalizeChatFileRequest,
    FinalizeChatFileResponse,
    PresignChatFileRequest,
    PresignChatFileResponse,
    SharedConversationResponse,
    ShareListItem,
    ShareResponse,
    UploadFileResponse,
)
from .service import ChatShareService

router = APIRouter(prefix="/api/chat", tags=["chat-share"])


# ---- 工厂: per-request session (修 2026-06-30 _get_service bug) ----
# 之前 _get_service 把 session_scope (generator 函数) 当 Session 传给 repo,
# 导致 _session.query() 报 'function' object has no attribute 'query'.
# 修法: 改 FastAPI Depends 链, 跟 approvals/router.py 模式一致 —
#   get_session() → Session → SqlAlchemyChatShareRepo → ChatShareService.
# 测试用 app.dependency_overrides[_get_service] 替换, 跟 approvals 测试同模式.


def _get_session() -> Generator[Session]:
    """per-request 同步 session, 走 storage.session.get_session (expire_on_commit=False)."""
    yield from get_session()


def _get_repo(session: Session = Depends(_get_session)) -> SqlAlchemyChatShareRepo:
    """构造 repo 绑定本请求 session (sync)."""
    return SqlAlchemyChatShareRepo(session)


def _get_service(repo: SqlAlchemyChatShareRepo = Depends(_get_repo)) -> ChatShareService:
    """构造 service 绑定本请求 repo. 测试用 app.dependency_overrides 替换."""
    return ChatShareService(repo=repo)


# ---- 文件上传白名单 ----

# 允许的 MIME 前缀 / 精确匹配 (跟 Dify Files API 对齐)
_ALLOWED_MIME_PREFIXES: tuple[str, ...] = ("image/", "audio/", "text/", "video/")
_ALLOWED_MIME_EXACT: frozenset[str] = frozenset({"application/pdf"})
# 显式禁用的 MIME (避免把 .exe 等伪装成 application/octet-stream 透传)
_DISALLOWED_MIME_EXACT: frozenset[str] = frozenset(
    {
        "application/octet-stream",
        "application/x-msdownload",
        "application/x-msdos-program",
        "application/x-executable",
        "application/x-shockwave-flash",
    }
)


def _validate_upload(file: UploadFile) -> None:
    """校验文件大小 + 类型, 不通过 → HTTPException."""
    # 类型校验
    ct = (file.content_type or "").lower().split(";")[0].strip()
    if not ct:
        raise HTTPException(status_code=400, detail="缺少 Content-Type")
    if ct in _DISALLOWED_MIME_EXACT:
        raise HTTPException(status_code=400, detail=f"不允许的文件类型: {ct}")
    if ct in _ALLOWED_MIME_EXACT:
        pass  # 白名单精确命中
    elif any(ct.startswith(p) for p in _ALLOWED_MIME_PREFIXES):
        pass  # 白名单前缀命中
    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ct}")

    # 大小校验 (content_length 是 header 给的, 不一定准; 真校验靠 starlette 暂存大小)
    if file.size is not None and file.size > defaults.DEFAULT_CHAT_FILE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大 ({file.size} > {defaults.DEFAULT_CHAT_FILE_MAX_BYTES} bytes)",
        )


def _validate_mime_and_size(mime: str, size: int) -> None:
    """presign 端点用: 校验 mime + size 字符串, 复用白名单规则.

    Args:
        mime: Content-Type, 可带 charset (e.g. "image/png; charset=utf-8") → 取主类型
        size: 文件字节数, 超过 DEFAULT_CHAT_FILE_MAX_BYTES → 413
    """
    ct = (mime or "").lower().split(";")[0].strip()
    if not ct:
        raise HTTPException(status_code=400, detail="缺少 Content-Type")
    if ct in _DISALLOWED_MIME_EXACT:
        raise HTTPException(status_code=400, detail=f"不允许的文件类型: {ct}")
    if not (ct in _ALLOWED_MIME_EXACT or any(ct.startswith(p) for p in _ALLOWED_MIME_PREFIXES)):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ct}")
    if size > defaults.DEFAULT_CHAT_FILE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大 ({size} > {defaults.DEFAULT_CHAT_FILE_MAX_BYTES} bytes)",
        )


# ---- 端点 ----


@router.post(
    "/shares",
    response_model=ShareResponse,
    status_code=status.HTTP_200_OK,
    summary="创建对话快照分享",
    description=(
        "## 用途\n\n"
        "登录用户把某条对话 (conv_id) 打成不可变快照, 生成可公开访问的 share 链接, "
        "供匿名用户 (跟 ChatGPT 公开 share 同模式) 读取. 用于把对话结果发到 IM / 论坛.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫: 登录用户; anon 也能调但 service 强制要求 `user_id`.\n\n"
        "## 行为\n\n"
        "service 把 conversation messages 序列化进 share row, 生成 share_id (URL 友好短串). "
        "返 `{share_id, url, title, expires_at, created_at}`. 快照创建后不可改 (除撤销外)."
    ),
    responses={
        200: {"description": "share 创建成功, 含 URL 和元数据"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "conv_id 不存在或不属于当前用户"},
        422: {"description": "Pydantic 校验失败 (conv_id / title 格式)"},
    },
)
def create_share(
    req: CreateShareRequest,
    current: CurrentUser = Depends(resolve_user),
    service: ChatShareService = Depends(_get_service),
) -> ShareResponse:
    # (2026-06-30) 透传客户端发来的 messages 快照给 service 落库,
    # 跟 spec §风险 5 "截断 200 轮" 一致; Pydantic 已强制 min_length=1 / max_length=200.
    # exclude_none=True: timestamp 缺省时不写入 dict, 跟 task1 测试断言 2-key dict 对齐.
    messages_payload = [msg.model_dump(mode="json", exclude_none=True) for msg in req.messages]
    result = service.create_share(
        conv_id=req.conv_id,
        user_id=current.id,
        title=req.title,
        messages=messages_payload,
    )
    return ShareResponse(**result)


@router.get(
    "/shares/{share_id}",
    response_model=SharedConversationResponse,
    summary="公开读分享",
    description=(
        "## 用途\n\n"
        "匿名公开读 share 内容 (跟 ChatGPT 公开 share 同模式). 拿到 share_id 的任何人都能读, "
        "无需登录. 浏览器直接 GET 即可展示对话快照.\n\n"
        "## 鉴权\n\n"
        "**无鉴权** (anon 可直读).\n\n"
        "## 行为\n\n"
        "service 按 share_id 查快照, 返 messages + 元数据. "
        "**不含 user_id / token**: 公开响应里把创建者身份剥掉, 防止反向追溯. "
        "不存在 / 已撤销 → 404."
    ),
    responses={
        200: {"description": "快照内容 + 元数据 (不含 user_id / token)"},
        404: {"description": "share 不存在或已撤销"},
    },
)
def get_share(
    share_id: str,
    service: ChatShareService = Depends(_get_service),
) -> SharedConversationResponse:
    try:
        result = service.get_share(share_id)
    except _service_mod.ShareNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return SharedConversationResponse(**result)


@router.delete(
    "/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="撤销分享",
    description=(
        "## 用途\n\n"
        "创建者撤销自己创建的 share. 撤销后匿名 GET 同一 share_id 返 404.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫: 必须登录, service 校验 `share_id` 归属.\n\n"
        "## 行为\n\n"
        "service 标记 share 为已撤销. "
        "**非所有者 → 统一 404 (防 ID 探测)**: 即便 share_id 存在但属于别人, 也跟不存在一样返 404, "
        "不暴露 share_id 是否有效."
    ),
    responses={
        204: {"description": "撤销完成"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "share 不存在 OR 不属于当前用户 (统一 404 防 ID 探测)"},
    },
)
def revoke_share(
    share_id: str,
    current: CurrentUser = Depends(resolve_user),
    service: ChatShareService = Depends(_get_service),
) -> Response:
    try:
        service.revoke_share(share_id, current_user_id=current.id)
    except _service_mod.ShareNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        "`resolve_user` 守卫, 必须登录. 跨用户隔离: 仅返当前 user 自己的.\n\n"
        "## 行为\n\n"
        "走 `ix_chat_shares_conv_id_user_id` 复合索引. "
        "`?conv_id=` 必填, 不传 → 422. limit 默认 20, 上限 100."
    ),
    responses={
        200: {"description": "share 元数据列表, 最新在前"},
        401: {"description": "未登录 / token 无效"},
        422: {"description": "conv_id 缺失"},
    },
)
def list_shares(
    conv_id: str = Query(..., max_length=36, description="已登录用户 conv_id (server 端 UUID, String(36))"),
    limit: int = Query(20, ge=1, le=100, description="分页大小, 1-100"),
    current: CurrentUser = Depends(resolve_user),
    service: ChatShareService = Depends(_get_service),
) -> list[ShareListItem]:
    """按 (conv_id, user_id) 列 share 元数据."""
    rows = service.list_shares(conv_id=conv_id, user_id=current.id, limit=limit)
    return [ShareListItem(**row) for row in rows]


@router.post(
    "/files",
    response_model=UploadFileResponse,
    summary="上传文件 (透传 Dify)",
    description=(
        "## 用途\n\n"
        "浏览器 multipart 上传文件, 后端透传到 Dify `/files/upload`, 拿到 Dify `uploadFileId` "
        "供后续 chat 消息引用. 用于小文件 (≤20MB) 的同步上传.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫: 必须登录, `current.id` 用于 audit / Dify 透传标识.\n\n"
        "## 行为\n\n"
        "类型白名单: `image/*` / `audio/*` / `text/*` / `video/*` / `application/pdf`. "
        "**显式禁用**: `application/octet-stream` / `x-msdownload` / `x-msdos-program` / "
        "`x-executable` / `x-shockwave-flash` (避免把 .exe 等伪装透传). "
        "**大小上限 20MB** (跟 Dify Files API 对齐). "
        "超类型 → 400; 超大 → 413."
    ),
    responses={
        200: {"description": "上传成功, 返 Dify uploadFileId"},
        400: {"description": "Content-Type 缺失 / 类型不在白名单 / 显式禁用类型"},
        401: {"description": "未登录 / token 无效"},
        413: {"description": "文件 > 20MB"},
        422: {"description": "Pydantic 校验失败"},
        500: {"description": "Dify 透传失败"},
    },
)
async def upload_file(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(resolve_user),
    service: ChatShareService = Depends(_get_service),
) -> UploadFileResponse:
    _validate_upload(file)
    result = await service.upload_to_dify(file)
    return UploadFileResponse(**result)


# ---- B 集成 (2026-06-16): presign + finalize 端点 ----


@router.post(
    "/files/presign",
    response_model=PresignChatFileResponse,
    summary="签 PUT URL 直传",
    description=(
        "## 用途\n\n"
        "签发对象存储的预签名 PUT URL, 浏览器拿 URL 直传大文件 (绕过 20MB 同步上传). "
        "上传完成后调 `/files/finalize` 通知后端转发到 Dify.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫: 必须登录, `current.id` 拼到 URI 路径里 (`chat/{user_id}/{name}`) "
        "作为天然隔离.\n\n"
        "## 行为\n\n"
        "**URI 模式**: minio 后端 → `s3://{bucket}/chat/{user_id}/{name}`; local 后端 → "
        "`local://chat/{user_id}/{name}`. "
        "**双重校验**: Pydantic 边界 (mime 长度 / size 范围) + handler `_validate_mime_and_size` "
        "(白名单 + 20MB 上限). "
        "返 `{uri, put_url, mime}`, `put_url` 可直接 PUT 二进制."
    ),
    responses={
        200: {"description": "签名成功, 返 uri + put_url + mime"},
        400: {"description": "mime 缺失 / 不在白名单 / 显式禁用类型"},
        401: {"description": "未登录 / token 无效"},
        413: {"description": "size > 20MB"},
        422: {"description": "Pydantic 校验失败 (mime / size / name 格式)"},
        500: {"description": "对象存储签 URL 失败"},
    },
)
async def presign_chat_file(
    req: PresignChatFileRequest,
    current: CurrentUser = Depends(resolve_user),
) -> PresignChatFileResponse:
    _validate_mime_and_size(req.mime, req.size)

    # 兜底防 schema 漏 (SEC-002): 即便 schema pattern 被绕过, 这里再 sanitize 一次,
    # 用 Path.name 截掉所有路径分隔符, 防 ../ / / 越权写其他用户目录.
    safe_name = Path(req.name).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=422, detail="invalid filename")

    store = get_object_store()
    backend = store.backend_name()
    if backend == "minio":
        bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
        uri = f"s3://{bucket}/chat/{current.id}/{safe_name}"
    else:
        # local backend: 走 local://chat/{user_id}/{name}
        uri = f"local://chat/{current.id}/{safe_name}"
    put_url = store.presign_put(uri) or ""
    return PresignChatFileResponse(uri=uri, put_url=put_url, mime=req.mime)


@router.post(
    "/files/finalize",
    response_model=FinalizeChatFileResponse,
    summary="通知后端拉 bytes 转发 Dify",
    description=(
        "## 用途\n\n"
        "浏览器 PUT 完大文件到对象存储后, 通知后端: '从 store 拉 bytes, 转发到 Dify `/files/upload`'. "
        "拿到 Dify `uploadFileId` 供 chat 消息引用. presign + finalize 配对使用.\n\n"
        "## 鉴权\n\n"
        "`resolve_user` 守卫: 必须登录, `current.id` 用于 URI 路径归属校验.\n\n"
        "## 行为\n\n"
        "**URI 必须在 store 存在**: handler 调 `store.exists(uri)` 验, 不存在 → 404. "
        "**Dify 失败 → URI 保留**: 转发异常时返 500, 但 URI 不删, 允许前端重试. "
        "**对象存储异常 → 503**: `ObjectStoreError` 翻译."
    ),
    responses={
        200: {"description": "转发成功, 返 Dify uploadFileId"},
        401: {"description": "未登录 / token 无效"},
        404: {"description": "URI 在 store 中不存在 (前端没真传)"},
        422: {"description": "Pydantic 校验失败 (uri / mime / name 格式)"},
        500: {"description": "Dify 转发失败 (URI 保留, 可重试)"},
        503: {"description": "对象存储不可用"},
    },
)
async def finalize_chat_file(
    req: FinalizeChatFileRequest,
    current: CurrentUser = Depends(resolve_user),
    service: ChatShareService = Depends(_get_service),
) -> FinalizeChatFileResponse:
    store = get_object_store()
    # 验 URI 存在
    try:
        if not store.exists(req.uri):
            raise HTTPException(status_code=404, detail=f"文件不存在: {req.uri}")
    except ObjectStoreError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    # 转发 Dify (用 service 走 httpx)
    try:
        # mock UploadFile 对象 (service 调 filename/content_type)
        fake_file = MagicMock()
        fake_file.filename = req.name
        fake_file.content_type = req.mime
        result = await service.upload_to_dify(fake_file, uri=req.uri)
        return FinalizeChatFileResponse(**result)
    except Exception as e:
        # Dify 失败: URI 保留, 让前端重试
        raise HTTPException(status_code=500, detail=f"Dify 转发失败: {e}") from e
