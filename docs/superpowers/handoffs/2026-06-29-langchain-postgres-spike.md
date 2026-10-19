# Spike: langchain-postgres 0.0.17 真实 API (2026-06-29)

本 spike 验证 spec `2026-06-29-langchain-replace-llamaindex-design.md` v2.1 §5.6 对 `langchain-postgres` API 的假设是否正确, 避免后续 commit 全建在错误假设上.

## 跑法

```bash
cd packages/service
uv run pytest tests/spike/test_langchain_postgres_spike.py -v -m integration
```

需要 `.env.local` 配 PG_* + EMBED_* (dev DB), 真连 pgvector 跑 add/query/delete.

## 结论

3 个 spike test 全 PASS, spec §5.6 API 假设大体正确, 但有 3 个偏差必须正式实施前处理.

- [✅] `PGEngine.from_connection_string(url=...)` — 真实签名 `(url: str | URL, **kwargs) -> PGEngine`
- [✅] `engine.init_vectorstore_table(table_name, vector_size, overwrite_existing)` — 真实签名见下, kw-only
- [✅] `PGVectorStore.create_sync(engine, embedding_service, table_name)` — 真实签名见下
- [✅] `store.add_texts(texts, metadatas, ids=None)` 返 `list[str]` (uuid 字符串)
- [✅] `store.similarity_search_by_vector(query_vec, k)` 返 `list[Document]`
- [✅] `Document` 有 `page_content: str` + `metadata: dict` (langchain_core.documents)
- [✅] `ref_doc_id` 走 `langchain_metadata` 列, 原生 SQL `langchain_metadata->>'ref_doc_id'` 工作 (但**底层是 json 不是 jsonb**, 见偏差 #1)
- [✅] `PGVectorStore.add_texts` 写入后 `similarity_search_by_vector` 可读 (内部走 cosine distance)

## 实际 API 跟 spec §5.6 偏差

### 偏差 #1 [严重] `langchain_metadata` 列是 `json` 不是 `jsonb`

跑 `\d spike_test_langchain_pg` 输出:

```
columns:
  langchain_id              uuid                  nullable=NO
  content                   text                  nullable=NO
  embedding                 vector(1024)          nullable=NO  (USER-DEFINED)
  langchain_metadata        json                  nullable=YES   <-- 不是 jsonb!
indexes:
  spike_test_langchain_pg_pkey on (langchain_id)  <-- 没自动建 IVFFLAT/HNSW
```

跟项目 CLAUDE.md "JSONB 使用规范 (2026-06-25 json-jsonb spec)" 直接冲突:

> 新列必须 JSONB, 禁止 sa.JSON()

且原生 SQL `langchain_metadata->>'ref_doc_id'` 在 PG 上 json 跟 jsonb 都支持, 但 jsonb 才有 GIN index. langchain-postgres 0.0.17 内置不建 GIN.

**正式实施处理**: 跑 `init_vectorstore_table` 后, 自己跑 ALTER 把列改 jsonb + 建 GIN index, 或考虑后续 PR 给 langchain-postgres.

### 偏差 #2 [中] `init_vectorstore_table` 不建 vector index

spike 表只有 pkey 索引, 没建 IVFFLAT / HNSW. spec §5.6 隐含 "建表即建索引", 实际需显式调 `store.apply_vector_index(...)` (sync API 已 expose).

**正式实施处理**: `init_vectorstore_table` 后调一次 `apply_vector_index(...)`, 用 .env.local 的 PG_INDEX_TYPE / PG_HNSW_M 等参数.

### 偏差 #3 [小] `PGEngine.close()` 是 coroutine, 不是同步方法

```python
eng = PGEngine.from_connection_string(url=...)
eng.close()  # ❌ RuntimeWarning: coroutine 'PGEngine.close' was never awaited
await eng.close()  # ✅
```

且 PGEngine 不暴露 `.connect()` 或同步 SA Engine 出口 — 业务跑 raw SQL DELETE 必须自己 `create_engine()` 单独拿 SA Engine.

**正式实施处理**: 业务代码持有 2 个 engine — PGEngine (给 langchain) + SA Engine (给 raw SQL DELETE / GIN index 创建). 单进程内共享 connection pool 不冲突 (psycopg3 池化).

## 平台 / 环境特殊问题 (跟 spec 无关, 但需要记)

### Windows ProactorEventLoop 跟 psycopg3 async 不兼容

```
sqlalchemy.exc.InterfaceError: (psycopg.InterfaceError) Psycopg cannot use the
'ProactorEventLoop' to run in async mode.
```

修法 (`tests/spike/conftest.py`):

```python
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

**注意**: `WindowsSelectorEventLoopPolicy` 在 Python 3.16 移除 (DeprecationWarning). 项目用 Python 3.14, 临时可用, 但后续要找替代 (asyncio.run loop_factory 参数).

**正式实施处理**: 业务侧 main.py / FastAPI lifespan 需在 Windows dev 跑前显式切 SelectorEventLoop. Linux 容器 (生产) 不受影响.

### bge-m3 (SiliconFlow) 不支持 OpenAI `dimensions` 参数

```python
OpenAIEmbeddings(model="BAAI/bge-m3", dimensions=1024)  # ❌ 400 invalid param
OpenAIEmbeddings(model="BAAI/bge-m3", check_embedding_ctx_length=False)  # ✅
```

bge-m3 固定 1024 维 (服务端 hard-code), `dimensions` 是 OpenAI text-embedding-3 系列私有特性, SiliconFlow 不实现. 同时 `check_embedding_ctx_length=False` 跳过 tiktoken 编码 (bge-m3 用 XLM-RoBERTa tokenizer, ≠ OpenAI tiktoken).

**正式实施处理**: 业务初始化 OpenAIEmbeddings 时不传 dimensions + 设 check_embedding_ctx_length=False. EMBED_DIMENSIONS env 仅用来跑 `init_vectorstore_table(vector_size=...)`, 不传给 embedder.

## API 真实签名 (供后续实施 copy-paste)

```python
# 创建 engine
PGEngine.from_connection_string(url: str | URL, **kwargs) -> PGEngine
PGEngine.from_engine(engine: AsyncEngine) -> PGEngine

# 建表 (kw-only, 注意 vector_size 必传)
engine.init_vectorstore_table(
    table_name: str,
    vector_size: int,  # = EMBED_DIMENSIONS
    *,
    schema_name: str = "public",
    content_column: str = "content",
    embedding_column: str = "embedding",
    metadata_columns: list[Column | ColumnDict] | None = None,
    metadata_json_column: str = "langchain_metadata",  # 这是 json 不是 jsonb!
    id_column: str | Column | ColumnDict = "langchain_id",
    overwrite_existing: bool = False,
    store_metadata: bool = True,
    hybrid_search_config: HybridSearchConfig | None = None,
) -> None

# 创建 store (k/fetch_k/lambda_mult 都有默认值, 业务一般用默认)
PGVectorStore.create_sync(
    engine: PGEngine,
    embedding_service: Embeddings,
    table_name: str,
    schema_name: str = "public",
    content_column: str = "content",
    embedding_column: str = "embedding",
    metadata_columns: list[str] | None = None,
    ignore_metadata_columns: list[str] | None = None,
    id_column: str = "langchain_id",
    metadata_json_column: str = "langchain_metadata",
    distance_strategy: DistanceStrategy = DistanceStrategy.COSINE_DISTANCE,
    k: int = 4,
    fetch_k: int = 20,
    lambda_mult: float = 0.5,
    index_query_options: QueryOptions | None = None,
    hybrid_search_config: HybridSearchConfig | None = None,
) -> PGVectorStore

# 写入
store.add_texts(
    texts: Iterable[str],
    metadatas: list[dict] | None = None,
    ids: list | None = None,
    **kwargs,
) -> list[str]  # uuid 字符串

# 查询
store.similarity_search_by_vector(
    embedding: list[float],
    k: int | None = None,  # None 取 create_sync 时的 k=4
    filter: dict | None = None,  # JSONB filter 支持 (但底层是 json, 性能未验)
    **kwargs,
) -> list[Document]  # langchain_core.documents.Document

# 关闭 (await!)
await engine.close()
```

## 后续 (Task 1-N 实施动作项)

1. **Task 1 vector_store.py** 跟 spec §5.6 写得一致, 但要加 2 步: (a) `init_vectorstore_table` 后 ALTER `langchain_metadata` 改 jsonb + 建 GIN, (b) 调 `apply_vector_index` 建 IVFFLAT/HNSW.
2. **业务持有 2 engines**: `PGEngine` (langchain-postgres) + `sqlalchemy.Engine` (raw SQL DELETE / 索引维护). 注释解释为啥.
3. **embedder 工厂** 不传 `dimensions`, 传 `check_embedding_ctx_length=False`. 单独抽到 `embedder.py` 跟项目老 BGE 实现切换.
4. **Windows dev 启动** 加 SelectorEventLoop policy (uvicorn lifespan 或 main.py 顶部).
5. **业务跑 raw SQL DELETE ref_doc_id** 用 jsonb 操作符 `langchain_metadata @> '{"ref_doc_id": "..."}'::jsonb` 可走 GIN; 现 `->>'ref_doc_id' = ...` 走 json 是 seq scan.
6. **spec §5.6 v2.1 需更新** 加: (a) JSONB 转换步骤, (b) vector index 显式 apply, (c) Windows event loop 注释.

## 文件改动 (spike commit)

- `packages/service/pyproject.toml`: 加 3 个依赖
- `packages/service/uv.lock`: 同步
- `packages/service/tests/spike/__init__.py`: 空文件
- `packages/service/tests/spike/conftest.py`: Windows SelectorEventLoop 修正
- `packages/service/tests/spike/test_langchain_postgres_spike.py`: 3 个 spike test
- `docs/superpowers/handoffs/2026-06-29-langchain-postgres-spike.md`: 本文件

## 清理

跑完 spike 后 `spike_test_langchain_pg` 表已 DROP (spike 跑完留 dev DB 干净).

Task 1 正式实施后, spike 文件可删 (留 git 历史即可), 但建议先留着, 等正式 vector_store.py 跑通后再删.
