# Mineru → MinIO 持久化集成 (2026-07-02)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-07-02
**Status:** 待批准
**Scope:** 让 mineru 跑出来的 md 自动落独立 MinIO bucket `rag-mineru`, 业务侧 (前端 + backend) 能查询 md URL / 重新下载.
**Out of scope:** Mineru input 走 MinIO 拉取 (现 `process_uri()` 已经把 inputs 从 MinIO 借到本地, 不需要二次下载). Mineru 镜像 / docker-compose 编排 (上周已落, 见 `docker/mineru-docker-compose.yml`). Mineru 长驻 HTTP 服务模式 (跟当前 `docker.from_env()` 临时容器模式并存, 不切换).

## Context

### 现状

**mineru 在项目里有 2 个独立使用模式**:

1. **CLI 临时容器模式** (2026-06-03 spec 引入, 当前在用): `MineruConverter._run_mineru()` 用 `docker.from_env()` + `client.containers.run("mineru:latest", "mineru -p /app/input -o /app/output -b pipeline", ...)` 每个 PDF 批跑一次新容器. 输入是宿主机 `tempfile.TemporaryDirectory` 隔离目录, 输出是宿主机调用方传的 `output_dir` (通常是 `settings.paths.output_dir`).
2. **HTTP 长驻服务模式** (本周刚加, 待真用): `docker/mineru-docker-compose.yml` 起 4 个 profile (openai-server/api/router/gradio), 端口 30000/8000(对外 18000)/8002/7860. **当前 backend 代码不调用这些服务** —— 它们是给运维/手玩/未来集成准备的.

**MinIO 状况**:

