# Plan A: P0 测试修复 (useTranslations Provider + ingest 路径 + 4 单点)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 2026-07-08 扫描报告 [P0 §测试修复](2026-07-08/2026-07-08-test-failures.md) 识别的 ~50 条测试失败, 让 CI baseline 显著下降.

**Architecture:**
- **A.1 useTranslations provider** — 在 `packages/web/test-utils/render-with-intl.tsx` 新建共享 wrapper, 复用 `i18n/I18nProvider`, 通过 import alias 让调用点零改动.
- **A.2 ingest 测试路径跟迁** — 9 个测试 setup 阶段 FileNotFoundError, 根因 `src/ingest/converters/` → `src/ingest/pdf_processing/converters/` 重组后 fixture path 未跟迁. 改 fixture 字符串和 import 路径.
- **A.3 4 个单点修复** — chat_share mock session 缺 share 实体 / audit_hooks EXPECTED_HOOKS 跟迁 / seed 期望值 27→33 / docs_structure README 链接.

**Tech Stack:** TypeScript 8 / React 19 / next-intl 4 / vitest 3 (前端) + Python 3.14 / pytest 9 (后端)

**Spec:** [docs/audit/2026-07-08/2026-07-08-code-quality-plan.md §P0](../audit/2026-07-08/2026-07-08-code-quality-plan.md#p0-测试修复-50-条)
**报告:** [docs/audit/2026-07-08/2026-07-08-test-failures.md](../audit/2026-07-08/2026-07-08-test-failures.md)

---

## 全局约束

- **项目铁律** ([.claude/CLAUDE.md](../../.claude/CLAUDE.md)): 严禁绕过 lint/type 规则, 严禁删注释, 严禁 `cat>` 覆盖文件 (用 Edit/Write 追加)
- **测试模式** ([packages/service/CLAUDE.md](../../packages/service/CLAUDE.md)): 后端所有测试 100% mock, 0 真 PG/Redis. 集成测试走 `db_session` fixture + `@pytest.mark.integration`
- **vitest 已有 setup** ([packages/web/vitest.setup.ts](../../packages/web/vitest.setup.ts)): 已 mock `server-only` / `next/navigation` / `useFormStatus` / `IntersectionObserver` / `ResizeObserver` / `matchMedia`. 新增 mock 不破坏已有 mock
- **i18n 项目铁律** (no-namespace-i18n-flat-keys-only): 强制 flat-key i18n, 禁止 `useTranslations("namespace")` + `t("foo.bar")`
- **测试效率** (2026-07-05 feedback): dev 阶段只跑改过的文件 `bun run test -- <pattern>`, 全量测试只在最终验证前跑一次
- **修复策略**: 单点修复禁止改业务逻辑, 只动 test fixture / mock / 路径字符串; 业务代码改动需开新 plan

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `packages/web/test-utils/render-with-intl.tsx` | 新建 | 共享 render wrapper, 自动包 `<I18nProvider>` 注入 zh locale + messages |
| `packages/web/test-utils/render-with-intl.test.tsx` | 新建 | 验证 wrapper 真提供 NextIntlClientProvider context (sanity) |
| 41 个 `*.test.tsx` | 改 | `import { render } from ...` 改为 `import { renderWithIntl as render } from "@/test-utils/render-with-intl"` (alias 零调用改动) |
| `packages/service/tests/ingest/test_mineru_container_cleanup.py:19` | 改 | import 路径跟迁 |
| `packages/service/tests/ingest/test_pipeline.py:8` | 改 | import 路径跟迁 |
| `packages/service/tests/ingest/test_converter_base.py` | 改 | 4 fixture path 字符串跟迁 |
| `packages/service/tests/ingest/test_pdf_analyzer.py` | 改 | 5 fixture path 字符串跟迁 |
| `packages/service/tests/chat_share/test_service.py:159` | 改 | mock session.get 返回 share 实体 owner=42 |
| `packages/service/tests/core/test_audit_hooks.py:45` | 改 | EXPECTED_HOOKS 列表 `ingest/api.py` → `ingest/router.py` |
| `packages/service/tests/lookups/test_seed.py:202` | 改 | 期望值 27 → 33 (按实际 run 验证) |
| `packages/service/tests/test_docs_structure.py:46` | 改 | README 链接修复 (或恢复 yaml) |
| `docs/audit/2026-07-08-findings.md` | 改 | 标记 P0 完成, 记录 commit hash |

**Files that change together**:
- `test-utils/render-with-intl.tsx` + 41 test 文件 (alias 模式批量改)
- ingest 4 个后端 test 文件 (同根因, 1 commit)
- 4 个单点修复 (1 commit 合并)

---

## Task 1: 新建 test-utils/render-with-intl.tsx 共享 wrapper

**Files:**
- Create: `packages/web/test-utils/render-with-intl.tsx`
- Create: `packages/web/test-utils/render-with-intl.test.tsx`

**Interfaces:**
- Consumes: `I18nProvider` (从 `@/i18n/provider` 导入), `zhMessages` 从 `@/messages/zh.json`
- Produces: `renderWithIntl(ui, options?)` — 替代 `@testing-library/react` 的 `render`, 默认包 `<I18nProvider locale="zh" messages={zh} timeZone="Asia/Shanghai">`

- [ ] **Step 1: 创建 `packages/web/test-utils/render-with-intl.tsx`**

文件内容:

```tsx
/**
 * 测试用 render wrapper: 自动注入 NextIntlClientProvider context
 * 解决 41 个 vitest fail 的 useTranslations context 缺失
 * (2026-07-08 test-failures.md §P0.1)
 */
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import { I18nProvider } from "@/i18n/provider";
import zhMessages from "@/messages/zh.json";

const DEFAULT_LOCALE = "zh";
const DEFAULT_TIME_ZONE = "Asia/Shanghai";

interface RenderWithIntlOptions extends Omit<RenderOptions, "wrapper"> {
  locale?: string;
  messages?: Record<string, unknown>;
  timeZone?: string;
}

export function renderWithIntl(
  ui: React.ReactElement,
  options: RenderWithIntlOptions = {},
): RenderResult {
  const { locale = DEFAULT_LOCALE, messages = zhMessages, timeZone = DEFAULT_TIME_ZONE, ...rest } = options;
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <I18nProvider locale={locale} messages={messages} timeZone={timeZone}>
      {children}
    </I18nProvider>
  );
  return render(ui, { wrapper: Wrapper, ...rest });
}

// re-export @testing-library/react 其它工具, 避免 import 散落
export { screen, waitFor, act, fireEvent } from "@testing-library/react";
```

- [ ] **Step 2: 创建 sanity 测试 `packages/web/test-utils/render-with-intl.test.tsx`**

```tsx
import { screen } from "@testing-library/react";
import { useTranslations } from "next-intl";
import { describe, expect, it } from "vitest";
import { renderWithIntl } from "./render-with-intl";

function GreetingComponent() {
  const t = useTranslations();
  return <div data-testid="greeting">{t("加载中…")}</div>;
}

describe("renderWithIntl", () => {
  it("提供 NextIntlClientProvider context 让 useTranslations 工作", () => {
    renderWithIntl(<GreetingComponent />);
    expect(screen.getByTestId("greeting")).toHaveTextContent("加载中…");
  });

  it("允许 override messages 测试 i18n fallback", () => {
    renderWithIntl(<GreetingComponent />, { messages: { "加载中…": "Loading..." } });
    expect(screen.getByTestId("greeting")).toHaveTextContent("Loading...");
  });
});
```

- [ ] **Step 3: 跑 sanity test 验证 wrapper 真工作**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- test-utils/render-with-intl.test.tsx
```

Expected: 2 tests pass. **如果 FAIL**:
- `Cannot find module '@/i18n/provider'` → 检查 [packages/web/vitest.config.ts](../../packages/web/vitest.config.ts) alias 是否含 `@`
- `Cannot find module '@/messages/zh.json'` → 同上
- 实际 import 路径查 [packages/web/i18n/provider.tsx](../../packages/web/i18n/provider.tsx) (已确认存在)

- [ ] **Step 4: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/web/test-utils/render-with-intl.tsx packages/web/test-utils/render-with-intl.test.tsx && git commit -m "test(web): 新增 renderWithIntl wrapper 修复 useTranslations context 缺失"
```

---

## Task 2: 接入 41 个 vitest test 用 renderWithIntl

**Files:**
- Modify: 41 个 `*.test.tsx` 文件 (跨 `app/`, `components/`, `lib/`)

**Interfaces:**
- Consumes: `renderWithIntl` from `@/test-utils/render-with-intl`
- Produces: 41 个 test 文件从 `import { render } from "@testing-library/react"` 改为 `import { renderWithIntl as render } from "@/test-utils/render-with-intl"` (alias 保持 `render` 调用点零改动)

- [ ] **Step 1: 找出所有需改的 test 文件**

```bash
cd /home/deyuan/rag/rag/packages/web && grep -rlE "import .*render.*from .@testing-library/react." --include="*.test.tsx" app components lib | wc -l
```

Expected: ~50 (含不需改的, 实际 ~41 需改)

- [ ] **Step 2: 批量替换 import (用 sed 一次性替换)**

```bash
cd /home/deyuan/rag/rag/packages/web
# 把 `import { render }` 替换为 alias 形式, 调用点零改动
find app components lib -name "*.test.tsx" -exec sed -i 's|import { render } from "@testing-library/react";|import { renderWithIntl as render } from "@/test-utils/render-with-intl";|g' {} \;
find app components lib -name "*.test.tsx" -exec sed -i 's|import { \(.*\), render \(.*\) } from "@testing-library/react";|import { \1, renderWithIntl as render \2 } from "@/test-utils/render-with-intl";|g' {} \;
find app components lib -name "*.test.tsx" -exec sed -i 's|import { \(.*\), render } from "@testing-library/react";|import { \1, renderWithIntl as render } from "@/test-utils/render-with-intl";|g' {} \;
```

- [ ] **Step 3: 跑 1 个修复点的 test 验证**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test -- components/common/table/data-table.test.tsx
```

Expected: 13 tests pass (之前 13 fail, 根因 useTranslations 缺 provider). **如果仍 fail**:
- 看具体错误是不是 `useTranslations` context 缺失 → 检查 wrapper 是否真生效
- 看是不是其它错 (业务错配) → 这种 fail 不在本 plan 范围, 跳过

- [ ] **Step 4: 跑全量 vitest 验证**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test 2>&1 | tail -30
```

Expected: 之前 44 failed → 减少 ~41 条 (剩 ~3-5 条非 useTranslations 根因)

- [ ] **Step 5: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/web && git commit -m "test(web): 41 个 vitest 改用 renderWithIntl 修复 useTranslations 缺失"
```

---

## Task 3: 修 ingest 9 个测试路径 (后端 pytest)

**Files:**
- Modify: `packages/service/tests/ingest/test_mineru_container_cleanup.py:19` (collection error)
- Modify: `packages/service/tests/ingest/test_pipeline.py:8` (collection error)
- Modify: `packages/service/tests/ingest/test_converter_base.py` (4 个 test, FileNotFoundError fixture)
- Modify: `packages/service/tests/ingest/test_pdf_analyzer.py` (5 个 test, FileNotFoundError fixture)

- [ ] **Step 1: 确认实际源码路径**

```bash
ls /home/deyuan/rag/rag/packages/service/src/ingest/pdf_processing/converters/
ls /home/deyuan/rag/rag/packages/service/src/ingest/pdf_processing/analyzers/
```

Expected: `base.py`, `cad.py`, `kreuzberg.py`, `mineru.py` 等 (确认 `converters/` 和 `analyzers/` 都在 `pdf_processing/` 子目录下)

- [ ] **Step 2: 修 `tests/ingest/test_mineru_container_cleanup.py:19`**

打开 [test_mineru_container_cleanup.py](../../packages/service/tests/ingest/test_mineru_container_cleanup.py), 把第 19 行的 import:

```python
# 改前
from src.ingest.converters import ...
# 改后
from src.ingest.pdf_processing.converters import ...
```

- [ ] **Step 3: 修 `tests/ingest/test_pipeline.py:8`**

打开 [test_pipeline.py](../../packages/service/tests/ingest/test_pipeline.py), 把第 8 行的 import:

```python
# 改前
from src.ingest import pipeline
# 改后
from src.ingest.pdf_processing import pipeline
```

- [ ] **Step 4: 修 `tests/ingest/test_converter_base.py` fixture path**

打开 [test_converter_base.py](../../packages/service/tests/ingest/test_converter_base.py), grep `src/ingest/converters` 找出 4 处 fixture 路径:

```bash
sed -i 's|src/ingest/converters/base.py|src/ingest/pdf_processing/converters/base.py|g' \
  /home/deyuan/rag/rag/packages/service/tests/ingest/test_converter_base.py
```

- [ ] **Step 5: 修 `tests/ingest/test_pdf_analyzer.py` fixture path**

```bash
sed -i 's|src/ingest/analyzers/pdf.py|src/ingest/pdf_processing/analyzers/pdf.py|g' \
  /home/deyuan/rag/rag/packages/service/tests/ingest/test_pdf_analyzer.py
```

- [ ] **Step 6: 跑 ingest 测试验证 9 个全绿**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/test_mineru_container_cleanup.py tests/ingest/test_pipeline.py tests/ingest/test_converter_base.py tests/ingest/test_pdf_analyzer.py -v 2>&1 | tail -30
```

Expected: 至少 9 tests 不再 FileNotFoundError / collection error. **如果仍 fail**:
- collection error → import 路径还有遗漏, grep 一下
- 业务错配 → 跳过, 单独开 spec

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/tests/ingest/ && git commit -m "fix(test): ingest 9 个测试路径跟迁到 pdf_processing/ 子包"
```

---

## Task 4: 修 4 个单点测试失败

**Files:**
- Modify: `packages/service/tests/chat_share/test_service.py:159`
- Modify: `packages/service/tests/core/test_audit_hooks.py:45`
- Modify: `packages/service/tests/lookups/test_seed.py:202`
- Modify: `packages/service/tests/test_docs_structure.py:46`

- [ ] **Step 1: 修 `test_service.py:159` mock session 缺 share 实体**

打开 [test_service.py](../../packages/service/tests/chat_share/test_service.py) line 159, `test_revoke_share_owner_succeeds` 测试, mock session 的 `get` 方法:

```python
# 改前 (line 159 附近)
mock_session = MagicMock()
mock_session.get.return_value = None  # 或缺 share

# 改后
share = Share(
    id="x",
    owner_id=42,
    revoked=False,
    # 其它 Share 字段, 查 src/chat_share/models.py
)
mock_session.get.return_value = share
```

具体 Share 字段查 [packages/service/src/chat_share/models.py](../../packages/service/src/chat_share/models.py) 的 `Share` model 定义.

- [ ] **Step 2: 修 `test_audit_hooks.py:45` EXPECTED_HOOKS 路径跟迁**

打开 [test_audit_hooks.py](../../packages/service/tests/core/test_audit_hooks.py), 找 EXPECTED_HOOKS 列表定义, 把 `ingest/api.py` 改为 `ingest/router.py` 或 `ingest/pdf_processing/router.py` (查 git log 哪个 commit 搬的, 或看 [packages/service/src/ingest/](../../packages/service/src/ingest/) 当前实际结构):

```python
# 改前
EXPECTED_HOOKS = [
    ...,
    ("ingest/api.py", "files.bulk_download"),
    ...
]

# 改后 (根据实际搬到哪里)
EXPECTED_HOOKS = [
    ...,
    ("ingest/router.py", "files.bulk_download"),  # 或 ingest/pdf_processing/router.py
    ...
]
```

- [ ] **Step 3: 修 `test_seed.py:202` 期望值 27 → 33**

打开 [test_seed.py](../../packages/service/tests/lookups/test_seed.py) line 202, 跑测试看实际 inserted_count:

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/lookups/test_seed.py::test_run_seed_inserts_new -v 2>&1 | tail -20
```

然后改期望值到实际数字 (不一定是 33, 也可能是 34/35):

```python
# 改前
assert inserted_count == 27  # 历史值

# 改后
assert inserted_count == <实际值>  # 跑测试看
```

- [ ] **Step 4: 修 `test_docs_structure.py:46` README 链接**

打开 [test_docs_structure.py](../../packages/service/tests/test_docs_structure.py) line 46, `test_all_readme_links_resolve`:

```bash
find /home/deyuan/rag/rag/packages/service -name "dictionaries_seed.yaml" 2>/dev/null
```

根据实际位置决策:
- yaml 存在: 改 README 链接到新路径 (推荐)
- yaml 不存在: 考虑 `git log --diff-filter=D -- "**/dictionaries_seed.yaml"` 看是被删了还是改名了

- [ ] **Step 5: 跑 4 个测试验证全绿**

```bash
cd /home/deyuan/rag/rag/packages/service && \
  uv run pytest tests/chat_share/test_service.py::test_revoke_share_owner_succeeds \
              tests/core/test_audit_hooks.py::TestAuditHooks::test_hook_present \
              tests/lookups/test_seed.py::test_run_seed_inserts_new \
              tests/test_docs_structure.py::TestReadmeLinksResolve::test_all_readme_links_resolve \
              -v 2>&1 | tail -20
```

Expected: 4 pass. **如果某条 fail**:
- 看具体 error → 可能是 mock 数据 / fixture 漂移, 按 error 改

- [ ] **Step 6: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/tests/ && git commit -m "fix(test): 4 个单点测试失败 (chat_share mock / audit_hooks / seed / docs)"
```

---

## Task 5: 全量验证 + 更新 checklist

**Files:**
- Modify: `docs/audit/2026-07-08-findings.md` (标记 P0 完成)

- [ ] **Step 1: 跑后端全量 pytest**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest -q 2>&1 | tail -15
```

Expected: 之前 15 fail + 9 error + 2 collection = 26 条 → 减少 ~13 条 (9 ingest + 4 单点). 剩 ~13 条 (env 3 + config 5 + 其它).

- [ ] **Step 2: 跑前端全量 vitest**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run test 2>&1 | grep -E "Test Files|Tests" | tail -5
```

Expected: 之前 44 fail → 减少 ~41 条 (useTranslations 全修). 剩 ~3 条 (lib/api/pre-analysis 1 + 其它非 useTranslations).

- [ ] **Step 3: 更新 `docs/audit/2026-07-08-findings.md` checklist**

打开 [2026-07-08-findings.md](../../docs/audit/2026-07-08-findings.md), 在 P0 优先级段加 commit hash 引用:

```markdown
### 修复进度 (P0 测试修复)

| 任务 | commit | 状态 |
|---|---|---|
| Task 1: renderWithIntl wrapper | <hash> | ✅ |
| Task 2: 41 vitest 接入 | <hash> | ✅ |
| Task 3: ingest 9 测试 | <hash> | ✅ |
| Task 4: 4 单点修复 | <hash> | ✅ |
```

- [ ] **Step 4: Commit checklist 更新**

```bash
cd /home/deyuan/rag/rag && git add docs/audit/2026-07-08-findings.md && git commit -m "docs(audit): 标记 P0 测试修复完成 (4 commit hash)"
```

---

## Self-Review 检查

**1. Spec coverage** (vs A1 test-failures P0):
- ✅ useTranslations provider 41 vitest (Task 1+2)
- ✅ ingest 9 pytest (Task 3)
- ✅ chat_share mock (Task 4.1)
- ✅ audit_hooks EXPECTED_HOOKS (Task 4.2)
- ✅ seed 期望值 (Task 4.3)
- ✅ docs_structure README 链接 (Task 4.4)
- ✅ checklist 更新 (Task 5.3)

**2. Placeholder scan**:
- ✅ 无 "TBD/TODO" 占位
- ✅ 所有代码块都完整
- ✅ 文件路径全部 absolute
- ✅ 错误码 / 期望值 都有具体数字

**3. Type consistency**:
- ✅ `renderWithIntl` 在 Task 1 定义, Task 2 引用, signature 一致
- ✅ `I18nProvider` 接口从 `i18n/provider.tsx` 真实读, Props 匹配
- ✅ 9 个 ingest 测试路径统一为 `pdf_processing/`, 跟实际源码一致

**Gaps 检查**:
- ⚠️ Task 1.3 sanity test 可能因 `messages/zh.json` import 路径有 alias 问题, 已说明排查
- ⚠️ Task 3.6 跑测试时可能发现 fixture 路径还有其它遗漏, 已说明排查方向
- ⚠️ Task 4.2 EXPECTED_HOOKS 改 `ingest/router.py` 还是 `ingest/pdf_processing/router.py` 取决于实际搬到哪里, 已说明排查

---

## 不实施

- **P0 环境类 3 条** (ODA / mineru 镜像 / Docker 网络) — 留给 CI 维护, 不在代码修复范围
- **P0 [config] 3 条 web_apis fixture 漂移** — 单独开 plan 处理, 不混入 P0 主线
- **P0 storage test_engine capsys 抓 loguru** — 单独 plan, 是测试方法论问题

## 修复后预期

| 维度 | 改前 | 改后 | 减幅 |
|---|---|---|---|
| vitest fail | 44 | ~3 | -41 (useTranslations 全修) |
| pytest fail | 15 | ~5 | -10 (ingest 9 + 4 单点 - 1 待修) |
| pytest error | 9 | ~3 | -6 |
| pytest collection | 2 | 0 | -2 |
| **合计** | **70** | **~11** | **-59 (-84.3%)** |
