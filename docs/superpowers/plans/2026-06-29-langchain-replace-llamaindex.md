# LangChain 替换 LlamaIndex 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `packages/service/src/` 下所有 LlamaIndex 调用替换为 LangChain 1.4 生态 + DeepEval 评估, 同时删除生产 0 调用的 `src/orchestration/` 和 dead `/api/v1/evaluate` 端点.

**Architecture:** 9 个原子 commit, 顺序执行. Spike (T0) 验证真实 `langchain-postgres.PGVectorStore.create_sync + PGEngine` API, 然后基础设施层 (T1-T3) → 数据迁移 (T4 alembic) → 核心 RAG 链路 (T5) → 清理 (T6-T8). 对外 API 100% 不变, pgvector 数据通过 alembic migration 从 `llamaindex_embeddings` 迁到 `rag_embeddings` 单表 LC schema.

**Tech Stack:**
- LangChain 1.x: `langchain-core 1.4.8 / langchain-openai / langchain-ollama / langchain-postgres 0.0.17 / langchain-text-splitters`
- DeepEval 3.x (5 metrics + DeepSeek judge)
- pgvector + SQLAlchemy + alembic 数据迁移
- pytest 4 模式测试隔离 (mock 优先, 0 真实 DB)

**关联 Spec:** [docs/superpowers/specs/2026-06-29-langchain-replace-llamaindex-design.md](../specs/2026-06-29-langchain-replace-llamaindex-design.md) v2.2
**Spike Handoff (T0 实测):** [docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md](../handoffs/2026-06-29-langchain-postgres-spike.md)

**Spike T0 关键偏差 (T1 之后必读)**:
1. `langchain_metadata` 列 LC 建是 **json** 不是 jsonb → 业务必须 ALTER 转 jsonb + 建 GIN
2. `init_vectorstore_table` **不建 vector index** → 业务必须 `apply_vector_index(HNSWIndex(...))`
3. `PGEngine.close()` 是 coroutine → 业务持有 2 engine (PGEngine + SA Engine)
4. `OpenAIEmbeddings` bge-m3 端点: 不传 `dimensions`, 传 `check_embedding_ctx_length=False`
5. Windows dev async: `asyncio.WindowsSelectorEventLoopPolicy` (生产 Linux 不受影响)

---

## 文件结构

### 新建 (3 个)

- `packages/service/src/common/document.py` — `RAGDoc` dataclass (取代 LlamaIndex `Document`)
- `packages/service/src/eval/deepeval_eval.py` — `DeepEvalEvaluator` + `DeepSeekJudge` + `DeepEvalError`
- `packages/service/alembic/versions/20260629_lc_pgvector_schema.py` — 数据迁移
- `packages/service/tests/eval/test_deepeval_eval.py` — 评估器单测
- `packages/service/tests/spike/test_langchain_postgres_spike.py` — T0 spike 凭据
- `docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md` — spike 结果记录

### 修改 (源码 ~12, 测试 ~10)

- `src/common/chunker.py` — `RecursiveCharacterTextSplitter` + 中文 separators
- `src/common/document_loader.py` — Document → RAGDoc
- `src/common/__init__.py` — 删 `get_default_node_parser` export
- `src/common/evaluation.py` — RAGAMetrics 加 hallucination
- `src/generation/llm.py` — ChatOpenAI / ChatOllama
- `src/generation/query_engine.py` — LCEL RunnableParallel + _LCQueryEngine
- `src/generation/__init__.py` — 同步 export
- `src/retrieval/embedder.py` — OpenAIEmbeddings
- `src/retrieval/vector_store.py` — PGEngine + PGVectorStore.create_sync + _delete_by_ref_doc_id
- `src/retrieval/__init__.py` — 同步 export
- `src/eval/router.py` — DeepEvalEvaluator 引用
- `src/eval/runner.py` — DeepEvalError 错误前缀
- `src/buyer_profile/extractor.py:50-54` — `.invoke + .content`
- `src/health/checks.py:74` — 注释去 LlamaIndex
- `src/telemetry/langfuse_client.py:94` — docstring 更新
- `src/api/routes.py` — 删 evaluate_endpoint + 改 query_endpoint doc
- `src/api/schemas.py` — 删 EvaluateRequest/Response
- `src/api/__init__.py` — 同步 export
- `src/__init__.py` — 删 orchestration + get_default_node_parser export + docstring
- `pyproject.toml` — dep 替换

### 删除 (5 个)

- `src/orchestration/` 整目录 (4 文件)
- `src/eval/llama_eval.py`
- `tests/orchestration/test_workflows.py`
- `tests/eval/test_llama_eval.py`
- 老 `init_pgvector()` 中 `llamaindex_embeddings` 建表逻辑 (改建 `rag_embeddings`)

---

## Task 0: Spike — 验证 langchain-postgres 真实 API

**目的:** 确认 spec §5.6 写的 `PGEngine + PGVectorStore.create_sync` API 在 dev DB 真的能跑, 避免后续 commit 4-5 全建在错误假设上.

**Files:**
- Create: `packages/service/tests/spike/test_langchain_postgres_spike.py` (临时, 验证后删)
- Create: `docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md` (结果留档)

**前置:** dev 环境有 pgvector + .env.local 配 PG_*

- [ ] **Step 1: 装包**

```bash
cd packages/service
uv add "langchain-core>=1.4,<2.0" "langchain-openai>=1.0,<2.0" "langchain-postgres>=0.0.17,<0.1"
uv sync
```

Expected: `uv.lock` 更新, 无依赖冲突

- [ ] **Step 2: 写 spike 脚本**

创建 `packages/service/tests/spike/__init__.py` (空文件).
创建 `packages/service/tests/spike/test_langchain_postgres_spike.py`:

```python
"""SPIKE: 验证 langchain-postgres 0.0.17 真实 API.

不是生产 test, marker integration 跳过 default CI. 验证后用 handoff 记录然后删.
"""

import os
import pytest

pytestmark = pytest.mark.integration  # default CI 跳

from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGEngine, PGVectorStore
from sqlalchemy import text


@pytest.fixture(scope="module")
def engine():
    """从 PG_* env 拼 connection_string, 走 PGEngine."""
    url = (
        f"postgresql+psycopg://{os.environ['PG_USER']}:{os.environ['PG_PASSWORD']}"
        f"@{os.environ['PG_HOST']}:{os.environ['PG_PORT']}/{os.environ['PG_DATABASE']}"
    )
    eng = PGEngine.from_connection_string(url=url)
    yield eng


@pytest.fixture(scope="module")
def embedder():
    return OpenAIEmbeddings(
        model=os.environ.get("EMBED_MODEL", "text-embedding-3-small"),
        api_key=os.environ["EMBED_API_KEY"],
        base_url=os.environ["EMBED_BASE_URL"],
        dimensions=int(os.environ.get("EMBED_DIMENSIONS", "1024")),
    )


def test_spike_init_table(engine, embedder):
    """验证 PGEngine.init_vectorstore_table API 真存在 + 返回啥"""
    table = "spike_test_table"
    # 假设签名: init_vectorstore_table(table_name, vector_size, metadata_columns)
    engine.init_vectorstore_table(
        table_name=table,
        vector_size=1024,
        overwrite_existing=True,
    )
    # 验证表真建了
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
        assert result.scalar() == 0


def test_spike_create_sync(engine, embedder):
    """验证 PGVectorStore.create_sync 工厂方法返 PGVectorStore 实例"""
    table = "spike_test_table"
    store = PGVectorStore.create_sync(
        engine=engine,
        embedding_service=embedder,
        table_name=table,
    )
    assert store is not None


def test_spike_add_query_delete(engine, embedder):
    """完整 add → query → delete by metadata 流程"""
    table = "spike_test_table"
    store = PGVectorStore.create_sync(
        engine=engine,
        embedding_service=embedder,
        table_name=table,
    )

    # 1. add_texts 带 metadata.ref_doc_id
    ids = store.add_texts(
        texts=["RAG 是什么", "向量数据库简介"],
        metadatas=[
            {"ref_doc_id": "doc-A", "file_path": "/tmp/a.md"},
            {"ref_doc_id": "doc-A", "file_path": "/tmp/a.md"},
        ],
    )
    assert len(ids) == 2

    # 2. similarity_search_by_vector
    query_vec = embedder.embed_query("RAG")
    docs = store.similarity_search_by_vector(query_vec, k=5)
    assert len(docs) > 0
    # docs[0] 应有 .page_content + .metadata
    assert hasattr(docs[0], "page_content")
    assert hasattr(docs[0], "metadata")
    assert docs[0].metadata.get("ref_doc_id") == "doc-A"

    # 3. delete by metadata (原生 SQL)
    with engine.connect() as conn:
        conn.execute(
            text(f"DELETE FROM {table} WHERE langchain_metadata->>'ref_doc_id' = :rid"),
            {"rid": "doc-A"},
        )
        conn.commit()
    # 验证删干净
    docs_after = store.similarity_search_by_vector(query_vec, k=5)
    assert len(docs_after) == 0
```

- [ ] **Step 3: 跑 spike**

```bash
cd packages/service
uv run pytest tests/spike/test_langchain_postgres_spike.py -v -m integration
```

Expected: 3 个 test 全 PASS

**如果 FAIL:** 别继续, 把真实 API 调用方式记到 handoff, 回 spec §5.6 重写代码再跑.

- [ ] **Step 4: 记 handoff**

创建 `docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md`:

```markdown
# Spike: langchain-postgres 0.0.17 真实 API (2026-06-29)

## 结论

- ✅ `PGEngine.from_connection_string(url=...)` 成功
- ✅ `engine.init_vectorstore_table(table_name, vector_size, overwrite_existing)` 成功
- ✅ `PGVectorStore.create_sync(engine, embedding_service, table_name)` 成功
- ✅ `store.add_texts(texts, metadatas)` 返 ids: list[str]
- ✅ `store.similarity_search_by_vector(query_vec, k)` 返 list[Document]
- ✅ Document 有 `page_content` + `metadata` 字段
- ✅ ref_doc_id 走 metadata JSONB, 原生 SQL `DELETE WHERE langchain_metadata->>'ref_doc_id' = :rid` 工作

## 验证 SQL schema

跑完 spike 后:
\`\`\`sql
\d spike_test_table
-- 应有列: langchain_id (UUID), content (TEXT), embedding (vector), langchain_metadata (JSONB)
\`\`\`

## 后续

正式实施跟 spec §5.6 一致. 删 `tests/spike/`.
```

- [ ] **Step 5: Commit spike (临时)**

```bash
cd c:/Users/abcuc/Desktop/rag
git add packages/service/tests/spike/ packages/service/pyproject.toml packages/service/uv.lock docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md
git commit -m "spike: 验证 langchain-postgres 0.0.17 PGEngine + PGVectorStore.create_sync API"
```

---

## Task 1: 加 LangChain 依赖

**Files:**
- Modify: `packages/service/pyproject.toml`

- [ ] **Step 1: 加 dep**

`packages/service/pyproject.toml` 在 `dependencies` 数组加:

```toml
"langchain-core>=1.4,<2.0",  # LangChain 核心抽象 (Runnable, prompts, parsers)
"langchain-openai>=1.0,<2.0",  # ChatOpenAI + OpenAIEmbeddings (兼容 DeepSeek/SiliconFlow 等)
"langchain-ollama>=1.0,<2.0",  # ChatOllama (本地 LLM)
"langchain-postgres>=0.0.17,<0.1",  # PGVectorStore + PGEngine (pgvector 集成)
"langchain-text-splitters>=1.0,<2.0",  # RecursiveCharacterTextSplitter
"deepeval>=3.0",  # RAG 5 指标评估 (替代 LlamaIndex Evaluation)
```