- `docker/rag-docker-compose.yml` 的 `minio` 服务已经在跑 (`localhost:9000`)
- backend `OBJECT_STORE_BACKEND` env 切 `local` (默认, 走 `LocalFSObjectStore`, root 默认 `./ingest_uploads`) 或 `minio` (走 `MinioObjectStore`, 端点默认 `http://localhost:9000`)
- 当前 backend 用过 MinIO 的代码点: `ingest/api.py` upload presign (s3://rag-ingest/inputs/), `chat_share/router.py` chat 截图 (s3://rag-ingest/chat/), `eval/router.py` dataset.csv (s3://rag-ingest/eval/), `product_decoders/output_api.py` RAG outputs (s3://rag-ingest/outputs/), `auth/account_settings_service.py` 头像 (rag-avatars bucket)
- **没人在用 mineru 转换产物存 MinIO** —— 现在的 md 跟 mineru 跑完就放调用方传的 `output_dir` 里, 即后端的 `settings.paths.output_dir`

**`process_uri()` (pipeline.py:59)**: 2026-06-16 已经实现 "把 inputs 从 MinIO 借到本地 → 跑 `process_files` → 把 outputs 回传 MinIO" 的 URI 模式入口. 但是**只搬了 input 借来借去**, 没特殊处理 mineru 这条线 (它跟 kreuzberg 一样是 subprocess 调用 + 写本地磁盘).

### 用户决策 (2026-07-02)

1. **新增独立 bucket `rag-mineru`** —— 跟 `rag-ingest` / `rag-avatars` 平级, 业务唯一目的是 mineru 转换产物 (md + 中间文件)
2. **bucket 初始化**: 项目自带 init 脚本, dev 起 `minio` 自动 `mc mb` 建桶 + 配匿名读 (因为前端要直读)
3. **集成方式**: 不改 `MineruConverter._run_mineru()` 的 docker 调用方式, 只改"产物上传 MinIO"这一步在 pipeline 层做. 这条路径跟现有 `process_uri()` outputs 回传模式一致, 不增加新架构.
4. **前端能否查**: 仅 backend 暴露 1 个 `GET /api/mineru/converted/{pdf_stem}` 端点, 返 presigned GET URL. 前端按需集成 (本期不做前端改动, 留 v2 spec).

### 根问题 (用户业务视角)

跑完一轮 PDF 解析后, 用户的 md 文件散落在 backend host 的 `data/outputs/<pdf_stem>/auto/<pdf_stem>.md` —— 几点差:

1. **不进 MinIO**, 跟其它产物 (chat 截图, RAG outputs, eval datasets) 不一致, 没有统一的对象存储 bucket 视图
2. **没有访问控制**, 任何人能 `cat` 主机文件
3. **没有共享 URL** —— 调 `chat_share` 给前端链接只能截图, 不能传 md 内容
4. **清理依赖手动**, 没分用户 / 任务 / 时间, 旧 md 没机制自动清

## 关键设计

### 1. 新增独立 `rag-mineru` bucket (跟 `rag-ingest` / `rag-avatars` 并列)

**为什么独立 bucket, 不复用 `rag-ingest`**:

| 维度 | `rag-ingest` | `rag-mineru` (新) |
|---|---|---|
| 用途 | 输入 PDF + 早期输出混存 | 只放 mineru 解析产物 |
| 桶策略 | 私读 (backend 内部) | **公开读** (前端要直读 md) |
| 保留期 | 任务级, 用户触发清 | md 永久保留 (业务要求) |
| presign | 写 signed | 写 signed + 读 **unsigned 永久公开** |

> ⚠️ 重要决策点: 公开读 bucket = 任何拿到 md URL 的人都能访问 md 内容 (虽然没有列表, 但有 URL 即可). 业务上评估后认为可接受 —— md 里无非是结构化文本, 不含 PII / token / 私有文件. **如果未来需保密, 切 presigned GET 即可**, 设计上不锁死 (URI 跟 backend 解耦).

**桶结构**:

```
s3://rag-mineru/
└── converted/
    ├── 2026/07/02/                  # date partition, 按任务完成日期 (UTC)
    │   ├── task_abc123/              # task_id (ingest task UUID)
    │   │   └── <pdf_stem>/
    │   │       └── auto/
    │   │           ├── <pdf_stem>.md              # 主产物
    │   │           ├── <pdf_stem>_content_list.json  # mineru 中间产物
    │   │           ├── <pdf_stem>.pdf              # (如果 exists, mineru 偶尔会复制)
    │   │           └── images/                    # 图目录, 平铺
    │   └── task_def456/
    └── 2026/07/03/
```

**理由**:
- `converted/` 顶层前缀明确标"已转换产物", 未来能加 `raw/` / `failed/` 等子前缀
- `YYYY/MM/DD/` 时间分区让运维能按时间清 + 列 prefix 高效 (注意: mineru 跑产物是写宿主机的本地磁盘 tempdir, 时间戳是转换完成时刻)
- `task_<id>/` 挂任务, 让 1 个 IngestTask 可以关联多个 PDF 转换产物
- `<pdf_stem>/auto/` 跟 mineru 自有输出结构对齐 (`<out>/<pdf_stem>/<method>/<pdf_stem>.md`), 不动 mineru 解析路径 + 后端 `resolve_md_path()` 仍然工作

**桶匿名读策略** (`mc anonymous set download rag-mineru/converted`): 前端能拼 `<endpoint>/<bucket>/converted/2026/07/02/task_xxx/foo/auto/foo.md` 直接 GET, 不需要 token. bucket **写**还是需要 key+secret.

### 2. 业务集成点: 改 pipeline 层, 不改 converter 层

**关键不变性**: `MineruConverter` 仍然吃本地路径. 它不感知 MinIO —— 跟 `KreuzbergConverter` / `EzdxfConverter` 同等待遇.

**改动位置**: `pipeline.py::process_uri()` 第 87-92 行已经在做"outputs 回传 MinIO", 但是用调用方传的 `output_prefix` (即 `s3://rag-ingest/inputs/<task_id>/output/`).

**新方案**: 在 `process_uri()` 调用 `process_files()` 之后, **额外做一轮 mineru 后处理** —— 把所有 `*.md` 和 `<pdf_stem>/auto/` 子目录批量搬到独立 `rag-mineru/converted/<date>/<task_id>/` bucket, 用 `minio upload dir` 在 backend 里走 boto3 (因为我们不调 `mc`, 调业务代码统一 ABC).

**为什么不在 `_run_mineru` 直接上传**: mineru CLI 跑完立刻 return, 不会触发 backend 业务上传. **必须**在 pipeline 层 (即 `convert_batch` return 之后) 做事后处理.

**为什么不在 `MineruConverter.convert_batch` 内部做事后上传**: converter 接口是 `convert_batch(paths_in_group, str(output_path)) -> dict[str, str]` (注: 当前签名是 dict, 不是 URI). converter 应保持纯粹, 不引入对象存储依赖 (其它 converter 都没 import 对象存储).

### 3. bucket 自举: 加 init 脚本

**问题**: MinIO 新建 bucket 需要调 mc / boto3 / admin API, 第一次起栈时桶不存在会被 mput 报 NoSuchBucket.

**方案**: 在 `docker/rag-docker-compose.yml` 的 `minio` 服务加 1 个 `mc` init 容器 (用 `minio/mc` 镜像) 跑 `mc mb && mc anonymous set download`, 通过 `depends_on` 等 minio healthy. **不要**在 backend Python 里 init 桶 —— 那是运维职责, 业务代码不应耦合部署细节.

**配置**: 给 `minio` 加 `MINIO_BROWSER_REDIRECT_URL` (前端 console 用) 不在本期范围.

### 4. backend 配置

**新 env**:

```bash
# docker/.env
MINERU_OUTPUT_BUCKET=rag-mineru
MINERU_OUTPUT_PREFIX=converted   # 一级前缀, bucket 下编址用
# 不需要新 endpoint/region/secret, 复用 OBJECT_STORE_S3_* 5 env
```

**`.env.local`** (跟当前 `OBJECT_STORE_S3_BUCKET=rag-ingest` 并列):

```bash
MINERU_OUTPUT_BUCKET=rag-mineru
MINERU_OUTPUT_PREFIX=converted
```

**settings.py 加** (`packages/service/src/config/settings.py:174` 旁边):

```python
mineru_output_bucket: str = field(
    default_factory=lambda: os.getenv("MINERU_OUTPUT_BUCKET", "rag-mineru"),
)
mineru_output_prefix: str = field(
    default_factory=lambda: os.getenv("MINERU_OUTPUT_PREFIX", "converted"),
)
```

**不**新增 ObjectStore 单例 (避免单例复杂度翻倍), 而是在 pipeline 层**显式构造第二个 MinioObjectStore** (复用 boto3 client, bucket 不同). 抽取小函数 `get_mineru_store()` 跟现有 `get_object_store()` 同模式.

### 5. 新增 1 个端点

**`GET /api/mineru/converted/{pdf_stem}`** (新 router 文件 `packages/service/src/mineru/router.py`):

- 入参: `pdf_stem` (path param), 可选 `?date=YYYY-MM-DD` (默认今天)
- 出参: `{ pdf_stem, md_uri, md_url }` 或 `{ pdf_stem, items: [{date, task_id, md_uri, md_url, size}] }`
- 实际: 给 `pdf_stem` 返最近的 (按 LastModified desc) 转换记录 (md URL + size + mime)
- 如果多版本, 返列表; 单版本返对象 (Pydantic 自动判)
- 鉴权: `require_page("output")` (跟现有 ingest 端点一致; 后续接入用户态再加 `Depends(current_user)`)

**简化决策**: 本期只返 1 个对象 (最近 1 个), 多版本列表留 v2 spec. 理由: 当前 `IngestTask` 跟 PDF 是 1:1 (上传 1 个 task 1 个 PDF), 没有"同一 PDF 跑多轮"业务流.

### 6. 测试

| 测试模式 | 数量 | 范围 |
|---|---|---|
| 模式 1 (mock) | 11+ | 全 unit test: `get_mineru_store()` 工厂 + `process_uri()` 后处理分流 + 新 router 端点 + URI 拼装逻辑 + 桶策略 helper (1 函数 1-3 测) |
| 模式 4 (E2E) | 2 | (后置手测) 起 minio + mineru container, 跑端到端 1 个 PDF 验证 md 真的落新 bucket + GET endpoint 返 presign URL |

**不写**: 模式 2 / 3 (业务侧 IO 走 ABC 抽象, mock 已覆盖).

## 失败链分析 (5 类)

1. **桶不存在**: `mc mb` 在 init 阶段创建, 业务侧拿 404 报错 → 应 attempt `store.exists(bucket)` fallback to create. **本期 reject**: 依赖运维 init. 文档里写明"必须先跑 `docker compose up minio` + 桶 init"
2. **`store.put_bytes` 失败 (网络/磁盘满)**: pipeline 后处理 catch + log + 标 "上传失败" 不阻塞其它文件上传. **当前 spec 设计**: 1 个失败不应阻塞整批. `process_uri()` 后处理改用 try/except per-file
3. **`/api/mineru/converted/{stem}` 多次调用**: backend 用 `MinioObjectStore.list_prefix` 是 idempotent, 多次返同一结果. **安全** ← 不涉及副作用
4. **race condition**: 多个 ingest task 并行上传, 同 task_id 写同 prefix (理论 race) —— **本 spec 不考虑**, IngestTask ID 唯一, 同 task 不重复上传 (因为每个 task 一次性跑 `process_uri()`)
5. **公开读泄漏**: bucket 配 anonymous download = URL 知道就有. **接受业务风险** —— 设计上不锁 (URI 字符串仍是 backend 唯一可信源, 公开读只是优化)

## 改造产物 (代码)

### A. `docker/rag-docker-compose.yml` — 新增 `minio-init` 服务

```yaml
  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin};
      mc mb --ignore-existing local/${MINERU_OUTPUT_BUCKET:-rag-mineru};
      mc anonymous set download local/${MINERU_OUTPUT_BUCKET:-rag-mineru}/converted;
      echo 'minio-init done';
      "
    restart: "no"   # 一次性跑完即退
    networks:
      - app-network
```

> 跟现有 minio 服务并列, 不改 minio 服务本身. 等 minio healthy 起 1 次性 init container, 自动 rm.

### B. `docker/.env.example` — 新增

```bash
# Mineru 解析产物 bucket (独立于 rag-ingest, 用于长期保存 md + 中间文件 + 公开读)
MINERU_OUTPUT_BUCKET=rag-mineru
MINERU_OUTPUT_PREFIX=converted
```

### C. `packages/service/src/config/settings.py` — 加 2 字段

见 §4.

### D. `packages/service/src/storage/object_store.py` — 加 `get_mineru_store()`

(不动现有 `get_object_store()`, 新增 1 函数) 复用 `MinioObjectStore` 但 bucket 不同, 用 `settings.mineru_output_bucket`.

### E. `packages/service/src/storage/mineru_bucket.py` (新) — 桶策略 helper

- `def build_converted_uri(task_id: str, pdf_stem: str, ext: str = ".md", date: datetime | None = None) -> str`
- `def build_converted_url(endpoint: str, task_id: str, pdf_stem: str, ext: str = ".md") -> str`  (公开读的 URL, 不签)
- `def list_converted_for_pdf(bucket, pdf_stem: str) -> list[ObjectMeta]`
- 拼 URI / URL 唯一地方, 1 处定义, 1 处测试

### F. `packages/service/src/ingest/pipeline.py` — `process_uri()` 加后处理

```python
# 现有逻辑: outputs 回传 output_prefix
# 加: 上传完成的 .md + 子目录到 rag-mineru bucket
try:
    mineru_store = get_mineru_store()
    task_id = ...  # 从入参或进程上下文拿 (注: 当前 process_uri 不接 task_id, 见 §G)
    for p in Path(local_output).rglob("*"):
        if p.suffix == ".md" or p.is_relative_to(...):
            uri = build_converted_uri(task_id=task_id, pdf_stem=p.stem)
            mineru_store.put_file(uri, str(p))
except Exception as e:
    logger.opt(exception=True).warning("mineru 后处理上传失败 (PDF 已写入 {}): {}", local_output, e)
```

### G. `_run_ingest()` 拿 task.id (实际调用点在 api.py:514)

当前 `process_uri(input_prefix, output_prefix, store)` 在 [`packages/service/src/ingest/api.py:514-518`](../../packages/service/src/ingest/api.py#L514-L518) 调用, 是 `_run_ingest(task_id, work_dir)` 后台任务.

**真实改动**: `process_uri` 加可选 `task_id: str | None = None` (向后兼容, 旧 CLI 调用 None 即跳过后处理). `_run_ingest()` 改 `process_uri(..., task_id=task_id, ...)`. 这条改动**只 1 行**. IngestTask.id 已经在函数顶部 (`api.py:505` `_load(task_id)`), 直接复用.

### H. `packages/service/src/mineru/router.py` (新) + `mineru/schemas.py` (新)

```python
# router.py
mineru_router = APIRouter(prefix="/api/mineru", tags=["mineru"])

@mineru_router.get("/converted/{pdf_stem}", response_model=ConvertedResponse)
async def get_converted(pdf_stem: str, current=Depends(require_page("output"))):
    """返最近 1 个 md 的 URL (公开读, 永久)"""
    store = get_mineru_store()
    matches = list_converted_for_pdf(store, pdf_stem)
    if not matches:
        raise HTTPException(404, detail=f"未找到 {pdf_stem} 转换产物")
    latest = max(matches, key=lambda m: m.last_modified or 0)
    return ConvertedResponse(pdf_stem=pdf_stem, md_uri=latest.uri, md_url=build_public_url(...))
```

### I. `packages/service/src/app.py` — 加 `mineru_router` 注册

跟现有 `ingest_router` 注册模式一致, 1 行.

## 测试清单 (11+ 模式 1 单测 + 2 模式 4 E2E)

### 模式 1 (mock, 自动跑)

| Test | 位置 |
|---|---|
| `test_get_mineru_store_returns_minio_with_different_bucket` | `tests/storage/test_object_store.py` |
| `test_build_converted_uri_format` (含日期分区) | `tests/storage/test_mineru_bucket.py` |
| `test_build_converted_url_no_presign_public` | 同上 |
| `test_list_converted_for_pdf_returns_sorted` | 同上 |
| `test_process_uri_after_mineru_step_uploads_md` (mock mineru_store.put_file) | `tests/ingest/test_pipeline.py` |
| `test_process_uri_after_mineru_step_skips_when_no_task_id` | 同上 |
| `test_process_uri_after_mineru_step_swallows_upload_error` (1 PDF 失败不阻塞其它) | 同上 |
| `test_mineru_get_converted_returns_latest_match` | `tests/mineru/test_router.py` |
| `test_mineru_get_converted_404_when_no_match` | 同上 |
| `test_mineru_get_converted_uses_public_url_not_presigned` | 同上 |
| `test_settings_mineru_output_bucket_defaults_to_rag_mineru` | `tests/config/test_settings.py` |

### 模式 4 (E2E, 手测)

| Test | 位置 |
|---|---|
| `test_mineru_end_to_end_pipeline_writes_to_rag_mineru_bucket` (真 mineru 容器 + 真 minio, `RUN_SLOW_TESTS=1`) | `tests/integration/test_mineru_e2e.py` |
| `test_minio_init_container_creates_rag_mineru_bucket` (真跑 `minio-init`, 验桶存在 + 匿名读策略) | `tests/integration/test_minio_init.py` |

## 关键依赖 / 现有代码复用

| 复用 | 路径 |
|---|---|
| `MinioObjectStore` | `packages/service/src/storage/object_store.py:267` (直接构造, 不单例) |
| `parse_uri` / `build_uri` | `object_store.py:61` `object_store.py:82` (新 helper 复用) |
| `require_page("output")` 鉴权 | 跟 `ingest/api.py:302` 一致 |
| `tempfile.TemporaryDirectory` 隔离 (input 借用) | `pipeline.py:72` (既有, 不动) |
| `IngestTask.id` 作为 task_id 来源 | `ingest/api.py:319` (`_new_task_id()`) |
| `get_converter()` 单例 | `converters/__init__.py` (既有) |
| docker-py SDK + DeviceRequest GPU | `mineru.py:90-103` (不动) |
| mineru CLI batch + 磁盘真相源 + 单文件重试 | `mineru.py:84-195` (完全不动) |
| `pipeline.process_uri` outputs 回传模板 | `pipeline.py:87-92` (复制成 mineru 上传模板) |

## 不在范围 (留给后续 spec)

- ❌ **前端组件**: 用新端点展示 md 列表 / 按钮下载 ← 留 frontend v2 spec
- ❌ **多版本 PDF 反复转换**: 同 PDF 跑多轮存多版本 ← v2 spec
- ❌ **用户级访问隔离**: 当前匿名读 = 1 URL 即可访问, 后端只验 presign 写不验 presign 读 ← v2 spec (业务再调研)
- ❌ **桶生命周期 / 自动清理**: 当前 md 永久保留 ← v2 spec
- ❌ **走 HTTP 长驻 mineru-api** (替代 docker run 临时容器): docker compose 已就绪, 但改 backend convert 调用模式是大重构 ← 留 v3 spec
- ❌ **input 直接从 MinIO 流式给 mineru**: 现 `process_uri()` 先借本地再 docker run, 已经走 MinIO ← **现状 OK 不改**

## 实施步骤 (TDD-task list)

> Use **superpowers:test-driven-development** skill. 红 → 绿 → 重构, 一文件一 task, 不 batch.

- [ ] **T1** 加 `MINERU_OUTPUT_BUCKET` + `MINERU_OUTPUT_PREFIX` 到 `packages/service/src/config/settings.py`
   test_settings 跑绿
- [ ] **T2** 建 `tests/config/test_mineru_settings.py` 1 单测, 测默认 `rag-mineru` + `converted`
- [ ] **T3** 建 `packages/service/src/storage/mineru_bucket.py` 3 函数
   test_mineru_bucket 跑绿 (3-4 单测)
- [ ] **T4** `object_store.py` 加 `get_mineru_store()` 工厂
   test_object_store 跑绿 (1 单测, mock boto3)
- [ ] **T5** `pipeline.py::process_uri()` 加可选参数 `task_id: str | None = None`, 跑 `process_uri(task_id=xxx)` 时加 mineru 后处理上传
   test_pipeline 跑绿 (3 单测, 含失败容错)
- [ ] **T6** `ingest/api.py` final 阶段调 `process_uri` 传 `task.id` (1 行改动)
- [ ] **T7** 建 `packages/service/src/mineru/router.py` + `schemas.py`
   test_mineru_router 跑绿 (3 单测, 含 404 + latest)
- [ ] **T8** `app.py` 注册 `mineru_router` (1 行 + import)
- [ ] **T9** `docker/rag-docker-compose.yml` 加 `minio-init` 服务
- [ ] **T10** `docker/.env.example` 加 2 env
- [ ] **T11** docker compose up minio + minio-init, 手验: `mc ls local/rag-mineru` 应出现, `mc anonymous get local/rag-mineru/converted` 应 OK
- [ ] **T12** 端到端手测: 后端跑 ingest task → 跑 PDF → `mc ls -r local/rag-mineru/converted/` 应出现新 md
- [ ] **T13** 跑全量 `uv run pytest` + `uv run pyright` + `uv run ruff check`, 必须 0 新 fail
- [ ] **T14** commit (按 `feedback-commit-in-batches-for-large-changes` 分 3 commit: T1-T4 infra / T5-T8 业务 / T9-T12 部署 + 验证)

## 关键风险 + 缓解

| 风险 | 缓解 |
|---|---|
| **公开读 bucket 设计**被业务否决 → 改 presigned GET | 已记录 v2 spec, `build_converted_url` 函数化, 1 行改返 `store.presign_get(uri, ttl_seconds=...)` |
| **minio-init 容器 race**: minio 未真正 ready 但 healthcheck 已绿 | init 容器本身有 5s sleep + retry (mc 自带), 测过 skip; 真实 fault 可改 depends_on condition: service_healthy 已用 |
| **`process_uri` 拿不到 task_id**: 当前签名无 task_id 入参 | T5 加参数, T6 上游传. 旧调用方 (历史 CLI / 测试) 传 None = 跳过后处理, 不破 |
| **GPU 跑 mineru 失败**: 当前 spec 不重提 cli 调用, 跟"docker run 临时容器" 不变, 失败链已存在 (RunError) 不变 |
| **桶越来越大没清理**: 业务数据, 不属于本期. v2 spec 处理 (lifecycle policy) |

## 兼容 + 回滚

- ✅ 旧 `process_uri` 调用方 (None task_id) 行为不变
- ✅ `MineruConverter` / docker CLI 调用方式 0 改动
- ✅ 新端点只 GET 不改写, 加 1 删 0
- ❌ 改 `minio` 服务的 compose? **不改**, 加并列 `minio-init`
- 回滚: 删 `minio-init` + revert pipeline 后处理代码 + 删 mineru router 注册
