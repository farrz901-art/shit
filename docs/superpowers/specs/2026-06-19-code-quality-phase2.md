# 代码规范 Phase 2: Test Isolation + Oxlint 清零 + Coverage 门禁 + GitHub CI

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：以 `c:/doc/Code/rag` 仓库 `code-quality-2026-06-19` 分支 (bed26fd) 为基准
> 🎯 范围：把 code-quality handoff 遗留的 3 大问题 + CI 一次性解决

---

## 一、目标 & 整体架构

**目标**：handoff 3 大遗留问题 + GitHub CI 一次性解决，沉淀为"测试强制 mock + 前端零 lint warning + CI 覆盖率门禁"的新代码规范。

**5 个阶段（顺序依赖）**：

```
Phase A (Test Isolation) ── 全部 mock, 0 真连接
  ↓
Phase B (Oxlint) ──── 3412 warning → 0, 不改规则, 优先箭头函数, 常量放 const/
  ↓
Phase C (Coverage) ── 后端 80%, 前端 75%
  ↓
Phase D (CI) ──────── .github/workflows/ci.yml, 先报告后门禁
  ↓
Phase E (CLAUDE.md) ─ 3 个文件 append 新规范
```

**Phase A → B → C 不可颠倒**（CI 从第一天不红），D 可以跟 C 并行，E 最后。

| Phase | 内容 | 估算 |
|-------|------|------|
| A | 30+ test 文件 mock 改造 + 22 fail 0 errors | 20-30h |
| B | 200+ 前端文件修 3412 warning | 16-24h |
| C | 补测试到后端 80% / 前端 75% | 10-16h |
| D | GitHub CI yml + 配置 | 2h |
| E | CLAUDE.md append 新规范 | 1h |
| **总计** | **~250 文件** | **~48-72h** |

---

## 二、Phase A: Test Isolation

### A.1 问题分析

当前 51 个 test 文件涉及 DB 连接，分 3 种模式：

| 模式 | 文件数 | 典型 | 问题 |
|------|--------|------|------|
| **模式 1 (mock)** | ~20 个 | test_csv_storage.py patch session_scope | 0 真连接 ✅ |
| **模式 2 (db_session)** | ~5 个 | tests/integration/ 下 | 事务回滚，有真连接 |
| **真连 PG (坏)** | **~30 个** | TestClient 调 router → resolve_user → engine | **22 fail + 38 errors 全部来自这** |

### A.2 改造策略

**核心思路**：让 TestClient 不走真 engine。不在 src 代码加 mock（不改业务逻辑），只在 test 层加 monkeypatch/fixture。

```
改造前:
  TestClient → router → resolve_user → session_scope → engine.connect() → PG

改造后:
  TestClient → router → resolve_user → session_scope → MagicMock() → 0 真连接
```

### A.3 30 个 TestClient 文件分类

| 类 | 数量 | 典型文件 | 改造方式 |
|----|------|---------|---------|
| **auth 类** | 10 | test_login.py, test_auth_cookie.py, test_invite_flow.py 等 | mock `resolve_user` 返假 CurrentUser + mock `session_scope` |
| **router 类** | 12 | eval/test_router.py, memory/test_router.py, kg/test_router.py 等 | mock `session_scope` + `get_object_store` + `get_redis` |
| **integration 类** | 8 | test_db_session_fixture.py, test_rbac_e2e.py 等 | 改标记 `@pytest.mark.integration` CI 默认 skip，不 mock |

### A.4 核心 fixture 方案

在 `tests/conftest.py` 加：

```python
@pytest.fixture(autouse=True)
def mock_all_db_connections(monkeypatch):
    """全自动 mock: 每个 test 跑前 mock 所有 DB/Redis/Neo4j 连接.

    避免任何 test 意外直连 PG/Redis/Neo4j.
    业务代码用 session_scope() 时拿到 MagicMock, 不走真 engine.
    """
    from src.storage import session_scope
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_scope = MagicMock()
    mock_scope.__enter__.return_value = mock_session
    mock_scope.__exit__.return_value = False

    monkeypatch.setattr("src.storage.engine._engine", None)  # 关真 engine
    monkeypatch.setattr("src.storage.session.session_scope", lambda: mock_scope)
    # Redis / Neo4j 类似

    # 注意: 对于显式想要 mock 的 test, 可以 override
```

### A.5 已知风险

