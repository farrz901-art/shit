# RAG Ingest 接入 MinIO 对象存储 (2026-06-16)

> Status: **DRAFT v1 — 等审批**
> 目标: 把 RAG Ingest 知识库 (PDF / CAD / Office / Archive 上传 → 解析 → 产物查询) 的**本地 FS**
> 改走 MinIO 对象存储, 解决: 多 worker 不共享 / 容器重启丢数据 / 无 presigned URL / 大文件
> backend 中转压力大. 配套: ObjectStorage ABC 抽象层, 业务可切 LocalFS / MinIO.

## 1. 背景与动机

### 1.1 当前痛点 (本地 FS 4 大问题)

| 问题 | 表现 | 触发场景 |
|------|------|----------|
| **多 worker 不共享** | 进程内 `tasks: dict` cache + `ingest_uploads/` 本地盘, 多 uvicorn worker 拿不到对方 task | 部署时 `uvicorn --workers 4`, 上传走 worker A, 列表走 worker B, 拿不到 |
| **容器重启丢数据** | `ingest_uploads/` 容器内, `docker compose restart service` 清空 (非 volume 挂载) | 部署 / 调试 restart 后老 task 全 404 |
| **无 presigned URL** | `read_task_file` 把文件 `read_text()` 进 response body, MD / JSON 还能撑, PDF / SVG 直接卡 | admin 文件预览页要 5MB SVG base64 渲染, 慢 |
| **大文件 backend 中转** | `POST /upload` 走 backend `UploadFile.read()` 流式写, backend 必过 bytes, OOM 风险 | 上传 200MB CAD, backend 内存峰值 = 1 chunk = 1MB OK, 但并发 5 个任务就 5MB+ |
| **product_decoders/output_api.py** | `output/` 本地, `MAX_FILE_SIZE=10MB`, admin 后台只读 | 跨 worker 同样不共享, admin 后台看不到其它 worker 跑的产物 |

### 1.2 MinIO 已就位 (无需 docker 改造)

`docker-compose.yml:53-73` MinIO service 完整, 端口 9000 (API) / 9001 (console), volume `./volumes/minio_data:/data`, network `app-network`. **本次 spec 不动 docker-compose.yml, 只在启动后跑一次性 init 脚本** (`docker/scripts/minio_init.sh`).

### 1.3 候选子系统清单 (本次 4 子系统, E YAGNI)

| # | 子系统 | 集成价值 | 本次 spec | 备注 |
|---|--------|----------|----------|------|
| **A** | **RAG Ingest 知识库 (PDF/CAD/Office)** | ⭐⭐⭐ 大 (5+ 文件) | ✅ Phase 2 | 痛点最大, 必做 |
| **B** | **Chat 媒体 (图片/语音/文件)** | ⭐⭐ 中 (2-3 文件) | ✅ Phase 2.5 | 顺路还 chat-share P0 Dify follow-up (Dify Files API 真接通) |
| **C** | **Eval CSV 数据集** | ⭐ 小 (1-2 文件) | ✅ Phase 4 | 跟 A 顺带, 改造成本小 |
| **D** | **Product decoders 输出 (MD/JSON)** | ⭐ 小 (1 文件) | ✅ Phase 3 | A 的子集, 跟 A 同步 |
| E | 账号头像 | — | ❌ YAGNI | 留未来 |

## 2. 目标 (in-scope, 4 子系统)

1. **新建 ObjectStorage ABC**: `src/storage/object_store.py`, 14 抽象方法 + URI parse/build helper, 业务代码不直接 import impl
2. **2 个 impl**: `LocalFSObjectStore` (默认, dev 用) + `MinioObjectStore` (新, 走 boto3)
3. **env 切换**: `OBJECT_STORE_BACKEND=local` (默认) | `minio`
4. **A 集成 (RAG Ingest)**: `IngestTask.work_dir` 改 URI; 新增 2 端点 `presign`/`finalize`; 保留 `upload` fallback; 响应 shape 改 2 处
5. **B 集成 (Chat 媒体)**: `upload_to_dify` 真接通 Dify Files API (走 ABC 拿原件 + httpx 透传); 1 新端点 (presigned PUT 给 chat composer 用)
6. **C 集成 (Eval CSV)**: `data/eval_datasets/` 改 ABC; `Evaluation.dataset_uri` 新字段; runner 从 URI 读
7. **D 集成 (Product decoders output)**: `output_api.list_files` / `read_file` 改 ABC
8. **bucket 1 + prefix 4**: `rag-ingest` bucket, `inputs/` `outputs/` `temp/` `chat/` `eval/` (按子系统分 prefix)
9. **lifecycle policy**: `temp/` 1 天删, `outputs/` 90 天删, `chat/` 永久, `eval/` 永久
10. **CORS 配 1 个 origin**: 走 `ALLOWED_ORIGIN` env, dev `http://localhost:3000`
11. **新依赖**: `boto3>=1.34,<2.0` + dev `boto3-stubs[s3]`
12. **测试覆盖**: 模式 1 mock 单元 40-55 个 + 模式 4 集成 6-8 个 (CI 必跑)
13. **前端 5 组件 TDD 改**: DocumentsImportForm / TaskDetailClient / OutputListClient / output 文件预览页 / ChatShell-Composer 上传
14. **`FRONTEND_EXPECTS` 同步**: 加 2 个 ingest 端点 + 1 个 chat presign 端点 + 改 2 个响应 shape
15. **handoff 文档 + 文档更新**: handoff md + `docs/ingest.md` + `packages/service/CLAUDE.md` + `README.md`
16. **Health check 集成**: 新增 `check_minio()`, 接进 `health/cache.py` 的 5s 轮询, `/api/health/system` 响应加 `minio` key

## 3. 非目标 (out-of-scope, YAGNI)

- **不** 迁老 data (F1 决策, 接受丢, 老 task 加载报错属预期)
- **不** 改其它子系统 (Chat / Eval / Avatar / Langfuse)
- **不** 写 Python CLI 工具 (bash init 脚本够)
- **不** 跨 bucket 复制 / 多 region / CDN 加速
- **不** 配 SSE-KMS 服务端加密 (MinIO 默认加密够, 生产再开)
- **不** override DeepEval-style 模板 (后续 P1)
- **不** 改 presign TTL 走配置 (硬编 900s, 后续 spec 再抽)
- **不** 加 storage 配额 / 监控 / 告警 (留 ops spec)
- **不** 写 Minio impl unit test (走模式 4 集成测覆盖)

## 4. 现状 (RAG Ingest 5 文件 + 3 BFF)

### 4.1 服务端 5 文件

