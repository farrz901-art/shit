# Health Page Design (2026-06-11)

## 目标

从 NextJS header 齿轮的 `SettingsDialog` 弹框点「健康」一行, 跳转到 `/[locale]/health` 单页, 通过 Python 后端一个 `/api/health/system` 端点代理 5 类检查:

1. **Python 后端** — 进程在跑 + uptime
2. **Dify** — `/v1/parameters` ping, 算 latency
3. **Neo4j** — `driver.verify_connectivity()`, 算 latency
4. **pgvector** — `SELECT 1`, 算 latency
5. **主机资源** — psutil 采 CPU/内存, pynvml 采 GPU

5 秒轮询, admin-only (走 `x-admin-token`).

## 范围

**做**:
- 后端 `/api/health/system` 端点, 后台 5s task 跑 5 个 check 写进程内 cache
- 前端 `/[locale]/health` 页面, 5 区块单页全量, 5s 轮询
- `SettingsDialog` 加「健康」行
- BFF 透传路由 `web/app/api/health/system/route.ts`
- i18n (zh + en)
- pyproject 加 `psutil` + `pynvml`
- 契约测试更新

**不做** (YAGNI):
- ❌ 历史曲线图 (Chart.js) — 当前 5s 实时值够用
- ❌ 告警 / 邮件 / webhook — 后续真要告警再加
- ❌ 多机/集群监控 — 单机就够
- ❌ 用户可配置轮询间隔 — 5s 写死
- ❌ 暗色主题特殊样式 — 复用现有 `bg-status-*` token

## 架构

```
┌──────────────────────────────────────────────┐
│ 浏览器 /health 页                              │
│   └─ SettingsDialog 「健康」行 → 跳转          │
│   └─ SWR 5s 拉 /api/health/system             │
└──────────────────┬───────────────────────────┘
                   │ x-admin-token (cookie/header)
┌──────────────────▼───────────────────────────┐
│ FastAPI 8000 (main.py → create_app)          │
│   /api/health/system  →  SystemHealthView    │
│     ├─ _check_python: process uptime          │
│     ├─ _check_dify: DifyClient ping           │
│     ├─ _check_neo4j: Neo4jStore ping          │
│     ├─ _check_pgvector: PGVectorStore ping    │
│     └─ _check_system: psutil+pynvml           │
│   后台 5s task 把 5 个结果写 _health_cache     │
│   HTTP handler 直接读 cache (亚毫秒响应)      │
└──────────────────────────────────────────────┘
```

## 后端设计

### 新增文件

```
src/rag/health/
├── __init__.py
├── router.py          # /api/health/system FastAPI router
├── router_test.py     # 单元测试 (TDD)
├── checks.py          # 5 个 _check_* 函数 (纯函数, 易测)
├── checks_test.py     # 单元测试
├── cache.py           # 后台 5s 任务 + 内存缓存 + 锁
└── cache_test.py      # 单元测试
```

### 模块职责

#### `checks.py`

5 个 async 函数, 各自独立, 返回 `CheckResult` dataclass:

```python
@dataclass
class CheckResult:
    status: Literal["ok", "error"]
    latency_ms: float | None = None
    error: str | None = None
    extra: dict = field(default_factory=dict)
```

5 个检查 (统一返 `CheckResult`, latency_ms 是核心, 特有信息走 `extra` 字段):
- `_check_python()` — 读 `process_start_time` (模块级 `time.time()` 在模块加载时记录) 算 uptime. 返 `extra={"uptime_s": N, "version": "0.1.0"}`, `latency_ms=0.0` (本地读, 不算网络)
- `_check_dify()` — 复用 `DifyClient` (从 `src/rag/integrations/dify_client.py` 导入) 调 `/v1/parameters` (Dify 公开的轻量端点, 不消耗 workflow), 算 latency
- `_check_neo4j()` — 调 `Neo4jStore.execute("RETURN 1")` (现有方法, 不引入新依赖, 走 `driver.session().run` 内置连通性验证), 算 latency
- `_check_pgvector()` — 通过 `sqlalchemy` 直接用 `PGVectorConfig.connection_string` 建连接跑 `SELECT 1` (绕开 `llama_index.vector_stores.pgvector` 的复杂初始化, 5s 周期起一次 PGVectorStore 加载太重), 算 latency
- `_check_system()` — `psutil.cpu_percent(interval=0.1)` + `psutil.virtual_memory()` + `pynvml.nvmlDeviceGetUtilizationRates(handle)`. GPU 驱动缺失 (pynvml `NVMLError`) → `extra={"gpu": []}`, 不报错

