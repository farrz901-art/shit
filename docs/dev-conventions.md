# 开发规范

## 测试

### 后端 (Python)

```bash
uv run pytest tests/                      # 跑全部
uv run pytest tests/ -m "not slow"        # 跑非 slow 测试
uv run pytest tests/product_decoders/     # 跑产品解析器
uv run pytest tests/rag/                  # 跑 RAG 流水线
uv run pytest tests/test_kg_*.py          # 跑知识图谱 38 个 (PR 1-8)
```

测试位置：跟源码镜像（`src/rag/ingest/pipeline.py` → `tests/rag/ingest/test_pipeline.py`）。

### 前端 (TypeScript / React)

```bash
# 单元测试 (vitest + jsdom, 49 用例)
cd web && bun run test          # 一次性
cd web && bun run test:watch    # watch

# E2E (Playwright + chromium, 18 用例)
cd web && bun run test:e2e      # 一次性 (自动起 next dev + 后端)
cd web && bun run test:e2e:ui   # UI 模式
```

- **单元测试**: 跟实现文件同目录, 后缀 `.test.ts` / `.test.tsx`
- **E2E**: 集中放 `web/e2e/`, 后缀 `.spec.ts`
- 详见 [web/CLAUDE.md](../web/CLAUDE.md) + [web-e2e.md](web-e2e.md)

## 编码规范

### 后端 (Python)

- **中文注释**：所有代码注释用中文
- **中文日志**：所有 `print(...)` / `logging.*` 用中文
- **不删注释**：改代码时保留所有原有注释
- **TDD 流程**：先红 → 绿 → 重构
- **函数/类 ≤ 100 行**: 拆细

### 前端 (TypeScript)

- **`satisfies` 关键字**: 类型配置 (如 shadcn variants)
- **function 声明式**: `function Foo() {}` 而非 `const Foo = () => {}`
- **`cn()` 工具**: 组合类名从 `@/lib/utils`
- **Zod 验证**: 运行时 schema 镜像 YAML
- **.js → .ts**: 新代码全部 TS

## 依赖管理

### 后端

- 用 `uv run` 跑 Python（确保依赖一致）
- 实施完成时核对 `pyproject.toml` dependencies 跟实际 import 匹配
- 验证包用 `import` 而非 `pip show`

### 前端

- 用 `bun` (不用 npm/pnpm/yarn)
- 装包: `bun install` (自动写 `bun.lock` 入库)

## 设计文档 & 实施计划

- 设计文档：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- 实施计划：`docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- 都提交 git
- 例: [knowledge-management-page-design.md](superpowers/specs/2026-06-08-knowledge-management-page-design.md)

## shim 禁令

**严禁**写 shim / 兼容代码 / 兜底包装。**新项目零技术债**。

包括但不限于：
- "旧 API 兼容 shim"（新项目没旧 API）
- "未来可能用到的抽象"
- "如果 A 失败就 fallback 到 B"（除非有真实用户场景）
- "反射测试"（测 `xxx_NOT_importable` 这种"不存在"的属性）

每个决策都要能回答"为什么"。惯例或模板出发前先停下来想"原始需求是什么"。

## 调试原则

- 区分不同根因，别用最简单的解释掩盖真正问题
- 外部系统 bug 修复必须真实端到端验证，不信 mock
- 测加密 / 压缩 / IO 路径要测真行为，不是"不崩"
- E2E 发现的 bug, 修完写 E2E 用例防回归 (见 [web-e2e.md § 已修复的 Bug](web-e2e.md))

## 已知工程坑 (踩过的)

- **Tailwind v4 仍需 postcss.config** — 漏配 → CSS 0 字节, 页面裸 HTML, 见 [web/CLAUDE.md](../web/CLAUDE.md#样式约定)
- **uv run 在 Windows worktree 路径上会失败** — 用 `.venv/Scripts/python.exe` 直跑, 见 [web-e2e.md § 3](web-e2e.md#3-用-venv-python-不用-uv-run)
- **SQLite Windows file lock** — 单连接 + `PRAGMA journal_mode=DELETE` + `check_same_thread=False` + `timeout=10`

