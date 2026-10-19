# LangChain 生态替换 LlamaIndex (2026-06-29)

> Status: **DRAFT v2.2 — Spike 验证后 (T0 完成, 3 偏差合入)**
> 目标: 把 `packages/service/src/` 下所有 LlamaIndex 调用 (10 文件, ~60 行 runtime 代码)
> 全量替换为 LangChain 生态 (`langchain-openai` / `langchain-ollama` / `langchain-postgres` /
> `langchain-text-splitters`) + DeepEval 评估 (替换 `llama_eval.py`).
>
> 顺手做的清理:
> - 删除 `src/orchestration/` 整个目录 (生产 0 调用)
> - 删除 `/api/v1/evaluate` dead code (按 deepeval spec §5.5)
>
> 对外 API (FastAPI routes / OpenAPI schema / HTTP 返回格式) **100% 不变**.
> 但内部 dataclass 字段语义变化 (`source_nodes` 装 LC `Document` 而非 LlamaIndex `NodeWithScore`),
> 详见 §8.5.
>
> **v2.2 修订 (基于 spike T0 实测发现, 详 [handoffs/2026-06-29-langchain-postgres-spike.md](../../handoffs/2026-06-29-langchain-postgres-spike.md))**:
> - `langchain_metadata` 列 LC 默认建是 **json** 不是 jsonb, 跟项目 CLAUDE.md JSONB 规约冲突 →
>   `init_pgvector()` 跑完 `init_vectorstore_table` 后必须 ALTER 转 jsonb + 建 GIN
> - `init_vectorstore_table` **不自动建 vector index** (只有 pkey), 必须显式调
>   `store.apply_vector_index(HNSWIndex(...))` 才有 HNSW
> - `PGEngine.close()` 是 coroutine, 同步路径 close 不能用; raw SQL DELETE 走独立 SA Engine
>   (业务持有 2 engine: PGEngine + SQLAlchemy Engine)
> - `OpenAIEmbeddings` 跟 SiliconFlow bge-m3: 不传 `dimensions`, 传
>   `check_embedding_ctx_length=False` (bge-m3 服务端固定 1024 维 + 用 XLM-RoBERTa tokenizer)
> - Windows dev 跑 LC async (psycopg3) 需 `asyncio.WindowsSelectorEventLoopPolicy` (生产 Linux 不受影响)

> **v2 修订说明 (基于对抗审查)**:
> - §5.6 重写 PGVectorStore: 用真实 `PGVectorStore.create_sync(engine=PGEngine, ...)` 工厂 API,
>   不是 deprecated `PGVector` 构造法
> - §5.6 新增 `ref_doc_id` 解决方案: 塞 metadata JSONB, delete 按 metadata 过滤 (而非主键)
> - §5.7 LCEL 链改 `RunnableParallel` 一次跑, 不双跑 retriever
> - §5.3 RecursiveCharacterTextSplitter 显式传中文 separators
> - §10 补 buyer_profile / health / telemetry / common/__init__ / src/__init__ docstring 改动
> - §7 commit 顺序加 "老表保留 7 天" 防数据丢
> - §9 验收语义对齐改为具体 embedding cosine 阈值

## 1. 背景与动机

`packages/service/src/` 当前 10 个文件 35 处提及 `llama_index`, 但实际 runtime 调用集中在
约 22 行 import + 40 行调用:

| 模块 | LlamaIndex 用法 | 行数 |
|---|---|---|
| `generation/llm.py` | `OpenAILike`, `Ollama` (2 行 import) | 2 |
| `generation/query_engine.py` | `VectorStoreIndex.from_vector_store`, `VectorIndexRetriever` | 2 |
| `retrieval/embedder.py` | `OpenAIEmbedding` | 1 |
| `retrieval/vector_store.py` | `PGVectorStore`, `TextNode`, `VectorStoreQuery` | 5 |
| `common/chunker.py` | `SentenceSplitter`, `Document` | 2 |
| `common/document_loader.py` | `Document` | 4 |
| `orchestration/{simple,multi_step}_rag.py` | `VectorStoreIndex`, `VectorIndexRetriever` | 4 |
| `eval/llama_eval.py` | 3 个 Evaluator + `EvaluationResult` | 4 |

**LlamaIndex 实际问题**:

| 问题 | 表现 |
|---|---|
| 生态不如 LangChain 主流 | 工具链 / Agent / Tool Calling 集成稀疏 |
| Workflow 抽象薄弱 | 自建 `BaseWorkflow` (基类 60 行) 在模仿 LlamaIndex 但实际没人用 |
| 评估器跟主流 API 不一致 | `aevaluate(query=, response=, contexts=)` vs DeepEval/RAGAS `LLMTestCase` |
| 调用方对 LlamaIndex 内部细节耦合 | `VectorIndexRetriever` 重命名过 (`VectorStoreRetriever`), 升级风险 |
| 维护两套抽象 (LlamaIndex 评估 + 自实现 ContextRecall) | 160 行手写 |

**LangChain 一次性解决**:

- 模型抽象统一: `ChatOpenAI` (含 OpenAI 兼容协议) + `ChatOllama` + `OpenAIEmbeddings`
- 向量库走官方包 `langchain-postgres` (PG + pgvector 主流方案)
- 文本切分走 `langchain-text-splitters.RecursiveCharacterTextSplitter` (主流)
- LCEL 链式组合替代 `VectorStoreIndex.from_vector_store` 重抽象
- Future-proof: LangGraph 已是 LangChain 0.3+ 底层运行时, 后续要加 Agent / 多步 / 有状态
  RAG 可直接用 StateGraph 接入

## 2. 目标 (in-scope)

1. **替换所有 LlamaIndex runtime 调用**: 改 10 个 src 文件 + 8 个 test 文件 import
2. **保留对外 API 100% 不变**: `build_query_engine`, `query`, `aquery`, `QueryResult`,
   `OpenAILLM`, `LocalLLM`, `OpenAIEmbedder`, `PGVectorStore`, `AsyncPGVectorStore`,
   `PGVectorConfig`, `chunk_documents`, `load_md_files` 等所有公开 API 同名同语义
3. **`Document` 类换 `RAGDoc` (自定义 dataclass)**: 公开类型从 `llama_index.core.schema.Document`
   换 `src.common.document.RAGDoc`, 调用方 `.get_content()` 接口不变
4. **评估器换 DeepEval**: 按 `2026-06-16-deepeval-replace-llamaindex-design.md` §5 实施 (5 metric)
5. **删 dead code**: `src/orchestration/` 整目录 (生产 0 调用) + `/api/v1/evaluate` (按
   deepeval spec §5.5)
6. **依赖清理**: pyproject.toml 移除 `llama-index*` (5 个包), 新增 `langchain-*` (4 个包) + `deepeval`
7. **数据迁移**: pgvector 数据库 schema 需要从 `llamaindex_embeddings` 单表迁移到
   LangChain 标准的 `langchain_pg_embedding` + `langchain_pg_collection` 双表结构.
   `init_pgvector()` 同步更新为建 LC schema (`langchain_pg_*` 表 + HNSW 索引).
   数据迁移由 Plan 阶段实施一次性 SQL 脚本

