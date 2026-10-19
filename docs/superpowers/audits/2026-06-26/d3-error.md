# D3: Error handling & Resilience 扫描结果

> 扫描时间: 2026-06-26
> Agent 角色: 偏韧性视角 — 假设所有外部依赖都不可用
> 工具调用次数: 20 / 30
> 找到 6 条 finding (verified: 6, refuted: 0, 待 verify: 0)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径:
  - packages/service/src/core/redis_client.py (熔断器 + facade)
  - packages/service/src/storage/object_store.py (MinIO + LocalFS impl)
  - packages/service/src/middleware/auth.py (鉴权中间件)
  - packages/service/src/core/errors.py (全局 exception handlers)
  - packages/service/src/core/logging.py (PII scrub + error sink)
  - packages/service/src/core/lifespan.py (启动/关闭钩子)
  - packages/service/src/core/rate_limiter.py (Redis 限流)
  - packages/service/src/core/pii_fields.py (PII 字段定义)
  - packages/service/src/chat/service.py + router.py
  - packages/service/src/kg/neo4j.py + client.py + router.py
  - packages/service/src/integrations/dify_client.py + dify_datasets.py
  - packages/service/src/memory/mem0_client.py
  - packages/service/src/approvals/executor.py
  - packages/service/src/generation/llm.py + query_engine.py
  - packages/service/src/api/routes.py
  - packages/service/src/storage/session.py
  - packages/service/src/health/checks.py
  - packages/service/src/product_decoders/router.py
  - packages/service/src/lookups/cache.py
  - packages/service/scripts/neo4j_import.py
  - Grep: `except Exception`, `except:`, `except BaseException`, `@app.exception_handler`, `timeout`, `max_tokens`
- 已知跳过:
  - 前端代码 (D5 范围)
  - Neo4j driver 的底层面板配置 (仅读 Python 代码层)
  - 第三方库的默认超时行为 (如 httpx 默认 5s 无 timeout 时)
- 备注: 代码库在 Redis 熔断和 fail-open 方面设计良好 (redis_client.py 有完整 circuit breaker + facade 降级)。主要发现集中在 Neo4j 无韧性保护、500 响应泄露 details、以及 LLM 无 max_tokens 预算。

## Findings (6 条)

- id: ERR-001
  dimension: error
  severity: medium
  confidence: high
  title: "3 个 /api/v1 端点返回 str(e) 到 500 响应体"
  file: packages/service/src/api/routes.py
  line: 62
  description: |
    query_endpoint / evaluate_endpoint / ingest_endpoint 三个端点在捕获 Exception 后直接 raise HTTPException(500, detail=str(e))。全局 exception_handler 对 HTTPException 原样透传 detail，导致异常消息 (可能包含路径、模型名、列名) 落到客户端。虽非完整 traceback，但仍比 global handler 的 "Internal server error" 泄露更多信息。
  evidence: |
    ```python
    # query_endpoint (routes.py:61-62)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # evaluate_endpoint (routes.py:108-109)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # ingest_endpoint (routes.py:145-146)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    ```
  impact: |
    生产环境这些端点标记为 "内部脚本 / 离线评估流水线用"，但若暴露到公网，攻击者可观测到后端实现细节：模型名、embedder 类型、pgvector 连接字符串局部、文件系统路径等。配合其他信息可缩小攻击面。
  fix_sketch: |
    三个端点改为 raise HTTPException(500, detail="Internal server error") 或移除 catch，让全局 unhandled_exc handler 统一处理。保留 loguru 日志用于调试。
  references:
    - owasp-a04:2021

