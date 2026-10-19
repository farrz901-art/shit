# Splitters → Chunkers 重构计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `src/kg/splitters/`（Markdown 文本切片器）不删逻辑搬到 `src/ingest/chunkers/`, KG 及其他模块引用新路径.

**架构:** KG 现在有 3 个 splitter（heading / semantic / token）和一个 `TextChunk` 基类, 纯粹做文本切片, 跟 Neo4j / schema / client 零耦合. 搬入 `src/ingest/chunkers/` 后, `ingest/` 下有完整的文档结构化流水线: PDF 转 Markdown → 切 chunks → 后续分析, 同时对外保持 `from ingest.chunkers import ...` 统一入口.

**Tech Stack:** Python 3.14, 仅搬文件改 import, 无新依赖.

---

## 文件映射

| 当前位置 | 目标位置 | 改动类型 |
|---------|---------|---------|
| `src/kg/splitters/base.py` | `src/ingest/chunkers/base.py` | 搬 (不改逻辑) |
| `src/kg/splitters/heading.py` | `src/ingest/chunkers/heading.py` | 搬 (不改逻辑) |
| `src/kg/splitters/semantic.py` | `src/ingest/chunkers/semantic.py` | 搬 (不改逻辑) |
| `src/kg/splitters/token.py` | `src/ingest/chunkers/token.py` | 搬 (不改逻辑) |
| `src/kg/splitters/__init__.py` | (删) | 删空文件 |
| (新建) | `src/ingest/chunkers/__init__.py` | 新建, 重导出 |
| `src/kg/router.py:37-39` | 改 import | `from .splitters.xxx` → `from src.ingest.chunkers.xxx` |
| `src/ingest/__init__.py` | 加 chunkers 行 | 公开 API 加一行注释/导出 |
| `tests/kg/splitters/test_heading.py` | `tests/ingest/chunkers/test_heading.py` | 搬 + 改 import |
| `tests/kg/splitters/test_semantic.py` | `tests/ingest/chunkers/test_semantic.py` | 搬 + 改 import |
| `tests/kg/splitters/test_token.py` | `tests/ingest/chunkers/test_token.py` | 搬 + 改 import |
| `tests/kg/test_extract_runner.py` | 改 import 路径 | `from src.kg.splitters.base` → `from src.ingest.chunkers.base` |
| `tests/kg/extractors/spacy_rule/test_extractor.py` | 改 import 路径 | 同上 |
| `tests/kg/extractors/llm_pydantic/test_extractor.py` | 改 import 路径 | 同上 |

---

### Task 1: 建 `src/ingest/chunkers/` 目录 + 搬 4 个源文件

⚠️ 不删老文件, 只并行创建新文件, 让新旧并存确保 import 不出死.

**Files:**
- Create: `packages/service/src/ingest/chunkers/__init__.py`
- Create: `packages/service/src/ingest/chunkers/base.py`
- Create: `packages/service/src/ingest/chunkers/heading.py`
- Create: `packages/service/src/ingest/chunkers/semantic.py`
- Create: `packages/service/src/ingest/chunkers/token.py`

- [ ] **Step 1: 建目录**

```bash
mkdir -p packages/service/src/ingest/chunkers
```

- [ ] **Step 2: Write `src/ingest/chunkers/__init__.py`**

```python
"""(2026-07-09) Markdown 文本切片器

从 src/kg/splitters/ 搬来. 纯文本切片, 不依赖 kg/ingest 其他模块.
kg / 后续 RAG 等模块均可引用.

用法:
    from ingest.chunkers import HeadingSplitter, TokenSplitter, SemanticSplitter
    from ingest.chunkers.base import TextChunk, BaseSplitter
"""

from .base import BaseSplitter, TextChunk, _make_chunk_id
from .heading import HeadingSplitter
from .semantic import SemanticSplitter
from .token import TokenSplitter

__all__ = [
    "BaseSplitter",
    "TextChunk",
    "HeadingSplitter",
    "SemanticSplitter",
    "TokenSplitter",
    "_make_chunk_id",
]
```

- [ ] **Step 3: 复制 4 个源文件 (内容不变, 只改 import 路径)**

复制 `src/kg/splitters/base.py` → `src/ingest/chunkers/base.py`, 改行 13:

```python
# 改前:
from .base import TextChunk, _make_chunk_id
# 改成:
from . import TextChunk, _make_chunk_id
# heading, semantic, token 各自改 .base → . 或 from .base import ...
```

具体改法:

**`src/ingest/chunkers/base.py`** — 原样复制, 无 import 依赖.

**`src/ingest/chunkers/heading.py`** — 改行 13:
```python
# 改前:
from .base import TextChunk, _make_chunk_id
# 改后:
from . import TextChunk, _make_chunk_id
```

**`src/ingest/chunkers/semantic.py`** — 改行 18-19:
```python
# 改前:
from .base import TextChunk, _make_chunk_id
from .heading import HeadingSplitter
# 改后:
from . import TextChunk, _make_chunk_id
from .heading import HeadingSplitter
```

**`src/ingest/chunkers/token.py`** — 改行 11:
```python
# 改前:
from .base import TextChunk, _make_chunk_id
# 改后:
from . import TextChunk, _make_chunk_id
```

- [ ] **Step 4: 验证 import 在新位置能通**

Run:
```bash
cd packages/service && uv run python -c "
from ingest.chunkers import HeadingSplitter, SemanticSplitter, TokenSplitter, TextChunk
from ingest.chunkers import _make_chunk_id
print('HeadingSplitter' in dir())
assert _make_chunk_id('hello', 'u', 0)
assert len(_make_chunk_id('hello', 'u', 0)) == 12
print('OK: chunkers import 通')
"
```

Expected: 不抛 ImportError, 打印 "OK: chunkers import 通".

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/ingest/chunkers/
git commit -m "feat(chunkers): 新建 src/ingest/chunkers/ 目录, 4 文件原样复制自 kg/splitters"
```

---

### Task 2: 改 `src/kg/router.py` import 指向新路径

**Files:**
- Modify: `packages/service/src/kg/router.py:37-39`

- [ ] **Step 1: 改 import**

```python
# 改前:
from .splitters.heading import HeadingSplitter
from .splitters.semantic import SemanticSplitter
from .splitters.token import TokenSplitter

# 改后:
from src.ingest.chunkers import HeadingSplitter, SemanticSplitter, TokenSplitter
```

- [ ] **Step 2: 验证 import + router 启动不炸**

Run:
```bash
cd packages/service && uv run python -c "from src.kg.router import router; print('router OK:', type(router).__name__)"
```

Expected: 打印 "router OK: APIRouter".

- [ ] **Step 3: Commit**

```bash
git add packages/service/src/kg/router.py
git commit -m "refactor(kg): router import splitters → ingest.chunkers"
```

---

### Task 3: 更新 `ingest/__init__.py` 公开 chunkers

**Files:**
- Modify: `packages/service/src/ingest/__init__.py`

- [ ] **Step 1: 加 chunkers 导出**

```python
# 在 .pre_analysis import 下方加一行:
from . import chunkers  # noqa: F401  # (2026-07-09) Markdown 文本切片器, kg/RAG 引用入口
```

- [ ] **Step 2: Commit**

```bash
git add packages/service/src/ingest/__init__.py
git commit -m "docs(ingest): __init__.py 加 chunkers 引用注释"
```

---

### Task 4: 搬 3 个 splitter 测试到 `tests/ingest/chunkers/`

**Files:**
- Create: `packages/service/tests/ingest/chunkers/test_heading.py`
- Create: `packages/service/tests/ingest/chunkers/test_semantic.py`
- Create: `packages/service/tests/ingest/chunkers/test_token.py`
- Delete: `packages/service/tests/kg/splitters/`

- [ ] **Step 1: 写 `tests/ingest/chunkers/test_heading.py`**

复制自 `tests/kg/splitters/test_heading.py`, 改 import:

```python
"""HeadingSplitter 测试"""

from src.ingest.chunkers import HeadingSplitter, TextChunk, _make_chunk_id


def test_heading_top_level():
    """### 级 heading → 切成 1 个 chunk"""
    chunks = HeadingSplitter().split("### Hello", "test://doc.md")
    assert len(chunks) == 1
    assert "Hello" in chunks[0].text


def test_heading_splits_into_two():
    """2 个 ## → 切 2 个 chunk"""
    text = "## H1\ncontent1\n## H2\ncontent2"
    chunks = HeadingSplitter().split(text, "test://doc.md")
    assert len(chunks) == 2
    assert chunks[0].text.startswith("## H1")
    assert chunks[1].text.startswith("## H2")
    assert "content1" in chunks[0].text


def test_heading_path_builds_correctly():
    """H2 under H1 → heading_path 含 H1+H2"""
    text = "# Title\n## Sub\ncontent"
    chunks = HeadingSplitter().split(text, "test://doc.md")
    sub = [c for c in chunks if "Sub" in c.text][0]
    assert "Title" in sub.meta.get("heading_path", [])