#### `cache.py`

进程内单例缓存:
- `_health_cache: dict | None = None`
- `_cache_lock: asyncio.Lock` (防并发刷新竞态)
- `start_health_loop()` — `asyncio.create_task` 后台 5s 任务, 调 5 个 check, 写 cache
- `get_cached_health() -> dict` — 读 cache, 启动后 1s 内若没数据返 `{"checked_at": null, "status": "warming_up"}`
- `stop_health_loop()` — 测试用, cancel task

#### `router.py`

FastAPI 端点:
- 鉴权: 必须 `x-admin-token` header (admin-only). 不复用 `_check_token` (那个是 user/admin 都行), 自己写一个 `_require_admin_token` helper: 缺 header 立即 401 `{"detail": "缺少 x-admin-token"}`. 头存在就过 (不强校验 token 值, 跟项目现有 `RAG_DEV_AUTH` 风格一致, dev 模式 admin token 不强校验)
- `GET /api/health/system` 调 `get_cached_health()`, 直接返
- 挂到 `product_decoders/app.py` 的 `create_app()` 里: `app.include_router(health_router, prefix="/api/health")`

### 端点契约

`GET /api/health/system`

**请求**: 需 `x-admin-token` header, 否则 401

**响应 200** (每个子检查都有 `latency_ms` + `error` + `extra`, 主机检查特殊结构):
```json
{
  "checked_at": "2026-06-11T10:30:00.000Z",
  "python":   { "status": "ok", "latency_ms": 0.0,  "error": null, "extra": { "uptime_s": 12345, "version": "0.1.0" } },
  "dify":     { "status": "ok", "latency_ms": 120,  "error": null, "extra": {} },
  "neo4j":    { "status": "ok", "latency_ms": 45,   "error": null, "extra": {} },
  "pgvector": { "status": "error", "latency_ms": null, "error": "ConnectionRefused", "extra": {} },
  "system":   {
    "status": "ok",
    "latency_ms": 5.0,
    "error": null,
    "extra": {
      "cpu_pct": 23.5,
      "mem_pct": 67.2,
      "mem_used_mb": 12000,
      "mem_total_mb": 18000,
      "gpu": [
        { "name": "NVIDIA RTX 4090", "util_pct": 45, "mem_used_mb": 8000, "mem_total_mb": 24000 }
      ]
    }
  }
}
```

**响应 401**: `{"detail": "缺少 x-admin-token"}` (admin token 缺失)

**关键不变式**: 任一子检查失败不影响 HTTP 200, 字段 `status: "error"` + `error: "<msg>"`. 只有 admin token 缺失才 401.

### 启动时机

`main.py` 的 `lifespan` 上下文 (FastAPI 0.93+ 风格) 或 `@app.on_event("startup")` (兼容版), 启动 `start_health_loop()`, shutdown 时 `stop_health_loop()`.

### pyproject.toml 新增依赖

`psutil` + `pynvml` 两条.

## 前端设计

### 新增文件

```
web/app/[locale]/health/
├── page.tsx           # 健康页 (client component, "use client")
└── page.test.tsx      # vitest 单元测试

web/app/api/health/system/
└── route.ts           # BFF 透传端点
```

### BFF 路由

`route.ts`:
- `GET /api/health/system` → 转发到 `http://localhost:8000/api/health/system`
- 头转发: 读 `x-admin-token` cookie / header, 透传给 FastAPI
- 响应直接 JSON 透传, 不做处理
- 错误: FastAPI 401 → BFF 也 401; 503/500 → BFF 502 + 错误信息 (跟 [feedback-bff-must-propagate-502-not-silently-zero](feedback-bff-must-propagate-502-not-silently-zero.md) 一致)

