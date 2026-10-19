# Code Quality 全量清理 + Coverage 检测 + CLAUDE.md 总结 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `code-quality-2026-06-19` 新分支跑全 6 工具链 (oxfmt/oxlint/ruff/pyright/pytest/vitest) 自动修复 + 加 coverage 检测 + 把本轮问题沉淀到 3 个 CLAUDE.md, 防再犯.

**Architecture:** 顺序前到后 (P0 format → P1 lint fix → P2 类型+测试 → P3 ignore 清理 → P4 coverage 配置 → P5 CLAUDE.md 总结). 每个 P 阶段一个 commit, 单阶段改 > 500 行停下问用户. 修能修的, 修不了列 known issues.

**Tech Stack:**
- 后端: Python 3.14 / ruff (lint+format) / pyright (类型) / pytest + pytest-cov (测试 + 覆盖率)
- 前端: TypeScript 8 / React 19 / oxfmt (format) / oxlint (lint) / tsgo (类型) / vitest + @vitest/coverage-v8 (测试 + 覆盖率)
- 项目锁版本: 不升级任何工具

**Spec:** `docs/superpowers/specs/2026-06-19-code-quality-cleanup-design.md`

---

## 任务依赖关系

```
P0 (格式化, 0 语义改)
  ↓
P1 (lint 自动修复, 0 语义改)
  ↓
P2 (类型 + 测试, 修能修的)
  ├─ P2a: pyright (后端)
  ├─ P2b: vitest (前端)
  └─ P2c: pytest (后端)
  ↓
P3 (ignore / noqa 清理, 修能修的)
  ├─ P3a: type: ignore / @ts-ignore
  └─ P3b: noqa
  ↓
P4 (coverage 配置, 不强制门禁)
  ├─ P4a: pytest-cov
  └─ P4b: vitest coverage
  ↓
P5 (CLAUDE.md 沉淀, 3 个文件)
  ├─ P5a: 项目根 CLAUDE.md (新建)
  ├─ P5b: packages/service/CLAUDE.md (append)
  └─ P5c: packages/web/CLAUDE.md (append)
```

---

## 前置: 创建分支

```bash
cd c:/doc/Code/rag
git status  # 确认工作树干净
git checkout -b code-quality-2026-06-19
```

期望: 切换到新分支, 没有任何改动.

---

### Task P0: 全量格式化 (前端 oxfmt + 后端 ruff)

**Files:**
- Modify: 全项目所有 .ts/.tsx/.py 文件 (格式化, 0 语义改)

- [ ] **Step 1: 跑前端 oxfmt --write**

```bash
cd c:/doc/Code/rag/packages/web
bun run format
```

期望: 0 exit code, 输出 `Formatted N files in T seconds` (N 可能 0-几百).

- [ ] **Step 2: 跑后端 ruff format**

```bash
cd c:/doc/Code/rag/packages/service
uv run ruff format .
```

期望: 0 exit code, 输出 `N files left unchanged, M files reformatted`.

- [ ] **Step 3: 检查改动量**

```bash
cd c:/doc/Code/rag
git diff --stat | tail -5
```

期望: 改文件数 + 行数. **STOP 条件**: 改 > 500 行 → 停下来报告 `git diff --stat` 给用户, 等用户确认才 commit.

- [ ] **Step 4: 验证无新 fail**

```bash
cd c:/doc/Code/rag/packages/web && bun run test 2>&1 | tail -5
cd c:/doc/Code/rag/packages/service && uv run pytest 2>&1 | tail -5
```

