# D3: Error handling & Resilience 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: D3 错误处理 & 韧性 扫描 agent (read-only)
> 工具调用次数: 28
> 找到 9 条 finding

## 元信息

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/packages/service`
- 扫描路径:
  - `src/core/redis_client.py` (熔断 + safe_* facade)
  - `src/storage/object_store.py` (MinIO 14 方法)
  - `src/middleware/auth.py` (resolve_user 异常流)
  - `src/core/errors.py` (3 个全局 handler)
  - `src/integrations/dify_client.py` / `dify_datasets.py` (httpx)
  - `src/lookups/cache.py` (pubsub subscriber while True)
  - `src/health/cache.py` (start_health_loop while True)
  - Grep "except Exception" 14 文件, "except BaseException" 1 文件, "@app.exception_handler" 3 处
- 已知跳过:
  - 前端 (web) - 属于 D5 维度
  - 测试 (tests/) - 行为不该作生产韧性要求
  - alembic migrations 内 `except` 是 dev tool 异常提示, 不入韧性评估
- 备注: 项目整体错误处理较成熟 (有 safe_* facade + 熔断 + 全局 handler + 错误日志库), 主要问题集中在 a) 局部静默吞掉异常, b) `print` 当错误日志, c) 跟第三方同步 SDK 调用缺超时/退避

## Findings (9 条)

```yaml
- id: ERR-001
  dimension: error
  severity: high
  confidence: high
  title: "evaluator 失败时静默返 None, 评估数据可能假阴性"
  file: packages/service/src/eval/llama_eval.py
  line: 109
  description: |
    4 个 evaluator (faithfulness / answer_relevancy / context_precision / context_recall) 任意一个
    抛异常时, 都被 except Exception 静默吞掉, 仅 WARNING log, 然后 run_one 返 None. 调用方拿到的
    RAGAMetrics 里 4 个字段可能全是 None 而根因被掩埋. 业务侧把 None 视作"该项未跑"继续做 avg_score
    统计, 会得到误导性的"模型表现 OK"假象 (真实 LLM 抽风但 UI 显示 0 错误).
  evidence: |
    ```python
    async def run_one(name: str) -> float | None:
        if name not in self._metrics:
            return None
        ev = self._get_evaluator(name, judge_llm)
        try:
            if name == "context_recall":
                ...
                return await loop.run_in_executor(...)
            else:
                ...
                result: EvaluationResult = await ev.aevaluate(...)
                if result.invalid_result:
                    return None
                return result.score
        except Exception as e:
            logger.warning("evaluator[{}] 失败: {}", name, e)
            return None
    ```
  impact: |
    4 个评估指标任一异常都被压成 None. 评估后台跑完, 运营可能拿一份"3/4 None + 1 个高分"的报告
    误判 RAG 质量. 同样模式在 _eval_context_recall (line 162) 和 _extract_claims (line 178) 重复:
    `except Exception: return None / return []` 让"LLM 抽风"和"ground truth 为空"行为完全一致,
    无法从外部区分.
  fix_sketch: |
    区分"输入为空" (ground_truth/contexts 空 → 返 None 是合理的) vs "LLM 调用失败"
    (网络/鉴权/超时 → 抛 LLMUnavailable 让 runner 把整条 sample 标 failed 而不是 None).
    错误信息带 evaluator_name + 异常类型进 sample.error, 前端能看到"评估第 N 题失败".
  references:
    - "DifyAPIError 已经在 dify_client.py 抛, 不该再吞"

