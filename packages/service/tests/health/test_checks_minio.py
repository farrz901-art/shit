"""check_minio 单元测试 (2026-06-16 RAG MinIO 集成, 2026-07-07 重写 probe 模式)

4 模式 1 mock 测试, 覆盖:
- local backend: status=ok + extra.skipped=True
- minio backend success (probe exists): status=ok + extra.backend/bucket/endpoint
- minio backend success (probe missing → auto-create): status=ok
- minio backend failure (exists 抛): status=error
- minio backend failure (auto-create 抛): status=error
- minio backend latency > 0

(2026-07-07) 改 probe 模式原因: 旧实现走 `list_prefix(f"s3://{bucket}/")` 列根目录,
触发 `parse_uri("s3://rag-ingest/")` 空 key → ValueError("URI 缺 key"),
health check 永远返 error 即使 MinIO 正常. 改为 `exists(probe_uri)` 探测,
首次缺失自动 `put_bytes` 创建 probe 文件, 不依赖 list 根目录.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.health.checks import check_minio


@pytest.fixture
def mock_local_store():
    s = MagicMock()
    s.backend_name.return_value = "local"
    return s


@pytest.fixture
def mock_minio_store_probe_exists():
    """probe 文件已存在 → exists 返 True, 不调 put_bytes"""
    s = MagicMock()
    s.backend_name.return_value = "minio"
    # (2026-06-17) 注: MinioObjectStore 实际用 _bucket / _endpoint 属性
    # (不是 _cfg), mock 也跟真实字段对齐, 避免 check_minio 跟真实实现脱节
    s._bucket = "rag-ingest"
    s._endpoint = "http://localhost:9000"
    s.exists.return_value = True
    return s


@pytest.fixture
def mock_minio_store_probe_missing():
    """probe 文件缺失 → exists 返 False, 自动调 put_bytes 创建"""
    s = MagicMock()
    s.backend_name.return_value = "minio"
    s._bucket = "rag-ingest"
    s._endpoint = "http://localhost:9000"
    s.exists.return_value = False
    s.put_bytes.return_value = None
    return s


def test_check_minio_local_backend_skipped(mock_local_store):
    """OBJECT_STORE_BACKEND=local → status=ok + extra.skipped=True"""
    with patch("src.health.checks._get_object_store", return_value=mock_local_store):
        result = asyncio.run(check_minio())
    assert result.status == "ok"
    assert result.extra["backend"] == "local"
    assert result.extra["skipped"] is True


def test_check_minio_minio_backend_probe_exists(mock_minio_store_probe_exists):
    """minio backend, probe 文件已存在 → exists 返 True, status=ok, 不调 put_bytes"""
    with patch("src.health.checks._get_object_store", return_value=mock_minio_store_probe_exists):
        result = asyncio.run(check_minio())
    assert result.status == "ok"
    assert result.extra["backend"] == "minio"
    assert result.extra["bucket"] == "rag-ingest"
    assert result.extra["endpoint"] == "http://localhost:9000"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
    # probe 命中: put_bytes 不应被调用
    mock_minio_store_probe_exists.put_bytes.assert_not_called()


def test_check_minio_minio_backend_probe_auto_create(mock_minio_store_probe_missing):
    """minio backend, probe 文件缺失 → exists 返 False 后自动 put_bytes 创建"""
    with patch("src.health.checks._get_object_store", return_value=mock_minio_store_probe_missing):
        result = asyncio.run(check_minio())
    assert result.status == "ok"
    # put_bytes 必须被调用 1 次, uri 以 .health-probe/ready 结尾
    mock_minio_store_probe_missing.put_bytes.assert_called_once()
    call_args = mock_minio_store_probe_missing.put_bytes.call_args
    probe_uri = call_args[0][0]
    assert probe_uri.endswith(".health-probe/ready")
    assert call_args[0][1] == b"ok"


def test_check_minio_minio_backend_failure_exists():
    """minio backend, exists 抛 ConnectionError → status=error"""
    s = MagicMock()
    s.backend_name.return_value = "minio"
    s._bucket = "rag-ingest"
    s._endpoint = "http://localhost:9000"
    s.exists.side_effect = ConnectionError("MinIO 不可达")
    with patch("src.health.checks._get_object_store", return_value=s):
        result = asyncio.run(check_minio())
    assert result.status == "error"
    assert result.error is not None
    assert "ConnectionError" in result.error or "MinIO" in result.error


def test_check_minio_minio_backend_failure_put():
    """minio backend, probe 缺失 + put_bytes 抛错 → status=error (auto-create 路径失败)"""
    s = MagicMock()
    s.backend_name.return_value = "minio"
    s._bucket = "rag-ingest"
    s._endpoint = "http://localhost:9000"
    s.exists.return_value = False
    s.put_bytes.side_effect = ConnectionError("MinIO 写入失败")
    with patch("src.health.checks._get_object_store", return_value=s):
        result = asyncio.run(check_minio())
    assert result.status == "error"
    assert result.error is not None


def test_check_minio_records_latency(mock_minio_store_probe_exists):
    """minio 测时 latency_ms >= 0"""
    with patch("src.health.checks._get_object_store", return_value=mock_minio_store_probe_exists):
        result = asyncio.run(check_minio())
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
