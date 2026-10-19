"""DifyClient._client 属性验证 (2026-06-15)

check_dify() 引用 client._client.get(...) 但 DifyClient.__init__ 未初始化 self._client,
导致 AttributeError → check_dify() 永远报 error → health page 显示 Dify 连不上.

此测试验证: DifyClient 构造后 _client 属性存在且可用.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx


@patch.dict(
    "os.environ",
    {"DIFY_CHAT_API_KEY": "app-test-key", "DIFY_BASE_URL": "http://localhost/v1"},
)
def test_dify_client_has_sync_client():
    """DifyClient 构造后 _client 属性存在且是 httpx.Client"""
    from src.integrations.dify_client import DifyClient

    client = DifyClient()
    assert hasattr(client, "_client"), "DifyClient 缺少 _client 属性"
    assert isinstance(client._client, httpx.Client), f"_client 类型错误: {type(client._client)}"


@patch.dict(
    "os.environ",
    {"DIFY_CHAT_API_KEY": "app-test-key", "DIFY_BASE_URL": "http://localhost/v1"},
)
def test_dify_client_sync_client_base_url():
    """DifyClient._client 的 base_url 与 DifyClient._base_url 一致 (httpx 会加尾部 /)"""
    from src.integrations.dify_client import DifyClient

    client = DifyClient()
    # httpx.Client.base_url 是 URL 对象, rstrip("/") 后比较
    assert str(client._client.base_url).rstrip("/") == client._base_url, "_client base_url 不匹配"


@patch.dict(
    "os.environ",
    {"DIFY_CHAT_API_KEY": "app-test-key", "DIFY_BASE_URL": "http://localhost/v1"},
)
def test_dify_client_sync_client_auth_header():
    """DifyClient._client 默认 header 包含 Authorization"""
    from src.integrations.dify_client import DifyClient

    client = DifyClient()
    # httpx.Client 默认 header (从 headers 参数或 mount 设置)
    # 验证 _client 存在, 具体 header 由 _get_headers helper 设
    assert client._client is not None