| 风险 | 缓解 |
|------|------|
| TestClient 的 `resolve_user` 依赖 PG 查 account | monkeypatch `resolve_user` 返假 CurrentUser |
| 有些 test 用 `with session_scope() as s: s.query(...)` 真查数据 | mock 后返空列表/预设数据 |
| integration test 用 `db_session` fixture 依赖真事务 | 标记 `@pytest.mark.integration` CI 跳过 |

### A.6 验收标准

- [ ] `uv run pytest` 0 fail + 0 errors
- [ ] `uv run pytest --no-header -q` 输出只有 passed + skipped（无 failed/errors）
- [ ] 后端 test 启动不依赖 docker PG 启动
- [ ] `KNOWN_ISSUES.md` 删掉 22 fail + 38 errors 行（清零）

---

## 三、Phase B: Oxlint Warning 清理

### B.1 3412 warning 分类

| 规则 | 数量 | 典型修复 | 难度 |
|------|------|---------|------|
| `id-length` | 754 | `v` → `val`, `i` → `idx`, `e` → `err` | 🟢 机械替换 |
| `no-magic-numbers` | 703 | 提取命名常量到 `const/index.ts` | 🟡 需理解语义 |
| `sort-imports` | 546 | import 行按字母重排 | 🟢 自动修复 |
| `func-style` | 456 | `function foo(){}` → `const foo = () => {}` | 🟢 机械替换 |
| `no-ternary` | 353 | `a ? b : c` → if/else | 🟡 需理解 |
| `max-statements` | 79 | 函数拆小 | 🔴 需重构 |
| `new-cap` | 63 | 构造函数首字母大写 | 🟢 简单 |
| `init-declarations` | 33 | 变量声明时初始化 | 🟡 |
| `no-shadow` | 28 | 变量名冲突改名 | 🟡 |
| 其他 (11 规则) | ~150 | 各种风格 | 🟢~🟡 |

### B.2 修复策略

**不改 `.oxlintrc.json`**，逐规则修复，从易到难：

1. **批量自动修**：`sort-imports` (546) + `new-cap` (63) + `no-duplicate-imports` (23) 等 → 跑 `oxlint --fix`
2. **机械替换**：`func-style` (456) → `function foo(){}` → `const foo = () => {}`（React 组件 default export 保留 `export default function`）
3. **机械替换**：`id-length` (754) → 单字符变量改全名（`v→val`, `i→idx`, `e→err`）
4. **语义理解**：`no-magic-numbers` (703) → 每个数字提取命名常量放 `packages/web/const/index.ts`，已有 `export const ZERO = 0`
5. **语义理解**：`no-ternary` (353) → 三元改 if/else 分支
6. **重构**：`max-statements` (79) + `max-params` (3) → 函数拆分

### B.3 STOP 条件

每跑 500 行改动停下报告（跟 code-quality P0 同样的规则）。

### B.4 风险

- `func-style` 改 456 个：React 组件 `export default function Component()` 不能改 `export default const`，必须单独处理
- `no-magic-numbers` 703 处：0/1/-1 在一些场景改常量反而降低可读性（如 `arr[0]`），需合理判断
- `no-ternary` 353 处：JSX 里三元常见，提取成变量比改成 if/else 更合理

### B.5 验收

- [ ] `bun run lint` 0 warning + 0 error
- [ ] `bun run test` 719/719 passed（不引入回归）
- [ ] `bun run typecheck` 0 errors

---

## 四、Phase C: Coverage 补测试

### C.1 现状差距

| 维度 | 当前 | 目标 | 差距 |
|------|------|------|------|
| **后端 Lines** | 74.1% | 80% | **+6%** (~440 stmts) |
| 后端 Branches | ~70% | 70% | 接近 |
| **前端 Lines** | 66.75% | 75% | **+13%** (~360 stmts) |
| 前端 Branches | 56.76% | 65% | **+8%** |

### C.2 后端补测策略

跑 `coverage report --show-missing --skip-covered` 看哪些模块最低，逐模块补：
- 对每个覆盖率 < 70% 的模块，补充核心路径 + 异常路径测试
- 不追求 100%（边际效益递减），80% 足够
- 优先补业务逻辑（src/），不补 migration / __init__ / 配置代码

### C.3 前端补测策略

跑 `bun run test:coverage` 看 missing lines：
- 优先补 hooks/ 和 components/common/
- 其次补 lib/ 下 utils / api 封装
- 不补 pages 的 RSC 测试（测试成本高）

### C.4 验收

- [ ] `uv run pytest --cov=src --cov-fail-under=80` → exit 0
- [ ] `bun run test:coverage` 输出 Lines ≥ 75%

---

## 五、Phase D: GitHub CI

### D.1 Workflow 结构

