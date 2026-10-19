"""chapter_config.py 测试 (mode 1 mock, 2026-07-09).

ChapterExtractionConfig 覆盖:
- 默认值
- from_form 正常 / 缺字段 / 类型错 / 越界 clamp / 非法 JSON
- to_dict 序列化
"""

from __future__ import annotations

import json

import pytest


class TestChapterExtractionConfig:
    def test_defaults(self) -> None:
        """无参构造走 dataclass default."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig()
        assert cfg.enable_llm_refinement is False
        assert cfg.llm_provider == "openai"
        assert cfg.chapter_max_level_for_display == 3
        assert cfg.llm_summary_max_level == 3
        assert cfg.llm_summary_per_chapter_pages == 2

    def test_from_form_empty(self) -> None:
        """空 JSON → 默认."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig.from_form("{}")
        assert cfg == ChapterExtractionConfig()

    def test_from_form_normal(self) -> None:
        """正常字段解析."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        data = {
            "enable_llm_refinement": True,
            "llm_provider": "ollama",
            "chapter_max_level_for_display": 4,
            "llm_summary_max_level": 5,
            "llm_summary_per_chapter_pages": 3,
        }
        cfg = ChapterExtractionConfig.from_form(json.dumps(data))
        assert cfg.enable_llm_refinement is True
        assert cfg.llm_provider == "ollama"
        assert cfg.chapter_max_level_for_display == 4
        assert cfg.llm_summary_max_level == 5
        assert cfg.llm_summary_per_chapter_pages == 3

    def test_from_form_missing_fields_use_defaults(self) -> None:
        """只传 1 个字段, 其余走默认."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig.from_form(json.dumps({"llm_provider": "ollama"}))
        assert cfg.llm_provider == "ollama"
        assert cfg.enable_llm_refinement is False
        assert cfg.chapter_max_level_for_display == 3

    def test_from_form_clamp_lower(self) -> None:
        """小于 1 → clamp 到 1."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig.from_form(
            json.dumps(
                {
                    "chapter_max_level_for_display": 0,
                    "llm_summary_max_level": -1,
                    "llm_summary_per_chapter_pages": 0,
                }
            )
        )
        assert cfg.chapter_max_level_for_display == 1
        assert cfg.llm_summary_max_level == 1
        assert cfg.llm_summary_per_chapter_pages == 1

    def test_from_form_clamp_upper(self) -> None:
        """大于上限 → clamp."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig.from_form(
            json.dumps(
                {
                    "chapter_max_level_for_display": 99,
                    "llm_summary_max_level": 99,
                    "llm_summary_per_chapter_pages": 99,
                }
            )
        )
        assert cfg.chapter_max_level_for_display == 6
        assert cfg.llm_summary_max_level == 6
        assert cfg.llm_summary_per_chapter_pages == 10

    def test_from_form_wrong_type_uses_default(self) -> None:
        """类型错 (bool/int/str) → 走 default."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig.from_form(
            json.dumps(
                {
                    "enable_llm_refinement": "yes",  # 不是 bool
                    "llm_provider": "claude",  # 不在枚举
                    "chapter_max_level_for_display": "4",  # str 而非 int
                    "llm_summary_per_chapter_pages": True,  # bool 是 int 子类, 排掉
                }
            )
        )
        assert cfg.enable_llm_refinement is False
        assert cfg.llm_provider == "openai"
        assert cfg.chapter_max_level_for_display == 3
        assert cfg.llm_summary_per_chapter_pages == 2

    def test_from_form_invalid_json_raises(self) -> None:
        """非法 JSON → ValueError."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        with pytest.raises(ValueError, match="chapter_config_json JSON 非法"):
            ChapterExtractionConfig.from_form("{not json}")

    def test_from_form_non_object_raises(self) -> None:
        """JSON 不是 object (list/number) → ValueError."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        with pytest.raises(ValueError, match="必须是 JSON object"):
            ChapterExtractionConfig.from_form("[1, 2, 3]")

    def test_from_form_empty_string(self) -> None:
        """空字符串 → 默认."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig.from_form("")
        assert cfg == ChapterExtractionConfig()

    def test_to_dict_roundtrip(self) -> None:
        """to_dict 序列化后 JSON 再 parse 回同样字段."""
        from src.ingest.pre_analysis.chapter_extractors.chapter_config import ChapterExtractionConfig

        cfg = ChapterExtractionConfig(
            enable_llm_refinement=True,
            llm_provider="ollama",
            chapter_max_level_for_display=4,
        )
        d = cfg.to_dict()
        cfg2 = ChapterExtractionConfig.from_form(json.dumps(d))
        assert cfg == cfg2
