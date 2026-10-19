"""pre_analysis 测试目录 conftest.

(2026-07-08 refactor) 集成测试 (跑真 PDF) 隐性依赖 enhancer 在缺模型时不报错.
(2026-07-08 final review) spacy 缺模型抛 RuntimeError 透传, 集成测试 (7 个用真 d81_dummy.pdf 的)
会全红. 本 conftest 提供 autouse fixture, 默认给 flag_extractors 的 _ENHANCER 单例注 no-op MagicMock:

- 单测显式 monkeypatch.setattr(enhancer_mod, "_ENHANCER", xxx) 会覆盖本 fixture
- 集成测试跑真 PDF 时也用 mock enhancer, 不再触发 spacy 真实加载
- T21 test_spacy_enhancer_missing_model_raises_runtime_error 直接验 SpacyEnhancer 类构造,
  不会受本 fixture 影响 (它测的是类本身, 不走 _get_enhancer 路径)

(2026-07-08 flag_extractors 拆分) _ENHANCER 单例跟着搬到
src.ingest.pre_analysis.flag_extractors.spacy_enhancer, monkeypatch 入口必须
指向新模块, 否则 _get_enhancer() 找不到 mock 会真去加载 spaCy 模型.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_default_enhancer(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认 mock flag_extractors._ENHANCER → 返空 lemmas, 避免集成测试触发 spaCy 真实加载."""
    from src.ingest.pre_analysis.flag_extractors import spacy_enhancer as enhancer_mod

    default_enhancer = MagicMock()
    default_enhancer.enhance.return_value = {"lemmas": [], "token_count": 0, "language": "unknown"}
    monkeypatch.setattr(enhancer_mod, "_ENHANCER", default_enhancer)
