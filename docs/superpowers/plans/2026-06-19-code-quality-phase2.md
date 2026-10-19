# Code Quality Phase 2 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test isolation (全部 mock 0 真连接) + Oxlint 3412 warning 清零 + Coverage 补到 80%/75% + GitHub CI + CLAUDE.md 沉淀。

**Architecture:** 5 个阶段顺序执行 A→E，A (test isolation) 先让 pytest 全绿，B (oxlint) 再让前端 lint 全清，C 补覆盖率，D 写 CI，E 沉淀规范。

**Tech Stack:** Python 3.12 / FastAPI / pytest + pytest-cov / ruff / pyright / Redis fakeredis / TypeScript 8 / React 19 / oxlint / tsgo / vitest + @vitest/coverage-v8 / GitHub Actions

**Spec:** `docs/superpowers/specs/2026-06-19-code-quality-phase2.md`

---

## File Structure

本 plan 涉及文件：

### Phase A - Test Isolation
- **创建**:
  - `packages/service/tests/conftest.py` — 全局 `mock_all_db_connections` fixture
  - `packages/service/tests/helpers.py` — mock CurrentUser 工厂
- **修改**: 30+ test 文件 (mock 改造, 见各 task 清单)
- **修改**: `KNOWN_ISSUES.md` — 清零后删除 22 fail + 38 errors 行

### Phase B - Oxlint Warning
- **创建**: `packages/web/const/index.ts` (扩充, 已有 `ZERO`)
- **修改**: 200+ 前端文件 (修 3412 warning, 按规则分批)

### Phase C - Coverage
- **创建**: 后端 + 前端新 test 文件 (按 coverage report missing lines 决定)
- **修改**: 现有 test 文件 (补充断言)

### Phase D - CI
- **创建**: `.github/workflows/ci.yml`

### Phase E - CLAUDE.md
- **修改**: `CLAUDE.md` + `packages/service/CLAUDE.md` + `packages/web/CLAUDE.md`

---

## 任务依赖关系

```
Phase A (test isolation, 必须第一)
  ├── Task A1: conftest.py + helpers 基建
  ├── Task A2: auth 类 10 个 test 文件 mock
  ├── Task A3: router 类 12 个 test 文件 mock
  ├── Task A4: integration 类标记 skip
  ├── Task A5: 验收 0 fail 0 errors + 更新 KNOWN_ISSUES.md
  │
  ├── Phase B (oxlint, 必须 A 完成)
  │   ├── Task B1: oxlint --fix 批量自动修 (sort-imports + new-cap + no-duplicate)
  │   ├── Task B2: func-style 456 处 → const 箭头函数
  │   ├── Task B3: id-length 754 处 → 全名变量
  │   ├── Task B4: no-magic-numbers 703 处 → const/index.ts 常量
  │   ├── Task B5: no-ternary 353 处 → if/else
  │   ├── Task B6: max-statements 79 处 → 拆函数 + 其余规则
  │   ├── Task B7: 验收 0 warning + 719 test passed
  │   │
  │   ├── Phase C (coverage, 必须 A+B 完成)
  │   │   ├── Task C1: 后端补测到 80%
  │   │   ├── Task C2: 前端补测到 75%
  │   │   │
  │   │   ├── Phase D (CI, 可跟 C 并行)
  │   │   │   └── Task D1: .github/workflows/ci.yml
  │   │   │
  │   │   └── Phase E (文档, 最后)
  │   │       └── Task E1: 3 个 CLAUDE.md append
  │   │
  │   └── 最终验收: push branch
```

---

### Task A1: 基建 - conftest.py + helpers

**Files:**
- Create: `packages/service/tests/conftest.py`
- Create: `packages/service/tests/helpers.py`

- [ ] **Step 1: 写 tests/conftest.py (全局 fixture)**

