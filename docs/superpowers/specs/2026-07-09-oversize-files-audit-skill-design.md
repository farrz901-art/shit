# 2026-07-09 oversize-files-audit skill design

> 新增一个独立只读 audit skill: 扫描项目里所有 >300 行的 .py / .ts / .tsx 文件, 出 1 份带重构建议的 audit 报告.
> **不修任何业务代码, 不写 spec 草稿, 不调 LLM 增强**. 跟现有 [code-quality-scan](../../../.claude/skills/code-quality-scan/SKILL.md) / [full-stack-audit](../../../.claude/skills/full-stack-audit/SKILL.md) 平级, 单一职责.

## 背景与动机

项目截至 2026-07-09 已有两个 audit skill:

- `code-quality-scan` (4 维度: 测试 / pyright / lint / strict) — 出 P0-P5 路线图
- `full-stack-audit` (6 维度: Security / Concurrency / Error / Data / Frontend / Architecture) — 出 finding + 5 份 spec 草稿

两者都**不**扫描"哪些文件 >300 行"以及"该怎么拆". 这是一个真缺口:

- [项目根 .claude/CLAUDE.md](../../../.claude/CLAUDE.md) 强制 "每个函数或类的代码量不能超过 100 行"
- [项目根 CLAUDE.md §前端 React/Next.js 准则](../../../CLAUDE.md) 强制 "React 单文件 ≤300 行, Dialog 拆独立文件"
- 但**没有自动机制**找违反文件, 全靠人 grep 走查

新建 `oversize-files-audit` 补这个洞.

## 目标

- **定量**: 一次性扫出项目所有 >300 行的 .py / .ts / .tsx 文件
- **定性**: 对每个文件给 6 段固定格式建议:
  1. 拆分点 (行号 + 干什么 + 拆后建议名)
  2. 能否拆成 pure function / pure component / hook
  3. 库替代 (按语种: Python 走 pydantic/dataclass/functools; TS Page 走 shadcn/zod; TS Hook 走 react-use/ahooks/es-toolkit)
  4. 能否用对象替 if
  5. 能否用数组迭代替循环
  6. 预计减少行数 %
- **自动化**: 跟现有两个 audit skill 共享 `docs/audit/<DATE>/` 命名空间, 1 commit 模式, checklist 一致

## 非目标 (out of scope, v1)

- ❌ 修任何业务代码 (违反项目规范, 跟现有 skill 一样只读)
- ❌ 写 spec 草稿 (留给 full-stack-audit 单一职责)
- ❌ LLM 增强 (例如调 es-toolkit 实际 import 验证) — v1 只出表格建议, 不调外部库
- ❌ 行数趋势监控 / 历史 diff — 单次快照, 后续 spec 再加
- ❌ 跨多项目批量跑 — 单仓单跑, 跨仓留未来

## 边界 (跟现有 skill)

| Skill | 关注 | 出 |
|---|---|---|
| code-quality-scan | test/type/lint/strict 4 维度统计 | P0-P5 路线图 |
| full-stack-audit | 6 维度业务审计 + adversarial verify | finding + 5 份 spec 草稿 |
| **oversize-files-audit** (本 spec) | **文件膨胀扫描 + 拆分建议** | **1 份拆分建议表** |

边界判定:
- code-quality-scan 看"统计数量", oversize-files-audit 看"具体文件" → 互补
- full-stack-audit D6 Architecture 也看重复代码, 但看的是"跨文件重复", 不看"单文件膨胀" → 互补

## 设计

### Skill 位置

`.claude/skills/oversize-files-audit/SKILL.md` + `.claude/skills/oversize-files-audit/references/{agent-prompts.md, scan-script.py}`

### 触发

- `/oversize-files-audit` — 默认今天, 默认阈值 300 行
- `/oversize-files-audit --min-lines 200` — 调阈值
- `/oversize-files-audit --include fixtures` — 包含默认排除目录 (慎用)

不触发场景 (写进 description):
- 想修代码 → 用对应 refactor skill
- 单文件 lint → 用 ruff/oxlint 直接跑
- 想找 bug → 用 systematic-debugging

### 工作流 (主线程 6 步)

#### Step 1: Prepare

主线程执行 (快, 不浪费 subagent 工具预算):

```python
# scan-script.py (放在 references/, 主线程调用)
import os, sys, json
from pathlib import Path

EXCLUDE_DIRS = {"__generated__", "node_modules", ".next", "dist", "build",
                ".venv", "venv", ".pytest_cache", ".ruff_cache", "coverage",
                "graphify-out", ".git"}
EXCLUDE_FILE_PATTERNS = ["migrations/versions/", "*.generated.*",
                         "*.test.*", "*.spec.*", "__snapshots__/",
                         "fixtures/"]
EXTS = {".py", ".ts", ".tsx"}
MIN_LINES = int(os.environ.get("MIN_LINES", "300"))

root = Path(sys.argv[1])
results = []
for fp in root.rglob("*"):
    if not fp.is_file(): continue
    if fp.suffix not in EXTS: continue
    if any(part in EXCLUDE_DIRS for part in fp.parts): continue
    if any(p in str(fp) for p in EXCLUDE_FILE_PATTERNS): continue
    try:
        lines = sum(1 for _ in fp.open("rb"))
    except OSError:
        continue
    if lines >= MIN_LINES:
        results.append({"path": str(fp.relative_to(root)), "lines": lines})

results.sort(key=lambda r: -r["lines"])
print(json.dumps(results, ensure_ascii=False, indent=2))
```

