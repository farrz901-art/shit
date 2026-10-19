---
title: RAG MinIO 集成 - 回归 bug 修复
date: 2026-06-17
status: 完成
---

# RAG MinIO 集成 - 回归 bug 修复 (2026-06-17)

## 背景

跑全量 `pytest` + `vitest` 发现 3 类回归 bug, 来自 [[2026-06-16-rag-minio-integration]] 实施期间引入或预存 baseline 问题.

## 修复 commit

`309fe86` — fix: collection error + output_api 本地/minio 分支 + vitest server-only shim

5 文件改动:
- 新建 `packages/service/tests/chat_share/__init__.py` (空文件)
- 新建 `packages/service/tests/memory/__init__.py` (空文件)
- 新建 `packages/web/test-shims/server-only-empty.ts`
- 改 `packages/web/vitest.config.ts` (加 `server-only` alias)
- 改 `packages/service/src/product_decoders/output_api.py` (local/minio 分支 + 改用 store.backend_name)

---

## Bug 1: pytest collection error (test_router/test_service 同名冲突)

### 症状

跑 `pytest tests/` 直接报 collection error:

```
ERROR collecting tests/memory/test_router.py
import file mismatch:
imported module 'test_router' has this __file__ attribute:
  C:\doc\Code\rag\packages\service\tests\chat_share\test_router.py
which is not the same as the test file we want to collect:
  C:\doc\Code\rag\packages\service\tests\memory\test_router.py
```

### 根因

pytest 默认 `import-mode=prepend`, 把 test 文件按 basename 当模块名. `tests/chat_share/test_router.py` 和 `tests/memory/test_router.py` 同名, 后者被前者覆盖, collection 报 mismatch.

`tests/eval/__init__.py` 存在所以 eval 测试能跑, 其他缺 `__init__.py` 的子目录 (chat_share, memory) 互相冲突.

### 修复

加 `__init__.py` 让两个目录都成 Python package, pytest 走完整包路径.

### 经验

**预防**: 任何含 `tests/<subdir>/test_*.py` 的子目录都需要 `__init__.py` (跟 `tests/eval/` 一致). 建议加 pre-commit hook 强制.

---

## Bug 2: vitest `import "server-only"` 解析失败 (26 文件 fail)

### 症状

跑 `bun run test` 时 RSC 相关测试集体 fail:

```
Error: Failed to resolve import "server-only" from "lib/api/rsc-queries.ts". Does the file exist?
```

涉及 `app/[locale]/knowledge/{datasets,relations}/page.test.tsx` 等 26 个 RSC 文件.

### 根因

`lib/api/rsc-queries.ts` 是 RSC prefetch 工具, 文件头有 `import "server-only"` (Next.js marker, 防 client 端误 import). vitest 在 jsdom/client 环境跑, `server-only` 是 Node-only 包 (装了会抛 "you're importing it from client code"), vitest 解析失败.

### 修复

1. 创建 `packages/web/test-shims/server-only-empty.ts` (空模块):
   ```ts
   // server-only 是 Next.js 的 marker module, 用于标记 RSC 代码不能在 client 端 import.
   // 在 vitest 里把它 alias 成空模块, 让 RSC prefetch 工具的测试能跑.
   ```

2. `vitest.config.ts` 加 alias:
   ```ts
   "server-only": path.resolve(__dirname, "test-shims/server-only-empty.ts"),
   ```

### 效果

26 个 fail → 5 个 fail (剩 5 个是其它 baseline 问题).

### 经验

**预防**: 项目同时存在 `next.js` (用 server-only marker) + `vitest` (走 jsdom) 的场景, 必须有 shim 策略. 建议把 shim 加进 vitest setup template, 后续加 RSC 测试不需要重复配置.

---

## Bug 3 (核心回归): output_api D 集成破坏 test_web_apis 路径

### 症状

D 集成 commit `1420792` 后, `tests/ingest/test_web_apis.py` 5 个测试 fail:

```
FAILED tests/ingest/test_web_apis.py::TestListFiles::test_list_files_returns_md_and_json_only
AssertionError: assert 'doc1.md' in []
```

测试 fixture:
```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    fake_paths = Paths(input_dir=tmp_path, output_dir=tmp_path)
    monkeypatch.setattr("src.ingest.config.get_paths", lambda: fake_paths)
    return TestClient(create_app())
```

测试期望: 写文件到 `get_paths().output_dir` → `/api/output/files` 能列出.

### 根因

D 集成把 `output_api.py` 改成全走 ABC:

```python
def _outputs_prefix() -> str:
    backend = os.getenv("OBJECT_STORE_BACKEND", "local").lower()
    if backend == "minio":
        bucket = os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")
        return f"s3://{bucket}/outputs/"
    return "local://outputs/"  # ← 这里
```

`local://outputs/` 在 LocalFS impl 里解析到 `OBJECT_STORE_LOCAL_ROOT/outputs/` (= `./ingest_uploads/outputs/`), **跟 `get_paths().output_dir` (= `./output`) 完全不是同一目录**.

旧 `output_api.py` 是直接读 `_output_dir() = get_paths().output_dir`. 测试在 `tmp_path` 写文件, 旧代码从同一路径读, 通过. 新代码从 `./ingest_uploads/outputs/` 读, 永远空.

