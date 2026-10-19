# P1 - 错误处理与韧性 spec 草稿 (2026-06-26)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Error handling (D3)
> 关联 checklist: [docs/audit/2026-06-26-findings.md](../../../../docs/audit/2026-06-26-findings.md)

## 范围

### 已验证 finding
- ERR-004 (high) — Neo4j 客户端无熔断器, 宕机时持续重试

### 未 verify
- ERR-001 (medium) — 3 个 /api/v1 端点返回 str(e) 到 500 响应体
- ERR-002 (medium) — Neo4jStore 驱动无连接超时配置 (默认 30s)
- ERR-005 (medium) — OpenAILLM 的 max_tokens 默认为 None
- ERR-006 (low) — kg/router.py /products 缺降级处理

### Refuted (排除)
- ERR-003 (high) — Neo4j retry (Bolt 协议自带重试, 非 HTTP API)

## 修复策略

### 1. Neo4j 熔断器
- 参考 redis_client.py 的 `_trip_circuit` / `_is_circuit_open` 实现
- 30s 窗口内 > N 次失败 → 熔断打开, 直接返回降级值
- 周期性尝试半开恢复

### 2. 错误响应
- 禁止 `return {"detail": str(e)}` — 改统一错误响应格式
- 全局 `@app.exception_handler(Exception)` 加结构化输出

### 3. Neo4j 超时
- 构造 driver 时加 `connection_timeout=5` 参数
- 避免请求挂起 30s

### 4. LLM token 预算
- OpenAILLM 默认 max_tokens=4096 (非 None)
- 加 max_tokens 上限检查

### 5. kg 降级
- Neo4j 不可达时 kg/router.py 返回降级数据而非 500
- 参考 Redis facade 的 `fail-open` 模式

## 不在本文范围
- ERR-003 (refuted) — 排除
- P0 / P2-P4 其他 finding