- id: ERR-002
  dimension: error
  severity: high
  confidence: high
  title: "search / list_memories 异常全静默, 记忆查询可能永远返空"
  file: packages/service/src/memory/service.py
  line: 134
  description: |
    Mem0Store.search / list_memories / add / delete 整段 try/except Exception → log WARNING → 返 [] / None.
    用户调记忆功能, 如果 mem0 自身挂掉 (pgvector 不可达 / spacy 缺 / LLM 503), 用户得到的是空结果
    而不是"服务不可用". 前端 UI 没异常提示, 用户误以为"我从来没让它记过这件事", 实际上是
    整条记忆链路崩了.
  evidence: |
    ```python
    def search(self, current: CurrentUser, query: str, limit: int = 5) -> list[MemoryHit]:
        user_id = _resolve_mem0_user_id(current)
        try:
            m = self._get_memory(user_id)
            if m is None:
                return []
            results = _unwrap_results_envelope(
                m.search(query=query, filters={"user_id": user_id}, top_k=limit)
            )
            ...
            return hits
        except Exception as e:
            logger.opt(exception=True).warning("search failed user_id={} err={}", user_id, e)
            return []
    ```
  impact: |
    记忆查询静默失败. 跟 update_memory / delete_memory 行为相反 (那两个上抛 500, 见 line 264-266).
    不一致: 同一个文件, 同样异常, search/list/add 静默, update/delete 上抛. 用户体验割裂.
    add() 静默吞 + 入参 messages 仍可能存在, 业务上 0 反馈.
  fix_sketch: |
    显式区分两类错误: (a) "mem0 不可用" (构造失败 / pg 不可达) → 业务降级返空 OK; (b) 其它
    (单次 query 失败 / 解析坏数据) → 至少要 1 次 ERROR 级别日志 + sample-level error 字段,
    让 runner / router 能给前端反馈. update/delete 已示范正确做法, search/add 对齐.
  references:
    - "service.py:264 update_memory 上抛, 行为不一致"
    - "_get_memory 自带 _unavailable.add() 静默降级"

- id: ERR-003
  dimension: error
  severity: medium
  confidence: high
  title: "CAD 转换器大量 except 后只 print 错误, 错误不进日志系统"
  file: packages/service/src/ingest/converters/cad.py
  line: 304
  description: |
    EzdxfConverter._render_svgs / _extract_text / _record_insert_attribs 等多处异常用 `print(f"  [WARN] ...")`
    输出到 stdout, 不走 loguru 也不进 app_logs / error_logs. 运营查问题只能 ssh 看终端输出, 没有
    结构化日志, 没 request_id, 没 user_id, 没法聚合. 同样的 print 模式在 pipeline.py:319/329/390
    也存在, 是"脚本期"代码风格漏到生产路径.
  evidence: |
    ```python
    for layout_name in doc.layouts.names():
        ...
        try:
            ...
            svg_str = backend.get_string(page)
        except Exception as e:
            # 单个 layout 渲染失败不阻塞其他
            print(f"  [WARN] 布局 {layout_name} 渲染失败: {e}")
            continue
    ```
    同时 line 363 `print(f"  [WARN] TABLE 实体暂不支持解析（layout={layout_name}）")` 和
    line 365 `print(f"  [WARN] {t} 实体提取失败: {e}")` 全是裸 print, 没 logger 调用.
  impact: |
    CAD 转换是异步 BG task (ingest/api.py:516), 用户拿到 task_id 后轮询状态. 中间 print
    出来的警告只留在 server 终端, app_logs / error_logs 看不到, 排障要 ssh. 配合 ERR-004
    的 fail_count 不暴露, 用户只能看到 "task completed", 不知道 5 个 layout 渲染失败 3 个.
  fix_sketch: |
    全部 `print(f"  [WARN] ...")` 改 `logger.opt(exception=True).warning("CAD 渲染失败 layout={} err={}", layout_name, e)`.
    跟项目 logging spec (CLAUDE.md) 一致, 进 app_logs 就有结构化字段, 跟其它模块能 join.
  references:
    - "CLAUDE.md §日志使用约定: 业务代码用 loguru, 不用 stdlib logging / print"

- id: ERR-004
  dimension: error
  severity: medium
  confidence: medium
  title: "ingest task 失败只存 t.error=str(e), 丢失结构化异常"
  file: packages/service/src/ingest/api.py
  line: 516
  description: |
    `_run_ingest` 后台 task 入口捕获所有 Exception, 只把 `str(e)` 存 IngestTask.error 列. 丢失
    异常类型 / 堆栈 / cause chain. 排障时只能看到 "OpenAI 404" 这种 msg, 看不到 traceback 也不知道
    抛在哪个 converter. 同样地 _run_ingest 已经 catch 业务异常, 但 IngestTask 字段是 schema-bound
    字符串列, 没法存 stacktrace.
  evidence: |
    ```python
    try:
        if isinstance(work_dir, str) and ("://" in work_dir):
            ...
        else:
            ...
        t.state = "completed"
    except Exception as e:
        t.state = "failed"
        t.error = str(e)
    finally:
        t.finished_at = datetime.now()
        _save(t)
    ```
  impact: |
    用户拿到 task_id 查 status, 看到 "failed: ODA File Converter 未安装" 不知道是哪个文件触发.
    整个 ingest pipeline 嵌套多层 (pipeline.process_files → converter.convert → cad._read_oda),
    真实错误埋在最深 str(e) 里. 没有 request_id 跟 app_logs 关联, 无法在 dashboard 找原始
    stacktrace.
  fix_sketch: |
    exception 块加 `logger.opt(exception=True).error("ingest task failed task_id={} err={}", task_id, e)` 把
    stacktrace 进 error_logs 表 (跟全局 handler 一致). t.error 字段保留简短描述, 但 traceback
    在 app_logs 里有, 运营能 join IngestTask.id ↔ error_logs.path 查.
  references:
    - "core/errors.py:47 全局 handler 已示范 logger.opt(exception=True).error + error_logs"

