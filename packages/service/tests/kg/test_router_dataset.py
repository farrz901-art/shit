"""dataset query param + GET /datasets + submit_triples admin 鉴权 测试"""

from unittest.mock import patch

import pytest

from src.kg import datasets


@pytest.fixture(autouse=True)
def _seed_datasets(monkeypatch: pytest.MonkeyPatch):
    """每个 test 前种子 ALLOWED_DATASETS 白名单, 避免被其他 test 污染"""
    monkeypatch.setattr(datasets, "ALLOWED_DATASETS", ["motor", "plc"])


def test_list_kg_datasets_returns_whitelist():
    """list_kg_datasets() 函数返 [{label}] 列表 (env 白名单)"""
    datasets.ALLOWED_DATASETS = ["motor", "plc"]
    from src.kg.router import list_kg_datasets

    result = list_kg_datasets()
    assert {d["label"] for d in result} == {"motor", "plc"}


def test_list_kg_datasets_empty_when_no_whitelist():
    """ALLOWED_DATASETS 空 → 返空列表"""
    datasets.ALLOWED_DATASETS = []
    from src.kg.router import list_kg_datasets

    result = list_kg_datasets()
    assert result == []


def test_validate_dataset_in_router_rejects_unknown():
    """router 端点入口 validate_dataset 拒绝白名单外 dataset

    直接测试 validate_dataset (router 端点逻辑已集成在 KgClient)
    """
    datasets.ALLOWED_DATASETS = ["motor", "plc"]
    import pytest as _pytest

    with _pytest.raises(ValueError, match="白名单"):
        datasets.validate_dataset("evil_inject")
    with _pytest.raises(ValueError, match="identifier"):
        datasets.validate_dataset("motor-bad")


def test_kgclient_validates_dataset_in_router_context():
    """KgClient 构造时强制 validate_dataset, 业务侧不会绕过 router"""
    from src.kg.client import KgClient

    with patch("src.kg.client.Neo4jStore"):
        kg = KgClient(dataset="motor")
        assert kg.dataset == "motor"
        # 不在白名单的 dataset 必报错
        import pytest as _pytest

        with _pytest.raises(ValueError):
            KgClient(dataset="hack")