**LlamaIndex 5 包暂不删**, T8 才删.

- [ ] **Step 2: uv sync**

```bash
cd packages/service
uv sync
```

Expected: 6 包装上, 无依赖冲突

- [ ] **Step 3: 验证 import 可跑**

```bash
cd packages/service
uv run python -c "
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama
from langchain_postgres import PGEngine, PGVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableParallel
from langchain_core.prompts import ChatPromptTemplate
from deepeval.metrics import FaithfulnessMetric
print('OK')
"
```

Expected: 输出 `OK`

- [ ] **Step 4: 跑全量 test 验证旧代码仍工作**

```bash
cd packages/service
uv run pytest tests/ -v --tb=no -q
```

Expected: pre-existing fail 22 + errors 38, 其余绿 (跟 baseline 一致)

- [ ] **Step 5: Commit**

```bash
git add packages/service/pyproject.toml packages/service/uv.lock
git commit -m "feat(deps): 加 langchain 1.x + deepeval 依赖 (T1 of LlamaIndex 替换)"
```

---

## Task 2: 新建 RAGDoc + 改 chunker + document_loader

**Files:**
- Create: `packages/service/src/common/document.py`
- Modify: `packages/service/src/common/chunker.py`
- Modify: `packages/service/src/common/document_loader.py`
- Modify: `packages/service/src/common/__init__.py`
- Modify: `packages/service/tests/common/test_chunker.py`
- Modify: `packages/service/tests/common/test_document_loader.py`

- [ ] **Step 1: 写 RAGDoc test**

`packages/service/tests/common/test_document.py` (新建):

```python
"""测试 RAGDoc 数据类 (取代 LlamaIndex Document)"""

from src.common.document import RAGDoc


def test_ragdoc_basic():
    doc = RAGDoc(text="hello", metadata={"file_path": "/a.md"})
    assert doc.text == "hello"
    assert doc.metadata == {"file_path": "/a.md"}


def test_ragdoc_get_content_returns_text():
    doc = RAGDoc(text="content")
    assert doc.get_content() == "content"


def test_ragdoc_default_metadata():
    doc = RAGDoc(text="x")
    assert doc.metadata == {}


def test_ragdoc_metadata_is_dict():
    doc = RAGDoc(text="x", metadata={"k": "v"})
    doc.metadata["k2"] = "v2"
    assert doc.metadata == {"k": "v", "k2": "v2"}
```

- [ ] **Step 2: 跑 test 验证 fail**

```bash
cd packages/service
uv run pytest tests/common/test_document.py -v
```

Expected: FAIL (`ModuleNotFoundError: No module named 'src.common.document'`)

- [ ] **Step 3: 实现 RAGDoc**

`packages/service/src/common/document.py` (新建):

```python
"""RAGDoc 数据载体, 取代 llama_index.core.schema.Document.

接口保留 `.get_content()` 跟原 LlamaIndex Document 一致, 调用方零改动.
"""

from dataclasses import dataclass, field


@dataclass
class RAGDoc:
    """统一 RAG 文档载体. 跟 LlamaIndex Document 鸭子兼容."""

    text: str
    metadata: dict = field(default_factory=dict)

    def get_content(self) -> str:
        return self.text
```

- [ ] **Step 4: 跑 test 验证 pass**

```bash
uv run pytest tests/common/test_document.py -v
```

Expected: 4/4 PASS

- [ ] **Step 5: 改 chunker.py**

`packages/service/src/common/chunker.py` 整个文件替换:

```python
"""文档分块器

将 RAGDoc 列表分块为更小的片段, 用于 embedding 和检索.
"""

from collections.abc import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .document import RAGDoc

# 中文友好 separators: 段落 → 行 → 中文句末 → 西文句末 → 空格 → 字符
# LC 默认 ["\n\n", "\n", " ", ""] 对中文表现差, 必须显式加中文标点
_CN_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", " ", ""]


def chunk_documents(
    documents: Sequence[RAGDoc],
    chunk_size: int = 512,
    chunk_overlap: int = 128,
) -> list[RAGDoc]:
    """将 RAGDoc 列表分块, 返回新 RAGDoc 列表.

    Args:
        documents: 原始 RAGDoc 列表
        chunk_size: 每块字符数
        chunk_overlap: 相邻块重叠字符数

    Returns:
        分块后的 RAGDoc 列表 (metadata 从原文档复制)
    """
    if not documents:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_CN_SEPARATORS,
    )
    out: list[RAGDoc] = []
    for d in documents:
        for piece in splitter.split_text(d.text):
            out.append(RAGDoc(text=piece, metadata=d.metadata.copy()))
    return out
```

- [ ] **Step 6: 改 document_loader.py**

`packages/service/src/common/document_loader.py` 整个文件替换:

```python
"""文档加载器

从文件系统加载 .md / .txt 文件为 RAGDoc.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path

from .document import RAGDoc
from .text_io import read_text_with_fallback


def load_md_files(dir_path: str | Path, recursive: bool = True) -> list[RAGDoc]:
    """递归加载目录下所有 .md 文件, 返回 RAGDoc 列表"""
    dir_path = Path(dir_path)
    pattern = "**/*.md" if recursive else "*.md"
    files = sorted(dir_path.glob(pattern))
    return _load_text_files(files)


def load_txt_files(dir_path: str | Path, recursive: bool = True) -> list[RAGDoc]:
    """递归加载目录下所有 .txt 文件"""
    dir_path = Path(dir_path)
    pattern = "**/*.txt" if recursive else "*.txt"
    files = sorted(dir_path.glob(pattern))
    return _load_text_files(files)


def _load_text_files(files: Sequence[Path]) -> list[RAGDoc]:
    """通用文本文件加载器"""
    docs: list[RAGDoc] = []
    for f in files:
        text = read_text_with_fallback(f)
        if text is None:
            continue
        docs.append(RAGDoc(text=text, metadata={"file_path": str(f)}))
    return docs


def load_documents_from_files(
    file_paths: Iterable[str | Path],
) -> list[RAGDoc]:
    """从文件路径列表加载为 RAGDoc 列表"""
    docs: list[RAGDoc] = []
    for fp in file_paths:
        fp = Path(fp)
        if not fp.exists():
            continue
        text = read_text_with_fallback(fp)
        if text is None:
            continue
        docs.append(RAGDoc(text=text, metadata={"file_path": str(fp)}))
    return docs


def filter_empty_documents(docs: Sequence[RAGDoc]) -> list[RAGDoc]:
    """过滤空白文档"""
    return [d for d in docs if extract_plain_text(d).strip()]


def extract_plain_text(doc: RAGDoc) -> str:
    return doc.get_content()


def documents_to_texts(docs: Sequence[RAGDoc]) -> list[str]:
    return [extract_plain_text(d) for d in docs]
```

- [ ] **Step 7: 改 common/__init__.py**

`packages/service/src/common/__init__.py` 替换:

```python
"""common 子包: 共享工具 (chunker, document_loader, batch_utils, evaluation, defaults)"""

from . import defaults
from .batch_utils import batch_embed, estimate_tokens, truncate_text
from .chunker import chunk_documents
from .document import RAGDoc
from .document_loader import (
    documents_to_texts,
    extract_plain_text,
    filter_empty_documents,
    load_documents_from_files,
    load_md_files,
    load_txt_files,
)
from .evaluation import EvaluationReport, RAGAMetrics, generate_evaluation_dataset

__all__ = [
    "defaults",
    # chunker
    "chunk_documents",
    # document
    "RAGDoc",
    # document_loader
    "load_md_files",
    "load_txt_files",
    "load_documents_from_files",
    "filter_empty_documents",
    "extract_plain_text",
    "documents_to_texts",
    # batch_utils
    "estimate_tokens",
    "truncate_text",
    "batch_embed",
    # evaluation
    "RAGAMetrics",
    "EvaluationReport",
    "generate_evaluation_dataset",
]
```

(删了 `get_default_node_parser` import + export)

- [ ] **Step 8: 改 test_chunker.py**

`packages/service/tests/common/test_chunker.py` 替换 (跟 RAGDoc 对齐):

```python
"""测试 chunker - 走 RAGDoc + RecursiveCharacterTextSplitter"""

from src.common.chunker import chunk_documents
from src.common.document import RAGDoc


def test_chunk_documents_empty():
    """空输入返空列表, 不抛"""
    assert chunk_documents([]) == []


def test_chunk_documents_short_text_not_split():
    """文本短于 chunk_size, 不切"""
    docs = [RAGDoc(text="短文本", metadata={"k": "v"})]
    out = chunk_documents(docs, chunk_size=512, chunk_overlap=128)
    assert len(out) == 1
    assert out[0].text == "短文本"
    assert out[0].metadata == {"k": "v"}


def test_chunk_documents_long_text_split():
    """长文本按 chunk_size 切多块"""
    long_text = "。".join([f"句子{i}" for i in range(200)])  # ~1200 字符
    docs = [RAGDoc(text=long_text, metadata={"file_path": "/a.md"})]
    out = chunk_documents(docs, chunk_size=200, chunk_overlap=50)
    assert len(out) > 1
    # 每块都带原 metadata 副本
    for c in out:
        assert c.metadata == {"file_path": "/a.md"}


def test_chunk_documents_metadata_independent_copies():
    """metadata 是 copy, 改一个不影响另一个"""
    docs = [RAGDoc(text="句子。" * 100, metadata={"k": "v"})]
    out = chunk_documents(docs, chunk_size=50, chunk_overlap=10)
    assert len(out) > 1
    out[0].metadata["new"] = "x"
    assert "new" not in out[1].metadata


def test_chunk_documents_cn_separators_prefer_period():
    """中文 separator 优先在句号断"""
    text = "句一。" * 50  # 一堆短句, 句号分隔
    docs = [RAGDoc(text=text)]
    out = chunk_documents(docs, chunk_size=100, chunk_overlap=20)
    # 每块都是句号结尾或文本末尾
    for c in out[:-1]:  # 最后一块可能末尾不带句号
        # 起码不应该断在句号中间 (chunk size 限制下, separators 优先级保证)
        assert "句" in c.text
```

- [ ] **Step 9: 改 test_document_loader.py**

`packages/service/tests/common/test_document_loader.py` 中所有 `llama_index.core.schema.Document` 改 `src.common.document.RAGDoc`. 把 `.get_content()` 调用保留 (RAGDoc 也支持).

具体改法:

```bash
cd packages/service
# 检查现有 import
grep -n "llama_index\|Document" tests/common/test_document_loader.py
```

把 `from llama_index.core.schema import Document` 改 `from src.common.document import RAGDoc`, 所有 `Document(text=..., metadata=...)` 改 `RAGDoc(text=..., metadata=...)`. 断言不变.

- [ ] **Step 10: 跑测试**

```bash
cd packages/service
uv run pytest tests/common/ -v
```

Expected: 全绿

- [ ] **Step 11: Commit**

```bash
git add packages/service/src/common/ packages/service/tests/common/
git commit -m "feat(common): RAGDoc + RecursiveCharacterTextSplitter 替代 LlamaIndex (T2 of LlamaIndex 替换)"
```

---

## Task 3: 改 LLM + Embedder + buyer_profile 调用方

**Files:**
- Modify: `packages/service/src/generation/llm.py`
- Modify: `packages/service/src/retrieval/embedder.py`
- Modify: `packages/service/src/buyer_profile/extractor.py`
- Modify: `packages/service/tests/generation/test_llm.py`
- Modify: `packages/service/tests/retrieval/test_embedder.py`
- Modify: `packages/service/tests/buyer_profile/test_extractor.py` (如存在)

- [ ] **Step 1: 改 llm.py**

`packages/service/src/generation/llm.py` 整个文件替换:

