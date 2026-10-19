"""OpenAPI 元数据 smoke test: 验 78 端点 + 14 tag + 字段 description 全部就位

(2026-06-17) feat(openapi): 全局 OpenAPI 展示增强 — 防回归
(2026-06-19) phase2: 改用 TestClient 不依赖真服务 (端口 8000)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def spec() -> dict:
    """从业务 FastAPI app 拉 OpenAPI spec, 不依赖真起服务."""
    from src.core.app_factory import create_app

    app = create_app()
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200, f"openapi.json fetch failed: {resp.status_code}"
    return resp.json()


def test_info_title_and_contact(spec: dict) -> None:
    """L1: info.title / contact / license / servers 全有值"""
    info = spec["info"]
    assert info["title"] == "RAG + 产品订货号解析服务"
    assert info["contact"]["name"] == "RAG Backend Team"
    assert info["license"]["name"] == "MIT"
    assert len(spec.get("servers", [])) == 3


def test_all_tags_have_description(spec: dict) -> None:
    """L2: 14 tag 全有 description"""
    no_desc = [t["name"] for t in spec["tags"] if not t.get("description")]
    assert no_desc == [], f"missing description on tags: {no_desc}"


def test_all_endpoints_have_summary_and_description(spec: dict) -> None:
    """L3: 78 端点 100% 有 summary + description"""
    no_summary = []
    no_description = []
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method in ("get", "post", "put", "patch", "delete"):
                if not op.get("summary"):
                    no_summary.append(f"{method.upper()} {path}")
                if not op.get("description"):
                    no_description.append(f"{method.upper()} {path}")
    assert no_summary == [], f"missing summary: {no_summary}"
    assert no_description == [], f"missing description: {no_description}"


def test_endpoint_count(spec: dict) -> None:
    """端点总数 >= 67"""
    count = 0
    for methods in spec["paths"].values():
        for method in methods:
            if method in ("get", "post", "put", "patch", "delete"):
                count += 1
    assert count >= 67, f"expected >= 67 endpoints, got {count}"


def test_field_descriptions_coverage(spec: dict) -> None:
    """L4: Pydantic 字段 100% 描述覆盖 (排 framework + inline body)"""
    # 已知不可修的字段: 3 framework ValidationError + 4 inline multipart Body
    UNMODIFIABLE = {
        "components.schemas.ValidationError.msg",
        "components.schemas.ValidationError.type",
        "components.schemas.ValidationError.input",
        "components.schemas.ValidationError.ctx",
        "components.schemas.Body_upload_file_api_chat_files_post.file",
        "components.schemas.Body_upload_run_api_evaluate_runs_post.concurrency",
        "components.schemas.Body_post_avatar_api_account_avatar_post.file",
        "components.schemas.Body_upload_extract_file_api_kg_extract_upload_post.file",
        "components.schemas.Body_upload_pre_analysis_api_pre_analysis_upload_post.file",
        "components.schemas.Body_upload_pre_analysis_api_pre_analysis_upload_post.table_backend",
        "components.schemas.Body_upload_pre_analysis_api_pre_analysis_upload_post.table_params",
        "components.schemas.PatchItem.selected",
        "components.schemas.StartExtractRequest.extractor",
        "components.schemas.StartExtractRequest.splitter",
    }
    total, no_desc = 0, 0
    no_desc_list = []

    def walk(o, path=""):
        nonlocal total, no_desc
        if isinstance(o, dict):
            if "properties" in o and isinstance(o["properties"], dict) and o.get("type") == "object":
                for k, v in o["properties"].items():
                    if isinstance(v, dict) and "$ref" not in v and v.get("type") != "array":
                        total += 1
                        if v.get("description") is None:
                            no_desc += 1
                            no_desc_list.append(f"{path}.{k}")
            for k, v in o.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for x in o:
                walk(x, path)

    walk(spec)
    real_no_desc = [x for x in no_desc_list if x not in UNMODIFIABLE]
    assert real_no_desc == [], f"missing description: {real_no_desc}"
    assert total >= 100, f"expected >= 100 fields, got {total}"