- id: ERR-002
  dimension: error
  severity: medium
  confidence: high
  title: "Neo4jStore 驱动无连接超时配置，请求可能挂起 30s"
  file: packages/service/src/kg/neo4j.py
  line: 44
  description: |
    Neo4jStore 使用 neo4j.GraphDatabase.driver() 创建驱动时仅传 uri 和 auth，未传 connection_timeout、connection_acquisition_timeout、max_connection_lifetime 等参数。Neo4j Python driver 默认 connection_timeout 为 30s，意味着 Neo4j 不可达时每个请求会阻塞 30s 才超时。在大量并发请求下会快速耗尽量程池。
  evidence: |
    ```python
    @property
    def driver(self) -> Any:
        if self._driver is None:
            import neo4j
            self._driver = neo4j.GraphDatabase.driver(
                self._config.uri,
                auth=(self._config.username, self._config.password),
                # 缺少 connection_timeout
                # 缺少 connection_acquisition_timeout
                # 缺少 max_connection_lifetime
            )
        return self._driver
    ```
  impact: |
    Neo4j 宕机时 /api/kg/nodes、/api/kg/relationships、/api/kg/products、/api/kg/triples 等端点每个请求挂起 ~30s。FastAPI 默认线程池有限，导致所有依赖该线程池的端点（包括非 KG 端点）排队等待，形成级联故障。
  fix_sketch: |
    在 driver() 中传入 connection_timeout=5 和 connection_acquisition_timeout=10，与 Redis 的 2s 超时对齐，并定期 max_connection_lifetime=1800 防止连接过期。
  references: []

- id: ERR-003
  dimension: error
  severity: high
  confidence: high
  title: "Neo4j 批量写入 batch_upsert_triples 无重试机制"
  file: packages/service/src/kg/client.py
  line: 92
  description: |
    KgClient.batch_upsert_triples 的组内 execute_and_fetch 调用无重试逻辑。Neo4j 连接超时或瞬态故障（如主从切换、负载高）导致整组写入失败，errors 仅收集 str(e) 消息而不重试。对比 Dify 客户端（dify_datasets.py、dify_client.py）使用 tenacity retry + 3 次指数退避，Neo4j 操作完全没有重试。
  evidence: |
    ```python
    # kg/client.py:87-95 — 无重试，一旦失败直接收集
    for group_rows in groups.values():
        cypher, params = self._build_unwind_cypher(group_rows)
        try:
            self._store.execute_and_fetch(cypher, params)
            success += len(group_rows)
        except Exception as e:  # noqa: BLE001
            failed += len(group_rows)
            errors.append(str(e))
    ```
  impact: |
    生产环境中批量写入（几十到几千条三元组）在 Neo4j 瞬态故障下整组失败，用户必须重新提交整个请求。数据导入流程（Excel 导入、approvals executor）可靠性受影响。
  fix_sketch: |
    在 execute_and_fetch 外层加 tenacity @retry（3 次，wait_exponential），只重试网络超时 / 5xx 类异常，保留 4xx/数据错误直接透传。与 Dify 客户端模式一致。

- id: ERR-004
  dimension: error
  severity: high
  confidence: high
  title: "Neo4j 客户端无熔断器，宕机时持续重试"
  file: packages/service/src/kg/neo4j.py
  line: 44
  description: |
    Neo4j 客户端没有类比 Redis 熔断器的机制。Redis 有 _is_circuit_open / _trip_circuit / _reset_circuit_if_due 实现熔断降级（30s 内静默返回空/降级值），而 Neo4j 每次请求都试图建立新连接。在 kg/router.py 中，list_nodes / list_relationships / get_schema 等端点都调 Neo4jStore，当 Neo4j 宕机时每个请求都完整尝试连接-超时-异常流程。
  evidence: |
    ```python
    # neo4j.py:39-48 — 无熔断保护，每次请求都直连
    @property
    def driver(self) -> Any:
        if self._driver is None:
            import neo4j
            self._driver = neo4j.GraphDatabase.driver(
                self._config.uri,
                auth=(self._config.username, self._config.password),
            )
        return self._driver

    # compare: redis_client.py:39-62 有完整的熔断实现
    # — 但 kg 模块中没有类似组件
    ```
  impact: |
    Neo4j 宕机时，每秒钟数十个请求会持续尝试连接，产生大量无意义的 socket 连接和异常日志。不降级时还可能因默认 30s 超时加剧线程耗尽。框架引入 Redis 熔断器后（2026-06-23），Neo4j 是唯一未受保护的外部依赖。
  fix_sketch: |
    为 Neo4jStore 加熔断封装（包装 driver() 调用或在 KgClient 层加 _circuit_open_until），模式参考 redis_client.py。熔断开启期间返回默认值（空列表 / 零计数），并在异常日志中降低频率。