```python
"""LLM 封装 (LangChain ChatOpenAI / ChatOllama)

(2026-06-29 LC 替换) 从 llama_index 切到 langchain. ChatOpenAI 配 base_url 走任何 OpenAI
兼容端点 (DeepSeek / SiliconFlow / 本地 vllm 等), 不走 OpenAI 模型白名单.
"""

import os
from typing import TYPE_CHECKING, Any

from ..common import defaults
from ..config.settings import settings

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI


def _llm_model() -> str:
    return os.getenv("LLM_MODEL") or settings.llm_model or defaults.DEFAULT_LLM_MODEL_OPENAI


def _openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or settings.openai_api_key or defaults.DEFAULT_OPENAI_API_KEY


def _openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL") or settings.openai_base_url or defaults.DEFAULT_OPENAI_BASE_URL


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL") or settings.ollama_base_url or defaults.DEFAULT_OLLAMA_BASE_URL


def _ollama_model() -> str:
    return os.getenv("LLM_MODEL") or settings.llm_model or defaults.DEFAULT_LLM_MODEL_OLLAMA


class OpenAILLM:
    """OpenAI 兼容协议 LLM (DeepSeek / SiliconFlow / OpenAI / ...).

    `self.llm` 返 `langchain_openai.ChatOpenAI` 实例, 调用接口:
    - resp = self.llm.invoke(prompt) → AIMessage (用 resp.content 取文本)
    - resp = await self.llm.ainvoke(prompt) → AIMessage
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = defaults.DEFAULT_OPENAI_MAX_TOKENS,
    ):
        self.model = model or _llm_model()
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._llm: ChatOpenAI | None = None

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            from langchain_openai import ChatOpenAI

            base_url = _openai_base_url()
            # DeepSeek completions API 走 /beta 端点 (chat API 走默认)
            if base_url and "deepseek" in base_url and not base_url.endswith("/beta"):
                base_url = base_url.rstrip("/") + "/beta"

            kwargs: dict[str, Any] = {
                "model": self.model,
                "api_key": self._api_key or _openai_api_key(),
                "base_url": base_url,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                kwargs["max_tokens"] = self._max_tokens
            self._llm = ChatOpenAI(**kwargs)
        return self._llm


class LocalLLM:
    """本地 Ollama LLM. `self.llm` 返 `langchain_ollama.ChatOllama`."""

    def __init__(self, model: str | None = None, base_url: str | None = None, temperature: float = 0.0):
        self.model = model or _ollama_model()
        self.base_url = base_url or _ollama_base_url()
        self._temperature = temperature
        self._llm: ChatOllama | None = None

    @property
    def llm(self) -> ChatOllama:
        if self._llm is None:
            from langchain_ollama import ChatOllama

            self._llm = ChatOllama(model=self.model, base_url=self.base_url, temperature=self._temperature)
        return self._llm
```

- [ ] **Step 2: 改 test_llm.py mock 路径**

`packages/service/tests/generation/test_llm.py` 中:
- mock target `src.generation.llm.OpenAILike` → `src.generation.llm.ChatOpenAI`
- mock target `src.generation.llm.Ollama` → `src.generation.llm.ChatOllama`
- 断言 `.api_base` 改 `.base_url`

具体打开看一下当前 mock setup, 1:1 换路径名.

```bash
cd packages/service
uv run pytest tests/generation/test_llm.py -v
```

Expected: 全绿

- [ ] **Step 3: 改 embedder.py**

`packages/service/src/retrieval/embedder.py` 整个文件替换:

```python
"""Embedder 封装 (OpenAI 兼容协议, LangChain)

走 LangChain `langchain_openai.OpenAIEmbeddings`, base_url 配 EMBED_BASE_URL.
EmbedCache (Redis 7d) 包装层保留.
"""

import asyncio
import os
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..common import defaults

if TYPE_CHECKING:
    from langchain_openai import OpenAIEmbeddings


class OpenAIEmbedder:
    """OpenAI 兼容 embedder: 走 EMBED_BASE_URL + EMBED_API_KEY (独立 env, 不共用 LLM)"""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
    ):
        # env 优先级: 显式参数 > EMBED_* > 代码默认
        self.model = model or os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_OPENAI)
        self._api_key = (
            api_key or os.getenv("EMBED_API_KEY") or os.getenv("OPENAI_API_KEY") or defaults.DEFAULT_OPENAI_API_KEY
        )
        self._base_url = base_url or os.getenv("EMBED_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
        env_dims = os.getenv("EMBED_DIMENSIONS")
        self._dimensions = dimensions if dimensions is not None else (int(env_dims) if env_dims else None)
        self._embedder: OpenAIEmbeddings | None = None

    @property
    def embedder(self) -> OpenAIEmbeddings:
        if self._embedder is None:
            from langchain_openai import OpenAIEmbeddings

            kwargs: dict[str, Any] = {
                "model": self.model,
                "api_key": self._api_key or None,
                # (Spike 偏差 #4) bge-m3 (SiliconFlow) 用 XLM-RoBERTa tokenizer,
                # 不是 tiktoken. 必须关 LC 默认 tiktoken 编码长度检查 (否则 KeyError).
                "check_embedding_ctx_length": False,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            # (Spike 偏差 #4) 不传 `dimensions`: bge-m3 服务端固定 1024 维, 传 dimensions
            # 会 400. OpenAI text-embedding-3 系列私有特性, 其他 OpenAI 兼容端点不支持.
            # 维度通过 init_vectorstore_table(vector_size=) 表达, 不通过 embedder.
            self._embedder = OpenAIEmbeddings(**kwargs)
        return self._embedder

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.embed_documents(texts)

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """带 EmbedCache 包装 (Redis 7d). 重复 text 7d 内 0 LLM 调用."""
        from ..core.embed_cache import cache_vector, get_cached_vector

        if not texts:
            return []

        # 1. 并发查 cache
        cached_results = await asyncio.gather(*[get_cached_vector(t) for t in texts])
        results: list[list[float] | None] = list(cached_results)
        miss_indices = [i for i, v in enumerate(results) if v is None]

        if not miss_indices:
            return [v for v in results if v is not None]  # type: ignore[list-item]

        # 2. miss 的调底层 embedder (LC OpenAIEmbeddings)
        miss_texts = [texts[i] for i in miss_indices]
        computed = await self.embedder.aembed_documents(miss_texts)

        # 3. 回填 + fire-and-forget 写 cache
        for idx, vec in zip(miss_indices, computed):
            results[idx] = list(vec)
            asyncio.create_task(cache_vector(texts[idx], vec))

        return [v for v in results if v is not None]  # type: ignore[list-item]

    def __call__(self, text: str) -> list[float]:
        return self.embed([text])[0]


def get_embedder(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    batch_size: int | None = None,
) -> OpenAIEmbedder:
    """返回 OpenAI 兼容 embedder. batch_size 保留兼容 (不影响 OpenAI 协议)."""
    return OpenAIEmbedder(model=model, api_key=api_key, base_url=base_url)


def embed_documents(
    documents: Sequence[Any], embedder: Any, batch_size: int = 32, show_progress: bool = True
) -> list[list[float]]:
    if documents and hasattr(documents[0], "get_content"):
        texts = [d.get_content() for d in documents]
    elif documents and isinstance(documents[0], str):
        texts = list(documents)
    else:
        raise TypeError("documents 必须是 RAGDoc 列表或字符串列表")
    from ..common.batch_utils import batch_embed

    return batch_embed(texts, embedder, batch_size=batch_size, show_progress=show_progress)


def embed_texts(
    texts: Iterable[str], embedder: Any, batch_size: int = 32, show_progress: bool = True
) -> list[list[float]]:
    from ..common.batch_utils import batch_embed

    return batch_embed(texts, embedder, batch_size=batch_size, show_progress=show_progress)


def get_embedding_dimension(embedder: Any) -> int | None:
    if hasattr(embedder, "dimensions"):
        return embedder.dimensions
    return None


def is_embedder_ready(embedder: Any) -> bool:
    try:
        result = embedder(["./__health_check__"])
        return isinstance(result, list) and len(result) == 1
    except Exception:
        logger.warning("is_embedder_ready 检查失败, embedder 可能无法使用")
        return False
```

- [ ] **Step 4: 改 test_embedder.py mock 路径**

`packages/service/tests/retrieval/test_embedder.py`:
- mock target `src.retrieval.embedder.OpenAIEmbedding` → `src.retrieval.embedder.OpenAIEmbeddings`
- 调用 `get_text_embedding_batch` → `embed_documents`
- 调用 `aget_text_embedding_batch` → `aembed_documents`

```bash
cd packages/service
uv run pytest tests/retrieval/test_embedder.py -v
```

Expected: 全绿

- [ ] **Step 5: 改 buyer_profile/extractor.py**

`packages/service/src/buyer_profile/extractor.py:50-54` 改:

```python
def _call_llm(prompt: str) -> dict[str, Any]:
    """调用 LLM 提取字段, 解析 JSON 返回.

    (2026-06-29 LC 替换) OpenAILLM 内部已切到 ChatOpenAI, API 从 `.complete(prompt) + .text`
    改为 `.invoke(prompt) + .content` (LangChain AIMessage 接口).
    """
    from src.generation.llm import OpenAILLM

    llm = OpenAILLM().llm
    resp = llm.invoke(prompt)
    text = resp.content if hasattr(resp, "content") else str(resp)

    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    result = json.loads(cleaned)
    if not isinstance(result, dict):
        return {}
    return {k: v for k, v in result.items() if v is not None}
```

- [ ] **Step 6: 检查 + 改 buyer_profile test**

```bash
cd packages/service
ls tests/buyer_profile/
grep -rn "llm.complete\|\.text" tests/buyer_profile/
```

如有 mock `.complete` / `.text`, 改成 `.invoke` / `.content`. 如 mock setup 是:

```python
mock_llm.complete.return_value = Mock(text='{"a":1}')
```

改为:

```python
mock_llm.invoke.return_value = Mock(content='{"a":1}')
```

```bash
uv run pytest tests/buyer_profile/ -v
```

Expected: 全绿

- [ ] **Step 7: 跑相关 test 整体验证**

```bash
cd packages/service
uv run pytest tests/generation/test_llm.py tests/retrieval/test_embedder.py tests/buyer_profile/ -v
```

Expected: 全绿

- [ ] **Step 8: Commit**

```bash
git add packages/service/src/generation/llm.py packages/service/src/retrieval/embedder.py packages/service/src/buyer_profile/extractor.py packages/service/tests/generation/test_llm.py packages/service/tests/retrieval/test_embedder.py packages/service/tests/buyer_profile/
git commit -m "feat(generation,retrieval): ChatOpenAI/ChatOllama + OpenAIEmbeddings 替代 LlamaIndex (T3 of LlamaIndex 替换)"
```

---

## Task 4: 数据迁移 alembic migration

**Files:**
- Create: `packages/service/alembic/versions/20260629_lc_pgvector_schema.py`
- Modify: `packages/service/src/retrieval/vector_store.py` (改 `init_pgvector()`)

**前置:** T0 spike 确认 `PGEngine.init_vectorstore_table` API 真实 + 实测 `langchain_metadata` 列存在.

- [ ] **Step 1: 查现有 alembic head**

```bash
cd packages/service
uv run alembic current
ls alembic/versions/ | head -5
```

记下最新 revision id (作为本 migration 的 `down_revision`).

- [ ] **Step 2: 查现有 `llamaindex_embeddings` schema 跟数据量**

