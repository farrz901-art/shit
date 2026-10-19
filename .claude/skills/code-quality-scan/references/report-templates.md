# 5 份报告章节模板

> 所有报告输出到 `docs/audit/$DATE/` 子目录 (符合 [README 命名约定](../../README.md))
> 每份报告**必须**含: Metadata 块 + 摘要表 + 分类明细 + 结论/建议
> A1-A4 互不引用, 由主线程 Step 4 合成到第 5 份报告

---

## 1. $DATE-test-failures.md — A1 输出

**目标读者**: 修复测试的人. 列出每条 fail + 分类 + 根因.

### 必含章节

```markdown
# 测试失败快照 (YYYY-MM-DD)

## Metadata

| 项 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| 项目根 | c:/doc/Code/rag |
| pytest 版本 | x.x.x |
| Python 版本 | 3.14.x |
| pytest 结果 | N pass / M fail / K error |
| vitest 结果 | N pass / M fail |
| 工具调用数 | N / 30 |
| 扫描 agent | A1 (general-purpose) |

## 摘要

| 类别 | 数量 | 说明 |
|---|---|---|
| [bug] | N | 真实 bug |
| [env] | N | 环境未起 |
| [regression] | N | 近期 commit 引入 |
| [flaky] | N | 偶发 |
| [config] | N | 测试配置错误 |
| [pg-violation] | N | 违反项目强制规范 (模式 1) |
| **合计** | N | — |

## [类别] 段落

每条 fail 用统一格式:

### [类别] test_file.py::test_name

- **文件**: `tests/.../test_file.py:行号`
- **错误**: <错误信息摘要 100 字>
- **推测根因**: <1-3 句>
- **上下文**: <2-3 句>

## [pg-violation] 专项 ⚠️ (项目强制规范违反)

| 文件 | 违规类型 | 建议 |
|---|---|---|
| tests/auth/test_router.py:xx | 直调 session_scope | [pg-violation] 须重写为 mock session |
| tests/integration/test_db_session.py:12 | db_session fixture | 模式 2 集成测试, opt-in 可接受 |

**判定规则**:
- 用 `db_session` fixture 事务回滚 → 模式 2, **不违规**
- 标 `@pytest.mark.integration` → opt-in 集成, **不违规**
- 直调 `session_scope()` / `RAG_DB_URL` / `PG_*` env → [pg-violation]

## 按类别汇总表

| 类别 | pytest | vitest | 合计 |
|---|---|---|---|
| [bug] | N | N | N |
| ... | ... | ... | ... |

## 结论

- 最严重: P0 (bug + regression)
- 最紧急: P-scan (pg-violation, 强制规范)
- 偶发: flaky 需要隔离全局状态
```

---

## 2. $DATE-pyright-ignores.md — A2 输出

**目标读者**: 清理 type:ignore 的人. 按库分组 + 可删性分类.

### 必含章节

```markdown
# Pyright type:ignore 审计 (YYYY-MM-DD)

## Metadata

| 项 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| pyright 版本 | x.x.x |
| src type:ignore 总数 | N |
| tests type:ignore 总数 | N |
| 扫描 agent | A2 (Explore) |

## 摘要

| 类别 | src | test | 合计 | 说明 |
|---|---|---|---|---|
| [stub] | N | 0 | N | 第三方库推断限制, 不可修 |
| [fixable] | N | 0 | N | 自己代码类型问题, 可改 |
| [dead] | N | 0 | N | pyright 已不报, 直接删 |
| [rule-up] | N | 0 | N | 升严格规则时会炸 |
| [test] | 0 | N | N | 测试故意传非法值 |
| **合计** | N | N | N | — |

## pyrightconfig.json 现状

```json
<运行时 Read 的内容>
```

## SRC 审计 (按库分组)

每条:
| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-001 | src/chat/service.py:307 | attr-defined | SQLAlchemy | [stub] | ORM 推断限制 |

按库分组示例:
- Pillow
- SQLAlchemy ORM
- FastAPI
- tqdm
- pymupdf
- PGVectorStore
- botocore
- kreuzberg
- embedder (项目自己)

## [fixable] 明细

| ID | file:line | 错误码 | 问题 | 修复建议 |
|---|---|---|---|---|
| PYR-005 | health/checks.py:243 | attr-defined | 私有 `_bucket` 访问 | 改 `store._bucket` → getter 方法 |

## [dead] 明细 (可直接删)

| ID | file:line | 错误码 | 验证方式 |
|---|---|---|---|
| PYR-013 | eval/runner.py:255 | misc | 删 ignore, pyright 0 error |

## TESTS 审计 (按库分组)

| ID | file:line | 错误码 | 库 | 备注 |
|---|---|---|---|---|
| T-PYR-001 | tests/auth/test_router.py:42 | arg-type | FastAPI TestClient | 测试故意传非法值 |

## 裸 type: ignore 检查 (强制规范违反)

| 文件:行 | 当前 | 应改为 |
|---|---|---|
| tests/foo/test_bar.py:10 | `# type: ignore` | `# type: ignore[specific-code]` |

