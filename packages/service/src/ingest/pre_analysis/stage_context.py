# packages/service/src/ingest/pre_analysis/stage_context.py
"""Stage 间数据契约 (2026-07-09).

StageContext: 5 个 stage 共用依赖容器, frozen + replace() immutable 传值.
StageResult: stage 函数返值, 表达 ok/error.
ObjectStoreProto / StageStoreProto: Protocol 定义, 跟 StageContext 同文件方便 stage 直接 import.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol

import pymupdf

from .stage_models import PreAnalysisStage
from .store import PreAnalysisTaskStore


class ObjectStoreProto(Protocol):
    """(2026-07-09) 从 runner.py 搬过来. 跟 src/storage/object_store.py ObjectStore ABC 同 shape."""

    def put_bytes(self, uri: str, data: bytes, mime: str = "application/octet-stream") -> None: ...

    def open_local(self, uri: str) -> str: ...

    def backend_name(self) -> str: ...


class StageStoreProto(Protocol):
    """(2026-07-09) 从 runner.py 搬过来."""

    def mark_stage_started(self, task_id: str, stage: str) -> None: ...

    def mark_stage_completed(
        self, task_id: str, stage: str, progress: int = 100, message: str | None = None
    ) -> None: ...

    def mark_stage_failed(self, task_id: str, stage: str, error: str) -> None: ...

    def list_stages(self, task_id: str) -> list[PreAnalysisStage]: ...


@dataclass(frozen=True)
class StageContext:
    """5 个 stage 共用依赖容器. frozen=True + replace() immutable 传值.

    阶段间数据流: stage 1 写 doc/config/output_prefix, stage 2 写 chapters/chapter_uri,
    依此类推. stage 函数返 (ctx.replace(...), StageResult).
    """

    task_id: str
    pdf_uri: str
    object_store: ObjectStoreProto
    task_store: PreAnalysisTaskStore  # noqa: F821  # 类型注入在 runner 装配时显式声明
    stage_store: StageStoreProto
    start_monotonic: float

    # stage 1 产出
    doc: pymupdf.Document | None = None
    config: dict | None = None
    output_prefix: str | None = None

    # stage 2 产出
    chapters: list[dict] | None = None
    chapter_uri: str | None = None

    # stage 3 产出
    tables: list[tuple[int, int, list[list[str]]]] | None = None
    cross_page_count: int = 0

    # stage 4 产出
    flagged: list[dict] | None = None
    flagged_uri: str | None = None

    # stage 5 产出
    index_uri: str | None = None

    def replace(self, **kwargs: Any) -> StageContext:
        """immutable 字段替换. 跟 dataclasses.replace 一致, 暴露成方法方便 stage 调 ctx.replace(...)."""
        return replace(self, **kwargs)


@dataclass(frozen=True)
class StageResult:
    """stage 函数返回. ok=False 表示 stage 失败, runner 应终止."""

    ok: bool
    error: str | None = None
    stage_name: str = ""
    message: str | None = None


__all__ = ["ObjectStoreProto", "StageStoreProto", "StageContext", "StageResult"]
