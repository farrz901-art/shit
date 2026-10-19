# spaCy 模型加载统一管理 plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 抽 `src/core/spacy_manager.py`, 统一管理 spaCy 模型加载, 消除 kg 和 ingest 各自 `spacy.load()` 的重复逻辑.

**Architecture:** 现在 kg/router.py 硬编码 `spacy.load("zh_core_web_sm")`, ingest/spacy_enhancer.py 硬编码 `spacy.load(f"{lang}_core_web_sm")`, 两边各管各的且可能加载同模型 (比如同时用 `en_core_web_sm`). 抽一个中央 manager, 用 `functools.lru_cache` 确保同名模型只加载一次, 错误处理统一为 RuntimeError.

**Tech Stack:** Python 3.14, spaCy 3.8.14, `functools.lru_cache`

---

## 文件映射

| 文件 | 改动类型 |
|------|---------|
| `src/core/spacy_manager.py` | 新建, 统一 get_spacy_model 函数 |
| `src/kg/router.py:713-727` | 改: `import spacy; spacy.load(...)` → `get_spacy_model(...)` |
| `src/ingest/pre_analysis/flag_extractors/spacy_enhancer.py:18,40` | 改: `import spacy; spacy.load(...)` → `get_spacy_model(...)` |
| `tests/core/test_spacy_manager.py` | 新建, 测试 manager 行为 |
| `tests/kg/test_router_extract.py:43-68` | 改: mock 从 `spacy.load` → `get_spacy_model` |
| `tests/ingest/pre_analysis/test_runner.py` (多处) | 改: mock 从 `spacy.load` → `get_spacy_model` |
| `tests/ingest/pre_analysis/conftest.py` | 不改 (只 mock _ENHANCER 单例, 不碰 spacy.load) |

---

### Task 1: 建 `src/core/spacy_manager.py`

**Files:**
- Create: `packages/service/src/core/spacy_manager.py`
- Test: `packages/service/tests/core/test_spacy_manager.py`

- [ ] **Step 1: Write the failing test**

```python
"""SpacyManager 测试"""

from unittest.mock import MagicMock, patch

import pytest


def test_get_spacy_model_returns_cached_instance():
    """同一 model_name 多次请求 → 返回同一实例 (lru_cache 命中)"""
    with patch("src.core.spacy_manager.spacy.load") as mock_load:
        mock_nlp = MagicMock()
        mock_load.return_value = mock_nlp

        from src.core.spacy_manager import get_spacy_model

        nlp1 = get_spacy_model("en_core_web_sm")
        nlp2 = get_spacy_model("en_core_web_sm")

        assert nlp1 is nlp2          # 同一实例
        assert mock_load.call_count == 1  # 只加载 1 次


def test_get_spacy_model_different_models_load_separately():
    """不同 model_name → 分别加载"""
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
    """spacy.load 抛 OSError → 包装成 RuntimeError 带安装提示"""
    with patch("src.core.spacy_manager.spacy.load") as mock_load:
        mock_load.side_effect = OSError("Can't find model 'en_core_web_sm'")

        from src.core.spacy_manager import get_spacy_model

        with pytest.raises(RuntimeError, match="spaCy 模型.*未安装"):
            get_spacy_model("en_core_web_sm")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/service && uv run pytest tests/core/test_spacy_manager.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.spacy_manager'`

- [ ] **Step 3: Write implementation**

```python
"""进程内统一 spaCy 模型管理.

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
            f"spaCy 模型 {model_name} 未安装: {e}. "
            f"请运行: cd packages/service && uv run spacy download {model_name}"
        ) from e
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/service && uv run pytest tests/core/test_spacy_manager.py -v`

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/core/spacy_manager.py packages/service/tests/core/test_spacy_manager.py
git commit -m "feat(core): 统一 spacy 模型加载 get_spacy_model (lru_cache + 统一错误处理)"
```

---

### Task 2: 改 `kg/router.py` 的 `_build_extractor` 用 manager

**Files:**
- Modify: `packages/service/src/kg/router.py:713-727`
- Test: `packages/service/tests/kg/test_router_extract.py:43-68`

- [ ] **Step 1: 改 `_build_extractor` 里的 spacy 加载**

```python
    if extractor_id == "spacy_rule":
        # 重依赖 lazy: spacy 模型加载 ~1s, 非 spacy_rule extractor 路径不需要
        from src.core.spacy_manager import get_spacy_model  # noqa: E402

        try:
            nlp = get_spacy_model("zh_core_web_sm")
        except RuntimeError as e:
            raise HTTPException(
                status_code=503,
                detail=str(e),
            ) from e
        return SpacyRuleExtractor(nlp=nlp)
```

- [ ] **Step 2: 改 test mock**

改 `tests/kg/test_router_extract.py` 行 43-68, 把 mock 从 `spacy.load` 换到 `get_spacy_model`:

```python
def test_build_extractor_spacy_returns_spacy_rule(monkeypatch):
    """[2026-07-03] _build_extractor('spacy_rule') → SpacyRuleExtractor (nlp=<mock>)"""
    from unittest.mock import MagicMock

    from src.kg.extractors.spacy_rule.extractor import SpacyRuleExtractor
    from src.kg.router import _build_extractor

    mock_nlp = MagicMock()
    # mock get_spacy_model 而非 spacy.load
    monkeypatch.setattr("src.core.spacy_manager.get_spacy_model", lambda name: mock_nlp)

    ext = _build_extractor("spacy_rule")
    assert isinstance(ext, SpacyRuleExtractor)
    assert ext.extractor_id == "spacy_rule"
    assert ext.nlp is mock_nlp