## 结论

- [fixable] 数量决定 P1 工作量
- [dead] 可立即 PR
- 裸 type:ignore 是强制规范违反, P0
- [stub] / [test] / [rule-up] 全部 keep
```

---

## 3. $DATE-lint-ignores.md — A3 输出

**目标读者**: 调 lint 规则 + 修 noqa 的人. oxlintrc overrides 是大头.

### 必含章节

```markdown
# Lint ignore 审计 (YYYY-MM-DD)

## Metadata

| 项 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| ruff 版本 | x.x.x |
| oxlint 版本 | x.x.x |
| noqa 总数 | N |
| oxlint ignore 总数 | N |
| 扫描 agent | A3 (Explore) |

## 概要

| 类别 | noqa | oxlint | 合计 |
|---|---|---|---|
| [keep] | N | N | N |
| [fixable-code] | N | N | N |
| [fixable-config] | N | N | N |
| [dead] | N | N | N |
| [downgrade] | N | N | N |
| **合计** | N | N | N |

## 一、NOQA 分析 (Python)

### 分类汇总

- [keep]: N (F401 import 副作用 / E402 import 顺序 / ARG001 守卫参数, 都有注释)
- [fixable-code]: N (收窄 except / 加错误码)
- [dead]: N (ruff 已不报)

### 详细清单

| ID | 文件:行 | 规则 | 标签 | 备注 |
|---|---|---|---|---|
| NOQA-001 | src/ingest/api.py:7 | E402 | [keep] | 故意: import 放在 dataclass 后 |

### 裸 noqa 检查 (强制规范违反)

| 文件:行 | 当前 | 应改为 |
|---|---|---|
| src/kg/client.py:92 | `# noqa` | `# noqa: BLE001` (或具体码) |

## 二、oxlint/eslint-disable 分析 (TS/TSX)

### 按目录分布

| 目录 | 数量 |
|---|---|
| packages/web/app/ | N |
| packages/web/lib/ | N |
| packages/web/components/ | N |
| packages/web/hooks/ | N |
| packages/web/i18n/ | N |

### 按规则分布 (Top 10)

| 规则 | 数量 |
|---|---|
| no-magic-numbers | N |
| max-statements | N |
| id-length | N |
| no-ternary | N |
| sort-imports | N |
| init-declarations | N |

### 关键发现

- 测试文件 X 条 → 可用 overrides 消
- framer-motion CSS 属性 Y 条 → 合理 keep
- SSE 流解析 Z 条 → 合理 keep
- e2e 全跳过 → 合理 keep

## 三、oxlintrc.json 现状

```json
<运行时 Read 的内容>
```

## 四、行动建议

### [fixable-config] 建议 overrides (一次改完可消 ~80 条)

```json
{
  "rules": { ... 现有规则 ... },
  "overrides": [
    {
      "files": ["**/*.test.*", "**/*.spec.*", "**/e2e/**"],
      "rules": {
        "no-magic-numbers": "off",
        "max-statements": "off",
        "id-length": "off",
        "no-ternary": "off",
        "sort-imports": "off",
        "init-declarations": "off"
      }
    }
  ]
}
```

**效果**: X 条 oxlint ignore 可删除, 仅保留 Y 条核心逻辑 keep.

### [fixable-code] 修复项

| ID | 文件 | 改法 |
|---|---|---|
| LINT-001 | api/approvals.test.ts:17 | 改 no-ternary → if/else |
| LINT-002 | evaluate-new-form.tsx:42 | 改用 typed any |

### 优先级

- P0: 裸 noqa 修复 (强制规范违反)
- P1: [fixable-code] 改代码
- P2: [fixable-config] 加 overrides
- P3: [keep] 不动
```

---

## 4. $DATE-pyright-strict-audit.md — A4 输出

**目标读者**: 决定 pyright 升级节奏的人. 4 层级 L0-L4.

### 必含章节

```markdown
# Pyright 严格模式可行性分析 (YYYY-MM-DD)

## Metadata

| 项 | 值 |
|---|---|
| 日期 | YYYY-MM-DD |
| pyright 版本 | x.x.x |
| 当前 typeCheckingMode | basic / standard / strict |
| 扫描 agent | A4 (Explore) |

## L0: 基线

| 指标 | 值 |
|---|---|
| typeCheckingMode | basic |
| reportUnknown* none 数量 | N |
| 当前 error 总数 | N |
| 0 error 文件数 | N / 总数 |
| 当前 pyrightconfig.json | <附 JSON> |

## L1: 删 reportUnknown* none → warning

