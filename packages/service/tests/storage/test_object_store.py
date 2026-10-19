"""ObjectStorage ABC + URI 解析测试 (2026-06-16 RAG MinIO 集成)

12-15 模式 1 mock 测试, 覆盖:
- URI parse / build round-trip
- 错误 URI 抛 ValueError
- 未知 scheme 抛 ValueError
- ABC 子类必须实现所有 abstractmethod
- LocalFS impl 14 方法基础行为 (临时目录隔离)
- Minio impl constructor + 错误模型

无 MinIO server 依赖, 无 PG 依赖. 纯单测.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.storage.object_store import (
    LocalFSObjectStore,
    MinioObjectStore,
    ObjectNotFound,
    ObjectStore,
    ObjectStoreError,
    build_uri,
    parse_uri,
)

# ---------------- URI parse / build ----------------


def test_parse_uri_s3():
    """s3://bucket/key/path → ('s3', 'key/path')"""
    assert parse_uri("s3://rag-ingest/inputs/2026/file.pdf") == ("s3", "inputs/2026/file.pdf")


def test_parse_uri_local():
    """local://key → ('local', 'key')"""
    assert parse_uri("local://inputs/2026/file.pdf") == ("local", "inputs/2026/file.pdf")


def test_parse_uri_s3_no_bucket_raises():
    """s3:// 没 bucket → ValueError"""
    with pytest.raises(ValueError, match="s3 URI 缺 bucket"):
        parse_uri("s3:///key/file.pdf")


def test_parse_uri_unknown_scheme_raises():
    """ftp:// 不支持 → ValueError"""
    with pytest.raises(ValueError, match="未知 URI scheme"):
        parse_uri("ftp://bucket/key")


def test_build_uri_s3():
    """build_uri('s3', 'key', 'bucket') → 's3://bucket/key'"""
    assert build_uri("s3", "inputs/2026/file.pdf", bucket="rag-ingest") == "s3://rag-ingest/inputs/2026/file.pdf"


def test_build_uri_local():
    """build_uri('local', 'key') → 'local://key' (无 bucket)"""
    assert build_uri("local", "inputs/2026/file.pdf") == "local://inputs/2026/file.pdf"


def test_build_uri_s3_no_bucket_raises():
    """s3 backend 必传 bucket"""
    with pytest.raises(ValueError, match="s3 backend 必传 bucket"):
        build_uri("s3", "key/file.pdf")


def test_uri_roundtrip():
    """build → parse 1:1"""
    original = "s3://rag-ingest/inputs/2026/file.pdf"
    backend, key = parse_uri(original)
    assert build_uri(backend, key, bucket="rag-ingest") == original


# ---------------- ABC 完整性 ----------------


def test_abc_has_14_abstract_methods():
    """ABC 必须有 14 抽象方法 (跟 spec 6.3 一致)"""
    abstract_methods = {
        name
        for name, method in inspect.getmembers(ObjectStore, predicate=inspect.isfunction)
        if getattr(method, "__isabstractmethod__", False)
    }
    expected = {
        "backend_name",
        "put_bytes",
        "put_stream",
        "put_file",
        "get_bytes",
        "get_stream",
        "open_local",
        "release_local",
        "list_prefix",
        "exists",
        "delete",
        "delete_prefix",
        "presign_put",
        "presign_get",
    }
    assert abstract_methods == expected, f"missing: {expected - abstract_methods}, extra: {abstract_methods - expected}"


def test_abc_cannot_instantiate():
    """ObjectStore 是 ABC, 不能直接实例化"""
    with pytest.raises(TypeError, match="abstract"):
        ObjectStore()  # type: ignore[abstract]


# ---------------- LocalFS impl ----------------


def test_localfs_put_and_get_bytes(tmp_path: Path):
    """put_bytes + get_bytes round-trip"""
    store = LocalFSObjectStore(local_root=tmp_path)
    store.put_bytes("local://inputs/foo.pdf", b"hello", mime="application/pdf")
    assert store.get_bytes("local://inputs/foo.pdf") == b"hello"


def test_localfs_exists_true_and_false(tmp_path: Path):
    store = LocalFSObjectStore(local_root=tmp_path)
    assert store.exists("local://inputs/foo.pdf") is False
    store.put_bytes("local://inputs/foo.pdf", b"x")
    assert store.exists("local://inputs/foo.pdf") is True