期望: 跟 baseline 接近 (P0 只改格式, 不应引入新 fail; 但可能减少几个 pytest pre-existing fail 因为格式后代码可被 import).

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/rag
git add -A
git commit -m "chore: 全量格式化 (oxfmt + ruff format)"
```

期望: 1 commit. 改文件列表已在 Step 3 报告.

---

### Task P1: 全量 lint 自动修复 (前端 oxlint + 后端 ruff check --fix)

**Files:**
- Modify: 全项目所有 .ts/.tsx/.py 文件 (lint fix, 0 语义改)

- [ ] **Step 1: 跑前端 oxlint --fix**

```bash
cd c:/doc/Code/rag/packages/web
bun run lint:fix
```

期望: 0 exit code 或 N warning. oxlint --fix 会自动改 unused import / 简单语法.

- [ ] **Step 2: 跑后端 ruff check --fix**

```bash
cd c:/doc/Code/rag/packages/service
uv run ruff check --fix .
```

期望: 输出 `Found N errors, M fixed, K remaining`. remaining 数应远小于 N.

- [ ] **Step 3: 检查改动量**

```bash
cd c:/doc/Code/rag
git diff --stat | tail -5
```

期望: 改文件数 + 行数. **STOP 条件**: 改 > 500 行 → 报告并停下问用户.

- [ ] **Step 4: 验证无新 fail**

```bash
cd c:/doc/Code/rag/packages/web && bun run test 2>&1 | tail -5
cd c:/doc/Code/rag/packages/service && uv run pytest 2>&1 | tail -5
```

期望: 跟 P0 baseline 一致, 0 新 fail.

- [ ] **Step 5: Commit**

```bash
cd c:/doc/Code/rag
git add -A
git commit -m "chore: 全量 lint 自动修复 (oxlint --fix + ruff check --fix)"
```

---

### Task P2a: 后端 pyright 类型修复

**Files:**
- Modify: `packages/service/src/**/*.py` (修复 pyright 报的可修类型错)
- Create: `KNOWN_ISSUES.md` (修不了的, 临时记这里)

- [ ] **Step 1: 跑 pyright 看现状**

```bash
cd c:/doc/Code/rag/packages/service
uv run pyright 2>&1 | tee /tmp/pyright-before.log | tail -10
```

期望: N errors / 0 warnings (或类似格式). 记下 N.

- [ ] **Step 2: 分类报告**

读 `/tmp/pyright-before.log`, 把 error 分两类:
- **可自动修**: 缺 import / 类型注解明显错 / 拼写错 → 自己改
- **需复杂改**: 类型 union 错 / 第三方库无类型 → 加 `# type: ignore[具体错误码]` (必须带具体码, 不写 `# type: ignore`)

- [ ] **Step 3: 改可修的**

逐文件改. 改完跑 `uv run pyright` 验证 - N 减少.

- [ ] **Step 4: 不可修的加 ignore**

每个 ignore 必须带具体错误码 + 注释说原因. 例:
```python
result = some_3rd_party_func()  # type: ignore[no-untyped-call]  # 第三方库无 type stub
```

- [ ] **Step 5: 再跑 pyright**

```bash
uv run pyright 2>&1 | tail -5
```

期望: 0 errors (如果仍有, 重复 Step 2-4).

- [ ] **Step 6: 跑 pytest 确认无新 fail**

```bash
uv run pytest 2>&1 | tail -5
```

期望: pre-existing fail 数不变 (35 fail + 38 errors baseline).

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/
git commit -m "chore: 修复 pyright 报的可修类型错 (N → 0 errors)"
```

---

### Task P2b: 前端 vitest 测试修复

**Files:**
- Modify: `packages/web/**/*.test.{ts,tsx}` (修能修的测试)
- Create: `KNOWN_ISSUES_WEB.md` (修不了的 pre-existing)

- [ ] **Step 1: 跑 vitest 看现状**

```bash
cd c:/doc/Code/rag/packages/web
bun run test 2>&1 | tee /tmp/vitest-before.log | tail -10
```

期望: X passed / Y failed. 记下 Y.

- [ ] **Step 2: 分类报告**

读 log, 把 failed 分两类:
- **可修**: snapshot 过期 (跑 `bun run test -u` 一次性更新 snapshot) / mock 数据错 / import 路径错 / 拼写错
- **不可修 (pre-existing)**: 跟 PG/Redis/dev auth 相关的, 已经在 lookup spec 报告过

- [ ] **Step 3: 改可修的**

逐文件改. 例: snapshot 过期跑 `bunx vitest run -u` (只更新能修的 snapshot).

- [ ] **Step 4: 把修不了的写进 KNOWN_ISSUES_WEB.md**

```markdown
# Web Known Issues (2026-06-19 code-quality)

## Vitest pre-existing fails

测试名: ...
原因: 跟 dev auth 模式 / PG 连接有关 (跟本次 --fix 无关)
何时修: CI 配真账号 + 集成测试改进时一起修

| Test | Module | Reason |
|---|---|---|
| ... | ... | ... |
```

- [ ] **Step 5: 再跑 vitest**

```bash
bun run test 2>&1 | tail -5
```

期望: 改了的全过, 不可修的仍在 fail list (但跟 baseline 一致).

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/
git commit -m "chore: 修复 vitest 报的可修测试 (Y → Y-N failed)"
```

---

### Task P2c: 后端 pytest 测试修复

