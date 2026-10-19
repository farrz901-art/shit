# 代码质量快照扫描设计 (2026-06-25)

> 状态: 设计中
> 范围: 后端 (packages/service) + 前端 (packages/web)
> 目标: 扫出 pytest/vitest fail + pyright type:ignore + lint ignore + pyright 严格模式可行性, 不修任何代码
> 交付: 5 份审计报告 + 1 份路线图

---

## 1. 背景

项目刚完成 60 条 finding 的全栈审计修复 (2026-06-24)，代码质量有显著提升。
现在需要一次 "快照扫描"：系统性地找出：

1. 全部测试遗留 bug (pytest + vitest)
2. 全部 `# type: ignore` 哪些可删可升
3. 全部 `eslint-disable` / `oxlint-disable` / `# noqa` 哪些可删可降
4. pyright 从 basic 渐近到 strict 的可行性

---

## 2. 总体架构

```
Phase 1: 4 路并行扫描 (4 个 Explore agent, 严格只读)
  ├─ A1: Test Scanner   → docs/audit/2026-06-25-test-failures.md
  ├─ A2: Pyright Scan   → docs/audit/2026-06-25-pyright-ignores.md
  ├─ A3: Lint Scan      → docs/audit/2026-06-25-lint-ignores.md
  └─ A4: Pyright Strict → docs/audit/2026-06-25-pyright-strict-audit.md

Phase 2: 主线程 synthesize
  └─ 4 份报告 → 去重合并 → docs/audit/2026-06-25-code-quality-plan.md
  └─ 更新 docs/audit/2026-06-24-findings.md (追加质量改进项)

Phase 3: 用户 review 路线图 → 决定哪些进入后续 spec
```

---

## 3. A1: Test Scanner

### 范围
- 后端: `cd packages/service && uv run pytest -v --tb=short`
- 前端: `cd packages/web && bun run test --reporter=verbose`

### 分类体系

| 类别 | 标签 | 处理 |
|---|---|---|
| Pre-existing infra | `[env]` | PG/Redis 未起、docker 未运行 |
| Pre-existing bug | `[bug]` | 真实 bug，已知未修 |
| Regression | `[regression]` | 之前 32 个 commit 引入 |
| Flaky | `[flaky]` | 偶发失败 |
| Configuration | `[config]` | 测试配置错误 |
| **连真 PG 违规** | `[pg-violation]` | **违反项目强制规范, 须重写为模式 1 mock** |

### 产出格式

每条 failure:

```markdown
### [bug] test_auth_router.py::test_login_with_invalid_email

- **文件**: `tests/auth/test_router.py:123`
- **错误**: `AssertionError: assert 200 == 422`
- **推测根因**: Pydantic schema 没校验 email 格式
- **上下文**: response_model 定义缺 email validator
```

### agent 指令
- 跑 `uv run pytest -v --tb=short` 截取全部 FAILED/ERROR
- 前端 `bun run test 2>&1` 截取全部 FAILED
- 对每条 failure: `Read` 测试文件 + 相关业务代码，给 root cause 推测
- 工具调用 ≤ 25 次

### 检出连真 PG 的测试 (专项)

**背景**: 项目 CLAUDE.md §测试隔离 4 模式 强制 — 所有 test 禁止直连 PG/Redis，必须 mock session_scope / get_redis。违者须重写为模式 1 (mock)。

**agent 识别方法**:
1. 跑 `uv run pytest -v --tb=short` 后，找 failures 里包含 `psycopg` / `OperationalError` / `connection refused` / `FATAL` 字样的错误
2. `Grep "db_session\|session_scope\|create_engine\|SQLALCHEMY_DATABASE_URL\|RAG_DB_URL\|PG_HOST\|PG_DATABASE"` 在 `tests/` 目录
3. `Grep "pytest.mark.integration"` — 集成测试标记
4. 对每处: Read 测试文件 → 判断是模式 2 (db_session fixtrue, 事务回滚, opt-in) 还是真连 PG 的违规模式

