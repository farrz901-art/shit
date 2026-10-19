"""Eval CSV 走 ABC 测试 (2026-06-16 C 集成)

3-4 模式 1 mock 测试, 覆盖:
- upload_run 调 store.put_bytes (s3://.../eval/{uuid}/dataset.csv)
- upload_run 存 dataset_uri 到 Evaluation
- runner 从 URI 读 (mock get_bytes)
- runner 旧 record (uri=None) 走本地 fallback
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from src.eval.router import upload_run
from src.eval.runner import run_evaluation


@pytest.fixture
def mock_user():
    """mock CurrentUser, 走 Depends(resolve_user) 路径"""
    u = MagicMock()
    u.id = 1
    u.is_admin = False
    return u


@pytest.fixture
def mock_store():
    """mock ObjectStore: backend_name='minio'"""
    s = MagicMock()
    s.backend_name.return_value = "minio"
    s._cfg = MagicMock(bucket="rag-ingest", endpoint="http://localhost:9000")
    return s


def _mock_uploadfile(content: bytes = b"question,ground_truth\nQ1,A1\n", name: str = "test.csv"):
    """构造 mock UploadFile"""
    f = MagicMock(spec=UploadFile)
    f.filename = name
    f.content_type = "text/csv"
    f.read = AsyncMock(return_value=content)
    f.size = len(content)
    return f


# ---------------- upload_run 写 ABC ----------------


def test_upload_run_stores_to_abc(mock_user, mock_store):
    """upload_run 调 store.put_bytes, URI 含 eval/{uuid}/"""
    f = _mock_uploadfile()
    background = MagicMock()
    request = MagicMock()  # Request mock, audit_ctx.set 走 attribute access
    with (
        patch("src.eval.router.get_object_store", return_value=mock_store),
        patch("src.eval.router.session_scope") as mock_session_scope,
    ):
        # session_scope mock: __enter__ 返 mock_session (add + flush 设 id)
        mock_session = MagicMock()

        def _fake_flush():
            if mock_session.add.called:
                added = mock_session.add.call_args[0][0]
                if hasattr(added, "id") and (added.id is None or added.id == 0):
                    added.id = 42

        mock_session.flush.side_effect = _fake_flush
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session_scope.return_value.__exit__.return_value = False

        resp = asyncio.run(upload_run(request=request, background=background, file=f, concurrency=1, current=mock_user))

    # 1. store.put_bytes 被调, URI 走 s3://rag-ingest/eval/{uuid}/dataset.csv
    mock_store.put_bytes.assert_called_once()
    args = mock_store.put_bytes.call_args
    assert args[0][0].startswith("s3://rag-ingest/eval/")
    assert args[0][0].endswith("/dataset.csv")
    assert args[0][1] == b"question,ground_truth\nQ1,A1\n"
    assert args[1]["mime"] == "text/csv"

    # 2. 响应 shape 正确
    assert resp["id"] == 42
    assert resp["status"] == "pending"

    # 3. Evaluation 行 dataset_uri 字段被设, dataset_path 不设
    added = mock_session.add.call_args[0][0]
    assert added.dataset_uri is not None
    assert added.dataset_uri.startswith("s3://rag-ingest/eval/")
    assert added.dataset_path is None  # (2026-06-16) 旧字段不再设

    # 4. BackgroundTasks.add_task 被调 (新走 BackgroundTasks, 替代 asyncio.create_task)
    background.add_task.assert_called_once()
    task_args = background.add_task.call_args
    # add_task 第一个参数是 callable, 后面的 kwargs
    assert task_args[0][0].__name__ == "_run_eval_background"
    assert task_args[1]["dataset_uri"].startswith("s3://rag-ingest/eval/")
    assert task_args[1]["dataset_name"] == "test.csv"
    assert task_args[1]["concurrency"] == 1
    assert task_args[1]["user_id"] == 1


def test_upload_run_local_backend_uses_local_scheme(mock_user, mock_store):
    """backend='local' → URI 走 local://eval/{uuid}/dataset.csv"""
    mock_store.backend_name.return_value = "local"
    f = _mock_uploadfile()
    background = MagicMock()
    request = MagicMock()  # Request mock
    with (
        patch("src.eval.router.get_object_store", return_value=mock_store),
        patch("src.eval.router.session_scope") as mock_session_scope,
    ):
        mock_session = MagicMock()
        mock_session.flush.side_effect = lambda: None
        mock_session_scope.return_value.__enter__.return_value = mock_session
        mock_session_scope.return_value.__exit__.return_value = False

        asyncio.run(upload_run(request=request, background=background, file=f, concurrency=1, current=mock_user))

    args = mock_store.put_bytes.call_args
    assert args[0][0].startswith("local://eval/")
    assert args[0][0].endswith("/dataset.csv")