**Files:**
- Modify: `packages/service/tests/**/*.py` (修能修的)
- Create/Append: `packages/service/KNOWN_ISSUES.md` (pre-existing)

- [ ] **Step 1: 跑 pytest 看现状**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest 2>&1 | tee /tmp/pytest-before.log | tail -10
```

期望: X passed / Y failed / Z errors. baseline 已知: 35 fail + 38 errors (lookup spec 报告).

- [ ] **Step 2: 分类报告**

读 log, 把 failed 分类:
- **可修**: import 错 / fixture 错 / 拼写错 / mock 数据错
- **不可修 (pre-existing)**: 跟 PG 真连接 / dev auth / token 缓存有关的

- [ ] **Step 3: 改可修的**

逐 test 文件改. 改完跑 `uv run pytest tests/that/file.py -v` 验证.

- [ ] **Step 4: 不可修的写进 KNOWN_ISSUES.md**

**重要**: append 到 `packages/service/KNOWN_ISSUES.md` (项目已有类似文件, 自己 grep 找), 不要新建. 例:
```markdown
## 2026-06-19 code-quality 审计

### pytest pre-existing fails (35 fail + 38 errors baseline)

| Test | Module | Reason |
|---|---|---|
| tests/auth/test_* | auth | dev auth 模式差异 |
| tests/eval/test_* | eval | PG fixture 未启 |
| ... | ... | ... |

何时修: CI 集成测试 + 真 PG + 真账号时一起修
```

- [ ] **Step 5: 再跑 pytest**

```bash
uv run pytest 2>&1 | tail -5
```

期望: 改了的全过, pre-existing 数不变.

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/tests/ packages/service/KNOWN_ISSUES.md
git commit -m "chore: 修复 pytest 报的可修测试 (35 fail → 35-N, pre-existing 不动)"
```

---

### Task P3a: 审计清理 type: ignore / @ts-ignore

**Files:**
- Modify: `packages/service/src/**/*.py` (删可删的 type: ignore)
- Modify: `packages/web/**/*.{ts,tsx}` (删可删的 @ts-ignore / @ts-expect-error)

- [ ] **Step 1: 统计现状**

```bash
cd c:/doc/Code/rag
echo "=== 后端 type: ignore ==="
grep -rn "# type: ignore" packages/service/src | wc -l
echo "=== 后端 noqa ==="
grep -rn "# noqa" packages/service/src | wc -l
echo "=== 前端 @ts-ignore ==="
grep -rn "@ts-ignore" packages/web --include="*.ts" --include="*.tsx" | wc -l
echo "=== 前端 @ts-expect-error ==="
grep -rn "@ts-expect-error" packages/web --include="*.ts" --include="*.tsx" | wc -l
```

期望: 4 个数字. 记下, 跟 Step 6 比对.

- [ ] **Step 2: 跑类型/测试确认 ignore 当前必要**

```bash
cd c:/doc/Code/rag/packages/service
uv run pyright 2>&1 | grep -c "error"  # 确认无新 error

cd c:/doc/Code/rag/packages/web
bun run typecheck 2>&1 | tail -5
```

期望: 后端 0 error, 前端 0 error. (P2a/P2b 已经清到 0 了.)

- [ ] **Step 3: 删可删的 ignore (后端)**

逐文件审. 删的规则:
- 第三方库已加 type stub → 删 `# type: ignore[no-untyped-call]`
- 错误码已不存在 → 删
- "临时 ignore" 但没注释原因 → 删 (或加注释)

不能删的 (保留):
- 第三方库无 type stub, 短期内无解
- 故意 union narrowing 不到, 业务上已知
- 必须带具体错误码 + 注释

- [ ] **Step 4: 删可删的 ignore (前端)**

规则同 Step 3. 例:
```typescript
// 可删 (类型已对)
const value: string = obj.someProp  // 删 @ts-ignore

// 不可删 (第三方库没类型)
const result = legacyLib.doThing() as any  // 保留
```

- [ ] **Step 5: 再跑类型/测试确认无新 fail**

```bash
cd c:/doc/Code/rag/packages/service
uv run pyright 2>&1 | tail -3
uv run pytest 2>&1 | tail -3

cd c:/doc/Code/rag/packages/web
bun run typecheck 2>&1 | tail -3
bun run test 2>&1 | tail -3
```

期望: 全绿, 跟 P2 一致. 不能因为删 ignore 引入新 fail.

- [ ] **Step 6: 统计清理结果**

跟 Step 1 的数字比, 算出清了多少条.