```python
"""全局测试 fixture: 自动 mock 所有 DB/Redis 连接.

所有 test 跑前自动注入 mock, 防止意外直连 PG/Redis/Neo4j.
集成测试 (标记 @pytest.mark.integration) 不受此 fixture 影响.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_all_db_connections(monkeypatch):
    """每个 test 跑前 mock 所有数据库连接.

    - session_scope → MagicMock
    - get_redis → FakeRedis / MagicMock
    - get_object_store → MagicMock
    - engine._engine → None (关真 engine)
    """
    from unittest.mock import MagicMock

    # session_scope mock
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False

    monkeypatch.setattr("src.storage.engine._engine", None)

    # 注意: 不直接 monkeypatch session_scope 模块级别, 因为有些 test 已经自己 patch
    # 这里只关 engine, session_scope 由各 test 按需 mock

    # Redis mock
    try:
        import fakeredis.aioredis  # noqa: F401

        fake_redis = fakeredis.FakeAsyncRedis()
        monkeypatch.setattr("src.core.redis_client.get_redis", lambda: fake_redis)
    except ImportError:
        pass  # fakeredis 没装就跳过

    # ObjectStore mock (MinIO / LocalFS)
    mock_store = MagicMock()
    mock_store.backend_name.return_value = "mock"
    monkeypatch.setattr("src.storage.object_store.get_object_store", lambda: mock_store)
```

- [ ] **Step 2: 写 tests/helpers.py (mock CurrentUser 工厂)**

```python
"""测试辅助工具: mock CurrentUser 工厂.

用法:
    user = mock_current_user(id=1, role="admin")
    user = mock_current_user(is_anon=True)
"""

from __future__ import annotations

from unittest.mock import MagicMock


def mock_current_user(
    *,
    id: int = 1,
    role: str = "user",
    email: str | None = "admin@x.com",
    is_account: bool = True,
    is_active: bool = True,
    is_pending_deletion: bool = False,
) -> MagicMock:
    """构造 mock CurrentUser (不依赖 Pydantic 构造, 走 MagicMock).

    role 字段控制 is_admin 派生:
    - "admin" / "super_admin" → is_admin=True
    - "user" → is_admin=False
    """
    user = MagicMock()
    user.id = id
    user.public_token = f"tok-{id}"
    user.role = role
    user.email = email
    user.is_account = is_account
    user.is_active = is_active
    user.is_pending_deletion = is_pending_deletion
    user.account_id = id if is_account else None
    user.display_name = email or None
    user.avatar_url = None
    user.deletion_requested_at = None

    # is_admin 派生属性
    user.is_admin = role in ("admin", "super_admin")
    return user
```

- [ ] **Step 3: 验证 conftest.py 可 import**

```bash
cd c:/doc/Code/rag/packages/service
uv run python -c "from tests.conftest import mock_all_db_connections; print('conftest OK')"
uv run python -c "from tests.helpers import mock_current_user; u=mock_current_user(role='admin'); print(f'user role={u.role}, is_admin={u.is_admin}')"
```

Expected: 都输出 OK

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/tests/conftest.py packages/service/tests/helpers.py
git commit -m "feat(test): 全局 mock DB fixture + helpers (mock_current_user 工厂)"
```

---

### Task A2: auth 类 10 个 test 文件 mock 改造

**Files:**
- Modify: `tests/auth/test_login.py`
- Modify: `tests/auth/test_auth_cookie.py`
- Modify: `tests/auth/test_invite_flow.py`
- Modify: `tests/auth/test_password_reset.py`
- Modify: `tests/auth/test_seed_admin.py`
- Modify: `tests/auth/test_admin_router_role.py`
- Modify: `tests/auth/test_admin_users_api.py`
- Modify: `tests/auth/test_middleware_integration.py`
- Modify: `tests/auth/test_me.py`
- Modify: `tests/auth/test_logout.py`

每个文件改造模式相同：

```python
# 改造前: TestClient 走 resolve_user → session_scope → PG
def test_something(client):
    resp = client.post("/api/login", json={...})
    assert resp.status_code == 200

# 改造后: 调 resolve_user 被 mock, session_scope 也被 mock
def test_something(client):
    resp = client.post("/api/login", json={...})
    # resolve_user 返 mock_current_user, session_scope 返 MagicMock
    assert resp.status_code == 200
