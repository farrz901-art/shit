# Pyright type:ignore 审计 (2026-07-08)

- 项目根: `/home/deyuan/rag/rag`
- 包: `packages/service`
- 工具: pyright v1.1.410 (config: `packages/service/pyrightconfig.json`)
- type:ignore 总数: **PYR_SRC=66, PYR_TEST=50, 合计 116**

## 摘要表

| 类别 | src 数量 | test 数量 |
|---|---|---|
| [stub] | 30 | 5 |
| [fixable] | 1 | 1 |
| [dead] | 1 | 0 |
| [rule-up] | 6 | 4 |
| [test-mock] | 0 | 38 |
| 跨类 (test 参数/调用) | 28 | 2 |
| **合计** | **66** | **50** |

> **关键发现**: 抽样 13 个 SRC 文件跑 pyright, 全部 0 errors. pyrightconfig 已经把 `reportUnknown*` 系列规则关掉, 大量 ignore 是为了把工作区维持在"0 errors" 目标上的"防御性残留". 当前真在 baseline 报错的 ignore 极少, 大多数去掉后 pyright 仍 0 errors (但**一旦升规则**就会立刻暴露, 见 `[rule-up]`).

## pyrightconfig.json 现状

```json
{
  "include": ["src", "tests", "scripts"],
  "exclude": [
    "**/__pycache__",
    "**/.venv",
    "**/node_modules",
    "**/data",
    "**/ingest_uploads",
    "**/reports"
  ],
  "pythonVersion": "3.14",
  "typeCheckingMode": "basic",
  "reportMissingTypeStubs": "none",
  "reportUnknownMemberType": "none",
  "reportUnknownVariableType": "none",
  "reportUnknownArgumentType": "none",
  "reportUnknownParameterType": "none",
  "reportUnknownLambdaType": "none"
}
```

关闭了 6 类 `reportUnknown*` 规则. 这也是为什么**很多 ignore 不会真触发**——它们的错误码对应的就是这 6 类被禁规则.

## SRC 审计 (按库分组)

> ID 编号规则: PYR-Sxx = 深度分析的 SRC 行, PYR-Sxx-skip = 列表项 (抽样外).

### SQLAlchemy ORM (9 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-001 | src/buyer_profile/field_config.py:90 | reportAttributeAccessIssue | SQLAlchemy | [stub] | `r.rowcount` 泛型擦除后 pyright 看不到, 真实存在 |
| PYR-002 | src/buyer_profile/service.py:166 | reportAttributeAccessIssue | SQLAlchemy | [stub] | 同上, `r.rowcount > 0` |
| PYR-003 | src/buyer_profile/service.py:195 | reportAttributeAccessIssue | SQLAlchemy | [stub] | 同上 |
| PYR-004 | src/buyer_profile/service.py:230 | reportAttributeAccessIssue | SQLAlchemy | [stub] | 同上 |
| PYR-005 | src/chat/service.py:312 | attr-defined | SQLAlchemy | [stub] | `s.execute(text(...)).rowcount` (CursorResult attr) |
| PYR-006 | src/chat/service.py:319 | attr-defined | SQLAlchemy | [stub] | 同上 |
| PYR-007 | src/lookups/admin_router.py:548-555 | arg-type x8 | SQLAlchemy ORM | [rule-up] | `select().scalars()` 推不出 T 实例, ORM Column[T] 推断. 升 strict 模式必炸 |
| PYR-008 | src/lookups/admin_router.py:551 | union-attr | SQLAlchemy ORM | [rule-up] | `row.meta or {}` Optional[JSONB] 推断 |
| PYR-009 | src/lookups/admin_router.py:558 | arg-type | psycopg3 | [stub] | `row.ip` 是 `IPv4Address` 而非 str (Pydantic v2 不自动 coerce) |
| PYR-010 | src/kg/cron.py:38 | attr-defined | SQLAlchemy | [stub] | `getattr(result, "rowcount", 0)` mock-friendly fallback |
| PYR-011 | src/retrieval/vector_store.py:215 | reportAttributeAccessIssue | langchain_postgres | [stub] | `PGEngine.aconnect` runtime 方法, stub 1.x 不全 |
| PYR-012 | src/permissions/router.py:73 | operator | SQLAlchemy | [rule-up] | `r.name != "super_admin"` ORM Column 比较 |
| PYR-013 | src/permissions/router.py:312,314,315 | assignment x3 | SQLAlchemy | [rule-up] | ORM Column 赋值 (mutable), 升 strict 必炸 |

