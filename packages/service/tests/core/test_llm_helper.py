"""(2026-07-09) trim_repeated_header 测试 (sync 版本).

mock OpenAI/Ollama 客户端避免真调 LLM, 验证:
1. is_repeated=True → 返 (True, rows_to_skip)
2. is_repeated=False → 返 (False, 0)
3. invalid JSON → 抛 LLMParsingError
4. LLM 客户端不可用 → 抛 LLMUnavailableError
5. LRU cache 命中 → 第二次不调 LLM
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_trim_repeated_header_is_repeated_true() -> None:
    """LLM 返 is_repeated=true, rows_to_skip=2 → 返 (True, 2)."""
    from src.core.llm_helper import trim_repeated_header

    prev_rows = [["Name", "Type"], ["Motor 1", "A"]]
    curr_rows = [["Name", "Type"], ["Motor 2", "B"]]  # 重复 header

    # mock src.generation.llm.LocalLLM.llm.invoke 返 AIMessage
    fake_llm = MagicMock()
    fake_llm.invoke.return_value.content = '{"is_repeated": true, "rows_to_skip": 2}'

    with patch("src.core.llm_helper._get_llm_client", return_value=fake_llm):
        result = trim_repeated_header(prev_rows, curr_rows)

    assert result == (True, 2)


def test_trim_repeated_header_is_repeated_false() -> None:
    """LLM 返 is_repeated=false → 返 (False, 0)."""
    from src.core.llm_helper import trim_repeated_header

    prev_rows = [["Name", "Type"], ["Motor 1", "A"]]
    curr_rows = [["Selection table continued", ""], ["Name", "Type"], ["Motor 2", "B"]]

    fake_llm = MagicMock()
    fake_llm.invoke.return_value.content = '{"is_repeated": false, "rows_to_skip": 0}'

    with patch("src.core.llm_helper._get_llm_client", return_value=fake_llm):
        result = trim_repeated_header(prev_rows, curr_rows)

    assert result == (False, 0)


def test_trim_repeated_header_invalid_json_raises() -> None:
    """LLM 返 invalid JSON → 抛 LLMParsingError."""
    from src.core.errors import LLMParsingError
    from src.core.llm_helper import trim_repeated_header

    fake_llm = MagicMock()
    fake_llm.invoke.return_value.content = "not a json"

    with patch("src.core.llm_helper._get_llm_client", return_value=fake_llm):
        with pytest.raises(LLMParsingError):
            trim_repeated_header([["a"]], [["b"]])


def test_trim_repeated_header_llm_unavailable_raises() -> None:
    """_get_llm_client 抛 LLMUnavailableError → 透传."""
    from src.core.errors import LLMUnavailableError
    from src.core.llm_helper import trim_repeated_header

    with patch(
        "src.core.llm_helper._get_llm_client",
        side_effect=LLMUnavailableError("no key", backend="openai"),
    ):
        with pytest.raises(LLMUnavailableError):
            trim_repeated_header([["a"]], [["b"]])


def test_trim_repeated_header_lru_cache_hit() -> None:
    """相同 prev_rows + curr_rows 第二次调用 → 不再调 LLM (LRU cache 命中)."""
    from src.core.llm_helper import trim_repeated_header

    fake_llm = MagicMock()
    fake_llm.invoke.return_value.content = '{"is_repeated": true, "rows_to_skip": 1}'

    prev_rows = [["a"]]
    curr_rows = [["a"], ["b"]]

    with patch("src.core.llm_helper._get_llm_client", return_value=fake_llm) as mock_get:
        # 第一次调
        r1 = trim_repeated_header(prev_rows, curr_rows, page_a=1, page_b=2)
        # 第二次调相同输入
        r2 = trim_repeated_header(prev_rows, curr_rows, page_a=1, page_b=2)
        # LLM 只应被 invoke 1 次
        assert fake_llm.invoke.call_count == 1, f"LRU cache 应命中, 实际 LLM 被调 {fake_llm.invoke.call_count} 次"
        assert r1 == r2
        # _get_llm_client 也只调 1 次 (LRU 在外面包的)
        assert mock_get.call_count == 1