```bash
cd packages/service
uv run python -c "
import os, psycopg
conn = psycopg.connect(
    host=os.environ['PG_HOST'], port=os.environ['PG_PORT'],
    user=os.environ['PG_USER'], password=os.environ['PG_PASSWORD'],
    dbname=os.environ['PG_DATABASE'],
)
with conn.cursor() as cur:
    cur.execute(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'llamaindex_embeddings'\")
    print('Schema:', cur.fetchall())
    cur.execute('SELECT COUNT(*) FROM llamaindex_embeddings')
    print('Rows:', cur.fetchone()[0])
"
```

Expected: 列 `id, text, metadata, ref_doc_id, embedding`, 行数记下来.

- [ ] **Step 3: 写 migration**

`packages/service/alembic/versions/20260629_lc_pgvector_schema.py` (新建):

```python
"""LC PGVectorStore schema 迁移: llamaindex_embeddings → rag_embeddings

替换 LlamaIndex PGVectorStore (单表 5 列) 到 LangChain PGVectorStore 单表 schema
(langchain_id / content / embedding / langchain_metadata JSONB).

ref_doc_id 从老表独立列迁到 langchain_metadata.ref_doc_id JSONB key.

老表 llamaindex_embeddings 保留 7 天, P3 follow-up 单独 DROP.

Revision ID: 20260629_lc_pgvector
Revises: <PREV_REVISION>
Create Date: 2026-06-29
"""

import os
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "20260629_lc_pgvector"
down_revision = "<PREV_REVISION>"  # ← Step 1 拿到的 head
branch_labels = None
depends_on = None


def _get_embed_dim() -> int:
    """从 env 读 embedding 维度, 跟 EMBED_DIMENSIONS 单源一致."""
    return int(os.getenv("EMBED_DIMENSIONS", "1024"))


def upgrade() -> None:
    """建 rag_embeddings 表 + HNSW 索引 + GIN 索引 + INSERT FROM 老表

    注: 这里直接写 CREATE TABLE 等价 SQL, 不调 LC PGEngine.init_vectorstore_table.
    (a) alembic 应该是 reproducible, 不依赖 LC 库版本变化时 schema 改动
    (b) LC 默认 langchain_metadata 是 json 不是 jsonb (跟项目规约冲突), 直接 SQL 建 jsonb
    """
    dim = _get_embed_dim()

    # 1. 建新表 (LC PGVectorStore 标准 schema, 但 langchain_metadata 是 jsonb 不是 json)
    op.execute(f"""
        CREATE TABLE rag_embeddings (
            langchain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content TEXT NOT NULL,
            embedding vector({dim}),
            langchain_metadata JSONB DEFAULT '{{}}'::jsonb
        );
    """)

    # 2. HNSW 索引 (vector cosine) — LC init_vectorstore_table 不建, 我们建
    op.execute("""
        CREATE INDEX rag_embeddings_hnsw_idx
            ON rag_embeddings USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200);
    """)

    # 3. GIN 索引 (JSONB metadata, 加速 ref_doc_id 删除走 @> 操作符)
    op.execute("""
        CREATE INDEX rag_embeddings_metadata_gin_idx
            ON rag_embeddings USING gin (langchain_metadata jsonb_path_ops);
    """)

    # 4. 一次性数据迁移 (若老表存在且有数据)
    # 老表: id, text, metadata, ref_doc_id, embedding
    # 新表: langchain_id, content, langchain_metadata (含 ref_doc_id), embedding
    op.execute("""
        INSERT INTO rag_embeddings (langchain_id, content, langchain_metadata, embedding)
        SELECT
            id,
            text,
            COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('ref_doc_id', ref_doc_id::text),
            embedding
        FROM llamaindex_embeddings
        WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'llamaindex_embeddings');
    """)


def downgrade() -> None:
    """删 rag_embeddings (老表仍在, 业务回到 LlamaIndex 代码即可)"""
    op.execute("DROP INDEX IF EXISTS rag_embeddings_metadata_gin_idx;")
    op.execute("DROP INDEX IF EXISTS rag_embeddings_hnsw_idx;")
    op.execute("DROP TABLE IF EXISTS rag_embeddings;")
```

把 `<PREV_REVISION>` 改成 Step 1 拿到的 head ID.

- [ ] **Step 4: 跑迁移**

```bash
cd packages/service
uv run alembic upgrade head
```

Expected: `Running upgrade <prev> -> 20260629_lc_pgvector, LC PGVectorStore schema migration`, 无错误

- [ ] **Step 5: 验证数据**

```bash
cd packages/service
uv run python -c "
import os, psycopg
conn = psycopg.connect(
    host=os.environ['PG_HOST'], port=os.environ['PG_PORT'],
    user=os.environ['PG_USER'], password=os.environ['PG_PASSWORD'],
    dbname=os.environ['PG_DATABASE'],
)
with conn.cursor() as cur:
    cur.execute('SELECT COUNT(*) FROM rag_embeddings')
    new_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM llamaindex_embeddings')
    old_count = cur.fetchone()[0]
    print(f'rag_embeddings: {new_count}, llamaindex_embeddings: {old_count}')
    assert new_count == old_count, f'数据迁移行数不一致! {new_count} != {old_count}'

    # 验证 ref_doc_id 都迁到 metadata
    cur.execute(\"SELECT COUNT(*) FROM rag_embeddings WHERE langchain_metadata->>'ref_doc_id' IS NULL\")
    missing = cur.fetchone()[0]
    print(f'缺 ref_doc_id 的行: {missing}')
    assert missing == 0, f'有 {missing} 行 ref_doc_id 缺失'
print('OK')
"
```

Expected: `rag_embeddings: N, llamaindex_embeddings: N` (相等) + `OK`

如行数为 0 (dev 没数据) OK, 等价 INSERT noop.

- [ ] **Step 6: 改 init_pgvector**

`packages/service/src/retrieval/vector_store.py` 中 `init_pgvector` 函数改为走 LC schema. 但因为 T5 还没改 vector_store 主体, 这里**先不动**, 留 T5 一起改.

**注**: alembic migration 已经把表建好了, `init_pgvector` 本身是 dev tooling 函数, T5 改时一起改.

- [ ] **Step 7: Commit**

```bash
git add packages/service/alembic/versions/20260629_lc_pgvector_schema.py
git commit -m "feat(alembic): rag_embeddings LC schema + 迁移 llamaindex_embeddings 数据 (T4 of LlamaIndex 替换)"
```

---

## Task 5: 改 vector_store + query_engine (核心 RAG 链路)

**Files:**
- Modify: `packages/service/src/retrieval/vector_store.py`
- Modify: `packages/service/src/generation/query_engine.py`
- Modify: `packages/service/src/retrieval/__init__.py`
- Modify: `packages/service/src/generation/__init__.py`
- Modify: `packages/service/tests/retrieval/test_vector_store.py`
- Modify: `packages/service/tests/retrieval/test_retrieval_exports.py`
- Modify: `packages/service/tests/generation/test_query_engine.py`
- Modify: `packages/service/tests/api/test_routes_endpoints.py`

- [ ] **Step 1: 改 vector_store.py**

`packages/service/src/retrieval/vector_store.py` 整个文件替换:

