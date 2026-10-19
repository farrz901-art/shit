"""extract_runner 测试 (v3, 含 dataset 透传)"""

from contextlib import contextmanager
from unittest.mock import MagicMock

from src.ingest.chunkers import TextChunk
from src.kg import datasets
from src.kg.extract_runner import run_extraction
from src.kg.extractors.base import ExtractedEntity, ExtractedRelation, ExtractionResult
from src.kg.tasks import TaskStore


def _seed_datasets(monkeypatch):
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc"])


def _make_fake_session_scope(captured_sql, captured_params):
    """返一个 contextmanager: 收集 SQL + params, 跳过真 commit

    注: extract_runner.py 用 'from src.storage import session_scope' 局部绑定,
    所以 monkeypatch 必须打 src.kg.extract_runner.session_scope 而不是 src.storage.session_scope
    """

    @contextmanager
    def fake_session_scope():
        class FakeSession:
            def execute(self, stmt, params=None):
                captured_sql.append(str(stmt.compile()))
                captured_params.append(params or {})

            def commit(self):
                pass

        yield FakeSession()

    return fake_session_scope


def test_run_extraction_full_pipeline(monkeypatch):
    """[M6] 全路径: ObjectStore → splitter → extractor → 2 条 INSERT"""
    _seed_datasets(monkeypatch)
    captured_sql: list[str] = []
    captured_params: list[dict] = []
    monkeypatch.setattr(
        "src.kg.extract_runner.session_scope",
        _make_fake_session_scope(captured_sql, captured_params),
    )

    mock_store = MagicMock()
    mock_store.get_bytes.return_value = b"# Title\n\n1LE0001 supports 230V"

    mock_extractor = MagicMock()
    mock_extractor.extractor_id = "spacy_rule"
    mock_extractor.extract.return_value = ExtractionResult(
        entities=[ExtractedEntity(text="1LE0001", label="Product", chunk_id="abc12345ab", char_span=(0, 7))],
        relations=[ExtractedRelation(head="1LE0001", rel_type="HAS_SPEC", tail="230V", chunk_id="abc12345ab")],
    )

    mock_splitter = MagicMock()
    mock_splitter.split.return_value = [TextChunk(chunk_id="abc12345ab", text="content", meta={})]

    task_store = TaskStore()
    task_id = task_store.submit("kg_extract", {"dataset": "motor"})

    run_extraction(
        task_id=task_id,
        dataset="motor",
        source_uri="local://inputs/test.md",
        extractor=mock_extractor,
        splitter=mock_splitter,
        extractor_id="spacy_rule",
        splitter_id="heading",
        object_store=mock_store,
        task_store=task_store,
    )

    mock_store.get_bytes.assert_called_once_with("local://inputs/test.md")
    mock_splitter.split.assert_called_once()
    mock_extractor.extract.assert_called_once()
    assert len(captured_sql) == 2
    assert any("'entity'" in s for s in captured_sql)
    assert any("'relation'" in s for s in captured_sql)


def test_run_extraction_extractor_error_marks_failed(monkeypatch):
    """[M6] extractor.error 非 None → TaskStore.mark_failed, 不 INSERT"""
    _seed_datasets(monkeypatch)
    captured_sql: list[str] = []
    captured_params: list[dict] = []
    monkeypatch.setattr(
        "src.kg.extract_runner.session_scope",
        _make_fake_session_scope(captured_sql, captured_params),
    )

    mock_store = MagicMock()
    mock_store.get_bytes.return_value = b"content"

    mock_extractor = MagicMock()
    mock_extractor.extractor_id = "spacy_rule"
    mock_extractor.extract.return_value = ExtractionResult(
        error="模型加载失败",
        extractor_id="spacy_rule",
    )

    mock_splitter = MagicMock()
    mock_splitter.split.return_value = [TextChunk(chunk_id="c", text="t", meta={})]

    task_store = TaskStore()
    task_id = task_store.submit("kg_extract", {"dataset": "motor"})
    run_extraction(
        task_id=task_id,
        dataset="motor",
        source_uri="local://x.md",
        extractor=mock_extractor,
        splitter=mock_splitter,
        object_store=mock_store,
        task_store=task_store,
    )

    assert captured_sql == []
    t = task_store.get(task_id)
    assert t.state == "failed"
    assert "模型加载失败" in t.errors


def test_run_extraction_exception_marks_failed(monkeypatch):
    """[M6] ObjectStore.get_bytes 抛异常 → TaskStore.mark_failed"""
    _seed_datasets(monkeypatch)
    captured_sql: list[str] = []
    captured_params: list[dict] = []
    monkeypatch.setattr(
        "src.kg.extract_runner.session_scope",
        _make_fake_session_scope(captured_sql, captured_params),
    )

    mock_store = MagicMock()
    mock_store.get_bytes.side_effect = RuntimeError("object store down")

    mock_extractor = MagicMock()
    mock_splitter = MagicMock()

    task_store = TaskStore()
    task_id = task_store.submit("kg_extract", {"dataset": "motor"})
    run_extraction(
        task_id=task_id,
        dataset="motor",
        source_uri="local://x.md",
        extractor=mock_extractor,
        splitter=mock_splitter,
        object_store=mock_store,
        task_store=task_store,
    )
    assert task_store.get(task_id).state == "failed"


def test_run_extraction_validates_dataset():
    """[M6] dataset 不在白名单 → 业务一进来就拒绝"""
    import pytest as _pytest

    datasets.ALLOWED_DATASETS = ["motor"]
    mock_store = MagicMock()
    mock_extractor = MagicMock()
    mock_splitter = MagicMock()
    task_store = TaskStore()

    with _pytest.raises(ValueError, match="白名单"):
        run_extraction(
            task_id="t3",
            dataset="hack",
            source_uri="local://x.md",
            extractor=mock_extractor,
            splitter=mock_splitter,
            object_store=mock_store,
            task_store=task_store,
        )


def test_run_extraction_writes_dataset_to_sql(monkeypatch):
    """[M6] v3: SQL 必含 :ds (dataset) 参数"""
    _seed_datasets(monkeypatch)
    captured_sql: list[str] = []
    captured_params: list[dict] = []
    monkeypatch.setattr(
        "src.kg.extract_runner.session_scope",
        _make_fake_session_scope(captured_sql, captured_params),
    )

    mock_store = MagicMock()
    mock_store.get_bytes.return_value = b"content"

    mock_extractor = MagicMock()
    mock_extractor.extractor_id = "spacy_rule"
    mock_extractor.extract.return_value = ExtractionResult(
        entities=[ExtractedEntity(text="X", label="Product", chunk_id="c", char_span=(0, 1))],
    )

    mock_splitter = MagicMock()
    mock_splitter.split.return_value = [TextChunk(chunk_id="c", text="x", meta={})]

    task_store = TaskStore()
    task_id = task_store.submit("kg_extract", {"dataset": "plc"})
    run_extraction(
        task_id=task_id,
        dataset="plc",
        source_uri="local://x.md",
        extractor=mock_extractor,
        splitter=mock_splitter,
        extractor_id="spacy_rule",
        splitter_id="heading",
        object_store=mock_store,
        task_store=task_store,
    )

    assert len(captured_params) == 1
    assert captured_params[0]["ds"] == "plc"
    assert captured_params[0]["tid"] == task_id
    assert captured_params[0]["ext"] == "spacy_rule"
    assert captured_params[0]["spl"] == "heading"