**标注**: 标 `[pg-violation]` + 写明"须重写为模式 1 mock, 禁止直连 PG"

**产出追加段**:

```markdown
## 连真 PG 违规清单

| 文件 | 行号 | 违规类型 | 建议 |
|---|---|---|---|
| `tests/integration/test_db_session_fixture.py:12` | `db_session` fixtrue | 模式 2 集成测试, 可接受 (opt-in) |
| `tests/auth/test_router.py:xx` | `session_scope()` 直调 | [pg-violation] 须重写为 mock session |
```

---

## 4. A2: Pyright ignore Scanner

### 范围
- 78 处 `# type: ignore` (43 `src/` + 35 `tests/`)

### 分类体系

| 类别 | 标签 | 含义 |
|---|---|---|
| 可修复 | `[fixable]` | 改代码就能去掉 |
| 必须保留 (stub) | `[stub]` | 第三方库无 stub / ORM 限制 |
| 规则升级预警 | `[rule-up]` | 升 rule level 时会炸 |
| 已过期 | `[dead]` | 不再需要的 ignore |

### agent 对每条 ignore 的执行
1. `Read` 该行 + 上下文 20 行
2. 在 `pyrightconfig.json` 不做改动的假设下，尝试删这条 ignore
3. 删后跑 `uv run pyright {file}` 看是否依然报错
4. 如果不报了 → `[dead]`
5. 如果报错 → 看报什么: 第三方 stub 问题 → `[stub]`; 自己代码问题 → `[fixable]` + 给出改法

### 特殊关注
- `tests/` 里的 35 处 `type: ignore` — 按 CLAUDE.md 规约**必须带具体错误码**
- 检查哪些 tests/ 里的 ignore 是裸 `# type: ignore` (之前 ARCH-004 只改了 src/ 的 2 处, 没改 tests/ 的)

### 产出格式

```markdown
| ID | file:line | 代码 | 标签 | 备注 |
|---|---|---|---|---|
| PYR-001 | src/chat/service.py:307 | `.rowcount  # type: ignore[attr-defined]` | [stub] | SQLAlchemy 推断限制 |
| PYR-002 | tests/lookups/test_audit.py:47 | `...  # type: ignore` | [fixable] | 裸 ignore, 应加 `[reportArgumentType]` |
```

### agent 指令
- 工具调用 ≤ 30 次 (78 处不可能全测, 测前 30 处 + 标注 skip)
- pyright 每次调用 `.py` 单个文件, 不跑全量

---

## 5. A3: Lint ignore Scanner

### 范围
- 172 处 `eslint-disable` / `oxlint-disable` (web/)
- 23 处 `# noqa` (service/)

### 分类体系

| 类别 | 标签 | 含义 |
|---|---|---|
| 可修复（改代码） | `[fixable-code]` | 改代码去掉 |
| 可修复（调规则） | `[fixable-config]` | 改 oxlintrc / pyproject.toml |
| 必须保留 | `[keep]` | 有合理理由 |
| 已过期 | `[dead]` | 规则已不再报 |
| 可收窄 | `[downgrade]` | file-level → line-level |

### agent 流程
- Grep 全部 `oxlint-disable` / `eslint-disable` / `noqa`
- 23 处 noqa: 每处 Read 上下文 → 判断类别
- 172 处 oxlint: 前 50 条深度分析
- 其余 122 条只列规则名 + 文件路径 + 粗略归类

### 产出格式

```markdown
| ID | file:line | 规则 | 标签 | 备注 |
|---|---|---|---|---|
| LINT-001 | api/approvals.test.ts:17 | no-ternary | [fixable-config] | 测试环境应豁免 no-ternary |
| LINT-002 | components/documents-import-form.tsx:256 | id-length | [keep] | form 字段名 `bx` `cx` 不可改 |
| NOQA-001 | ingest/api.py:7 | E402 | [keep] | 故意: import 放在 dataclass 之后 |
```