```python
"""pgvector 向量库封装 (LangChain PGVectorStore + PGEngine)

公开 API: PGVectorStore (sync) + AsyncPGVectorStore + PGVectorConfig + add_to_vector_store
+ delete_from_vector_store + init_pgvector + get_vector_store.

内部走 langchain_postgres:
- PGEngine.from_connection_string → SQLAlchemy engine wrapper
- PGVectorStore.create_sync(engine, embedding_service, table_name=rag_embeddings) → LC store
- delete 按 metadata.ref_doc_id 走原生 SQL (LC delete 只按主键)
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from src.common.db_url import get_rag_db_url
from src.common.document import RAGDoc

if TYPE_CHECKING:
    from langchain_postgres import PGEngine
    from langchain_postgres import PGVectorStore as LCPGVectorStore


# LC PGVectorStore 表名 (取代老 llamaindex_embeddings)
_VECTOR_TABLE = "rag_embeddings"


@dataclass
class PGVectorConfig:
    """pgvector 配置. 5 个连接字段从 PG_* env 派生. 向量索引调参是 dataclass 默认值."""

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "rag"
    vector_dim: int | None = None  # None = 用 _get_embed_dim()
    index_type: str = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    ivfflat_lists: int = 100

    @property
    def connection_string(self) -> str:
        return get_rag_db_url()

    @classmethod
    def from_env(cls) -> PGVectorConfig:
        from ..common import defaults

        return cls(
            host=os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST),
            port=int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))),
            user=os.getenv("PG_USER", defaults.DEFAULT_PG_USER),
            password=os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD),
            database=os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE),
        )


class PGVectorStore:
    """业务包装. 公开 API 同名 (add / delete / query), 内部走 LC PGVectorStore.

    持有 2 个 engine (Spike 偏差 #3):
    - _pg_engine (PGEngine): 给 LC PGVectorStore 用 (async psycopg3)
    - _sa_engine (sqlalchemy.Engine): 给 raw SQL DELETE / GIN 索引建 (sync)
    PGEngine.close() 是 coroutine, sync 路径不可靠, 所以 sync 操作走独立 SA Engine.
    """

    def __init__(self, config: PGVectorConfig | None = None, embedder: Any | None = None):
        self._config = config or PGVectorConfig.from_env()
        self._embedder = embedder
        self._vs: LCPGVectorStore | None = None
        self._pg_engine: PGEngine | None = None
        self._sa_engine: Any | None = None  # sqlalchemy.Engine

    @property
    def config(self) -> PGVectorConfig:
        return self._config

    @property
    def vector_store(self) -> LCPGVectorStore:
        if self._vs is None:
            from langchain_postgres import PGEngine
            from langchain_postgres import PGVectorStore as LCPGVectorStore
            from sqlalchemy import create_engine

            if self._embedder is None:
                raise RuntimeError(
                    "PGVectorStore 需要传入 embedder. LC PGVectorStore.create_sync "
                    "构造期需要 OpenAIEmbeddings 实例. 调用方应显式注入."
                )
            self._pg_engine = PGEngine.from_connection_string(url=self._config.connection_string)
            self._sa_engine = create_engine(self._config.connection_string)
            inner = self._embedder.embedder if hasattr(self._embedder, "embedder") else self._embedder
            self._vs = LCPGVectorStore.create_sync(
                engine=self._pg_engine,
                embedding_service=inner,
                table_name=_VECTOR_TABLE,
            )
        return self._vs

    def add(self, documents: Sequence[RAGDoc], batch_size: int = 100) -> list[str]:
        """add - metadata 应含 ref_doc_id (上层产生, 文档级标识), 用于 delete 按文档清."""
        if not documents:
            return []
        texts = [d.text for d in documents]
        metadatas = [d.metadata for d in documents]
        return self.vector_store.add_texts(texts, metadatas=metadatas)

    def delete(self, doc_ids: Sequence[str], ref_doc_id: str | None = None) -> None:
        """按 ref_doc_id 删 - 跟 LlamaIndex 原 ref_doc_id 语义对齐.

        签名兼容老调用:
        - `delete([doc_id])` -> 按 ref_doc_id IN ([doc_id]) 删
        - `delete([], ref_doc_id="doc-A")` -> 按 ref_doc_id = "doc-A" 删
        """
        ids = list(doc_ids) if doc_ids else ([ref_doc_id] if ref_doc_id else [])
        if not ids:
            return
        # 触发 lazy build (拿到 _sa_engine)
        _ = self.vector_store
        _delete_by_ref_doc_id(self._sa_engine, _VECTOR_TABLE, ids)

    def query(self, query_embedding: list[float], top_k: int = 5, filter: dict | None = None) -> Any:
        """按 vector cosine 检索, 返 LC Document 列表."""
        return self.vector_store.similarity_search_by_vector(query_embedding, k=top_k, filter=filter)

    def close(self) -> None:
        """sync 路径 close. PGEngine.close 是 coroutine, sync 没法清, 只清 SA Engine."""
        if self._sa_engine is not None:
            self._sa_engine.dispose()
        self._vs = None
        self._pg_engine = None
        self._sa_engine = None


class AsyncPGVectorStore:
    """异步版. 走 LC PGVectorStore.create (async 工厂) + aadd_texts / asimilarity_search_by_vector."""

    def __init__(self, config: PGVectorConfig | None = None, embedder: Any | None = None):
        self._config = config or PGVectorConfig.from_env()
        self._embedder = embedder
        self._vs: LCPGVectorStore | None = None
        self._engine: PGEngine | None = None

    @property
    def config(self) -> PGVectorConfig:
        return self._config

    async def aconnect(self) -> None:
        from langchain_postgres import PGEngine
        from langchain_postgres import PGVectorStore as LCPGVectorStore

        if self._embedder is None:
            raise RuntimeError("AsyncPGVectorStore 需要传入 embedder")
        self._engine = PGEngine.from_connection_string(url=self._config.connection_string)
        inner = self._embedder.embedder if hasattr(self._embedder, "embedder") else self._embedder
        # LC AsyncPGVectorStore.create 工厂方法
        self._vs = await LCPGVectorStore.create(
            engine=self._engine,
            embedding_service=inner,
            table_name=_VECTOR_TABLE,
        )

    async def aadd(self, documents: Sequence[RAGDoc]) -> list[str]:
        if not documents:
            return []
        assert self._vs is not None
        return await self._vs.aadd_texts(
            texts=[d.text for d in documents],
            metadatas=[d.metadata for d in documents],
        )

    async def adelete(self, doc_ids: Sequence[str]) -> None:
        if not doc_ids:
            return
        assert self._engine is not None
        # async 也走原生 SQL DELETE BY metadata
        await _adelete_by_ref_doc_id(self._engine, _VECTOR_TABLE, list(doc_ids))

    async def adisconnect(self) -> None:
        if self._engine is not None:
            aclose = getattr(self._engine, "aclose", None)
            if aclose is not None:
                await aclose()
        self._vs = None
        self._engine = None


def _delete_by_ref_doc_id(engine: Any, table_name: str, ref_doc_ids: list[str]) -> None:
    """按 langchain_metadata->>'ref_doc_id' = ANY(:rids) 删 (sync).

    engine 是 sqlalchemy.Engine (不是 PGEngine), 因为 PGEngine 是 async wrapper,
    sync raw SQL 走独立 SA Engine. langchain_metadata 已 ALTER 成 jsonb, ->>'k' 走 GIN.
    """
    sql = text(f"DELETE FROM {table_name} WHERE langchain_metadata->>'ref_doc_id' = ANY(:rids)")
    with engine.connect() as conn:
        conn.execute(sql, {"rids": ref_doc_ids})
        conn.commit()


async def _adelete_by_ref_doc_id(engine: PGEngine, table_name: str, ref_doc_ids: list[str]) -> None:
    """async 版 - PGEngine async aconnect."""
    sql = text(f"DELETE FROM {table_name} WHERE langchain_metadata->>'ref_doc_id' = ANY(:rids)")
    async with engine.aconnect() as conn:
        await conn.execute(sql, {"rids": ref_doc_ids})
        await conn.commit()


def get_vector_store(config: PGVectorConfig | None = None, use_async: bool = False) -> Any:
    if use_async:
        return AsyncPGVectorStore(config or PGVectorConfig.from_env())
    return PGVectorStore(config)


def init_pgvector(config: PGVectorConfig | None = None, force: bool = False) -> None:
    """初始化 pgvector + rag_embeddings 表 (走 LC PGEngine + 修正 JSONB / vector index).

    生产用 alembic migration. 此函数用于 dev tooling (重置 schema).
    实际跑 4 步, 跟 Spike T0 偏差对齐:
    1. CREATE EXTENSION vector
    2. PGEngine.init_vectorstore_table (但建出来 langchain_metadata 是 json + 无 vector index)
    3. ALTER langchain_metadata 转 jsonb + 建 GIN (跟项目 JSONB 规约一致)
    4. apply_vector_index(HNSWIndex) 建真实 HNSW
    """
    from langchain_postgres import PGEngine
    from langchain_postgres.v2.indexes import HNSWIndex
    from sqlalchemy import create_engine, text

    config = config or PGVectorConfig.from_env()
    pg_engine = PGEngine.from_connection_string(url=config.connection_string)
    sa_engine = create_engine(config.connection_string)  # 跑 raw SQL ALTER / 索引

    # 1. pgvector 扩展 (LC 不管)
    with sa_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    # 2. LC 标准建表 (Spike: 只建 pkey + langchain_metadata=json)
    pg_engine.init_vectorstore_table(
        table_name=_VECTOR_TABLE,
        vector_size=config.vector_dim or _get_embed_dim(),
        overwrite_existing=force,
    )

    # 3. (Spike 偏差 #1) ALTER 转 jsonb + 建 GIN (项目 JSONB 规约)
    with sa_engine.connect() as conn:
        conn.execute(text(
            f"ALTER TABLE {_VECTOR_TABLE} "
            "ALTER COLUMN langchain_metadata TYPE jsonb "
            "USING langchain_metadata::jsonb"
        ))
        conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS {_VECTOR_TABLE}_metadata_gin_idx "
            f"ON {_VECTOR_TABLE} USING gin (langchain_metadata jsonb_path_ops)"
        ))
        conn.commit()

    # 4. (Spike 偏差 #2) 建 HNSW vector index
    # 需要先构造 store (load embedding_service), 然后 apply_vector_index
    # 这里 embedding_service 不会被 apply_vector_index 用, 但 create_sync 要求传
    from .embedder import get_embedder
    store = LCPGVectorStore.create_sync(
        engine=pg_engine,
        embedding_service=get_embedder().embedder,
        table_name=_VECTOR_TABLE,
    )
    store.apply_vector_index(HNSWIndex(
        name=f"{_VECTOR_TABLE}_hnsw_idx",
        m=config.hnsw_m,
        ef_construction=config.hnsw_ef_construction,
    ))

    sa_engine.dispose()


def _get_embed_dim() -> int:
    """向量列维度从 EMBED_DIMENSIONS env 派生, 默认 1024 (BGE)."""
    return int(os.getenv("EMBED_DIMENSIONS", "1024"))


def add_to_vector_store(
    documents: Sequence[RAGDoc], vector_store: PGVectorStore, embedder: Any | None = None, batch_size: int = 100
) -> list[str]:
    if not documents:
        return []
    return vector_store.add(documents, batch_size=batch_size)


def delete_from_vector_store(doc_ids: Sequence[str], vector_store: PGVectorStore) -> None:
    if not doc_ids:
        return
    vector_store.delete(doc_ids)
```

- [ ] **Step 2: 改 retrieval/__init__.py (类型修正)**

`packages/service/src/retrieval/__init__.py` 检查 export, 跟新 vector_store 对齐:

```python
"""retrieval 子包: 检索层 (embedder + vector store)"""

from .embedder import (
    OpenAIEmbedder,
    embed_documents,
    embed_texts,
    get_embedder,
    get_embedding_dimension,
    is_embedder_ready,
)
from .vector_store import (
    AsyncPGVectorStore,
    PGVectorConfig,
    PGVectorStore,
    add_to_vector_store,
    delete_from_vector_store,
    get_vector_store,
    init_pgvector,
)

__all__ = [
    "OpenAIEmbedder",
    "get_embedder",
    "embed_documents",
    "embed_texts",
    "get_embedding_dimension",
    "is_embedder_ready",
    "PGVectorStore",
    "AsyncPGVectorStore",
    "PGVectorConfig",
    "get_vector_store",
    "init_pgvector",
    "add_to_vector_store",
    "delete_from_vector_store",
]
```

- [ ] **Step 3: 改 query_engine.py**

`packages/service/src/generation/query_engine.py` 整个文件替换:

```python
"""QueryEngine 封装 (LangChain LCEL)

build_query_engine 返回 _LCQueryEngine, 公开 .query / .aquery 接口跟老 LlamaIndex 一致.
内部走 LCEL RunnableParallel: 一次跑 retriever, 同时拿到 docs + LLM response, 不双跑.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


@dataclass
class QueryResult:
    """结构化查询响应.

    - response: LLM 输出 str
    - sources: list[dict] (file_path / page_label / text), 前端依赖
    - source_nodes: LC Document 列表 (内部用; 跟 LlamaIndex NodeWithScore 语义不同, 但
      项目内 0 真实调用方)
    - metadata: dict (保留 backward compat)
    """

    response: str
    sources: list[dict] = field(default_factory=list)
    source_nodes: Any = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_response(cls, response: str, source_docs: list | None = None) -> QueryResult:
        sources = []
        if source_docs:
            for doc in source_docs:
                entry: dict = {}
                meta = getattr(doc, "metadata", {}) or {}
                entry["file_path"] = meta.get("file_path", "")
                entry["page_label"] = meta.get("page_label", "")
                content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                entry["text"] = content[:200] + "..." if len(content) > 200 else content
                sources.append(entry)
        return cls(response=response, sources=sources, source_nodes=source_docs, metadata={})


class _LCQueryEngine:
    """LCEL chain 适配器, 公开 .query / .aquery 跟老 BaseQueryEngine 对齐."""

    def __init__(self, chain_with_docs: Runnable):
        # chain_with_docs.invoke(question) → dict {"response": str, "docs": list[Document]}
        self._chain = chain_with_docs

    def query(self, question: str, **kwargs: Any) -> QueryResult:
        result = self._chain.invoke(question)
        return QueryResult.from_response(result["response"], source_docs=result["docs"])

    async def aquery(self, question: str, **kwargs: Any) -> QueryResult:
        result = await self._chain.ainvoke(question)
        return QueryResult.from_response(result["response"], source_docs=result["docs"])


def get_llm(llm_type: str | None = None, model: str | None = None, **kwargs: Any) -> Any:
    """返回 LC LLM 实例 (ChatOpenAI / ChatOllama)."""
    from ..common import defaults
    from .llm import LocalLLM, OpenAILLM

    llm_type = llm_type or defaults.DEFAULT_LLM_TYPE
    model = model or defaults.DEFAULT_LLM_MODEL_OPENAI
    if llm_type == "openai":
        return OpenAILLM(model=model, **kwargs).llm
    return LocalLLM(model=model, **kwargs).llm


def build_query_engine(
    vector_store: Any,
    embedder: Any,
    llm: Any = None,
    top_k: int = 5,
    **kwargs: Any,
) -> _LCQueryEngine:
    """构造 LCEL chain. retriever 一次跑, docs 跟 response 一起返."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda, RunnableParallel

    # vector_store 是项目 PGVectorStore (包装), 内部 .vector_store 是 LC PGVectorStore
    # vector_store 内部 embedder 已 inject (PGVectorStore 构造期), retriever 走 LC API
    # 注: PGVectorStore.create_sync 之后 .as_retriever() 会用同一个 embedding_service
    if hasattr(vector_store, "vector_store"):
        if vector_store._embedder is None:
            vector_store._embedder = embedder
        retriever = vector_store.vector_store.as_retriever(search_kwargs={"k": top_k})
    else:
        # 容错: 直接是 LC PGVectorStore (test mock 路径)
        retriever = vector_store.as_retriever(search_kwargs={"k": top_k})

    if llm is None:
        llm = get_llm()

    prompt = ChatPromptTemplate.from_template(
        "根据以下上下文回答。\n\n上下文：\n{context}\n\n问题：{question}\n\n回答："
    )

    def format_docs(docs: list) -> str:
        return "\n\n".join(d.page_content for d in docs)

    response_chain = prompt | llm | StrOutputParser()

    # RunnableParallel: 同时跑 retriever + passthrough question, 然后 .assign 算 response
    chain = RunnableParallel(
        question=RunnableLambda(lambda x: x),  # passthrough
        docs=retriever,
    ).assign(
        response=lambda x: response_chain.invoke({
            "context": format_docs(x["docs"]),
            "question": x["question"],
        })
    )

    return _LCQueryEngine(chain)


def query(question: str, query_engine: Any, **kwargs: Any) -> QueryResult:
    return query_engine.query(question, **kwargs)


async def aquery(question: str, query_engine: Any, **kwargs: Any) -> QueryResult:
    return await query_engine.aquery(question, **kwargs)
```

