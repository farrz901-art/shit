# P1 - 错误处理与韧性 spec 草稿 (2026-06-24)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D3 Error handling & Resilience
> 关联 checklist: [docs/audit/2026-06-24-findings.md](../../../../docs/audit/2026-06-24-findings.md)

## 范围

### High (3)
- ERR-001 — evaluator 静默吞错返 None
- ERR-002 — memory search/list 异常吞
- ERR-005 — Dify 集成无 retry / 超时

### Medium (4)
- ERR-003 — CAD 转换器 print 当日志
- ERR-004 — ingest task 失败丢 stacktrace
- ERR-006 — approval executor Neo4j 失败 pass
- ERR-007 — object_store 全 except 抹错误码
- ERR-009 — lookup cache subscriber 30s 静默

### Low (1)
- ERR-008 — embedder_ready 静默期

合计 9 条 finding.

## 修复策略

### Phase 1 (1 周) — 业务失败信号

1. **ERR-001**: `eval/llama_eval.py:109` 把 `except Exception: return None` 改成 raise, 上层 service 决定 fallback 策略 (跟 ERR-002 统一).
2. **ERR-002**: memory service 异常分两类: 业务可恢复 (返空列表) 跟 系统故障 (raise), 加 `ErrorKind` 枚举.
3. **ERR-005**: Dify / dify_datasets / chat_share 三处 httpx 调用加 `tenacity` retry (指数退避, max 3 次) + 显式 `timeout=10.0`.

### Phase 2 (2 周) — 日志统一 + 错误保留

4. **ERR-003**: `ingest/converters/cad.py` + `pipeline.py` 47 处 print() 全替换 `logger.warning(...)` / `logger.opt(exception=True).error(...)`.
5. **ERR-004**: ingest task 失败时 `t.error` 存 `repr(traceback.format_exc())` 而非 `str(e)`.
6. **ERR-006**: approval executor Neo4j 失败时把任务状态置为 `retry` 而非静默, 加 `@audited` 装饰器 (跟 ARCH-006 一起).
7. **ERR-007**: object_store `except Exception` 改成只 catch `botocore.exceptions.ClientError` + `requests.RequestException`, 其他 re-raise.
8. **ERR-009**: subscriber 30s 静默期改成 5min + 持续 3 次失败后发 WARNING 日志.
9. **ERR-008**: embedder ready 检查加 circuit breaker, 持续失败时返 503 而非永久 False.

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- P0/P2/P3/P4 其他维度 finding
- LLM max_tokens 预算 (跟 D6 ARCH 一起)

## 验收标准

- 9 条 finding 全部 verified=true
- 全局 FastAPI exception handler 0 栈泄露
- 第三方 SDK 调用 100% 有 timeout + retry
- print() 在后端 0 命中 (用 ruff 自定义规则检测)
- pytest 覆盖 `with pytest.raises(...)` 在 9 个对应 service
