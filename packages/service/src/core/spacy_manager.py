"""进程内统一 spaCy 模型管理 (2026-07-09 spec).

所有模块通过 get_spacy_model() 请求模型, 不自己 spacy.load():
- 同名模型只加载 1 次 (functools.lru_cache)
- 模型名不写死, 由调用方指定
- 缺模型抛 RuntimeError, 统一处理

用法:
    from src.core.spacy_manager import get_spacy_model
    nlp = get_spacy_model("zh_core_web_sm")
"""

from __future__ import annotations

import functools

import spacy


@functools.lru_cache(maxsize=4)
def get_spacy_model(model_name: str):
    """按名返回 spaCy 模型, 按 model_name 缓存.

    Args:
        model_name: spaCy 模型名, 例 "zh_core_web_sm", "en_core_web_sm"

    Returns:
        spacy.Language 实例

    Raises:
        RuntimeError: 模型未安装 / 加载失败, 带安装命令提示
    """
    try:
        return spacy.load(model_name)
    except OSError as e:
        raise RuntimeError(
            f"spaCy 模型 {model_name} 未安装: {e}. 请运行: cd packages/service && uv run spacy download {model_name}"
        ) from e