def test_localfs_list_prefix(tmp_path: Path):
    """list_prefix 返 prefix 下所有 object, 含元数据"""
    store = LocalFSObjectStore(local_root=tmp_path)
    store.put_bytes("local://inputs/a.pdf", b"x", mime="application/pdf")
    store.put_bytes("local://inputs/b.pdf", b"y" * 100, mime="application/pdf")
    metas = store.list_prefix("local://inputs/")
    assert len(metas) == 2
    names = {m.uri.rsplit("/", 1)[-1] for m in metas}
    assert names == {"a.pdf", "b.pdf"}
    assert all(m.size > 0 for m in metas)


def test_localfs_presign_returns_none(tmp_path: Path):
    """LocalFS impl presign 返 None (不签 URL)"""
    store = LocalFSObjectStore(local_root=tmp_path)
    assert store.presign_put("local://foo") is None
    assert store.presign_get("local://foo") is None


def test_localfs_open_local_no_copy(tmp_path: Path):
    """open_local 不复制, 返 LOCAL_ROOT 下的绝对路径"""
    store = LocalFSObjectStore(local_root=tmp_path)
    store.put_bytes("local://inputs/foo.pdf", b"x")
    p = store.open_local("local://inputs/foo.pdf")
    assert Path(p).is_absolute()
    assert Path(p).read_bytes() == b"x"


def test_localfs_delete_idempotent(tmp_path: Path):
    """delete 不存在不抛 (idempotent)"""
    store = LocalFSObjectStore(local_root=tmp_path)
    store.delete("local://nonexistent")  # 不应抛


def test_localfs_get_bytes_not_found_raises(tmp_path: Path):
    """get_bytes 不存在 → ObjectNotFound"""
    store = LocalFSObjectStore(local_root=tmp_path)
    with pytest.raises(ObjectNotFound):
        store.get_bytes("local://nonexistent")


# ---------------- 错误模型 ----------------


def test_error_classes_inherit_runtime_error():
    """ObjectStoreError 继承 RuntimeError, ObjectNotFound 继承它. PresignNotSupported 已删 (LocalFS 返 None, 不抛)."""
    assert issubclass(ObjectStoreError, RuntimeError)
    assert issubclass(ObjectNotFound, ObjectStoreError)


# ---------------- Minio impl (mock boto3) ----------------


@pytest.fixture
def mock_s3_client():
    """mock boto3.client('s3'). 不真连 MinIO."""
    return MagicMock()


@pytest.fixture
def minio_store(mock_s3_client, monkeypatch, tmp_path):
    """MinioObjectStore 实例, _client 返 mock. stage_root 用 tmp_path 隔离."""
    import boto3

    monkeypatch.setattr(boto3, "client", lambda *a, **k: mock_s3_client)
    store = MinioObjectStore(
        endpoint="http://localhost:9000",
        access_key="x",
        secret_key="y",
        bucket="rag-ingest",
        stage_root=str(tmp_path / "minio_stage"),
    )
    return store


def test_minio_backend_name(minio_store):
    assert minio_store.backend_name() == "minio"


def test_minio_put_bytes_calls_put_object(minio_store, mock_s3_client):
    minio_store.put_bytes("s3://rag-ingest/inputs/foo.pdf", b"hello", mime="application/pdf")
    mock_s3_client.put_object.assert_called_once()
    kwargs = mock_s3_client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "rag-ingest"
    assert kwargs["Key"] == "inputs/foo.pdf"
    assert kwargs["Body"] == b"hello"
    assert kwargs["ContentType"] == "application/pdf"


def test_minio_get_bytes_returns_body(minio_store, mock_s3_client):
    mock_s3_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"hi")}
    assert minio_store.get_bytes("s3://rag-ingest/inputs/foo.pdf") == b"hi"


def test_minio_get_bytes_not_found_raises_objectnotfound(minio_store, mock_s3_client):
    mock_s3_client.get_object.side_effect = Exception("NoSuchKey: 404")
    with pytest.raises(ObjectNotFound):
        minio_store.get_bytes("s3://rag-ingest/inputs/nonexistent")