def test_build_extractor_spacy_missing_model_raises_503(monkeypatch):
    """[2026-07-03] spacy.load 抛 RuntimeError → HTTPException 503 + 安装命令提示"""
    from fastapi import HTTPException

    from src.kg.router import _build_extractor

    def _fake_get_model(_name: str):
        raise RuntimeError("spaCy 模型 zh_core_web_sm 未安装. 请运行: cd packages/service && uv run spacy download zh_core_web_sm")

    monkeypatch.setattr("src.core.spacy_manager.get_spacy_model", _fake_get_model)

    with pytest.raises(HTTPException) as exc_info:
        _build_extractor("spacy_rule")
    assert exc_info.value.status_code == 503
    assert "zh_core_web_sm" in exc_info.value.detail
    assert "spacy download" in exc_info.value.detail
```

- [ ] **Step 3: 跑测试验证**

Run: `cd packages/service && uv run pytest tests/kg/test_router_extract.py -v`

Expected: 2 个 test PASS (test_build_extractor_spacy_returns_spacy_rule, test_build_extractor_spacy_missing_model_raises_503) + 其他 test PASS

- [ ] **Step 4: Commit**

```bash
git add packages/service/src/kg/router.py packages/service/tests/kg/test_router_extract.py
git commit -m "refactor(kg): router 的 spacy.load → get_spacy_model"
```

---

### Task 3: 改 `ingest/spacy_enhancer.py` 用 manager

**Files:**
- Modify: `packages/service/src/ingest/pre_analysis/flag_extractors/spacy_enhancer.py:18,40`
- Test: (已有 test 不改, 只验证不炸)

- [ ] **Step 1: 改 spacy_enhancer.py**

行 18: 删 `import spacy`
行 38-45: `_load` 方法调用 `get_spacy_model`:

```python
from __future__ import annotations

from typing import Any

import tiktoken


class SpacyEnhancer:
    """(2026-07-07 v3) spacy 增强器. 进程内单例, lazy init.

    enhance() 返 3 key: lemmas / token_count / language. 不返 sents/ents.
    """

    def __init__(self, primary_lang: str = "en") -> None:
        self.primary_lang = primary_lang
        self.nlp: Any = self._load(primary_lang)
        self.enc: Any = tiktoken.get_encoding("cl100k_base")

    @staticmethod
    def _load(lang: str) -> Any:
        # (2026-07-09) 统一走 core spacy manager, 不走直接 spacy.load()
        from src.core.spacy_manager import get_spacy_model  # noqa: E402

        model_name = f"{lang}_core_web_sm"
        try:
            return get_spacy_model(model_name)
        except RuntimeError as e:
            raise RuntimeError(
                f"spaCy 模型 {model_name} 未加载: {e}. "
                f"请运行: cd packages/service && uv run spacy download {model_name}"
            ) from e
```

- [ ] **Step 2: 跑测试验证**

Run: `cd packages/service && uv run pytest tests/ingest/pre_analysis/ -q --tb=short -x`

Expected: 全部 PASS (已有 test 全 mock 了 _ENHANCER 单例, `_load` 路径只在 T21 test 测试新 `SpacyEnhancer()` 构造时才真调)

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/ingest/pre_analysis/flag_extractors/spacy_enhancer.py
git commit -m "refactor(ingest): spacy_enhancer 的 spacy.load → get_spacy_model"
```

---

### Task 4: 清理残留 mock 路径 (可选验证)

确认全局无其他直接 mock `spacy.load` 的残留:

- [ ] **Step 1: 搜索 `spacy.load` 引用**

```bash
cd packages/service && grep -rn "spacy\.load" src/ tests/ --include="*.py"
```

Expected: 0 条 (全被 get_spacy_model 替代)

- [ ] **Step 2: 跑全量测试验证不炸**

Run: `cd packages/service && uv run pytest -q`

Expected: 跟 baseline 一致 (当前 ~1075 PASS / 22 fail + 38 errors pre-existing), 不出现新 fail.

---

## 自检清单

**1. Spec 覆盖:**
- [x] `src/core/spacy_manager.py` 新建 + lru_cache (Task 1)
- [x] kg/router.py 改用 manager (Task 2)
- [x] ingest/spacy_enhancer.py 改用 manager (Task 3)
- [x] 测试 mock 从 `spacy.load` 换到 `get_spacy_model` (Task 2 Step 2)
- [x] 无残留直接 `spacy.load` (Task 4)

**2. 无占位符:** 所有代码完整, 无 "TODO".

**3. 类型一致性:**
- `get_spacy_model(model_name: str) → spacy.Language` — 返回值跟原 `spacy.load` 一致
- kg 侧用 try/except RuntimeError 转 HTTPException 503, 行为不变
- ingest 侧已 try/except RuntimeError 转 RuntimeError, 行为不变 (抛出的异常类型没变)