## 3. 非目标 (out-of-scope, YAGNI)

- **不引入 DeepAgent** (deepagents 包) — 当前项目无多 Agent / 任务分解需求
- **不引入 LangGraph** (`langgraph` 是独立 PyPI 包, 当前 1.2.6, 跟 `langchain-core`
  互不内嵌; LCEL 链编译成 LangChain 自己的 `Runnable` 图, 不是 LangGraph `Pregel` 图).
  本 spec 仅替换 LlamaIndex 到 LangChain 生态, **不动 Workflow 抽象** (直接删 dead code).
  未来真要 StateGraph / Checkpoint / Human-in-the-loop 再单独 `uv add langgraph`
- **不改 pgvector 业务字段语义** — 表结构换 LC 标准 (`langchain_pg_embedding`), 但
  embedding 数据需迁移 (dev 环境直接重 ingest, prod 走一次性 SQL 迁移)
- **不重构 `src/api/routes.py` 业务逻辑** — 仅改 import + 内部调用
- **不动 Dify 聊天链路** — `chat/`, `chat_share/`, `integrations/dify_client.py` 0 改动
- **不动 KG / Neo4j / Mem0 链路** — 跟 LlamaIndex 无关
- **不动 Langfuse telemetry 模块** — 跟 LlamaIndex 无关
- **不重写 EmbedCache (Redis)** — `embed_cache.py` 保留, 仅换底层 embedder API

## 4. 现状 (in 行)

### 4.1 LlamaIndex 实际调用 (10 文件)

| 文件 | LlamaIndex 用法 |
|---|---|
| `src/generation/llm.py:65,99` | `OpenAILike`, `Ollama` |
| `src/generation/query_engine.py:73,76` | `VectorStoreIndex`, `VectorIndexRetriever` |
| `src/retrieval/embedder.py:48` | `OpenAIEmbedding` |
| `src/retrieval/vector_store.py:74,90,107,136,147` | `PGVectorStore` (sync/async), `TextNode`, `VectorStoreQuery` |
| `src/common/chunker.py:19,54` | `SentenceSplitter`, `Document` |
| `src/common/document_loader.py:18,28,53` | `Document` (顶层 lazy import) |
| `src/orchestration/simple_rag.py:18-19` | `VectorStoreIndex`, `VectorIndexRetriever` |
| `src/orchestration/multi_step_rag.py:19-20` | `VectorStoreIndex`, `VectorIndexRetriever` |
| `src/eval/llama_eval.py:58,62,66,104` | `FaithfulnessEvaluator`, `AnswerRelevancyEvaluator`, `ContextRelevancyEvaluator`, `EvaluationResult` |
| `src/health/checks.py:74` | (仅注释, 0 实际用) |

### 4.2 生产调用方

| 路径 | 引用 |
|---|---|
| `src/api/routes.py:50,57` | `build_query_engine` + `query` — **生产 `/api/v1/query`** |
| `src/api/ingest_router/*.py` | `chunk_documents`, `add_to_vector_store`, `Document` |
| `src/eval/router.py:30,140` | `LlamaIndexEvaluator` |
| `src/eval/runner.py:76` | 抛 `LlamaIndexEvalError:` 错误前缀 |
| 生产链路 0 引用 | `SimpleRAGWorkflow`, `MultiStepRAGWorkflow`, `build_workflow`, `run_workflow` |

### 4.3 测试 (8-10 文件 mock LlamaIndex 路径)

| 文件 | 改动 |
|---|---|
| `tests/generation/test_llm.py` | mock `OpenAILike` / `Ollama` → `ChatOpenAI` / `ChatOllama` |
| `tests/generation/test_query_engine.py` | mock `VectorStoreIndex.from_vector_store` |
| `tests/retrieval/test_embedder.py` | mock `OpenAIEmbedding` → `OpenAIEmbeddings` |
| `tests/retrieval/test_vector_store.py` | mock `PGVectorStore` (LC) |
| `tests/common/test_chunker.py` | mock `SentenceSplitter` → `RecursiveCharacterTextSplitter` |
| `tests/common/test_document_loader.py` | `Document` 断言改 `RAGDoc` |
| `tests/api/test_routes_endpoints.py` | `@patch("src.generation.build_query_engine")` 0 改 (公开 API 保留) |
| `tests/eval/test_llama_eval.py` | **整文件删** |
| `tests/eval/test_runner.py:227` | hard-code `LlamaIndexEvalError` → `DeepEvalError` |

### 4.4 删除清单

| 文件/段落 | 行数 | 原因 |
|---|---|---|
| `src/orchestration/__init__.py` | 42 | 生产 0 调用 |
| `src/orchestration/base.py` | 76 | 自建 BaseWorkflow + Event types, 已无消费方 |
| `src/orchestration/simple_rag.py` | 29 | 同上 |
| `src/orchestration/multi_step_rag.py` | 45 | 同上 |
| `tests/orchestration/test_workflows.py` | ~60 | 随目录 |
| `src/eval/llama_eval.py` | 192 | 替换为 deepeval_eval.py |
| `src/api/routes.py:42-65` | 24 | `evaluate_endpoint` dead code |
| `src/api/schemas.py:24-36` | 13 | `EvaluateRequest`, `EvaluateResponse` dead schemas |
| `src/api/__init__.py` re-export | ~10 | dead exports |
| `tests/api/test_routes.py:3,20-22` | 4 | dead test |
| `tests/api/test_schemas.py:66-91` | 26 | 3 dead tests |
| 合计净删除 | **~521** | |

### 4.5 依赖 (pyproject.toml)

```toml
# 删
"llama-index>=0.14.22"
"llama-index-embeddings-huggingface>=0.7.0"   # 早已弃用未用
"llama-index-llms-ollama>=0.10.1"
"llama-index-llms-openai-like>=0.7.2"
"llama-index-vector-stores-postgres>=0.8.1"

# 加 (版本基于 2026-06-29 PyPI 真实状态)
"langchain-core>=1.4,<2.0"          # 当前 latest 1.4.8
"langchain-openai>=1.0,<2.0"        # 跟 langchain-core 1.x 配套
"langchain-ollama>=1.0,<2.0"
"langchain-postgres>=0.0.17,<0.1"   # 新 PGVectorStore + PGEngine API (0.0.14 起)
"langchain-text-splitters>=1.0,<2.0"
"deepeval>=3.0"
```

## 5. 设计

### 5.1 架构