| 规则 | warning 数 | 重灾区 |
|---|---|---|
| reportUnknownMemberType | N | src/permissions/, src/lookups/ |
| reportUnknownParameterType | N | ... |
| reportUnknownArgumentType | N | ... |
| reportUnknownVariableType | N | ... |
| reportUnknownLambdaType | N | ... |

**结论**: warning 不影响 CI, 6,758 个 warning → 可按 module 逐文件修.

## L2: typeCheckingMode: standard

| 指标 | 值 |
|---|---|
| 总 error | N |
| Top 5 文件 | src/auth/router.py:23, ... |
| vs L0 delta | +N |

**结论**: 推荐 (只多 N 个 error, 1-2 个 PR 修完).

## L3: standard + optional 规则

| 规则 | 额外 error (vs L2) |
|---|---|
| reportOptionalMemberAccess | N |
| reportOptionalSubscript | N |
| reportOptionalCall | N |
| reportOptionalIterable | N |
| reportOptionalContains | N |
| reportOptionalChain | N |

**结论**: 视规则分批加.

## L4: typeCheckingMode: strict

| 指标 | 值 |
|---|---|
| 总 error | N (or "too many (>1000), 跳过") |
| vs L2 delta | +N |

**结论**: 暂不推荐 (项目无 Python 全套类型注解).

## 结论与建议

| 层级 | 可行性 | 推荐度 | 工作量 |
|---|---|---|---|
| L1 | ✅ 立即可做 | 🟢 高 | 1 PR |
| L2 | ✅ 推荐 | 🟡 中 | 1-2 PR |
| L3 | ⚠️ 视规则 | 🟡 中 | 视规则 |
| L4 | ❌ 暂不可行 | ⚪ 低 | 整个项目类型注解 |
```

---

## 5. $DATE-code-quality-plan.md — Phase 2 主线程输出

**目标读者**: 决策者. 6 级优先级, 决定下一步 spec.

### 必含章节

```markdown
# 代码质量提升路线图 (YYYY-MM-DD)

> 来源: 4 维度并行扫描
> 原始报告:
> - [test-failures.md](test-failures.md) — N 条测试失败
> - [pyright-ignores.md](pyright-ignores.md) — N 处 type: ignore
> - [lint-ignores.md](lint-ignores.md) — N noqa + N oxlint ignore
> - [pyright-strict-audit.md](pyright-strict-audit.md) — 4 层级分析

## 汇总

| 优先级 | 数量 | 主要行动 | 复杂度 |
|---|---|---|---|
| **P0 测试修复** | N 条 | 修 bug + 修回归 | 🔴 |
| **P5 PG 测试** | N 条 | 改为模式 1 mock | 🔴 |
| **P1 ignore 清理** | N 条 | 删 fixable/dead | 🟡 |
| **P2 配置优化** | N 条 | 调 oxlintrc/pyright | 🟢 |
| **P3 pyright 升级** | L2 standard | 5 new error | 🟡 |
| **P4 观察项** | — | keep, 不动 | ⚪ |

## P0: 测试修复

[从 test-failures.md 拉 P0 finding, 列表 + 根因 + 建议]

## P5: PG 违规测试 ⚠️

[从 test-failures.md [pg-violation] 段拉, 列表 + 每条 mock 策略]

## P1: ignore 清理

[从 pyright-ignores.md + lint-ignores.md 拉 [fixable] + [dead]]

## P2: 配置优化

[从 lint-ignores.md [fixable-config] + pyright-strict-audit.md 拉]

## P3: Pyright 升级

[从 pyright-strict-audit.md 拉 L1/L2/L3 建议]

## P4: 观察项 (不动)

[从 4 报告拉 [keep] / [stub] / [test] 类]

## 修复优先级建议

1. 🔴 P5: 先修 PG 违规 (强制规范)
2. 🟡 P0: 修真 bug + 回归
3. 🟢 P1: 清 fixable/dead ignore
4. 🟢 P2: 改 oxlintrc overrides
5. 🟢 P3: 升 pyright standard
6. ⚪ P4: flaky 专项

## 不实施

- L4 pyright strict (N error, 暂缓)
- [keep] 类 (合理理由)
- [stub] / [test] 类 (第三方库限制)
```

---

## 报告长度参考

基于 2026-06-25 扫描 (已 commit `5bf29ab5`) 的实际行数:

| 报告 | 行数 | finding 数量 |
|---|---|---|
| test-failures.md | 227 | 49 |
| pyright-ignores.md | 210 | 78 |
| lint-ignores.md | 208 | 198 |
| pyright-strict-audit.md | 115 | 4 层级 |
| code-quality-plan.md | 166 | 6 优先级 |

**提示**: 不要追求行数, 重点是**信息密度**. 表格 + 简短说明 > 大段文字.