### agent 指令
- 工具调用 ≤ 25 次
- 不跑全量 oxlint（172 处太多，抽样足够判断）

---

## 6. A4: Pyright Strict Mode Analyzer

### 分析层级（非累积，每级独立测）

| 层级 | 改动 | 预期 error 数 | 风险 |
|---|---|---|---|
| L0 现状 | basic (6 个 none) | 0 | 引用基线 |
| L1 类型推断 | 删 5 个 `reportUnknown*` none → 默认 warn | ~50-500 | 低 |
| L2 标准模式 | `typeCheckingMode: "standard"` | ~100-1000 | 中 |
| L3 部分 strict | standard + `reportOptionalMemberAccess: "error"` + 等 | ~200-2000 | 高 |
| L4 完整 strict | `typeCheckingMode: "strict"` | ~300-5000+ | 激进 |

### 产出格式

```markdown
## L1: 删 reportUnknown* none

| 规则 | 新 error 数 | 重灾区 |
|---|---|---|
| reportUnknownMemberType | 42 | src/permissions/, src/lookups/ |
| reportUnknownVariableType | 18 | tests/lookups/ |
| reportUnknownParameterType | 8 | ... |
| **合计** | **78** | |

结论: L1 可行, error 可收敛, 建议逐个开
```

### agent 流程
1. 备份 pyrightconfig.json
2. 改 `reportUnknown*: "warning"` → 跑 pyright → 计每条规则的 error 数
3. 恢复 pyrightconfig.json
4. 改 `typeCheckingMode: "standard"` → 跑 pyright → 计
5. 恢复 pyrightconfig.json
6. 在 standard 上加个别规则 → 跑 pyright → 计
7. 恢复
8. strict → 跑 → 计 (超过 1000 跳 "too many")

### agent 指令
- 工具调用 ≤ 20 次
- 必须在每次修改后**恢复** pyrightconfig.json，不能残留

---

## 7. Phase 2: Synthesize

### 去重规则
- 如果同一条 `type: ignore` 出现在 A2 (fixable) 又在 A4 (L1 会炸) → 标 `[rule-up]`

### 路线图表 (6 级优先级)

| 优先级 | 类型 | 行动 |
|---|---|---|
| P0 | 真 test bug | 立即修 |
| P1 | fixable pyright ignore + dead lint ignore | 逐个清 |
| P2 | fixable-config lint ignore + pyright level up | 规则配置 |
| P3 | keep (无风险) | 不动 |
| P4 | keep (有理由) | 不动 |

---

## 8. 错误处理

- 任一 agent 失败：不阻塞，在路线图顶部标"未完成维度"
- 工具调用超限：记录已知缺口，跳下一项
- pyright strict 超 1000 error：跳 L4，只报基数

---

## 9. 产出物清单

| 路径 | 内容 |
|---|---|
| `docs/audit/2026-06-25-test-failures.md` | A1: 测试失败分类 |
| `docs/audit/2026-06-25-pyright-ignores.md` | A2: type: ignore 可删性分析 |
| `docs/audit/2026-06-25-lint-ignores.md` | A3: eslint/oxlint/noqa 可删性分析 |
| `docs/audit/2026-06-25-pyright-strict-audit.md` | A4: 4 层级严格模式可行性 |
| `docs/audit/2026-06-25-code-quality-plan.md` | 合成路线图 (Phase 2) |
| `docs/superpowers/specs/2026-06-25-code-quality-scan-design.md` | 本 spec |

**不实施任何修复**，不改任何业务代码。

---

## 10. 后续流程

1. 你 review 本 spec → 批准
2. 走 writing-plans → 生成实施 plan
3. 执行 Phase 1 (4 agent) → Phase 2 (synthesize) → 出 5 份报告
4. 你 review docs/audit/2026-06-25-code-quality-plan.md → 决定哪些修
