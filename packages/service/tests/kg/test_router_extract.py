"""5 个 extract API 端点测试 (PR3 Task 15)

直接调函数, 避免 TestClient 启动 app_factory 慢的问题
"""

from unittest.mock import MagicMock

import pytest

from src.kg import datasets


@pytest.fixture(autouse=True)
def _seed_datasets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc"])


def test_list_extractors_returns_two_whitelist():
    """[M7] list_extractors → 2 个 (spacy_rule / llm_pydantic)"""
    from src.kg.router import list_extractors

    result = list_extractors()
    ids = {e["id"] for e in result}
    assert ids == {"spacy_rule", "llm_pydantic"}


def test_list_splitters_returns_three():
    """[M7] list_splitters → 3 个 (heading / token / semantic)"""
    from src.kg.router import list_splitters

    result = list_splitters()
    ids = {s["id"] for s in result}
    assert ids == {"heading", "token", "semantic"}


def test_build_extractor_spacy_returns_spacy_rule(monkeypatch: pytest.MonkeyPatch):
    """[2026-07-03] _build_extractor('spacy_rule') → SpacyRuleExtractor (nlp=<mock>)"""
    from unittest.mock import MagicMock

    from src.kg.extractors.spacy_rule.extractor import SpacyRuleExtractor
    from src.kg.router import _build_extractor

    # mock get_spacy_model 而非 spacy.load (2026-07-09 走 core manager 统一入口)
    mock_nlp = MagicMock()
    monkeypatch.setattr("src.core.spacy_manager.get_spacy_model", lambda model_name: mock_nlp)

    ext = _build_extractor("spacy_rule")
    assert isinstance(ext, SpacyRuleExtractor)
    assert ext.extractor_id == "spacy_rule"
    assert ext.nlp is mock_nlp


def test_build_extractor_spacy_missing_model_raises_503(monkeypatch: pytest.MonkeyPatch):
    """[2026-07-03] spacy.load 抛 OSError → HTTPException 503 + 安装命令提示"""
    from fastapi import HTTPException

    from src.kg.router import _build_extractor

    # mock get_spacy_model 抛 RuntimeError, 模拟模型未下载 (2026-07-09 走 core manager 统一错误处理)
    def _fake_get_model(_model_name: str):
        raise RuntimeError(
            "spaCy 模型 zh_core_web_sm 未安装. 请运行: cd packages/service && uv run spacy download zh_core_web_sm"
        )

    monkeypatch.setattr("src.core.spacy_manager.get_spacy_model", _fake_get_model)

    with pytest.raises(HTTPException) as exc_info:
        _build_extractor("spacy_rule")
    assert exc_info.value.status_code == 503
    assert "zh_core_web_sm" in exc_info.value.detail
    assert "spacy download" in exc_info.value.detail


def test_build_extractor_llm_returns_llm_pydantic():
    """[M7] _build_extractor('llm_pydantic') → LlmPydanticExtractor (llm=None)"""
    from typing import Any, cast

    from src.kg.extractors.llm_pydantic.extractor import LlmPydanticExtractor
    from src.kg.router import _build_extractor

    ext = _build_extractor("llm_pydantic")
    assert isinstance(ext, LlmPydanticExtractor)
    assert ext.extractor_id == "llm_pydantic"
    assert cast(Any, ext).llm is None  # llm 是 llm_pydantic 的 attr


def test_build_extractor_unknown_raises():
    """[M7] _build_extractor 未知 id → ValueError"""
    from src.kg.router import _build_extractor

    with pytest.raises(ValueError, match="未知"):
        _build_extractor("nonexistent")


def test_build_splitter_all_three():
    """[M7] _build_splitter 3 个白名单都返对应 splitter"""
    from src.kg.router import _build_splitter

    assert _build_splitter("heading").splitter_id == "heading"
    assert _build_splitter("token").splitter_id == "token"
    assert _build_splitter("semantic").splitter_id == "semantic"


def test_build_splitter_unknown_raises():
    """[M7] _build_splitter 未知 id → ValueError"""
    from src.kg.router import _build_splitter

    with pytest.raises(ValueError, match="未知"):
        _build_splitter("nonexistent")


def test_start_extract_validate_dataset_in_request():
    """[M7] StartExtractRequest.dataset 字段类型应是 str

    Pydantic 不会强制 dataset 在 env 白名单 (那在 router 里做),
    但 start_extract endpoint 内部必跑 validate_dataset().
    本测试验证 validate_dataset 函数本身.
    """
    from src.kg.router import StartExtractRequest

    req = StartExtractRequest(
        uri="local://test.md",
        dataset="motor",
        extractor="spacy_rule",
        splitter="heading",
    )
    assert req.dataset == "motor"

    # dataset="evil_inject" 在白名单外 → 必抛 ValueError
    with pytest.raises(ValueError, match="白名单"):
        datasets.validate_dataset("evil_inject")


def test_start_extract_rejects_invalid_dataset_via_validate():
    """[M7] dataset 不在白名单 → validate_dataset 抛 ValueError

    start_extract 端点被 @audited 装饰器包成 async, 不能直接调测试函数;
    改测 validator 逻辑: dataset="evil_inject" 在白名单外 → 必抛 ValueError
    """
    with pytest.raises(ValueError, match="白名单"):
        datasets.validate_dataset("evil_inject")