def test_minio_list_prefix_returns_metas(minio_store, mock_s3_client):
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "inputs/a.pdf", "Size": 100, "LastModified": datetime(2026, 1, 1, tzinfo=UTC)},
            {"Key": "inputs/b.pdf", "Size": 200, "LastModified": datetime(2026, 1, 2, tzinfo=UTC)},
        ]
    }
    metas = minio_store.list_prefix("s3://rag-ingest/inputs/")
    assert len(metas) == 2
    assert metas[0].uri == "s3://rag-ingest/inputs/a.pdf"
    assert metas[0].size == 100
    assert metas[1].uri == "s3://rag-ingest/inputs/b.pdf"


def test_minio_presign_put_returns_url(minio_store, mock_s3_client):
    mock_s3_client.generate_presigned_url.return_value = (
        "https://minio:9000/rag-ingest/inputs/foo.pdf?X-Amz-Signature=abc"
    )
    url = minio_store.presign_put("s3://rag-ingest/inputs/foo.pdf")
    assert url is not None
    assert "X-Amz-Signature" in url
    mock_s3_client.generate_presigned_url.assert_called_once()
    args = mock_s3_client.generate_presigned_url.call_args
    assert args[0][0] == "put_object"


def test_minio_presign_get_returns_url(minio_store, mock_s3_client):
    mock_s3_client.generate_presigned_url.return_value = (
        "https://minio:9000/rag-ingest/outputs/foo.md?X-Amz-Signature=xyz"
    )
    url = minio_store.presign_get("s3://rag-ingest/outputs/foo.md")
    assert url is not None
    assert "X-Amz-Signature" in url


def test_minio_delete_calls_delete_object(minio_store, mock_s3_client):
    minio_store.delete("s3://rag-ingest/inputs/foo.pdf")
    mock_s3_client.delete_object.assert_called_once_with(Bucket="rag-ingest", Key="inputs/foo.pdf")


def test_minio_delete_prefix_lists_then_deletes(minio_store, mock_s3_client):
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "inputs/a.pdf"}, {"Key": "inputs/b.pdf"}]}
    minio_store.delete_prefix("s3://rag-ingest/inputs/")
    assert mock_s3_client.delete_object.call_count == 2


def test_minio_open_local_cached_returns_path_string(minio_store, mock_s3_client):
    """open_local 第二次同 uri 返 path 字符串 (regression for C1 bug).

    C1: 之前 cached 分支返 refcount int, 改 _borrowed 结构后返 cached path str.
    """

    # mock download_file 不真下载, 写点小内容方便验证
    def fake_download(bucket, key, path):
        Path(path).write_bytes(b"cached")

    mock_s3_client.download_file.side_effect = fake_download
    p1 = minio_store.open_local("s3://rag-ingest/inputs/foo.pdf")
    p2 = minio_store.open_local("s3://rag-ingest/inputs/foo.pdf")  # 走 cached 分支
    # 必须返 str (不是 int), 二次返相同 path
    assert isinstance(p1, str)
    assert isinstance(p2, str)
    assert p1 == p2
    # download_file 只调 1 次 (第二次走 cached 不重下)
    assert mock_s3_client.download_file.call_count == 1


def test_minio_release_local_decrements_refcount(minio_store, mock_s3_client, tmp_path):
    """release_local 引用计数 -1, 归 0 删 entry + unlink file."""

    # mock download_file 写空文件, 验证 unlink 行为
    def fake_download(bucket, key, path):
        Path(path).write_bytes(b"x")

    mock_s3_client.download_file.side_effect = fake_download
    uri = "s3://rag-ingest/inputs/foo.pdf"
    p1 = minio_store.open_local(uri)
    p2 = minio_store.open_local(uri)
    # 两次 open 之后 refcount=2
    assert minio_store._borrowed[uri]["refcount"] == 2
    assert p1 == p2
    # 第一次 release: refcount=1, entry 仍存, 文件仍在
    minio_store.release_local(p1)
    assert minio_store._borrowed[uri]["refcount"] == 1
    assert Path(p1).exists()
    # 第二次 release: 归 0, entry 删, 文件 unlink
    minio_store.release_local(p2)
    assert uri not in minio_store._borrowed
    assert not Path(p1).exists()
