"""Ghostscript fallback 专项测试 (mode 1 mock).

(2026-07-09) B 模块: ghostscript extra + use_fallback=True 后端写死.
- 验证 _FLAVOR_DEFAULTS 含 use_fallback=True
- 验证 use_fallback=True 被透传给单页调度 (Task 4 重构后 camelot.read_pdf 不再直接被 extract 调,
  改走 _run_camelot_single_page, 所以验证点改为捕获 params 而不是 camelot.read_pdf 的 kwargs).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_flavor_defaults_includes_use_fallback() -> None:
    """(2026-07-09) _FLAVOR_DEFAULTS["lattice"] 含 use_fallback=True."""
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        _FLAVOR_DEFAULTS,
    )

    defaults = _FLAVOR_DEFAULTS["lattice"]
    assert defaults.get("use_fallback") is True, f"_FLAVOR_DEFAULTS['lattice'] 缺 use_fallback=True, 当前: {defaults}"


def test_use_fallback_passed_to_camelot() -> None:
    """(2026-07-09) use_fallback=True 透传到单页调度 params.

    (2026-07-09) Task 4: extract() 改为按页并行 _extract_single_page → _run_camelot_single_page
    → _call_camelot → camelot.read_pdf. 验证 caller 显式传 use_fallback=True 仍在 params dict 里.
    """
    pytest.importorskip("camelot")
    from src.ingest.pre_analysis.table_extractors.base import TableData
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )

    captured_params: list[dict] = []

    def fake_run(pdf_path: str, page: int, flavor: str, params: dict) -> list[TableData]:  # noqa: ARG001
        captured_params.append(dict(params))
        return []

    # 构造 mock pymupdf doc, 让 extract 跳过 pymupdf.open (单页调度即可)
    class _MockPage:
        def find_tables(self, strategy: str) -> list:  # noqa: ARG002
            return []

    class _MockDoc:
        page_count = 1

        def load_page(self, page_idx: int) -> object:  # noqa: ARG002
            return _MockPage()

    with patch(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor._run_camelot_single_page",
        side_effect=fake_run,
    ):
        CamelotTableExtractor({"flavor": "lattice", "use_fallback": True}).extract(
            "dummy.pdf",
            _pymupdf_doc=_MockDoc(),
        )

    assert captured_params, "extract 应至少调一次 _run_camelot_single_page"
    assert captured_params[0].get("use_fallback") is True, "caller 显式 use_fallback=True 透传到单页调度"
