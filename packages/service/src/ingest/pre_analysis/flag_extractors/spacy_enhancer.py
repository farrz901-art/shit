"""(2026-07-08 refactor) spaCy 段落增强器.

提取自 runner.py:111-161, 跟 src/kg/router.py:720 的 lazy-load + 透传 RuntimeError
模式一致 (CLAUDE.md §错误处理 "关键依赖失败必须显式").

公开:
  - SpacyEnhancer: 类
  - _ENHANCER: 模块级单例 (测试 monkeypatch 入口)
  - _get_enhancer(): 工厂函数

enhance() 返 3 key dict: lemmas / token_count / language. 不返 sents/ents (spec §4.7).
"""

from __future__ import annotations

from typing import Any

import tiktoken


class SpacyEnhancer:
    """(2026-07-07 v3) spacy 增强器. 进程内单例, lazy init.

    跟 src/kg/router.py:720 同模式: 缺模型抛 RuntimeError, 让 runner 走 mark_failed,
    不静默降级 (CLAUDE.md §错误处理: 关键依赖失败必须显式).

    enhance() 返 3 key: lemmas / token_count / language. 不返 sents/ents (spec §4.7).
    """

    def __init__(self, primary_lang: str = "en") -> None:
        self.primary_lang = primary_lang
        self.nlp: Any = self._load(primary_lang)
        # tiktoken cl100k_base 跟 OpenAI GPT-4 / text-embedding-3-small 对齐
        self.enc: Any = tiktoken.get_encoding("cl100k_base")

    @staticmethod
    def _load(lang: str) -> Any:
        # (2026-07-09) 统一走 core spacy manager, 不再直接 spacy.load()
        from src.core.spacy_manager import get_spacy_model  # noqa: E402

        model_name = f"{lang}_core_web_sm"
        try:
            return get_spacy_model(model_name)
        except RuntimeError as e:
            raise RuntimeError(
                f"spaCy 模型 {model_name} 未加载: {e}. "
                f"请运行: cd packages/service && uv run spacy download {model_name}"
            ) from e

    def enhance(self, text: str) -> dict[str, Any]:
        """对单段文本跑 spacy + tiktoken, 返 3 key 字典."""
        doc = self.nlp(text)
        lemmas = [t.lemma_ for t in doc if not t.is_punct and not t.is_space]
        token_count = len(self.enc.encode(text))
        return {
            "lemmas": lemmas,
            "token_count": token_count,
            "language": self.primary_lang,
        }


# (2026-07-08 final review) enhancer 改 module-level 单例 + _get_enhancer() 工厂:
# - 干掉 frozen dataclass 上的 object.__setattr__ hack (reviewer Important #3)
# - 缺模型抛 RuntimeError 透传, 不 try/except 静默降级 (reviewer Important #4)
# - 测试侧用 monkeypatch.setattr(runner_mod, "_ENHANCER", mock) 注入
# (2026-07-08 refactor) 上述单例搬到 flag_extractors 包, 行为不变.
_ENHANCER: SpacyEnhancer | None = None


def _get_enhancer() -> SpacyEnhancer | None:
    """进程内单例懒加载 SpacyEnhancer. 缺模型 RuntimeError 透传, 让 runner.run 走 mark_failed."""
    global _ENHANCER
    if _ENHANCER is None:
        # 不吞 RuntimeError — spec §4.7 明确要求 "不静默降级"
        _ENHANCER = SpacyEnhancer(primary_lang="en")
    return _ENHANCER
