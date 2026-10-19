# Code Quality 全量清理 + Coverage 检测 + CLAUDE.md 总结 (2026-06-19)

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：以 `c:/doc/Code/rag` 仓库当前 master (07bda92) 为准
> 🎯 范围：在新分支跑全量格式化/lint/test/类型/coverage 修复，把本轮发现的问题总结进 3 个 CLAUDE.md

---

## 一、目标 & 范围

**目标**：跑全 6 个工具链（oxfmt/oxlint/ruff/pyright/pytest/vitest），修能修的，加 coverage 检测，最后把本轮发现的 top-N 问题沉淀到 CLAUDE.md 防再犯。

**核心约束**：
- ✅ 全在 `code-quality-2026-06-19` 新分支跑，不污染 master 的 11 个 lookup commit
- ✅ 顺序前到后（format → lint → 类型 → 测试 → coverage → 文档）
- ✅ 修能修的，修不了列 known issues（不雪崩）
- ✅ 大范围改动（>500 行/阶段）停下来问用户 review
- ❌ 不升级任何工具版本
- ❌ 不改 CI/CD（后续 spec 处理）
- ❌ 不强制修 pre-existing fail

---

## 二、任务依赖关系

```
P0 (格式化)
  ↓
P1 (lint fix)
  ↓
P2 (类型 + 测试)
  ├─ P2a: pyright (后端类型)
  ├─ P2b: vitest (前端测试)
  └─ P2c: pytest (后端测试)
  ↓
P3 (清理 ignore/noqa)
  ├─ P3a: type: ignore / @ts-ignore 审计
  └─ P3b: noqa 审计
  ↓
P4 (coverage 配置)
  ├─ P4a: pytest-cov 配置
  └─ P4b: vitest coverage 配置
  ↓
P5 (CLAUDE.md 沉淀)
  ├─ P5a: 项目根 CLAUDE.md (新建)
  ├─ P5b: packages/service/CLAUDE.md (append)
  └─ P5c: packages/web/CLAUDE.md (append)
```

---

## 三、每个阶段的执行规范

### P0 - 全量格式化

**前端**：
```bash
cd packages/web
bun run format       # oxfmt --write
```

**后端**：
```bash
cd packages/service
uv run ruff format .
```

**预期**：
- 改动行数可能 100-1000 行（仅空白/缩进/引号）
- 0 语义变化
- 一个 commit: `chore: 全量格式化 (oxfmt + ruff)`

### P1 - 全量 lint fix

**前端**：
```bash
cd packages/web
bun run lint:fix     # oxlint --fix
```

**后端**：
```bash
cd packages/service
uv run ruff check --fix .
uv run ruff check --fix --unsafe-extras .   # 安全类 fix（可选）
```

**预期**：
- oxlint 可能改 50-500 行（unused import / console.log / 简单语法）
- ruff 可能改 100-300 行（import 排序 / 未使用变量）
- 0 语义变化
- 一个 commit: `chore: 全量 lint 自动修复 (oxlint + ruff)`

**STOP 条件**：单工具改 > 500 行 → 报告并停下问用户。

### P2 - 类型 + 测试

#### P2a - pyright (后端类型)

```bash
cd packages/service
uv run pyright | tee /tmp/pyright.log
```

修能修的（缺 import / 类型错），修不了写 `# type: ignore[xxx]`（必须带具体错误码）。

#### P2b - vitest (前端测试)

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/vitest.log
```

修能修的（snapshot 过期 / 拼写错），修不了列 known issues。

#### P2c - pytest (后端测试)

```bash
cd packages/service
uv run pytest 2>&1 | tee /tmp/pytest.log
```

**Pre-existing 已知**（lookup spec 已报告）：
- 35 fail + 38 errors（auth/eval/memory/invite 等模块，跟 PG/dev auth 模式有关）
- 不在本期范围

每个 P2 子阶段一个 commit：`chore: 修复 {vitest|pyright|pytest} 报的可修问题`

### P3 - 清理 ignore / noqa

#### P3a - 审计 type: ignore / @ts-ignore

```bash
# 后端
grep -rn "# type: ignore" packages/service/src | wc -l
grep -rn "# noqa" packages/service/src | wc -l

# 前端
grep -rn "@ts-ignore" packages/web --include="*.ts" --include="*.tsx" | wc -l
grep -rn "@ts-expect-error" packages/web --include="*.ts" --include="*.tsx" | wc -l
```

逐条审：能删的删（比如 import 已修，ignore 没用了），必须留的加注释说原因。

#### P3b - 审计 noqa

同上，逐条审。

一个 commit：`chore: 清理可清理的 type: ignore / noqa (本轮清理 N 条)`

### P4 - Coverage 检测配置

#### P4a - 后端 pytest-cov

改 `packages/service/pyproject.toml`：
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
]
show_missing = true
skip_covered = false

[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-report=html --cov-report=lcov"
```

加 `pytest-cov` 到 `[dependency-groups]` 或 `[project.optional-dependencies.test]`。