# ---------------- runner 走 URI 模式 ----------------


def test_runner_reads_from_uri(mock_store):
    """run_evaluation(dataset_uri=...) 调 store.get_bytes"""
    mock_store.get_bytes.return_value = b"question,ground_truth\nQ1,A1\n"
    with (
        patch("src.eval.runner.get_object_store", return_value=mock_store),
        patch("src.eval.runner.parse_eval_csv") as mock_parse,
    ):
        mock_parse.return_value = [{"question": "Q1", "ground_truth": "A1"}]
        try:
            asyncio.run(
                run_evaluation(
                    user_id=1,
                    dataset_name="t.csv",
                    concurrency=1,
                    dify=MagicMock(),
                    evaluator=MagicMock(),
                    dataset_uri="s3://rag-ingest/eval/abc/dataset.csv",
                )
            )
        except Exception:
            # 其它 mock 缺失导致 runner 后段报错, 我们只关心 get_bytes
            pass

    mock_store.get_bytes.assert_called_once_with("s3://rag-ingest/eval/abc/dataset.csv")


def test_runner_fallback_to_local_when_uri_none(tmp_path, monkeypatch):
    """老 record (uri=None) 走本地 DATASETS_DIR fallback"""
    # 写一个真实本地 fallback CSV
    dataset_dir = tmp_path / "eval_datasets"
    dataset_dir.mkdir()
    dataset_csv = dataset_dir / "99.csv"
    dataset_csv.write_bytes(b"question,ground_truth\nQQ,AA\n")

    # monkeypatch Path("data/eval_datasets/{id}.csv") 走 tmp_path
    # runner 用 Path(f"data/eval_datasets/{evaluation_id}.csv"), 这里覆写 Path 的行为
    real_Path = Path

    def patched_Path(p: str):
        if p.startswith("data/eval_datasets/"):
            suffix = p[len("data/eval_datasets/") :]
            return tmp_path / "eval_datasets" / suffix
        return real_Path(p)

    monkeypatch.setattr("src.eval.runner.Path", patched_Path)

    with patch("src.eval.runner.parse_eval_csv") as mock_parse:
        mock_parse.return_value = [{"question": "QQ", "ground_truth": "AA"}]
        try:
            asyncio.run(
                run_evaluation(
                    user_id=1,
                    dataset_name="t.csv",
                    concurrency=1,
                    dify=MagicMock(),
                    evaluator=MagicMock(),
                    dataset_uri=None,
                    evaluation_id=99,
                )
            )
        except Exception:
            pass

    # 验证 parse_eval_csv 被调 (意味着本地 fallback 路径生效)
    assert mock_parse.called


def test_runner_raises_when_no_dataset_source():
    """无 dataset 也无 URI 也无本地 fallback → FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        asyncio.run(
            run_evaluation(
                user_id=1,
                dataset_name="t.csv",
                concurrency=1,
                dify=MagicMock(),
                evaluator=MagicMock(),
                dataset_uri=None,
                evaluation_id=None,
            )
        )