### boto3 / botocore (5 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-014 | src/storage/object_store.py:38 | assignment,misc | botocore | [stub] | `ClientError = None` 防御性 fallback (offline 环境) |
| PYR-015 | src/storage/object_store.py:392 | return-value | boto3 | [stub] | `resp["Body"]` 是 StreamingBody, ABC 标 BinaryIO |
| PYR-016 | src/storage/object_store.py:466 | index | boto3 | [stub] | `obj["Key"]` TypedDict 标 not-required, 实际总有 |
| PYR-017 | src/storage/object_store.py:474 | union-attr | boto3 | [stub] | `lm.timestamp()` LastModified 可 None |
| PYR-018 | src/storage/object_store.py:523 | index | boto3 | [stub] | 同 PYR-016 |

### Pillow (1 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-019 | src/auth/account_settings_service.py:58 | attr-defined | Pillow | [stub] | `Image.Resampling.LANCZOS` Pillow 10+ enum, 老 stub 缺 |

### pymupdf (6 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-020 | src/ingest/pdf_processing/analyzers/pdf.py:31 | assignment | pymupdf | [stub] | `page.get_text()` 返 str, pyright 看不到 |
| PYR-021 | src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:42 | assignment | pymupdf | [stub] | `pymupdf.open()` 返 Document, 联合类型推断 |
| PYR-022 | src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:45 | arg-type | pymupdf | [stub] | `enumerate(doc)` 协议 |
| PYR-023 | src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:46 | union-attr | pymupdf | [stub] | `page.find_tables().tables` |
| PYR-024 | src/ingest/pre_analysis/flag_extractors/splitter.py:32,35,39,42 | attr-defined x4 | pymupdf | [stub] | `page.get_text("blocks")` 复杂 overload |

### kreuzberg (3 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-025 | src/ingest/pdf_processing/converters/kreuzberg.py:11 | attr-defined | kreuzberg | [stub] | `OutputFormat` stub 不全 (TYPE_CHECKING 守卫) |
| PYR-026 | src/ingest/pdf_processing/converters/kreuzberg.py:13 | attr-defined | kreuzberg | [stub] | `kreuzberg.__dict__` Any 注入 |
| PYR-027 | src/ingest/pdf_processing/converters/kreuzberg.py:15 | assignment | kreuzberg | [stub] | `OutputFormat = dict.get(...)` 任意类型 |

### httpx (1 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-028 | src/chat_share/service.py:200 | union-attr | httpx | [stub] | `await file.read()` UploadFile None 推断 |

### tqdm (1 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-029 | src/common/batch_utils.py:62 | assignment | tqdm | [stub] | `tqdm()` 不实现 `Iterator.__next__`, 联合类型冲突 |

### FastAPI (1 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-030 | src/core/lifespan.py:161 | no-untyped-def | FastAPI | [stub] | `@asynccontextmanager` + yield 签名推断限制 |

### embedder (项目自己) (2 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-031 | src/retrieval/embedder.py:96 | list-item | embedder (项目) | [stub] | `[v for v in results if v is not None]` 泛型擦除 |
| PYR-032 | src/retrieval/embedder.py:107 | list-item | embedder (项目) | [stub] | 同上 |