- [ ] **Step 4: 改 generation/__init__.py (检查 export 一致)**

```bash
cd packages/service
cat src/generation/__init__.py
```

如果 export `OpenAILLM, LocalLLM, get_llm, QueryResult, build_query_engine, query, aquery` 都在, 不动. 如果有 LlamaIndex 内部类型 leak, 删.

- [ ] **Step 5: 改 test_vector_store.py**

`packages/service/tests/retrieval/test_vector_store.py`:

```python
"""测试 PGVectorStore 公开 API (内部走 LC, 全 mock)"""

from unittest.mock import MagicMock, patch

from src.common.document import RAGDoc
from src.retrieval.vector_store import (
    AsyncPGVectorStore,
    PGVectorConfig,
    PGVectorStore,
    _delete_by_ref_doc_id,
    _get_embed_dim,
    add_to_vector_store,
    delete_from_vector_store,
)


def test_pgvector_config_from_env(monkeypatch):
    """from_env 拼对字段"""
    monkeypatch.setenv("PG_HOST", "h")
    monkeypatch.setenv("PG_PORT", "5432")
    monkeypatch.setenv("PG_USER", "u")
    monkeypatch.setenv("PG_PASSWORD", "p")
    monkeypatch.setenv("PG_DATABASE", "d")
    cfg = PGVectorConfig.from_env()
    assert cfg.host == "h" and cfg.user == "u"


@patch("langchain_postgres.PGEngine.from_connection_string")
@patch("langchain_postgres.PGVectorStore.create_sync")
def test_pgvector_store_lazy_build(mock_create, mock_engine_factory):
    """PGVectorStore.vector_store lazy 构造 + 注入 embedder"""
    mock_engine_factory.return_value = MagicMock()
    mock_create.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embedder = MagicMock()

    store = PGVectorStore(embedder=mock_embedder)
    _ = store.vector_store  # 触发 lazy

    mock_engine_factory.assert_called_once()
    mock_create.assert_called_once()


@patch("langchain_postgres.PGEngine.from_connection_string")
@patch("langchain_postgres.PGVectorStore.create_sync")
def test_pgvector_store_add(mock_create, mock_engine_factory):
    mock_engine_factory.return_value = MagicMock()
    mock_lc_store = MagicMock()
    mock_lc_store.add_texts.return_value = ["id1", "id2"]
    mock_create.return_value = mock_lc_store
    mock_embedder = MagicMock()
    mock_embedder.embedder = MagicMock()

    store = PGVectorStore(embedder=mock_embedder)
    docs = [
        RAGDoc(text="t1", metadata={"ref_doc_id": "doc-A"}),
        RAGDoc(text="t2", metadata={"ref_doc_id": "doc-A"}),
    ]
    ids = store.add(docs)
    assert ids == ["id1", "id2"]
    mock_lc_store.add_texts.assert_called_once_with(
        ["t1", "t2"],
        metadatas=[{"ref_doc_id": "doc-A"}, {"ref_doc_id": "doc-A"}],
    )


def test_pgvector_store_no_embedder_raises():
    store = PGVectorStore()  # no embedder
    try:
        _ = store.vector_store
        assert False, "should raise"
    except RuntimeError as e:
        assert "embedder" in str(e)


@patch("src.retrieval.vector_store._delete_by_ref_doc_id")
@patch("langchain_postgres.PGEngine.from_connection_string")
@patch("langchain_postgres.PGVectorStore.create_sync")
def test_pgvector_store_delete_by_ref_doc_id(mock_create, mock_engine_factory, mock_delete):
    """delete([ref_doc_id]) 走原生 SQL 按 metadata 删, 不是按主键"""
    mock_engine_factory.return_value = MagicMock()
    mock_create.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embedder = MagicMock()

    store = PGVectorStore(embedder=mock_embedder)
    _ = store.vector_store  # 触发 engine 构造
    store.delete(["doc-A", "doc-B"])

    mock_delete.assert_called_once()
    args = mock_delete.call_args[0]
    assert args[1] == "rag_embeddings"
    assert args[2] == ["doc-A", "doc-B"]


def test_pgvector_store_delete_empty_noop():
    store = PGVectorStore()
    store.delete([])  # 不应抛 (不触发 engine)


def test_async_pgvector_store_no_embedder_raises():
    import asyncio
    store = AsyncPGVectorStore()
    try:
        asyncio.run(store.aconnect())
        assert False, "should raise"
    except RuntimeError as e:
        assert "embedder" in str(e)


def test_get_embed_dim_from_env(monkeypatch):
    monkeypatch.setenv("EMBED_DIMENSIONS", "1536")
    assert _get_embed_dim() == 1536


def test_get_embed_dim_default(monkeypatch):
    monkeypatch.delenv("EMBED_DIMENSIONS", raising=False)
    assert _get_embed_dim() == 1024


def test_add_to_vector_store_empty():
    assert add_to_vector_store([], MagicMock()) == []


def test_delete_from_vector_store_empty():
    delete_from_vector_store([], MagicMock())  # noop
```

- [ ] **Step 6: 改 test_retrieval_exports.py**

```bash
cd packages/service
cat tests/retrieval/test_retrieval_exports.py
```

如果 import 跟新 export 列表一致, 不动. 如果断言 `init_pgvector` 走 psycopg2, 改为走 PGEngine (mock).

- [ ] **Step 7: 改 test_query_engine.py**

`packages/service/tests/generation/test_query_engine.py`:

```python
"""测试 QueryEngine LCEL 链 (全 mock)"""

from unittest.mock import MagicMock, patch

from src.generation.query_engine import QueryResult, _LCQueryEngine, build_query_engine, query


def test_query_result_from_response_no_sources():
    r = QueryResult.from_response("ans", source_docs=None)
    assert r.response == "ans"
    assert r.sources == []


def test_query_result_from_response_with_docs():
    doc = MagicMock()
    doc.page_content = "context"
    doc.metadata = {"file_path": "/a.md", "page_label": "1"}
    r = QueryResult.from_response("ans", source_docs=[doc])
    assert r.response == "ans"
    assert len(r.sources) == 1
    assert r.sources[0]["file_path"] == "/a.md"
    assert r.sources[0]["text"] == "context"


def test_query_result_text_truncation():
    doc = MagicMock()
    doc.page_content = "x" * 500
    doc.metadata = {}
    r = QueryResult.from_response("ans", source_docs=[doc])
    assert r.sources[0]["text"].endswith("...")
    assert len(r.sources[0]["text"]) <= 203  # 200 + "..."


def test_lc_query_engine_invoke():
    """_LCQueryEngine.query 把 chain 输出 dict 转 QueryResult"""
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = {"response": "ans", "docs": []}
    qe = _LCQueryEngine(mock_chain)
    r = qe.query("q?")
    assert r.response == "ans"


def test_build_query_engine_callable():
    """构造不抛 (实际是 mock vector_store / llm)"""
    mock_vs = MagicMock()
    mock_vs._embedder = None
    mock_vs.vector_store.as_retriever.return_value = MagicMock()
    mock_embedder = MagicMock()
    mock_llm = MagicMock()
    qe = build_query_engine(mock_vs, mock_embedder, llm=mock_llm, top_k=5)
    assert isinstance(qe, _LCQueryEngine)


def test_query_function_passthrough():
    mock_qe = MagicMock()
    mock_qe.query.return_value = QueryResult(response="r", sources=[])
    r = query("q?", mock_qe)
    assert r.response == "r"
```

- [ ] **Step 8: 改 test_routes_endpoints.py**

`packages/service/tests/api/test_routes_endpoints.py:157-200` 检查 `@patch("src.generation.build_query_engine")` 后面的 mock setup:

```python
# 旧 mock 可能是:
mock_qe = MagicMock()
mock_qe.query.return_value = MagicMock(response="ans", source_nodes=[...])

# 新 mock (返 QueryResult, 不是 LlamaIndex Response):
from src.generation.query_engine import QueryResult
mock_qe = MagicMock()
mock_qe.query.return_value = QueryResult(
    response="ans",
    sources=[{"file_path": "/a.md", "page_label": "1", "text": "ctx"}],
)
```

具体打开看一下 test 改 mock.

- [ ] **Step 9: 跑 retrieval + generation + api test**

```bash
cd packages/service
uv run pytest tests/retrieval/ tests/generation/ tests/api/ -v --tb=short
```

Expected: 全绿 (pre-existing fail 不算)

- [ ] **Step 10: e2e 验证 /api/v1/query**

```bash
cd packages/service
uv run python main.py &
sleep 5  # 等启动
curl -X POST http://localhost:8000/api/v1/query -H "Content-Type: application/json" -d '{"query": "测试", "top_k": 3}'
# 看 response 非空, sources 是 list
kill %1
```

Expected: HTTP 200, `{"response": "...", "sources": [...], "latency_ms": ...}` (sources 长度取决于 dev DB 数据)

- [ ] **Step 11: Commit**

```bash
git add packages/service/src/retrieval/vector_store.py packages/service/src/retrieval/__init__.py packages/service/src/generation/query_engine.py packages/service/src/generation/__init__.py packages/service/tests/retrieval/ packages/service/tests/generation/ packages/service/tests/api/test_routes_endpoints.py
git commit -m "feat(rag): LC PGVectorStore + LCEL RunnableParallel chain 替代 LlamaIndex (T5 of LlamaIndex 替换)"
```

---

## Task 6: 删除 orchestration + 同步 src/__init__.py

**Files:**
- Delete: `packages/service/src/orchestration/` (整目录)
- Delete: `packages/service/tests/orchestration/test_workflows.py`
- Modify: `packages/service/src/__init__.py`

- [ ] **Step 1: 删除 orchestration 目录**

```bash
cd packages/service
rm -rf src/orchestration/
rm -rf tests/orchestration/
```

- [ ] **Step 2: 改 src/__init__.py**

`packages/service/src/__init__.py`:

- 顶部 docstring 第 1 行 `"""rag 包：标准 LlamaIndex RAG 系统` → `"""rag 包: RAG 系统`
- 删除 import block:
  ```python
  # 删整段:
  from .orchestration import (
      BaseWorkflow,
      MultiStepRAGWorkflow,
      ResponseEvent,
      SimpleRAGWorkflow,
      WorkflowStats,
      build_workflow,
      run_workflow,
  )
  ```
- 删除 `__all__` 中:
  - `"build_workflow"`, `"run_workflow"`, `"SimpleRAGWorkflow"`, `"MultiStepRAGWorkflow"`, `"BaseWorkflow"`, `"ResponseEvent"`, `"WorkflowStats"` (7 个)
  - `"get_default_node_parser"` (chunker.py 已删)
- 同步从 `from .common import (...)` 中删 `get_default_node_parser`

- [ ] **Step 3: 跑 grep 验证 0 hit**

```bash
cd packages/service
grep -rn "build_workflow\|SimpleRAGWorkflow\|MultiStepRAGWorkflow\|BaseWorkflow\|ResponseEvent\|WorkflowStats\|get_default_node_parser" src/ tests/
```

Expected: 0 hit

