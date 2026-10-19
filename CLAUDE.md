# 项目代码质量铁律 (2026-06-19)

> 本文件由 [code-quality-cleanup spec](docs/superpowers/specs/2026-06-19-code-quality-cleanup-design.md) 沉淀.
> 任何 commit / PR 改动前必读. 跟 [.claude/CLAUDE.md](.claude/CLAUDE.md) 项目级配置配套使用.

## 工具链一览 (锁版本, 不升级)

### 后端 (Python 3.14)

- **format**: `uv run ruff format` (0 exit = 通过)
- **lint**: `uv run ruff check --fix` (自动修) / `uv run ruff check` (只读)
- **类型**: `uv run pyright` (必须 0 error 才 commit; 当前 basic 模式)
- **测试**: `uv run pytest` (~1075 tests pass; 22 fail + 38 errors pre-existing 见 [packages/service/KNOWN_ISSUES.md](packages/service/KNOWN_ISSUES.md))
- **覆盖率**: `uv run pytest` 自动带 coverage (term + html + lcov), 起始基线 **74.1% lines**

### 前端 (TypeScript 8 / React 19 / Next.js)

- **format**: `bun run format` (oxfmt --write)
- **lint**: `bun run lint:fix` (oxlint --fix) / `bun run lint` (只读)
- **类型**: `bun run typecheck` (tsc --noEmit, 必须 0 error)
- **测试**: `bun run test` (719 tests passed) / `bun run test:coverage` (带覆盖率)
- **覆盖率**: `@vitest/coverage-v8`, v8 provider, html/lcov 报告, 起始基线 **66.75% lines**

## 顺序不可颠倒

任何代码改动必须按顺序:

1. **format** → 0 报错
2. **lint fix** → 0 报错
3. **类型检查** → 0 error
4. **测试** → 0 新 fail (pre-existing fail 不算新 fail)
5. **commit** (commit message 前缀: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:`)

跳过任何一步都不行. husky pre-commit 钩子会自动跑 lint-staged + tsc + vitest + format:check.

## 范围控制

- 单次 `--fix` 改 > 500 行 → **停下来问用户 review**
- pre-existing test fail → 列 `KNOWN_ISSUES.md`, 不雪崩修
- 别人 worktree 的 stash 残留 → **不 reset / 不 checkout** (会丢别人工作)

## 后端 Rust-like 严格准则

- ruff 警告不允许绕过 (`# noqa` 必须带具体错误码 + 注释)
- pyright 必须 0 error (`# type: ignore` 必须带具体错误码 + 注释)
- 测试必须 mock, **不连真 PG/Redis** (项目老规范, 见 [packages/service/CLAUDE.md §测试隔离 4 模式](packages/service/CLAUDE.md))
- alembic migration 可回滚 (downgrade 干净)
- audit log 走 `@audited` 装饰器 (DELETE / 改账户 / 改权限 / 导出数据)
- 业务 enum 必须走 lookup 字典模块, 禁止新增硬编 `StrEnum`

## 前端 React/Next.js 准则

- oxfmt + oxlint 必须 0 error
- tsc 必须 0 error
- 优先用项目封装 (DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form / FormField)
- i18n: `t("中文 key")` 中间用中文作 key, zh.json identity, en.json 翻译
- **路由跳转必须用 `@/i18n/navigation` 的 useRouter** (禁止 `next/navigation` 的, 强制 locale 前缀)
- JSX 不写行内 `onClick={() => {}}` 复杂表达式, 提取命名函数

## 不要做的事

- ❌ 写 `useState` 套 5 层的 hook 而不抽封装
- ❌ 直接 import 第三方 UI 库 (shadcn/ui 已经按需装, 用项目封装)
- ❌ 改前端 URL 顺序: 先 BFF 改 → 后端改 → 前端改 (不可逆, 见 [.claude/CLAUDE.md §重构规则](.claude/CLAUDE.md))
- ❌ 删 BFF route 不跑契约测试 (`pytest tests/test_api_contract.py`)
- ❌ 新增 `StrEnum` 不走 lookup (字典唯一事实源, 见 [packages/service/src/lookups/README.md](packages/service/src/lookups/README.md))
- ❌ 连真 PG/Redis 跑测试 (项目老规范)
- ❌ 覆盖别人工作树残留 (用 `git stash list` 确认, 不动)

## 测试模式 (4 模式)

后端测试, 按用途选:

1. **模式 1 (mock)**: ORM 字段 / Pydantic / 纯函数 / util — `unittest.mock.patch`, 0 PG 依赖
2. **模式 2 (db_session)**: 集成测, repo CRUD / SQL / FK — `db_session` fixture 事务回滚
3. **模式 3 (tmp_pg_schema)**: 迁移 DDL / schema 完整性 — 临时 schema
4. **模式 4 (E2E)**: 完整业务流 — `PG_*` env 指向独立 DB

详细见 [packages/service/CLAUDE.md §测试隔离 4 模式](packages/service/CLAUDE.md).

前端测试:

- 单元: vitest + jsdom (已有 setup, `vitest.config.ts`)
- 组件: vitest + @testing-library/react
- E2E: Playwright (`packages/web/e2e/` 目录, `playwright.config.ts`)

## 强制测试隔离 (2026-06-19 phase2)

- **所有 test 禁止直连 PG/Redis/Neo4j**。必须 mock session_scope / get_redis / get_neo4j
- 集成测试标记 `@pytest.mark.integration`，CI 默认 skip（`-m "not integration"`)
- CI 覆盖率门禁: 待 phase3 加 thresholds (当前 `--cov-fail-under=0` 仅采集)