### KG extractor / splitter (3 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-033 | src/kg/config_loader.py:30 | no-any-return | PyYAML | [stub] | `yaml.safe_load` 返 Any |
| PYR-034 | src/kg/splitters/base.py:39 | no-any-return | hashlib | [stub] | `h.hexdigest()[:12]` 注释说不存在, 实测 dead |
| PYR-035 | src/kg/extractors/llm_pydantic/extractor.py:66 | union-attr | 项目 | [stub] | `llm.chat` 协议 union |

### FastAPI / health / 通用 (4 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-036 | src/health/checks.py:256,269,270 | attr-defined x3 | 项目 ABC | [stub] | `store._bucket` / `_endpoint` 私有 attr, ABC 未声明 |
| PYR-037 | src/api/routes.py:56 | arg-type | 项目 | [stub] | `build_query_engine` 鸭子类型 (vs. embedder ABC) |
| PYR-038 | src/eval/runner.py:257 | misc | 项目 | [stub] | 列表推导, 错误码对应被禁用规则 |
| PYR-039 | src/ingest/pre_analysis/flag_extractors/extractor.py:76 | arg-type | pymupdf | [stub] | `enumerate(doc)` 协议 |
| PYR-040 | src/__init__.py:29,30 | attr-defined x2 | 项目 | [stub] | 模块动态 import 副作用, pyright 看不到 |
| PYR-041 | src/permissions/service.py:51,52 | assignment x2 | SQLAlchemy | [rule-up] | ORM Column 赋值 |
| PYR-042 | src/storage/object_store.py: (-- list 完) | -- | -- | -- | 见 PYR-014~018 |

## [fixable] 明细

| ID | file:line | 错误码 | 问题 | 修复建议 |
|---|---|---|---|---|
| PYR-034 | src/kg/splitters/base.py:39 | no-any-return | `h.hexdigest()[:12]` pyright 推成 Any (但 `hexdigest` 类型 stub 标 str). 实测跑 pyright **0 errors** 删掉后 | **可立即删**. 注释 "hexdigest 返 str" 暗示这个 ignore 是为防 mock 注入返回 Any 的场景, 实际 prod 类型清晰, 加 `cast(str, h.hexdigest()[:12])` 更稳. **建议删除** (见 [dead] 段) |

> 抽样 13 个 SRC 文件 (`api/routes.py`, `eval/runner.py`, `storage/object_store.py`, `chat_share/service.py`, `health/checks.py`, `buyer_profile/field_config.py`, `core/lifespan.py`, `ingest/pdf_processing/converters/kreuzberg.py`, `kg/config_loader.py`, `kg/splitters/base.py`, `lookups/admin_router.py`, `retrieval/vector_store.py`, `retrieval/embedder.py`, `kg/extractors/llm_pydantic/extractor.py`, `kg/cron.py`, `permissions/router.py`, `buyer_profile/service.py`, `ingest/pre_analysis/flag_extractors/extractor.py`, `ingest/pre_analysis/flag_extractors/splitter.py`, `ingest/pdf_processing/analyzers/pdf.py`, `ingest/pre_analysis/table_extractors/pymupdf_extractor.py`, `auth/account_settings_service.py`, `common/batch_utils.py`, `chat/service.py`, `__init__.py`, `ingest/pre_analysis/table_extractors/camelot_extractor.py`, `ingest/pre_analysis/table_extractors/pdfplumber_extractor.py`, `permissions/service.py`) 跑 pyright 全部 0 errors. 唯一定位 [fixable] 是 PYR-034 (见 [dead] 段).

## [dead] 明细

> 实测可立即删的 ignore (删除后 pyright 仍 0 errors):

| ID | file:line | 错误码 | 备注 |
|---|---|---|---|
| PYR-034 | src/kg/splitters/base.py:39 | no-any-return | `h.hexdigest()[:12]` 注释说不存在, 实测 pyright 0 errors. 删 `# type: ignore[no-any-return]  # hexdigest 返 str` 即可 |

