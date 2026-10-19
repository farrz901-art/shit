# LlamaIndex 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

LlamaIndex 是为 LLM 应用而生的**数据框架**，专门解决"让 LLM 能用上你的私有数据"这个核心问题。它提供从文档加载、解析、分块、嵌入、索引、检索到查询引擎的完整工具链。

**同类对比：**

| 框架 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **LlamaIndex** | RAG 数据框架 | 本项目**主力框架**，RAG 链路最完整 |
| **LangChain** | LLM 应用综合 | 通用，RAG 不如 LlamaIndex 深入 |
| **Haystack** | NLP 管道 | 老牌，文档不如 LlamaIndex |
| **txtai** | 语义搜索 | 轻量，但 RAG 能力弱 |

**LlamaIndex 解决的核心问题**：
- **数据接入**：PDF / Word / Excel / 数据库 / API 全格式支持
- **分块策略**：固定大小 / 句子 / 段落 / 语义分块
- **索引类型**：Vector Index / Summary Index / Keyword Table Index
- **检索增强**：embedding 相似度 + 关键词 + 元数据过滤 + rerank
- **查询引擎**：单步 retrieve / 多步 Sub-Question / ReAct Agent

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# 核心
uv add llama-index

# 项目用的几个适配器
uv add llama-index-llms-ollama
uv add llama-index-llms-openai-like
uv add llama-index-embeddings-huggingface
uv add llama-index-vector-stores-postgres
```

### 2.2 环境变量

```bash
# OpenAI 兼容
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Embedding（独立）
EMBED_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBED_API_KEY=sk-xxx
EMBED_MODEL=BAAI/bge-m3
EMBED_DIMENSIONS=1024
EMBED_DEVICE=cpu
EMBED_BATCH_SIZE=32
```

### 2.3 全局 Settings

```python
from llama_index.core import Settings, ServiceContext
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.openai import OpenAIEmbedding

Settings.llm = OpenAILike(
    model="deepseek-chat",
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base=os.getenv("OPENAI_BASE_URL"),
)
Settings.embed_model = OpenAIEmbedding(
    model="BAAI/bge-m3",
    api_key=os.getenv("EMBED_API_KEY"),
    api_base=os.getenv("EMBED_BASE_URL"),
    dimensions=int(os.getenv("EMBED_DIMENSIONS", "1024")),
)
Settings.chunk_size = 512
Settings.chunk_overlap = 50
```

---

## 三、核心概念 & 抽象

### 3.1 Document

LlamaIndex 的基本数据单元，承载文本 + 元数据。

```python
from llama_index.core import Document

doc = Document(
    text="RAG 是检索增强生成...",
    metadata={"source": "tutorial.md", "page": 1, "category": "intro"},
)
```

### 3.2 Node

Document 切分后的小块，含 `text`、`metadata`、`embedding`、`node_id`。

### 3.3 Index（索引）

数据预处理结果，支持多种类型：
- **VectorStoreIndex**：embedding 相似度
- **SummaryIndex**：全文 LLM 摘要
- **KeywordTableIndex**：关键词提取
- **KnowledgeGraphIndex**：知识图谱
- **SQLIndex**：SQL 查询

### 3.4 Retriever（检索器）

从 Index 拉取相关 Node 的接口。

```python
retriever = index.as_retriever(similarity_top_k=5)
nodes = retriever.retrieve("什么是 RAG?")
```

### 3.5 QueryEngine

Retriever + ResponseSynthesizer（拼 prompt + 调 LLM）的封装。

```python
query_engine = index.as_query_engine()
response = query_engine.query("什么是 RAG?")
```

### 3.6 StorageContext

管理 Index 的存储位置（内存 / 持久化 / 向量库）。

### 3.7 ServiceContext / Settings（旧 vs 新）

LlamaIndex 0.10+ 改用 `Settings`（全局单例）替代 `ServiceContext`（每实例）。

---

## 四、常用 API & 命令速查

### 4.1 文档加载

```python
from llama_index.core import SimpleDirectoryReader