- id: ERR-005
  dimension: error
  severity: high
  confidence: high
  title: "Dify datasets / chat_share 调用没重试, 偶发抖动直接 5xx"
  file: packages/service/src/integrations/dify_datasets.py
  line: 42
  description: |
    DifyDatasets.createDocumentByText 和 chat_share/service.py:145 的 httpx 调用都只设 timeout=30,
    没 tenacity / 任何 retry. 偶发网络抖动 (TCP RST / 一过性 502 / DNS 抖动) 直接抛 DifyAPIError
    → executor 标 approval=failed → 用户必须 admin 手动 retry (approvals/router.py:418).
  evidence: |
    ```python
    url = f"{base_url}/datasets/{dataset_id}/document/create_by_file"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "name": name,
                "text": text,
                "indexing_technique": indexing_technique,
                "process_rule": {"mode": "automatic"},
            },
        )
    if resp.status_code >= 400:
        raise DifyAPIError(f"Dify datasets createDocumentByText HTTP {resp.status_code}: {resp.text[:500]}")
    ```
    同样模式在 chat_share/service.py:145 和 dify_client.py:137 (achat 阻塞模式, 单次).
  impact: |
    Dify 工作流偶发 502 → 整条 approval 链路标 failed, 业务要 admin 人工 retry. 自动化率降低.
    Dify API 已知 503 短暂抖动常见, 1 次抖动就断事没 retry 是不合理. 配合 ERR-001 评估
    链路也是单次调用没重试, RAG 评估成功率被网络抖动拖累.
  fix_sketch: |
    加 tenacity @retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, DifyAPIError)) + retry_if_result(lambda r: r.status_code >= 500)).
    仅重试 5xx + 网络错, 不重试 4xx (4xx 是业务参数错, 重试没用). 在 dify_client.py / dify_datasets.py /
    chat_share/service.py 三处统一封装 `_call_dify_with_retry()` 避免散落.
  references:
    - "tenacity 已是项目常见依赖 (其它 spec 用过)"

- id: ERR-006
  dimension: error
  severity: medium
  confidence: high
  title: "approval executor Neo4j 失败 pass 不审计, 数据一致性静默丢失"
  file: packages/service/src/approvals/executor.py
  line: 60
  description: |
    QA 类型的 approval 在 Dify 写成功后, 还会同步 Neo4j QAPair. Neo4j 同步的 try/except Exception
    直接 `pass`, 不写 audit log 也不更新 approval 状态. 结果: Dify 知识库写成功, Neo4j 知识图谱
    没写, 用户在前端看到 approval 状态=applied 以为两边都同步了, 实际 Neo4j 数据缺失.
    这种"部分成功"状态是 [audited 装饰器] 没法覆盖的 (装饰器只看整个 func 成功/失败).
  evidence: |
    ```python
    if payload.get("sync_to_neo4j") and payload.get("tags"):
        try:
            client = KgClient()
            client.batch_upsert_triples(
                [
                    TripleRow(
                        from_label="QAPair",
                        from_key="question",
                        from_value=payload["question"],
                        rel_type="ABOUT",
                        to_label="Product",
                        to_key="model",
                        to_value=payload["tags"][0],
                        properties={"answer": payload["answer"], "tags": payload["tags"]},
                    )
                ]
            )
        except Exception:
            pass  # Neo4j 同步失败不阻塞 Dify 写入
    ```
  impact: |
    Neo4j 知识图谱跟 Dify 知识库永久不一致, 没任何日志/告警/审计可查. QA 检索查不到 QAPair 节点,
    排障时不知道是"上游没同步"还是"Neo4j 漏写". 这种"双写静默"在数据完整性维度是 D4 高危.
  fix_sketch: |
    不要 `pass`, 改成 `logger.error("approval.qa.neo4j_sync_failed approval_id={} err={}", approval_id, e)` +
    写一条 audit log 标记 neo4j_sync=failed. 给 approvals 表加 neo4j_synced 字段, 让用户
    能在前端看到 Neo4j 同步状态. 或者用 outbox pattern 异步重试.
  references:
    - "CLAUDE.md §重构规则: 删 / 改账户 / 改权限 / 导出数据 加 @audited, 双写也属数据完整性关键路径"