```

核心难点: auth test 的 `resolve_user` 依赖 PG 查 account 表。用 `app.dependency_overrides` 替换。

- [ ] **Step 1: 分析 auth test 中哪个文件用到 resolve_user**

```bash
cd c:/doc/Code/rag
grep -l "resolve_user\|require_account\|require_page\|require_super_admin" packages/service/tests/auth/*.py
```

每个文件需 `dependency_overrides` 替换鉴权守卫。

- [ ] **Step 2-11: 逐文件改造 (每个文件独立 commit)**

每个文件的改造模式 (以 test_login.py 为例):

```python
"""Login tests - 全 mock (模式 1), 0 PG 连接"""

from tests.helpers import mock_current_user

def test_login_success(client, app):
    """登录成功 → 200 + 返 token + account"""
    # mock resolve_user (login 路由不走 resolve_user, 但后续 router 可能用)
    # 注: login 本身不依赖 resolve_user, 它自己从 body 读 credential
    # 但后续 /me /logout 等依赖, 这里 mock 掉
    from src.middleware.auth import resolve_user
    app.dependency_overrides[resolve_user] = lambda: mock_current_user(id=1, role="user")

    resp = client.post("/api/login", json={"email": "admin@x.com", "password": "longpassword"})

    # 如果 login 调了 session_scope (查 account), 需要 mock
    # 但 login 的 password_hash 验证在业务层, mock session_scope 返空 → 401
    # 这里看具体实现, 可能需要 mock session_scope 返预设 account 数据
    ...
```

> **注意**: auth test 改造量最大。每个文件都需要:
> 1. `app.dependency_overrides[resolve_user] = lambda: mock_current_user(...)`
> 2. `monkeypatch` 或 `patch` 掉 `session_scope` (如果测试里调了)
> 3. 原来依赖 PG 真数据的断言 (如查 DB 看是否插入) 改为断言 mock 调用
>
> 具体每个文件改多少取决于实现。建议逐个文件审、改、跑、commit。

- [ ] **Step 12: 提交 (每个文件改完单独 commit)**

---

### Task A3: router 类 12 个 test 文件 mock 改造

**Files:**
- Modify: `tests/eval/test_router.py`
- Modify: `tests/memory/test_router.py`
- Modify: `tests/kg/test_kg_router.py`
- Modify: `tests/middleware/test_auth.py`
- Modify: `tests/approvals/test_router.py`
- Modify: `tests/chat/test_router.py`
- Modify: `tests/chat/test_service.py`
- Modify: `tests/chat_share/test_router.py`
- Modify: `tests/chat_share/test_files_upload.py`
- Modify: `tests/permissions/test_router.py`
- Modify: `tests/roles/test_router.py`
- Modify: `tests/lookups/test_admin_router.py`

这些文件有的已经 mock 了 session_scope（如 eval/test_csv_storage.py 模式 1），有的直接调 TestClient 走真 engine（如 eval/test_router.py 当前 fail）。改造模式：

```python
# 改造前 (fail):
def test_upload_creates_pending_evaluation(client):
    resp = client.post("/api/eval/upload", ...)
    assert resp.status_code == 200  # 403 因为 evaluate page 不给 user

# 改造后 (mock 鉴权守卫):
def test_upload_creates_pending_evaluation(client, app):
    from src.middleware.auth import resolve_user
    from tests.helpers import mock_current_user

    # 替换 resolve_user 为 admin
    app.dependency_overrides[resolve_user] = lambda: mock_current_user(id=1, role="admin")
    # mock session_scope
    with patch("src.eval.router.session_scope") as mock_scope:
        mock_session = MagicMock()
        mock_scope.return_value.__enter__.return_value = mock_session
        # ... 业务逻辑
        resp = client.post("/api/eval/upload", ...)
        assert resp.status_code == 200
```

- [ ] **Step 1-12: 逐文件改造 + 跑通 + commit**

---

### Task A4: integration 类标记 skip

**Files:**
- Modify: `tests/integration/test_db_session_fixture.py`
- Modify: `tests/integration/test_account_settings_models.py`
- Modify: `tests/integration/test_minio_e2e.py`
- Modify: `tests/integration/test_rbac_e2e.py`
- Modify: `tests/db/test_log_tables.py`
- Modify: `tests/middleware/test_cors_credentials.py`
- Modify: `tests/integration/test_mineru_retry_e2e.py`

- [ ] **Step 1: 给每个文件加 `@pytest.mark.integration` 标记**

```python
# 文件头部或类/函数加:
pytestmark = pytest.mark.integration
```

- [ ] **Step 2: 验证 `pytest --no-header -q -m "not integration"` 跳过它们**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest --no-header -q -m "not integration" 2>&1 | tail -5
```

Expected: 0 failed + 0 errors

- [ ] **Step 3: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/tests/integration/ packages/service/tests/db/ packages/service/tests/middleware/
git commit -m "refactor(test): integration test 标记 @pytest.mark.integration (CI 默认 skip)"
```

---

### Task A5: 验收 0 fail + 0 errors + KNOWN_ISSUES.md 更新

**Files:**
- Modify: `packages/service/KNOWN_ISSUES.md`

- [ ] **Step 1: 跑全测试**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest --no-header -q --tb=no 2>&1 | tail -5
```

Expected: 0 failed, 0 errors (可能有一些 skipped, 那是 integration test)

- [ ] **Step 2: 更新 KNOWN_ISSUES.md**

把 "仍 fail 的 22 个" 段整个删掉，加新段：

```markdown
## 2026-06-19 code-quality phase2 完成

- **passed: XXXX** (全部 test 模式 1 mock)
- **failed: 0**
- **errors: 0**
- **skipped: YY** (全部 `@pytest.mark.integration`)

所有 test 不再直连 PG/Redis/Neo4j.
集成测试标记 integration, CI 默认跳过.
```

- [ ] **Step 3: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/KNOWN_ISSUES.md
git commit -m "fix(test): 全部 test mock 改造完成 - 0 fail 0 errors (KNOWN_ISSUES 清零)"
```

---

### Task B1: oxlint --fix 批量自动修

**Files:**
- Modify: 前端所有 .ts/.tsx 文件 (sort-imports / new-cap / no-duplicate-imports 等可自动修)

- [x] **Step 1: 跑 oxlint --fix**

```bash
cd c:/doc/Code/rag/packages/web
bun run lint:fix 2>&1 | tail -5
```

实测: 3421 → 3415 (oxlint --fix 自动可修能力有限).

- [x] **Step 2: 跑测试 + typecheck 验证不破坏**

```bash
cd c:/doc/Code/rag/packages/web
bun run test 2>&1 | tail -3
bun run typecheck 2>&1 | tail -3
```

---

### Task B2-Bn: 按目录拆 30+ task

**为什么拆这么细**: spec §2 估算 16-24h 修 200+ 文件 + 3412 warning. 单 task 200+ warning 风险高 (改 React 组件易破坏 typecheck). 按目录拆每 task 5-100 warning, 单次可控、可验、可单独 commit. 用户明确要求 "拆成 30 个任务也没问题".

**目录 warning 实测分布 (2026-06-19, 排序按数量)**:

| Task | 路径 | warning | 优先级 |
|---|---|---|---|
| B2 | 根目录 (`*.ts`, `proxy.test.ts`, `playwright.config.ts`, `next.config.ts`) | 28 | 🟢 简单 |
| B3 | `i18n/` + `scripts/` + `hooks/` | 26 | 🟢 简单 |
| B4 | `lib/auth` + `lib/dom` + `lib/hooks` + `lib/store` + `lib/test-utils` + `lib/theme` | 41 | 🟢 简单 |
| B5 | `lib/*.ts` (根) | 131 | 🟡 中 |
| B6 | `lib/api` | 173 | 🟡 中 |
| B7 | `lib/chat` | 199 | 🟡 中 |
| B8 | `components/auth` + `components/i18n` + `components/settings` | 34 | 🟢 简单 |
| B9 | `components/knowledge` + `components/evaluate` | 124 | 🟡 中 |
| B10 | `components/ui` | 71 | 🟢 中 (shadcn 包装组件) |
| B11 | `components/*.tsx` (根 PageGuard / UserMenu / header / theme-provider) | 71 | 🟡 中 |
| B12 | `components/common` | 270 | 🔴 高 (DataTable/AppDialog 等核心) |
| B13 | `components/chat` | 290 | 🔴 高 |
| B14 | `app/[locale]/login` + `forgot-password` + `reset-password` + `invite` | 32 | 🟢 简单 |
| B15 | `app/[locale]/_actions` | 91 | 🟡 中 |
| B16 | `app/[locale]/account` | 132 | 🟡 中 |
| B17 | `app/[locale]/chat` | 21 | 🟢 简单 |
| B18 | `app/[locale]/decode` | 63 | 🟢 中 |
| B19 | `app/[locale]/evaluate` | 133 | 🟡 中 |
| B20 | `app/[locale]/health` | 59 | 🟢 中 |
| B21 | `app/[locale]/output` | 212 | 🔴 高 |
| B22 | `app/[locale]/submissions` | 89 | 🟡 中 |
| B23 | `app/[locale]/admin/invites` | 29 | 🟢 简单 |
| B24 | `app/[locale]/admin/permissions` | 94 | 🟡 中 |
| B25 | `app/[locale]/admin/users` | 106 | 🟡 中 |
| B26 | `app/[locale]/admin/dicts` | 116 | 🟡 中 |
| B27 | `app/[locale]/knowledge/_components` + `batch` + `graph` + `nodes` | 101 | 🟡 中 |
| B28 | `app/[locale]/knowledge/dataset-documents` + `datasets` + `relations` + `qa` | 150 | 🟡 中 |
| B29 | `app/[locale]/knowledge/triples` | 106 | 🟡 中 |
| B30 | `app/[locale]/knowledge/documents` | 119 | 🟡 中 |
| B31 | `app/api` (BFF routes) | 182 | 🟡 中 |
| B32 | filename-case 重命名扫尾 (126 文件 PascalCase → kebab-case) | 126 | 🔴 高 (需改所有 import 站点) |
| B33 | 全套验收: bun lint = 0 warning, bun test = 719 passed, bun typecheck = 0 error | - | - |

**通用步骤** (每个 task):

1. `cd packages/web && bunx oxlint <dir>` 看具体 warning
2. 自动修: `bunx oxlint <dir> --fix`
3. 手动改 (按规则优先级):
   - **func-style**: `function foo(){}` → `const foo = () => {}` (React 组件 default export 保留)
   - **id-length**: 单字符变量改全名 (e→err, i→idx, v→val, _→_unused)
   - **no-magic-numbers**: 提取到 `const/index.ts`, 基础 0/1/-1 加 `// eslint-disable-next-line no-magic-numbers -- 基础数字`
   - **no-ternary**: 三元改 if/else, JSX 内提取 ReactNode 变量
   - **max-statements**: 拆函数 (>10 statement)
   - **new-cap**: 构造函数首字母大写
   - **prefer-global-this**: `window.foo` → `globalThis.foo`
   - **filename-case**: 重命名 PascalCase → kebab-case (B32 单独处理)
4. 验证: `bunx oxlint <dir>` 0 warning, `bun run typecheck` 0 error, `bun run test` 不引入回归
5. Commit: `chore(web): oxlint 清理 <dir> (-N warnings)`

**Files:**
- Modify: 前端含 `function foo(){}` 的文件 (456 处)

- [ ] **Step 1: 列出所有 `function ` 声明**

```bash
cd c:/doc/Code/rag/packages/web
grep -rn "^function \|^export function \|^export default function " --include="*.ts" --include="*.tsx" app/ components/ hooks/ lib/ i18n/ | grep -v ".d.ts" | wc -l
```

- [ ] **Step 2-10: 分批改 (每 100 个一组, 改完跑测试)**

改法:
```typescript
// 改前
function doSomething(arg: string) {
  return arg.toUpperCase();
}

// 改后
const doSomething = (arg: string): string => arg.toUpperCase();

// 改前 (React 组件 default export - 保留)
export default function Page() { ... }

// 改前 (React 组件 default export 必须 function)
export default function Page() { ... }
// 不改
```

- [ ] **Step 11: 验收 + Commit**

```bash
cd c:/doc/Code/rag/packages/web
bun run lint 2>&1 | grep -c "func-style"
bun run test 2>&1 | tail -3
bun run typecheck 2>&1 | tail -3
```

Expected: func-style 0 warning

```bash
cd c:/doc/Code/rag
git add packages/web/
git commit -m "chore(web): func-style 456 处改 const 箭头函数 (React 组件 default export 保留)"
```

---

### Task B33 验收

- [ ] `bun run lint` 0 warning + 0 error
- [ ] `bun run test` 719 passed (不引入回归)
- [ ] `bun run typecheck` 0 errors

---

### Task C1: 后端补测到 80% lines

**Files:**
- Create/Modify: 按 coverage report 缺哪补哪

- [ ] **Step 1: 跑 coverage 看缺哪些模块**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest --cov=src --cov-report=term-missing 2>&1 | grep -E "^src/" | awk '$NF < 80' | sort -t' ' -k2 -rn
```

Expected: 列出覆盖率 < 80% 的模块

- [ ] **Step 2-10: 逐模块补测试**

每个模块的补法:
1. 读 missing lines (coverage 报告里每个文件的 `Missing` 列)
2. 对每个缺失行判断: 是否核心业务逻辑?
   - 是 → 写测试
   - 否 (exception handler / __init__ / 配置) → 加 `# pragma: no cover`
3. 改完跑 `uv run pytest --cov-fail-under=80` 验证

- [ ] **Step 11: 验收**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest --cov=src --cov-fail-under=80 2>&1 | tail -5
```

Expected: exit 0, coverage ≥ 80%

---

### Task C2: 前端补测到 75% lines

**Files:**
- Create/Modify: 前端 test 文件

- [ ] **Step 1: 跑 coverage 看缺哪些模块**

```bash
cd c:/doc/Code/rag/packages/web
bun run test:coverage 2>&1 | grep -E "^.*\|" | awk -F'|' '$5 ~ /[0-9]+/ && $5+0 < 75' | head -20
```

- [ ] **Step 2-10: 逐模块补测试**

- [ ] **Step 11: 验收**

```bash
cd c:/doc/Code/rag/packages/web
bun run test:coverage 2>&1 | grep "Lines"
```

Expected: Lines ≥ 75%

---

### Task D1: GitHub CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: 创建 .github 目录 + ci.yml**

```bash
cd c:/doc/Code/rag
mkdir -p .github/workflows
```

按 spec §5 的 yaml 内容写入 `ci.yml`。

- [ ] **Step 2: 验证 yaml 语法**

```bash
cd c:/doc/Code/rag
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```

- [ ] **Step 3: Commit**

```bash
cd c:/doc/Code/rag
git add .github/workflows/ci.yml
git commit -m "ci: GitHub Actions workflow (format+lint+type+test+coverage)"
```

---

### Task E1: 3 个 CLAUDE.md append

**Files:**
- Modify: `CLAUDE.md`
- Modify: `packages/service/CLAUDE.md`
- Modify: `packages/web/CLAUDE.md`

- [ ] **Step 1: 项目根 CLAUDE.md append**

追加 spec §6.2 的"强制测试隔离"段。

- [ ] **Step 2: packages/service/CLAUDE.md append**

追加 spec §6.2 的"测试隔离强制规范"段。

- [ ] **Step 3: packages/web/CLAUDE.md append**

追加 spec §6.2 的"零 lint warning 规范"段。

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag
git add CLAUDE.md packages/service/CLAUDE.md packages/web/CLAUDE.md
git commit -m "docs: 3 个 CLAUDE.md append phase2 新规范 (test-isolation + lint 零 warning + coverage 门禁)"
```

---

## 自审 (spec 覆盖)

| Spec 节 | 实施 Task |
|---------|----------|
| §一 目标 & 架构 | 全局 (A→E) |
| §二 Phase A: Test Isolation | Task A1-A5 |
| §三 Phase B: Oxlint | Task B1-B6 |
| §四 Phase C: Coverage | Task C1-C2 |
| §五 Phase D: CI | Task D1 |
| §六 Phase E: CLAUDE.md | Task E1 |
| §七 范围外 | plan 中无 codegen/升级/E2E |

---

## 执行选择

**Plan complete and saved to `docs/superpowers/plans/2026-06-19-code-quality-phase2.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每 task 派一个新 subagent, task 间 review, 快速迭代

**2. Inline Execution** - 当前会话批量执行 + checkpoints

**Which approach?**