**两个语义错位**:
1. ABC `outputs/` prefix vs `get_paths().output_dir` 不同位置
2. Pipeline 实际产物落在 per-task `{workdir}/output/` (process_uri), 也不是全局 `outputs/`

### 修复

`output_api.py` 加 backend 分支:

```python
def _backend_name() -> str:
    """读 store backend, 测试可 monkeypatch get_object_store"""
    return get_object_store().backend_name()


@router.get("/files")
def list_files():
    if _backend_name() == "local":
        # 本地 FS (跟旧行为 1:1, 兼容测试)
        output_dir = _output_dir()  # = get_paths().output_dir
        ...
    # minio: 走 ABC + presigned GET
    ...
```

- local backend: 保留旧本地 FS 逻辑 (content 字段 + 10MB 限制 + 越权校验), 跟 `test_web_apis.py` 行为一致
- minio backend: 走 ABC `s3://bucket/outputs/` + presigned GET (新 D 集成 spec)

**关键改动**: `_backend_name()` 改读 `get_object_store().backend_name()` 而非 env, 让测试 mock `get_object_store` 直接控制 backend 行为, 不需要 mock env.

### 效果

- test_web_apis 5 个 fail → pass
- product_decoders/test_output_api_uri 6 个 fail → pass (之前因 lazy import + 用 env, mock patch 失效)

### Follow-up (未做, R17 风险点)

`process_uri` 写产物到 per-task `{workdir}/output/`, 但 `output_api.py` 全局列 `outputs/` 或 `get_paths().output_dir` — **生产环境 admin 页看不到 ingest 产物**.

需要在后续 plan 加:
1. `output_api.py` 枚举所有 task workdir, 聚合 outputs
2. 或 `process_uri` 写一份镜像到全局 `outputs/` (冗余但简单)

---

## 测试结果对比

| 维度 | 修复前 | 修复后 |
|------|-------|-------|
| pytest collection | ❌ 2 errors | ✅ pass |
| pytest passed | 701 | **706** (+5) |
| pytest failed | 6 | **1** (baseline DB) |
| pytest errors | 20 | **20** (baseline DB) |
| vitest files failed | 26 | **5** (-21) |
| vitest tests failed | 46 | **16** (-30) |
| vitest tests passed | 533 | **608** (+75) |

## 剩余 baseline 失败 (不归 MinIO plan)

### pytest (1 fail + 20 errors)

全部 `psycopg.OperationalError: password authentication failed for user "postgres"`:
- `tests/kg/test_kg_router.py::TestTriples::test_post_empty_rows_returns_zero` — KG 测试要真 PG
- `tests/ingest/test_api.py` (18 tests) — Ingest 集成测要真 PG
- `tests/approvals/test_repo.py` (2 tests) — approvals repo 测要真 PG

**根因**: `RAG_DB_URL` 默认 `postgresql+psycopg://postgres:***@localhost:5432/rag`, 本地 dev 环境 docker PG 未启或密码错. CI 环境正常.

### vitest (16 tests)

| 模块 | 数量 | 根因 |
|------|-----|------|
| `components/chat/memory-management-dialog.test.tsx` | 8 | lucide-react mock 缺 `X` 图标 export |
| `lib/chat/memory-integration.test.ts` | 3 | memory hooks baseline |
| `app/[locale]/submissions/page.test.tsx` | 3 | RSC 路由 baseline |
| `app/[locale]/health/page.test.tsx` | 1 | RSC 路由 baseline |
| `components/common/dialog/app-dialog.test.tsx` | 1 | DOM 位置断言 (`Node.DOCUMENT_POSITION_FOLLOWING` 返回 0) |

均与 MinIO plan 无关, 各自独立 follow-up.

## 关键决策记录

- **D 集成 local backend 行为保留**: 不强推 ABC 一致性, 因为本地 mode 的核心价值是 dev 无依赖 + 测试无 MinIO server. 强行统一会让 baseline test 失效, ROI 不划算.
- **vitest shim 用独立目录 + 文件**: `test-shims/` 而非塞进 setupFiles, 因为 alias 需要 path.resolve, 必须在 resolve.alias 阶段配置.
- **Backend 判断走 store 而非 env**: 让 mock patch 完全控制行为, 避免 mock env 反复折腾. 这条适用于所有 ABC-based 代码.

## 接手者速查

- **跑测试**: `cd packages/service && uv run pytest tests/`, `cd packages/web && bun run test`
- **本地 baseline fail**: 需启 docker PG (RAG_DB_URL) + 修 lucide-react mock (跟本次 plan 无关)
- **新加 RSC 测试**: 直接 `import "server-only"` 即可, vitest alias 已配
- **新加跟 output_api 类似的 ABC-based 路由**: 用 `_backend_name() = get_object_store().backend_name()` 模式

## 关联文档

- [[2026-06-16-rag-minio-integration]] — 主 plan, 12 task 实施
- `docs/superpowers/specs/2026-06-16-rag-minio-integration-design.md` — spec
- `docs/superpowers/plans/2026-06-16-rag-minio-integration.md` — plan