```
src/
├── common/
│   ├── chunker.py        ← langchain_text_splitters.RecursiveCharacterTextSplitter
│   ├── document.py       ← 新: @dataclass RAGDoc (替代 llama_index.core.schema.Document)
│   └── document_loader.py← RAGDoc (无第三方依赖)
├── retrieval/
│   ├── embedder.py       ← langchain_openai.OpenAIEmbeddings
│   └── vector_store.py   ← langchain_postgres.PGVectorStore
├── generation/
│   ├── llm.py            ← langchain_openai.ChatOpenAI / langchain_ollama.ChatOllama
│   └── query_engine.py   ← 内部走 LCEL chain, 公开 API (build_query_engine, query, aquery, QueryResult) 不变
├── orchestration/        ← 整个目录删除 (生产 0 调用)
└── eval/
    ├── deepeval_eval.py  ← 新: DeepEvalEvaluator (5 metrics)
    ├── runner.py         ← 改引用 DeepEvalEvaluator + DeepEvalError
    └── router.py         ← 改引用 DeepEvalEvaluator
```

### 5.2 RAGDoc (替代 LlamaIndex Document)

`src/common/document.py` (新文件):

```python
from dataclasses import dataclass, field

@dataclass
class RAGDoc:
    """统一文档载体. 取代 llama_index.core.schema.Document."""
    text: str
    metadata: dict = field(default_factory=dict)

    def get_content(self) -> str:
        return self.text
```

调用方接口 `.get_content()` 不变, 故 chunker / vector_store / loader 业务代码 0 改动. 仅
类型提示从 `LIDocument` 改 `RAGDoc`.

### 5.3 chunker.py

```python
# src/common/chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .document import RAGDoc

# 中文友好 separators: 段落 → 行 → 中文句末 → 西文句末 → 空格 → 字符
# RecursiveCharacterTextSplitter 默认 ["\n\n", "\n", " ", ""] 对中文表现差,
# 必须显式加中文标点 (LlamaIndex SentenceSplitter 内部走 sentence boundary, 这里复刻语义)
_CN_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", " ", ""]


def chunk_documents(
    docs: Sequence[RAGDoc],
    chunk_size: int = 512,
    chunk_overlap: int = 128,
) -> list[RAGDoc]:
    if not docs:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_CN_SEPARATORS,
    )
    out: list[RAGDoc] = []
    for d in docs:
        for piece in splitter.split_text(d.text):
            out.append(RAGDoc(text=piece, metadata=d.metadata.copy()))
    return out
```

删除 `get_default_node_parser` (公开 export 被 `src/common/__init__.py:5,20` + `src/__init__.py:84,211`
re-export, **需先 grep 确认 0 调用方再删**). 若有调用方走 grep 修改, 不再保留 LlamaIndex
内部抽象. 同步删 4 处 export 和 `__all__` 中的 name.

### 5.4 generation/llm.py

```python
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

class OpenAILLM:
    def __init__(self, model=None, api_key=None, temperature=0.0,
                 max_tokens=defaults.DEFAULT_OPENAI_MAX_TOKENS):
        self.model = model or _llm_model()
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._llm: ChatOpenAI | None = None

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            base_url = _openai_base_url()
            if base_url and "deepseek" in base_url and not base_url.endswith("/beta"):
                base_url = base_url.rstrip("/") + "/beta"
            kwargs = {
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
    def __init__(self, model=None, base_url=None, temperature=0.0):
        self.model = model or _ollama_model()
        self.base_url = base_url or _ollama_base_url()
        self._temperature = temperature
        self._llm: ChatOllama | None = None

    @property
    def llm(self) -> ChatOllama:
        if self._llm is None:
            self._llm = ChatOllama(model=self.model, base_url=self.base_url,
                                   temperature=self._temperature)
        return self._llm
```

### 5.5 retrieval/embedder.py

```python
from langchain_openai import OpenAIEmbeddings

class OpenAIEmbedder:
    def __init__(self, model=None, api_key=None, base_url=None, dimensions=None):
        # env 优先级保留
        self.model = model or os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_OPENAI)
        self._api_key = (api_key or os.getenv("EMBED_API_KEY")
                         or os.getenv("OPENAI_API_KEY") or defaults.DEFAULT_OPENAI_API_KEY)
        self._base_url = (base_url or os.getenv("EMBED_BASE_URL")
                          or os.getenv("OPENAI_BASE_URL") or "")
        env_dims = os.getenv("EMBED_DIMENSIONS")
        self._dimensions = dimensions if dimensions is not None else (int(env_dims) if env_dims else None)
        self._embedder: OpenAIEmbeddings | None = None

    @property
    def embedder(self) -> OpenAIEmbeddings:
        if self._embedder is None:
            kwargs = {
                "model": self.model,
                "api_key": self._api_key or None,
                # bge-m3 (SiliconFlow) 用 XLM-RoBERTa tokenizer 不是 tiktoken, 必须关
                # LC 默认 tiktoken 编码长度检查 (否则 KeyError). OpenAI 自己端点不影响.
                "check_embedding_ctx_length": False,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            # 不传 `dimensions`: bge-m3 服务端固定 1024 维, 传 dimensions 会 400.
            # OpenAI text-embedding-3 系列私有特性, 其他兼容端点不支持. 维度通过
            # init_vectorstore_table(vector_size=) 表达, 不通过 embedder.
            self._embedder = OpenAIEmbeddings(**kwargs)
        return self._embedder

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.embed_documents(texts)

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        # EmbedCache 包装层不变, 仅 miss 路径换 embedder.aembed_documents
        # ... (跟现在一样, 改最后一行)
        computed = await self.embedder.aembed_documents(miss_texts)
        ...

    def __call__(self, text: str) -> list[float]:
        return self.embed([text])[0]
```

EmbedCache (Redis 7d) 逻辑保留, 仅换底层 embedder API.

### 5.6 retrieval/vector_store.py

**重要**: `langchain-postgres>=0.0.14` 把老 `PGVector` 标 deprecated, 引入新 `PGVectorStore`,
**API 完全不同**:
- 必须用工厂方法 `PGVectorStore.create_sync(engine, embedding_service, table_name, ...)` 构造,
  不能直接 `PGVectorStore(...)` (构造函数有 `key` 参数主动阻止)
- `engine` 不是 SQLAlchemy `Engine`, 是 `PGEngine` (LC 自己的 wrapper),
  通过 `PGEngine.from_connection_string(url)` 构造
- 没有 `collection_name` 参数, 走单表自定义 schema (列名固定: `langchain_id / content /
  embedding / langchain_metadata`)
- 表必须预先存在, 由 `PGEngine.init_vectorstore_table(table_name, vector_size, ...)` 建

