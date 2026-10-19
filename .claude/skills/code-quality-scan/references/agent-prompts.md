# 4 个 Subagent Prompt 模板

> **调用方式**: 4 个 Agent tool call 在**同一 message** 派发, 都 `run_in_background: true`.
> **Agent type**:
> - A1: `general-purpose` (需要跑 pytest/vitest, 可写文件)
> - A2/A3/A4: `Explore` (只读, 节省资源)
>
> **公共参数 (主线程 Step 1 注入)**:
> - `DATE`: `YYYY-MM-DD` 格式
> - `PROJECT_ROOT`: `c:/doc/Code/rag`
> - `OUTPUT_DIR`: `docs/audit/$DATE/`
> - `NOQA_COUNT`, `PYRIGHT_IGNORE_SRC`, `PYRIGHT_IGNORE_TEST`, `OXLINT_COUNT`: Step 1 拿到的当前数字

---

## A1 Test Scanner

**目标**: 跑 pytest + vitest, 分类所有失败, **专项**识别连真 PG 的违规测试 (项目强制规范).

```
你是 A1 Test Scanner agent. 严格只读业务代码 (不要修改 packages/*/src/ 或 tests/), 唯一可写: $OUTPUT_DIR/$DATE-test-failures.md

项目根: $PROJECT_ROOT
工作目录: $PROJECT_ROOT
日期: $DATE
输出: $OUTPUT_DIR/$DATE-test-failures.md (Write 工具)

## 任务

1. **跑 pytest**:
   `cd packages/service && uv run pytest -v --tb=short 2>&1 | head -300`

2. **跑 vitest**:
   `cd packages/web && bun run test 2>&1 | head -200`

3. **收集全部 FAILED/ERROR**, 每条按以下格式输出:

### [类别] test_file.py::test_name

- **文件**: `tests/.../test_file.py:行号`
- **错误**: <错误信息摘要 100 字>
- **推测根因**: <1-3 句>
- **上下文**: <2-3 句>

类别取值: [bug] [env] [regression] [flaky] [config] [pg-violation]

### 专项: [pg-violation] 检出连真 PG 的测试

项目强制规范 (见 [packages/service/CLAUDE.md §测试隔离 4 模式](../../service/CLAUDE.md)):
- 模式 1: 单元测试, 必须 mock, 0 PG 依赖
- 模式 2: 集成测试, 用 `db_session` fixture (事务回滚), 标 `@pytest.mark.integration`
- 模式 3/4: 高级模式, 不常用

**识别方法**:
1. 看 failures 里含 `psycopg` / `OperationalError` / `connection refused` / `FATAL` 字样的错误
2. Grep `db_session|session_scope|RAG_DB_URL|PG_HOST|PG_DATABASE` 在 tests/ 目录
3. Grep `pytest.mark.integration` — 这些是合法模式 2 集成测试, **不是违规**
4. 对每处: Read 测试文件 → 判断是模式 2 db_session fixture 还是真连 PG

**违规判定** (输出到报告 §pg-violation 段):
| 文件 | 违规类型 | 建议 |
|---|---|---|
| tests/auth/test_router.py:xx | 直调 session_scope | [pg-violation] 须重写为 mock session |

### 分类说明

- [bug]: 真实 bug, 有复现步骤
- [env]: PG/Redis 未起, docker 没跑, 网络不通 — 仍继续扫
- [regression]: 之前 commit 引入
- [flaky]: 偶发 (时间戳/竞争/顺序依赖/全局状态污染)
- [config]: 测试配置错误 (mock 不对 / fixture 缺)
- [pg-violation]: 违反强制规范, 须重写为模式 1 mock

### 工具限制
- 最多 30 次工具调用
- 写产出文件: $OUTPUT_DIR/$DATE-test-failures.md

### 最终回复

status (DONE / DONE_WITH_CONCERNS) + finding 总数 + 按类别分组 + 文件行数
```

---

## A2 Pyright Scanner

**目标**: 列全部 `type: ignore`, 评估可删性 (按 [stub] / [fixable] / [dead] / [rule-up] / [test] 分类).

```
你是 A2 Pyright Scanner agent. 严格只读. 唯一可写: $OUTPUT_DIR/$DATE-pyright-ignores.md

项目根: $PROJECT_ROOT
日期: $DATE
当前 type:ignore 总数: PYR_SRC=$PYRIGHT_IGNORE_SRC, PYR_TEST=$PYRIGHT_IGNORE_TEST

## 任务

1. 读 pyrightconfig.json 现状: Read packages/service/pyrightconfig.json (注意: 不要假设内容, 运行时读)
2. 列全部 type: ignore: Grep "type: ignore" 在 packages/service/src/ 和 packages/service/tests/, 排除 __pycache__ 和 .venv

3. **对前 30 条 ignore 深度分析** (其余只列表):
   a. Read 该行 + 上下文 20 行
   b. 尝试删 ignore: 改文件 (临时), 跑 `cd packages/service && uv run pyright <file>` 验证
   c. 分类:
      - pyright 不报了 → [dead] (可立即删)
      - 报第三方库问题 → [stub] (SQLAlchemy ORM / httpx / pymupdf 等)
      - 报自己代码类型问题 → [fixable] + 写怎么改
      - 报 optional/union 问题 → [rule-up] (升规则时会炸)

4. **检查 tests/ 里的 `type: ignore`** 有没有用裸 `# type: ignore$` (没带错误码)
   项目强制规范 (见 [CLAUDE.md §后端 Rust-like 严格准则](../../CLAUDE.md)): 必须带具体错误码 `# type: ignore[错误码]`

