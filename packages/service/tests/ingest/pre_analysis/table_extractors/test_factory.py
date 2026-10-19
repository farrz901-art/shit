"""get_table_extractor 工厂测试 (mode 1 mock).

覆盖:
- 3 backend 路由都对
- 未知 backend 抛 ValueError
- params=None 走默认空 dict
"""

from __future__ import annotations

import pytest


def test_pymupdf_routes_to_pymupdf_adapter() -> None:
    """backend='pymupdf' → PymupdfTableExtractor."""
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    ext = get_table_extractor("pymupdf", {})
    assert isinstance(ext, PymupdfTableExtractor)


def test_camelot_routes_to_camelot_adapter() -> None:
    """backend='camelot' → 路由到 camelot 后端 (可能抛 BackendNotInstalledError).

    (2026-07-08) factory 包了一层 _CamelotFallbackWrapper, 真实类型不再是 CamelotTableExtractor,
    但 extract() 行为一致. 验证 wrapper 有 extract() 方法 + 能 mock 调通即可.
    """
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    try:
        ext = get_table_extractor("camelot", {"flavor": "lattice"})
    except BackendNotInstalledError as e:
        # 包未装 OK, 关键是路由判断正确 (factory 选对了实现)
        assert e.backend == "camelot"
    else:
        # wrapper 必有 extract() 方法
        assert hasattr(ext, "extract"), "camelot wrapper 应有 extract() 方法"


def test_pdfplumber_routes_to_pdfplumber_adapter() -> None:
    """backend='pdfplumber' → 路由到 PdfplumberTableExtractor."""
    from src.ingest.pre_analysis.table_extractors.base import (
        BackendNotInstalledError,
    )
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor
    from src.ingest.pre_analysis.table_extractors.pdfplumber_extractor import (
        PdfplumberTableExtractor,
    )

    try:
        ext = get_table_extractor("pdfplumber", {})
    except BackendNotInstalledError as e:
        assert e.backend == "pdfplumber"
    else:
        assert isinstance(ext, PdfplumberTableExtractor)


def test_unknown_backend_raises_value_error() -> None:
    """backend='foo' → ValueError 含 backend 名."""
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    with pytest.raises(ValueError) as exc_info:
        get_table_extractor("foo", {})
    assert "未知表格后端" in str(exc_info.value)
    assert "foo" in str(exc_info.value)


def test_default_params_when_none() -> None:
    """params=None → 适配器正常构造 (默认空 dict 透传)."""
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor
    from src.ingest.pre_analysis.table_extractors.pymupdf_extractor import (
        PymupdfTableExtractor,
    )

    ext = get_table_extractor("pymupdf", params=None)
    assert isinstance(ext, PymupdfTableExtractor)
    assert ext._params == {}


# (2026-07-08) factory camelot backend 默认开 fallback_chain -------------------------------


def test_factory_camelot_extract_uses_fallback_chain_by_default() -> None:
    """(2026-07-08) factory 返出的 camelot wrapper extract() 默认走 fallback 链.

    验证: 调 wrapper.extract() 时, 内部会调 CamelotTableExtractor.extract_with_fallback.
    """
    pytest.importorskip("camelot")
    from unittest.mock import patch

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    with patch.object(CamelotTableExtractor, "extract_with_fallback", return_value=[]) as mock_fb:
        ext = get_table_extractor("camelot", {"flavor": "lattice"})
        result = ext.extract("dummy.pdf")

    assert result == []
    assert mock_fb.called, "factory 应默认调 extract_with_fallback, 没调说明 factory 没接 fallback 钩子"


def test_factory_camelot_fallback_chain_can_be_disabled() -> None:
    """(2026-07-08) fallback_chain=False → wrapper.extract 走单 flavor (旧版行为).

    实现: wrapper 统一调 extract_with_fallback, 后者内部按 fallback_chain 参数
    决定是单 flavor 还是链. 验证传入的 fallback_chain=False 被透传.
    """
    pytest.importorskip("camelot")
    from unittest.mock import patch

    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    with patch.object(CamelotTableExtractor, "extract_with_fallback", return_value=[]) as mock_fb:
        ext = get_table_extractor("camelot", {"flavor": "lattice", "fallback_chain": False})
        result = ext.extract("dummy.pdf")

    assert result == []
    assert mock_fb.called, "fallback_chain=False 也走 extract_with_fallback 路径 (内部判 fallback_chain)"
    # 验证传了 fallback_chain=False
    assert mock_fb.call_args.kwargs.get("fallback_chain") is False, (
        f"应透传 fallback_chain=False, 实际 {mock_fb.call_args.kwargs}"
    )


def test_camelot_ghostscript_extra_available() -> None:
    """(2026-07-09) camelot[ghostscript] extra 装了 → pdfminer.six (ghostscript 间接依赖) 可 import."""
    try:
        import pdfminer  # noqa: F401 — ghostscript extra 的间接依赖
    except ImportError:
        pytest.fail("camelot[ghostscript] extra 未装, 需 uv sync 后重试")


def test_factory_camelot_wrapper_passes_through_new_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(2026-07-09) wrapper 透传 max_page_workers / ml_max_workers / ml_device 到 CamelotTableExtractor.

    extract_with_fallback 内部开 CamelotTableExtractor({**user_params, "flavor": try_flavor}),
    这些新 params 通过 self._params 流到 extract() (Task 4 extract 已消费).
    """
    from src.ingest.pre_analysis.table_extractors.camelot_extractor import (
        CamelotTableExtractor,
    )
    from src.ingest.pre_analysis.table_extractors.factory import get_table_extractor

    captured_init_params: list[dict] = []

    original_extractor_init = CamelotTableExtractor.__init__

    def spy_init(self: CamelotTableExtractor, params: dict) -> None:
        captured_init_params.append(dict(params))
        original_extractor_init(self, params)

    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CamelotTableExtractor.__init__",
        spy_init,
    )
    # stub extract 避免触发真 PDF
    monkeypatch.setattr(
        "src.ingest.pre_analysis.table_extractors.camelot_extractor.CamelotTableExtractor.extract",
        lambda *args, **kwargs: [],
    )

    wrapper = get_table_extractor(
        "camelot",
        {
            "flavor": "lattice",
            "max_page_workers": 8,
            "ml_max_workers": 3,
            "ml_device": "cpu",
        },
    )
    wrapper.extract("/tmp/fake.pdf")

    # extract_with_fallback 内部按 flavor 顺序 try, 新 params 应至少在一次 init 中出现
    assert any(
        p.get("max_page_workers") == 8 and p.get("ml_max_workers") == 3 and p.get("ml_device") == "cpu"
        for p in captured_init_params
    ), f"新 params 未透传到 CamelotTableExtractor.__init__: {captured_init_params}"