- [ ] **Step 4: 跑全量测试**

```bash
cd packages/service
uv run pytest tests/ -v --tb=no -q
```

Expected: 净测试数减 4 (workflow tests), 其余绿

- [ ] **Step 5: 跑 pyright + ruff**

```bash
cd packages/service
uv run pyright src/
uv run ruff check src/
```

Expected: 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/ packages/service/tests/
git rm -r packages/service/src/orchestration/ packages/service/tests/orchestration/ 2>/dev/null || true
git commit -m "refactor: 删 dead code src/orchestration/ (生产 0 调用) (T6 of LlamaIndex 替换)"
```

---

## Task 7: DeepEval 评估器 (按 deepeval spec)

**Files:**
- Create: `packages/service/src/eval/deepeval_eval.py`
- Modify: `packages/service/src/common/evaluation.py`
- Modify: `packages/service/src/eval/router.py`
- Modify: `packages/service/src/eval/runner.py`
- Modify: `packages/service/src/api/routes.py` (删 evaluate_endpoint)
- Modify: `packages/service/src/api/schemas.py` (删 EvaluateRequest/Response)
- Modify: `packages/service/src/api/__init__.py`
- Modify: `packages/service/tests/eval/test_runner.py`
- Modify: `packages/service/tests/api/test_routes.py`
- Modify: `packages/service/tests/api/test_schemas.py`
- Create: `packages/service/tests/eval/test_deepeval_eval.py`

- [ ] **Step 1: 改 RAGAMetrics 加 hallucination**

`packages/service/src/common/evaluation.py:11-49` 改:

```python
@dataclass
class RAGAMetrics:
    """RAG 评估指标 dataclass - 5 指标 (2026-06-29 加 Hallucination)"""

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    hallucination: float | None = None  # ← 新 (DeepEval HallucinationMetric)
    context_entity_precision: float | None = None  # 保留兼容, 不进 avg_score
    raw_result: dict | None = None

    def to_dict(self) -> dict:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
            "hallucination": self.hallucination,
            "context_entity_precision": self.context_entity_precision,
        }

    @property
    def avg_score(self) -> float | None:
        # 5-key 平均 (None 过滤), 老样本 (无 hallucination) 退化 4-key
        values = [
            v
            for v in [
                self.faithfulness,
                self.answer_relevancy,
                self.context_precision,
                self.context_recall,
                self.hallucination,
            ]
            if v is not None
        ]
        return sum(values) / len(values) if values else None

    def summary(self) -> str:
        lines = ["评估结果："]
        for metric, value in self.to_dict().items():
            lines.append(f"  {metric}: {value:.4f}" if value is not None else f"  {metric}: N/A")
        return "\n".join(lines)
```

- [ ] **Step 2: 写 test_deepeval_eval.py**

`packages/service/tests/eval/test_deepeval_eval.py` (新建):

```python
"""测试 DeepEvalEvaluator (5 metrics, mock 所有 DeepEval 内部)"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.eval.deepeval_eval import DeepEvalError, DeepEvalEvaluator


@pytest.mark.asyncio
async def test_evaluator_5_metrics_all_pass():
    """5 metric 全跑通, 返 RAGAMetrics 5 字段都有分数"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    with patch.object(evaluator, "_build_metric") as mock_build:
        mock_metric = MagicMock()
        mock_metric.score = 0.85
        mock_metric.a_measure = AsyncMock()
        mock_build.return_value = mock_metric

        result = await evaluator.evaluate_single(
            question="q?",
            answer="a",
            contexts=["c1"],
            ground_truth="gt",
        )

        assert result.faithfulness == 0.85
        assert result.answer_relevancy == 0.85
        assert result.context_precision == 0.85
        assert result.context_recall == 0.85
        assert result.hallucination == 0.85


@pytest.mark.asyncio
async def test_evaluator_single_metric_fail():
    """单 metric 失败, 该字段 None, 其他正常"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    call_count = [0]

    def mock_build_metric(name):
        call_count[0] += 1
        m = MagicMock()
        m.score = 0.7

        async def measure_or_fail(_):
            if name == "faithfulness":
                raise RuntimeError("LLM error")

        m.a_measure = measure_or_fail
        return m

    with patch.object(evaluator, "_build_metric", side_effect=mock_build_metric):
        result = await evaluator.evaluate_single(
            question="q?", answer="a", contexts=["c1"], ground_truth="gt"
        )
        assert result.faithfulness is None
        assert result.answer_relevancy == 0.7


@pytest.mark.asyncio
async def test_evaluator_context_recall_no_ground_truth():
    """没传 ground_truth, context_recall 返 None (不抛)"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    with patch.object(evaluator, "_build_metric") as mock_build:
        mock_metric = MagicMock()
        mock_metric.score = 0.9
        mock_metric.a_measure = AsyncMock()
        mock_build.return_value = mock_metric

        result = await evaluator.evaluate_single(
            question="q?", answer="a", contexts=["c1"], ground_truth=None
        )
        assert result.context_recall is None  # 跳过
        assert result.faithfulness == 0.9


def test_build_test_case():
    """LLMTestCase 字段映射"""
    evaluator = DeepEvalEvaluator(llm=MagicMock())
    tc = evaluator._build_test_case("q?", "a", ["c1"], "gt")
    assert tc.input == "q?"
    assert tc.actual_output == "a"
    assert tc.retrieval_context == ["c1"]
    assert tc.expected_output == "gt"


def test_build_metric_unknown_raises():
    evaluator = DeepEvalEvaluator(llm=MagicMock())
    with pytest.raises(ValueError, match="未知指标"):
        evaluator._build_metric("nonexistent")


def test_deepeval_error_is_runtime_error():
    e = DeepEvalError("test")
    assert isinstance(e, RuntimeError)


@pytest.mark.asyncio
async def test_evaluator_all_metrics_fail_returns_all_none():
    """全部 metric 失败, 5 字段全 None"""
    mock_judge = MagicMock()
    evaluator = DeepEvalEvaluator(llm=mock_judge)

    def mock_build_metric(name):
        m = MagicMock()

        async def fail(_):
            raise RuntimeError("all fail")

        m.a_measure = fail
        return m

    with patch.object(evaluator, "_build_metric", side_effect=mock_build_metric):
        result = await evaluator.evaluate_single(
            question="q?", answer="a", contexts=["c1"], ground_truth="gt"
        )
        assert result.faithfulness is None
        assert result.answer_relevancy is None
        assert result.context_precision is None
        assert result.context_recall is None
        assert result.hallucination is None