## 测试运行避坑 (2026-07-08 沉淀)

跑后端 `uv run pytest` 反复撞 3 个错, 加铁律避免重犯:

1. **必须 `cd packages/service`** — `uv run` 读当前目录的 `pyproject.toml` + `.venv` 找 pytest.
   仓库根跑立即报 `Failed to spawn: pytest (No such file or directory)` exit 0, 看起来"没结果".
   - ✅ 永远 `cd /home/deyuan/rag/rag/packages/service && uv run pytest ...`
   - ❌ 在仓库根跑 `uv run pytest` (没 cd)

2. **重定向必须配 cd** — `uv run pytest 2>/tmp/pw.txt 1>/tmp/po.txt` 单独写不 cd → 文件 0 字节 (命令立即报 uv 错, 没进 pytest).
   - ✅ 整条命令同一行带 `cd`: `cd packages/service && uv run pytest ... 2>pw.txt`
   - ❌ 拆成两步: 先 `cd` 在 background task, 后写 pytest, CWD 不持久

3. **大输出会超 buffer** — 1k+ test 跑全量时 30k+ 行 (含 warning 路径 + traceback), Bash 截断后像"没结果".
   - ✅ 跑过的用 `Read` 读 /tmp/pytest-stdout.txt 找具体行, 不重跑
   - ✅ 验证性测试只跑单文件 (`uv run pytest tests/foo/test_x.py`), 1.x 秒, 不重跑全量
   - ❌ 看输出空就重跑 5 分钟的全量

**开发循环**: 单文件跑 (`tests/foo/test_x.py`) → 修 → 单文件再跑 → 绿 → 改下一个. **只在最终 commit 前**跑全量 1 次. (跟 [.claude/CLAUDE.md §测试效率](.claude/CLAUDE.md) 一致)

**Why**: 2026-07-08 inline 修 18 fail + 2 warnings + 1 filter config, 误判"pytest 还在跑"重试 3 次, 单次就够的验证被多花 10-15 分钟.
**How to apply**: 任何 `uv run pytest` / `bun run test` 跑前先确认 (a) CWD 是 `packages/service` 或 `packages/web` (b) 不写文件重定向除非整条命令同 cd (c) 验证只跑改过的文件, 不重跑全量.

## 关联文档

- 项目 Claude 配置: [.claude/CLAUDE.md](.claude/CLAUDE.md)
- 后端局部约定: [packages/service/CLAUDE.md](packages/service/CLAUDE.md)
- 前端局部约定: [packages/web/CLAUDE.md](packages/web/CLAUDE.md)
- Spec / Plan: `docs/superpowers/specs/` + `docs/superpowers/plans/`
- 教程: `docs/cookbook/`
- 已知问题: [packages/service/KNOWN_ISSUES.md](packages/service/KNOWN_ISSUES.md) (后端 pre-existing)