5. 写产出文件 $OUTPUT_DIR/$DATE-pyright-ignores.md

### 报告格式

```
## 摘要表

| 类别 | src 数量 | test 数量 |
|---|---|---|
| [stub] | N | 0 |
| [fixable] | N | 0 |
| [dead] | N | 0 |
| [rule-up] | N | 0 |
| [test] | 0 | N |
| **合计** | N | N |

## pyrightconfig.json 现状

\`\`\`json
<运行时 Read 到的内容>
\`\`\`

## SRC 审计 (按库分组)

每条:
| ID | file:line | 错误码 | 库 | 标签 | 备注 |
|---|---|---|---|---|---|
| PYR-001 | src/chat/service.py:307 | attr-defined | SQLAlchemy | [stub] | ORM 推断限制 |

## [fixable] 明细

| ID | file:line | 错误码 | 问题 | 修复建议 |
|---|---|---|---|---|

## [dead] 明细

可直接删除的 ignore 列表

## TESTS 审计 (按库分组)

格式同 SRC

## 裸 type: ignore 检查

| 文件:行 | 当前 | 应改为 |
|---|---|---|

## 结论

修复优先级 + 建议升哪些规则
```

### 工具限制
- 最多 30 次工具调用
- pyright 每次只跑单文件 (`cd packages/service && uv run pyright <file>`)
- 写产出, 不修代码 (改文件是为了验证, 验证后恢复)
```

---

## A3 Lint Scanner

**目标**: 列全部 `noqa` (Python) + `oxlint-disable` / `eslint-disable` (TS), 评估可删性.

```
你是 A3 Lint Scanner agent. 严格只读. 唯一可写: $OUTPUT_DIR/$DATE-lint-ignores.md

项目根: $PROJECT_ROOT
日期: $DATE
当前数字: NOQA=$NOQA_COUNT 条, OXLINT=$OXLINT_COUNT 条 (主线程 Step 1 注入, 是当前实际数)

## 任务

1. **统计全部 oxlint/eslint disable** (前端):
   Grep "eslint-disable|oxlint-disable" packages/web/app/ packages/web/lib/ packages/web/components/ packages/web/hooks/ packages/web/i18n/ --include="*.ts" --include="*.tsx"

2. **统计全部 noqa** (后端):
   Grep "noqa" packages/service/src/ --include="*.py"

3. **NOQA 全部深度分析** (数量少, < 30 条):
   - 每条 Read 上下文 → 归类
   - 检查是否符合 [CLAUDE.md §后端 Rust-like 严格准则](../../CLAUDE.md): 不允许 `# noqa` 绕过, 必须带具体错误码 + 注释
   - 找出裸 `# noqa` (没带错误码) → 标 [fixable-config] 建议在 ruff.toml 加 `extend-select`

4. **oxlint 前 50 条深度分析** (其余只列规则名+文件+粗略归类):
   - 找 file-level 注释 vs inline 注释
   - 找可以用 .oxlintrc.json overrides 消掉的 (如: 测试文件应豁免 no-magic-numbers / max-statements / id-length / no-ternary / sort-imports / init-declarations)

5. **Read packages/web/.oxlintrc.json** — 看规则配置
   找出可以调到 rule config 而不是 file-level 的
   **重要**: 给出建议的 overrides 段 JSON 片段

6. 写产出文件 $OUTPUT_DIR/$DATE-lint-ignores.md

### 报告格式

```
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
- [keep]: N (F401 import 副作用 / E402 import 顺序 / ARG001 守卫参数)
- [fixable-code]: N (收窄 except / 加错误码 / 加注释)
- [dead]: N (ruff 已不报)

### 详细清单
| ID | 文件:行 | 规则 | 标签 | 备注 |
|---|---|---|---|---|
| NOQA-001 | src/ingest/api.py:7 | E402 | [keep] | 故意: import 放在 dataclass 后 |

### 裸 noqa 检查
| 文件:行 | 当前 | 应改为 |
|---|---|---|

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
| ... | |

### 关键发现
- 测试文件 X 条 → 可用 overrides 消
- framer-motion CSS 属性 Y 条 → 合理 keep
- SSE 流解析 Z 条 → 合理 keep

## 三、oxlintrc.json 现状

\`\`\`json
<运行时 Read 到的内容>
\`\`\`

## 四、行动建议

### [fixable-config] 建议 overrides

\`\`\`json
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
\`\`\`

### [fixable-code] 修复项
| ID | 文件 | 改法 |
|---|---|---|
| LINT-xxx | evaluate-new-form.tsx:42 | 改用 typed any |

### 优先级
- P0: 裸 noqa 修复 (强制规范违反)
- P1: [fixable-code] 改代码
- P2: [fixable-config] 加 overrides
- P3: [keep] 不动
```