def test_heading_deterministic_ids():
    """相同输入 → 相同 chunk_id"""
    text = "## A\nx\n## B\ny"
    c1 = HeadingSplitter().split(text, "test://doc.md")
    c2 = HeadingSplitter().split(text, "test://doc.md")
    for a, b in zip(c1, c2):
        assert a.chunk_id == b.chunk_id
```

- [ ] **Step 2: 写 `tests/ingest/chunkers/test_semantic.py`**

```python
"""SemanticSplitter 测试"""

from src.ingest.chunkers import SemanticSplitter, TextChunk


class _MockEmbedder:
    def __init__(self):
        self._alternating = 0

    def embed_batch(self, texts):
        """返回模拟向量: 偶句 [1,0], 奇句 [0,1] → cosine=0 → 必切分"""
        return [[1.0, 0.0] if i % 2 == 0 else [0.0, 1.0] for i in range(len(texts))]


def _assert_key_text(chunks: list[TextChunk], text: str):
    """断言至少有一个 chunk 包含指定文本片段"""
    assert any(text in c.text for c in chunks), f"chunks 中未找到包含 {text!r} 的片段"


def test_semantic_splits_by_cosine():
    """cosine=0 的句对 → 切开"""
    embedder = _MockEmbedder()
    text = "句A。句B。"
    chunks = SemanticSplitter(embedder=embedder, cosine_threshold=0.5, min_chunk_size=2).split(text, "test://doc.md")
    assert len(chunks) >= 2


def test_semantic_fallback_on_embedder_error():
    """[M3] embedder 抛错 → 降级到 HeadingSplitter"""
    class _BrokenEmbedder:
        def embed_batch(self, texts):
            raise RuntimeError("mock embedder crash")

    text = "# Title\ncontent"
    chunks = SemanticSplitter(embedder=_BrokenEmbedder(), cosine_threshold=0.5).split(text, "test://doc.md")
    assert len(chunks) == 1
    assert "Title" in chunks[0].text


def test_semantic_merges_similar_sentences():
    """cosine=1 的句对 → 合并"""
    class _SameVecEmbedder:
        def embed_batch(self, texts):
            return [[1.0, 0.0]] * len(texts)

    text = "A。B。C。"
    chunks = SemanticSplitter(embedder=_SameVecEmbedder(), cosine_threshold=0.5, min_chunk_size=2).split(text, "test://doc.md")
    assert len(chunks) <= 2


def test_semantic_deterministic():
    """相同输入 → 相同 chunk_id (同输入同输出)"""
    embedder = _MockEmbedder()
    text = "X。Y。"
    c1 = SemanticSplitter(embedder=embedder, cosine_threshold=0.5).split(text, "test://doc.md")
    c2 = SemanticSplitter(embedder=embedder, cosine_threshold=0.5).split(text, "test://doc.md")
    assert len(c1) == len(c2)
    for a, b in zip(c1, c2):
        assert a.chunk_id == b.chunk_id
```

- [ ] **Step 3: 写 `tests/ingest/chunkers/test_token.py`**

```python
"""TokenSplitter 测试"""

import pytest
from src.ingest.chunkers import TokenSplitter, TextChunk


def test_token_splits_basic_text():
    """简单文本 → 切 chunks"""
    text = "hello world " * 50
    chunks = TokenSplitter(chunk_size=128, overlap=16).split(text, "test://doc.md")
    assert len(chunks) >= 2
    assert all(isinstance(c, TextChunk) for c in chunks)


def test_token_overlap_preserved():
    """overlap > 0 → 相邻 chunk 有重叠文本"""
    text = "word " * 20
    chunks = TokenSplitter(chunk_size=64, overlap=8).split(text, "test://doc.md")
    assert len(chunks) >= 2
    # 相邻 chunk 应该有重叠: 前一个 chunk 末尾 == 后一个 chunk 开头
    overlap_found = any(
        chunks[i].text.split()[-2:] == chunks[i + 1].text.split()[:2]
        for i in range(len(chunks) - 1)
    )
    assert overlap_found, "overlap 应该让相邻 chunk 有重叠"


def test_token_empty_input():
    """空文本 → 空 list"""
    chunks = TokenSplitter(chunk_size=128).split("", "test://doc.md")
    assert chunks == []


def test_token_short_text():
    """文本短于 chunk_size → 1 个 chunk"""
    text = "short text"
    chunks = TokenSplitter(chunk_size=128).split(text, "test://doc.md")
    assert len(chunks) == 1