### 页面布局

```
┌─ 「健康状态」h1  (4xl display)         ─┐
│  副标题: 显示最后检查时间               │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │ 🟢 Python 后端                    │  │
│  │   状态: ok   运行时长: 3h 25m     │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ 🟢 Dify                           │  │
│  │   状态: ok   延迟: 120ms         │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ 🔴 Neo4j                          │  │
│  │   状态: error                     │  │
│  │   错误: ConnectionRefused          │  │
│  │   延迟: —                         │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ 🟢 pgvector                       │  │
│  │   状态: ok   延迟: 45ms          │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ 🟢 主机资源                        │  │
│  │   CPU:    23%   ▓▓▓░░░░░░          │  │
│  │   内存:   67%   12 GB / 18 GB     │  │
│  │   GPU 0:  45%   NVIDIA RTX 4090  │  │
│  │          显存: 8 GB / 24 GB       │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

- 状态色: 用现有 `bg-status-success` / `bg-status-error` (跟 HealthDot 一致, 不用 emoji, 改用 Lucide `CheckCircle2` / `XCircle`)
- 进度条: `@/components/ui/progress` (项目 shadcn 已封装)
- 错误折叠: `<details>` 元素, 避免长错误信息撑爆布局
- 5s 轮询: `useApi` (项目自封装 SWR) + `refreshInterval: 5000`
- loading 状态: cache 未就绪时显「数据采集中...」

### SettingsDialog 改动 (一行)

- 在「语言」行下方插入「健康」行
- 行为: 点击跳 `/[locale]/health` (用 `LocalizedLink` 走 i18n 前缀)
- 视觉: 跟其他行对齐, 左侧文字「健康」, 右侧一个 `→` 图标 (Lucide `ChevronRight`)
- 非 admin 也能跳 (跳转本身不需要 admin, BFF 才校验)

### 国际化 (i18n)

`web/messages/zh.json` 新增 (中文作 key):
- "健康"
- "Python 后端"
- "Dify"
- "Neo4j"
- "pgvector"
- "主机资源"
- "状态"
- "延迟"
- "运行时长"
- "CPU"
- "内存"
- "数据采集中..."
- "需要管理员权限"
- "后端服务不可达, 请检查 main.py 是否在 8000 端口运行"

`web/messages/en.json` 加英文翻译.

## 错误处理

| 失败点 | 行为 | UI 反馈 |
|--------|------|---------|
| 缺 `x-admin-token` | HTTP 401 | BFF 返 401, 页面显示「需要管理员权限」+ 返回链接 |
| FastAPI 不可达 | BFF 502 | 显示「后端服务不可达, 请检查 main.py 是否在 8000 端口运行」 |
| Dify 不可达 | 子检查 `status: "error"`, HTTP 仍 200 | 区块显示红 dot + 错误信息, 不影响其他区块 |
| Neo4j 不可达 | 同上 | 同上 |
| pgvector 不可达 | 同上 | 同上 |
| 主机检查异常 | 整个 system 块 `status: "error"` | 区块显示红 dot, 错误信息折叠 |
| GPU 驱动缺失 (pynvml `NVMLError`) | `gpu: []` 数组空, 区块显「无 GPU / 驱动未安装」 | 不报错, 优雅降级 |
| 后台 cache 任务崩 | 下次 5s 重新启动, 中间窗口 `checked_at: null` | UI 显「数据采集中...」 |

## 测试覆盖 (TDD)

### 后端

**`checks_test.py`**:
- `test_check_python_returns_uptime` — mock `time.time` 验证 uptime 计算
- `test_check_dify_ok` — mock DifyClient 调通, 验证 latency
- `test_check_dify_connection_error` — mock 抛 ConnectionError, 验证返 status=error
- `test_check_neo4j_ok` — mock `verify_connectivity` 成功
- `test_check_neo4j_driver_missing` — mock import 失败, 返 error
- `test_check_pgvector_ok` — mock 跑通 SELECT 1
- `test_check_system_returns_cpu_mem_gpu` — mock psutil + pynvml 返数值
- `test_check_system_no_gpu` — mock pynvml 抛 NVMLError, 验证 gpu=[]

**`cache_test.py`**:
- `test_get_cached_health_returns_warming_up_when_empty` — 启动后 0 数据
- `test_cache_set_and_get` — 注入 dict, 读出来
- `test_loop_runs_all_checks` — monkeypatch 5 个 check 函数, 验证被调用

**`router_test.py`**:
- `test_health_endpoint_requires_admin_token` — 无 header → 401 `{"detail": "缺少 x-admin-token"}`
- `test_user_token_alone_is_rejected` — 仅有 `x-user-token` (没 admin) → 401
- `test_health_endpoint_returns_cached_data` — admin header, 注入 cache, 验证 200 + 字段
- `test_health_endpoint_warming_up_response` — cache 为空 → 200 + `checked_at: null`

### 前端

**`page.test.tsx`** (vitest + IntlWrapper):
- `test_renders_all_5_sections` — 5 区块标题都在
- `test_renders_python_uptime_and_status`
- `test_renders_dify_latency_when_ok`
- `test_renders_dify_error_message_when_error`
- `test_renders_system_cpu_mem_gpu` — 验证进度条 + 数值
- `test_renders_warming_up_state` — cache 未就绪时显「数据采集中...」

### 契约测试

`tests/test_api_contract.py` `FRONTEND_EXPECTS` 列表新增 `/api/health/system` 条目 (项目硬规则: 删 BFF route 前必跑, 见 [CLAUDE.md §重构规则](../../CLAUDE.md))

## 实施步骤

1. 后端 `pyproject.toml` 加 `psutil` + `pynvml`
2. 写 `src/rag/health/checks.py` + `checks_test.py` (TDD 红→绿)
3. 写 `src/rag/health/cache.py` + `cache_test.py` (TDD 红→绿)
4. 写 `src/rag/health/router.py` + `router_test.py` (TDD 红→绿)
5. `main.py` `create_app()` 挂 router + lifespan 启停 cache loop
6. 跑全量后端测试
7. BFF `web/app/api/health/system/route.ts`
8. `web/messages/zh.json` + `en.json` 加翻译
9. `web/app/[locale]/health/page.tsx` + `page.test.tsx` (TDD 红→绿)
10. `web/components/settings/settings-dialog.tsx` 加「健康」行
11. `tests/test_api_contract.py` 加 BFF 期望
12. 跑全量测试 + 重启 FastAPI + uv run python main.py 验证

## 风险点

- ⚠️ **pynvml 在没有 NVIDIA 驱动的机器上启动时 `nvmlInit()` 会抛** → 启动时 try/except, 失败就当「无 GPU」处理 (返 `gpu: []`)
- ⚠️ **psutil 第一次 `cpu_percent` 必须 `interval=0.1` 才有值** (Windows 行为)
- ⚠️ **后台 5s task 在测试环境可能跟 TestClient 抢事件循环** → 测试用 `monkeypatch` 注入假数据, 不真起 loop
- ⚠️ **Dify `/v1/parameters` 端点可能需要鉴权** → 复用 `DifyClient` 已有逻辑, 不另写鉴权
- ⚠️ **`pyproject.toml` 加依赖必须 uv** (不用 pip, 见 [feedback-uv-only-no-pip](feedback-uv-only-no-pip.md))
- ⚠️ **后端加新 router 必须重启 uvicorn** (见 [feedback-uvicorn-must-restart-after-route-add](feedback-uvicorn-must-restart-after-route-add.md))

## 参考

- 现有 `/api/knowledge/health` 实现: `web/components/knowledge/HealthDot.tsx` (Dify 健康点)
- 现有 `DifyClient`: `src/rag/integrations/dify_client.py`
- 现有 `Neo4jStore`: `src/rag/kg/neo4j.py`
- 现有 `PGVectorStore`: `src/rag/retrieval/vector_store.py`
- 现有 `_check_token` admin 鉴权: `src/rag/ingest/api.py:171`
- 项目硬规则: [CLAUDE.md](../../CLAUDE.md) (TDD / 不删注释 / 中文注释 / BFF 契约测试)
- i18n 约定: [project-i18n-use-chinese-as-t-key](../../MEMORY.md)
