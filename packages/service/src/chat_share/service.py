"""ChatShareService 业务核心 (2026-06-16)

5 个方法:
- create_share(conv_id, user_id, title, messages, model) → dict
- get_share(share_id) → dict (raises ShareNotFound)
- revoke_share(share_id, current_user_id) → None (raises ShareNotFound)
- list_shares(conv_id, user_id, limit) → list[dict] (登录, 按 conv + user)
- upload_to_dify(file) → dict (Task 2 透传, 当前占位)

设计要点:
- repo 注入 (测试用 MagicMock, 运行时走 SqlAlchemyChatShareRepo)
- 短 ID 用 secrets.token_urlsafe(9)[:12] (9 字节 base64 = 12 字符, 熵 ~71 bits)
- URL 拼接: WEB_BASE_URL + /{locale}/chat/s/{share_id}
- 异常语义: ShareNotFound 统一处理 "不存在" + "非所有者" (防 ID 探测)
- get_share 响应**不含** user_id 等敏感字段 (公开端点)
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..common import defaults
from ..storage import get_object_store
from .repo import ChatShareRepo


def _is_retryable_dify_error(exc: BaseException) -> bool:
    """仅重试网络超时/断连 以及 Dify 5xx 服务端错误, 4xx 直接透传."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable_dify_error),
    before_sleep=lambda retry_state: logger.warning("重试 upload_to_dify attempt={}", retry_state.attempt_number),
)
async def _upload_file_to_dify(url: str, api_key: str, filename: str, content: bytes, content_type: str) -> dict:
    """带 tenacity 重试的 Dify Files API 上传 (最多 3 次指数退避)."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        files = {"file": (filename, content, content_type)}
        resp = await client.post(
            url,
            files=files,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        return resp.json()


class ShareNotFound(Exception):
    """share 不存在 OR 当前用户非所有者 — 统一异常, 防 ID 探测.

    router 翻译为 HTTP 404.
    """


class ChatShareService:
    """chat 对话分享业务核心.

    Args:
        repo: ChatShareRepo 实现 (测试用 MagicMock, 运行时用 SqlAlchemyChatShareRepo).
        locale: URL 前缀 locale 段 (默认 'zh', 走 env / defaults 兜底).
    """

    def __init__(self, repo: ChatShareRepo, locale: str | None = None):
        self._repo = repo
        self._locale = locale or defaults.DEFAULT_CHAT_SHARE_LOCALE

    # ---- create_share ----

    def create_share(
        self,
        conv_id: str,
        user_id: int,
        title: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """创建 share: 短 ID + URL + TTL + 存消息快照.

        Returns:
            {share_id, url, title, expires_at, created_at}
        """
        share_id = self._gen_share_id()
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=defaults.DEFAULT_CHAT_SHARE_TTL_DAYS)
        messages_json = json.dumps(messages or [], ensure_ascii=False)

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

    # ---- get_share (公开, anon) ----

    def get_share(self, share_id: str) -> dict[str, Any]:
        """读 share 快照, 不含 user_id / 任何 PII. 不存在 → ShareNotFound."""
        share = self._repo.get_by_id(share_id)
        if share is None:
            raise ShareNotFound(f"share {share_id} 不存在")

        return {
            "share_id": share.share_id,
            "title": share.title,
            "messages": json.loads(share.messages_json or "[]"),
            "model": share.model,
            "created_at": share.created_at,
        }

    # ---- revoke_share ----

    def revoke_share(self, share_id: str, current_user_id: int) -> None:
        """撤销 share. 仅所有者可删, 否则 ShareNotFound (跟不存在同异常, 防 ID 探测)."""
        share = self._repo.get_by_id(share_id)
        if share is None or share.user_id != current_user_id:
            raise ShareNotFound(f"share {share_id} 不存在或无权访问")
        self._repo.delete(share_id)

    # ---- list_shares (登录, 按 conv + user) ----

    def list_shares(
        self,
        conv_id: str,
        user_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """按 (conv_id, user_id) 列 share 元数据 (不含 messages 快照).

        用于 ShareDialog "我的分享" 列表. 跨用户永不返 (user_id 强过滤).

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

    # ---- upload_to_dify (B 集成, 2026-06-16 真接 Dify Files API) ----

    async def upload_to_dify(self, file, uri: str = "") -> dict[str, Any]:
        """真接 Dify Files API: 从 URI 下载, 转发到 Dify /files/upload.

        Args:
            file: FastAPI UploadFile (仅 filename/content_type 用作 metadata)
                - finalize 路由里可传 mock 对象 (只读 filename/content_type)
            uri: (2026-06-16) 对象存储 URI (e.g. s3://rag-ingest/chat/1/abc.png).
                - 空字符串: 走旧 multipart 路径, file.file.read() 取 bytes
                - 非空: 走 presign 路径, store.get_bytes(uri) 下载

        Returns:
            {uploadFileId, uri}

        Raises:
            DifyAPIError: Dify 返 4xx/5xx
            ObjectStoreError: store 下载失败
        """
        filename = getattr(file, "filename", "upload.bin") or "upload.bin"
        content_type = getattr(file, "content_type", "application/octet-stream") or "application/octet-stream"

        if uri:
            # (2026-06-16) presign 路径: 从 store 拿 bytes
            store = get_object_store()
            content = store.get_bytes(uri)
        else:
            # 旧 multipart 路径: 从 UploadFile 读
            content = await file.read()

        api_key = os.getenv("DIFY_DATASET_API_KEY", "")
        dify_url = f"{os.getenv('DIFY_BASE_URL', '').rstrip('/')}/files/upload"
        try:
            data = await _upload_file_to_dify(dify_url, api_key, filename, content, content_type)
        except httpx.HTTPStatusError as e:
            # 防循环: dify_client 在异常分支才需要, 模块装载期不引入
            from ..integrations.dify_client import DifyAPIError  # noqa: E402

            raise DifyAPIError(f"Dify upload HTTP {e.response.status_code}: {e.response.text[:500]}") from e
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            # 防循环: 同上, dify_client 异常分支才需要
            from ..integrations.dify_client import DifyAPIError  # noqa: E402

            raise DifyAPIError(f"Dify upload 请求失败 (重试后): {e}") from e
        logger.info("[chat_share] 上传 Dify 成功 uri={} dify_id={}", uri, data.get("id"))
        return {"uploadFileId": data["id"], "uri": uri}

    # ---- helpers ----

    @staticmethod
    def _gen_share_id() -> str:
        """生成 12 字符短 ID (nanoid 等价: 9 字节 base64 = 12 字符, 熵 ~71 bits)."""
        return secrets.token_urlsafe(9)[: defaults.DEFAULT_CHAT_SHARE_ID_LENGTH]

    def _build_url(self, share_id: str) -> str:
        """拼接完整 share URL: {WEB_BASE_URL}/{locale}/chat/s/{share_id}.

        WEB_BASE_URL 来自 env (env 没配时用 defaults 默认值).
        """
        base = os.getenv("WEB_BASE_URL", defaults.DEFAULT_WEB_BASE_URL).rstrip("/")
        return f"{base}/{self._locale}/chat/s/{share_id}"