- id: ERR-005
  dimension: error
  severity: medium
  confidence: high
  title: "OpenAILLM 的 max_tokens 默认为 None，无 token 预算上限"
  file: packages/service/src/generation/llm.py
  line: 24
  description: |
    OpenAILLM.__init__ 的 max_tokens 参数默认 None，仅在显式传入时才传给底层 OpenAILike。这意味着未指定 max_tokens 的调用方（如 query_endpoint、evaluate_endpoint）可以使用无限 token。LocalLLM (Ollama) 甚至完全不支持 max_tokens 参数。用户可以提交任意长的 prompt，后端按 token 计费无限生成。
  evidence: |
    ```python
    # generation/llm.py:18-56
    class OpenAILLM:
        def __init__(
            self,
            model: str | None = None,
            api_key: str | None = None,
            temperature: float = 0.0,
            max_tokens: int | None = None,  # 默认为 None
        ):
            ...
            kwargs: dict[str, Any] = {
                "model": self.model,
                ...
            }
            if self._max_tokens is not None:  # None 时不传
                kwargs["max_tokens"] = self._max_tokens
            self._llm = OpenAILike(**kwargs)

    # query_engine.py:61-63 — 调用时未传 max_tokens
    def get_llm(llm_type=None, model=None, **kwargs):
        return OpenAILLM(model=model, **kwargs).llm  # max_tokens 不传则 None
    ```
  impact: |
    恶意用户可通过 API 端点发送极长 prompt 或要求无限生成，导致 LLM API 费用失控、响应耗时过长耗尽 worker 资源。即使按 token 计费的外部 API 有服务端限制，本地部署的模型（Ollama）会一直生成本地 GPU/OOM。
  fix_sketch: |
    OpenAILLM.__init__ 的 max_tokens 加合理默认值（如 4096），允许调用方临时覆盖更大值但记录审计告警。LocalLLM 应增加 max_tokens 支持（Ollama 参数原生支持 num_predict）。

- id: ERR-006
  dimension: error
  severity: low
  confidence: high
  title: "kg/router.py /products 缺降级处理，Neo4j 不可达时返回 500"
  file: packages/service/src/kg/router.py
  line: 375
  description: |
    list_products 端点直接调用 KgClient()._store.execute_and_fetch()，未用 try/except 包裹。对比同级 /nodes、/relationships、/stats、/datasets 等端点都使用 graceful degradation（Neo4j 不可达时返空列表或零计数），/products 是唯一抛出 500 的端点。
  evidence: |
    ```python
    # kg/router.py:375-383 — 无 try/except
    def list_products(q: str = "", limit: int = 50) -> list[dict]:
        cypher = (...)
        rows = KgClient()._store.execute_and_fetch(cypher, {"q": q, "limit": limit})
        return [{"id": str(r["id"]), "model": r["model"], "name": r["name"]} for r in rows]

    # 对比 list_nodes:270-271 有 graceful degradation
    def list_nodes(skip: int = 0, limit: int = 100) -> list[dict]:
        try:
            return KgClient().list_nodes(skip=skip, limit=limit)
        except Exception:
            return []
    ```
  impact: |
    Neo4j 宕机时前端 combobox 区域白屏（500 响应），而其他 KG 页面区域正常工作。用户体验不一致，且 500 会触发 sentry/alert 造成不必要的告警。
  fix_sketch: |
    给 list_products 加 try/except 返回空列表，与 list_nodes / list_relationships 行为一致。如需保留 "combobox 关键数据" 语义可改为抛 503 而不是 500，并让前端显示 "Neo4j 暂不可用" 提示。

## 未扫 / 已知缺口

- neo4j.py 的连接池配置仅在 Python 代码层检查，未实际连接测试验证默认超时值
- 前端（packages/web/）的 LLM 调用不在本维度范围（见 D5 Frontend pitfalls）
- `scripts/neo4j_import.py` 中的 `except Exception: pass` 是 CLI 脚本编码适配，不是生产运行时路径，lower severity 不单独列 finding
- Dify 客户端的 tenacity 重试配置（3 次指数退避 1-10s）已足够好，未发现明显问题
- `session_scope()`（session.py:37-39）的 `except Exception: rollback(); raise` 是正确的"re-raise after rollback"模式，不视为缺陷
- Lookups cache subscriber（lookups/cache.py）已有重连 + 退避机制，不重复列发现
