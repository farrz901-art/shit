# packages/service/src/ingest/pre_analysis_runner.py
"""PreAnalysisRunner: PDF 后台预分析 pipeline (2026-07-02)

设计 (跟 src/kg/extract_runner.py:49 run_extraction 模式对齐):
- 接收 ObjectStore URI 形式 PDF
- 调 pymupdf 提取 TOC + 表格 CSV + 关键词段落
- 产物写 ObjectStore (chapter_structure.json / tables/*.csv / flagged_paragraphs.csv / index.json)
- 更新 DB state (pending → running → completed / failed)

跨页表候选检测: 启发式 (页 N 表格 N 跟页 N+1 表格 1 列数 ≥ 80% 一致 + footer 关键词),
计数写 summary.cross_page_candidates, 不自动合并 (本期不做, 用户决策 2026-07-02).

(2026-07-03) 5 stage wrap: load_config / extract_chapters / extract_tables / extract_flagged / write_outputs
每个 stage mark_stage_started → 跑函数 → mark_stage_completed (success) / mark_stage_failed (异常).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from .chapter_extractors.chapter_config import ChapterExtractionConfig
from .stage_models import PreAnalysisStage
from .store import PreAnalysisTaskStore


@dataclass(frozen=True)
class PreAnalysisResult:
    """Runner 返回值, API 层直接序列化给前端."""

    success: bool
    task_id: str
    chapter_structure_uri: str = ""
    flagged_paragraphs_uri: str = ""
    table_uris: list[str] = field(default_factory=list)
    index_uri: str = ""
    total_chapters: int = 0
    total_tables: int = 0
    total_flagged: int = 0
    cross_page_candidates: int = 0
    elapsed_ms: int = 0
    error: str | None = None


class ObjectStoreProto(Protocol):
    """跟 src/storage/object_store.py ObjectStore ABC 同 shape (mode 1 mock 用)."""

    def put_bytes(self, uri: str, data: bytes, mime: str = "application/octet-stream") -> None: ...

    def open_local(self, uri: str) -> str: ...

    def backend_name(self) -> str:
        """(2026-07-03) 返 'local' / 'minio', 供 _output_prefix 拼正确 URI scheme."""
        ...


class StageStoreProto(Protocol):
    """(2026-07-03) stage 状态切换 facade. 实现由 PreAnalysisStageStore 提供."""

    def mark_stage_started(self, task_id: str, stage: str) -> None: ...

    def mark_stage_completed(
        self, task_id: str, stage: str, progress: int = 100, message: str | None = None
    ) -> None: ...

    def mark_stage_failed(self, task_id: str, stage: str, error: str) -> None: ...

    # (2026-07-07) 失败时抽 partial summary 需要, mark_failed 拿已完成 stage message
    def list_stages(self, task_id: str) -> list[PreAnalysisStage]: ...


@dataclass(frozen=True)
class PreAnalysisRunner:
    """PDF 预分析 runner (mode 1 mock friendly)."""

    object_store: ObjectStoreProto
    task_store: PreAnalysisTaskStore
    # (2026-07-03) 新增 stage_store, 5 stage wrap 调
    stage_store: StageStoreProto
    # (2026-07-09) 删 keyword_config_path: prepare_input 走 env RULE_KEYWORDS_PATH 自己找 yaml,
    # 不再需要 runner 持路径透传.

    def run(
        self,
        task_id: str,
        pdf_uri: str,
        table_extraction_config: dict | None = None,  # (2026-07-06) M2 Strategy 后端配置
        chapter_config: ChapterExtractionConfig | None = None,  # (2026-07-09 PDF 章节树状化)
    ) -> PreAnalysisResult:
        """主入口. PDF 不存在 / 损坏 → 返 success=False + error.

        Args:
            task_id: 业务 UUID.
            pdf_uri: ObjectStore URI (s3://... / local://...).
            table_extraction_config: (2026-07-06) 后端配置 {backend, params}.
                None → 走默认 pymupdf + 空 params.
            chapter_config: (2026-07-09) 章节配置 (max_level, llm 等), None → 走默认.

        Returns:
            PreAnalysisResult with success + counts + URIs.
        """
        if table_extraction_config is None:
            table_extraction_config = {"table_backend": "pymupdf", "table_params": {}}
        start = time.monotonic()
        # === stage 1: prepare_input (open PDF + 加载 yaml + 拼 output_prefix) ===
        # (2026-07-09) 抽到 prepare_input.py. 失败由 stage 内部 mark_failed, runner 终止.
        from .prepare_input import prepare_input  # noqa: PLC0415 局部 import 避免循环
        from .stage_context import StageContext

        ctx = StageContext(
            task_id=task_id,
            pdf_uri=pdf_uri,
            object_store=self.object_store,
            task_store=self.task_store,
            stage_store=self.stage_store,
            start_monotonic=start,
        )
        # 转换 task 状态 pending → running (原 line 119 行为)
        self.task_store.mark_running(task_id)
        ctx, stage_r = prepare_input(ctx)
        if not stage_r.ok:
            doc = ctx.doc
            if doc is not None:
                doc.close()
            return PreAnalysisResult(success=False, task_id=task_id, error=stage_r.error or "stage 1 failed")
        doc = ctx.doc
        assert doc is not None  # type: ignore[unreachable]  # prepare_input 成功后必填
        output_prefix = ctx.output_prefix
        assert output_prefix is not None  # type: ignore[unreachable]  # 同上

        # === stage 2: chapters_section (抽到 chapter_extractors/chapters_section.py, 2026-07-09) ===
        from .chapter_extractors.chapters_section import run as chapters_run  # noqa: PLC0415

        ctx, stage_r = chapters_run(ctx, chapter_config=chapter_config)
        if not stage_r.ok:
            doc.close()
            return PreAnalysisResult(success=False, task_id=task_id, error=stage_r.error or "stage 2 failed")
        chapters = ctx.chapters
        chapter_uri = ctx.chapter_uri
        assert chapters is not None  # type: ignore[unreachable]  # chapters_run 成功后必填
        assert chapter_uri is not None  # type: ignore[unreachable]  # 同上

        # === stage 3: tables_section (抽到 table_extractors/tables_section.py, 2026-07-09) ===
        from .table_extractors.tables_section import run as tables_run  # noqa: PLC0415

        ctx, stage_r = tables_run(ctx, table_extraction_config=table_extraction_config)
        if not stage_r.ok:
            doc.close()
            return PreAnalysisResult(success=False, task_id=task_id, error=stage_r.error or "stage 3 failed")
        tables = ctx.tables
        cross_page = ctx.cross_page_count
        assert tables is not None  # type: ignore[unreachable]  # tables_run 成功后必填

        # === stage 4: flagged_section (抽到 flag_extractors/flagged_section.py, 2026-07-09) ===
        from .flag_extractors.flagged_section import run as flagged_run  # noqa: PLC0415

        ctx, stage_r = flagged_run(ctx)
        if not stage_r.ok:
            doc.close()
            return PreAnalysisResult(success=False, task_id=task_id, error=stage_r.error or "stage 4 failed")
        flagged = ctx.flagged
        flagged_uri = ctx.flagged_uri
        assert flagged is not None  # type: ignore[unreachable]  # flagged_run 成功后必填
        assert flagged_uri is not None  # type: ignore[unreachable]  # 同上

        # === stage 5: finalize_output (抽到 finalize_output.py, 2026-07-09) ===
        from .finalize_output import run as finalize_run  # noqa: PLC0415

        ctx, stage_r = finalize_run(ctx, table_extraction_config=table_extraction_config)
        if not stage_r.ok:
            doc.close()
            return PreAnalysisResult(success=False, task_id=task_id, error=stage_r.error or "stage 5 failed")
        index_uri = ctx.index_uri
        assert index_uri is not None  # type: ignore[unreachable]  # finalize_run 成功后必填

        doc.close()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return PreAnalysisResult(
            success=True,
            task_id=task_id,
            chapter_structure_uri=chapter_uri,
            flagged_paragraphs_uri=flagged_uri,
            table_uris=[],  # (2026-07-06) 表格 URI 在 output_files_json 里, 不再汇总
            index_uri=index_uri,
            total_chapters=len(chapters),
            total_tables=len(tables),
            total_flagged=len(flagged),
            cross_page_candidates=cross_page,
            elapsed_ms=elapsed_ms,
        )

    # (2026-07-09) 抽到 table_extractors/tables_section.py. 留 thin wrapper 兼容 test_runner.py 老调用.
    @staticmethod
    def _detect_cross_page(
        # (2026-07-09) 用 Sequence 协变兼容测试传的 list[tuple[int, ...]] (跨页合并后 page_no 才升级 str)
        tables: Sequence[tuple[int | str, int, Sequence[Sequence[str]]]],
        config: dict,
    ) -> int:
        """薄壳, 走新位置. test_runner.py 仍调 runner._detect_cross_page."""
        from .table_extractors.tables_section import _detect_cross_page as _impl

        return _impl(list(tables), config)

    # (2026-07-09) 抽到 flag_extractors/flagged_section.py. 留 thin wrapper 兼容 test_runner.py 老调用.
    def _write_flagged_paragraphs(self, prefix: str, flagged: list[dict], task_id: str) -> tuple[str, int]:
        """薄壳, 走新位置. test_runner.py 仍调 runner._write_flagged_paragraphs."""
        from .flag_extractors.flagged_section import write_flagged_csv

        return write_flagged_csv(self.object_store, prefix, flagged, task_id)


__all__ = ["PreAnalysisRunner", "PreAnalysisResult"]