# 读目录下所有文件
documents = SimpleDirectoryReader("./docs", recursive=True).load_data()
```

### 4.2 文本分块

```python
from llama_index.core.node_parser import SentenceSplitter

splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
nodes = splitter.get_nodes_from_documents(documents)
```

### 4.3 嵌入 + 索引

```python
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.postgres import PGVectorStore

vector_store = PGVectorStore(connection_string="postgresql://...")
storage_context = StorageContext.from_defaults(vector_store=vector_store)

index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context,
    embed_model=Settings.embed_model,
)
```

### 4.4 检索

```python
# 相似度检索
retriever = index.as_retriever(similarity_top_k=5)
nodes = retriever.retrieve("什么是 RAG?")

# 带元数据过滤
retriever = index.as_retriever(
    similarity_top_k=5,
    filters=MetadataFilters(filters=[
        MetadataFilter(key="category", value="intro", operator="=="),
    ]),
)
```

### 4.5 查询

```python
# 简单查询
query_engine = index.as_query_engine()
response = query_engine.query("什么是 RAG?")
print(response.response)       # LLM 答案
print(response.source_nodes)   # 检索到的源 nodes

# 流式
query_engine = index.as_query_engine(streaming=True)
response = query_engine.query("...")
for token in response.response_gen:
    print(token, end="")
```

### 4.6 索引持久化

```python
# 持久化到磁盘
index.storage_context.persist(persist_dir="./storage")

# 加载
from llama_index.core import load_index_from_storage
storage_context = StorageContext.from_defaults(persist_dir="./storage")
index = load_index_from_storage(storage_context)
```

---

## 五、项目集成点

### 5.1 项目主力框架

`packages/service/pyproject.toml:22-26` 显式用了 4 个 LlamaIndex 包：

| 包 | 用途 |
|------|------|
| `llama-index>=0.14.22` | 核心 |
| `llama-index-embeddings-huggingface>=0.7.0` | BGE 本地 embedder（`src/retrieval/embedder.py`） |
| `llama-index-llms-ollama>=0.10.1` | Ollama 本地 LLM（`src/generation/llm.py`） |
| `llama-index-llms-openai-like>=0.7.2` | OpenAI 兼容 LLM（`src/eval/llama_eval.py:41`） |
| `llama-index-vector-stores-postgres>=0.8.1` | pgvector 适配（`src/retrieval/vector_store.py`） |

### 5.2 项目核心 RAG 链路

```
用户问题
  ↓
src/retrieval/embedder.py:OpenAIEmbedder   # 嵌入
  ↓
src/retrieval/vector_store.py:PGVectorStore.query()  # 检索
  ↓
src/orchestration/{simple,multi_step}_rag.py  # 编排（拼 prompt + 调 LLM）
  ↓
src/generation/llm.py:OpenAILLM / LocalLLM  # 生成
  ↓
返回 ResponseEvent(response, source_nodes)
```

### 5.3 项目评估

`src/eval/router.py:23` 用 LlamaIndex 内置评估器：
- `FaithfulnessEvaluator`
- `RelevancyEvaluator`
- `CorrectnessEvaluator`
- `SimilarityEvaluator`

---

## 六、项目代码示例

### 6.1 项目 SimpleRAGWorkflow

`packages/service/src/orchestration/simple_rag.py:8-29`：

```python
from llama_index.core import VectorStoreIndex
from llama_index.core.indices.vector_store.retrievers import VectorIndexRetriever

class SimpleRAGWorkflow(BaseWorkflow):
    async def arun(self, query: str, **kwargs) -> ResponseEvent:
        # 1. 检索
        index = VectorStoreIndex.from_vector_store(
            self._vector_store, embed_model=self._embedder,
        )
        retriever = VectorIndexRetriever(index=index, similarity_top_k=self._top_k)
        nodes = retriever.retrieve(query)

        # 2. 生成
        context_str = "\n\n".join(
            n.get_content() if hasattr(n, "get_content") else str(n) for n in nodes
        )
        prompt = f"上下文：\n{context_str}\n\n问题：{query}\n\n回答："
        response_obj = self._llm.complete(prompt)
        response_text = response_obj.text if hasattr(response_obj, "text") else str(response_obj)
        return ResponseEvent(
            response=response_text, source_nodes=nodes, steps_used=["retrieve", "generate"],
        )