#### P4b - 前端 vitest coverage

改 `packages/web/vitest.config.ts`：
```typescript
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "happy-dom",
    // ... 现有 config
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
      ],
      thresholds: {
        // 不强制门禁, 仅展示当前覆盖率 (后续 spec 加门禁)
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

加 `@vitest/coverage-v8` 到 devDependencies。

加 `package.json` 脚本：
```json
{
  "test:coverage": "vitest run --coverage"
}
```

一个 commit：`chore: 加 pytest-cov + vitest coverage 配置 (起步基线)`

### P5 - CLAUDE.md 沉淀

#### P5a - 项目根 CLAUDE.md（新建）

内容大纲：
1. **代码质量铁律**（全局）
   - format → lint → 类型 → 测试 → commit 顺序不可颠倒
   - 改 > 500 行停下问用户
   - pre-existing fail 列 known issues，不雪崩
2. **后端 Rust-like 严格准则**
   - ruff 不可绕过
   - pyright 必须 0 error 才 commit
   - 测试必须 mock（不连真 PG/Redis，参考 4 测试模式）
3. **前端 React/Next.js 准则**
   - oxfmt + oxlint 必须 0 error
   - tsgo 必须 0 error
   - 优先用项目封装（DataTable / AppDialog / ErrorBanner 等）

#### P5b - packages/service/CLAUDE.md append

「本轮清理 top-N 总结」段：
- 修了多少 ruff 警告
- 修了多少 pyright 类型错
- pytest 当前 baseline（X passed / Y pre-existing fail）
- pytest-cov 起始覆盖率（行/函数/分支）

#### P5c - packages/web/CLAUDE.md append

「本轮清理 top-N 总结」段：
- 修了多少 oxfmt 格式问题
- 修了多少 oxlint 警告
- vitest 当前 baseline（X passed / Y pre-existing fail）
- vitest coverage 起始覆盖率

**每个 P5 子段一个 commit**。

---

## 四、关键文件

| 文件 | 类型 | 说明 |
|---|---|---|
| `CLAUDE.md` | 新建 | 项目根全局代码质量规范 |
| `packages/service/pyproject.toml` | 改 | 加 pytest-cov 配置 |
| `packages/service/CLAUDE.md` | 改 | append 本轮总结 |
| `packages/web/vitest.config.ts` | 改 | 加 coverage 字段 |
| `packages/web/package.json` | 改 | 加 test:coverage 脚本 + @vitest/coverage-v8 依赖 |
| `packages/web/CLAUDE.md` | 改 | append 本轮总结 |

---

## 五、风险 & 缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|------|------|------|
| R1 | oxfmt/oxlint 改几万行 | 中 | 高 | 单阶段 >500 行停下问用户 |
| R2 | pyright 升级引发连锁 | 低 | 中 | 不升级, 用项目锁版本 |
| R3 | pytest pre-existing fail 雪崩 | 高 | 中 | 列 known issues, 不进 commit |
| R4 | coverage 配置导致 CI 慢 | 低 | 中 | 起始不强制阈值, 只采集 |
| R5 | noqa 大量遗留清理不掉 | 中 | 中 | 逐条 audit, 必须保留的加注释 |
| R6 | vitest coverage 解析 tsx 慢 | 低 | 低 | 用 v8 provider 不用 istanbul |
| R7 | 跟 master 的 lookup commit 冲突 | 低 | 高 | 全在新分支, 最后 PR 合回 |

---

## 六、验收门

每阶段结束：
- [ ] `git diff --stat` 报告改动量
- [ ] 跑 1 次完整测试套件验证无新 fail
- [ ] 改 > 500 行的阶段停下问用户

P5 结束（最终验收）：
- [ ] 3 个 CLAUDE.md 全部含「本轮 top-N 问题 + 防再犯守则」段
- [ ] 后端 `pytest-cov` baseline 采集成功
- [ ] 前端 `vitest --coverage` baseline 采集成功
- [ ] `code-quality-2026-06-19` branch 推到 origin
- [ ] 跟 master 提 PR

---

## 七、不做（明确范围外）

- ❌ 不升级 ruff/pyright/oxlint/oxfmt/vitest 任何版本
- ❌ 不改 CI/CD workflow
- ❌ 不强制修复所有 pre-existing test fail
- ❌ 不动 master 的 11 个 lookup commit
- ❌ 不做 E2E coverage（Playwright，本期只 unit + 集成）
- ❌ 不强制 coverage 门禁（只采集，不阻断 PR）
- ❌ 不清理别人 worktree 的 stash 残留

---

## 八、参考

- **oxfmt 文档**：https://oxc.rs/docs/guide/usage/formatter.html
- **oxlint 文档**：https://oxc.rs/docs/guide/usage/linter/rules.html
- **ruff 文档**：https://docs.astral.sh/ruff/
- **pyright 文档**：https://microsoft.github.io/pyright/
- **pytest-cov 文档**：https://pytest-cov.readthedocs.io/
- **vitest coverage 文档**：https://vitest.dev/guide/coverage.html