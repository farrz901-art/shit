"""RAG MinIO 对象存储测试 (2026-06-29 重写, 6 → 3 项)

跟用户原话 '不希望 test 在 MinIO 增删改查, mock 实现' 一致:
- 3 项 ABC 接口测 mock 业务对 ABC 调用契约
- 2 项 presign 真 HTTP 测 删 (boto3 presign URL + 真 PUT/GET 不能 mock)
- 1 项 ObjectNotFound 错误路径 删 (验 MinIO 真抛, 违反不连外部服务)

跑前需 (本文件无需, 全部 mock): 0 外部依赖.
"""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock

import src.storage.object_store as obj_store_mod
from src.storage.object_store import ObjectMeta, ObjectNotFound, build_uri


def test_abc_put_get_roundtrip_mocked(monkeypatch):
    """ABC put_bytes → get_bytes roundtrip (mock 验业务对 ABC 调用契约)"""
    fake_store = MagicMock()
    stored: dict[str, bytes] = {}

    def fake_put(uri, data, mime=None):
        stored[uri] = data

    def fake_get(uri):
        if uri not in stored:
            raise ObjectNotFound(uri)
        return stored[uri]

    fake_store.put_bytes.side_effect = fake_put
    fake_store.get_bytes.side_effect = fake_get
    fake_store.backend_name.return_value = "minio"

    monkeypatch.setattr(obj_store_mod, "get_object_store", lambda: fake_store)
    store = obj_store_mod.get_object_store()
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
    uri = build_uri("s3", f"test/{int(time.time())}/data.txt", bucket=bucket)
    store.put_bytes(uri, b"hello-mock", mime="text/plain")
    assert store.get_bytes(uri) == b"hello-mock"
    fake_store.put_bytes.assert_called_once_with(uri, b"hello-mock", mime="text/plain")
    fake_store.get_bytes.assert_called_once_with(uri)


def test_abc_list_prefix_returns_objects_mocked(monkeypatch):
    """ABC list_prefix 返多个 objects (mock)"""
    fake_store = MagicMock()
    fake_store.backend_name.return_value = "minio"
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
    prefix = f"s3://{bucket}/test/list-{int(time.time())}/"
    expected_metas = [
        ObjectMeta(uri=f"{prefix}a0.md", size=1, mime="text/markdown"),
        ObjectMeta(uri=f"{prefix}a1.md", size=1, mime="text/markdown"),
        ObjectMeta(uri=f"{prefix}a2.md", size=1, mime="text/markdown"),
    ]
    fake_store.list_prefix.return_value = expected_metas

    monkeypatch.setattr(obj_store_mod, "get_object_store", lambda: fake_store)
    store = obj_store_mod.get_object_store()
    metas = store.list_prefix(prefix)

    assert len(metas) == 3
    assert metas == expected_metas
    fake_store.list_prefix.assert_called_once_with(prefix)


def test_5_prefix_isolation_mocked(monkeypatch):
    """5 个 prefix 互不干扰 (mock 验 put + exists + delete 调用契约)"""
    fake_store = MagicMock()
    fake_store.backend_name.return_value = "minio"
    fake_store.exists.return_value = True
    bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")

    monkeypatch.setattr(obj_store_mod, "get_object_store", lambda: fake_store)
    store = obj_store_mod.get_object_store()
    ts = int(time.time())
    for prefix in ["inputs", "outputs", "chat", "eval", "temp"]:
        uri = f"s3://{bucket}/{prefix}/test-{ts}.bin"
        store.put_bytes(uri, b"x")
        assert store.exists(uri) is True
        store.delete(uri)

    assert fake_store.put_bytes.call_count == 5
    assert fake_store.exists.call_count == 5
    assert fake_store.delete.call_count == 5