主线程通过 `python scan-script.py . 300 > .scan-cache.json` 传阈值 (避免 env 漂移).

把 `{FILE_COUNT}` `{TOTAL_LINES}` `{PY_COUNT}` `{TSX_COUNT}` 4 个数字注入到 subagent prompt (跟 [code-quality-scan §Step 1 注入数字](references/../../code-quality-scan/SKILL.md) 模式一致).

#### Step 2: Create output dir

```bash
DATE=$(date +%Y-%m-%d)
mkdir -p docs/audit/$DATE
```

后续所有 agent 输出写到 `docs/audit/$DATE/oversize-files-audit/` 子目录 (跟 README 约定 [docs/audit/README.md §命名约定](../../../audit/README.md) 一致 — 本 skill 自创子目录, 因为产物不止 1 份 .md).

#### Step 3: Dispatch 3 parallel subagents

**同一 message 派发** (3 个 Agent tool call 并行, 都 `run_in_background: true`, 都 `subagent_type: "general-purpose"`):

| Agent | 语种 | 路径范围 | 工具 | 产出 | 关键差异 |
|---|---|---|---|---|---|
| A1 Python | .py | `packages/service/src/`, `packages/service/tests/` | 只读 (Read/Grep/Glob/Bash wc-l) | `a1-python.md` | 库清单: pydantic / dataclass / functools / itertools / pathlib / pytest fixtures |
| A2 TS Page/Component | .ts/.tsx | `packages/web/app/`, `packages/web/components/` | 只读 | `a2-ts-page.md` | 库清单: shadcn / zod / tanstack-query / lucide-react |
| A3 TS Hook/Util | .ts/.tsx | `packages/web/hooks/`, `packages/web/lib/`, `packages/web/i18n/` | 只读 | `a3-ts-hook.md` | 库清单: react-use / ahooks / es-toolkit / zod / dayjs / nuqs |

**Wait**: 等 3 个 background agent 全部 complete (会收到 task notification).

**降级规则**:
- 某个 agent 失败 → 主线程在合成阶段留 `it.todo` 占位, 加中文注释指明哪个文件漏了
- 某个 agent 缺网络 → 跟现有 audit skill 一样, 禁用 WebSearch (本 skill 不需要联网)

#### Step 4: Synthesize

主线程执行 (不派 subagent):

1. Read 3 份 a1/a2/a3 .md
2. 按文件行数倒序合并
3. 写 `docs/audit/<DATE>/oversize-files-audit/oversize-files-audit.md`

**每文件 section 固定 6 段格式**:

```markdown
### `<相对路径>` (N 行, M 个函数/组件)

**1. 拆分点提议**:
- L1-72 `<干什么>` → `<拆后文件名>.ts` (pure function / hook / component)
- L88-150 `<干什么>` → `<拆后文件名>.ts` (...)

**2. 纯函数/hook 化**: ✅ 可拆 (列出) / ❌ 不可拆 (原因)
**3. 库替代**: ✅ shadcn `<Table>` / react-use `<useDebounce>` (具体) / ❌ 无
**4. 对象替 if**: ✅ L152-260 action variant switch → `actionMap[variant]` / ❌ 无
**5. 数组替循环**: ✅ `for` 循环改 `.map()` / ❌ 无
**6. 预计减少**: N → M (-X%)
```

**顶部汇总表** (markdown table):

| 路径 | 行数 | 语种 | 拆后预计 | 建议 |
|---|---|---|---|---|
| packages/web/.../x.tsx | 412 | TSX | 240 (-42%) | P1 |
| ... | ... | ... | ... | ... |

**末尾路线图**:
- P0: 行数 >500 且被多文件 import 的核心组件 (建议优先拆)
- P1: 行数 300-500 的页面/组件
- P2: 行数 300-500 的 hook/util

#### Step 5: Update checklist + commit

**5.1** 追加到 `docs/audit/<DATE>-findings.md` (如不存在则用本日 checklist 模板创建):

```markdown
## $DATE oversize-files-audit (不修, 仅报告)

| 维度 | 找到 | 说明 |
|---|---|---|
| >300 行 .py | N | 详见 [docs/audit/$DATE/oversize-files-audit/oversize-files-audit.md]($DATE/oversize-files-audit/oversize-files-audit.md) §Python |
| >300 行 .ts/.tsx | N | 同上 §TS |
| 总 oversize 文件 | N | 同上 |
| 路线图 | 3 档 P0/P1/P2 | 同上 §路线图 |
```