def test_token_overlap_must_be_less_than_chunk_size():
    """overlap >= chunk_size → ValueError"""
    with pytest.raises(ValueError):
        TokenSplitter(chunk_size=64, overlap=64)
    with pytest.raises(ValueError):
        TokenSplitter(chunk_size=64, overlap=100)
```

- [ ] **Step 4: 删旧测试目录**

```bash
rm -rf packages/service/tests/kg/splitters
```

- [ ] **Step 5: 跑新测试全绿**

Run:
```bash
cd packages/service && uv run pytest tests/ingest/chunkers/ -v
```

Expected: 3 文件 × ~4 test 每个 = 12+ PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/service/tests/ingest/chunkers/ && git rm -r packages/service/tests/kg/splitters/
git commit -m "refactor(chunkers): 搬 3 个 splitter 测试到 tests/ingest/chunkers/, 删旧目录"
```

---

### Task 5: 改 3 个非 splitter 测试的 import 路径

**Files:**
- Modify: `packages/service/tests/kg/test_extract_runner.py:9`
- Modify: `packages/service/tests/kg/extractors/spacy_rule/test_extractor.py:6`
- Modify: `packages/service/tests/kg/extractors/llm_pydantic/test_extractor.py:7`

这 3 个文件 import `TextChunk` 用于构造 mock chunk 测试数据, 实际逻辑不变.

- [ ] **Step 1: 改 `tests/kg/test_extract_runner.py:9`**

```python
# 改前:
from src.kg.splitters.base import TextChunk
# 改后:
from src.ingest.chunkers import TextChunk
```

- [ ] **Step 2: 改 `tests/kg/extractors/spacy_rule/test_extractor.py:6`**

```python
# 改前:
from src.kg.splitters.base import TextChunk
# 改后:
from src.ingest.chunkers import TextChunk
```

- [ ] **Step 3: 改 `tests/kg/extractors/llm_pydantic/test_extractor.py:7`**

```python
# 改前:
from src.kg.splitters.base import TextChunk
# 改后:
from src.ingest.chunkers import TextChunk
```

- [ ] **Step 4: 跑这 3 个测试确认绿**

Run:
```bash
cd packages/service && uv run pytest tests/kg/test_extract_runner.py tests/kg/extractors/spacy_rule/test_extractor.py tests/kg/extractors/llm_pydantic/test_extractor.py -v
```

Expected: 全 PASS (跟搬前一样).

- [ ] **Step 5: Commit**

```bash
git add packages/service/tests/kg/test_extract_runner.py packages/service/tests/kg/extractors/spacy_rule/test_extractor.py packages/service/tests/kg/extractors/llm_pydantic/test_extractor.py
git commit -m "refactor(test): 3 个测试 TextChunk import 指向 src.ingest.chunkers"
```

---

### Task 6: 删 `src/kg/splitters/` 完整目录

确认无其他引用后删除.

- [ ] **Step 1: 确认 src 下无其他 import**

Run:
```bash
cd packages/service && grep -r "kg.splitters" src/ || echo "无残留引用"
```

Expected: "无残留引用".

- [ ] **Step 2: 删目录**

```bash
rm -rf packages/service/src/kg/splitters
```

- [ ] **Step 3: 跑全量测试确认不炸**

Run:
```bash
cd packages/service && uv run pytest tests/ingest/chunkers/ tests/kg/ -q
```

Expected: 全 PASS (chunkers 12+ tests + kg 全套 tests).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor(kg): 删 src/kg/splitters/ (已搬至 ingest/chunkers)"
```

---

## 自检清单

**1. Spec 覆盖:**
- [x] 4 个源文件搬至 `ingest/chunkers/` (Task 1)
- [x] `TextChunk` 和 `BaseSplitter` 在新位置可用 (Task 1 Step 4)
- [x] `kg/router.py` import 改新路径 (Task 2)
- [x] 3 个 test 文件搬至 `tests/ingest/chunkers/` + import 更新 (Task 4)
- [x] 3 个 kg 测试改 import (Task 5)
- [x] 删旧目录 (Task 6)
- [x] `ingest/__init__.py` 加 chunkers 注释 (Task 3)

**2. 无占位符:** 所有代码完整, 无 "TODO" / "fix later".

**3. 类型一致性:** `TextChunk` / `HeadingSplitter` / `SemanticSplitter` / `TokenSplitter` 在新旧位置签名一致.
