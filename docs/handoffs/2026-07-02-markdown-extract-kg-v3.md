# Markdown Extract KG — Handoff 2026-07-02

## 任务总体进展

**Goal**: 上传 Markdown → 异步抽取 → 预览校对 → 3 出口 (Neo4j / JSONL / Cypher) 的 4 PR 大型功能

**当前状态**: PR1 + PR2 全部完成,PR3 完成 Task 14 + 15 (Task 15 待修 pyright 后 commit),PR4 没动

**已 commit**: 11 个 PR1+PR2 commits + 0 个 PR3 commits 已正式 commit (Task 14 已 commit,Task 15 还在 working tree)

---

## 已完成 (11 commits)

### PR1: dataset label 隔离 + Neo4j 索引 (5+1 commits)
- `998bb2a8` feat(core): 加 user_hash util (后续被 reset,**已不存在,大改动前用户撤了 docs**
- 这里是 v3 分支实际 commit 列表:
  - `6adca939` feat(kg): KgClient dataset label 隔离 + datasets 白名单 (env KG_ALLOWED_DATASETS)
  - `cb70d6b7` feat(kg): main.py 启动时 bootstrap KG_ALLOWED_DATASETS 白名单
  - `8224bc21` feat(kg): router 加 dataset query param + GET /datasets + require_page kg 鉴权
  - `51e5f19c` feat(kg): Neo4j dataset label 索引 cypher + init script + 删 graphifyy dev dep
  - `63b42652` test(kg): 改写 init_neo4j_script test 用直接调 main() 替代 subprocess

### PR2: Splitters + Extractors + 配置 + 迁移 (8 commits)
- `2bcbb657` feat(kg): BaseSplitter Protocol + HeadingSplitter
- `568c6e06` feat(kg): TokenSplitter (tiktoken cl100k_base 滑窗)
- `35c3835c` feat(kg): SemanticSplitter (句切 + cosine 距离, 降级 heading)
- `f90f6315` feat(kg): BaseExtractor Protocol + ExtractedEntity/Relation/Result + RuleType Literal
- `4cdb3cbd` feat(kg): SpacyRuleExtractor
- `5be88c4b` feat(kg): 2 个 extractor yaml + config_loader
- `fdadb8d2` feat(kg): LlmPydanticExtractor (含 union-attr # type: ignore 注解)
- `69b32a08` feat(kg): alembic 迁移 kg_extract_items (JSONB + dataset 字段 + AST 验证)

### PR3: extract_runner + 5 端点 (Task 14 + Task 15)
- `4072bf88` feat(kg): extract_runner 后台 pipeline (含 dataset 透传) — Task 14 ✅
- Task 15 已完成代码 + 测试,**但 commit 失败**: test_router_extract.py 有 2 个 pyright 错误(下"当前 bug" 章节)

---

## 当前 Bug (Task 15 commit 阻塞)

### 文件
`packages/service/tests/kg/test_router_extract.py`

### 2 个 pyright 错误
```
tests/kg/test_router_extract.py:42:16 - error: 无法访问类"LlmPydanticExtractor"的属性"nlp"
  属性"nlp"未知 (reportAttributeAccessIssue)
tests/kg/test_router_extract.py:51:16 - error: 无法访问类"SpacyRuleExtractor"的属性"llm"
  属性"llm"未知 (reportAttributeAccessIssue)
```

### 修复方式
测试 line 42 / 51 是这种写法:
```python
ext = _build_extractor("spacy_rule")
assert ext.nlp is None  # ❌ pyright: LlmPydanticExtractor 没 nlp
```

应该改成 (from actual extractor class):
```python
ext = _build_extractor("spacy_rule")
assert ext.extractor_id == "spacy_rule"  # ✅
assert isinstance(ext.nlp, type(None))  # 用 type(None) 而不是 is None
```

或者用 `# type: ignore[attr-defined]` (项目规约要求具体错误码)。

或者用 cast(Any, ext) 后访问。

### 修复后
加 `pyright` 期望 0 错,然后:
```bash
git add packages/service/src/kg/router.py packages/service/tests/kg/test_router_extract.py
git commit -m "feat(kg): 5 端点 list_extractors/list_splitters/upload/start/tasks + BackgroundTasks + dataset 透传"
```

预期 commit 成功(pyright 0 错)。

---

## 未完成 (PR3 剩余 + PR4 全)

### Task 16: 4 端点 preview/items PATCH/commit/export
- 在 `packages/service/src/kg/router.py` 末尾追加
- 测试: `tests/kg/test_commit_export.py` (新建,4 test)

### Task 17: 7d cron cleanup
- 创建 `packages/service/src/kg/cron.py`
- 测试: `tests/kg/test_cron.py` (1 test,AST 验证)

### Task 18: PR3 全量验证
- `uv run pytest tests/kg/ -v`
- `uv run ruff format && uv run ruff check --fix && uv run pyright`

### PR4: 6 commits
- Task 19: lib/api/knowledge.ts 加 9 wrapper + 8 type + 9 vitest test
- Task 20: 7 个 BFF route 透传
- Task 21: i18n 同步 (zh + en + 13 key)
- Task 22: knowledge-tabs.tsx 加 1 行
- Task 23: 3 个前端页面 (extract + progress + preview,含 dataset 下拉)
- Task 24: Playwright e2e + 收尾

---

## 项目规约 (跨 PR 不变量, 给接手人)

### 用户设计决策(v3, 2026-07-01)
- 项目是**内部项目,只有管理员能修改**, **单一 Neo4j Community Edition 1 database** (调研:CE 限 1 standard DB)
- 用 **dataset label 隔离**不同数据集(motor / plc / sensor)
- env `KG_ALLOWED_DATASETS=motor,plc,sensor` 单源白名单 (CLAUDE.md §测试隔离强制)
- **不加** user_hash / (label,key) 唯一约束 (跟 v1 不同)
- 全部 [PR3 端点] + [PR4 3 页面] 都必传 `dataset` 参数

### 关键基础设施位置
- 白名单: `packages/service/src/kg/datasets.py`
- KgClient: `packages/service/src/kg/client.py` (所有方法透传 `dataset` 参数,cypher 加 `<Dataset>` label)
- TaskStore: `packages/service/src/kg/tasks.py` (v1 实现,纯内存,需 .submit() 注册后再 .mark_*)
- extract_runner: `packages/service/src/kg/extract_runner.py` (Task 14 透传 `dataset` 到 `KgClient(dataset=dataset)`)
- audit_record: `kg_audit` ORM 表 (`actor=None` 仍是允许,actor_id 字段在 detail)

### ⚠️ 已踩坑 / 给接手人警告

1. **`monkeypatch.setattr("src.kg.extract_runner.session_scope", ...)`**
   `extract_runner.py` 用 `from src.storage import session_scope` 局部绑定,monkeypatch 必须打 `src.kg.extract_runner.session_scope` 不能打 `src.storage.session_scope`。Task 14 test 我踩过这坑,改对了。

2. **`@audited` 装饰器把 sync def 包成 async wrapper**
   - 装饰器在 `packages/service/src/core/audit.py:55-79`
   - 影响: 任何被 `@audited(...)` 包裹的 endpoint 不能在测试里直接当 sync 函数调
   - 解决: 测子函数(如 `_build_extractor`) 或测 validator (如 `datasets.validate_dataset`),不要测 `@audited` 包裹的 endpoint

3. **TaskStore 需先 .submit() 注册**
   - Task 14 测 `mark_running(task_id) → TaskNotFoundError` 是因为没先 `.submit(task_id)`
   - 解法: `task_id = task_store.submit("kg_extract", {...})` 拿随机 UUID 的 task_id
   - 错误信息是中文乱码(Windows bash),看 stderr 还是能看到是 TaskNotFoundError

4. **uv remove graphifyy 报"not found"**
   - 原因: graphifyy 在 `[dependency-groups].dev`,不是 `[project].dependencies`
   - 解决: 直接编辑 `uv.lock` 里的 `[[package.dev-dependencies]]` + `[package.metadata.requires-dev]` 双删,加 pyproject.toml 注释

5. **Python 3.14 + Windows bash 中文乱码**
   - 不影响功能,但测试报错时 `f"任务不存在: {task_id}"` 会变 `\xb9\xfe\xcc\xe5\xb2\xbb...`
   - 解码方式: stderr 是 UTF-8,但 console 默认 GBK

6. **lint-staged pytest --picked 0 test 时会 exit 1**
   - 当前所有 commit 都过了(项目用 `--strict-markers + 自动 pytest --picked`)

7. **ConfigLoader 路径**
   - `src/kg/config_loader.py` 用 `parents[2]` (→ packages/service),别用 parents[3]
   - `tests/kg/test_init_neo4j_script.py` 用 `parents[2]` (→ packages/service,找 cypher 文件)

8. **ruff auto-fix 不能修 `# type: ignore` 加错误码**
   - pyright 报 unknown attr 时,加 `# type: ignore[attr-defined]` 比 `# type: ignore[union-attr]` 准
   - Task 15 修复:用 `cast(Any, ext).nlp` 或加 ignore 注解

---

## 分支信息

```bash
git branch feature/markdown-extract-kg-v3
git log --oneline | head -20
git status  # 当前 working tree: 改完 task 15 但 pyright 报错未 commit
git diff packages/service/src/kg/router.py | wc -l  # 约 +150 行 (5 端点)
```

---

## 任务清单 (接手人参照)

```bash
# Task 15: 修 pyright + commit (最快, ~5min)
cd packages/service
# 修 test_router_extract.py line 42 / 51 的 ext.nlp / ext.llm 访问
# 方案 A: cast(Any, ext) 后访问; 方案 B: 加 # type: ignore[attr-defined]
git add packages/service/src/kg/router.py packages/service/tests/kg/test_router_extract.py
git commit -m "feat(kg): 5 端点 list_extractors/list_splitters/upload/start/tasks + BackgroundTasks + dataset 透传"

# Task 16: 4 端点 preview/items PATCH/commit/export (~1h)
# 在 router.py 末尾追加 (参考 PR3 plan §Task 16 完整代码)
# commit: "feat(kg): 4 端点 preview/items PATCH/commit/export + @audited 4 处 + dataset 透传"

# Task 17: 7d cron cleanup (~30min)
# 创建 src/kg/cron.py
# 测试 AST 验证 1 个
# commit: "feat(kg): cron cleanup_old_extract_items (7d hard-delete)"

# Task 18: 全量验证 (~10min)
uv run pytest tests/kg/ -v
uv run ruff format && uv run ruff check --fix && uv run pyright
```

---

## Pre-existing (跟本 PR 无关)

- `tests/conftest.py` 有 autouse mock 矩阵 (engine / redis / neo4j / permission_cache)
- 22 fail + 38 errors 在 pre-existing 列表 (见 packages/service/KNOWN_ISSUES.md)
- 本 PR 所有新测试全 mock,**0 真 PG/Neo4j** (AST 验证)

---

## 接手人建议

1. **先解决 Task 15 的 pyright 问题** (5min)
2. **顺序做 Task 16 → 17 → 18** (PR3 收尾)
3. **PR4 全量 6 commit** (~6h)
4. **总剩余工作量**: 估计 8-10h (含 PR4 6 前端页面)
5. **优先 PR3 收尾**,PR4 是大块 UI 工作