**5.2** 更新 `docs/audit/README.md` (在文档列表加一行)

**5.3** Commit:

```bash
git add docs/audit/$DATE/oversize-files-audit/ docs/audit/$DATE-findings.md docs/audit/README.md
git status
git commit -m "chore(audit): $DATE oversize-files 扫描 - N 个 >300 行文件 + 拆分建议"
```

Expected: 1 commit, 3+ 个 a*.md + 1 主报告 + 1 checklist + 1 README 更新.

### Anti-pattern 防御 (写进 SKILL.md)

- ❌ 派 agent 后忘记传 `run_in_background: true` → 串行, 浪费 10-20 min
- ❌ Agent 失败后静默跳过 → 必须留 `it.todo` 占位
- ❌ Subagent prompt 硬编码文件行数 → 用 `${FILE_COUNT}` placeholder
- ❌ 改任何 `packages/*/src/**` 或 `packages/*/tests/**` → 违反只读原则
- ❌ 用 emoji 而非 lucide-react 图标 (跨平台中文乱码) → 跟现有 skill 一致
- ❌ 把主报告写到 `docs/audit/` 根 → 必须走 `oversize-files-audit/` 子目录

### 测试

- **不写业务代码 → 不写 unit test**
- **正确性靠人工抽样**: 主线程随机挑 3-5 个文件, 用 Read 比对 agent 建议是不是 50% 准确. 准确率 < 50% → 改 prompt 重跑
- **回归**: 不写 (单次快照, 不需持续)

### 文档

- SKILL.md (主入口, 200-400 行)
- references/agent-prompts.md (3 份 prompt 模板, 各 30-60 行)
- references/scan-script.py (Python 跨平台扫描脚本, ~30 行)
- 上述 3 份放 `.claude/skills/oversize-files-audit/`
- 跑完的产物在 `docs/audit/<DATE>/oversize-files-audit/` (git 跟踪)

## 实施检查清单 (写 spec 用, 不进 plan)

- [ ] 创建 `.claude/skills/oversize-files-audit/SKILL.md`
- [ ] 创建 `.claude/skills/oversize-files-audit/references/agent-prompts.md` (含 3 份 prompt)
- [ ] 创建 `.claude/skills/oversize-files-audit/references/scan-script.py`
- [ ] 跑 `/oversize-files-audit` 1 次, 确认产物 1 commit
- [ ] 抽样 3-5 文件验证建议质量
- [ ] 在项目根 CLAUDE.md 加一行 "oversize-files-audit skill: 扫描 >300 行文件" (跟现有 2 skill 一致)
- [ ] 在 `.claude/skills/README.md` (如存在) 加 1 行

## 风险与未决项

| 风险 | 缓解 |
|---|---|
| Windows bash 中文乱码 ([feedback-windows-console-corrupts-non-ascii-when-writing-yaml](https://example.com)) | scan-script.py 全 ASCII 输出, 报告里中文只进 markdown body (Write 工具生成, 不经 bash echo) |
| subagent token 超限 (单 agent 拿 50 个 400 行文件) | 阈值默认 300 + 按语种分, 预估算 3 个 agent 各自 ≤ 50k tokens, 远低于 200k 上限; 单 agent 文件上限 80 (主线程派发前 assert, 超过则改阈值或拆任务) |
| 行数阈值漂移 (项目增长, 300 不再合理) | 加 `--min-lines` flag, 默认 300 跟现有 CLAUDE.md "函数 ≤ 100 行" 互补 (一个文件通常 3-5 个函数, 300 行 ≈ 平均 60-100 行/函数) |
| 拆分建议质量低 (subagent 看不懂业务) | v1 接受 50% 准确率, v2 加 verifier agent (跟 full-stack-audit Phase 3 一样) |
| 子目录命名冲突 (后续可能有别 skill 也用 `oversize-`) | 限定子目录名 `oversize-files-audit/`, SKILL.md 跟子目录同名, 不会撞 |

## 关联文档

- 项目级配置: [.claude/CLAUDE.md §编码规范](../../../.claude/CLAUDE.md) (100 行/函数)
- 项目级配置: [CLAUDE.md §前端 React/Next.js 准则](../../../CLAUDE.md) (300 行/文件)
- 现有 audit skill: [code-quality-scan/SKILL.md](../../../.claude/skills/code-quality-scan/SKILL.md)
- 现有 audit skill: [full-stack-audit/SKILL.md](../../../.claude/skills/full-stack-audit/SKILL.md)
- 命名约定: [docs/audit/README.md](../../../audit/README.md)
- 已知坑: [feedback-卡住 30 分钟立刻 STOP 报告](https://example.com), [feedback-windows-console-corrupts-non-ascii-when-writing-yaml](https://example.com)
