# 后端测试覆盖率 74.7% → 80% 设计方案

## 现状

| 维度 | 当前值 | 目标 |
|------|--------|------|
| Lines | **74.7%** (7304 行) | ≥ 80% |
| Tests | 1094 passed, 38 errors (pre-existing) | 不新增 error |

**缺口：~387 行**（7304 × 5.3%）。

## 选文件原则

1. **优先纯函数 + 低 mock 成本** — 避免需要真 PG/Redis 的集成测试
2. **跳过预知不可测文件** — CAD/OCR 等依赖外部二进制
3. **每批写完才跑覆盖率** — 不中途跑

## 目标文件

### 第 1 批（纯函数 + 低 mock 成本）

| 文件 | 当前覆盖 | 缺失行 | 测试策略 | 预估贡献 |
|------|----------|--------|----------|----------|
| `src/eval/llama_eval.py` | 12.7% | 75 | mock LLM 客户端，测评估执行/结果解析 | ~60 |
| `src/api/routes.py` | 26.1% | 32 | FastAPI TestClient，测路由注册 | ~25 |
| `src/common/document_loader.py` | 46.9% | 22 | mock 文件读取，测文档加载 | ~18 |
| `src/config.py` | 44.1% | 17 | mock os.environ，测配置加载 | ~14 |

**预估贡献：~117 行**

### 第 2 批（中等 mock 成本）

| 文件 | 当前覆盖 | 缺失行 | 测试策略 | 预估贡献 |
|------|----------|--------|----------|----------|
| `src/auth/account_settings_router.py` | 26.2% | 88 | mock service 层，TestClient 测端点 | ~70 |
| `src/ingest/store.py` | 34.8% | 22 | mock object_store，测 CRUD | ~18 |
| `src/core/dify_query_cache.py` | 54.2% | 22 | mock redis，测缓存逻辑 | ~18 |
| `src/core/logging.py` | 69.5% | 23 | mock logger，测格式化 | ~18 |

**预估贡献：~124 行**

### 第 3 批（高 mock 成本，如果需要）

| 文件 | 当前覆盖 | 缺失行 | 测试策略 | 预估贡献 |
|------|----------|--------|----------|----------|
| `src/ingest/api.py` | 54.3% | 127 | mock store + object_store，TestClient | ~80 |
| `src/ingest/pipeline.py` | 66.7% | 74 | mock converter，测转换流程 | ~50 |
| `src/kg/neo4j.py` | 42.4% | 48 | mock neo4j driver，测 Cypher | ~35 |
| `src/lookups/cache.py` | 51.1% | 35 | mock redis，测缓存 | ~28 |

**预估贡献：~193 行**

## 不测文件（明确排除）

| 文件 | 原因 |
|------|------|
| `src/ingest/converters/cad.py` | 依赖 CAD 外部二进制 |
| `src/ingest/converters/kreuzberg.py` | 依赖外部 OCR 服务 |
| `src/ingest/converters/mineru.py` | 依赖外部 API |
| `src/ingest/analyzers/cad.py` | 依赖 CAD 二进制 |
| `src/health/checks.py` | 88%，依赖系统服务 |
| `tests/integration/*` | 需要真 PG/Redis |

## 执行顺序

1. 写第 1 批测试 → `bun run lint` 检查
2. **跑一次覆盖率验证**
3. 如不足 80%，写第 2 批
4. **跑一次覆盖率验证**
5. 如仍不足，写第 3 批
6. **最后一次覆盖率验证**