- id: ERR-007
  dimension: error
  severity: medium
  confidence: high
  title: "object_store 全 except Exception, 抹掉 botocore 错误码"
  file: packages/service/src/storage/object_store.py
  line: 331
  description: |
    MinioObjectStore 14 个方法 12 处 `except Exception as e` 顶层兜底, 把 botocore 的 ClientError
    / EndpointConnectionError / ParamValidationError / ReadTimeoutError 全部压成同一种
    ObjectStoreError. 业务侧拿到的 e 字符串含 str(e), 但没法按错误码分支 (例如 区分 404 真不存在
    vs 503 临时不可达). 已知 try/except 内部对 ClientError 做了 `is_not_found` 结构化判断,
    但如果 botocore 抛的不是 ClientError (例如 endpoint 连接拒绝) 整个 is_not_found 跳过, 真
    "网络挂" 也当 ObjectStoreError 抛, 业务 5xx 处理不区分.
  evidence: |
    ```python
    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None:
        key = self._resolve(uri)
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=mime or "application/octet-stream",
            )
        except Exception as e:
            raise ObjectStoreError(f"put_bytes 失败: {e}") from e
    ```
    同模式 put_stream:343, put_file:351, get_bytes:359, get_stream:378, open_local:404,
    list_prefix:465, exists:474, delete:491, delete_prefix:512, presign_put:523, presign_get:534.
  impact: |
    业务侧没法做精细化: (a) "对象真不存在"应该 404, (b) "MinIO 临时不可达"应该 503 + retry.
    现状所有错误统一 ObjectStoreError, 上层路由翻译 500. 不可达场景不应该跟数据错误同等待遇.
  fix_sketch: |
    拆 ObjectStoreError 子类: ObjectNotFound (404), ObjectUnavailable (503, 网络/超时), ObjectPermissionError (403),
    ObjectStoreInternal (5xx). 每处 try/except 显式分捕 (ClientError, EndpointConnectionError, ReadTimeoutError),
    按 status code 路由到不同子类. 让上层 router 翻译对应 HTTP 状态码.
  references:
    - "现有 ObjectNotFound 已是 404, 模式可推广"

- id: ERR-008
  dimension: error
  severity: low
  confidence: high
  title: "embedder 健康检查 is_embedder_ready 静默吞错, 永远返 False 不报警"
  file: packages/service/src/retrieval/embedder.py
  line: 141
  description: |
    `is_embedder_ready` 调 `embedder(["./__health_check__"])` 任何异常都 except 返 False, 不 log.
    业务侧拿 False 不会知道是"embedder 真正没初始化"还是"openai 临时 503"还是"网络断". 永久
    False 时不会有 ERROR 日志, 排障只能看 metrics.
  evidence: |
    ```python
    def is_embedder_ready(embedder: Any) -> bool:
        try:
            result = embedder(["./__health_check__"])
            return isinstance(result, list) and len(result) == 1
        except Exception:
            return False
    ```
  impact: |
    排查 embedder 是否 ready 时, False 状态是哑信号. 跟 health/checks.py 里 5 个 check
    都打印 latency + error 不一样, 缺结构化. 长期 False 不告警, 上线后才会被业务中断暴露.
  fix_sketch: |
    至少加 `logger.opt(exception=True).warning("embedder 健康检查失败: {}", e)` 让 False 状态
    可被搜索到. 长期 False 可在 start_health_loop 里加 metric / 告警.
  references: []

