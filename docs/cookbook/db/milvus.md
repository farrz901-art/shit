# Milvus 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 启动](#二安装--启动)
- [三、核心概念](#三核心概念)
- [四、常用命令 & 用法速查](#四常用命令--用法速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、运维 & 最佳实践 + 常见坑](#八运维--最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

Milvus 是 LF AI & Data 基金会旗下的开源向量数据库，专门为大规模向量相似度搜索和 AI 应用设计。它支持十亿级向量毫秒级检索，提供 HNSW / IVF / DiskANN 多种索引，单节点可扩展到 100 亿向量。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Milvus** | 专业级向量数据库 | LF AI 顶级项目，10 亿级向量 |
| **pgvector** | PG 向量扩展 | 本项目**当前使用**（`src/retrieval/vector_store.py`）|
| **Qdrant** | 轻量向量数据库 | 性能好，但生态小 |
| **Weaviate** | 向量 + 模块化 | 内置多模态，资源占用大 |
| **Chroma** | 嵌入式向量库 | 仅适合小数据 / 原型 |
| **FAISS** | Facebook 向量库 | 库而非服务，运维要自己做 |

**Milvus 解决的核心问题**：
- **亿级向量**：远超 pgvector 的实用范围
- **毫秒延迟**：HNSW / IVF / DiskANN 多种 ANN 索引
- **混合检索**：向量 + 标量字段过滤
- **多租户**：partition key / database 隔离
- **水平扩展**：分片 + 副本

---

## 二、安装 & 启动

### 2.1 Docker Compose（独立部署）

```bash
# 下载官方 compose
wget https://github.com/milvus-io/milvus/releases/download/v2.5.10/milvus-standalone-docker-compose.yml -O docker-compose.yml
docker compose up -d
# 默认端口：19530 (gRPC), 9091 (HTTP), 9000 (S3 兼容)
```

### 2.2 嵌入式模式（Python）

```bash
uv add pymilvus
# 适合小数据集 / 测试，无需 Docker
```

```python
from pymilvus import MilvusClient
client = MilvusClient("./milvus_demo.db")
```

### 2.3 Attu（Web UI）

```bash
docker run -d -p 8000:3000 -e MILVUS_URL=localhost:19530 zilliz/attu:latest
# 访问 http://localhost:8000
```

### 2.4 健康检查

```bash
# HTTP 健康
curl -f http://localhost:9091/healthz

# 客户端
python -c "from pymilvus import MilvusClient; print(MilvusClient('http://localhost:19530').list_collections())"
```

---

## 三、核心概念

### 1. Collection（集合）

类似 SQL 表。每个 collection 有 schema + 索引 + 数据。

### 2. Field（字段）

每个 collection 由多个 field 组成：
- **主键字段**：`INT64` / `VARCHAR`，自动去重
- **向量字段**：`FLOAT_VECTOR` / `BINARY_VECTOR` / `SPARSE_FLOAT_VECTOR`
- **标量字段**：`INT64` / `FLOAT` / `VARCHAR` / `BOOL` / `JSON`
- **动态字段**：schema 没声明的字段自动加（`enable_dynamic_field=True`）

### 3. Index（索引）

向量字段必须建索引才能高效检索：

| 索引 | 适用场景 | 召回 | 速度 |
|------|---------|------|------|
| **HNSW** | 通用 | 极高 | 中 |
| **IVF_FLAT** | 内存充足 | 高 | 中 |
| **IVF_SQ8** | 内存紧张 | 中 | 快 |
| **DiskANN** | 超大数据（>1 亿）| 中 | 中（盘上） |
| **AUTOINDEX** | 不知道选啥 | 平衡 | 平衡 |

### 4. Partition（分区）

按 partition_key 把 collection 拆成多个分区。查询时只扫相关分区，加速检索 + 隔离。

### 5. Search vs Query

- **search**：向量相似度检索，返 top_k 距离最近的
- **query**：标量字段过滤，返符合条件的所有
- **hybrid search**：两者结合，先标量过滤再向量排序

### 6. Consistency Level

Milvus 是分布式，最终一致性。可选：
- `STRONG`：强一致，慢
- `SESSION`：会话内一致（推荐）
- `EVENTUAL`：最终一致，快
- `BOUNDED`：有限时间窗内一致

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Docker Compose
docker compose up -d milvus
docker compose down        # 停止（保留数据）
docker compose down -v     # 停止 + 删卷（数据全丢）

# 系统服务
sudo systemctl start milvus
```

### 4.2 创建 Collection

```python
from pymilvus import MilvusClient, DataType

client = MilvusClient(uri="http://localhost:19530")

# Schema
schema = client.create_schema(auto_id=True)
schema.add_field("id", DataType.INT64, is_primary=True)
schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
schema.add_field("text", DataType.VARCHAR, max_length=8192)
schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=1024)
schema.add_field("category", DataType.VARCHAR, max_length=50)
schema.add_field("created_at", DataType.INT64)

# 索引
index_params = client.prepare_index_params()
index_params.add_index(
    field_name="embedding",
    index_type="HNSW",
    metric_type="COSINE",
    params={"M": 16, "efConstruction": 200},
)
index_params.add_index(field_name="category", index_type="AUTOINDEX")  # 标量

client.create_collection(
    collection_name="rag_docs",
    schema=schema,
    index_params=index_params,
)
```

### 4.3 插入数据

```python
data = [
    {"doc_id": "d1", "text": "RAG 是...", "embedding": [0.1, 0.2, ...], "category": "intro", "created_at": 1719000000},
    {"doc_id": "d2", "text": "向量检索是...", "embedding": [0.3, 0.4, ...], "category": "tech", "created_at": 1719000001},
]
client.insert(collection_name="rag_docs", data=data)
# 返 Primary Key 列表（auto_id=True 自动生成）
```

### 4.4 向量检索

```python
# 单向量检索
query_embedding = [0.1, 0.2, ...]  # 1024 维
results = client.search(
    collection_name="rag_docs",
    data=[query_embedding],
    limit=5,
    filter="category == 'tech'",         # 标量过滤
    output_fields=["doc_id", "text"],     # 返回的字段
    search_params={"metric_type": "COSINE", "params": {"ef": 50}},
)
# [[{"id": ..., "distance": ..., "entity": {"doc_id": ..., "text": ...}}]]

# 批量检索
query_embeddings = [[0.1, ...], [0.2, ...]]
results = client.search(
    collection_name="rag_docs",
    data=query_embeddings,
    limit=5,
)
```

### 4.5 标量查询

```python
results = client.query(
    collection_name="rag_docs",
    filter="category == 'tech' and created_at > 1719000000",
    output_fields=["id", "doc_id", "text"],
    limit=100,
)
```

### 4.6 删除

```python
# 按 id
client.delete(collection_name="rag_docs", ids=[1, 2, 3])

# 按 filter
client.delete(collection_name="rag_docs", filter="created_at < 1718000000")
```

### 4.7 Hybrid Search

```python
from pymilvus import AnnSearchRequest, RRFRanker

# 多路召回 + RRF 融合
req1 = AnnSearchRequest(data=[emb1], anns_field="dense", param={"nprobe": 10}, limit=20)
req2 = AnnSearchRequest(data=[emb2], anns_field="sparse", param={}, limit=20)

results = client.hybrid_search(
    collection_name="rag_docs",
    reqs=[req1, req2],
    ranker=RRFRanker(),
    limit=5,
    output_fields=["text"],
)
```

---

## 五、项目集成点

### 5.1 项目**当前使用 pgvector**

`src/retrieval/vector_store.py:73-86` 是 `PGVectorStore` 封装。

### 5.2 Milvus 切换路径

如果将来向量规模 > 1000 万 + 复杂混合检索需求，可迁移到 Milvus。迁移要点：
1. 重写 `src/retrieval/vector_store.py` 的 `PGVectorStore` → `MilvusStore`
2. 抽象层 `BaseVectorStore` 已有类似设计（推测）
3. 业务代码用 `get_vector_store()` 工厂，跟 LangChain 一样的接口

### 5.3 Milvus 优势（vs pgvector）

| 维度 | pgvector | Milvus |
|------|---------|--------|
| 亿级向量 | 卡（PG 单表上限）| 顺 |
| 10 万 QPS | 难 | 容易 |
| 多租户 | 手工分区 | 原生 partition |
| 标量+向量混合 | SQL 强 | 弱一些 |
| 运维 | 已有 PG | 独立集群 |

### 5.4 LlamaIndex 集成

LlamaIndex 有原生 Milvus reader：

```python
from llama_index.vector_stores.milvus import MilvusVectorStore
# 跟 PGVectorStore 接口几乎一样
```

---

## 六、项目代码示例

### 6.1 Milvus store 封装（如果迁移）

`src/retrieval/milvus_store.py`（假设）：

```python
from pymilvus import MilvusClient, DataType
import os

class MilvusVectorStore:
    def __init__(self, config: "MilvusConfig" = None):
        self._client = MilvusClient(uri=os.getenv("MILVUS_URI", "http://localhost:19530"))
        self._collection = "rag_docs"

    def add(self, documents, embedder, batch_size: int = 100) -> list[str]:
        data = [
            {
                "doc_id": doc.doc_id,
                "text": doc.text,
                "embedding": embedder.get_text_embedding(doc.text),
                "category": doc.metadata.get("category", "default"),
            }
            for doc in documents
        ]
        return self._client.insert(collection_name=self._collection, data=data)

    def query(self, query_embedding: list[float], top_k: int = 5, filter: dict | None = None) -> Any:
        results = self._client.search(
            collection_name=self._collection,
            data=[query_embedding],
            limit=top_k,
            filter=_dict_to_expr(filter) if filter else None,
            output_fields=["doc_id", "text", "category"],
        )
        return results[0]  # 单 query 返 list[hit]
```

### 6.2 替换 pgvector 业务代码

`src/orchestration/simple_rag.py`（项目风格）：

```python
# 之前用 PGVectorStore
# from src.retrieval.vector_store import PGVectorStore, get_vector_store

# 切到 Milvus
from src.retrieval.milvus_store import get_vector_store

class SimpleRAGWorkflow(BaseWorkflow):
    async def arun(self, query: str, **kwargs) -> ResponseEvent:
        store = get_vector_store()  # 工厂函数，按 env 决定 impl
        embedder = OpenAIEmbedder()

        # 1. 检索
        embedding = embedder.get_text_embedding(query)
        results = store.query(query_embedding=embedding, top_k=5)
        nodes = [Hit(text=r.entity["text"], score=1 - r.distance) for r in results]

        # 2. 生成
        context_str = "\n\n".join(n.text for n in nodes)
        prompt = f"上下文：\n{context_str}\n\n问题：{query}\n\n回答："
        response = self._llm.complete(prompt)
        return ResponseEvent(response=response.text, source_nodes=nodes)
```

### 6.3 批量灌数据

```python
# 大数据 ingest：分批 + 进度日志
from loguru import logger

def bulk_insert(store, documents, batch_size: int = 500):
    total = len(documents)
    for i in range(0, total, batch_size):
        batch = documents[i:i+batch_size]
        ids = store.add(batch, embedder=embedder)
        logger.info("ingest progress {}/{} (ids: {}...{})", i + len(batch), total, ids[0], ids[-1])
    logger.info("ingest done total={}", total)
```

### 6.4 混合检索

```python
# RAG 场景：BM25 + 向量
from pymilvus import AnnSearchRequest, RRFRanker

def hybrid_search(client, query_text, query_embedding, top_k=5):
    # 1. 向量召回
    dense_req = AnnSearchRequest(
        data=[query_embedding],
        anns_field="dense_embedding",
        param={"nprobe": 16},
        limit=top_k * 2,
    )
    # 2. 全文召回（Milvus 2.4+ 内置 BM25）
    sparse_req = AnnSearchRequest(
        data=[query_text],
        anns_field="sparse_embedding",
        param={"drop_ratio_search": 0.1},
        limit=top_k * 2,
    )
    # 3. RRF 融合
    return client.hybrid_search(
        collection_name="rag_docs",
        reqs=[dense_req, sparse_req],
        ranker=RRFRanker(k=60),  # RRF k 参数
        limit=top_k,
        output_fields=["text", "doc_id"],
    )
```

---

## 七、项目没用到的能力

以下 Milvus 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Partition** | 多租户 / 按时间分区 | 1000 万 + 向量时 |
| **Multi-replica** | 高可用 | 业务对 SLA 要求高时 |
| **DiskANN** | 超大数据（>1 亿向量）| 数据爆炸时 |
| **Scalar + Vector Hybrid** | 标量 + 向量混合检索 | 项目已用 PG 混合查询 |
| **BM25 / Sparse Vector** | 全文 + 向量融合 | RAG 调优 |
| **Multi-vector（ColBERT / SPLADE）** | 细粒度检索 | 高级 RAG |
| **Database / Resource Group** | 多租户隔离 | SaaS 化时 |
| **CDC（Change Data Capture）** | 监听 collection 变更 | 实时下游 |

**建议关注**：Hybrid Search（向量 + BM25）能显著提升 RAG 召回率。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **资源规划**：1 亿 1024 维 float 向量 ≈ 400 GB 内存 + 200 GB 磁盘
2. **索引选型**：
   - < 100 万向量：HNSW
   - 100 万 - 1 亿：IVF_PQ 或 HNSW
   - > 1 亿：DiskANN
3. **备份**：`mc cp` 拷贝 MinIO 桶（Milvus 数据存 MinIO）
4. **监控**：Prometheus metrics（Milvus 自带 exporter）
5. **升级**：大版本必须按官方升级路径，跨大版本不可跳

### 常见坑

1. **向量维度不一致**：插入 768 维向量到 1024 维 collection → 报错
2. **未建索引就 search**：报错"index not found"
3. **filter 表达式语法错**：`category == "tech"` 双等号不是单等号
4. **top_k 太大**：返 1000 条全屏卡死
5. **metric_type 不匹配**：建索引用 `COSINE`，查询 `L2` → 距离全乱
6. **consistency_level 不一致**：写入后立刻查可能看不到
7. **Milvus Lite（嵌入式）≠ Milvus（服务）**：前者单进程、后者集群
8. **动态字段陷阱**：`enable_dynamic_field=True` 时，未声明的字段也能写，但 schema 不可见

### 项目测试隔离

`src/retrieval/milvus_store.py`（如果存在）在测试**不要**连真实 Milvus。Mock 客户端：

```python
from unittest.mock import MagicMock, patch

@patch("src.retrieval.milvus_store.MilvusClient")
def test_query(mock_milvus_cls):
    mock_client = MagicMock()
    mock_client.search.return_value = [[{"id": 1, "distance": 0.1, "entity": {"text": "test"}}]]
    mock_milvus_cls.return_value = mock_client
    # 测试逻辑
```

---

## 📚 参考

- [Milvus 官方文档](https://milvus.io/docs)
- [Milvus GitHub](https://github.com/milvus-io/milvus)
- [pymilvus Python SDK](https://github.com/milvus-io/pymilvus)
- [Milvus 索引选型](https://milvus.io/docs/index.md)
- [Attu Web UI](https://github.com/zilliztech/attu)
- [LlamaIndex Milvus 集成](https://docs.llamaindex.ai/en/stable/examples/vector_stores/MilvusIndexDemo.html)
- [项目 cookbook/db/postgres.md](postgres.md)（pgvector 当前方案）

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