```

### 6.2 项目 PGVectorStore 集成

`src/retrieval/vector_store.py:73-86`：

```python
def _build_vector_store(self) -> BaseVectorStore:
    from llama_index.vector_stores.postgres.base import PGVectorStore

    cfg = self.config
    hnsw_kwargs: dict[str, Any] | None = None
    if cfg.index_type == "hnsw":
        hnsw_kwargs = {"hnsw_m": cfg.hnsw_m, "hnsw_ef_construction": cfg.hnsw_ef_construction}
    return PGVectorStore(
        connection_string=cfg.connection_string,
        embed_dim=cfg.vector_dim or _get_embed_dim(),
        hnsw_kwargs=hnsw_kwargs,
    )
```

### 6.3 项目 Embedder

`src/retrieval/embedder.py`（推测）：

```python
from llama_index.embeddings.openai import OpenAIEmbedding

class OpenAIEmbedder:
    def __init__(self):
        self._embedder = OpenAIEmbedding(
            model=os.getenv("EMBED_MODEL", "BAAI/bge-m3"),
            api_key=os.getenv("EMBED_API_KEY"),
            api_base=os.getenv("EMBED_BASE_URL"),
            dimensions=int(os.getenv("EMBED_DIMENSIONS", "1024")),
        )

    def get_text_embedding(self, text: str) -> list[float]:
        return self._embedder.get_text_embedding(text)
```

### 6.4 项目评估入口

`src/eval/llama_eval.py:41`（推测）：

```python
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.evaluation import FaithfulnessEvaluator, RelevancyEvaluator

class LlamaEvaluator:
    def __init__(self):
        self._llm = OpenAILike(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_base=os.getenv("OPENAI_BASE_URL"),
        )
        self._faith = FaithfulnessEvaluator(llm=self._llm)
        self._rel = RelevancyEvaluator(llm=self._llm)

    def evaluate(self, question, response, contexts):
        faith_result = self._faith.evaluate(
            query=question, response=response, contexts=contexts,
        )
        rel_result = self._rel.evaluate(
            query=question, response=response, contexts=contexts,
        )
        return {
            "faithfulness": faith_result.score,
            "relevancy": rel_result.score,
        }
```

### 6.5 Ingest 流程（PDF → 索引）

`src/ingest/pipeline.py`（推测）：

```python
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter

def ingest_documents(input_dir: str) -> list[str]:
    # 1. 读 PDF / DOCX / Markdown
    documents = SimpleDirectoryReader(input_dir).load_data()

    # 2. 分块
    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    nodes = splitter.get_nodes_from_documents(documents)

    # 3. 嵌入 + 入库（自动用 Settings.embed_model）
    index = VectorStoreIndex(
        nodes=nodes,
        storage_context=StorageContext.from_defaults(vector_store=pgvector_store),
    )
    return [n.node_id for n in nodes]
```

---

## 七、项目没用到的能力

以下 LlamaIndex 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **SubQuestionQueryEngine** | 多步复杂问答 | 项目用 MultiStepRAGWorkflow 自建 |
| **RouterQueryEngine** | 多个 index 路由 | 多知识库场景 |
| **ReAct Agent** | 工具调用 Agent | 见 `cookbook/rag/deepagent.md` |
| **Citation/Refining** | 答案 + 来源引用 | UI 展示来源时用 |
| **Streaming** | token-by-token 输出 | LLM 流式响应场景 |
| **HyDE（假设文档嵌入）** | 假设性 doc 检索 | 检索质量调优 |
| **Auto Merging Retriever** | 大 chunk 聚合 | 文档分块策略调优 |
| **Multi-modal（图像 / 表格）** | 多模态 RAG | 项目仅文本 |
| **Knowledge Graph Index** | 知识图谱 | 用 Neo4j 替代（`cookbook/db/neo4j.md`） |

**建议关注**：Citation（答案带来源引用）适合 B2B 场景（必须可追溯）。

---

## 八、评测 & 调优技巧

### 8.1 延迟监控

```python
import time
start = time.time()
retriever = index.as_retriever(similarity_top_k=5)
nodes = retriever.retrieve(query)
print(f"Retrieve: {time.time() - start:.3f}s")