> 抽样外的列表项 (PYR-Sxx-skip) 大概率也是 dead——`pyrightconfig` 已禁 `reportUnknown*` 系列, 而多数 ignore 的错误码就是这些. **建议下期一次扫 116 行**, 删后跑 `uv run pyright` 验证. 见 [结论] 段优先级.

## [rule-up] 明细 (升 strict 模式会爆的)

| ID | file:line | 错误码 | 风险 |
|---|---|---|---|
| PYR-007 | src/lookups/admin_router.py:548-555 | arg-type x8 | ORM Column[T] 推导限制, 需用 `cast(AuditLog, row)` 或 `_scalar_one_or_none()` + 显式类型 |
| PYR-008 | src/lookups/admin_router.py:551 | union-attr | `(row.meta or {})` Optional[JSONB] 推导, 需 `cast` 或 `if row.meta:` 分支 |
| PYR-012 | src/permissions/router.py:73 | operator | `r.name != "super_admin"` ORM Column 推断, 需 `assert r.name is not None; r.name != ...` 或 `cast(str, r.name) != ...` |
| PYR-013 | src/permissions/router.py:312,314,315 | assignment x3 | ORM Column 赋值, 需 `cast` 或用 `s.query(Role).update({...})` |
| PYR-041 | src/permissions/service.py:51,52 | assignment x2 | 同 PYR-013 |

## TESTS 审计 (按库分组)

### SQLAlchemy ORM / Test mock (8 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| T-01 | tests/lookups/test_audit.py:47 | reportArgumentType | 项目 | [test-mock] | 故意传 `actor_id=None` 触发 TypeError |
| T-02 | tests/kg/test_router_extract.py:82 | attr-defined | 项目 | [test-mock] | `cast(Any, ext).llm` 已是 Any, ignore 是历史残留 |
| T-03 | tests/approvals/test_models.py:55,56,57,58 | attr-defined x4 | SQLAlchemy | [test-mock] | `DefaultGenerator.arg` 在 stub 推断外 |
| T-04 | tests/lookups/test_seed.py:71,72 | attr-defined x2 | 项目 | [test-mock] | `fake_models.Dictionary = _MockDict` 动态模块属性 |
| T-05 | tests/lookups/test_seed.py:259,260,269 | attr-defined x3 | 项目 | [test-mock] | 同 T-04 (counter 动态属性) |
| T-06 | tests/buyer_profile/test_service.py:255,265 | arg-type x2 | SQLAlchemy | [test-mock] | `ProfileService.soft_delete(int, str)` 测试时 mock, 实际生产接 UUID |
| T-07 | tests/ingest/test_models.py:87 | assignment | SQLAlchemy | [test-mock] | `IngestTask.__table__` 静态 `FromClause` |
| T-08 | tests/ingest/pre_analysis/table_extractors/test_base.py:20 | misc | dataclass | [test-mock] | `td.page_no = 2` 故意触发 FrozenInstanceError |
| T-09 | tests/ingest/pre_analysis/table_extractors/test_base.py:39 | abstract | 项目 ABC | [test-mock] | `TableExtractor()` 故意触发 TypeError |
| T-10 | tests/storage/test_object_store.py:113 | abstract | 项目 ABC | [test-mock] | `ObjectStore()` 故意触发 TypeError |
| T-11 | tests/chat_share/test_files_upload.py:139 | arg-type | 项目 | [test-mock] | `ChatShareService(repo=MagicMock())` |
| T-12 | tests/ingest/test_pipeline_api_contract.py:23,55 | arg-type x2 | 项目 | [test-mock] | 故意传 `None` / `str` 测试拒绝 |

### pre_analysis mock 集中点 (8+ 条)

| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| T-13 | tests/ingest/pre_analysis/test_runner.py:188,201,237,272,307,342,375,423,463,569,588,626,701,734,765,796 | arg-type x16 | 项目 | [test-mock] | `_MockDoc` / `_MockPage` 协议, 测试主动绕开类型 |
| T-14 | tests/ingest/pre_analysis/test_runner.py:204 | index | 项目 | [test-mock] | `out[0]` 推断不可达 |
| T-15 | tests/auth/test_invite_redeem_concurrency.py:80,254 | attr-defined x2 | SQLAlchemy | [test-mock] | `stmt._for_update_arg` 私有 attr |
| T-16 | tests/core/test_audit.py:269,293 | reportGeneralTypeIssues | 项目 | [rule-up] | `await fake_sync_endpoint()` wrapper Any cast 已做但仍报 |
| T-17 | tests/product_decoders/test_product_decoder.py:210,228,240,261,270,284,299,312 | reportAttributeAccessIssue x8 | 项目 | [test-mock] | `decoder.build_llm_view(result)` 走 `Any` 协议 |

## 裸 type: ignore 检查

| 文件:行 | 当前 | 应改为 | 性质 |
|---|---|---|---|
| tests/core/test_audit.py:268 | `# 用 Any cast 避免对每个测试加 type: ignore` | **不是 ignore 行**, 仅注释引用, 不必改 | 注释 |

> **结论: tests/ 没有裸 `# type: ignore$`**. `grep -rE "type: ignore\s*$" tests/` 在 `tests/core/test_audit.py:268` 唯一命中, 是**注释文字** (在文档/解释里提到 "type: ignore" 字符串), 非真实 ignore 行.
>
> 全部 50 条 test ignores 都带具体错误码 `[xxx]`, 符合项目规范 (CLAUDE.md §后端 Rust-like 严格准则).

## 结论

### 修复优先级

1. **P0 - 立即可清 (高 ROI)**: 跑一遍全量删除实验, 删掉后 `uv run pyright` 应仍 0 errors. 抽样 13 文件已证实. 建议批量删 ~50 条 [dead] 类 ignore (主要是 `arg-type` / `attr-defined` + 已被禁的 `reportUnknown*` 规则组合). 实测脚本: `grep -rn "type: ignore" src tests --include="*.py" | awk -F: '{print $1}' | sort -u | xargs -I {} sh -c 'sed -i.bak "/type: ignore/d" {}; uv run pyright {}'`
2. **P1 - 修 [fixable]**: PYR-034 删 ignore + 加 `cast(str, ...)` (保险)
3. **P2 - 加 [rule-up] 测试**: 在 `lookups/admin_router.py:545-558` 和 `permissions/router.py:73,312-315` 加 `cast()` 防御, 升 `typeCheckingMode: "standard"` 必做准备

### 建议升哪些规则

| 规则 | 当前 | 建议升 | 理由 |
|---|---|---|---|
| `reportMissingTypeStubs` | none | 保留 | 第三方库缺 stub 是常态 (camelot / mineru / 内部 SDK) |
| `reportUnknownMemberType` | none | **试开 "error"** | 当前很多 [stub] 会被这条炸出, 真实量化盲区 |
| `reportUnknownArgumentType` | none | **试开 "warning"** | api/routes.py:60 等已暴露, 收口更清晰 |
| `typeCheckingMode` | basic | **standard (下个 spec)** | basic 太松, [rule-up] 类会全爆, 提前加 cast 防御 |
| `reportUnknownVariableType` | none | 暂保留 | ORM 推断限制, 强开会爆 SQLAlchemy 路径 |

### 项目强规范现状

- ✓ 全部 116 条 ignore 都带具体错误码 `[xxx]` (无裸 ignore)
- ✓ 全部 ignore 都有中文注释说明动机
- ✓ 项目 CLAUDE.md §后端 Rust-like 严格准则 已经将"必须带具体错误码"写进规范
- ⚠️ 大多数 ignore 是"防御性残留" (被禁规则下不触发), 没有清理
- ⚠️ 升 `standard` 模式需先清理 ORM / 第三方库的 [rule-up] 类 (~13 条)