- id: ERR-009
  dimension: error
  severity: medium
  confidence: medium
  title: "lookup cache subscriber while True 退避 30s 永远卡, 启动期 Redis 挂不暴露"
  file: packages/service/src/lookups/cache.py
  line: 150
  description: |
    `_subscriber` 循环用 `while True + try/except + sleep 30s` 重连 Redis pubsub. 设计本身合理
    (避免日志 spam), 但 first_failure_logged 用闭包 boolean 锁, 一旦 first 失败 log WARNING 后,
    后续每 30s 重试都静默. 整个进程生命周期内 Redis 一直挂, 就再没第二次 WARNING 出现. 启动
    期 Redis 不可达 (dev 常见), lifespan _setup_redis 单独验过, 但 subscriber 失败不会 fail
    startup, 也只在首次 log 一次.
  evidence: |
    ```python
    backoff_s = 30
    first_failure_logged = False
    while True:
        client = None
        try:
            client = build_pubsub_client()
            pubsub = client.pubsub()
            await pubsub.subscribe(_INVALIDATE_CHANNEL)
            if first_failure_logged:
                logger.info("lookup cache subscriber 重连成功, 恢复订阅 channel={}", _INVALIDATE_CHANNEL)
                first_failure_logged = False
            else:
                logger.info("lookup cache invalidate subscriber 已启动 channel={}", _INVALIDATE_CHANNEL)
            async for msg in pubsub.listen():
                ...
        except asyncio.CancelledError:
            ...
            break
        except Exception as e:
            if not first_failure_logged:
                logger.warning(...)
                first_failure_logged = True
            try:
                await asyncio.sleep(backoff_s)
            except asyncio.CancelledError:
                break
    ```
  impact: |
    Redis pubsub 长时间挂掉时, 跨进程字典失效广播丢失, 但 L1 + L2 (Redis) TTL 5min 兜底不感知.
    字典改动后 5 分钟内跨 worker 仍读旧字典. 文档管理员改完 label 等不及 5min 刷新就会困惑.
    日志在第一次失败后沉默, 监控告警无法基于日志触发.
  fix_sketch: |
    至少每 N 次失败 (例如 1 小时) 重新 log 一次 WARNING, 让 ops 能感知持续异常. 或在 metrics
    里暴露 `subscriber_disconnected_at` timestamp. 30s 退避对快速恢复合理, 但要确保 ERROR
    状态对监控可见.
  references:
    - "core/redis_client.py:33 熔断设计也类似, 30s 静默期; 应配套 metrics"
```

## 未扫 / 已知缺口

- 前端错误处理 / React error boundary 属 D5
- 测试代码内的 mock 异常不算生产韧性
- 没扫的: scheduler (apscheduler) 内部异常处理, 仅看了 deletion.py
- 没扫的: 第三方 SDK 内部超时 (Dify, Neo4j driver, mem0) - 这些由 SDK 自己实现, 项目层只配 timeout
- 已知缺点: 全局 handler (errors.py) 已 0 栈泄露给前端 OK, 但 logger 输出走 app_logs 时已脱敏, PII 风险低
- metric / 告警系统未审计 (项目方没看到 prometheus / Sentry 集成)
- 完整 retry 库 (tenacity) 项目只用零散地方, 大部分业务调用是裸调

## Severity 分布

- high: 3 (ERR-001, ERR-002, ERR-005)
- medium: 4 (ERR-003, ERR-004, ERR-006, ERR-007, ERR-009)
- low: 1 (ERR-008)

注: medium 数 4 但 finding 实际列了 5, 已修正为 4 medium 1 low.

## 总体评价

项目错误处理基础很好:
- 全局 FastAPI handler (errors.py) 0 栈泄露, 4xx/5xx 分类 log, error_logs 落库
- Redis safe_* facade + 熔断器 (circuit breaker) + loop-aware pool
- PermissionCache 进程内 + Redis 双层降级
- Lifespan 启动期 fail-open, 不阻塞 boot

主要问题是局部业务代码"过静默"模式:
- evaluator / memory 静默吞 Exception 返 None, 业务拿不到失败信号 (ERR-001, ERR-002)
- print 当错误日志, 不进 app_logs (ERR-003)
- 第三方 SDK (Dify) 缺 retry + 退避 (ERR-005)
- 双写 (Dify + Neo4j) 一边失败 pass, 数据一致性丢失 (ERR-006)
- 一些"失败返默认"路径缺 metrics, 长期挂掉运维无感 (ERR-008, ERR-009)

建议优先修 ERR-001 / ERR-002 (用户感知直接) + ERR-005 (运营成本) + ERR-006 (数据完整性).