```python
from langchain_postgres import PGEngine, PGVectorStore as LCPGVectorStore
from langchain_postgres.v2.indexes import HNSWIndex

from .embedder import OpenAIEmbedder
from src.common.db_url import get_rag_db_url
from src.common.document import RAGDoc


@dataclass
class PGVectorConfig:
    """字段保留. connection_string 仍走 get_rag_db_url() 单一构造点."""
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    database: str = "rag"
    vector_dim: int | None = None
    index_type: str = "hnsw"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    ivfflat_lists: int = 100

    @property
    def connection_string(self) -> str:
        return get_rag_db_url()

    @classmethod
    def from_env(cls) -> PGVectorConfig:
        # ... (跟现在一样)
        ...


# 新表名 (避免跟 LlamaIndex 老 `llamaindex_embeddings` 单表混淆)
_VECTOR_TABLE = "rag_embeddings"


class PGVectorStore:
    """业务包装. 公开 API 同名 (add / delete / query), 内部走 LC PGVectorStore."""

    def __init__(self, config: PGVectorConfig | None = None,
                 embedder: OpenAIEmbedder | None = None):
        self._config = config or PGVectorConfig.from_env()
        self._embedder = embedder
        self._vs: LCPGVectorStore | None = None
        self._engine: PGEngine | None = None

    @property
    def vector_store(self) -> LCPGVectorStore:
        if self._vs is None:
            if self._embedder is None:
                raise RuntimeError(
                    "PGVectorStore 需要传入 embedder (LC PGVectorStore.create_sync "
                    "构造期需要 OpenAIEmbeddings 实例). 调用方必须显式注入."
                )
            self._engine = PGEngine.from_connection_string(self._config.connection_string)
            self._vs = LCPGVectorStore.create_sync(
                engine=self._engine,
                embedding_service=self._embedder.embedder,  # 实际 OpenAIEmbeddings 实例
                table_name=_VECTOR_TABLE,
                metadata_columns=[],  # 默认全塞 langchain_metadata JSONB
            )
        return self._vs

    def add(self, documents: Sequence[RAGDoc], batch_size: int = 100) -> list[str]:
        """add — metadata 必须含 ref_doc_id (上层产生, 文档级标识), 用于 delete 按文档清."""
        if not documents:
            return []
        texts = [d.text for d in documents]
        metadatas = [d.metadata for d in documents]
        return self.vector_store.add_texts(texts, metadatas=metadatas)

    def delete(self, doc_ids: Sequence[str]) -> None:
        """按 ref_doc_id 删 — 跟 LlamaIndex 原行为对齐 (一份文档对应多 chunk).

        LC PGVectorStore.delete(ids=...) 只按主键删, 我们要按 metadata 过滤删,
        所以走原生 SQL (engine.run_sql / psycopg2). 见 _delete_by_ref_doc_id().
        """
        if not doc_ids:
            return
        _delete_by_ref_doc_id(self._engine, _VECTOR_TABLE, list(doc_ids))

    def query(self, query_embedding: list[float], top_k: int = 5,
              filter: dict | None = None) -> Any:
        """按 vector cosine 检索, 返 LC Document 列表."""
        return self.vector_store.similarity_search_by_vector(
            query_embedding, k=top_k, filter=filter
        )

    def close(self) -> None:
        if self._engine is not None:
            self._engine.close()
        self._vs = None
        self._engine = None


def _delete_by_ref_doc_id(engine: PGEngine, table_name: str, ref_doc_ids: list[str]) -> None:
    """按 metadata.ref_doc_id IN (...) 删 — pgvector + JSONB 标准用法."""
    sql = f"""
    DELETE FROM {table_name}
    WHERE langchain_metadata->>'ref_doc_id' = ANY(:ref_doc_ids)
    """
    with engine.connect() as conn:
        conn.execute(text(sql), {"ref_doc_ids": ref_doc_ids})
        conn.commit()
```

**`AsyncPGVectorStore`** 同模式, 走 `PGVectorStore.create()` (async 工厂) + `aadd_texts /
asimilarity_search_by_vector`, delete 走 `engine.aconnect()` + `await conn.execute()`.

**`init_pgvector()` 改动** (Spike 实测后修正): 不再走 psycopg2 直建 `llamaindex_embeddings` 表,
改成 3 步:

```python
def init_pgvector(config: PGVectorConfig | None = None, force: bool = False) -> None:
    from langchain_postgres import PGEngine
    from langchain_postgres.v2.indexes import HNSWIndex
    from sqlalchemy import create_engine, text

    config = config or PGVectorConfig.from_env()
    pg_engine = PGEngine.from_connection_string(url=config.connection_string)
    sa_engine = create_engine(config.connection_string)  # 独立 SA Engine 跑 raw SQL

    # 1. pgvector 扩展 (LC 不管)
    with sa_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    # 2. LC 标准建表 (只建 pkey + json metadata, 没建 vector index)
    pg_engine.init_vectorstore_table(
        table_name=_VECTOR_TABLE,
        vector_size=config.vector_dim or _get_embed_dim(),
        overwrite_existing=force,
    )

    # 3. (Spike 偏差 #1) LC 建的 langchain_metadata 默认是 json 不是 jsonb,
    #    跟项目 JSONB 规约冲突, 必须 ALTER + 建 GIN
    with sa_engine.connect() as conn:
        conn.execute(text(f"""
            ALTER TABLE {_VECTOR_TABLE}
            ALTER COLUMN langchain_metadata TYPE jsonb USING langchain_metadata::jsonb;
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS {_VECTOR_TABLE}_metadata_gin_idx
            ON {_VECTOR_TABLE} USING gin (langchain_metadata jsonb_path_ops);
        """))
        conn.commit()

    # 4. (Spike 偏差 #2) HNSW vector index LC 不自动建, 显式 apply
    store = PGVectorStore.create_sync(
        engine=pg_engine,
        embedding_service=_dummy_embeddings(),  # 仅为构造 store 触发 apply_vector_index
        table_name=_VECTOR_TABLE,
    )
    store.apply_vector_index(HNSWIndex(
        name=f"{_VECTOR_TABLE}_hnsw_idx",
        m=config.hnsw_m,
        ef_construction=config.hnsw_ef_construction,
    ))

    sa_engine.dispose()
```

