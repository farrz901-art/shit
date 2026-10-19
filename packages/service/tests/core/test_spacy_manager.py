"""SpacyManager 测试 (2026-07-09 spaCy 模型加载统一管理 spec).

get_spacy_model 行为契约:
1. 同 model_name 多次请求 → 返同一实例 (functools.lru_cache 命中)
2. 不同 model_name → 分别加载
3. spacy.load 抛 OSError → 包装成 RuntimeError 带安装命令提示

注意: lru_cache 是 module-level 全局状态, 跨 test 污染; 必须用 autouse
fixture 在每个 test 前 cache_clear, 否则上一个 test 缓存的 model_name
会让当前 test 的 mock spacy.load 不触发 (cache hit), 行为不可靠.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_spacy_cache():
    """每个 test 前清 lru_cache, 防跨 test 污染."""
    from src.core.spacy_manager import get_spacy_model

    get_spacy_model.cache_clear()
    yield
    get_spacy_model.cache_clear()


def test_get_spacy_model_returns_cached_instance():
    """同一 model_name 多次请求 → 返回同一实例 (lru_cache 命中)."""
    with patch("src.core.spacy_manager.spacy.load") as mock_load:
        mock_nlp = MagicMock()
        mock_load.return_value = mock_nlp

        from src.core.spacy_manager import get_spacy_model

        nlp1 = get_spacy_model("en_core_web_sm")
        nlp2 = get_spacy_model("en_core_web_sm")

        assert nlp1 is nlp2  # 同一实例
        assert mock_load.call_count == 1  # 只加载 1 次


def test_get_spacy_model_different_models_load_separately():
    """不同 model_name → 分别加载."""
    with patch("src.core.spacy_manager.spacy.load") as mock_load:
        mock_en = MagicMock()
        mock_zh = MagicMock()
        mock_load.side_effect = [mock_en, mock_zh]

        from src.core.spacy_manager import get_spacy_model

        nlp_en = get_spacy_model("en_core_web_sm")
        nlp_zh = get_spacy_model("zh_core_web_sm")

        assert nlp_en is not nlp_zh
        assert mock_load.call_count == 2


def test_get_spacy_model_missing_model_raises_runtime_error():
    """spacy.load 抛 OSError → 包装成 RuntimeError 带安装命令提示."""
    with patch("src.core.spacy_manager.spacy.load") as mock_load:
        mock_load.side_effect = OSError("Can't find model 'en_core_web_sm'")

        from src.core.spacy_manager import get_spacy_model

        with pytest.raises(RuntimeError, match="spaCy 模型.*未安装"):
            get_spacy_model("en_core_web_sm")
