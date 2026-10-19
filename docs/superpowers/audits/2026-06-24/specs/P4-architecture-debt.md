# P4 - 架构与规约债务 spec 草稿 (2026-06-24)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §D6 Architecture & Convention + SEC-001 (降级)
> 关联 checklist: [docs/audit/2026-06-24-findings.md](../../../../docs/audit/2026-06-24-findings.md)

## 范围

### 跟规约违反 (high)
- ARCH-002 — ingest/pipeline.py 47 处 print()
- ARCH-003 — os.getenv 散落 20+ 文件
- ARCH-004 — 裸 `# type: ignore`
- ARCH-005 — datetime.utcnow() + # type: ignore

### 规约违反 (medium)
- ARCH-006 — 4 处 TODO 提示加 @audited
- ARCH-007 — `any[]` 滥用
- ARCH-008 — scripts/e2e 用 console 而非 log
- ARCH-009 — package.json 用 tsc 不用 tsgo
- ARCH-010 — package.json 缺 lint:check

### 技术债 (low)
- ARCH-011 — SubmissionsTabs 53 行 useState 套层
- ARCH-012 — conftest autouse mock 缺文档

### 降级 finding
- SEC-001 (原 critical, 降 medium) — Python 2 syntax 实际不报 SyntaxError, 仍需改 `(ValueError, TypeError)`

合计 12 条 finding (含 SEC-001 降级).

## 修复策略

### Phase 1 (1-3 天) — 高收益低风险

1. **ARCH-009 (tsc → tsgo)**: `package.json:typecheck` 改 `tsgo --noEmit`, 同步 lint-staged 钩子. 性能 10x 提升, 0 风险.
2. **ARCH-010 (补 lint:check)**: package.json 加 `lint:check` + `format:check` scripts, 跟其他 script 命名风格一致.
3. **SEC-001 (Python 2 syntax)**: 改 `except (ValueError, TypeError):`, 加 `tests/auth/test_account_service.py::test_verify_password_imports` smoke test 防再犯.

### Phase 2 (1-2 周) — 类型 + 日志

4. **ARCH-004 (裸 type: ignore)**: `tests/lookups/test_audit.py:47` + `test_config.py:63` 改 `type: ignore[具体错误码]` + 注释.
5. **ARCH-005 (datetime.utcnow)**: 改 `datetime.now(timezone.utc)`, 5 处同时改, 跟 Python 3.14 deprecation 对齐.
6. **ARCH-007 (any[])**: 4 处 `lib/api/{permissions,buyer-profile}.ts` 加类型, 用 Pydantic 生成的 TypeScript 类型.
7. **ARCH-008 (console vs log)**: scripts + e2e 改用 `lib/log.ts` 封装.

### Phase 3 (持续) — 散落 + 重复清理

8. **ARCH-002 (print)**: ingest/pipeline.py 47 处 print() 改 loguru, 大型 PR.
9. **ARCH-003 (os.getenv 散落)**: 集中到 `config/settings.py` facade, 20+ 文件迁移, 拆 2-3 个 PR.
10. **ARCH-006 (@audited TODO)**: 4 处补 `@audited(...)` 装饰器, 跟 D1 SEC 一起做.
11. **ARCH-011 (SubmissionsTabs)**: 拆 <DataTable<T>> + <AppToggle> + 命名 onClick, 跟封装组件规约一致.
12. **ARCH-012 (conftest 文档)**: 在 `tests/conftest.py` 顶部加 docstring 注释 mock 矩阵 (engine/session_scope/redis/object_store/neo4j/permission_cache).

## 不在本文范围

- 实施代码 (留到 plan + implement 阶段)
- 业务功能新增
- P0/P1/P2/P3 其他维度 finding

## 验收标准

- 12 条 finding 全部 verified=true
- 后端 ruff + pyright 0 error
- 前端 oxfmt + oxlint + tsgo 0 error
- `grep -r 'print(' packages/service/src` 0 命中 (loguru 替代)
- `grep -r 'os.getenv' packages/service/src --exclude-dir=scripts` ≤ 5 命中 (config facade 集中)
- `grep -r 'function [A-Z]' packages/web/app` 0 命中 (const 声明组件)
