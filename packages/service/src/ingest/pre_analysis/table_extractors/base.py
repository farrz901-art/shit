"""TableExtractor 抽象基类 + TableData dataclass + BackendNotInstalledError (2026-07-06)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from loguru import logger

# (2026-07-09) 退化表阈值, 3 个 extractor 共用
_MIN_ROWS: int = 2  # 至少 2 行 (含表头)
_MIN_COLS: int = 2  # 至少 2 列 (横表)


@dataclass(frozen=True)
class TableData:
    """单张表格单元. 3 个实现统一这个 shape, runner 不关心后端.

    Attributes:
        page_no: 1-based 页码 (跨页合并后是 str 如 "5+6")
        table_no: 1-based (该页内编号)
        rows: 二维字符串表格
        bbox: (x0, y0, x1, y1) PDF 坐标 bbox, None 表示未识别 (2026-07-09 新增).
    """

    # (2026-07-09) page_no 可 str: 跨页合并表编码 "5+6" 表示 5+6 页拼成 1 张
    page_no: int | str
    table_no: int
    rows: list[list[str]]
    # (2026-07-09) spec 4.6 + 4.7 需要 bbox 字段判重 (lattice/ml IoU + C2 同页 strategy dedup).
    # 默认 None 兼容老调用, frozen dataclass 用 .replace(bbox=...) 设值.
    bbox: tuple[float, float, float, float] | None = None

    def replace(self, **kwargs: Any) -> TableData:
        """(2026-07-09) immutable 字段替换. 跟 dataclasses.replace 一致, 暴露成方法方便 extractor 设 bbox.

        跟 StageContext.replace 同 pattern (stage_context.py:79).
        """
        return replace(self, **kwargs)

    @staticmethod
    def is_valid_table(rows: Sequence[Sequence[str]]) -> bool:
        """(2026-07-09) 硬阈值:行>=2 且 列>=2 (排除整行空白).

        解决 Camelot stream fallback 出来的 1×N 假表 (整段文本当一列),
        以及 pymupdf/pdfplumber 在某些 PDF 上的 1×1 单格输出.

        rows 可能为空 [] 或 [[]] (空表) — 都返回 False.
        2×1 纵列表同样视为退化 (PDF 表格场景几乎不存在真实纵列表).
        整行所有 cell strip 后都是空字符串算作该行无内容, 不计入行数.
        """
        if not rows:
            return False
        # 过滤掉"整行纯空白"的伪行, 这些是 Camelot 输出的占位行
        non_blank_rows = [r for r in rows if any((c or "").strip() for c in r)]
        if len(non_blank_rows) < _MIN_ROWS:
            return False
        cols = max((len(r) for r in non_blank_rows), default=0)
        return cols >= _MIN_COLS

    @staticmethod
    def filter_valid(
        tables: Sequence[TableData],
        backend_name: str,
    ) -> list[TableData]:
        """(2026-07-09) 批量过滤退化表, 抽到 base 让 3 个 extractor 共用.

        对每张表调 is_valid_table(td.rows), 退化表跳过 + logger.warning.
        返回仅含 valid 表的新 list (不修改入参).

        Args:
            tables: 候选 TableData 列表.
            backend_name: 日志前缀 (e.g. "pymupdf" / "camelot" / "pdfplumber").

        Returns:
            过滤后的新 list, 顺序与入参一致.
        """
        result: list[TableData] = []
        for td in tables:
            if not TableData.is_valid_table(td.rows):
                logger.warning(
                    "{} 过滤退化表 page={} table={} rows={} cols={}",
                    backend_name,
                    td.page_no,
                    td.table_no,
                    len(td.rows),
                    max((len(r) for r in td.rows), default=0),
                )
                continue
            result.append(td)
        return result


class TableExtractor(ABC):
    """表格提取策略接口.

    3 个适配器 (Pymupdf / Camelot / Pdfplumber) 都继承 + 实现 extract().
    """

    @abstractmethod
    def extract(
        self,
        pdf_path: str,
        *,
        _pymupdf_doc: object | None = None,
        **params: object,
    ) -> list[TableData]:
        """提取所有表格. PDF 无表格 → 返 [].

        Args:
            pdf_path: PDF 文件路径 (主用 _pymupdf_doc, 此处作 fallback).
            _pymupdf_doc: 已打开 pymupdf.Document (推荐传, runner 已开过).
                pymupdf 适配器复用, camelot / pdfplumber 适配器忽略.
            **params: backend-specific 参数.

        Returns:
            list[TableData] 表格列表, 按 (page, table_no) 顺序.
        """


class BackendNotInstalledError(RuntimeError):
    """后端 Python 包未安装. factory 调用时检测, HTTP 503 翻译用.

    Attributes:
        backend: backend 名 (e.g. "camelot", "pdfplumber", "camelot[ml]")
        install_hint: 安装提示 (e.g. "uv add camelot-py" / "uv add 'camelot-py[ml]'")
    """

    def __init__(self, backend: str, install_hint: str) -> None:
        super().__init__(f"{backend} 未安装: {install_hint}")
        self.backend = backend
        self.install_hint = install_hint