`.github/workflows/ci.yml`，两 job 并行（后端 + 前端）：

```yaml
name: CI

on:
  push:
    branches: [master, "code-quality-*"]
  pull_request:
    branches: [master]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg18
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: rag_test
        ports: [5432/tcp]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: [6379/tcp]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff format --check .
      - run: uv run ruff check .
      - run: uv run pyright
      - run: uv run alembic upgrade head
        env:
          RAG_DB_URL: postgresql+psycopg://postgres:postgres@localhost:${{ job.services.postgres.ports[5432] }}/rag_test
      - run: uv run pytest --cov=src --cov-report=term --cov-fail-under=0
        env:
          RAG_DB_URL: postgresql+psycopg://postgres:postgres@localhost:${{ job.services.postgres.ports[5432] }}/rag_test

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install
        working-directory: packages/web
      - run: bun run format:check
        working-directory: packages/web
      - run: bun run lint
        working-directory: packages/web
      - run: bun run typecheck
        working-directory: packages/web
      - run: bun run test
        working-directory: packages/web
      - run: bun run test:coverage
        working-directory: packages/web
```

### D.2 关键设计点

| 点 | 设计 |
|----|------|
| **PG 服务** | CI 启真实 PostgreSQL + pgvector（不是 mock）。test DB 名 `rag_test` 跟 dev DB `rag` 隔离 |
| **Redis 服务** | CI 启真 Redis，用于 token cache + rate limiter 测试 |
| **覆盖率门禁** | 初始 `--cov-fail-under=0`（不阻断），Phase C 完成后改为 80 |
| **并行** | 后端 + 前端并行跑，总时间 ~5-8 分钟 |
| **alembic migrate** | CI 跑 `alembic upgrade head` 建表，确保 migration 可执行 |
| **排除** | Neo4j 不在 CI 跑（无真 Neo4j），kg 测试标记 skip |

### D.3 跟 Phase A 的关系

Phase A 把所有 test 改成 mock 后，CI 不需要 PG/Redis 也能跑大部分 test。但 CI 有真 PG 可以跑集成测试（`db_session` fixture），两全其美。

---

## 六、Phase E: CLAUDE.md 沉淀

### E.1 涉及文件

- `CLAUDE.md`（项目根）— append「新阶段规范」段
- `packages/service/CLAUDE.md` — append「测试强制 mock + coverage 门禁」段
- `packages/web/CLAUDE.md` — append「零 lint warning + 常量规范 + coverage 门禁」段

### E.2 新规范内容

**项目根 CLAUDE.md** 追加：

```markdown
## 强制测试隔离 (2026-06-19 phase2)

- **所有 test 禁止直连 PG/Redis/Neo4j**。必须 mock session_scope / get_redis / get_neo4j
- 集成测试标记 `@pytest.mark.integration`，CI 默认 skip
- CI 覆盖率门禁: 后端 80% lines / 70% branches, 前端 75% lines / 65% branches (phase3 加)
```

**packages/service/CLAUDE.md** 追加：

```markdown
## 测试隔离强制规范 (2026-06-19 phase2)

- 写新 test 前必须选 4 模式，默认走模式 1 (mock)
- 禁止任何 TestClient 测试直连 PG/Redis/Neo4j
- 集成测试必须显式 `@pytest.mark.integration`，否则 CI 自动跳过
- 跑 test 不需要 docker PG/Redis 启动
```

**packages/web/CLAUDE.md** 追加：

```markdown
## 零 lint warning 规范 (2026-06-19 phase2)

- `bun run lint` 必须 0 warning + 0 error
- 函数声明用 `const Component = () => {}`，禁止 `function Component(){}`
  (React 组件 default export 例外: `export default function Page(){}`)
- 魔法数字必须提取到 `const/index.ts` 作为命名常量
- 变量名禁止单字符 (val 替代 v, idx 替代 i)
- import 按字母排序
- 三元表达式禁止，改用 if/else
```

### E.3 验收

- [ ] 3 个 CLAUDE.md 都含「phase2 新规范」段
- [ ] 规范跟 Phase A/B/C 实际做的一致（不写做不到的规则）

---

## 七、范围外

- ❌ 不改 `.oxlintrc.json`（用户确认硬修）
- ❌ 不升级任何工具版本
- ❌ 不做 E2E 测试补充
- ❌ 不写 Playwright E2E CI job（后续 spec）
- ❌ 不改 BFF 路由 / 前端 URL 顺序
- ❌ 不改数据库表结构
- ❌ 不修 Neo4j / MinIO 集成测试（标 skip）