| 文件 | 行数 | 状态 |
|------|------|------|
| `src/ingest/api.py` | 431 | 有 `_collect_output_files` / `read_task_file` / `download_zip` / `upload` / `list_tasks` / `get_task` |
| `src/ingest/pipeline.py` | 408 | `process_path` / `process_files` / `process_documents` / `process_cad_files` / `process_passthrough` 走本地 Path |
| `src/ingest/store.py` | 94 | ORM 重写, `IngestTask` 持久化, `work_dir` 字段 String(500) |
| `src/ingest/models.py` | 48 | `IngestTask` ORM, 字段顺序跟原 SQLite 1:1 |
| `src/product_decoders/output_api.py` | 91 | `list_files` / `read_file` 读 `output/`, 10MB 上限, SAFE_NAME 白名单 |

### 4.2 BFF 3 route

| 路径 | 用途 | 状态 |
|------|------|------|
| `web/app/api/ingest/upload/route.ts` | multipart 透传 backend `/upload` | 31 行, apiProxy 模式 |
| `web/app/api/ingest/tasks/[id]/files/[name]/route.ts` | 读文件透传 | 25 行 |
| `web/app/api/ingest/tasks/[id]/download/route.ts` | 流式 zip 透传 | 25 行, 不读 body |

### 4.3 关键代码现状 (3 段)

`src/ingest/api.py:255-310` `upload` 端点:
```python
work_dir = UPLOAD_ROOT / uhash / task_id  # 本地 Path
input_dir = work_dir / "input"
output_dir = work_dir / "output"
input_dir.mkdir(parents=True, exist_ok=True)
output_dir.mkdir(parents=True, exist_ok=True)
# ... 流式写文件 ...
background.add_task(_run_ingest, task_id, work_dir, input_dir, output_dir)
```

`src/ingest/api.py:364-392` `read_task_file`:
```python
target = _find_output_file(t.work_dir / "output", name)
return {"name": name, "content": target.read_text(encoding="utf-8", errors="replace"), "mime": _mime_for(target)}
```

`src/product_decoders/output_api.py:54-90` `read_file`:
```python
return {"name": name, "content": target.read_text(encoding="utf-8"), "mime": mime}
```

## 5. 决策点表 (9 决策)

| # | 决策 | 选项 → 选定 | 理由 |
|---|------|-------------|------|
| D1 | scope | A,B,C,D,E → **A** | 痛点最大最直接, 改造成本可量化 (5 文件) |
| D2 | 抽象 | A1,A2,A3 → **A1** | ObjectStorage ABC + LocalFS + MinIO, 2 impl, env 切换 |
| D3 | DB 字段 | B1,B2,B3 → **B1** | URI 字符串 (`local://...` / `s3://...`), 跨 backend 0 歧义 |
| D4 | bucket 布局 | C1,C2,C3 → **C1** | 1 bucket `rag-ingest` + 3 prefix (`inputs/` `outputs/` `temp/`) |
| D5 | API 响应 | D1,D2,D3 → **D1** | 直接返 presigned URL (TTL 900s), 浏览器直 `<a href>` |
| D6 | 上传模式 | E1,E2,E3 → **E1** | 浏览器 presigned PUT 直传 MinIO, backend 不走 bytes |
| D7 | 老数据迁移 | F1,F2,F3 → **F1** | 不迁移, 接受丢 (active dev, 重跑便宜) |
| D8 | 默认 backend | G1,G2,G3 → **G1** | 默认 LocalFS, env 切 minio (复制 config.toml 就能跑) |
| D9 | phasing | H1,H2,H3 → **H1** | 3 phase 顺序交付 (P1 ABC, P2 Ingest, P3 output_api) |

## 6. 设计

### 6.1 三层架构

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (Next.js, 浏览器)                                   │
│  - DocumentsImportForm 上传 PDF → 调 presign API             │
│  - 拿 PUT URL → 浏览器直接 PUT 到 MinIO                      │
│  - 上传完调 /api/ingest/upload/finalize (传 URI)              │
│  - 列表 / 详情 / 下载: 拿 presigned GET URL → <a href>       │
└──────────────────────────────────────────────────────────────┘
        │ HTTPS                  │
        ▼                        ▼
┌──────────────────────┐   ┌────────────────────────┐
│  Next.js BFF         │   │  MinIO                 │
│  (RSC + API routes)  │   │  - bucket: rag-ingest  │
│  - 透传 / 签 URL     │   │  - inputs/{tid}/       │
│  - 不读 bytes         │   │  - outputs/{tid}/      │
└──────────────────────┘   │  - chat/{user}/         │
        │                  │  - eval/{run_id}/       │
        │                  │  - temp/               │
        │                  └────────────────────────┘
        ▼ HTTPS                  ▲ PUT / GET