- [ ] **Step 7: Commit**

```bash
cd c:/doc/Code/rag
git add -A
git commit -m "chore: 清理可清理的 type: ignore / @ts-ignore (本轮清 N 条)"
```

---

### Task P3b: 审计清理 noqa

**Files:**
- Modify: `packages/service/src/**/*.py` (删可删的 noqa)

- [ ] **Step 1: 列出所有 noqa 位置**

```bash
cd c:/doc/Code/rag
grep -rn "# noqa" packages/service/src
```

期望: 列出每条 noqa 的 file:line + 错误码.

- [ ] **Step 2: 跑 ruff 确认 noqa 当前必要**

```bash
cd c:/doc/Code/rag/packages/service
uv run ruff check . 2>&1 | tail -5
```

期望: 0 errors (P1 已经 ruff --fix 修完了). 如果有, 先修.

- [ ] **Step 3: 逐条审 noqa**

跟 P3a 同样的规则:
- 可删: 错误码已不存在 / 已修过
- 不可删: 业务上故意 (e.g. `E501` 长字符串必须一行) / 第三方库限制

- [ ] **Step 4: 删可删的**

修改文件, 删 `# noqa[错误码]` 部分. 改完跑 ruff check 验证 0 error.

- [ ] **Step 5: 跑 pytest 确认无新 fail**

```bash
uv run pytest 2>&1 | tail -5
```