### 工具限制
- 最多 30 次工具调用
- 写产出, 不修代码

**重要**: 数字 `$NOQA_COUNT` 和 `$OXLINT_COUNT` 是当前实际数, 写报告时**直接引用**作为"现状基线", 不要让 agent 重新 grep 全部 (它会重复你的工作).
```

---

## A4 Pyright Strict Analyzer

**目标**: 逐级升严格模式 (L1-L4), 验证可行性, **每次改 pyrightconfig.json 后必须 git checkout 恢复**.

```
你是 A4 Pyright Strict Analyzer agent. 严格只读业务代码. 唯一可写: $OUTPUT_DIR/$DATE-pyright-strict-audit.md
**关键约束**: 每次修改 pyrightconfig.json 后必须 `git checkout packages/service/pyrightconfig.json` 恢复原状.

项目根: $PROJECT_ROOT
日期: $DATE

## 任务

0. **第一步**: Read packages/service/pyrightconfig.json 拿**当前**配置 (不要假设, 不要硬编码昨天的版本)

### 逐级测试 (每级独立, 不累积, 每级后必须 git checkout 恢复)

**L0 (基线)**: 当前配置 — 跑 `cd packages/service && uv run pyright` → 记总 error 数 + 0 error 文件数

**L1**: 把 5 个 `reportUnknown*` 从 `none` 改为 `warning` (如果当前是 none, 跳过此级)
- 改 → 跑 pyright → 记每条规则的 warning 数
- 恢复

**L2**: `typeCheckingMode: "basic" → "standard"`
- 改 → 跑 pyright → 记总 error 数 + top 10 文件
- 恢复

**L3**: standard + 逐个加 strict 规则
- 候选规则: reportOptionalMemberAccess, reportOptionalSubscript, reportOptionalCall, reportOptionalIterable, reportOptionalContains, reportOptionalChain
- 每个规则改 → 跑 pyright → 记命中数
- 恢复

**L4**: `typeCheckingMode: "strict"`
- 改 → 跑 pyright → 记总 error 数
- 如果超过 1000 → 记录 "too many (>1000)" 跳过此级
- 恢复

### 产出格式

```
## L0: 基线

| 指标 | 值 |
|---|---|
| typeCheckingMode | basic |
| reportUnknown* none 数量 | N |
| 当前 error 数 | N |
| 0 error 文件数 | N / 总数 |

## L1: 删 reportUnknown* none → warning

| 规则 | warning 数 | 重灾区 |
|---|---|---|
| reportUnknownMemberType | N | src/permissions/, src/lookups/ |
| reportUnknownParameterType | N | ... |
| ... | ... | ... |

## L2: standard mode

| 指标 | 值 |
|---|---|
| 总 error | N |
| Top 5 文件 | src/auth/router.py:23, ... |
| vs L0 delta | +N |

## L3: standard + optional 规则

| 规则 | 额外 error (vs L2) |
|---|---|
| reportOptionalMemberAccess | N |
| reportOptionalSubscript | N |
| ... | ... |

## L4: strict mode

| 指标 | 值 |
|---|---|
| 总 error | N (or "too many (>1000), 跳过") |
| vs L2 delta | +N |

## 结论与建议

| 层级 | 可行性 | 推荐度 |
|---|---|---|
| L1 | ✅ 立即可做 | 🟢 高 |
| L2 | ✅ 推荐 (5 新 error) | 🟡 中 |
| L3 | ⚠️ 视规则 | 🟡 中 |
| L4 | ❌ 8,272 error 暂不可行 | ⚪ 低 |
```

### 工具限制
- 最多 20 次工具调用
- **每次改后必须恢复 pyrightconfig.json** (`git checkout packages/service/pyrightconfig.json` 或 sed 还原)
- 写产出, 不留改动
```

---

## 公共约束 (4 agent 都遵守)

1. **不要修改任何业务代码** — `packages/*/src/**` / `packages/service/tests/**` 全部只读
2. **产出文件** — 全部写到 `$OUTPUT_DIR/` (即 `docs/audit/$DATE/`), 不要写到 `docs/audit/` 根
3. **不 commit** — 主线程 Step 5 统一 commit
4. **不联网** — 不需要 WebSearch / WebFetch, 纯本地
5. **报告必须有 metadata 块** (项目根 / 日期 / 工具版本 / 总数)