┌──────────────────────────────────────────────────────────┐
│  FastAPI Service (Python)                                 │
│  - ObjectStore ABC:  LocalFSObjectStore | MinioObjectStore│
│  - ingest pipeline: 调 ABC, 拿 input / 写 output         │
│  - /api/ingest/* :  orchestrate, 签 URL, 不读 bytes       │
│  - IngestTask 表: work_dir 改成 storage_uri (URI 字符串)  │
└──────────────────────────────────────────────────────────┘
```

### 6.2 数据流 (上传 → 处理 → 下载)

| 阶段 | 旧 (local FS) | 新 (MinIO + presigned) |
|------|---------------|------------------------|
| **1. 上传** | 浏览器 multipart → BFF → backend 写 `ingest_uploads/...` | 浏览器调 `POST /presign` 拿 PUT URL → 浏览器直 PUT MinIO `s3://rag-ingest/inputs/{task_id}/{name}` → 调 `POST /finalize` 传 URI |
| **2. 处理** | `process_path(input_dir, output_dir)` 走本地 `Path` | `process_uri(input_prefix, output_prefix, store)` 调 ABC, Minio impl 借出到 `/tmp/minio_stage/{task_id}/` 处理后回传 |
| **3. 列表** | `rglob(output_dir)` | ABC 列出 `s3://rag-ingest/outputs/{task_id}/` (Minio impl 调 `list_objects_v2`) |
| **4. 读文件** | `target.read_text()` 返 `{"name","content","mime"}` | 返 `{"name","url","size","mime"}`, URL 是 `presigned_get_url(uri, ttl=900)` |
| **5. 下载 zip** | 进程内 `ZipFile(buf)` 全量打包 | 改 `store.list + store.open_local_ctx` 流式打包 |

### 6.3 ObjectStorage ABC (14 抽象方法 + URI helper)

```python
"""ObjectStorage ABC + LocalFS + MinIO 实现 (2026-06-16 RAG 接入 MinIO spec)

所有存读删都走 ABC, 业务代码 (ingest / output_api) 不直接 import 具体 impl.

URI scheme:
- local://<relative_path>  (例: local://inputs/20260616-.../foo.pdf)
- s3://<bucket>/<key>      (例: s3://rag-ingest/inputs/20260616-.../foo.pdf)

(注: LocalFS impl 内部 layout 跟 s3 保持一致 — 都用 `inputs/{task_id}/` 前缀.
LocalFS impl 把 key 直接当 LOCAL_ROOT 下的相对路径, 不存 uhash/task_id 嵌套.)
"""

from __future__ import annotations
import abc
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class ObjectMeta:
    """元数据 (不读 body)"""
    uri: str
    size: int
    mime: str | None = None
    last_modified: float | None = None  # epoch seconds


class ObjectStore(abc.ABC):
    """对象存储 ABC"""

    @abc.abstractmethod
    def backend_name(self) -> str: ...

    # ---- 写入 ----
    @abc.abstractmethod
    def put_bytes(self, uri: str, data: bytes, mime: str | None = None) -> None: ...
    @abc.abstractmethod
    def put_stream(self, uri: str, stream: BinaryIO, mime: str | None = None) -> None: ...
    @abc.abstractmethod
    def put_file(self, uri: str, src_path: str, mime: str | None = None) -> None: ...

    # ---- 读取 ----
    @abc.abstractmethod
    def get_bytes(self, uri: str) -> bytes: ...
    @abc.abstractmethod
    def get_stream(self, uri: str) -> BinaryIO: ...
    @abc.abstractmethod
    def open_local(self, uri: str) -> str:
        """下载到临时本地路径, 返路径. 业务代码拿到路径当普通文件用."""
    @abc.abstractmethod
    def release_local(self, local_path: str) -> None: ...

    @contextmanager
    def open_local_ctx(self, uri: str) -> Iterator[str]:
        path = self.open_local(uri)
        try:
            yield path
        finally:
            self.release_local(path)

    # ---- 列举 ----
    @abc.abstractmethod
    def list_prefix(self, prefix_uri: str) -> list[ObjectMeta]: ...
    @abc.abstractmethod
    def exists(self, uri: str) -> bool: ...
    @abc.abstractmethod
    def delete(self, uri: str) -> None: ...
    @abc.abstractmethod
    def delete_prefix(self, prefix_uri: str) -> None: ...

    # ---- Presigned URL (E1 直传用) ----
    @abc.abstractmethod
    def presign_put(self, uri: str, ttl_seconds: int = 900) -> str | None: ...
    @abc.abstractmethod
    def presign_get(self, uri: str, ttl_seconds: int = 900) -> str | None: ...

    # ---- 工厂 ----
    @staticmethod
    def from_config() -> "ObjectStore":
        """读 env 返单例"""


# URI 解析
def parse_uri(uri: str) -> tuple[str, str]:
    """'s3://rag-ingest/inputs/abc/foo.pdf' → ('s3', 'inputs/abc/foo.pdf')"""

def build_uri(backend: str, key: str, bucket: str | None = None) -> str: ...
```

### 6.4 LocalFS impl 行为

| 方法 | 行为 |
|------|------|
| `put_bytes` | `LOCAL_ROOT / key.write_bytes(data)` |
| `get_bytes` | `LOCAL_ROOT / key.read_bytes()` |
| `open_local` | `LOCAL_ROOT / key`, **不复制**, 返绝对路径 |
| `release_local` | no-op |
| `list_prefix` | `LOCAL_ROOT.rglob()` 过滤 key 起始 |
| `presign_*` | 返 `None` |
| `delete` | `unlink(missing_ok=True)` |
| `delete_prefix` | `shutil.rmtree()` |

### 6.5 Minio impl 行为

| 方法 | 行为 |
|------|------|
| `put_bytes` | `s3.put_object(Bucket, Key, Body=data, ContentType=mime)` |
| `put_stream` | `s3.upload_fileobj(stream, Bucket, Key)` (auto multipart ≥ 8MB) |
| `put_file` | `s3.upload_file(src_path, Bucket, Key)` |
| `get_bytes` | `s3.get_object(...)['Body'].read()` |
| `get_stream` | `s3.get_object(...)['Body']` (raw stream) |
| `open_local` | 下到 `/tmp/minio_stage/{key_hash}/{name}`, 维护 `借用表` 防重复下 |
| `release_local` | `os.remove(local_path)` + 引用计数归 0 清目录 |
| `list_prefix` | `s3.list_objects_v2(Bucket, Prefix=key)` → `[ObjectMeta]` |
| `presign_put` | `s3.generate_presigned_url('put_object', ...)` |
| `presign_get` | `s3.generate_presigned_url('get_object', ...)` |
| `delete` | `s3.delete_object(Bucket, Key)` |
| `delete_prefix` | `list + delete` batch |

### 6.6 错误模型

```python
class ObjectStoreError(RuntimeError): ...
class ObjectNotFound(ObjectStoreError): ...
class PresignNotSupported(ObjectStoreError): ...
```

### 6.7 IngestTask 字段调整

```python
class IngestTask(Base):
    # ... 其它字段不变 ...
    # (2026-06-16) 改造: work_dir 不再是本地 Path, 改 URI 字符串
    # 例: 's3://rag-ingest/inputs/20260616-.../' 或 'local://inputs/20260616-.../'
    # 注意: work_dir 是 input prefix, output prefix 由常量推: 's3://rag-ingest/outputs/{task_id}/'
    work_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

**`InputFile` / `OutputFile` dataclass 加 `uri` 字段**:
```python
@dataclass
class InputFile:
    name: str
    size: int
    mime: str
    uri: str  # (2026-06-16) 新增, ABC 拼出
```

**alembic 迁移**: 不需要. `work_dir` 字段类型 `String(500)` 没变, 旧值 (本地 Path) 在 LocalFS impl 下解析失败, 加载报错属 F1 决策预期.

### 6.8 上传端点改写 (E1 浏览器直传)

**新流程**:
```
1. 浏览器 POST /api/ingest/upload/presign
   body: {files: [{name, size, mime}, ...]}
   resp: {task_id, uploads: [{name, uri, put_url, mime}, ...]}
   ↑ 后端: 创 IngestTask (state=queued, no files yet)
          调 store.presign_put(uri, ttl=900) 拿 PUT URL
          返前端

2. 浏览器 对每个 upload 调 PUT {put_url}
   ↑ 浏览器直传 MinIO, 不走 backend

3. 浏览器 POST /api/ingest/upload/finalize
   body: {task_id}
   ↑ 后端: _load(task), state 仍 queued
          BackgroundTask 启动 _run_ingest(task_id, workdir_uri)
          返 {state: 'running', ...}
```

**保留旧 `POST /upload` (multipart) 作 fallback**, 走 `store.put_stream`.

### 6.9 pipeline.py 改造 (最小化)

`process_path` / `process_files` / `process_documents` 等**内部仍用本地 Path** (因为 PDF 解析器 / CAD 库要本地路径), 改用 `store.open_local_ctx()` 桥接:

```python
def process_uri(input_prefix: str, output_prefix: str, store: ObjectStore) -> dict:
    """URI 模式入口: 把 inputs 借出到本地, 跑 process_files, outputs 回传."""
    with tempfile.TemporaryDirectory(prefix="ingest_local_") as local_root:
        local_input = Path(local_root) / "input"
        local_output = Path(local_root) / "output"
        local_input.mkdir(parents=True)
        local_output.mkdir(parents=True)

        for meta in store.list_prefix(input_prefix):
            with store.open_local_ctx(meta.uri) as local_path:
                dst = local_input / Path(meta.uri).name
                shutil.copy(local_path, dst)

        result = process_files(input_dir=str(local_input), output_dir=str(local_output))

        for p in Path(local_output).rglob("*"):
            if p.is_file():
                rel = p.relative_to(local_output)
                uri = _join_uri(output_prefix, str(rel).replace("\\", "/"))
                store.put_file(uri, str(p))

        return result
```

`process_path` / `process_files` 仍**保留旧 path 接口** (向后兼容旧脚本 / CLI), 不删.

### 6.10 output_api.py 改造 (Phase 3)

```python
@router.get("/files")
def list_files():
    store = get_object_store()
    items = []
    for meta in store.list_prefix(_outputs_prefix()):
        if Path(meta.uri).suffix.lower() not in ALLOWED_EXTS:
            continue
        if Path(meta.uri).name.startswith("."):
            continue
        items.append({"name": Path(meta.uri).name, "size": meta.size, "mtime": meta.last_modified})
    return {"files": sorted(items, key=lambda x: x["mtime"], reverse=True)}


@router.get("/files/{name}")
def read_file(name: str):
    store = get_object_store()
    if not SAFE_NAME.match(name):
        raise HTTPException(400, detail=f"非法文件名: {name!r}")
    for meta in store.list_prefix(_outputs_prefix()):
        if Path(meta.uri).name == name:
            url = store.presign_get(meta.uri)
            return {"name": name, "url": url, "size": meta.size, "mime": _mime_for(name)}
    raise HTTPException(404, detail=f"文件不存在: {name}")
```

### 6.11 health check 集成 (P2 末)

`src/health/checks.py` 加 `check_minio()`, 跟 `check_dify` 同模式 (lazy import + 5s timeout + 异常翻 error):

```python
def _get_object_store():
    """从 src.storage 拿单例 (env-driven backend)."""
    from src.storage.object_store import get_object_store
    return get_object_store()


async def check_minio() -> CheckResult:
    """ping MinIO bucket: head_bucket + list 1 个 object 算 latency.

    - OBJECT_STORE_BACKEND=local: status=ok, extra={'backend': 'local', 'skipped': true}
      (不调任何 IO, 避免 dev 强制 MinIO 依赖, 跟 G1 决策一致)
    - OBJECT_STORE_BACKEND=minio: list_objects_v2(Bucket, MaxKeys=1) 测可达 + 算 ms
    - 失败 (网络断 / 凭据错 / bucket 不存在): status=error + error=<msg>
    """
    t0 = time.perf_counter()
    try:
        store = _get_object_store()
        if store.backend_name() == "local":
            return CheckResult(
                status="ok",
                latency_ms=0.0,
                extra={"backend": "local", "skipped": True},
            )
        # minio backend: 真测
        probe_uri = f"s3://{store._cfg.bucket}/.healthcheck-probe"  # impl detail: _cfg
        def _probe():
            return store.list_prefix(f"s3://{store._cfg.bucket}/")  # MaxKeys=1
        await asyncio.to_thread(_probe)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(
            status="ok",
            latency_ms=latency_ms,
            extra={"backend": "minio", "bucket": store._cfg.bucket, "endpoint": store._cfg.endpoint},
        )
    except Exception as e:
        return CheckResult(status="error", latency_ms=None, error=str(e))
```

**`src/health/cache.py` 改 2 处**:

1. `_run_all_checks` 的 `gather` 加 `check_minio()`, dict 加 `"minio": minio_r.__dict__`
2. `get_cached_health` 的 `warming_up` placeholder 加 `minio: {...}`

**`/api/health/system` 响应 shape 变 (兼容性, 纯加 key)**:
```json
{
  "checked_at": "2026-06-16T22:00:00+00:00",
  "python": {...},
  "dify": {...},
  "neo4j": {...},
  "pgvector": {...},
  "system": {...},
  "minio": {                              // ← 新增
    "status": "ok",
    "latency_ms": 12.3,
    "error": null,
    "extra": {"backend": "minio", "bucket": "rag-ingest", "endpoint": "http://localhost:9000"}
  }
}
```

**测试**:
- `tests/health/test_checks_minio.py` 4 测试 (模式 1 mock):
  - `test_check_minio_local_backend_skipped` — `_get_object_store` 返 mock store (backend_name='local'), expect status=ok + extra.skipped=True
  - `test_check_minio_minio_backend_success` — list_prefix 返 1 object, expect status=ok + extra.backend='minio' + extra.bucket
  - `test_check_minio_minio_backend_failure` — list_prefix 抛 ConnectionError, expect status=error + error 含 'Connection'
  - `test_check_minio_records_latency` — list_prefix 返 mock, latency_ms > 0

### 6.12 Chat 媒体集成 (B, Phase 2.5)

**位置**: `packages/service/src/chat_share/service.py` + `router.py` + `web/app/api/chat/files/route.ts`

**当前 placeholder 债** ([src/chat_share/service.py:116-123](packages/service/src/chat_share/service.py#L116-L123)):
```python
async def upload_to_dify(self, file) -> dict[str, Any]:
    """透传文件到 Dify Files API → 返 {uploadFileId}. 当前占位."""
    return {"uploadFileId": f"placeholder-{secrets.token_hex(6)}"}  # 假 ID, Dify Chatflow 读不到
```

**新流程 (BFF → backend → MinIO + Dify 透传)**:

```
1. 浏览器调 BFF POST /api/chat/files/presign
   body: {name, size, mime}
   BFF 透传到 backend
   ↑ backend: 拿 ABC 单例 → 创 chat/{user_id}/{uuid}-{name} URI
                调 store.presign_put(uri, ttl=900) 拿 PUT URL
                返 {uri, put_url, mime, expires_in: 900}

2. 浏览器直 PUT {put_url} (Content-Type: mime, body: file)
   ↑ 直传 MinIO, 不走 backend

3. 浏览器调 BFF POST /api/chat/files/finalize
   body: {uri, name, mime}
   BFF 透传到 backend
   ↑ backend: 从 ABC 读 bytes (store.get_bytes(uri))
              调 httpx → DIFY_BASE_URL/files/upload (multipart 透传, 走 DIFY_CHAT_API_KEY)
              返 Dify 真 {uploadFileId} + 自家 {uri} (原件, 可重发/可重处理)
              关键: 失败不删原件 (uri 留着, retry 用)
```

**`router.py` 新增 2 端点 (跟 ingest 同模式)**:

```python
@router.post("/files/presign", response_model=PresignChatFileResponse)
def presign_chat_file(
    req: PresignChatFileRequest,
    current: CurrentUser = Depends(resolve_user),
):
    """签 PUT URL, 浏览器直传 MinIO."""
    _validate_chat_file_meta(req.name, req.size, req.mime)  # 跟旧 _validate_upload 同逻辑
    uri = f"s3://{BUCKET}/chat/{current.id}/{uuid.uuid4().hex}-{Path(req.name).name}"
    put_url = get_object_store().presign_put(uri)
    return PresignChatFileResponse(uri=uri, put_url=put_url, mime=req.mime, expires_in=900)


@router.post("/files/finalize", response_model=UploadFileResponse)
async def finalize_chat_file(
    req: FinalizeChatFileRequest,
    current: CurrentUser = Depends(resolve_user),
):
    """读 ABC URI bytes, 透传 Dify Files API, 返真 {uploadFileId} + 自家 {uri}."""
    # 1. 验 URI owner 跟当前用户匹配 (防越权)
    if not req.uri.startswith(f"s3://{BUCKET}/chat/{current.id}/"):
        raise HTTPException(403, detail="URI 不属于当前用户")
    # 2. 读 bytes
    try:
        data = get_object_store().get_bytes(req.uri)
    except ObjectNotFound:
        raise HTTPException(404, detail="原件不存在, 请重传") from None
    # 3. 透传 Dify
    dify_resp = await _upload_to_dify_files_api(data, req.name, req.mime)
    return UploadFileResponse(uploadFileId=dify_resp["uploadFileId"], uri=req.uri)  # ← 新增 uri 字段


# 保留旧 POST /api/chat/files (multipart fallback)
@router.post("/files", response_model=UploadFileResponse)
async def upload_file(file: UploadFile = File(...), current: ...):
    """Fallback: 走 multipart 直 backend. Local backend: put_bytes. Minio: put_stream."""
    _validate_upload(file)
    data = await file.read()
    uri = f"s3://{BUCKET}/chat/{current.id}/{uuid.uuid4().hex}-{file.filename}"
    get_object_store().put_bytes(uri, data, mime=file.content_type)
    dify_resp = await _upload_to_dify_files_api(data, file.filename, file.content_type)
    return UploadFileResponse(uploadFileId=dify_resp["uploadFileId"], uri=uri)
```

**`UploadFileResponse` schema 加 `uri` 字段** (跟 A 同步, 保留 `uploadFileId` 给 Dify 兼容):

```python
class UploadFileResponse(BaseModel):
    uploadFileId: str  # Dify 真 ID, ChatComposer 用
    uri: str  # 自家 ABC URI, 重发/重处理用
```

**`service.py::upload_to_dify` 真接通** (走 httpx + DIFY_CHAT_API_KEY):
```python
async def _upload_to_dify_files_api(self, data: bytes, name: str, mime: str) -> dict:
    """httpx 透传 Dify Files API. 走 env DIFY_BASE_URL + DIFY_CHAT_API_KEY.
    失败抛 DifyAPIError (跟现有 dify_client 异常一致)."""
    base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
    api_key = os.getenv("DIFY_CHAT_API_KEY", "")
    if not api_key:
        raise DifyAPIError("DIFY_CHAT_API_KEY 未配置")
    resp = await httpx.AsyncClient().post(
        f"{base_url}/files/upload",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": (name, data, mime)},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise DifyAPIError(f"Dify upload failed: HTTP {resp.status_code} {resp.text}")
    return resp.json()  # {id, name, size, ...}
```

**BFF 改** (`web/app/api/chat/files/route.ts` 新):
```ts
// POST /api/chat/files/presign → backend POST /api/chat/files/presign (透传)
// POST /api/chat/files/finalize → backend POST /api/chat/files/finalize
// 旧 POST /api/chat/files 保留 fallback
```

**前端 ChatShell-Composer 改** (跟 A 同模式):
- 优先 presign/finalize 流程
- 失败 fallback 走 multipart
- `composer-attachments.tsx` 拿 `uploadFileId` 跟 `uri` 都存 local, 重发用 uri

**测试** (4 个新):
- `tests/chat_share/test_files_presign.py` 4-6 测试 (模式 1 mock)
  - `test_presign_chat_file_returns_put_url` — mock store.presign_put 返 'https://minio/...'
  - `test_presign_chat_file_oversize_rejected` — size > 20MB → 413
  - `test_presign_chat_file_bad_mime_rejected` — mime 'application/octet-stream' → 400
  - `test_finalize_chat_file_forwards_to_dify` — mock httpx 调 Dify, 验 {uploadFileId, uri}
  - `test_finalize_chat_file_uri_owner_mismatch_403` — uri 不属当前 user → 403
  - `test_finalize_chat_file_dify_failure_keeps_uri` — Dify 500, URI 仍存在 ABC (不删, 供 retry)
- 改 `tests/chat_share/test_files_upload.py` 1-2 测试: 旧 placeholder 测试改成真 httpx mock

### 6.13 Eval CSV 集成 (C, Phase 4)

**位置**: `packages/service/src/eval/router.py` + `runner.py` + `models.py`

**当前** ([src/eval/router.py:97-115](packages/service/src/eval/router.py#L97-L115)):
```python
content = await file.read()  # backend 走 bytes
rows = parse_eval_csv(content, ...)  # 校验
dataset_path = DATASETS_DIR / f"{uuid.uuid4().hex}.csv"
dataset_path.write_bytes(content)  # 写本地 data/eval_datasets/
```

**改造**:
1. 保留 multipart 入口 (5MB 小文件, 不值得走 presigned)
2. 内部把 bytes 走 ABC 写 `s3://rag-ingest/eval/{run_id}/dataset.csv` (无 user_id 嵌套, 跟 run 1:1)
3. `Evaluation` model 加 `dataset_uri: str | None` 字段
4. Runner 启动时, 从 `dataset_uri` 读 CSV (走 ABC), 不再读 `data/eval_datasets/`
5. 旧 `data/eval_datasets/` 本地保留 (dev), 不删 (active dev, 不破坏现有)
6. Alembic migration: 加列 (nullable, 旧 record 留 None → runner 走旧本地路径 fallback, F1 决策)

**`models.py::Evaluation` 加列** (CLAUDE.md "alembic DDL 用模式 3", 但本期未实现迁移机制, 用 plain `ALTER TABLE` 一行):
```python
class Evaluation(Base):
    # ... 旧字段 ...
    dataset_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)  # (2026-06-16) 新
```

**`router.py::upload_run` 改**:
```python
@router.post("/runs")
async def upload_run(file, concurrency, current):
    content = await file.read()
    try:
        rows = parse_eval_csv(content, filename=file.filename or "upload.csv")
    except CSVParsingError as e:
        raise HTTPException(400, str(e)) from e

    # (2026-06-16) 走 ABC, 不写本地
    run_id = uuid.uuid4().hex
    dataset_uri = f"s3://{BUCKET}/eval/{run_id}/dataset.csv"
    get_object_store().put_bytes(dataset_uri, content, mime="text/csv")

    with session_scope() as s:
        e = Evaluation(
            id=run_id, user_id=current.id, dataset_name=file.filename or "upload.csv",
            dataset_uri=dataset_uri,  # 新字段
            # 不再传 dataset_path (旧字段, 跟 local FS 绑)
            state="pending", total_samples=len(rows), concurrency=concurrency,
        )
        s.add(e)

    background.add_task(run_evaluation, run_id, dataset_uri, ...)  # ← 传 URI, 不传 path
    return {"id": run_id, "status": "pending", "total_samples": len(rows)}
```

**`runner.py::run_evaluation` 改**:
```python
async def run_evaluation(run_id, dataset_uri: str | None = None, ...):
    """启动时: 优先从 dataset_uri 读 ABC, 旧 record 走本地 fallback (F1)."""
    if dataset_uri:
        content = get_object_store().get_bytes(dataset_uri)
        dataset = parse_eval_csv(content, filename=dataset_uri)
    else:
        # 旧 record: 走本地 (F1 决策, 接受丢)
        dataset_path = DATASETS_DIR / f"{run_id}.csv"
        if not dataset_path.exists():
            raise FileNotFoundError(f"Eval {run_id} 缺 dataset (无 URI 也无本地)")
        dataset = parse_eval_csv(dataset_path.read_bytes(), filename=str(dataset_path))
    # ... 跟旧逻辑 ...
```

**前端 / BFF 0 改**: 前端 multipart 调 `/api/eval/runs`, BFF `evaluate/runs/route.ts` 透传. 前端无感.

**测试** (3-4 个新):
- `tests/eval/test_csv_storage.py` 3-4 测试 (模式 1 mock)
  - `test_upload_run_stores_to_abc` — mock store.put_bytes, 验 put_bytes 收到 (dataset_uri, content, mime='text/csv')
  - `test_upload_run_persists_dataset_uri_in_db` — `Evaluation.dataset_uri` 字段被设
  - `test_runner_reads_from_uri` — mock store.get_bytes 返 csv, runner 正常跑
  - `test_runner_fallback_to_local_when_uri_none` — 老 record (uri=None), 走 DATASETS_DIR
- 改 `tests/eval/test_router.py::test_upload_run_*`: 旧断言 `dataset_path.write_bytes` 改成 `store.put_bytes`

## 7. MinIO 端配置

### 7.1 docker-compose.yml 改动

**结论: 0 改动**. MinIO service 已在 `docker-compose.yml:53-73`, 配置完整.

### 7.2 .env.example 新增段

```bash
# -----------------------------------------------------------------------------
# Object Storage (2026-06-16 新增, RAG Ingest 接入 MinIO)
# -----------------------------------------------------------------------------
OBJECT_STORE_BACKEND=local  # local (默认) | minio
OBJECT_STORE_LOCAL_ROOT=./ingest_uploads
OBJECT_STORE_S3_ENDPOINT=http://localhost:9000
OBJECT_STORE_S3_ACCESS_KEY=minioadmin
OBJECT_STORE_S3_SECRET_KEY=minioadmin
OBJECT_STORE_S3_BUCKET=rag-ingest
OBJECT_STORE_S3_REGION=us-east-1
OBJECT_STORE_S3_USE_SSL=false
OBJECT_STORE_PRESIGN_TTL_SECONDS=900
OBJECT_STORE_STAGE_ROOT=/tmp/minio_stage
```

### 7.3 一次性 init 脚本

**新文件**: `docker/scripts/minio_init.sh` (bash, 80 行)

```bash
#!/usr/bin/env bash
# MinIO bucket + CORS + lifecycle 初始化
# 跑法: bash docker/scripts/minio_init.sh
# 幂等: 重复跑无副作用
set -euo pipefail

: "${MINIO_ROOT_USER:=minioadmin}"
: "${MINIO_ROOT_PASSWORD:=minioadmin}"
: "${MINIO_ENDPOINT:=localhost:9000}"
: "${BUCKET:=rag-ingest}"
: "${ALLOWED_ORIGIN:=http://localhost:3000}"

mc alias set local "http://${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
mc mb --ignore-existing "local/${BUCKET}"

# CORS (浏览器直传)
cat > /tmp/cors.json <<EOF
{"CORSRules": [{"AllowedOrigins": ["${ALLOWED_ORIGIN}"], "AllowedMethods": ["GET","PUT","POST","DELETE","HEAD"], "AllowedHeaders": ["*"], "ExposeHeaders": ["ETag","Content-Length","Content-Type"], "MaxAgeSeconds": 3000}]}
EOF
mc cors set /tmp/cors.json "local/${BUCKET}"

# Lifecycle (5 prefix rules)
cat > /tmp/lifecycle.json <<EOF
{"Rules": [
  {"ID": "expire-temp", "Status": "Enabled", "Filter": {"Prefix": "temp/"}, "Expiration": {"Days": 1}},
  {"ID": "expire-outputs", "Status": "Enabled", "Filter": {"Prefix": "outputs/"}, "Expiration": {"Days": 90}},
  {"ID": "keep-chat", "Status": "Enabled", "Filter": {"Prefix": "chat/"}, "Expiration": {"Days": 0}},
  {"ID": "keep-eval", "Status": "Enabled", "Filter": {"Prefix": "eval/"}, "Expiration": {"Days": 0}},
  {"ID": "keep-inputs", "Status": "Enabled", "Filter": {"Prefix": "inputs/"}, "Expiration": {"Days": 0}}
]}
EOF
mc ilm import < /tmp/lifecycle.json
```

### 7.4 Python 客户端 — boto3 (S3 兼容)

| 候选 | 选 / 不选 | 原因 |
|------|----------|------|
| `boto3` | **选** | 官方 AWS SDK, MinIO 完全兼容 S3 v4 签名, 类型 stub 完整 |
| `minio-py` | 不选 | 跟 S3 偏离 1 步, 后期换真 S3 / R2 / OSS 要重写 |
| `aioboto3` | 延后 | 现有 ingest 是 sync BackgroundTask, 不需 async |
| `s3fs` | 不选 | 抽象层再加一层, 跟 ABC 双层抽象重复 |

**`pyproject.toml` 新增依赖**:
```toml
dependencies = [..., "boto3>=1.34,<2.0"]
[project.optional-dependencies]
dev = ["boto3-stubs[s3]>=1.34,<2.0", "mypy-boto3-s3>=1.34,<2.0"]
```

### 7.5 启动期 bucket 探活 — 懒加载

`ObjectStore.from_config()` 拿到 impl 后, **不**在启动期 ping MinIO. 改成**懒加载**: 第一次调 `put_bytes / list_prefix` 时 check, 失败抛 `MinioObjectStoreError("连接失败: ...")`, router 翻 503.

**理由**:
- dev 不启 MinIO 也能起服务 (用 local backend)
- 集成测 docker compose up 顺序: MinIO healthcheck 已就绪, 服务再起
- 真实业务报 503 比启动失败好处理 (服务可启, 部分功能降级)

## 8. 实施步骤 (3 phase)

### Phase 1: ObjectStorage ABC (1-1.5 天)

- [ ] `src/storage/object_store.py` (~ 250 行): ABC + LocalFS impl + Minio impl + URI parse/build + 错误模型
- [ ] `src/storage/__init__.py` 暴露 `get_object_store()` 单例 helper
- [ ] `tests/storage/test_object_store.py` 12-15 测试 (模式 1)
- [ ] `pyproject.toml` 加 `boto3` + `boto3-stubs[s3]`
- [ ] `.env.example` 加 Object Storage 段
- [ ] `docker/scripts/minio_init.sh` 80 行 + chmod +x
- [ ] `uv sync` 跑通, `uv run pytest tests/storage/test_object_store.py` 全绿
- [ ] **P1 不接 ingest pipeline** (隔离清晰)

### Phase 2: Ingest 端到端迁移 (1-1.5 天)

- [ ] `src/ingest/models.py` `IngestTask.work_dir` 注释更新 + `InputFile.uri` / `OutputFile.uri` 加
- [ ] `src/ingest/store.py` `_to_dict` 注释更新 (语义变, 字段类型不变)
- [ ] `src/ingest/pipeline.py` 加 `process_uri` 适配层
- [ ] `src/ingest/api.py` 改造:
  - `presign_upload` (新) / `finalize_upload` (新) / `upload` (改走 put_stream, 保留 fallback)
  - `_collect_output_files(workdir_uri, store)` 改 ABC
  - `read_task_file` 改返 `{name, url, size, mime}` (D1)
  - `download_zip` 改流式拉 ABC
- [ ] BFF: 拆 `upload/route.ts` → `upload/presign/route.ts` + `upload/finalize/route.ts` + 保留 `upload/route.ts` (fallback)
- [ ] `tests/ingest/test_api_presign.py` 6-8 测试 (模式 1)
- [ ] `tests/ingest/test_api_ingest_uri.py` 8-10 测试 (模式 1)
- [ ] `tests/test_api_contract.py` `FRONTEND_EXPECTS` 同步: 加 2 个新端点 + 改 `files/{name}` 响应 shape
- [ ] `tests/integration/test_minio_e2e.py` 6-8 测试 (模式 4) **CI 必绿**
- [ ] `src/health/checks.py` 加 `check_minio()` (6.11 节)
- [ ] `src/health/cache.py` `_run_all_checks` + `warming_up` placeholder 加 `minio` key
- [ ] `tests/health/test_checks_minio.py` 4 测试 (模式 1)
- [ ] 前端 4 组件 TDD 改 (DocumentsImportForm / TaskDetailClient / OutputListClient / output 文件预览页)
- [ ] 全套 `uv run pytest` + `bun run test` + `bun run typecheck` + `bun run lint` 必绿
- [ ] 浏览器 E2E 手测: 50MB PDF 上传 → 处理 → 列表 → 点击预览 → 下载 zip
- [ ] admin `/api/health/system` 看到 `minio` key 报 {status: ok, backend: minio}

### Phase 3: output_api 迁移 (0.5 天)

- [ ] `src/product_decoders/output_api.py` `list_files` / `read_file` 改 ABC
- [ ] `tests/product_decoders/test_output_api_uri.py` 4-5 测试 (模式 1)
- [ ] admin 文件预览页前端改 (用 `url` 渲染)
- [ ] 全套测试必绿

### Phase 2.5: Chat 媒体集成 (B, 0.5-1 天)

- [ ] `src/chat_share/router.py` 加 `presign_chat_file` + `finalize_chat_file` 端点
- [ ] `src/chat_share/service.py::upload_to_dify` 改造: 走 httpx 透传真 Dify Files API (替换 placeholder)
- [ ] `src/chat_share/schemas.py::UploadFileResponse` 加 `uri` 字段
- [ ] 保留 `POST /api/chat/files` multipart 作 fallback (跟 A 同模式)
- [ ] BFF: 拆 `web/app/api/chat/files/route.ts` → `files/presign/route.ts` + `files/finalize/route.ts` + 保留 `files/route.ts`
- [ ] 前端 ChatShell-Composer 改: presign/finalize 优先, fallback multipart
- [ ] `tests/chat_share/test_files_presign.py` 4-6 测试 (模式 1 mock httpx + mock store)
- [ ] 改 `tests/chat_share/test_files_upload.py` 1-2 测试: 旧 placeholder 改真 httpx mock
- [ ] `tests/test_api_contract.py` `FRONTEND_EXPECTS` 同步: 加 2 个 chat 端点
- [ ] 全套测试必绿
- [ ] 浏览器 E2E 手测: chat composer 上传图片 → Dify 真上传 → Chatflow 能读到 file

### Phase 4: Eval CSV 集成 (C, 0.5 天)

- [ ] `src/eval/models.py::Evaluation` 加 `dataset_uri: str | None` 字段
- [ ] Alembic migration: `ALTER TABLE evaluations ADD COLUMN dataset_uri VARCHAR(500)` (nullable)
- [ ] `src/eval/router.py::upload_run` 改: 写 ABC, 存 dataset_uri, 不再写 `data/eval_datasets/`
- [ ] `src/eval/runner.py::run_evaluation` 改: 优先从 dataset_uri 读, 老 record 走本地 fallback
- [ ] `tests/eval/test_csv_storage.py` 3-4 测试 (模式 1 mock)
- [ ] 改 `tests/eval/test_router.py` 旧断言 (write_bytes → put_bytes)
- [ ] 全套测试必绿
- [ ] 浏览器 E2E 手测: admin 上传 CSV → runner 跑 → 列表看到 run 状态

### Rollout

- **dev**: 装包 → docker compose up minio → 跑 init 脚本 → .env.local 改 `OBJECT_STORE_BACKEND=minio` 测一遍
- **CI**: docker compose up minio + init 脚本 + 跑模式 4 集成测
- **生产**: secret manager 注入 MINIO 凭据 + init 脚本跑 1 次 + 灰度切 backend
- **回滚**: env 切回 `local` 立即生效, 灰度风险 0

## 9. 风险矩阵 (14 项)

| # | 风险 | 严重度 | 概率 | 缓解 |
|---|------|--------|------|------|
| R1 | MinIO 启动期未就绪 | 高 | 中 | 懒加载, 第一次失败翻 503 |
| R2 | CORS 没配 | 高 | 中 | `minio_init.sh` 配 CORS, e2e 校验 CORS 头 |
| R3 | presigned URL 过期 (16 min 后用) | 中 | 低 | TTL=900s, UI 提示"URL 已过期, 刷新" |
| R4 | 大文件 multipart 切 | 中 | 低 | boto3 `upload_fileobj` 8MB 自动切, put_stream 走它 |
| R5 | `/upload` fallback OOM | 中 | 中 | put_stream 不入内存; MAX_UPLOAD_SIZE 降到 100MB |
| R6 | `output_files[].url` 破坏旧前端 | 高 | 高 | **同 commit 改前端**, 7 组件 + 测试 |
| R7 | `IngestTask.work_dir` 旧值失效 | 中 | 高 (F1) | `_load` try/except, 单条坏数据不阻塞 list |
| R8 | MinIO IAM credentials 泄露 | 中 | 中 | `.env.local` 在 `.gitignore`, 跟现 PG_PASSWORD 一样处理 |
| R9 | boto3 库升级不兼容 | 低 | 低 | 钉 `boto3>=1.34,<2.0`, lock 文件锁 |
| R10 | ABC 接口缺方法 (未来场景) | 中 | 中 | 14 抽象方法够当前 + 3 未来场景, 后续 spec 加 |
| R11 | **B Dify Files API 透传失败, URI 残留** | 中 | 中 | Dify 5xx 时 URI 不删, 供 retry; 单独 cleanup 脚本 (out-of-scope) |
| R12 | **B UploadFileResponse 加 uri 字段破坏旧前端** | 中 | 中 | Composer 改读 uri 字段, TDD 必测; ChatShell.test.tsx 加 url 用法 |
| R13 | **C alembic 加 dataset_uri 列跟现 data 冲突** | 低 | 低 | 旧 record dataset_uri=None, runner 走本地 fallback (F1 决策) |
| R14 | **C 5MB 小文件也走 ABC, 走 latency** | 低 | 低 | put_bytes 单 PUT 5MB, 10ms 内完, 跟本地写差别小; 真不行留 multipart fallback |

## 10. 验收清单 (definition of done)

### Phase 1
- [ ] `src/storage/object_store.py` ABC + LocalFS + Minio impl
- [ ] `tests/storage/test_object_store.py` 12-15 测试全绿
- [ ] `pyproject.toml` 加 `boto3>=1.34,<2.0` + `boto3-stubs[s3]`
- [ ] `.env.example` 加 Object Storage 段
- [ ] `docker/scripts/minio_init.sh` 80 行可跑

### Phase 2
- [ ] `src/ingest/api.py` 改 ABC 完
- [ ] `src/ingest/pipeline.py` 加 `process_uri` 适配层
- [ ] BFF 拆 3 个 route 完
- [ ] `tests/ingest/test_api_presign.py` 6-8 测试 (模式 1)
- [ ] `tests/ingest/test_api_ingest_uri.py` 8-10 测试 (模式 1)
- [ ] `tests/test_api_contract.py` `FRONTEND_EXPECTS` 同步
- [ ] `tests/integration/test_minio_e2e.py` 6-8 测试 (模式 4) **CI 必绿**
- [ ] `src/health/checks.py` 加 `check_minio()` + `tests/health/test_checks_minio.py` 4 测试
- [ ] `src/health/cache.py` `_run_all_checks` + `warming_up` 加 `minio` key
- [ ] 前端 4 组件 TDD 改完
- [ ] 全套测试必绿
- [ ] 浏览器 E2E 手测通过 (含 admin `/api/health/system` 看到 `minio` 报 {status:ok, backend:minio})

### Phase 3
- [ ] `src/product_decoders/output_api.py` 改 ABC
- [ ] `tests/product_decoders/test_output_api_uri.py` 4-5 测试 (模式 1)
- [ ] admin 文件预览页前端改
- [ ] 全套测试必绿

### Phase 2.5
- [ ] `src/chat_share/router.py` 加 2 端点 (presign + finalize)
- [ ] `src/chat_share/service.py` `upload_to_dify` 真接通 (httpx + DIFY_CHAT_API_KEY)
- [ ] `src/chat_share/schemas.py` `UploadFileResponse` 加 `uri` 字段
- [ ] 保留 fallback `POST /api/chat/files`
- [ ] BFF 拆 3 个 route
- [ ] 前端 ChatShell-Composer 改
- [ ] `tests/chat_share/test_files_presign.py` 4-6 测试
- [ ] 改 `tests/chat_share/test_files_upload.py` 1-2 测试
- [ ] `FRONTEND_EXPECTS` 加 2 个 chat 端点
- [ ] 全套测试必绿
- [ ] 浏览器 E2E: chat composer 上传 → Dify 真接通

### Phase 4
- [ ] `src/eval/models.py::Evaluation` 加 `dataset_uri` 字段
- [ ] Alembic migration 加列
- [ ] `src/eval/router.py::upload_run` 改 ABC
- [ ] `src/eval/runner.py::run_evaluation` 改 URI 模式
- [ ] `tests/eval/test_csv_storage.py` 3-4 测试
- [ ] 改 `tests/eval/test_router.py` 旧断言
- [ ] 全套测试必绿
- [ ] 浏览器 E2E: admin 上传 CSV → runner 跑 → 列表看到 run

### 整体
- [ ] 9 个 commit (3 phase × 3 commit, 或按文件聚合 6-8)
- [ ] `docs/superpowers/handoffs/2026-06-16-rag-minio-integration.md` handoff 文档
- [ ] `docs/ingest.md` 更新 (加 MinIO 接入 + 端点 + env 章节)
- [ ] `packages/service/CLAUDE.md` 补 "ObjectStore ABC 使用" 章节
- [ ] `README.md` 加 MinIO 启动 + init 步骤

## 11. 关联 handoff / spec

- [[2026-06-16-chat-share-and-media]] — B (Chat 媒体) **本期一起做**, 还 P0 Dify Files API placeholder 债
- [[2026-06-16-test-isolation]] — 集成测走模式 4 (独立 DB + MinIO container), 跟 dev DB 隔离
- [[2026-06-16-sqlite-to-pgvector-migration]] — IngestTask ORM 已迁 PG, 本次 `work_dir` 字段类型不变, 不需 alembic; 但 C 加 `Evaluation.dataset_uri` 需要 alembic migration
- [[2026-06-16-deepeval-replace-llamaindex-design]] — 平行 spec, 互不影响 (但 RAGAMetrics contract 跟本次 0 关联)

## 12. 关联 skill / 决策记录

- `superpowers:brainstorming` 9 决策 D1-D9
- `superpowers:writing-plans` 即将调用, 拆 8-task plan
- 选 `boto3` 而非 `minio-py` — 留 S3/R2/OSS 兼容
- 选 `LocalFSObjectStore` 作默认 — 复制 config.toml 就能跑
- 选 lazy ping — dev 不强制 MinIO
- 选 E1 (presigned PUT) 而非 E2 (backend proxy) — 大文件不卡 backend
- 选 F1 (不迁) — active dev 重跑便宜
- 选 H1 (3 phase) — 隔离清晰, 阶段可跳
