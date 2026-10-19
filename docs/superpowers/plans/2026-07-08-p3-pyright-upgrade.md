# Plan D: P3 pyright 升级 (PR-A: standard + 6 optional + ORM cast 合并)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 `packages/service/pyrightconfig.json` 从 `basic` 到 `standard`, 同时开启 6 条 `reportOptional*` 规则 (L3), 预期 **0 new error** (A4 报告已验证). 配套给 6 处 [rule-up] ORM Column 加 `cast()` 防御, 让 standard 模式下不爆.

**Architecture:**
- **D.1 6 处 ORM cast() 防御** — A4 报告 [rule-up] 6 条 (PYR-007/008/012/013/041), 升 standard 必爆. 用 `cast(AuditLog, row)` / `cast(str, r.name)` 等显式类型, 让 ORM Column 推断不失.
- **D.2 修 L2 4 个新 error** — A4 报告 L2 命中 4 个新 error (kreuzberg.py:40 ABC 签名 + pymupdf_extractor.py:24 ABC 签名 + test_login.py:202 r 未绑定 + L0 已有 2 个 import 错). D.2 修 kreuzberg/pymupdf ABC, test_login r 初始化. (L0 已有 2 个是 ingest 路径未跟迁, 跟 P0 重复, Plan A 已修.)
- **D.3 pyrightconfig.json 升级** — basic→standard + 6 optional 全 error. 验证 0 new error.
- **D.4 跑全量 pytest + pyright 验证 0 error 不退化**

**Tech Stack:** Python 3.14 / pyright 1.1.410 / pytest 9 (后端)