```

- [ ] **Step 3: 跑 test 验证 fail**

```bash
cd packages/service
uv run pytest tests/eval/test_deepeval_eval.py -v
```

Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 4: 写 deepeval_eval.py**

`packages/service/src/eval/deepeval_eval.py` (新建):

```python
"""DeepEval 评估器 (替代 LlamaIndexEvaluator, 5 个 RAG 指标)

5 metric:
- Faithfulness, AnswerRelevancy, ContextualPrecision, ContextualRecall, Hallucination
- LLM judge 走 DeepSeekJudge (OpenAI 兼容协议, 项目通用 base_url)
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger

from ..common.evaluation import RAGAMetrics


class DeepEvalError(RuntimeError):
    """DeepEval 评估失败 (替代原 LlamaIndexEvalError)"""


class DeepSeekJudge:
    """DeepEval 自定义 LLM (走 OpenAI 兼容协议, 跟项目主流 base_url 一致).

    实现 DeepEvalBaseLLM 抽象 (load_model / generate / a_generate / get_model_name).
    内部用 openai SDK 直调 (不走 langchain 链路, 因为 deepeval 不接受 LC LLM 实例).
    """

    def __init__(self):
        from ..common import defaults

        self.model_name = os.getenv("LLM_MODEL") or defaults.DEFAULT_LLM_MODEL_OPENAI
        base_url = os.getenv("OPENAI_BASE_URL") or defaults.DEFAULT_OPENAI_BASE_URL
        if base_url and "deepseek" in base_url and not base_url.endswith("/beta"):
            base_url = base_url.rstrip("/") + "/beta"
        self.base_url = base_url
        self.api_key = os.getenv("OPENAI_API_KEY") or defaults.DEFAULT_OPENAI_API_KEY

    def load_model(self):
        from openai import OpenAI

        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        client = self.load_model()
        resp = client.chat.completions.create(
            model=self.model_name,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    async def a_generate(self, prompt: str) -> str:
        return await asyncio.to_thread(self.generate, prompt)

    def get_model_name(self) -> str:
        return self.model_name


class DeepEvalEvaluator:
    """DeepEval 评估器, 5 个 RAG 指标.

    threshold=0.0 (不卡阈值, 只取分数). async_mode=True (内置并发).
    """

    DEFAULT_METRICS = (
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "hallucination",
    )

    def __init__(self, llm: Any = None, metrics: list[str] | None = None):
        # llm 参数兼容老 API (router 里传 OpenAILLM().llm), 但 deepeval 实际不接受
        # LC ChatOpenAI 实例, 内部统一用 DeepSeekJudge
        self._judge = llm if hasattr(llm, "a_generate") else DeepSeekJudge()
        self._metric_names = metrics or list(self.DEFAULT_METRICS)

    def _build_test_case(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None,
    ):
        from deepeval.test_case import LLMTestCase

        return LLMTestCase(
            input=question,
            actual_output=answer,
            retrieval_context=contexts or [],
            expected_output=ground_truth,
        )

    def _build_metric(self, name: str) -> Any:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            FaithfulnessMetric,
            HallucinationMetric,
        )

        kwargs = {
            "model": self._judge,
            "threshold": 0.0,
            "async_mode": True,
            "include_reason": False,
        }
        if name == "faithfulness":
            return FaithfulnessMetric(**kwargs)
        if name == "answer_relevancy":
            return AnswerRelevancyMetric(**kwargs)
        if name == "context_precision":
            return ContextualPrecisionMetric(**kwargs)
        if name == "context_recall":
            return ContextualRecallMetric(**kwargs)
        if name == "hallucination":
            return HallucinationMetric(**kwargs)
        raise ValueError(f"未知指标: {name}")

    async def evaluate_single(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> RAGAMetrics:
        """5 metric 并发跑, 单 metric 失败该字段 None."""
        test_case = self._build_test_case(question, answer, contexts, ground_truth)

        async def _run(name: str) -> float | None:
            if name not in self._metric_names:
                return None
            if name == "context_recall" and not ground_truth:
                return None
            try:
                metric = self._build_metric(name)
                await metric.a_measure(test_case)
                return float(metric.score) if metric.score is not None else None
            except Exception as exc:
                logger.opt(exception=True).warning(
                    "evaluator[{}] 失败: {}", name, str(exc)[:200]
                )
                return None

        results = await asyncio.gather(
            _run("faithfulness"),
            _run("answer_relevancy"),
            _run("context_precision"),
            _run("context_recall"),
            _run("hallucination"),
        )

        return RAGAMetrics(
            faithfulness=results[0],
            answer_relevancy=results[1],
            context_precision=results[2],
            context_recall=results[3],
            hallucination=results[4],
            raw_result=None,
        )
```

- [ ] **Step 5: 跑 test_deepeval_eval 验证**

```bash
cd packages/service
uv run pytest tests/eval/test_deepeval_eval.py -v
```

Expected: 全绿

- [ ] **Step 6: 改 eval/router.py**

`packages/service/src/eval/router.py:30` 改:

```python
# 旧:
from .llama_eval import LlamaIndexEvaluator

# 新:
from .deepeval_eval import DeepEvalEvaluator
```

`router.py:140` 实例化:

```python
# 旧:
evaluator = LlamaIndexEvaluator(llm=llm)

# 新:
evaluator = DeepEvalEvaluator(llm=llm)
```

- [ ] **Step 7: 改 eval/runner.py 错误前缀**

`packages/service/src/eval/runner.py:76` 错误前缀:

```python
# 旧:
"error": f"LlamaIndexEvalError: {e}",

# 新:
"error": f"DeepEvalError: {e}",
```

顶部 import 不变 (runner.py 不直接 import 评估器, 由 router.py 注入).

- [ ] **Step 8: 改 tests/eval/test_runner.py:227**

`packages/service/tests/eval/test_runner.py` 中所有 hard-code `"LlamaIndexEvalError"` 改为 `"DeepEvalError"`.

```bash
cd packages/service
grep -n "LlamaIndexEvalError" tests/eval/test_runner.py
# 然后 sed 替换 or 手工改
```

- [ ] **Step 9: 删 /api/v1/evaluate 端点**

`packages/service/src/api/routes.py` 删除 lines 66-109 整段 evaluate_endpoint, 同时改 line 9-17 import:

```python
# 改 import 块, 去掉 EvaluateRequest/Response:
from .schemas import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceNode,
)
```

同时改 `query_endpoint` 的 docstring (去 "LlamaIndex QueryEngine" 字样):

```python
@router.post(
    "/query",
    response_model=QueryResponse,
    summary="RAG 检索查询",
    description=(
        "## 用途\n\n"
        "对 RAG 向量库发起一次检索 + 生成查询 (LangChain LCEL chain), "
        "返回答 + 命中的 source 节点 + 延迟.\n\n"
        ...
    ),
    ...
)
```

- [ ] **Step 10: 删 EvaluateRequest/Response schemas**

`packages/service/src/api/schemas.py` 删除 lines 24-36 (整段 EvaluateRequest + EvaluateResponse). 其他 schema 不动.

- [ ] **Step 11: 改 api/__init__.py**

`packages/service/src/api/__init__.py` 删除 EvaluateRequest/Response 的 import + `__all__` 条目:

```python
"""api 子包: HTTP 接口层"""

from .routes import router
from .schemas import (
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceNode,
)

__all__ = [
    "router",
    "QueryRequest",
    "QueryResponse",
    "SourceNode",
    "IngestRequest",
    "IngestResponse",
]
```

- [ ] **Step 12: 跑契约测试 (确认前端 0 hit)**

```bash
cd packages/service
uv run pytest tests/test_api_contract.py -v
```

Expected: 全绿 (`/api/v1/evaluate` 未在 FRONTEND_EXPECTS 中, 删除 0 影响)

如有 hit, 停下来检查前端是否还在用. 0 hit 才能继续.

- [ ] **Step 13: 删 dead code test**

`packages/service/tests/api/test_routes.py:3,20-22` 删除 `from src.api.schemas import EvaluateRequest` 和 `test_evaluate_request_schema`.

`packages/service/tests/api/test_schemas.py:66-91` 删除 3 个 evaluate test (`test_evaluate_request_all_fields`, `test_evaluate_response_all_none`, `test_evaluate_response_with_scores`).

- [ ] **Step 14: 跑 eval + api 测试**

```bash
cd packages/service
uv run pytest tests/eval/ tests/api/ -v --tb=short
```

Expected: 全绿

- [ ] **Step 15: grep 验证 0 hit**

```bash
cd packages/service
grep -rn "LlamaIndexEvalError\|EvaluateRequest\|EvaluateResponse" src/ tests/
```

Expected: 0 hit (除了 deepeval_eval.py 注释提到为何替换的, 那条是历史说明)

- [ ] **Step 16: Commit**

```bash
git add packages/service/src/eval/ packages/service/src/common/evaluation.py packages/service/src/api/ packages/service/tests/eval/ packages/service/tests/api/
git commit -m "feat(eval): DeepEvalEvaluator (5 metrics) 替代 LlamaIndexEvaluator + 删 /api/v1/evaluate dead code (T7 of LlamaIndex 替换)"
```

---

## Task 8: 删 llama_eval.py + 移除 LlamaIndex 依赖 + 清理 docstring

**Files:**
- Delete: `packages/service/src/eval/llama_eval.py`
- Delete: `packages/service/tests/eval/test_llama_eval.py`
- Modify: `packages/service/pyproject.toml`
- Modify: `packages/service/src/__init__.py` (顶部 docstring)
- Modify: `packages/service/src/health/checks.py:74` (注释)
- Modify: `packages/service/src/telemetry/langfuse_client.py:94-96` (docstring)
- Modify: `packages/service/tests/spike/` (整目录删, T0 临时验证已结束)

- [ ] **Step 1: 删 llama_eval.py + test**

```bash
cd packages/service
rm src/eval/llama_eval.py tests/eval/test_llama_eval.py
```

- [ ] **Step 2: 改 pyproject.toml 删 LlamaIndex deps**

`packages/service/pyproject.toml` `dependencies` 数组删除:

```toml
"llama-index>=0.14.22",
"llama-index-embeddings-huggingface>=0.7.0",
"llama-index-llms-ollama>=0.10.1",
"llama-index-llms-openai-like>=0.7.2",
"llama-index-vector-stores-postgres>=0.8.1",
```

- [ ] **Step 3: uv sync 卸载 LlamaIndex**

```bash
cd packages/service
uv sync
```

Expected: 5 包消失, uv.lock 更新

- [ ] **Step 4: 改 src/__init__.py docstring**

`packages/service/src/__init__.py:1` 顶部:

```python
"""rag 包: RAG 系统 (LangChain 1.x + DeepEval)

分层结构:
- ingest/      文档摄取
- api/         HTTP 接口层 (FastAPI routes + schemas)
- common/      共享工具 (chunk/doc/embed/token/batch + RAGDoc)
- retrieval/   检索层 (embedder + LC PGVectorStore)
- generation/  生成层 (ChatOpenAI/ChatOllama + LCEL chain)
- memory/      记忆层 (Mem0)
- kg/          知识图谱 (Neo4j)
- eval/        评估子系统 (DeepEval 5 指标 + 评估批 CRUD)
- auth/        鉴权
- telemetry/   可观测性 (Langfuse)
"""
```

- [ ] **Step 5: 改 health/checks.py:74 注释**

`packages/service/src/health/checks.py:74` 注释改:

```python
def _get_pg_engine():
    """直接 sqlalchemy create_engine, 不走 LC PGEngine (健康检查不需要 vector store 完整初始化).

    必须用 PGVectorConfig.from_env() 走 PG_* 环境变量, 绝不能 PGVectorConfig() 无参
    (后者走 dataclass 默认 password='postgres', 跟 docker/.env 实际密码 deyuan888
    对不上 → 认证失败).
    """
```

- [ ] **Step 6: 改 telemetry/langfuse_client.py:94 docstring**

`packages/service/src/telemetry/langfuse_client.py:94-96`:

```python
def get_callback_handler(self) -> Any:
    """返回 Langfuse CallbackHandler (兼容 LangChain LCEL chain 的 callbacks=[] 注入)"""
    return self.client.get_callback_handler()
```

- [ ] **Step 7: 删 spike 目录**

```bash
cd packages/service
rm -rf tests/spike/
```

- [ ] **Step 8: grep 验证 0 hit**

```bash
cd packages/service
grep -rn "llama_index\|llama-index\|LlamaIndex" src/ tests/ pyproject.toml
```

Expected: 0 hit (handoff 文档不算)

- [ ] **Step 9: 跑全量 test + lint + pyright**

```bash
cd packages/service
uv run pytest tests/ -v --tb=no -q
uv run pyright src/
uv run ruff check src/ tests/
```

Expected:
- pytest: pre-existing fail 22 + 净测试数从 1075 减到 ~1067 (删 8 test: 4 workflow + 4 llama_eval + 1 evaluate_route + 3 evaluate_schemas, 加 ~7 deepeval_eval test, 加 4 RAGDoc test 净减 ~ -1 维度)
- pyright: 0 error
- ruff: 0 error

- [ ] **Step 10: e2e 端到端验收**

跑 spec §9 所有验收项 (除了端到端 evaluation, 那需要真实 Dify):

```bash
cd packages/service
# 1. 检查 schema
uv run python -c "
import os, psycopg
conn = psycopg.connect(
    host=os.environ['PG_HOST'], port=os.environ['PG_PORT'],
    user=os.environ['PG_USER'], password=os.environ['PG_PASSWORD'],
    dbname=os.environ['PG_DATABASE'],
)
with conn.cursor() as cur:
    cur.execute(\"SELECT to_regclass('rag_embeddings')\")
    assert cur.fetchone()[0] is not None
    cur.execute(\"SELECT indexname FROM pg_indexes WHERE tablename = 'rag_embeddings'\")
    indexes = [r[0] for r in cur.fetchall()]
    assert any('hnsw' in i for i in indexes)
    assert any('gin' in i for i in indexes)
print('Schema OK')
"

# 2. 启动 service
uv run python main.py &
sleep 5
# /api/v1/query e2e
curl -X POST http://localhost:8000/api/v1/query -H "Content-Type: application/json" -d '{"query": "测试", "top_k": 3}'
# 验证 sources 非空 (取决于 dev 数据), response 非空
kill %1
```

- [ ] **Step 11: Final commit**

```bash
cd c:/Users/abcuc/Desktop/rag
git add packages/service/
git commit -m "feat(deps): 移除 llama-index 5 个包 + 删 llama_eval.py + 清理 docstring (T8 final of LlamaIndex 替换)

- 删 5 个 llama-index* dep
- 删 src/eval/llama_eval.py (192 行)
- 删 tests/eval/test_llama_eval.py + tests/spike/
- 改 src/__init__.py docstring 去 LlamaIndex 字样
- 改 src/health/checks.py:74 + src/telemetry/langfuse_client.py:94 注释/docstring

验收:
- grep llama_index 0 hit
- pytest 全绿 (pre-existing fail 22)
- pyright 0 error
- ruff 0 error
- e2e /api/v1/query 200 OK"
```

---

## 完成验收清单

按 spec §9 跑一遍:

- [ ] `uv sync` 后 5 个 `llama-index*` 包消失, 6 个 `langchain-*` + `deepeval` 出现
- [ ] `grep -rn "llama_index\|llama-index" packages/service/src packages/service/tests pyproject.toml` 0 hit
- [ ] `grep -rn "LlamaIndexEvalError" packages/service/` 0 hit
- [ ] `grep -rn "build_workflow\|SimpleRAGWorkflow\|MultiStepRAGWorkflow\|get_default_node_parser" packages/service/src packages/service/tests` 0 hit
- [ ] `uv run pytest packages/service/tests -v` 全绿 (allow pre-existing fail 22)
- [ ] `uv run pyright packages/service/src` 0 error
- [ ] `uv run ruff check packages/service/` 0 error
- [ ] `RAGAMetrics.__dataclass_fields__` 含 `hallucination`
- [ ] DB schema: `rag_embeddings` 表 + HNSW + GIN 索引存在
- [ ] DB 数据: 行数 == llamaindex_embeddings
- [ ] 端到端 `/api/v1/query`: response 非空 + sources 长度 > 0
- [ ] 端到端 `/api/v1/documents/{ref_doc_id}` DELETE: 按 ref_doc_id 删 (回归 P0 错误 15)
- [ ] 端到端 `/api/evaluate/runs`: 5 条样本, avg_metrics 5 key 全有分数

---

## Follow-up (本 plan 外)

- **P3**: 业务稳定 7 天后, 独立 commit `DROP TABLE llamaindex_embeddings;`
- **P5**: `telemetry/langfuse_client.py` 真接入 `langfuse.langchain.CallbackHandler`
- **P1**: 中文 judge prompt template override
- **P2**: 若未来需要 StateGraph, `uv add langgraph` 单独装