start = time.time()
response = query_engine.query(query)
print(f"Query: {time.time() - start:.3f}s, Tokens: ...")
```

### 8.2 检索质量调优

| 调优点 | 做法 |
|--------|------|
| top_k 太小 | 答案不全 → 增大到 5-10 |
| top_k 太大 | 噪声多 → 加 rerank |
| Embedding 模型 | 切更大 / 更好的（bge-m3 / bge-large） |
| Chunk 大小 | 256 / 512 / 1024 试 |
| Chunk overlap | 0-20% 试 |
| 元数据过滤 | 加上时间 / 类别 / 来源过滤 |

### 8.3 Prompt 调优

```python
# 自定义 QA prompt
from llama_index.core.prompts import PromptTemplate

qa_prompt = PromptTemplate(
    """你是一个专业的 RAG 助手。

严格基于以下上下文回答，不要编造。如果不知道就说"无法回答"。

上下文：{context_str}
问题：{query_str}
回答："""
)

query_engine = index.as_query_engine(text_qa_template=qa_prompt)
```

### 8.4 评估

用 `src/eval/router.py` 上传 CSV 跑评估，看 Faithfulness / Relevancy / Correctness 分数。

---

## 九、最佳实践 & 常见坑

### 1. 版本兼容（关键！）

LlamaIndex 0.10→0.11→0.14 多次 breaking change：

```python
# 错（旧版 0.9.x）
from llama_index.core import ServiceContext
from llama_index.llms import OpenAI

# 对（0.10+）
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
```

注意 `VectorStoreRetriever` 在新版改名 `VectorIndexRetriever`（项目代码已处理：`src/orchestration/simple_rag.py:19`）。

### 2. async 陷阱

```python
# 错：同步方法里 await
def handle():
    return await query_engine.aquery(query)  # 没用！

# 对
async def handle():
    return await query_engine.aquery(query)
```

### 3. Token 上限

LlamaIndex 默认 prompt 模板较长，4 个 source nodes 就能超过 4K token。监控 + 截断。

### 4. 嵌入成本

`BAAI/bge-m3` 单次 ~3K token，10K 文档嵌入一次 ~30M token。**嵌入文本是数据预处理时一次性的**，query 时是单条小文本。

### 5. 项目测试隔离

项目 `service/CLAUDE.md` 强制 mock。`Settings.embed_model` 和 `Settings.llm` 在测试必须 mock：

```python
from unittest.mock import patch, MagicMock

@patch("src.retrieval.embedder.OpenAIEmbedder")
def test_retrieve(mock_embedder):
    mock_embedder.return_value.get_text_embedding.return_value = [0.1, 0.2, ...]
    # ...
```

### 6. 索引不要每请求重建

`VectorStoreIndex.from_vector_store(...)` 是**只读连接**，不需要重建。`from_documents(...)` 才是写入。

### 7. 持久化 vs 实时

`pgvector` 存的就是持久化数据，restart 不丢。无需额外 `persist()`。

### 8. 元数据过滤性能

`MetadataFilters` 在 pgvector 上走 WHERE 条件。给过滤字段加索引（`CREATE INDEX`）能大幅加速。

---

## 📚 参考

- [LlamaIndex 官方文档](https://docs.llamaindex.ai/)
- [LlamaIndex 0.14 release notes](https://github.com/run-llama/llama_index/releases)
- [LlamaIndex PGVector 集成](https://docs.llamaindex.ai/en/stable/examples/vector_stores/postgres.html)
- [LlamaIndex 评估](https://docs.llamaindex.ai/en/stable/module_guides/evaluating/)
- [LlamaIndex Query Engines](https://docs.llamaindex.ai/en/stable/module_guides/querying/)
- [项目 service/CLAUDE.md](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