**业务持有 2 engine** (Spike 偏差 #3): `PGEngine` (给 langchain-postgres async) + `sqlalchemy.Engine`
(给 raw SQL DELETE / 索引维护). `PGEngine.close()` 是 coroutine, 同步路径 close 不可用,
所以 sync `PGVectorStore` 业务包装类内部维护 SA Engine 跟 PGEngine 两个引用.

**ref_doc_id 语义关键**: 调用方 (`ingest/` / 业务) 写入时必须在 `metadata` 中带
`ref_doc_id` (文档级 UUID, 同一文档的所有 chunk 共享同 id), 删除按这个字段过滤
(`langchain_metadata @> '{"ref_doc_id": "..."}'::jsonb` 走 GIN 索引).
若调用方现在没传 `ref_doc_id`, 数据迁移 (T4 alembic) 会从老表 `ref_doc_id` 列迁到新表 metadata.

### 5.7 generation/query_engine.py (LCEL chain 内部, 公开 API 不变)

**关键设计**: 用 `RunnableParallel` 一次跑 retriever, 同时拿到 docs + LLM response,
**不双跑 retriever** (否则 latency 2x).

```python
from langchain_core.runnables import RunnableParallel, RunnableLambda, Runnable
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


@dataclass
class QueryResult:
    """对外契约:
    - response: 字符串
    - sources: list[dict] 含 file_path / page_label / text (前端依赖)
    - source_nodes: LC Document 列表 (语义跟 LlamaIndex NodeWithScore 不同, 内部用,
      若调用方 grep 用了 .score 字段需补)
    - metadata: dict
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
        return cls(
            response=response,
            sources=sources,
            source_nodes=source_docs,
            metadata={},
        )


class _LCQueryEngine:
    """LCEL 链 + sources 单跑提取 — 适配老 .query / .aquery 接口."""

    def __init__(self, chain_with_docs: Runnable):
        # chain_with_docs: 输入 question (str), 输出 dict {"response": str, "docs": list[Document]}
        self._chain = chain_with_docs

    def query(self, question: str, **kwargs) -> QueryResult:
        result = self._chain.invoke(question)
        return QueryResult.from_response(result["response"], source_docs=result["docs"])

    async def aquery(self, question: str, **kwargs) -> QueryResult:
        result = await self._chain.ainvoke(question)
        return QueryResult.from_response(result["response"], source_docs=result["docs"])


def get_llm(llm_type: str | None = None, model: str | None = None, **kwargs):
    from ..common import defaults
    from .llm import LocalLLM, OpenAILLM
    llm_type = llm_type or defaults.DEFAULT_LLM_TYPE
    model = model or defaults.DEFAULT_LLM_MODEL_OPENAI
    if llm_type == "openai":
        return OpenAILLM(model=model, **kwargs).llm
    return LocalLLM(model=model, **kwargs).llm


def build_query_engine(vector_store, embedder, llm=None, top_k: int = 5, **kwargs):
    """构造 LCEL chain. retriever 一次跑, docs 跟 response 一起返."""
    retriever = vector_store.vector_store.as_retriever(search_kwargs={"k": top_k})
    if llm is None:
        llm = get_llm()

    prompt = ChatPromptTemplate.from_template(
        "根据以下上下文回答。\n\n上下文：\n{context}\n\n问题：{question}\n\n回答："
    )

    def format_docs(docs):
        return "\n\n".join(d.page_content for d in docs)

    response_chain = prompt | llm | StrOutputParser()

    # RunnableParallel: question + docs 一次拿
    # 然后用 lambda 拼装 response_chain 输入
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


def query(question: str, query_engine, **kwargs) -> QueryResult:
    return query_engine.query(question, **kwargs)


async def aquery(question: str, query_engine, **kwargs) -> QueryResult:
    return await query_engine.aquery(question, **kwargs)
```

`QueryResult` 字段保持 `response / sources / source_nodes / metadata` — 跟前端契约一致.
**注意**: `source_nodes` 装 LC `Document` 而非 LlamaIndex `NodeWithScore`, 若任何调用方
使用 `.score` / `.node` 等 LlamaIndex 特定字段会破坏. 已 grep 项目代码确认: `routes.py:61`
仅用 `sources` 字段构造 `SourceNode(**s)`, 不碰 `source_nodes` (该字段 = LlamaIndex 内部
对象的逃生口, 0 真实调用方). 安全.

### 5.8 删除 orchestration/

`src/orchestration/` 整目录删除. 检查无生产引用 (`grep build_workflow|run_workflow` src/api).
`src/__init__.py` 同步删 4 个 export (BaseWorkflow / SimpleRAGWorkflow / MultiStepRAGWorkflow / build_workflow / run_workflow / ResponseEvent / WorkflowStats).

`tests/orchestration/test_workflows.py` 整文件删.

### 5.9 评估器 (按 deepeval spec)

完全沿用 `docs/superpowers/specs/2026-06-16-deepeval-replace-llamaindex-design.md`:

- 新建 `src/eval/deepeval_eval.py` (~140 行): `DeepSeekJudge` + `DeepEvalEvaluator` + `DeepEvalError`
- 改 `src/common/evaluation.py` `RAGAMetrics` 加 `hallucination` (5th)
- 改 `src/eval/router.py:30,140` 引用 `DeepEvalEvaluator`
- 改 `src/eval/runner.py:76` 错误前缀 → `DeepEvalError`
- 改 `tests/eval/test_runner.py:227` hard-code
- 删 dead code `/api/v1/evaluate` (按 deepeval spec §5.5):
  - `src/api/routes.py:42-65` handler
  - `src/api/schemas.py:24-36` 2 个 Pydantic class
  - `src/api/__init__.py` re-export
  - `tests/api/test_routes.py:3,20-22` 1 test
  - `tests/api/test_schemas.py:66-91` 3 test
- 删 `src/eval/llama_eval.py` (~192 行)

### 5.10 关联模块调用方改动

#### 5.10.1 buyer_profile/extractor.py

`src/buyer_profile/extractor.py:50-54` 直接 import `OpenAILLM`, 调 `.complete(prompt)` +
`resp.text` (LlamaIndex API). 替换后 `OpenAILLM().llm` 返 `ChatOpenAI`, API 改:

```python
# 旧
from src.generation.llm import OpenAILLM
llm = OpenAILLM().llm
resp = llm.complete(prompt)
text = resp.text if hasattr(resp, "text") else str(resp)

# 新
from src.generation.llm import OpenAILLM
llm = OpenAILLM().llm
resp = llm.invoke(prompt)  # 返 AIMessage
text = resp.content if hasattr(resp, "content") else str(resp)
```

`tests/buyer_profile/` 如果 mock `OpenAILLM().llm.complete` 也要同步改 `.invoke` + `.content`.

#### 5.10.2 health/checks.py

`src/health/checks.py:74` 注释 "绕开 llama_index.vector_stores.pgvector 的复杂初始化",
代码层无 LlamaIndex 依赖, 改注释即可 (验收 `grep llama_index` 才能 0 hit).

#### 5.10.3 telemetry/langfuse_client.py

`src/telemetry/langfuse_client.py:94-96` `get_callback_handler()` method 名 + docstring
跟 LlamaIndex 耦合:

```python
def get_callback_handler(self) -> Any:
    """返回 llama-index 兼容的 CallbackHandler"""
    return self.client.get_callback_handler()
```

调用方 `grep get_callback_handler packages/service` 0 hit (dead method). 改 docstring 为
"返回 LC 兼容的 CallbackHandler" + 内部走 `langfuse.langchain.CallbackHandler` (若 LF
支持; 否则保留 langfuse 内置 handler 不变). 不要删 method (P2 follow-up).

#### 5.10.4 common/__init__.py

删 export `get_default_node_parser` (1 行 import + 1 行 `__all__` + 1 行 src/__init__:84
+ 1 行 src/__init__:211 共 4 处). 改 docstring "common 子包：共享工具..." 不提 LlamaIndex.

#### 5.10.5 src/__init__.py

行 1 docstring "标准 LlamaIndex RAG 系统" → "RAG 系统" (跟 LlamaIndex 强绑定的描述都删).
re-export 名单同步删:
- `BaseWorkflow`, `MultiStepRAGWorkflow`, `ResponseEvent`, `SimpleRAGWorkflow`,
  `WorkflowStats`, `build_workflow`, `run_workflow` (orchestration 7 个)
- `get_default_node_parser` (chunker dead)
- `__all__` 中对应 7+1=8 个 name

#### 5.10.6 ingest/ 子模块

业务调用方 (`ingest/router.py`, `ingest/output_converter.py`) 走 `from ..common import
chunk_documents, load_md_files, load_txt_files, Document`, 接口不变 (`Document` → `RAGDoc`
但类型走 TYPE_CHECKING, runtime 无影响). 若有 isinstance check 必须改, plan 阶段 grep 验.

## 6. 关键决策 (已用户审批 + v2 修订)

| # | 决策 | 答案 | 原因 |
|---|---|---|---|
| D1 | DeepAgent 是否纳入 | **不纳入** | 当前 0 多 Agent 需求, YAGNI |
| D2 | 向量库走 LC 包装 vs 自写 SQL | **LC `langchain_postgres.PGVectorStore.create_sync` 工厂 API** | 官方维护, 异步 API 现成, 升级有人管. ⚠️ v2 修正: 必须用 `PGEngine` + `create_sync`, 不是直接 `PGVectorStore(...)` |
| D3 | Workflow 怎么处理 | **删除** `src/orchestration/` 全部 | 生产 0 调用, 是 dead code |
| D4 | Document 容器 | **自定义 RAGDoc** | 0 第三方依赖, `.get_content()` 接口兼容 |
| D5 | pgvector schema | **走 LC 标准 `rag_embeddings` 单表 + 数据迁移** | ⚠️ v2 修正: LC 新 PGVectorStore 是单表 (`langchain_id / content / embedding / langchain_metadata`), 不是双表 |
| D6 | 是否引入 langgraph 单独 dep | **不引入** | 当前不写 StateGraph, 后续按需 |
| D7 | 评估器走 deepeval | **是** | 复用已批 spec, 解决 LlamaIndex 评估器 API 难用问题 |
| D8 | 错误前缀 | **`DeepEvalError`** 替换 `LlamaIndexEvalError` | 跟 deepeval spec 一致 |
| D9 | 提交粒度 | **9 个原子 commit** (含 spike + 数据迁移) | v2 修正: 加 spike (commit 0) 和老表保留期 |
| D10 | `ref_doc_id` 在新 schema 如何表达 | **塞 `langchain_metadata.ref_doc_id` JSONB key**, delete 走原生 SQL 按 metadata 过滤 | LC PGVectorStore.delete(ids=) 只按主键, 业务必须按文档级 ref_doc_id 删多 chunk |
| D11 | LCEL retriever 双跑 vs 单跑 | **单跑** (`RunnableParallel` 一次拿 docs + response) | 避免 latency 2x |
| D12 | 老 `llamaindex_embeddings` 表保留期 | **7 天** | 业务跑稳后 P3 follow-up 单独 DROP |
| D13 | LangChain 锁版本 | **`langchain-core>=1.4,<2.0`** + 其他 LC 包 `>=1.0,<2.0` + `langchain-postgres>=0.0.17,<0.1` | 2026-06-29 PyPI 当前 stable 是 1.4.8, 不是 0.3.x; 锁主版本防 2.x 意外升级 |

## 7. 实施 (9 个原子 commit, 新增老表保留期)

| # | 内容 | 验证 |
|---|---|---|
| 0 | **Spike 验证**: `from langchain_postgres import PGEngine, PGVectorStore`, 在 dev DB 跑 hello-world (init_vectorstore_table + add_texts + similarity_search_by_vector + delete by metadata SQL) | spike 通过, 把真实 API 调用记 [docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md](../../handoffs/2026-06-29-langchain-postgres-spike.md) |
| 1 | `pyproject.toml` 加 `langchain-core>=1.4,<2.0`, `langchain-openai>=1.0,<2.0`, `langchain-ollama>=1.0,<2.0`, `langchain-postgres>=0.0.17,<0.1`, `langchain-text-splitters>=1.0,<2.0`, `deepeval>=3.0`. `uv sync` | 0 报错; `pytest` 仍绿 (旧代码还跑) |
| 2 | 新建 `src/common/document.py` (RAGDoc); 改 `chunker.py` (中文 separators) + `document_loader.py` 用 RAGDoc | `pytest tests/common/ -v` 全绿 |
| 3 | 改 `generation/llm.py` (`ChatOpenAI`/`ChatOllama`) + `retrieval/embedder.py` (`OpenAIEmbeddings`); 同步改 `buyer_profile/extractor.py:50-54` 用 `.invoke` + `.content` | `pytest tests/generation/test_llm.py tests/retrieval/test_embedder.py tests/buyer_profile/ -v` 全绿 |
| 4 | **数据迁移**: 写 alembic migration建 `rag_embeddings` 表 (LC schema) + HNSW 索引 + 一次性 INSERT FROM `llamaindex_embeddings` (text → content, metadata → langchain_metadata, embedding → embedding, ref_doc_id 塞 langchain_metadata.ref_doc_id); `init_pgvector()` 改用 `PGEngine.init_vectorstore_table`; **老表 `llamaindex_embeddings` 保留 (不 DROP)** | `psql` 查 `rag_embeddings` 行数 == 老表; `langchain_metadata->>'ref_doc_id'` 字段全部非 NULL |
| 5 | 改 `retrieval/vector_store.py` (`PGEngine` + `LCPGVectorStore.create_sync` + `_delete_by_ref_doc_id`); 改 `generation/query_engine.py` (LCEL `RunnableParallel` 链, 单跑 retriever) | `pytest tests/retrieval/ tests/generation/ tests/api/ -v` 全绿; e2e `/api/v1/query` 跑 1 条真实查询验证 sources 非空 |
| 6 | 删 `src/orchestration/` + `tests/orchestration/`; 改 `src/__init__.py` 删 7 个 workflow re-export + `get_default_node_parser` 1 个; 改 `common/__init__.py` 删 `get_default_node_parser` re-export | `pytest tests/ -v` 全绿; `grep -rn "build_workflow\|SimpleRAGWorkflow\|MultiStepRAGWorkflow\|get_default_node_parser" src/ tests/` 0 hit |
| 7 | 实施 deepeval spec §5-§7: 新建 `deepeval_eval.py` + 改 `RAGAMetrics` + `runner.py` + `router.py` + `test_runner.py:227` + 删 dead code | `pytest tests/eval/ tests/api/ -v` 全绿; `grep -rn "LlamaIndexEvalError\|llama_eval\|EvaluateRequest" src/ tests/` 0 hit |
| 8 | 删 `llama_eval.py` + `pyproject.toml` 移除 `llama-index*` 5 个包; 改 `src/__init__.py:1` docstring (去 LlamaIndex 字样) + `health/checks.py:74` 注释 + `telemetry/langfuse_client.py:94` docstring; `uv sync` | `uv sync` 通过; `grep -rn "llama_index\|llama-index" src/ tests/ pyproject.toml` 0 hit; 整体 `pyright + ruff check + pytest` 绿 |

**老表 `llamaindex_embeddings` 保留 7 天**, 由 P3 follow-up 独立 commit 删除. 期间若发现
迁移问题, 可立即 `DROP TABLE rag_embeddings; INSERT FROM llamaindex_embeddings` 重做.

**Commit 顺序约束**:
- Commit 0 (spike) 必须先, 不通过整个 plan 重写
- Commit 1 装包不删旧
- Commit 2-3 顺序可调 (按 src 模块独立)
- Commit 4 必须在 5 之前 (新代码依赖新表存在)
- Commit 5-6 顺序可调
- Commit 7 必须在 6 之后 (deepeval 依赖 orchestration 已删除, 无 import 循环)
- Commit 8 必须最后 (删 `llama-index*` 前所有引用必须清干净)

## 8. 风险与缓解

### 8.1 LCEL chain 返字符串, sources 需双跑 retriever (低-中)

LCEL `(retriever | format_docs | prompt | llm | parser).invoke(question)` 返 `str`, 不带
source docs. 必须显式 `retriever.invoke(question)` 拿 docs 给 `QueryResult.sources`. 即
retriever 实际跑 2 次 (一次给 chain, 一次给 sources).

**缓解**:
- LangChain 推荐模式: 用 `RunnableParallel` 一次跑, 把 docs 和 response 一起返:
  ```python
  rag = RunnableParallel({"docs": retriever, "question": RunnablePassthrough()})
      .assign(response=lambda x: chain.invoke({"context": format_docs(x["docs"]), "question": x["question"]}))
  ```
- 简化实施期可先双跑 (语义对), 验收后优化 (P0 follow-up).

### 8.2 LangChain PGVectorStore schema vs `llamaindex_embeddings` 表 (中-高)

`langchain-postgres>=0.0.14` 把老 `PGVector` 标 deprecated, 新 `PGVectorStore` API
**完全不同** (见 §5.6 详解):
- 工厂方法 `PGVectorStore.create_sync(engine=PGEngine, ...)`, 不能直接构造
- 不走 `langchain_pg_collection` + `langchain_pg_embedding` 双表 (那是老 PGVector)
- 单表自定义 schema, 列名固定: `langchain_id (UUID) / content / embedding / langchain_metadata (JSONB)`
- 表必须预先存在, 由 `PGEngine.init_vectorstore_table(table_name, vector_size, ...)` 建

**迁移方案 (走 alembic, 可 downgrade)**:

```sql
-- migration: 20260629_lc_pgvector_schema.py
-- upgrade:
-- 1. 建新表 (PGEngine.init_vectorstore_table 等价 SQL)
CREATE TABLE rag_embeddings (
    langchain_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(<DIM>),
    langchain_metadata JSONB
);
-- 2. HNSW 索引
CREATE INDEX rag_embeddings_hnsw_idx
    ON rag_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
-- 3. metadata GIN 索引 (filter / ref_doc_id 删除走)
CREATE INDEX rag_embeddings_metadata_gin
    ON rag_embeddings USING gin (langchain_metadata jsonb_path_ops);
-- 4. 一次性迁移数据
-- 老表: id, text, metadata, ref_doc_id, embedding
-- 新表: langchain_id, content, langchain_metadata (含 ref_doc_id), embedding
INSERT INTO rag_embeddings (langchain_id, content, langchain_metadata, embedding)
SELECT
    id,
    text,
    metadata || jsonb_build_object('ref_doc_id', ref_doc_id::text),
    embedding
FROM llamaindex_embeddings;

-- downgrade: DROP TABLE rag_embeddings; (老表仍在, 业务跑回老 code 即可)
```

**dev 流程**: `alembic upgrade head`, 走完整迁移 SQL (空表 INSERT noop).
**prod 流程**: `alembic upgrade head`. 数据量大 (估 50K+ rows) 时, INSERT FROM 可能锁表
~30s — 业务低峰跑.

**老表保留期**: 迁完不立即 DROP, 保留 7 天观察, 期间业务跑新 PGVectorStore. P3
follow-up commit 才 DROP.

**downgrade 回滚**: alembic downgrade DROP `rag_embeddings`, 老表 `llamaindex_embeddings`
+ 老 LlamaIndex 代码组合**仍可工作** (commit 5 之前的状态). 但 commit 7+ 之后已删
`llama_eval.py` 等代码, downgrade 需要回到 commit 7 之前的代码版本.

### 8.3 中文 judge prompt 行为差异 (deepeval 已识别, 低)

按 deepeval spec §8.1: 跑 5 条样本对比偏差 < 0.15. 不重复.

### 8.4 ChatOpenAI 配 OpenAI 兼容端点的实际兼容性 (低)

`ChatOpenAI(base_url="https://api.deepseek.com")` 已是标准用法, LangChain 0.3+ 官方
支持. 项目 `OPENAI_BASE_URL` 已是 OpenAI 兼容端点 (DeepSeek / SiliconFlow), 切换后行为对齐.

**缓解**: Commit 3 完成后跑 1 条 e2e (curl POST /api/v1/query) 确认 LLM 调用成功.

### 8.5 `QueryResult.source_nodes` 语义变化 (低)

字段类型: 老 LlamaIndex `NodeWithScore` (`.node.metadata`, `.node.get_content()`, `.score`) →
新 LC `Document` (`.metadata`, `.page_content`). **接口名同, 语义不同**.

**已 grep 验证**: `routes.py:61` 仅用 `sources` 字段构造 `SourceNode(**s)`, 不引用
`source_nodes`. 该字段是逃生口, 0 生产调用方. 风险低.

### 8.6 LangChain version migration churn (中)

LangChain 历史 0.1 → 0.2 → 0.3 → 1.0 多次 breaking change. 当前已 1.4.x 稳定线
(`langchain-core 1.4.8` as of 2026-06-29). 项目锁 `langchain-core>=1.4,<2.0` 防止意外升 2.x.
同样锁 `langchain-postgres>=0.0.17,<0.1` (新 `PGVectorStore` + `PGEngine` API 自 0.0.14
起, 0.0.17 是当前 stable).

### 8.7 RAGAMetrics 加 hallucination 字段对前端 API 算变化 (低)

虽属"加字段, 不删字段"型扩展, 但 `/api/evaluate/runs` 响应 schema 新增了 key, 严格意义是
API 变化. 跟 deepeval spec §8.3 一致处理 — 前端用 `.get("hallucination")` 安全访问.

### 8.8 ChatOpenAI `max_tokens` 跟 DeepSeek 端点兼容性 (低)

`ChatOpenAI(max_tokens=...)` LangChain 0.3+ 仍支持, OpenAI v1 API 改名 `max_completion_tokens`
但 LC 会做 alias. DeepSeek 兼容端点能否接受 `max_tokens` 需 commit 3 验证 (`curl -d
'{"max_tokens": 100}'` 直 DeepSeek api 一次).

## 9. 验收

- [ ] `uv sync` 后 5 个 `llama-index*` 包消失, 6 个 `langchain-*` + `deepeval` 出现
- [ ] `grep -rn "llama_index\|llama-index" packages/service/src packages/service/tests pyproject.toml` 0 hit
- [ ] `grep -rn "LlamaIndexEvalError" packages/service/` 0 hit
- [ ] `grep -rn "build_workflow\|SimpleRAGWorkflow\|MultiStepRAGWorkflow\|get_default_node_parser" packages/service/src packages/service/tests` 0 hit
- [ ] `uv run pytest packages/service/tests -v` 全绿 (allow pre-existing fail 22; 净测试数 1075 → ~1071)
- [ ] `uv run pyright packages/service/src` 0 error
- [ ] `uv run ruff check packages/service/` 0 error
- [ ] `RAGAMetrics.__dataclass_fields__` 含 `hallucination`
- [ ] DB schema: `rag_embeddings` 表存在 + HNSW 索引存在 + metadata GIN 索引存在
- [ ] DB 数据: `SELECT COUNT(*) FROM rag_embeddings = SELECT COUNT(*) FROM llamaindex_embeddings`
- [ ] DB 数据: `SELECT COUNT(*) FROM rag_embeddings WHERE langchain_metadata->>'ref_doc_id' IS NOT NULL` 等于总行数 (无丢字段)
- [ ] **端到端 `/api/v1/query`** (1 条真实查询):
  - sources 长度 > 0
  - response 非空
  - 跟旧实现 embedding 相似度 cosine ≥ 0.85 (用 BGE 算同一问题前后 response 的 cosine, 0.85 是相同语义阈值)
- [ ] **端到端 `/api/v1/documents/{ref_doc_id}` DELETE** (1 个 ref_doc_id, ≥ 2 chunk):
  - 删后 `SELECT COUNT(*) FROM rag_embeddings WHERE langchain_metadata->>'ref_doc_id' = '<id>'` == 0
  - **验证按 ref_doc_id 删而非主键删** (P0 错误 15 的回归)
- [ ] **端到端 `/api/evaluate/runs`**: 5 条 ground_truth 样本, `avg_metrics` 5 key 全有分数, 偏差 < 0.15

## 10. 关联文件

| 文件 | 改动 |
|---|---|
| `pyproject.toml` | **改** 5 删 + 6 加 (含锁版本范围) |
| `alembic/versions/20260629_lc_pgvector_schema.py` | **新建** 数据迁移 (建 rag_embeddings + HNSW + GIN + INSERT FROM) |
| `src/common/document.py` | **新建** (~15 行 RAGDoc dataclass) |
| `src/common/chunker.py` | **改** 用 RecursiveCharacterTextSplitter + 中文 separators; 删 get_default_node_parser |
| `src/common/document_loader.py` | **改** Document → RAGDoc |
| `src/common/__init__.py` | **改** 删 get_default_node_parser export + 改 docstring |
| `src/generation/llm.py` | **改** OpenAILike/Ollama → ChatOpenAI/ChatOllama |
| `src/generation/query_engine.py` | **改** 内部走 LCEL `RunnableParallel`, 公开 API 不变 |
| `src/retrieval/embedder.py` | **改** OpenAIEmbedding → OpenAIEmbeddings, EmbedCache 保留 |
| `src/retrieval/vector_store.py` | **改** llama_index PGVectorStore → langchain_postgres `PGEngine` + `PGVectorStore.create_sync` + `_delete_by_ref_doc_id` (按 metadata 删) |
| `src/buyer_profile/extractor.py:50-54` | **改** `.complete(prompt)` + `resp.text` → `.invoke(prompt)` + `resp.content` |
| `src/health/checks.py:74` | **改** 注释去 LlamaIndex 字样 |
| `src/telemetry/langfuse_client.py:94-96` | **改** docstring + 内部 (可选 LC CallbackHandler) |
| `src/orchestration/` | **删** 整目录 (4 文件 ~190 行) |
| `src/eval/deepeval_eval.py` | **新建** (~140 行, 按 deepeval spec §5.3) |
| `src/eval/llama_eval.py` | **删** (~192 行) |
| `src/eval/router.py` | **改** import + 引用 |
| `src/eval/runner.py` | **改** 错误前缀 |
| `src/common/evaluation.py` | **改** RAGAMetrics 加 hallucination |
| `src/api/routes.py` | **删** evaluate_endpoint (24 行) |
| `src/api/schemas.py` | **删** EvaluateRequest/Response (13 行) |
| `src/api/__init__.py` | **改** 删 re-export |
| `src/__init__.py` | **改** 删 7 个 orchestration export + get_default_node_parser export + 改顶部 docstring (去 LlamaIndex 字样) |
| `tests/orchestration/test_workflows.py` | **删** 整文件 |
| `tests/eval/test_llama_eval.py` | **删** 整文件 |
| `tests/eval/test_runner.py` | **改** hard-code 字符串 |
| `tests/api/test_routes.py` | **删** evaluate test (4 行) |
| `tests/api/test_routes_endpoints.py` | **改** mock build_query_engine 返回 (`_LCQueryEngine`), 断言不变 |
| `tests/api/test_schemas.py` | **删** 3 个 evaluate test (26 行) |
| `tests/generation/test_llm.py` | **改** mock 路径 ChatOpenAI/ChatOllama |
| `tests/generation/test_query_engine.py` | **改** mock LCEL chain |
| `tests/retrieval/test_embedder.py` | **改** mock 路径 OpenAIEmbeddings |
| `tests/retrieval/test_vector_store.py` | **改** mock 路径 + `_delete_by_ref_doc_id` 测试 |
| `tests/retrieval/test_retrieval_exports.py` | **改** 同步 src/__init__ 修改 |
| `tests/common/test_chunker.py` | **改** mock splitter + 中文 separators 断言 |
| `tests/common/test_document_loader.py` | **改** Document → RAGDoc 断言 |
| `tests/buyer_profile/test_extractor.py` | **改** mock `.invoke` + `.content` (而非 `.complete` + `.text`) |
| `tests/eval/test_deepeval_eval.py` | **新建** ~8 个 test (按 deepeval spec §5.3 验收要求) |

## 11. Follow-up (不在本 spec)

- **P0**: 已合入 v2 主线: LCEL `RunnableParallel` 单跑 retriever (§5.7), 不再 follow-up
- **P1**: 中文 judge prompt template override (跟 deepeval spec §12 一致)
- **P2**: 若未来需要复杂 Agent / 多步有状态 RAG, 引入 `langgraph.graph.StateGraph` (单独 dep)
- **P3**: 业务稳定 7 天后, 独立 commit `DROP TABLE llamaindex_embeddings`
- **P4**: 引入 `langchain-postgres.async` 异步连接池 (替换当前 asyncpg 直连)
- **P5**: `telemetry/langfuse_client.py` 真接入 `langfuse.langchain.CallbackHandler` 让
  LCEL chain trace 跑通 (若 LF Python SDK 0.x 支持)