**Spec:** [docs/audit/2026-07-08/2026-07-08-code-quality-plan.md §P3](../audit/2026-07-08/2026-07-08-code-quality-plan.md#p3-pyright-升级-l2-l3-合并)
**报告:** [docs/audit/2026-07-08/2026-07-08-pyright-strict-audit.md](../audit/2026-07-08/2026-07-08-pyright-strict-audit.md)

---

## 全局约束

- **项目铁律** ([.claude/CLAUDE.md](../../.claude/CLAUDE.md)): 严禁绕过 pyright,oxlint 规则, **包括修改配置文件**. 本 plan 修改 pyrightconfig.json 是**主动升规则** (跟"绕过"不同), 是项目规范要求. **需要用户授权** (跟 Plan C 一样).
- **pyright 强规范** ([.claude/CLAUDE.md §后端 Rust-like 严格准则](../../.claude/CLAUDE.md)): pyright 必须 0 error. 本 plan 升 standard 后必须维持 0 error.
- **测试效率**: dev 阶段只跑改过的文件
- **A4 审计约束** ([.claude/skills/code-quality-scan/](../../.claude/skills/code-quality-scan/)): 每次改 pyrightconfig.json 后必须 `git checkout` 恢复. 本 plan 改 config 是**最终决策**, 不恢复.

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `packages/service/src/lookups/admin_router.py:545-558` | 改 | `cast(AuditLog, row)` + `cast(dict, row.meta or {})` |
| `packages/service/src/permissions/router.py:73` | 改 | `cast(str, r.name)` |
| `packages/service/src/permissions/router.py:312,314,315` | 改 | `cast(str, ...)` ORM Column 赋值 |
| `packages/service/src/permissions/service.py:51,52` | 改 | 同上 |
| `packages/service/src/ingest/pdf_processing/converters/kreuzberg.py:40` | 改 | Converter ABC 子类签名匹配 (Task 2) |
| `packages/service/src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:24` | 改 | TableExtractor ABC 子类签名匹配 (Task 2) |
| `packages/service/tests/auth/test_login.py:202` | 改 | `r = None` 初始化 (Task 2) |
| `packages/service/pyrightconfig.json` | 改 | basic→standard + 6 optional 规则 (Task 3) |
| `docs/audit/2026-07-08-findings.md` | 改 | 标记 P3 PR-A 完成, 记录 commit hash |

---

## Task 1: 6 处 [rule-up] ORM Column 加 cast() 防御

**Files:**
- Modify: `packages/service/src/lookups/admin_router.py:545-558` (PYR-007, PYR-008)
- Modify: `packages/service/src/permissions/router.py:73` (PYR-012)
- Modify: `packages/service/src/permissions/router.py:312,314,315` (PYR-013)
- Modify: `packages/service/src/permissions/service.py:51,52` (PYR-041)

- [ ] **Step 1: 看 admin_router.py:545-558 实际代码**

```bash
sed -n '540,565p' /home/deyuan/rag/rag/packages/service/src/lookups/admin_router.py
```

确认是 ORM `select().scalars()` 跟 Optional[JSONB] 推断.

- [ ] **Step 2: 改 admin_router.py 加 cast()**

```python
# 改前 (line 545-558 附近)
results = await session.execute(select(AuditLog).where(...))
for row in results.scalars():
    meta = row.meta or {}  # type: ignore[union-attr]
    actor = row.actor_id  # type: ignore[arg-type]

# 改后
from typing import cast
results = await session.execute(select(AuditLog).where(...))
for row in results.scalars():
    row_typed = cast(AuditLog, row)  # PYR-007 防御
    meta = cast(dict, row_typed.meta or {})  # PYR-008 防御
    actor = row_typed.actor_id
```

并删掉原来的 `# type: ignore[union-attr]` / `# type: ignore[arg-type]` 注释.

- [ ] **Step 3: 改 permissions/router.py:73**

```bash
sed -n '70,80p' /home/deyuan/rag/rag/packages/service/src/permissions/router.py
```

```python
# 改前
if r.name != "super_admin":  # type: ignore[operator]

# 改后
from typing import cast
if cast(str, r.name) != "super_admin":
```

并删 `# type: ignore[operator]`.

- [ ] **Step 4: 改 permissions/router.py:312,314,315 + permissions/service.py:51,52**

```python
# 改前 (router.py:312,314,315 附近)
role.name = new_name  # type: ignore[assignment]
role.is_active = is_active  # type: ignore[assignment]
role.sort_order = sort_order  # type: ignore[assignment]

# 改后
from typing import cast
role.name = cast(str, new_name)
role.is_active = cast(bool, is_active)
role.sort_order = cast(int, sort_order)
```

```python
# 改前 (service.py:51,52 附近)
record.value = value  # type: ignore[assignment]
record.description = description  # type: ignore[assignment]

# 改后
from typing import cast
record.value = cast(str, value)
record.description = cast(str | None, description)
```

具体类型名查 [packages/service/src/permissions/](../../packages/service/src/permissions/) 实际 model 定义.

- [ ] **Step 5: 跑 pyright 验证 (单文件)**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/lookups/admin_router.py src/permissions/router.py src/permissions/service.py 2>&1 | tail -10
```

Expected: 0 errors. **如果 FAIL**: cast 类型可能跟实际 mock 行为不匹配, 调整.

- [ ] **Step 6: 跑相关测试**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/lookups/ tests/permissions/ -q 2>&1 | tail -10
```

Expected: 0 fail (不破坏业务). **如果 FAIL**: 看具体错, 可能 ORM Column 类型 cast 后 mock fixture 类型不匹配.

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/lookups/ packages/service/src/permissions/ && git commit -m "refactor(service): 6 处 ORM Column 加 cast() 防御 (PYR-007/008/012/013/041)"
```

---

## Task 2: 修 L2 4 个新 error (2 ABC + 2 test_login)

**Files:**
- Modify: `packages/service/src/ingest/pdf_processing/converters/kreuzberg.py:40`
- Modify: `packages/service/src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:24`
- Modify: `packages/service/tests/auth/test_login.py:202`

- [ ] **Step 1: 看 kreuzberg.py:40**

```bash
sed -n '30,50p' /home/deyuan/rag/rag/packages/service/src/ingest/pdf_processing/converters/kreuzberg.py
```

确认是 `convert` 方法签名不匹配 Converter 父类 ABC.

- [ ] **Step 2: 改 kreuzberg.py 签名匹配 ABC**

```python
# 改前
def convert(self, file_path: str) -> ConvertResult:  # type: ignore[override]
    ...

# 改后
# Converter ABC 是 async convert
async def convert(self, file_path: str) -> ConvertResult:
    ...
```

具体 ABC 签名查 [packages/service/src/ingest/pdf_processing/converters/base.py](../../packages/service/src/ingest/pdf_processing/converters/base.py).

- [ ] **Step 3: 改 pymupdf_extractor.py:24**

```bash
sed -n '20,35p' /home/deyuan/rag/rag/packages/service/src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py
```

确认是 `extract_tables` 方法签名不匹配 TableExtractor ABC. 同样改签名匹配.

- [ ] **Step 4: 改 test_login.py:202**

```bash
sed -n '195,210p' /home/deyuan/rag/rag/packages/service/tests/auth/test_login.py
```

```python
# 改前
async def test_login():
    try:
        r = await client.post(...)
    except Exception:
        pass
    assert r.status_code == 200  # r 可能未绑定

# 改后
async def test_login():
    r = None  # 初始化避免 unbound
    try:
        r = await client.post(...)
    except Exception:
        pass
    assert r is not None and r.status_code == 200
```

- [ ] **Step 5: 跑 pyright 验证**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pyright src/ingest/pdf_processing/converters/kreuzberg.py src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py tests/auth/test_login.py 2>&1 | tail -10
```

Expected: 0 errors. **如果 FAIL**: 看具体错, 可能 ABC 签名不只一处不匹配.

- [ ] **Step 6: 跑相关测试**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pytest tests/ingest/ tests/auth/test_login.py -q 2>&1 | tail -10
```

Expected: 0 fail (kreuzberg/pymupdf converter 测试不挂, test_login 业务通过).

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/src/ingest/ packages/service/tests/auth/test_login.py && git commit -m "fix(service): L2 4 个新 error 修复 (kreuzberg/pymupdf ABC + test_login r 初始化)"
```

---

## Task 3: pyrightconfig.json 升级 (basic→standard + 6 optional)

**Files:**
- Modify: `packages/service/pyrightconfig.json`

**Interfaces:**
- Consumes: 当前 pyrightconfig.json (basic mode, 5 个 reportUnknown* 设 none)
- Produces: standard mode + 6 个 reportOptional* 设 error

- [ ] **Step 1: 备份当前 pyrightconfig.json**

```bash
cp /home/deyuan/rag/rag/packages/service/pyrightconfig.json /tmp/pyrightconfig.json.bak
```

**关键约束**: 万一升级后 0 error 没维持, 用 backup 恢复.

- [ ] **Step 2: 改 pyrightconfig.json**

替换 [packages/service/pyrightconfig.json](../../packages/service/pyrightconfig.json) 内容为:

```json
{
  "include": ["src", "tests", "scripts"],
  "exclude": [
    "**/__pycache__",
    "**/.venv",
    "**/node_modules",
    "**/data",
    "**/ingest_uploads",
    "**/reports"
  ],
  "pythonVersion": "3.14",
  "typeCheckingMode": "standard",
  "reportMissingTypeStubs": "none",
  "reportUnknownMemberType": "none",
  "reportUnknownVariableType": "none",
  "reportUnknownArgumentType": "none",
  "reportUnknownParameterType": "none",
  "reportUnknownLambdaType": "none",
  "reportOptionalMemberAccess": "error",
  "reportOptionalSubscript": "error",
  "reportOptionalCall": "error",
  "reportOptionalIterable": "error",
  "reportOptionalContains": "error",
  "reportOptionalChain": "error"
}
```

**改了什么**:
- `typeCheckingMode: "basic" → "standard"`
- 加 6 条 `reportOptional*: "error"` (L3 零成本开启)

- [ ] **Step 3: 跑 pyright 验证 0 error**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run pyright 2>&1 | tail -10
```

Expected: 0 errors. **如果 FAIL**:
- 看具体 error 数量, 应该跟 A4 报告 L2 + L3 命中数一致 (4 new + 6 已有 0 = 6 总)
- 如果多于 6 → Task 1/Task 2 漏修了, 回滚 config, 补修, 再升级
- 如果 0 → 完美, 进入 Step 4

- [ ] **Step 4: 跑 ruff + pytest 交叉验证**

```bash
cd /home/deyuan/rag/rag/packages/service && uv run ruff check src/ 2>&1 | tail -5
cd /home/deyuan/rag/rag/packages/service && uv run pytest -q 2>&1 | tail -10
```

Expected: ruff 0 error, pytest fail 数量不增.

- [ ] **Step 5: 跑 frontend tsc (交叉验证) + vitest (跨包)**

```bash
cd /home/deyuan/rag/rag/packages/web && bun run typecheck 2>&1 | tail -5
```

Expected: tsc 0 error (跟改前一致, 不影响前端).

- [ ] **Step 6: 清理 backup**

```bash
rm /tmp/pyrightconfig.json.bak
```

- [ ] **Step 7: Commit**

```bash
cd /home/deyuan/rag/rag && git add packages/service/pyrightconfig.json && git commit -m "feat(service): pyright 升级 basic→standard + 6 optional 规则 (0 new error)"
```

---

## Task 4: 全量验证 + 更新 checklist

- [ ] **Step 1: 跑后端全量 pyright + ruff + pytest**

```bash
cd /home/deyuan/rag/rag/packages/service
uv run pyright 2>&1 | tail -5
uv run ruff check src/ tests/ 2>&1 | tail -5
uv run pytest -q 2>&1 | tail -10
```

Expected: pyright 0 error, ruff 0 error, pytest fail 数量不增.

- [ ] **Step 2: 跑前端 tsc + oxlint + vitest (交叉验证)**

```bash
cd /home/deyuan/rag/rag/packages/web
bun run typecheck 2>&1 | tail -5
bun run lint 2>&1 | tail -5
bun run test 2>&1 | tail -10
```

Expected: 全部 0 error, vitest fail 数量不增.

- [ ] **Step 3: 更新 `docs/audit/2026-07-08-findings.md` checklist**

打开 [2026-07-08-findings.md](../../docs/audit/2026-07-08-findings.md), 在 P3 优先级段加 commit hash 引用:

```markdown
### 修复进度 (P3 pyright 升级)

| 任务 | commit | 状态 |
|---|---|---|
| Task 1: 6 处 ORM cast() 防御 | <hash> | ✅ |
| Task 2: L2 4 个新 error 修复 | <hash> | ✅ |
| Task 3: pyrightconfig 升级 standard + 6 optional | <hash> | ✅ |
```

- [ ] **Step 4: Commit checklist 更新**

```bash
cd /home/deyuan/rag/rag && git add docs/audit/2026-07-08-findings.md && git commit -m "docs(audit): 标记 P3 pyright 升级完成 (3 commit hash)"
```

---

## Self-Review 检查

**1. Spec coverage** (vs A4 P3):
- ✅ L2 standard (Task 1 + 2 + 3)
- ✅ L3 6 optional 规则 (Task 3)
- ✅ [rule-up] 6 处 ORM cast() (Task 1)
- ✅ L2 4 new error 修复 (Task 2)
- ✅ checklist 更新 (Task 4.3)

**2. Placeholder scan**:
- ✅ 无 "TBD/TODO" 占位
- ✅ 所有代码块 (cast, pyrightconfig) 完整
- ✅ 文件路径全部 absolute
- ✅ 备份 + 恢复机制

**3. Type consistency**:
- ✅ `cast(AuditLog, row)`, `cast(dict, row.meta or {})` 一致
- ✅ `cast(str, r.name)`, `cast(str, new_name)` 一致
- ✅ 6 条 reportOptional* 名称跟 A4 报告完全一致

**Gaps 检查**:
- ⚠️ Task 1 cast 类型可能跟 mock 行为不匹配 — 已说明 pytest 验证 + 回滚
- ⚠️ Task 2 ABC 签名不只一处不匹配 — 已说明 grep 验证
- ⚠️ Task 3 升级后 0 error 没维持 — backup 恢复机制
- ⚠️ pyrightconfig 修改触犯"严禁修改配置文件"铁律? — A4 报告 + 用户授权 (Plan 启动前确认), 是"升规则"不是"绕过"

---

## 不实施

- **A4 L1 reportUnknown* warning** (7,569 warning) — Plan 后续 backlog, 升后 1 行 JSON 即可
- **A4 L4 strict** (1,836 error) — 等 L1 backlog 消化, 远期
- **6 条 [stub]** (第三方库限制) — 不可修
- **38 条 [test-mock]** (测试故意) — 不可修

## 修复后预期

| 指标 | 改前 | 改后 | 变化 |
|---|---|---|---|
| pyright typeCheckingMode | basic | standard | 升级 |
| pyright error | 2 | 2 | 0 (L2 + L3 净增 0) |
| 6 reportOptional* 规则 | 未设 | error | 新增白嫖 |
| ORM cast 防御 | 0 处 | 6 处 | 升 standard 准备 |
| L2 4 new error 修复 | -- | 4/4 修 | -- |

## 4 plans 汇总 (P0/P1/P2/P3)

| Plan | 范围 | 净消 ignore | 测试 fail 减 | 工作量 |
|---|---|---|---|---|
| A (P0) | useTranslations + ingest + 4 单点 | -- | -59 | 1 周 |
| B (P1) | pyright [dead] + 8 fixable-code + PYR-034 | -100 | -- | 1 周 |
| C (P2) | oxlintrc overrides + 阈值 + sed stale | -128 | -- | 1 周 |
| D (P3) | pyright standard + 6 optional + ORM cast | -- | 0 new error | 1 周 |
| **合计** | **全 4 plan** | **228** | **-59** | **4 周** |
