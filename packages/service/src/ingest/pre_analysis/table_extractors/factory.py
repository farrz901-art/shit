"""get_table_extractor 工厂 — backend 字符串 → 适配器实例 (2026-07-06)."""

from __future__ import annotations

from typing import cast

from .base import TableData, TableExtractor


def get_table_extractor(backend: str, params: dict | None = None) -> TableExtractor:
    """工厂: backend 字符串 → 适配器实例.

    Args:
        backend: "pymupdf" | "camelot" | "pdfplumber"
        params: backend-specific 参数 (e.g. flavor / edge_tol / vertical_strategy)

    Returns:
        TableExtractor 实例.

    Raises:
        ValueError: backend 不在白名单.
        BackendNotInstalledError: 选了 camelot/pdfplumber 但 Python 包没装 (transitively 由适配器 __init__ 抛).
    """
    effective_params = params or {}
    match backend:
        case "pymupdf":
            from .pymupdf_extractor import PymupdfTableExtractor

            return PymupdfTableExtractor(effective_params)
        case "camelot":
            from .camelot_extractor import CamelotTableExtractor

            # (2026-07-08) 包装一层: 调 extract() 时默认走 extract_with_fallback.
            # admin 可传 params={"fallback_chain": False} 关掉 (单 flavor 行为, 跟旧版一致).
            class _CamelotFallbackWrapper:
                """把 fallback_chain params 透传到 extract_with_fallback."""

                def __init__(self, params: dict) -> None:
                    self._flavor: str = params.get("flavor", "lattice")
                    self._fallback_chain: bool = bool(params.get("fallback_chain", True))
                    self._params: dict = {k: v for k, v in params.items() if k not in {"flavor", "fallback_chain"}}

                def extract(
                    self,
                    pdf_path: str,
                    *,
                    _pymupdf_doc: object | None = None,
                    **kw: object,
                ) -> list[TableData]:
                    return CamelotTableExtractor.extract_with_fallback(
                        pdf_path,
                        flavor=self._flavor,
                        params=self._params,
                        _pymupdf_doc=_pymupdf_doc,
                        fallback_chain=self._fallback_chain,
                    )

            return cast(TableExtractor, _CamelotFallbackWrapper(effective_params))
        case "pdfplumber":
            from .pdfplumber_extractor import PdfplumberTableExtractor

            return PdfplumberTableExtractor(effective_params)
        case _:
            raise ValueError(f"未知表格后端: {backend}")