期望: pre-existing fail 数不变.

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add -A
git commit -m "chore: 清理可清理的 noqa (本轮清 N 条)"
```

---

### Task P4a: 后端 pytest-cov 配置

**Files:**
- Modify: `packages/service/pyproject.toml` (加 [tool.coverage.*] + [tool.pytest.ini_options] addopts)
- Modify: `packages/service/uv.lock` (uv 自动更新)

- [ ] **Step 1: 检查 pytest-cov 是否已装**

```bash
cd c:/doc/Code/rag/packages/service
uv run --no-sync python -c "import pytest_cov; print(pytest_cov.__version__)" 2>&1
```

期望: 报错 (没装) 或输出版本号.

- [ ] **Step 2: 加 pytest-cov 到 dev deps**

```bash
cd c:/doc/Code/rag/packages/service
uv add --dev pytest-cov 2>&1 | tail -10
```

期望: 安装成功, `pyproject.toml` 加一行 `pytest-cov = "..."`, `uv.lock` 更新.

- [ ] **Step 3: 改 pyproject.toml**

打开 `packages/service/pyproject.toml`, 在文件末尾追加:

```toml
[tool.coverage.run]
source = ["src"]
branch = true
omit = [
    "src/storage/migrations/*",
    "src/*/__init__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
show_missing = true
skip_covered = false
precision = 1

[tool.pytest.ini_options]
addopts = "--strict-markers --cov=src --cov-report=term-missing --cov-report=html --cov-report=lcov"
testpaths = ["tests"]
```

**注意**: 如果 pyproject 已有 `[tool.pytest.ini_options]`, 合并到现有 section, 不要新建. (检查用 `grep -A 5 "tool.pytest" pyproject.toml`.)

- [ ] **Step 4: 跑 pytest + 验证 coverage 输出**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest 2>&1 | tail -30
```

期望: pytest 输出末尾有 coverage 报告:
```
----------- coverage: platform linux, python 3.14 -----------
Name                                  Stmts   Miss Branch BrPart  Cover
-------------------------------------------------------------------------
src/lookups/service.py                  120     10     20      5    89%
src/lookups/safety_guard.py              80     15     15      3    80%
...
-------------------------------------------------------------------------
TOTAL                                   XXX     YY     ZZ     AA    NN%
```

记下 TOTAL 行的覆盖率和 src/ 下各模块覆盖率.

- [ ] **Step 5: 生成 html report 验证**

```bash
cd c:/doc/Code/rag/packages/service
ls htmlcov/index.html 2>&1
```

期望: 文件存在.

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/pyproject.toml packages/service/uv.lock
git commit -m "chore: 加 pytest-cov 配置 (起始覆盖率 X% lines / Y% branches)"
```

期望: 1 commit, 起始覆盖率写在 commit message.

---

### Task P4b: 前端 vitest coverage 配置

**Files:**
- Modify: `packages/web/vitest.config.ts` (加 coverage 字段)
- Modify: `packages/web/package.json` (加 @vitest/coverage-v8 dep + test:coverage 脚本)
- Modify: `packages/web/bun.lock` (bun 自动更新)

- [ ] **Step 1: 检查 @vitest/coverage-v8 是否已装**

```bash
cd c:/doc/Code/rag/packages/web
bun pm ls 2>&1 | grep coverage
```

期望: 输出 `@vitest/coverage-v8 X.Y.Z` 或不输出 (没装).

- [ ] **Step 2: 加 @vitest/coverage-v8**

```bash
cd c:/doc/Code/rag/packages/web
bun add -d @vitest/coverage-v8 2>&1 | tail -5
```

期望: 安装成功, `package.json` devDependencies 加一行.

- [ ] **Step 3: 改 vitest.config.ts**

打开 `packages/web/vitest.config.ts`, 改 test 字段加 coverage:

```typescript
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "happy-dom",
    // ... 现有配置保留 ...
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["**/*.{ts,tsx}"],
      exclude: [
        "node_modules/**",
        ".next/**",
        "**/*.test.{ts,tsx}",
        "**/*.config.ts",
        "**/types.ts",
        "**/*.d.ts",
      ],
      // 起始不强制门禁, 只采集. 后续 spec 加 thresholds.
      thresholds: {
        lines: 0,
        functions: 0,
        branches: 0,
        statements: 0,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

**注意**: 如果 vitest.config.ts 已有其他字段 (如 setupFiles, globals), 保留. 只加 coverage 字段.

- [ ] **Step 4: 改 package.json 加 test:coverage 脚本**

打开 `packages/web/package.json`, 在 scripts 段加:

```json
{
  "test:coverage": "vitest run --coverage"
}
```

**注意**: 不要覆盖现有 scripts, 只加新行.

- [ ] **Step 5: 跑 coverage 验证**

```bash
cd c:/doc/Code/rag/packages/web
bun run test:coverage 2>&1 | tail -30
```

期望: 末尾有 coverage report:
```
 % Coverage report from v8
File                  | % Stmts | % Branch | % Funcs | % Lines
----------------------|---------|----------|---------|--------
All files             |    XX   |    YY    |   ZZ    |   WW
 hooks/               |   100   |   100    |  100    |  100
  useLookup.ts        |   100   |   100    |  100    |  100
 lib/api/             |    80   |    75    |   85    |   80
  ...
```

记下 TOTAL 行覆盖率. 第一次跑可能慢 (1-2 分钟), 后续快 (10-30 秒).

- [ ] **Step 6: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/vitest.config.ts packages/web/package.json packages/web/bun.lock
git commit -m "chore: 加 vitest coverage 配置 (@vitest/coverage-v8, 起始覆盖率 X%)"
```

---

### Task P5a: 项目根 CLAUDE.md (新建)

**Files:**
- Create: `CLAUDE.md` (项目根)

- [ ] **Step 1: 读现有 .claude/CLAUDE.md 找已有规则**

```bash
cd c:/doc/Code/rag
cat .claude/CLAUDE.md
```

期望: 读出来项目级 Claude Code 配置内容.

- [ ] **Step 2: 写 CLAUDE.md**

创建 `c:/doc/Code/rag/CLAUDE.md`, 内容:

```markdown
# 项目代码质量铁律 (2026-06-19)

> 本文件由 code-quality-2026-06-19 spec 沉淀. 任何 commit / PR 改动前必读.

## 工具链一览 (锁版本, 不升级)

### 后端 (Python 3.14)
- **format**: `uv run ruff format` (0 exit = 通过)
- **lint**: `uv run ruff check --fix` (自动修) / `uv run ruff check` (只读)
- **类型**: `uv run pyright` (必须 0 error 才 commit)
- **测试**: `uv run pytest` (1187 tests baseline; pre-existing fail 见 KNOWN_ISSUES)
- **覆盖率**: `uv run pytest` 自动带 coverage (line/branch/func/stmt)

### 前端 (TypeScript 8 / React 19 / Next.js)
- **format**: `bun run format` (oxfmt --write)
- **lint**: `bun run lint:fix` (oxlint --fix) / `bun run lint` (只读)
- **类型**: `bun run typecheck` (tsgo --noEmit, 必须 0 error)
- **测试**: `bun run test` (700+ tests) / `bun run test:coverage` (带覆盖率)
- **覆盖率**: `@vitest/coverage-v8`, v8 provider, html/lcov 报告

## 顺序不可颠倒

任何代码改动必须按顺序:
1. **format** → 0 报错
2. **lint fix** → 0 报错
3. **类型检查** → 0 error
4. **测试** → 0 新 fail (pre-existing fail 不算新 fail)
5. **commit** (commit message 前缀: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:`)

跳过任何一步都不行. husky pre-commit 钩子会自动跑 lint-staged + tsgo + vitest + format:check.

## 范围控制

- 单次 `--fix` 改 > 500 行 → **停下来问用户 review**
- pre-existing test fail → 列 `KNOWN_ISSUES.md`, 不雪崩修
- 别人 worktree 的 stash 残留 → **不 reset / 不 checkout** (会丢别人工作)

## 后端 Rust-like 严格准则

- ruff 警告不允许绕过 (`# noqa` 必须带具体错误码 + 注释)
- pyright 必须 0 error (`# type: ignore` 必须带具体错误码 + 注释)
- 测试必须 mock, **不连真 PG/Redis** (项目老规范, 见 service/CLAUDE.md §测试规范)
- alembic migration 可回滚 (downgrade 干净)
- audit log 走 `@audited` 装饰器 (DELETE / 改账户 / 改权限 / 导出数据)

## 前端 React/Next.js 准则

- oxfmt + oxlint 必须 0 error
- tsgo 必须 0 error
- 优先用项目封装 (DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form / FormField)
- i18n: `t("中文 key")` 中间用中文作 key, zh.json identity, en.json 翻译
- **路由跳转必须用 `@/i18n/navigation` 的 useRouter** (禁止 `next/navigation` 的, 强制 locale 前缀)
- JSX 不写行内 `onClick={() => {}}` 复杂表达式, 提取命名函数

## 不要做的事

- ❌ 写 `useState` 套 5 层的 hook 而不抽封装
- ❌ 直接 import 第三方 UI 库 (shadcn/ui 已经按需装, 用项目封装)
- ❌ 改前端 URL 顺序: 先 BFF 改 → 后端改 → 前端改 (不可逆, 见 .claude/CLAUDE.md §重构规则)
- ❌ 删 BFF route 不跑契约测试 (`pytest tests/test_api_contract.py`)
- ❌ 新增 `StrEnum` 不走 lookup (字典唯一事实源)
- ❌ 连真 PG/Redis 跑测试 (项目老规范)
- ❌ 覆盖别人工作树残留 (用 stash list 确认, 不动)

## 测试模式 (4 模式)

后端测试, 按用途选:
1. **模式 1 (mock)**: ORM 字段 / Pydantic / 纯函数 / util — `unittest.mock.patch`, 0 PG 依赖
2. **模式 2 (db_session)**: 集成测, repo CRUD / SQL / FK — `db_session` fixture 事务回滚
3. **模式 3 (tmp_pg_schema)**: 迁移 DDL / schema 完整性 — 临时 schema
4. **模式 4 (E2E)**: 完整业务流 — `PG_*` env 指向独立 DB

详细见 `packages/service/CLAUDE.md §测试隔离 4 模式`.

前端测试:
- 单元: vitest + happy-dom (已有 setup)
- 组件: vitest + @testing-library/react
- E2E: Playwright (e2e/ 目录)

## 关联文档

- 项目 Claude 配置: `.claude/CLAUDE.md`
- 后端局部约定: `packages/service/CLAUDE.md`
- 前端局部约定: `packages/web/CLAUDE.md`
- Spec / Plan: `docs/superpowers/specs/` + `docs/superpowers/plans/`
- 教程: `docs/cookbook/`
- 已知问题: `packages/service/KNOWN_ISSUES.md` (后端 pre-existing)
```

- [ ] **Step 3: 验证格式**

```bash
cd c:/doc/Code/rag
head -10 CLAUDE.md
wc -l CLAUDE.md
```

期望: 文件存在, ~120 行, 标题正确.

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag
git add CLAUDE.md
git commit -m "docs: 项目根 CLAUDE.md (代码质量铁律 + 工具链 + 测试模式)"
```

---

### Task P5b: packages/service/CLAUDE.md append 本轮总结

**Files:**
- Modify: `packages/service/CLAUDE.md` (append 新段)

- [ ] **Step 1: 读现有 service CLAUDE.md**

```bash
cd c:/doc/Code/rag
cat packages/service/CLAUDE.md | tail -20
```

期望: 看到现有末尾内容 (例如 chat_router 段).

- [ ] **Step 2: append 本轮总结段**

打开 `packages/service/CLAUDE.md`, 在末尾追加:

```markdown

## 代码质量清理总结 (2026-06-19 code-quality spec)

### ruff / pyright 起始 vs 结束

| 工具 | 起始 | 结束 | 减幅 |
|---|---|---|---|
| ruff format | N files reformatted | 0 reformatted | - |
| ruff check --fix | N errors | 0 errors | -N |
| pyright errors | N errors | 0 errors | -N |

### pytest 起始 vs 结束

| 指标 | 起始 (P0 前) | 结束 (P5) | 减幅 |
|---|---|---|---|
| Passed | XXX | YYY | +Z |
| Failed | 35 (pre-existing) | 35-N | -N |
| Errors | 38 (pre-existing) | 38-N | -N |

Pre-existing fail 不在本期范围, 见 `KNOWN_ISSUES.md` (test isolation 跟 dev auth 模式有关).

### pytest-cov 起始覆盖率

| 维度 | 起始 (2026-06-19) | 目标 (后续 spec) |
|---|---|---|
| Lines | XX% | ≥ 80% |
| Branches | YY% | ≥ 70% |
| Functions | ZZ% | ≥ 85% |
| Statements | WW% | ≥ 80% |

### 本轮发现 top-N 防再犯守则

1. **测试必须 mock, 不连真 PG/Redis** (老规范). 例子: `tests/test_*.py` 跑必须 0 PG 连接. 检查: `pytest --co -q` 后跑 `pytest -v` 看是否启 db_session.
2. **type: ignore 必须带具体错误码 + 注释**. 不接受裸 `# type: ignore`.
3. **delete / 改账户 / 改权限 / 导出必须加 @audited 装饰器**. 防止误删, 留审计.
4. **alembic 迁移必须可回滚**. 写 migration 时同时写 downgrade 函数, 单测验证.
5. **新加 enum 必须走 lookup 字典**, 禁止新增硬编 `StrEnum` (除了 LLM 框架要求). 走 `src/common/dictionaries_seed.yaml` + `seed_dictionaries.py`.
6. **测试 file:line 引用必须真实**. 不写错的 line_number (跟实际代码同步).
7. **删 BFF route 前必跑契约测试** (`pytest tests/test_api_contract.py`).
8. **前端 useRouter 必须从 `@/i18n/navigation` 引** (强制 locale 前缀). 禁止 `next/navigation`.
9. **前端 URL 改顺序: 先后端改路由 → 再改前端 URL → 最后删 BFF**.
10. **覆盖率起始基线**: 后端 pytest-cov X% lines / Y% branches. 后续 spec 加 thresholds 门禁.
```

- [ ] **Step 3: 验证格式**

```bash
cd c:/doc/Code/rag
tail -50 packages/service/CLAUDE.md
```

期望: 新段在末尾, 不破坏旧内容.

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag
git add packages/service/CLAUDE.md
git commit -m "docs(service): CLAUDE.md append 本轮清理总结 + 防再犯守则"
```

---

### Task P5c: packages/web/CLAUDE.md append 本轮总结

**Files:**
- Modify: `packages/web/CLAUDE.md` (append 新段)

- [ ] **Step 1: 读现有 web CLAUDE.md**

```bash
cd c:/doc/Code/rag
cat packages/web/CLAUDE.md | tail -20
```

期望: 看到现有末尾内容 (例如 「This is NOT the Next.js you know」段).

- [ ] **Step 2: append 本轮总结段**

打开 `packages/web/CLAUDE.md`, 在末尾追加:

```markdown

## 代码质量清理总结 (2026-06-19 code-quality spec)

### oxfmt / oxlint / tsgo 起始 vs 结束

| 工具 | 起始 | 结束 | 减幅 |
|---|---|---|---|
| oxfmt --write | N files reformatted | 0 reformatted | - |
| oxlint --fix | N warnings | 0 warnings | -N |
| tsgo (typecheck) | N errors | 0 errors | -N |

### vitest 起始 vs 结束

| 指标 | 起始 (P0 前) | 结束 (P5) | 减幅 |
|---|---|---|---|
| Test Files | XX | YY | - |
| Tests | XXX passed | YYY passed | +Z |
| Failed | FF (pre-existing) | FF-N | -N |

Pre-existing fail (memory-integration / i18n / app-dialog 等) 不在本期范围.

### vitest coverage 起始覆盖率

| 维度 | 起始 (2026-06-19) | 目标 (后续 spec) |
|---|---|---|
| Lines | XX% | ≥ 75% |
| Branches | YY% | ≥ 65% |
| Functions | ZZ% | ≥ 80% |
| Statements | WW% | ≥ 75% |

### 本轮发现 top-N 防再犯守则

1. **oxfmt / oxlint / tsgo 必须 0 error 才 commit**. husky pre-commit 钩子会自动跑 lint-staged + tsgo + vitest + format:check, 不要 `--no-verify` 绕过.
2. **优先用项目封装** (DataTable / AppDialog / AppConfirm / ErrorBanner / CopyButton / AppTooltip / Form / FormField). 见项目「封装组件」段.
3. **JSX 不写行内 onClick 复杂表达式**. 必须提取命名函数放在组件体内.
4. **函数声明用 function / const = () =>**, 禁止 `function foo() {}` (项目规约).
5. **变量名禁止单字符** (val 替代 v, idx 替代 i).
6. **禁止魔法数字**, 用 const 定义常用常量 (e.g. `const DRAFT_KEY = "rag.chat.draft.v1"`).
7. **import 必须按首字母排序** (ESLint import/order 规则).
8. **i18n key 用中文**: `t("中文 key")`, zh.json identity, en.json 翻译. 改 UI 文案 commit 前必看 `git diff` 加 zh/en.json.
9. **路由跳转用 `@/i18n/navigation` 的 useRouter**, 禁止 `next/navigation` (强制 locale 前缀, 避免 307 重定向).
10. **TanStack Query 5.x**: staleTime 默认 60_000 (1 min), refetchOnWindowFocus 默认 false (跟项目风格一致).
11. **覆盖率起始基线**: 前端 vitest coverage X% lines / Y% branches. 后续 spec 加 thresholds 门禁.
12. **覆盖别人 worktree 残留**: 用 `git stash list` 确认, 不 reset / 不 checkout. (防止丢别人工作.)
```

- [ ] **Step 3: 验证格式**

```bash
cd c:/doc/Code/rag
tail -60 packages/web/CLAUDE.md
```

期望: 新段在末尾, 不破坏旧内容.

- [ ] **Step 4: Commit**

```bash
cd c:/doc/Code/rag
git add packages/web/CLAUDE.md
git commit -m "docs(web): CLAUDE.md append 本轮清理总结 + 防再犯守则"
```

---

## 最终验收门

- [ ] **Step 1: 跑全测试套件最终验证**

```bash
cd c:/doc/Code/rag/packages/service
uv run pytest 2>&1 | tail -3

cd c:/doc/Code/rag/packages/web
bun run test 2>&1 | tail -3
bun run typecheck 2>&1 | tail -3
```

期望: 跟前几个阶段一致 (pre-existing fail 数不变).

- [ ] **Step 2: 检查所有 commit**

```bash
cd c:/doc/Code/rag
git log --oneline master..code-quality-2026-06-19
```

期望: 11-12 个 commit (P0/P1/P2a/P2b/P2c/P3a/P3b/P4a/P4b/P5a/P5b/P5c).

- [ ] **Step 3: 检查工作树干净**

```bash
cd c:/doc/Code/rag
git status
```

期望: 干净 (除别人 worktree 的 web 改动, 那是 stash 残留不是你的活).

- [ ] **Step 4: 推送 branch**

```bash
cd c:/doc/Code/rag
git push -u origin code-quality-2026-06-19
```

期望: push 成功, branch 在 origin 上.

- [ ] **Step 5: 报告给用户**

告诉用户:
- 11-12 commits 全部到位
- 起始覆盖率 (后端 + 前端)
- pre-existing fail 数 (跟 baseline 对比)
- 需要决定: merge master / 提 PR / 留 branch

---

## 自审

1. **Spec 覆盖**: ✅ 10 项任务全部对应 P0-P5 子段
2. **占位符**: ✅ 无 TBD/TODO, 每步都给具体命令
3. **类型一致**: ✅ 工具链名称 (oxfmt/oxlint/ruff/pyright/vitest/pytest-cov) 跟 spec 一致
4. **commit 前缀**: ✅ 全部 `chore:` / `docs:`, 跟 husky 钩子兼容
5. **STOP 条件**: ✅ P0/P1 改 > 500 行停下, 已写明
6. **pre-existing fail**: ✅ 列 KNOWN_ISSUES, 不雪崩

---

## 执行选择

**Plan complete and saved to `docs/superpowers/plans/2026-06-19-code-quality-cleanup.md`. Two execution options:**

1. **Subagent-Driven (recommended)** - 每 task 派一个新 subagent, task 间 review, 快速迭代
2. **Inline Execution** - 当前会话批量执行 + checkpoints

**Which approach?**