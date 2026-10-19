"""章节提取配置 (2026-07-09, PDF 章节树状化+LLM增强).

ChapterExtractionConfig: 业务配置 dataclass, 跟 router form 字段对齐.
from_form 解析 JSON, 缺字段走默认值, 越界 clamp.

参考 table_extractors 工厂模式 + router.py:97 的 table_params JSON 解析.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

LLMProvider = Literal["openai", "ollama"]

# 默认值常量, 集中放本文件方便路由 + 测试共用
DEFAULT_CHAPTER_MAX_LEVEL = 3
DEFAULT_LLM_SUMMARY_MAX_LEVEL = 3
DEFAULT_LLM_SUMMARY_PER_CHAPTER_PAGES = 2
MIN_LEVEL = 1
MAX_LEVEL = 6
MIN_PAGES = 1
MAX_PAGES = 10


@dataclass(frozen=True)
class ChapterExtractionConfig:
    """章节提取配置. 字段映射前端 form JSON key.

    Attributes:
        enable_llm_refinement: 是否启用 LLM 章节重组 (fallback).
        llm_provider: LLM provider 名 (openai | ollama).
        chapter_max_level_for_display: 树状显示的最大层级 (1-6).
        llm_summary_max_level: 摘要生成的最大层级 (1-6).
        llm_summary_per_chapter_pages: 每章取前 N 页做摘要 (1-10).
    """

    enable_llm_refinement: bool = False
    llm_provider: LLMProvider = "openai"
    chapter_max_level_for_display: int = DEFAULT_CHAPTER_MAX_LEVEL
    llm_summary_max_level: int = DEFAULT_LLM_SUMMARY_MAX_LEVEL
    llm_summary_per_chapter_pages: int = DEFAULT_LLM_SUMMARY_PER_CHAPTER_PAGES

    @classmethod
    def from_form(cls, chapter_config_json: str = "{}") -> ChapterExtractionConfig:
        """从 form JSON 字符串解析. 缺字段走默认, 越界 clamp, JSON 非法 → ValueError.

        Args:
            chapter_config_json: JSON 字符串, 形如 '{"enable_llm_refinement": true, ...}'.

        Raises:
            ValueError: chapter_config_json 不是合法 JSON.
        """
        try:
            data = json.loads(chapter_config_json) if chapter_config_json else {}
        except json.JSONDecodeError as e:
            raise ValueError(f"chapter_config_json JSON 非法: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"chapter_config_json 必须是 JSON object, 拿到 {type(data).__name__}")
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> ChapterExtractionConfig:
        """逐字段读取, 缺字段用 default, 类型不匹配走 default, 越界 clamp."""
        enable = data.get("enable_llm_refinement", cls.enable_llm_refinement)
        if not isinstance(enable, bool):
            enable = cls.enable_llm_refinement

        provider = data.get("llm_provider", cls.llm_provider)
        if provider not in ("openai", "ollama"):
            provider = cls.llm_provider

        max_disp = _clamp_int(
            data.get("chapter_max_level_for_display"),
            cls.chapter_max_level_for_display,
            MIN_LEVEL,
            MAX_LEVEL,
        )
        max_sum = _clamp_int(
            data.get("llm_summary_max_level"),
            cls.llm_summary_max_level,
            MIN_LEVEL,
            MAX_LEVEL,
        )
        per_pages = _clamp_int(
            data.get("llm_summary_per_chapter_pages"),
            cls.llm_summary_per_chapter_pages,
            MIN_PAGES,
            MAX_PAGES,
        )

        return cls(
            enable_llm_refinement=enable,
            llm_provider=provider,  # type: ignore[arg-type]
            chapter_max_level_for_display=max_disp,
            llm_summary_max_level=max_sum,
            llm_summary_per_chapter_pages=per_pages,
        )

    def to_dict(self) -> dict[str, Any]:
        """反序列化为 dict, 便于存 task_config_json."""
        return {
            "enable_llm_refinement": self.enable_llm_refinement,
            "llm_provider": self.llm_provider,
            "chapter_max_level_for_display": self.chapter_max_level_for_display,
            "llm_summary_max_level": self.llm_summary_max_level,
            "llm_summary_per_chapter_pages": self.llm_summary_per_chapter_pages,
        }


def _clamp_int(value: Any, default: int, min_v: int, max_v: int) -> int:
    """从 JSON value 取 int, 缺/类型错走 default, 越界 clamp."""
    if value is None:
        return default
    if isinstance(value, bool):  # bool 是 int 子类, 排掉
        return default
    if not isinstance(value, int):
        return default
    return max(min_v, min(max_v, value))


__all__ = [
    "ChapterExtractionConfig",
    "DEFAULT_CHAPTER_MAX_LEVEL",
    "DEFAULT_LLM_SUMMARY_MAX_LEVEL",
    "DEFAULT_LLM_SUMMARY_PER_CHAPTER_PAGES",
]