def test_get_extract_task_returns_status():
    """[M7] get_extract_task → TaskStatus 字段"""
    from src.kg.router import _task_store, get_extract_task

    task_id = _task_store.submit("kg_extract", {"dataset": "motor"})
    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")

    result = get_extract_task(task_id=task_id, current_user=fake_user)
    assert result["task_id"] == task_id
    assert result["state"] in ("queued", "running", "done", "failed", "partial")


def test_get_extract_task_not_found_raises():
    """[M7] get_extract_task 不存在 → HTTPException 404"""
    from fastapi import HTTPException

    from src.kg.router import get_extract_task

    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")

    with pytest.raises(HTTPException) as exc_info:
        get_extract_task(task_id="nonexistent_task_id", current_user=fake_user)
    assert exc_info.value.status_code == 404


# (2026-07-03) KG 任务列表端点 list_extract_tasks + _serialize_task
# 测试需要替换模块级 _task_store (避免跨测试污染 + 验证新提交的 task 能被列出)


@pytest.fixture
def fresh_task_store(monkeypatch: pytest.MonkeyPatch):
    """注入新 TaskStore 替换 router 模块级 _task_store, 测试结束自动还原"""
    from src.kg import router as router_mod
    from src.kg.tasks import TaskStore

    new_store = TaskStore()
    monkeypatch.setattr(router_mod, "_task_store", new_store)
    return new_store


def test_list_extract_tasks_default_kg_extract(fresh_task_store):
    """[2026-07-03] GET /api/kg/extract/tasks 不传 kind 默认 kg_extract, 返 200 + items"""
    from src.kg.router import list_extract_tasks

    fresh_task_store.submit(
        "kg_extract", {"dataset": "motor", "uri": "local://x", "extractor": "spacy_rule", "splitter": "heading"}
    )
    fresh_task_store.submit("kg_batch", {"rows": []})  # 不应出现在默认结果

    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")
    result = list_extract_tasks(kind="kg_extract", limit=20, offset=0, current_user=fake_user)
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["kind"] == "kg_extract"
    assert result["items"][0]["dataset"] == "motor"
    assert result["items"][0]["uri"] == "local://x"
    assert result["total_success"] == 0
    assert result["total_failed"] == 0


def test_list_extract_tasks_filter_kind_batch(fresh_task_store):
    """[2026-07-03] kind=kg_batch 只返 batch 任务, kg_extract 被过滤"""
    from src.kg.router import list_extract_tasks

    fresh_task_store.submit(
        "kg_extract", {"dataset": "motor", "uri": "local://x", "extractor": "spacy_rule", "splitter": "heading"}
    )
    fresh_task_store.submit("kg_batch", {"rows": []})

    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")
    result = list_extract_tasks(kind="kg_batch", limit=20, offset=0, current_user=fake_user)
    assert result["total"] == 1
    assert result["items"][0]["kind"] == "kg_batch"
    # kg_batch 没有这些 payload 字段
    assert "dataset" not in result["items"][0]
    assert "uri" not in result["items"][0]


def test_list_extract_tasks_pagination(fresh_task_store):
    """[2026-07-03] limit + offset 切割 items, total 反映过滤后总数"""
    from src.kg.router import list_extract_tasks

    for _ in range(5):
        fresh_task_store.submit(
            "kg_extract", {"dataset": "motor", "uri": "local://x", "extractor": "spacy_rule", "splitter": "heading"}
        )

    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")
    page0 = list_extract_tasks(kind="kg_extract", limit=2, offset=0, current_user=fake_user)
    assert page0["total"] == 5
    assert len(page0["items"]) == 2
    assert page0["limit"] == 2
    assert page0["offset"] == 0

    page2 = list_extract_tasks(kind="kg_extract", limit=2, offset=4, current_user=fake_user)
    assert len(page2["items"]) == 1


def test_list_extract_tasks_invalid_kind_422(fresh_task_store):
    """[2026-07-03] kind 不在枚举 → HTTPException 422"""
    from fastapi import HTTPException

    from src.kg.router import list_extract_tasks

    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")
    with pytest.raises(HTTPException) as exc_info:
        list_extract_tasks(kind="invalid_kind", limit=20, offset=0, current_user=fake_user)
    assert exc_info.value.status_code == 422


def test_list_extract_tasks_aggregates_success_failed(fresh_task_store):
    """[2026-07-03] total_success / total_failed 是 kind 过滤后 sum"""
    from src.kg.router import list_extract_tasks

    tid_a = fresh_task_store.submit(
        "kg_extract", {"dataset": "motor", "uri": "local://a", "extractor": "spacy_rule", "splitter": "heading"}
    )
    fresh_task_store.mark_running(tid_a)
    fresh_task_store.mark_done(tid_a, success=10, failed=2)
    tid_b = fresh_task_store.submit(
        "kg_extract", {"dataset": "plc", "uri": "local://b", "extractor": "llm_pydantic", "splitter": "token"}
    )
    fresh_task_store.mark_running(tid_b)
    fresh_task_store.mark_done(tid_b, success=5, failed=0)
    # kg_batch 不参与 sum
    tid_c = fresh_task_store.submit("kg_batch", {"rows": []})
    fresh_task_store.mark_running(tid_c)
    fresh_task_store.mark_done(tid_c, success=100, failed=100)

    fake_user = MagicMock(id=1, email="admin@x.com", role="super_admin")
    result = list_extract_tasks(kind="kg_extract", limit=20, offset=0, current_user=fake_user)
    assert result["total"] == 2
    assert result["total_success"] == 15
    assert result["total_failed"] == 2
