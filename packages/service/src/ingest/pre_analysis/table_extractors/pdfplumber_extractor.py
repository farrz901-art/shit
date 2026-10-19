"""PdfplumberTableExtractor (2026-07-06).

纯 Python (pdfminer.six-based), MIT 许可证, 有可视化调试.
Lazy import: 缺包抛 BackendNotInstalledError.
"""

from __future__ import annotations

from .base import BackendNotInstalledError, TableData, TableExtractor

_INSTALL_HINT = "uv add pdfplumber"


class PdfplumberTableExtractor(TableExtractor):
    """pdfplumber.open() + pages.extract_tables() 适配器."""

    def __init__(self, params: dict) -> None:
        self._params = params
        try:
            import pdfplumber  # noqa: F401  # 可选依赖
        except ImportError as e:
            raise BackendNotInstalledError(backend="pdfplumber", install_hint=_INSTALL_HINT) from e

    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: object | None = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格."""
        import pdfplumber

        table_settings = {
            "vertical_strategy": self._params.get("vertical_strategy", "lines"),
            "horizontal_strategy": self._params.get("horizontal_strategy", "lines"),
            "snap_tolerance": self._params.get("snap_tolerance", 3),
            "join_tolerance": self._params.get("join_tolerance", 3),
        }
        raw: list[TableData] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables(table_settings=table_settings)
                for table_no, rows in enumerate(tables, start=1):
                    normalized: list[list[str]] = [
                        [str(cell) if cell is not None else "" for cell in row] for row in rows
                    ]
                    raw.append(TableData(page_no=page_idx + 1, table_no=table_no, rows=normalized))
        # (2026-07-09) 抽到 TableData.filter_valid, 3 个 extractor 共用
        return TableData.filter_valid(raw, backend_name="pdfplumber")
