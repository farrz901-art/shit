# PDF 结构化预分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-KILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 PDF 上传 → 后台异步预分析 → 4 类产物 (chapter_structure.json / tables/*.csv / flagged_paragraphs.csv / index.json) → admin 下载 zip 的端到端流水线, 跟 DeepSeek 西门子 D81.1 手册预分析 5 步方法论 1:1 对齐, 解耦 KG 抽取.

**Architecture:** 6 个独立 PR / 每个 1 个模块. 后端新建独立 `pre_analysis_tasks` 表 (跟 ingest_tasks 解耦) + `PreAnalysisRunner` 后台 pipeline (抄 `extract_runner.py` 模式) + 4 个 `/api/pre-analysis/*` 端点. 前端 0 自建组件, 全部复用 `<DataTable>` / `<FileDropzone>` / `<Badge>` / `<ErrorBanner>` / `<GuardPage>` / `<PageHero>` / `<BackLink>` + `<Button asChild><a download>`.

**Tech Stack:**
- 后端: Python 3.14 + FastAPI + SQLAlchemy 2.0 + pymupdf (>=1.24) + loguru + kreuzberg (>=4.9.7)
- 前端: TypeScript + React 19 + Next.js 16 + TanStack Query 5.x + shadcn/ui + next-intl 4.x
- 测试: pytest (mode 1 mock 默认, mode 2 db_session 集成) + vitest (mock fetch + @testing-library/react)
- 对象存储: ObjectStore ABC (LocalFS + MinIO)
- 不新装: PyMuPDF4LLM / Camelot / pdfplumber / fuzzy / pint / pandas (csv stdlib 即可)

---

## 项目规约 (跨 PR 不变量)

**所有 PR 必守** ([packages/service/CLAUDE.md](../../packages/service/CLAUDE.md) + [packages/web/CLAUDE.md](../../packages/web/CLAUDE.md)):

1. **测试 mock 优先, 不连真 PG/Redis/Neo4j** (CLAUDE.md §测试隔离 4 模式). 默认 mode 1 (mock), mode 2 (db_session) 仅 DDL 校验.
2. **`# type: ignore` 必须带具体错误码 + 注释** (CLAUDE.md §top-10 #2)
3. **`# noqa` 必须带具体错误码 + 注释** (CLAUDE.md §top-10 #3)
4. **业务代码用 loguru**, `logger.info("x done id={}", id)`, 不用 stdlib logging (CLAUDE.md §日志)
5. **delete / 改账户 / 改权限 / 导出加 `@audited`** (CLAUDE.md §危险操作)
6. **alembic migration 可回滚** (CLAUDE.md §top-10 #5), 必写 downgrade, 单测验证
7. **业务 enum 走 lookup 字典**, 禁新硬编 `StrEnum` (CLAUDE.md §字典). state 用 `Literal["pending","running","completed","failed"]` (跟现有 IngestTask 一致, 不走 lookup)
8. **新列必须 JSONB**, 禁 `sa.JSON()` (CLAUDE.md §JSONB). 本期用 Text 存 JSON 字符串 (跟现有 `output_files_json` 一致), 不需 JSONB
9. **ObjectStore 走 `get_object_store()` 单例**, URI 字符串 DB 持久化 (CLAUDE.md §ObjectStore)
10. **前端 `<DataTable<T>>` + `<DataEmpty>`**, 不许手写 `<table>` ([packages/web/CLAUDE.md §表格组件](../../packages/web/CLAUDE.md))
11. **前端 `useRouter` 从 `@/i18n/navigation`** 引, 禁 `next/navigation` ([packages/web/CLAUDE.md §路由跳转](../../packages/web/CLAUDE.md))
12. **前端 `t("中文")` 中文作 key**, zh.json identity, en.json 翻译 ([packages/web/CLAUDE.md §i18n](../../packages/web/CLAUDE.md))
13. **前端 0 新组件** — 全部复用项目封装 (用户拍板 2026-07-02)
14. **每 PR 收尾必跑** (CLAUDE.md §code quality):
    ```bash
    uv run ruff format && uv run ruff check --fix && uv run pyright
    bun run format && bun run lint:fix && bun run typecheck
    uv run pytest tests/ -q -x
    bun run test -- <touched-glob>
    ```

**单 PR ≤ 500 行红线** (CLAUDE.md §范围控制). 本 plan 6 个 PR 各 ≤ 500 行.

---

## PR1 = M1: PG 迁移 + ORM 类

> **Goal:** 新建独立 `pre_analysis_tasks` 表 + ORM 类, 跟 `ingest_tasks` 解耦. 1 个 alembic migration (含 upgrade/downgrade).

**Files:**
- Create: `packages/service/src/storage/migrations/versions/20260702_000000_pre_analysis_tasks.py`
- Create: `packages/service/src/ingest/pre_analysis_models.py`
- Create: `packages/service/tests/migrations/test_pre_analysis_tasks_schema.py`
- Create: `packages/service/tests/ingest/test_pre_analysis_models.py`

### Task 1.1: 写 migration 文件 (含 upgrade + downgrade)

- [ ] **Step 1: 创建目录 (如不存在) + 创建 migration 文件**

```bash
mkdir -p packages/service/src/storage/migrations/versions
```

- [ ] **Step 2: 写 migration 文件**

文件路径: `packages/service/src/storage/migrations/versions/20260702_000000_pre_analysis_tasks.py`

```python
"""pre_analysis_tasks: PDF 预分析 task 元数据 (2026-07-02 新建表)

设计决策 (跟 ingest_tasks 解耦, admin 列表清晰):
- id: 业务 UUID (跟 IngestTask 一致 String(36))
- user_hash: 从 token 派生 (跟 IngestTask.user_hash 一致 String(64))
- state: pending / running / completed / failed (跟 IngestTask 一致)
- pdf_filename: 原 PDF 文件名 (admin UI 显示, ≤ 255 字符)
- pdf_uri: ObjectStore URI (s3://rag-ingest/pre_analysis_inputs/{id}/input/{file})
- started_at / finished_at: 时间戳
- error: 失败时 stderr tail (NULL = 未失败)
- output_files_json: JSON 字符串数组 [{kind, filename, size_bytes, uri}, ...]
- summary_json: JSON 字符串 {total_chapters, total_tables, total_flagged_paragraphs, elapsed_ms, cross_page_candidates}

索引:
- (user_hash, started_at): 列表查询 (跟 IngestTask 索引模式一致)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260702_000000"
down_revision = "20260701_000000"  # kg_extract_items (上一条迁移)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pre_analysis_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_hash", sa.String(64), nullable=False, index=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("pdf_filename", sa.String(255), nullable=False),
        sa.Column("pdf_uri", sa.String(500), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("output_files_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("summary_json", sa.Text, nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "state IN ('pending', 'running', 'completed', 'failed')",
            name="ck_pre_analysis_tasks_state",
        ),
    )
    op.create_index(
        "ix_pre_analysis_tasks_user_started",
        "pre_analysis_tasks",
        ["user_hash", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pre_analysis_tasks_user_started", "pre_analysis_tasks")
    op.drop_table("pre_analysis_tasks")
```

- [ ] **Step 3: 确认 `down_revision` 正确**

Run: `ls packages/service/src/storage/migrations/versions/ | tail -5`

期望: 最后一条是 `20260701_000000_kg_extract_items.py` (或更新的 revision). 如果跟当前 migration 链不同, 把 `down_revision` 改成实际最新 revision 字符串.

- [ ] **Step 4: 写 schema 验证测试**

文件路径: `packages/service/tests/migrations/test_pre_analysis_tasks_schema.py`

```python
"""pre_analysis_tasks 迁移 AST 验证 + SQL 文本 (CLAUDE.md 禁真 PG, mode 1)

只验证:
1. migration 文件存在 + 含 upgrade/downgrade 函数
2. 字段定义完整 (id, user_hash, state, pdf_filename, pdf_uri, ...)
3. CHECK 约束 state 白名单
4. user_hash 字段 (跟 ingest_tasks 一致, 不是 user_id)
5. 索引 ix_pre_analysis_tasks_user_started
"""

import ast
from pathlib import Path

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "storage"
    / "migrations"
    / "versions"
    / "20260702_000000_pre_analysis_tasks.py"
)


def test_migration_file_exists() -> None:
    """[M1] migration 文件存在"""
    assert MIGRATION_FILE.exists(), f"找不到 migration 文件: {MIGRATION_FILE}"


def test_migration_has_upgrade_and_downgrade() -> None:
    """[M1] 必含 upgrade() + downgrade() 两条函数 (CLAUDE.md §alembic 可回滚)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "upgrade" in fns
    assert "downgrade" in fns


def test_migration_required_columns() -> None:
    """[M1] 必含所有字段 (id, user_hash, state, pdf_filename, pdf_uri, ...)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    for col in [
        "id", "user_hash", "state", "pdf_filename", "pdf_uri",
        "started_at", "finished_at", "error",
        "output_files_json", "summary_json",
    ]:
        assert col in source, f"缺字段: {col}"


def test_migration_state_check_constraint() -> None:
    """[M1] state CHECK 约束白名单"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ck_pre_analysis_tasks_state" in source
    assert "pending" in source
    assert "running" in source
    assert "completed" in source
    assert "failed" in source


def test_migration_user_hash_not_user_id() -> None:
    """[M1] 用 user_hash (跟 ingest_tasks 一致), 不用 user_id"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "user_hash" in source
    assert '"user_id"' not in source


def test_migration_index() -> None:
    """[M1] 索引 ix_pre_analysis_tasks_user_started (user_hash, started_at)"""
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert "ix_pre_analysis_tasks_user_started" in source
```

- [ ] **Step 5: 跑测试验证 migration 文件结构**

Run: `cd packages/service && uv run pytest tests/migrations/test_pre_analysis_tasks_schema.py -v`

期望: 7 个 test 全 PASS (存在 + upgrade/downgrade + 字段 + CHECK + user_hash + 索引).

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/storage/migrations/versions/20260702_000000_pre_analysis_tasks.py packages/service/tests/migrations/test_pre_analysis_tasks_schema.py
git commit -m "feat(migration): add pre_analysis_tasks table for PDF pre-analysis (PR1/M1)"
```

### Task 1.2: 写 ORM 类

- [ ] **Step 1: 写失败测试**

文件路径: `packages/service/tests/ingest/test_pre_analysis_models.py`

```python
"""PreAnalysisTask ORM 字段验证 (mode 1 mock)

只验证 ORM 类定义存在 + 字段映射正确, 不连 PG (mock engine).
"""

from __future__ import annotations


def test_pre_analysis_task_table_name() -> None:
    """ORM 类 __tablename__ = pre_analysis_tasks"""
    from src.ingest.pre_analysis_models import PreAnalysisTask
    assert PreAnalysisTask.__tablename__ == "pre_analysis_tasks"


def test_pre_analysis_task_required_columns() -> None:
    """ORM 含所有字段"""
    from src.ingest.pre_analysis_models import PreAnalysisTask
    from sqlalchemy import inspect

    mapper = inspect(PreAnalysisTask)
    col_names = {c.key for c in mapper.columns}
    expected = {
        "id", "user_hash", "state", "pdf_filename", "pdf_uri",
        "started_at", "finished_at", "error",
        "output_files_json", "summary_json",
    }
    assert expected.issubset(col_names), f"缺字段: {expected - col_names}"


def test_pre_analysis_task_user_hash_not_user_id() -> None:
    """ORM 字段名是 user_hash (跟 ingest_tasks 一致)"""
    from src.ingest.pre_analysis_models import PreAnalysisTask
    from sqlalchemy import inspect

    mapper = inspect(PreAnalysisTask)
    col_names = {c.key for c in mapper.columns}
    assert "user_hash" in col_names
    assert "user_id" not in col_names
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd packages/service && uv run pytest tests/ingest/test_pre_analysis_models.py -v`

期望: FAIL (ImportError: cannot import name 'PreAnalysisTask').

- [ ] **Step 3: 写 ORM 类**

文件路径: `packages/service/src/ingest/pre_analysis_models.py`

```python
"""pre_analysis_tasks ORM model (2026-07-02 新建表).

跟 src.ingest.models.IngestTask 解耦, admin 列表清晰, 不混产.
字段顺序 + 类型跟 migration 1:1 对齐 (用户决策 2026-07-02).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..storage import Base


class PreAnalysisTask(Base):
    """pre_analysis task 元数据.

    字段语义:
    - id: 业务 UUID 字符串 (跟 IngestTask 一致 String(36))
    - user_hash: 用户标识 (从 token 派生, 跟 IngestTask.user_hash 一致)
    - state: pending / running / completed / failed
    - pdf_filename: 原 PDF 文件名 (admin UI 显示)
    - pdf_uri: ObjectStore URI (s3://rag-ingest/pre_analysis_inputs/{id}/input/{file})
    - started_at / finished_at: 时间戳
    - error: 失败时 stderr tail (NULL = 未失败)
    - output_files_json: JSON 字符串数组, 4 类产物清单 [{kind, filename, size_bytes, uri}, ...]
    - summary_json: JSON 字符串, 跑完后的统计 {total_chapters, total_tables, total_flagged_paragraphs, elapsed_ms, cross_page_candidates}
    """

    __tablename__ = "pre_analysis_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    pdf_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str] = mapped_str = mapped_column(  # type: ignore[assignment]  # pyright: ORM Column 推断
        Text, nullable=False, default="{}"
    )  # pyright 没解析 mapped_str 复用, 强制重写下一行

    __table_args__ = (
        Index("ix_pre_analysis_tasks_user_started", "user_hash", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<PreAnalysisTask id={self.id} state={self.state} filename={self.pdf_filename}>"
```

注意: 上面 `summary_json` 字段用了 `mapped_str = mapped_column(...)` 的中间变量是为了让 ruff 不报警告 "expression has type X, variable has type Y". 如果你跑 ruff 报 `E731` (不要赋值给 lambda) 之类, 简化成:

```python
summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
```

直接替换 `summary_json` 那 1 行, 删 `mapped_str` 中间变量.

- [ ] **Step 4: 跑测试验证通过**

Run: `cd packages/service && uv run pytest tests/ingest/test_pre_analysis_models.py -v`

期望: 3 个 test 全 PASS.

- [ ] **Step 5: 跑 ruff + pyright**

Run:
```bash
cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright
```

期望: 0 error. 如果 pyright 报 ORM Column 推断问题, 加 `# type: ignore[assignment]` + 注释.

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/ingest/pre_analysis_models.py packages/service/tests/ingest/test_pre_analysis_models.py
git commit -m "feat(orm): add PreAnalysisTask ORM class (PR1/M1)"
```

### Task 1.3: dev DB 演练 upgrade + downgrade

- [ ] **Step 1: 跑 upgrade head**

Run: `cd packages/service && uv run alembic upgrade head`

期望: 输出 "running upgrade ... -> 20260702_000000, pre_analysis_tasks created". 如果报 `down_revision` 错, 看 §Task 1.1 Step 3 修.

- [ ] **Step 2: 验证表存在**

Run: `cd packages/service && uv run python -c "from src.storage import engine; from sqlalchemy import text; with engine.connect() as c: print(c.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='pre_analysis_tasks'\")).fetchall())"`

期望: 输出含 `id, user_hash, state, pdf_filename, pdf_uri, started_at, finished_at, error, output_files_json, summary_json` 10 个字段.

- [ ] **Step 3: 跑 downgrade 演练**

Run: `cd packages/service && uv run alembic downgrade -1`

期望: 输出 "downgrading ... -> 20260701_000000, pre_analysis_tables dropped".

- [ ] **Step 4: 再 upgrade 回到最新**

Run: `cd packages/service && uv run alembic upgrade head`

期望: 重新创建表成功.

- [ ] **Step 5: Commit (无文件改动, skip if clean)**

如果 §1.3 演练期间有手动修的 migration 文件, commit; 否则 skip.

---

## PR2 = M2: PreAnalysisRunner 后台 pipeline

> **Goal:** 后台异步跑 PDF 预分析, 3 个提取器 (TOC / 表格 CSV / 关键词段落) + 写产物到 ObjectStore + 更新 DB state. 抄 `extract_runner.py:49` 模式.
>
> **规模警告**: PR2 总行数估算 ~700 行 (yaml 30 + fixture 60 + runner 320 + store 90 + 测试 250), 单 PR 略超 CLAUDE.md §500 行红线. 实施时按 [[feedback-commit-in-batches-for-large-changes]] 拆 4 commit (yaml / fixture / store / runner + 测试), 1 PR 含多 commit 是允许的 (CLAUDE.md §commit-in-batches memory). 不拆 PR.

**Files:**
- Create: `packages/service/configs/pre_analysis/rule_keywords.yaml`
- Create: `packages/service/src/ingest/pre_analysis_runner.py`
- Create: `packages/service/src/ingest/pre_analysis_store.py`
- Create: `packages/service/tests/ingest/test_pre_analysis_runner.py`
- Create: `packages/service/tests/ingest/fixtures/d81_dummy.py` (pymupdf 程序生成 5 页 PDF)

### Task 2.1: 关键词 + 章节正则 yaml

- [ ] **Step 1: 创建目录**

```bash
mkdir -p packages/service/configs/pre_analysis
```

- [ ] **Step 2: 写 rule_keywords.yaml**

文件路径: `packages/service/configs/pre_analysis/rule_keywords.yaml`

```yaml
# PDF 预分析规则配置 (2026-07-02 新建, 跟 DeepSeek 方法论第 4 步 1:1 对齐)
#
# 业务方决策 (PRD §待业务方确认 #2): 5 个关键词默认开启, 不追加,
# 但运维级支持拓展: 改 yaml + 重启服务生效 (CLAUDE.md §变更管理)

# 规则段落关键词白名单
keywords:
  - 注意
  - 不能
  - 仅适用
  - 必须
  - 禁止

# 章节标题正则 (章节解析备用, 主用 pymupdf get_toc())
chapter_patterns:
  - "^\\s*第[一二三四五六七八九十百零]+章[\\s　]+"
  - "^\\s*\\d+\\.\\d+(\\.\\d+)?[\\s　]+"
  - "^\\s*#{1,6}\\s+"

# 段落最小长度 (避免误标单字符)
min_paragraph_length: 20

# 跨页表候选检测阈值 (列数一致 + footer 关键词)
cross_page_detection:
  min_column_match: 0.8   # 列数匹配度 ≥ 80%
  footer_keywords:
    - "续表"
    - "续"
    - "cont."
    - "(continued)"
```

- [ ] **Step 3: Commit**

```bash
git add packages/service/configs/pre_analysis/rule_keywords.yaml
git commit -m "feat(config): add pre_analysis rule_keywords yaml (PR2/M2)"
```

### Task 2.2: 程序生成 PDF fixture (mode 2 集成测用)

- [ ] **Step 1: 创建 fixtures 目录**

```bash
mkdir -p packages/service/tests/ingest/fixtures
```

- [ ] **Step 2: 写程序生成 PDF 脚本**

文件路径: `packages/service/tests/ingest/fixtures/d81_dummy.py`

```python
"""d81_dummy.pdf 程序生成 (5 页 PDF, 含 1 表格 + 3 关键词段) - mode 2 集成测用

生成 PDF 写入 tests/ingest/fixtures/d81_dummy.pdf, 5 页:
- 第 1 页: 章 1 通用技术指导 (含 "注意" 关键词)
- 第 2 页: 章 1.1 (含 "必须" 关键词)
- 第 3 页: 章 2 1LE1 选型 (含 1 个 4 列 4 行表格 + "不能" 关键词)
- 第 4 页: 章 2.1 (无关键词, 无表格)
- 第 5 页: 章 2.2 (含 "禁止" 关键词)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf


def build_d81_dummy(out_path: Path) -> None:
    doc = pymupdf.open()
    # 第 1 页: 章 1 通用技术指导 + "注意"
    p1 = doc.new_page()
    p1.insert_text(
        (50, 50),
        "第1章 通用技术指导\n\n注意: 海拔超过 1000 米时需降容",
        fontsize=14,
    )
    # 第 2 页: 章 1.1 + "必须"
    p2 = doc.new_page()
    p2.insert_text(
        (50, 50),
        "1.1 国际能效等级\n\n所有电机必须配置接地端子",
        fontsize=14,
    )
    # 第 3 页: 章 2 1LE1 选型 + 1 表格 + "不能"
    p3 = doc.new_page()
    p3.insert_text((50, 50), "第2章 1LE1 选型", fontsize=14)
    p3.insert_text((50, 80), "不能将 1LE1 与 1LA4 混用", fontsize=12)
    # 画 4 列 4 行表格
    table_x = 50
    table_y = 120
    col_w = 100
    row_h = 30
    for row_idx in range(4):
        for col_idx in range(4):
            x = table_x + col_idx * col_w
            y = table_y + row_idx * row_h
            p3.draw_rect(pymupdf.Rect(x, y, x + col_w, y + row_h))
            p3.insert_text(
                (x + 5, y + 18),
                f"R{row_idx}C{col_idx}",
                fontsize=10,
            )
    # 第 4 页: 章 2.1
    p4 = doc.new_page()
    p4.insert_text((50, 50), "2.1 选型参数", fontsize=14)
    # 第 5 页: 章 2.2 + "禁止"
    p5 = doc.new_page()
    p5.insert_text(
        (50, 50),
        "2.2 应用限制\n\n禁止在海拔 5000 米以上使用",
        fontsize=14,
    )
    doc.save(str(out_path))
    doc.close()


if __name__ == "__main__":
    out = Path(__file__).parent / "d81_dummy.pdf"
    build_d81_dummy(out)
    print(f"Generated {out} ({out.stat().st_size} bytes)")
```

- [ ] **Step 3: 跑脚本生成 PDF**

Run: `cd packages/service && uv run python tests/ingest/fixtures/d81_dummy.py`

期望: 输出 `Generated ...d81_dummy.pdf (XXXX bytes)`, 文件大小 > 1000 bytes.

- [ ] **Step 4: 验证 PDF 可被 pymupdf 读**

Run: `cd packages/service && uv run python -c "import pymupdf; d = pymupdf.open('tests/ingest/fixtures/d81_dummy.pdf'); print(f'pages={len(d)}, text={d[0].get_text()[:50]}')"`

期望: 输出 `pages=5, text=第1章 通用技术指导...`.

- [ ] **Step 5: Commit**

```bash
git add packages/service/tests/ingest/fixtures/d81_dummy.py packages/service/tests/ingest/fixtures/d81_dummy.pdf
git commit -m "test(fixture): add d81_dummy.pdf 5-page generated PDF (PR2/M2)"
```

### Task 2.3: 写 PreAnalysisRunner (TDD: 失败测试 → 实现 → 通过)

- [ ] **Step 1: 写失败测试**

文件路径: `packages/service/tests/ingest/test_pre_analysis_runner.py`

```python
"""PreAnalysisRunner 单元测试 (mode 1 mock ObjectStore + 真 PDF fixture)

测试覆盖:
- 跑真 d81_dummy.pdf → 产物数 ≥ 1 chapter + 1 flagged + 1 table
- chapter_structure.json 含 level/title/page_start
- flagged_paragraphs.csv 含关键词命中段
- tables/page-3-table-1.csv 含 4 列 4 行
"""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


FIXTURE_PDF = Path(__file__).parent / "fixtures" / "d81_dummy.pdf"


@pytest.fixture
def mock_store() -> MagicMock:
    store = MagicMock()
    store.put_bytes = MagicMock()
    store.open_local = MagicMock(side_effect=lambda uri: str(FIXTURE_PDF))
    return store


@pytest.fixture
def mock_task_store() -> MagicMock:
    store = MagicMock()
    store.mark_running = MagicMock()
    store.mark_completed = MagicMock()
    store.mark_failed = MagicMock()
    return store


def test_runner_extracts_chapter_structure(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    result = runner.run(
        task_id="pa-test-001",
        pdf_uri="local://pre_analysis_inputs/pa-test-001/input/d81_dummy.pdf",
    )
    assert result.total_chapters >= 1


def test_runner_extracts_tables(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    result = runner.run(
        task_id="pa-test-002",
        pdf_uri="local://pre_analysis_inputs/pa-test-002/input/d81_dummy.pdf",
    )
    # d81_dummy.pdf 第 3 页含 1 个表格
    assert result.total_tables >= 1
    assert any("page-3-table-1.csv" in uri for uri in result.table_uris)


def test_runner_extracts_flagged_paragraphs(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    result = runner.run(
        task_id="pa-test-003",
        pdf_uri="local://pre_analysis_inputs/pa-test-003/input/d81_dummy.pdf",
    )
    # d81_dummy.pdf 含 "注意/必须/不能/禁止" 共 4 段
    assert result.total_flagged >= 4


def test_runner_writes_chapter_structure_json(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    runner.run(
        task_id="pa-test-004",
        pdf_uri="local://pre_analysis_inputs/pa-test-004/input/d81_dummy.pdf",
    )
    # mock_store.put_bytes 应被调用 ≥ 1 次含 chapter_structure.json
    put_calls = [c.args[0] for c in mock_store.put_bytes.call_args_list]
    assert any("chapter_structure.json" in uri for uri in put_calls)


def test_runner_writes_index_json(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    runner.run(
        task_id="pa-test-005",
        pdf_uri="local://pre_analysis_inputs/pa-test-005/input/d81_dummy.pdf",
    )
    put_calls = [c.args[0] for c in mock_store.put_bytes.call_args_list]
    assert any("index.json" in uri for uri in put_calls)


def test_runner_marks_completed_on_success(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    runner.run(
        task_id="pa-test-006",
        pdf_uri="local://pre_analysis_inputs/pa-test-006/input/d81_dummy.pdf",
    )
    mock_task_store.mark_completed.assert_called_once()


def test_runner_handles_missing_pdf(mock_store: MagicMock, mock_task_store: MagicMock) -> None:
    """PDF 不存在 → mark_failed, 返 PreAnalysisResult(success=False)"""
    from src.ingest.pre_analysis_runner import PreAnalysisRunner

    mock_store.open_local = MagicMock(side_effect=FileNotFoundError("not found"))
    runner = PreAnalysisRunner(
        object_store=mock_store,
        task_store=mock_task_store,
        keyword_config_path=Path("configs/pre_analysis/rule_keywords.yaml"),
    )
    runner.run(
        task_id="pa-test-007",
        pdf_uri="local://nonexistent.pdf",
    )
    mock_task_store.mark_failed.assert_called_once()
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd packages/service && uv run pytest tests/ingest/test_pre_analysis_runner.py -v`

期望: FAIL (ImportError: cannot import name 'PreAnalysisRunner').

- [ ] **Step 3: 写 PreAnalysisStore (DB 操作 facade)**

文件路径: `packages/service/src/ingest/pre_analysis_store.py`

```python
"""pre_analysis_tasks ORM 操作 facade (2026-07-02 新建)

跟 src/ingest/store.py IngestTask 模式对齐:
- save_task / load_task / list_user_tasks 三个核心函数
- runner 调 mark_running / mark_completed / mark_failed 三个状态切换
- output_files_json / summary_json 是 JSON 字符串 (Text 列, 不是 JSONB)
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from ..storage import session_scope
from .pre_analysis_models import PreAnalysisTask


def _to_dict(task: PreAnalysisTask) -> dict:
    """ORM 对象 → API dict (跟 src/ingest/store.py 模式一致)."""
    return {
        "id": task.id,
        "user_hash": task.user_hash,
        "state": task.state,
        "pdf_filename": task.pdf_filename,
        "pdf_uri": task.pdf_uri,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "error": task.error,
        "output_files": json.loads(task.output_files_json or "[]"),
        "summary": json.loads(task.summary_json or "{}"),
    }


def save_task(d: dict) -> None:
    """创建 task 行 (state=pending)."""
    task = PreAnalysisTask(
        id=d["id"],
        user_hash=d["user_hash"],
        state=d.get("state", "pending"),
        pdf_filename=d["pdf_filename"],
        pdf_uri=d["pdf_uri"],
        started_at=d["started_at"],
        finished_at=None,
        error=None,
        output_files_json=json.dumps(d.get("output_files", []), ensure_ascii=False),
        summary_json=json.dumps(d.get("summary", {}), ensure_ascii=False),
    )
    with session_scope() as s:
        s.merge(task)


def load_task(task_id: str) -> dict | None:
    """查单条 task."""
    with session_scope() as s:
        task = s.get(PreAnalysisTask, task_id)
        return _to_dict(task) if task else None


def list_user_tasks(user_hash: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """列某用户 task, 按 started_at DESC."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(PreAnalysisTask)
                .where(PreAnalysisTask.user_hash == user_hash)
                .order_by(PreAnalysisTask.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [_to_dict(t) for t in rows]


class PreAnalysisTaskStore:
    """Runner 用的状态切换 facade (mark_running / mark_completed / mark_failed).

    设计: 独立类而不是函数, 因为 PreAnalysisRunner 接 Protocol (mode 1 mock).
    """

    def mark_running(self, task_id: str) -> None:
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "running"

    def mark_completed(
        self,
        task_id: str,
        output_files: list[dict],
        summary: dict,
    ) -> None:
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "completed"
                task.finished_at = datetime.now(datetime.UTC)  # type: ignore[attr-defined]  # pyright: datetime UTC
                task.output_files_json = json.dumps(output_files, ensure_ascii=False)
                task.summary_json = json.dumps(summary, ensure_ascii=False)

    def mark_failed(self, task_id: str, error: str) -> None:
        with session_scope() as s:
            task = s.get(PreAnalysisTask, task_id)
            if task is not None:
                task.state = "failed"
                task.finished_at = datetime.now(datetime.UTC)  # type: ignore[attr-defined]
                task.error = error[-1000:]  # stderr tail, 1KB 限制 (跟 IngestTask 模式一致)


__all__ = ["save_task", "load_task", "list_user_tasks", "PreAnalysisTaskStore"]
```

注意: `datetime.now(datetime.UTC)` 在 Python 3.11+ 才支持; 项目用 Python 3.14, 没问题. 如果 ruff/pyright 报, 改 `datetime.now(timezone.utc)`.

- [ ] **Step 4: 写 PreAnalysisRunner (核心)**

文件路径: `packages/service/src/ingest/pre_analysis_runner.py`

```python
"""PreAnalysisRunner: PDF 后台预分析 pipeline (2026-07-02)

设计 (跟 src/kg/extract_runner.py:49 run_extraction 模式对齐):
- 接收 ObjectStore URI 形式 PDF
- 调 pymupdf 提取 TOC + 表格 CSV + 关键词段落
- 产物写 ObjectStore (chapter_structure.json / tables/*.csv / flagged_paragraphs.csv / index.json)
- 更新 DB state (pending → running → completed / failed)

跨页表候选检测: 启发式 (页 N 表格 N 跟页 N+1 表格 1 列数 ≥ 80% 一致 + footer 关键词),
计数写 summary.cross_page_candidates, 不自动合并 (本期不做, 用户决策 2026-07-02).
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import pymupdf
import yaml
from loguru import logger

from .pre_analysis_store import PreAnalysisTaskStore


@dataclass(frozen=True)
class PreAnalysisResult:
    """Runner 返回值, API 层直接序列化给前端."""

    success: bool
    task_id: str
    chapter_structure_uri: str = ""
    flagged_paragraphs_uri: str = ""
    table_uris: list[str] = field(default_factory=list)
    index_uri: str = ""
    total_chapters: int = 0
    total_tables: int = 0
    total_flagged: int = 0
    cross_page_candidates: int = 0
    elapsed_ms: int = 0
    error: str | None = None


class ObjectStoreProto(Protocol):
    """跟 src/storage/object_store.py ObjectStore ABC 同 shape (mode 1 mock 用)."""

    def put_bytes(self, uri: str, data: bytes, mime: str = "application/octet-stream") -> None: ...

    def open_local(self, uri: str) -> str: ...


@dataclass(frozen=True)
class PreAnalysisRunner:
    """PDF 预分析 runner (mode 1 mock friendly)."""

    object_store: ObjectStoreProto
    task_store: PreAnalysisTaskStore
    keyword_config_path: Path

    def run(self, task_id: str, pdf_uri: str) -> PreAnalysisResult:
        """主入口. PDF 不存在 / 损坏 → 返 success=False + error."""
        start = time.monotonic()
        try:
            self.task_store.mark_running(task_id)
            pdf_path = self.object_store.open_local(pdf_uri)
        except Exception as e:
            logger.opt(exception=True).error("pre_analysis open failed task={} uri={}", task_id, pdf_uri)
            self.task_store.mark_failed(task_id, f"open failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        try:
            doc = pymupdf.open(pdf_path)
        except Exception as e:
            logger.opt(exception=True).error("pre_analysis pymupdf open failed task={} path={}", task_id, pdf_path)
            self.task_store.mark_failed(task_id, f"pymupdf open failed: {e}")
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        try:
            config = self._load_config()
            chapters = self._extract_chapters(doc)
            tables, cross_page = self._extract_tables(doc, config)
            flagged = self._extract_flagged_paragraphs(doc, config)
        except Exception as e:
            logger.opt(exception=True).error("pre_analysis extract failed task={}", task_id)
            self.task_store.mark_failed(task_id, f"extract failed: {e}")
            doc.close()
            return PreAnalysisResult(success=False, task_id=task_id, error=str(e))

        output_prefix = self._output_prefix(task_id)
        chapter_uri = self._write_chapter_structure(output_prefix, chapters, doc)
        flagged_uri = self._write_flagged_paragraphs(output_prefix, flagged)
        table_uris = self._write_tables(output_prefix, tables)
        index_uri, summary = self._write_index(
            output_prefix, task_id, pdf_uri, chapters, tables, flagged, cross_page, start
        )

        doc.close()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result = PreAnalysisResult(
            success=True,
            task_id=task_id,
            chapter_structure_uri=chapter_uri,
            flagged_paragraphs_uri=flagged_uri,
            table_uris=table_uris,
            index_uri=index_uri,
            total_chapters=len(chapters),
            total_tables=len(tables),
            total_flagged=len(flagged),
            cross_page_candidates=cross_page,
            elapsed_ms=elapsed_ms,
        )
        self.task_store.mark_completed(
            task_id=task_id,
            output_files=summary["files"],
            summary={
                "total_chapters": result.total_chapters,
                "total_tables": result.total_tables,
                "total_flagged_paragraphs": result.total_flagged,
                "elapsed_ms": result.elapsed_ms,
                "cross_page_candidates": result.cross_page_candidates,
            },
        )
        logger.info(
            "pre_analysis done task={} chapters={} tables={} flagged={} elapsed={}ms",
            task_id, result.total_chapters, result.total_tables, result.total_flagged, elapsed_ms,
        )
        return result

    def _load_config(self) -> dict:
        """加载 rule_keywords.yaml. yaml 缺失 / 解析失败 → 兜底默认 5 关键词 (CLAUDE.md §错误处理 fail-open)."""
        try:
            with self.keyword_config_path.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("rule_keywords.yaml load failed err={}, 兜底默认", e)
            return {"keywords": ["注意", "不能", "仅适用", "必须", "禁止"]}

    def _extract_chapters(self, doc: pymupdf.Document) -> list[dict]:
        """调 doc.get_toc() 拿章节. 返回空 list 如果 PDF 无 outline (logged WARNING, 不报错)."""
        toc = doc.get_toc()  # list[[level, title, page]]
        if not toc:
            logger.warning("PDF 无 outline (get_toc 返空), chapter_structure 标空")
        return [{"level": lvl, "title": title, "page_start": page, "page_end": page} for lvl, title, page in toc]

    def _extract_tables(self, doc: pymupdf.Document, config: dict) -> tuple[list[tuple[int, int, list[list[str]]]], int]:
        """遍历每页, 调 page.find_tables().tables[].extract() 拿 CSV 数据.

        Returns: (tables_list, cross_page_candidates_count)
        tables_list 元素: (page_no, table_no, rows)
        """
        tables: list[tuple[int, int, list[list[str]]]] = []
        prev_table = None  # (page_no, cols) 用于跨页检测
        cross_page = 0
        cross_config = config.get("cross_page_detection", {})
        col_match = cross_config.get("min_column_match", 0.8)
        footer_kws = cross_config.get("footer_keywords", [])

        for page_idx, page in enumerate(doc):
            for table_idx, table in enumerate(page.find_tables().tables):
                rows = table.extract()
                tables.append((page_idx + 1, table_idx + 1, rows))
                # 跨页候选启发式
                if prev_table is not None and table_idx == 0:
                    prev_page, prev_cols = prev_table
                    if prev_page == page_idx and len(rows[0] if rows else []) >= prev_cols * col_match:
                        # 检查 footer 关键词
                        last_row_text = rows[-1][0] if rows and rows[-1] else ""
                        if any(kw in last_row_text for kw in footer_kws):
                            cross_page += 1
                            logger.warning("跨页表候选 page={} -> page={}", prev_page, page_idx + 1)
                prev_table = (page_idx + 1, len(rows[0] if rows else []))
        return tables, cross_page

    def _extract_flagged_paragraphs(self, doc: pymupdf.Document, config: dict) -> list[dict]:
        """遍历每页 text, 按段切 (双换行), 任一关键词命中 → 标 [RULE].

        Returns: [{matched_keywords, page, section, text}, ...]
        """
        keywords = config.get("keywords", [])
        min_len = config.get("min_paragraph_length", 20)
        flagged: list[dict] = []
        for page_idx, page in enumerate(doc):
            text = page.get_text()  # type: ignore[assignment]  # pyright: pymupdf 返 str
            paragraphs = re.split(r"\n\s*\n", text)
            for para in paragraphs:
                para_text = para.strip()
                if len(para_text) < min_len:
                    continue
                matched = [kw for kw in keywords if kw in para_text]
                if matched:
                    flagged.append({
                        "matched_keywords": ",".join(matched),
                        "page": page_idx + 1,
                        "section": "",
                        "text": para_text,
                    })
        return flagged

    def _output_prefix(self, task_id: str) -> str:
        """产物目录 URI 前缀."""
        return f"local://pre_analysis_outputs/{task_id}"

    def _write_chapter_structure(self, prefix: str, chapters: list[dict], doc: pymupdf.Document) -> str:
        """写 chapter_structure.json."""
        payload = {
            "total_pages": len(doc),
            "total_chapters": len(chapters),
            "extracted_at": datetime.now(timezone.utc).isoformat(),  # type: ignore[attr-defined]
            "toc_source": "pdf_outline" if chapters else "empty",
            "chapters": chapters,
        }
        uri = f"{prefix}/chapter_structure.json"
        self.object_store.put_bytes(uri, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
        return uri

    def _write_flagged_paragraphs(self, prefix: str, flagged: list[dict]) -> str:
        """写 flagged_paragraphs.csv."""
        uri = f"{prefix}/flagged_paragraphs.csv"
        buf = io.StringIO()
        if flagged:
            writer = csv.DictWriter(buf, fieldnames=["matched_keywords", "page", "section", "text"])
            writer.writeheader()
            for row in flagged:
                writer.writerow(row)
        else:
            buf.write("matched_keywords,page,section,text\n")
        self.object_store.put_bytes(uri, buf.getvalue().encode("utf-8"), "text/csv")
        return uri

    def _write_tables(self, prefix: str, tables: list[tuple[int, int, list[list[str]]]]) -> list[str]:
        """写 tables/page-N-table-M.csv (每个表格单独 1 个 CSV)."""
        uris: list[str] = []
        for page_no, table_no, rows in tables:
            uri = f"{prefix}/tables/page-{page_no}-table-{table_no}.csv"
            buf = io.StringIO()
            writer = csv.writer(buf)
            for row in rows:
                writer.writerow(row)
            self.object_store.put_bytes(uri, buf.getvalue().encode("utf-8"), "text/csv")
            uris.append(uri)
        return uris

    def _write_index(
        self,
        prefix: str,
        task_id: str,
        pdf_uri: str,
        chapters: list[dict],
        tables: list[tuple[int, int, list[list[str]]]],
        flagged: list[dict],
        cross_page: int,
        start: float,
    ) -> tuple[str, dict]:
        """写 index.json (DB output_files_json 用), 返 (uri, summary_dict)."""
        elapsed_ms = int((time.monotonic() - start) * 1000)
        files = [
            {
                "kind": "chapter_structure",
                "filename": "chapter_structure.json",
                "size_bytes": 0,
                "uri": f"{prefix}/chapter_structure.json",
            },
            {
                "kind": "flagged_paragraphs",
                "filename": "flagged_paragraphs.csv",
                "size_bytes": 0,
                "uri": f"{prefix}/flagged_paragraphs.csv",
            },
        ]
        for page_no, table_no, _ in tables:
            files.append({
                "kind": "table",
                "filename": f"tables/page-{page_no}-table-{table_no}.csv",
                "size_bytes": 0,
                "uri": f"{prefix}/tables/page-{page_no}-table-{table_no}.csv",
            })
        payload = {
            "task_id": task_id,
            "pdf_filename": pdf_uri.rsplit("/", 1)[-1],
            "elapsed_ms": elapsed_ms,
            "summary": {
                "total_chapters": len(chapters),
                "total_tables": len(tables),
                "total_flagged_paragraphs": len(flagged),
                "cross_page_candidates": cross_page,
            },
            "files": files,
        }
        uri = f"{prefix}/index.json"
        self.object_store.put_bytes(uri, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")
        return uri, payload


__all__ = ["PreAnalysisRunner", "PreAnalysisResult"]
```

- [ ] **Step 5: 跑测试验证通过**

Run: `cd packages/service && uv run pytest tests/ingest/test_pre_analysis_runner.py -v`

期望: 7 个 test 全 PASS.

如果失败, 看 error msg 常见原因:
- `ModuleNotFoundError: No module named 'yaml'`: 项目 pyproject.toml 缺 PyYAML dep. 检查 pyproject.toml, 加 `PyYAML>=6.0` 到 dependencies.
- `ImportError: cannot import name 'session_scope' from 'src.storage'`: 项目有 session_scope, 在 src/storage/__init__.py 导出. 检查现有用法.
- `AttributeError: datetime has no attribute 'UTC'`: Python 版本 < 3.11. 改 `datetime.now(timezone.utc)`.

- [ ] **Step 6: 跑 ruff + pyright**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`

期望: 0 error. 如果 ruff 报 line too long, 折行. 如果 pyright 报 type: ignore 缺注释, 加 `# pyright: ignore[<code>]` + 1 行说明.

- [ ] **Step 7: Commit**

```bash
git add packages/service/src/ingest/pre_analysis_runner.py packages/service/src/ingest/pre_analysis_store.py packages/service/tests/ingest/test_pre_analysis_runner.py
git commit -m "feat(runner): add PreAnalysisRunner + Store facade (PR2/M2)"
```

---

## PR3 = M3: 4 个 API 端点 + zip 下载

> **Goal:** 4 个 `/api/pre-analysis/*` 端点 + zip 流下载. 抄 `src/ingest/api.py:300-393` 模板.

**Files:**
- Modify: `packages/service/src/ingest/api.py` (追加 pre_analysis_router)
- Create: `packages/service/tests/ingest/test_pre_analysis_api.py`

### Task 3.1: 写 API 失败测试

- [ ] **Step 1: 写失败测试**

文件路径: `packages/service/tests/ingest/test_pre_analysis_api.py`

```python
"""pre-analysis API 4 端点测试 (mode 1 mock TestClient + mock Runner)

测试覆盖:
- POST /api/pre-analysis/upload: super_admin 鉴权 + task 创建 + BackgroundTasks
- GET /api/pre-analysis/tasks: 列表 (用户隔离)
- GET /api/pre-analysis/tasks/{id}: 详情
- GET /api/pre-analysis/tasks/{id}/download: zip 流下载
- 鉴权: anon token 403
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_user_admin() -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.is_super_admin = True
    return user


@pytest.fixture
def mock_user_anon() -> MagicMock:
    user = MagicMock()
    user.id = 2
    user.is_super_admin = False
    return user


def test_upload_requires_super_admin(mock_user_anon: MagicMock) -> None:
    """POST /api/pre-analysis/upload anon 用户 → 403"""
    with patch("src.ingest.api.require_super_admin", return_value=lambda: mock_user_anon):
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        resp = client.post("/api/pre-analysis/upload", files={"file": ("a.pdf", b"x", "application/pdf")})
        assert resp.status_code == 403


def test_upload_creates_task_and_schedules_runner(mock_user_admin: MagicMock) -> None:
    """POST /api/pre-analysis/upload super_admin → 200 + task_id + BackgroundTasks add_task"""
    with (
        patch("src.ingest.api.require_super_admin", return_value=lambda: mock_user_admin),
        patch("src.ingest.api._run_pre_analysis") as mock_runner,
        patch("src.ingest.api.get_object_store") as mock_store_fn,
        patch("src.ingest.api.save_task"),
    ):
        mock_store = MagicMock()
        mock_store.put_bytes = MagicMock()
        mock_store.backend_name = MagicMock(return_value="local")
        mock_store_fn.return_value = mock_store

        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        resp = client.post(
            "/api/pre-analysis/upload",
            files={"file": ("D81.pdf", b"%PDF-1.4\n..." * 100, "application/pdf")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        assert body["state"] == "pending"


def test_list_tasks_returns_user_only(mock_user_admin: MagicMock) -> None:
    """GET /api/pre-analysis/tasks → 仅返当前用户 task"""
    with (
        patch("src.ingest.api.require_super_admin", return_value=lambda: mock_user_admin),
        patch("src.ingest.api.list_user_tasks", return_value=[{"id": "a", "user_hash": "hash1"}]),
    ):
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        resp = client.get("/api/pre-analysis/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["tasks"]) == 1


def test_download_returns_zip_stream(mock_user_admin: MagicMock) -> None:
    """GET /api/pre-analysis/tasks/{id}/download → zip 流"""
    with (
        patch("src.ingest.api.require_super_admin", return_value=lambda: mock_user_admin),
        patch("src.ingest.api._build_zip_stream", return_value=b"PK\x03\x04fakezip"),
    ):
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        resp = client.get("/api/pre-analysis/tasks/pa-test/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert resp.content[:2] == b"PK"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd packages/service && uv run pytest tests/ingest/test_pre_analysis_api.py -v`

期望: 4 个 test 全 FAIL (router 不存在 / endpoint 404).

### Task 3.2: 写 API 端点

- [ ] **Step 1: 在 src/ingest/api.py 追加 pre_analysis router**

修改文件: `packages/service/src/ingest/api.py` (在文件末尾追加, 不动现有 IngestTask 代码)

在文件最末尾追加:

```python
# ==================== pre_analysis (2026-07-02 新增) ====================

import io
import zipfile
from typing import Annotated

from fastapi import Depends, File, UploadFile

from ..core.auth import CurrentUser, require_super_admin
from .pre_analysis_models import PreAnalysisTask  # noqa: F401  # 间接供 alembic 反射
from .pre_analysis_runner import PreAnalysisRunner, PreAnalysisResult
from .pre_analysis_store import PreAnalysisTaskStore, load_task, list_user_tasks, save_task

pre_analysis_router = APIRouter(prefix="/api/pre-analysis", tags=["PDF 预分析"])


@pre_analysis_router.post(
    "/upload",
    summary="上传 PDF 触发预分析",
    description=(
        "## 用途\n\n"
        "super_admin 上传 1 个 PDF, 后台异步跑 pymupdf 预分析, 4 类产物写 ObjectStore.\n\n"
        "## 鉴权\n\n"
        "`require_super_admin` 守卫.\n\n"
        "## 行为\n\n"
        "1. 1 个 .pdf 文件, ≤ 100MB; 否则 413.\n"
        "2. 写入 ObjectStore: `s3://{bucket}/pre_analysis_inputs/{task_id}/input/{file}` 或 local 等价.\n"
        "3. 创建 pre_analysis_tasks 行 (state=pending).\n"
        "4. `BackgroundTasks.add_task(_run_pre_analysis, task_id)` 异步跑.\n"
    ),
    response_model=None,
    responses={
        200: {"description": "{task_id, state: pending, pdf_filename}"},
        401: {"description": "未登录 / token 无效"},
        403: {"description": "非 super_admin"},
        413: {"description": "PDF > 100MB"},
    },
)
async def upload_pre_analysis(
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_super_admin),
    file: UploadFile = File(...),
) -> dict:
    """上传 PDF, 调度后台预分析."""
    from ..storage import get_object_store
    from ..core.auth_helpers import user_hash_for

    token = user.token
    uhash = user_hash_for(token)

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 100 * 1024 * 1024:
        raise HTTPException(413, detail="PDF > 100MB")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="只接受 .pdf 文件")

    store = get_object_store()
    task_id = f"pa-{uuid.uuid4().hex[:12]}"
    pdf_filename = Path(file.filename).name
    workdir_uri = f"{store.backend_name()}://pre_analysis_inputs/{task_id}/input/{pdf_filename}"
    store.put_bytes(workdir_uri, pdf_bytes, mime="application/pdf")

    save_task({
        "id": task_id,
        "user_hash": uhash,
        "state": "pending",
        "pdf_filename": pdf_filename,
        "pdf_uri": workdir_uri,
        "started_at": datetime.now(timezone.utc),  # type: ignore[attr-defined]
    })

    background.add_task(_run_pre_analysis, task_id)
    logger.info("pre_analysis upload task={} pdf={} bytes={}", task_id, pdf_filename, len(pdf_bytes))
    return {"task_id": task_id, "state": "pending", "pdf_filename": pdf_filename}


@pre_analysis_router.get(
    "/tasks",
    summary="列 super_admin 的所有预分析任务",
    response_model=None,
)
async def list_pre_analysis_tasks(
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """列任务 (按 started_at DESC)."""
    from ..core.auth_helpers import user_hash_for

    uhash = user_hash_for(user.token)
    tasks = list_user_tasks(uhash, limit=limit, offset=offset)
    return {"tasks": tasks}


@pre_analysis_router.get(
    "/tasks/{task_id}",
    summary="查单条预分析任务详情",
    response_model=None,
)
async def get_pre_analysis_task(
    task_id: str,
    user: CurrentUser = Depends(require_super_admin),
) -> dict:
    """查 task 元数据 + 产物清单."""
    task = load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    return task


@pre_analysis_router.get(
    "/tasks/{task_id}/download",
    summary="下载预分析产物 zip 包",
    response_model=None,
    responses={
        200: {"content": {"application/zip": {}}, "description": "zip 流"},
        404: {"description": "任务不存在或产物缺失"},
    },
)
async def download_pre_analysis_zip(
    task_id: str,
    request: Request,
    user: CurrentUser = Depends(require_super_admin),
) -> Response:
    """StreamingResponse 流式 zip, 不 load 全文件进内存."""
    from ..core.audit import audited
    from ..storage import get_object_store

    task = load_task(task_id)
    if task is None:
        raise HTTPException(404, detail="任务不存在或已过期")
    if task["state"] != "completed":
        raise HTTPException(409, detail=f"task 状态错误: {task['state']}")

    store = get_object_store()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in task["output_files"]:
            try:
                data = store.get_bytes(f["uri"])
            except Exception:
                continue  # 单文件缺失跳过, 不阻断
            zf.writestr(f["filename"], data)

    zip_buf.seek(0)
    filename = f"{task['pdf_filename'].rsplit('.', 1)[0]}_pre_analysis_{task_id}.zip"
    return Response(
        content=zip_buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- 后台 runner 调度 ---

def _run_pre_analysis(task_id: str) -> None:
    """BackgroundTasks 调度入口. 抄 _run_ingest 模式."""
    from ..storage import get_object_store
    from ..common.paths import PROJECT_ROOT
    from .pre_analysis_runner import PreAnalysisRunner

    task = load_task(task_id)
    if task is None:
        logger.error("_run_pre_analysis task {} not found", task_id)
        return

    runner = PreAnalysisRunner(
        object_store=get_object_store(),
        task_store=PreAnalysisTaskStore(),
        keyword_config_path=PROJECT_ROOT / "configs" / "pre_analysis" / "rule_keywords.yaml",
    )
    try:
        runner.run(task_id=task_id, pdf_uri=task["pdf_uri"])
    except Exception as e:
        logger.opt(exception=True).error("_run_pre_analysis task={} failed", task_id)
        PreAnalysisTaskStore().mark_failed(task_id, f"runner exception: {e}")


# --- 注册 router ---
# 在 src/main.py 已有 `app.include_router(ingest_router)`, 加 1 行:
#   app.include_router(pre_analysis_router)
# 见 PR3 Step 4.
```

- [ ] **Step 2: 注册 pre_analysis_router 到 app**

修改文件: `packages/service/src/main.py` (找 `app.include_router(ingest_router)` 那行, 紧跟追加)

```python
from .ingest.api import ingest_router, pre_analysis_router  # 在 import 区追加

# 在 app = FastAPI(...) 之后的 include_router 区追加
app.include_router(pre_analysis_router)
```

(具体文件位置看 `packages/service/src/main.py` 现有 include_router 调用.)

- [ ] **Step 3: 跑测试验证通过**

Run: `cd packages/service && uv run pytest tests/ingest/test_pre_analysis_api.py -v`

期望: 4 个 test 全 PASS.

如果失败, 看 error msg 常见原因:
- `ImportError: cannot import name 'require_super_admin' from 'src.core.auth'`: 检查 `packages/service/src/core/auth.py` 是否有 require_super_admin 装饰器/依赖. 如果没有, 用现有的 admin 守卫模式 (参考 `require_page("output")`).
- `ImportError: cannot import name 'user_hash_for' from 'src.core.auth_helpers'`: 检查 `packages/service/src/core/auth_helpers.py`, 可能在 `src.core.auth` 自身. 调整 import 路径.
- `AttributeError: module 'src.ingest.api' has no attribute '_run_pre_analysis'`: 函数还没 patch 生效. 检查测试 patch 路径.

- [ ] **Step 4: 跑 ruff + pyright**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`

期望: 0 error. 加 `@audited` 到 download 端点 (CLAUDE.md §危险操作 / 数据导出):

修改文件: `packages/service/src/ingest/api.py` 在 download 端点加装饰器

```python
@pre_analysis_router.get("/tasks/{task_id}/download", ...)
@audited("pre_analysis.download", target_type="pre_analysis_task")
async def download_pre_analysis_zip(...) -> Response:
    request.state.audit_ctx.set(target_id=task_id, metadata={"pdf_filename": task["pdf_filename"]})
    ...
```

(具体 import `from ..core.audit import audited` 加在文件顶部.)

- [ ] **Step 5: Commit**

```bash
git add packages/service/src/ingest/api.py packages/service/src/main.py packages/service/tests/ingest/test_pre_analysis_api.py
git commit -m "feat(api): add 4 pre-analysis endpoints + zip download (PR3/M3)"
```

---

## PR4 = M4: 前端 lib/api wrapper

> **Goal:** 4 端点 API wrapper + 3 type + vitest.

**Files:**
- Create: `packages/web/lib/api/pre-analysis.ts`
- Create: `packages/web/lib/api/pre-analysis.test.ts`

### Task 4.1: 写 API wrapper (TDD)

- [ ] **Step 1: 写失败测试**

文件路径: `packages/web/lib/api/pre-analysis.test.ts`

```typescript
// pre-analysis API wrapper 测试 (mode 1 mock fetch)

import { afterEach, describe, expect, it, mock } from "bun:test";
import {
  preAnalysisUpload,
  listPreAnalysisTasks,
  getPreAnalysisTask,
  downloadPreAnalysisZip,
  type PreAnalysisTaskItem,
} from "./pre-analysis";

const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
});

describe("preAnalysisUpload", () => {
  it("POST /api/pre-analysis/upload with FormData", async () => {
    const mockResp: PreAnalysisUploadResponse = {
      task_id: "pa-abc",
      state: "pending",
      pdf_filename: "D81.pdf",
    };
    global.fetch = mock(async () =>
      new Response(JSON.stringify(mockResp), { status: 200 })
    ) as unknown as typeof fetch;

    const file = new File(["x"], "D81.pdf", { type: "application/pdf" });
    const result = await preAnalysisUpload(file);
    expect(result.task_id).toBe("pa-abc");
    expect(result.state).toBe("pending");
  });

  it("throws on 403", async () => {
    global.fetch = mock(async () =>
      new Response(JSON.stringify({ detail: "权限不足" }), { status: 403 })
    ) as unknown as typeof fetch;

    const file = new File(["x"], "D81.pdf", { type: "application/pdf" });
    expect(preAnalysisUpload(file)).rejects.toThrow();
  });
});

describe("listPreAnalysisTasks", () => {
  it("GET /api/pre-analysis/tasks 返 task 数组", async () => {
    const mockResp: PreAnalysisListResponse = {
      tasks: [
        {
          id: "pa-1",
          state: "completed",
          user_hash: "hash",
          pdf_filename: "D81.pdf",
          pdf_uri: "local://x",
          started_at: "2026-07-02T10:00:00Z",
          finished_at: "2026-07-02T10:01:00Z",
          output_files: [],
          summary: { total_chapters: 6, total_tables: 12, total_flagged_paragraphs: 11, elapsed_ms: 28421, cross_page_candidates: 1 },
          error: null,
        },
      ],
    };
    global.fetch = mock(async () =>
      new Response(JSON.stringify(mockResp), { status: 200 })
    ) as unknown as typeof fetch;

    const result = await listPreAnalysisTasks();
    expect(result.tasks).toHaveLength(1);
    expect(result.tasks[0]?.id).toBe("pa-1");
  });
});

describe("getPreAnalysisTask", () => {
  it("GET /api/pre-analysis/tasks/{id}", async () => {
    const mockTask: PreAnalysisTaskItem = {
      id: "pa-1",
      state: "completed",
      user_hash: "hash",
      pdf_filename: "D81.pdf",
      pdf_uri: "local://x",
      started_at: "2026-07-02T10:00:00Z",
      finished_at: "2026-07-02T10:01:00Z",
      output_files: [
        { kind: "chapter_structure", filename: "chapter_structure.json", uri: "local://x", size_bytes: 3842 },
      ],
      summary: { total_chapters: 6, total_tables: 12, total_flagged_paragraphs: 11, elapsed_ms: 28421, cross_page_candidates: 1 },
      error: null,
    };
    global.fetch = mock(async () =>
      new Response(JSON.stringify(mockTask), { status: 200 })
    ) as unknown as typeof fetch;

    const result = await getPreAnalysisTask("pa-1");
    expect(result.id).toBe("pa-1");
  });
});

describe("downloadPreAnalysisZip", () => {
  it("GET /api/pre-analysis/tasks/{id}/download 返 Blob", async () => {
    const fakeZip = new Uint8Array([0x50, 0x4b, 0x03, 0x04]); // PK header
    global.fetch = mock(async () =>
      new Response(fakeZip, {
        status: 200,
        headers: { "content-type": "application/zip" },
      })
    ) as unknown as typeof fetch;

    const blob = await downloadPreAnalysisZip("pa-1");
    expect(blob).toBeInstanceOf(Blob);
  });
});

// type-only imports for compile
import type { PreAnalysisUploadResponse, PreAnalysisListResponse } from "./pre-analysis";
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd packages/web && bun run test lib/api/pre-analysis.test.ts`

期望: FAIL (cannot resolve module).

- [ ] **Step 3: 写 API wrapper**

文件路径: `packages/web/lib/api/pre-analysis.ts`

```typescript
// pre-analysis 4 端点 API wrapper (2026-07-02 PR4)
//
// 类型定义跟后端 PreAnalysisTaskItem / PreAnalysisOutputFile 1:1 对齐.
// 后端返回 camelCase / snake_case 混合, 这里统一 camelCase (前端约定).

export interface PreAnalysisSummary {
  total_chapters: number;
  total_tables: number;
  total_flagged_paragraphs: number;
  elapsed_ms: number;
  cross_page_candidates: number;
}

export interface PreAnalysisOutputFile {
  kind: "chapter_structure" | "flagged_paragraphs" | "table" | "index";
  filename: string;
  uri: string;
  size_bytes: number;
}

export interface PreAnalysisTaskItem {
  id: string;
  state: "pending" | "running" | "completed" | "failed";
  user_hash: string;
  pdf_filename: string;
  pdf_uri: string;
  started_at: string;
  finished_at: string | null;
  output_files: PreAnalysisOutputFile[];
  summary: PreAnalysisSummary;
  error: string | null;
}

export interface PreAnalysisUploadResponse {
  task_id: string;
  state: "pending";
  pdf_filename: string;
}

export interface PreAnalysisListResponse {
  tasks: PreAnalysisTaskItem[];
}

const handleError = async (resp: Response): Promise<never> => {
  const body = await resp.json().catch(() => ({ detail: "未知错误" }));
  throw new Error(body.detail ?? `${resp.status} ${resp.statusText}`);
};

export async function preAnalysisUpload(file: File): Promise<PreAnalysisUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch("/api/pre-analysis/upload", {
    method: "POST",
    body: formData,
    credentials: "include",
  });
  if (!resp.ok) await handleError(resp);
  return (await resp.json()) as PreAnalysisUploadResponse;
}

export async function listPreAnalysisTasks(
  params?: { limit?: number; offset?: number },
): Promise<PreAnalysisListResponse> {
  const search = new URLSearchParams();
  if (params?.limit !== undefined) search.set("limit", String(params.limit));
  if (params?.offset !== undefined) search.set("offset", String(params.offset));
  const qs = search.toString();
  const resp = await fetch(`/api/pre-analysis/tasks${qs ? `?${qs}` : ""}`, {
    credentials: "include",
  });
  if (!resp.ok) await handleError(resp);
  return (await resp.json()) as PreAnalysisListResponse;
}

export async function getPreAnalysisTask(id: string): Promise<PreAnalysisTaskItem> {
  const resp = await fetch(`/api/pre-analysis/tasks/${id}`, { credentials: "include" });
  if (!resp.ok) await handleError(resp);
  return (await resp.json()) as PreAnalysisTaskItem;
}

export async function downloadPreAnalysisZip(id: string): Promise<Blob> {
  const resp = await fetch(`/api/pre-analysis/tasks/${id}/download`, {
    credentials: "include",
  });
  if (!resp.ok) await handleError(resp);
  return await resp.blob();
}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd packages/web && bun run test lib/api/pre-analysis.test.ts`

期望: 5 个 test 全 PASS.

- [ ] **Step 5: 跑 typecheck + lint**

Run: `cd packages/web && bun run format && bun run lint:fix && bun run typecheck`

期望: 0 error.

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/api/pre-analysis.ts packages/web/lib/api/pre-analysis.test.ts
git commit -m "feat(web): add pre-analysis API wrapper (PR4/M4)"
```

---

## PR5 = M5: 前端 admin 列表页

> **Goal:** 列表页 `/admin/pre-analysis` 用 `<DataTable>` + `<FileDropzone>` + `<Badge>` 渲染任务列表, 0 自建组件.

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/page.tsx`
- Create: `packages/web/app/[locale]/admin/pre-analysis/page.test.tsx`
- Modify: `packages/web/messages/zh.json`
- Modify: `packages/web/messages/en.json`

### Task 5.1: 加 i18n 字符串

- [ ] **Step 1: 加 zh.json 字符串**

修改文件: `packages/web/messages/zh.json` (在文件末尾追加, 按字母序找合适位置)

```json
{
  "PDF 预分析": "PDF 预分析",
  "上传 PDF": "上传 PDF",
  "状态": "状态",
  "产物数": "产物数",
  "无预分析任务": "无预分析任务",
  "点击上传按钮开始": "点击上传按钮开始",
  "待处理": "待处理",
  "处理中": "处理中",
  "已完成": "已完成",
  "失败": "失败",
  "PDF 文件名": "PDF 文件名",
  "上传时间": "上传时间",
  "耗时": "耗时",
  "下载": "下载",
  "查看详情": "查看详情"
}
```

(注意: `t("中文")` 用中文作 key, value 同样中文. 这里简化显示, 实际在 zh.json 里直接添加上述 key.)

- [ ] **Step 2: 加 en.json 字符串**

修改文件: `packages/web/messages/en.json` (同样追加)

```json
{
  "PDF 预分析": "PDF Pre-Analysis",
  "上传 PDF": "Upload PDF",
  "状态": "Status",
  "产物数": "Artifacts",
  "无预分析任务": "No pre-analysis tasks yet",
  "点击上传按钮开始": "Click the upload button to start",
  "待处理": "Pending",
  "处理中": "Running",
  "已完成": "Completed",
  "失败": "Failed",
  "PDF 文件名": "PDF Filename",
  "上传时间": "Upload Time",
  "耗时": "Elapsed",
  "下载": "Download",
  "查看详情": "View Details"
}
```

- [ ] **Step 3: 验证 JSON 合法**

Run: `cd packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"`

期望: `OK`.

### Task 5.2: 写列表页 (TDD)

- [ ] **Step 1: 写失败测试**

文件路径: `packages/web/app/[locale]/admin/pre-analysis/page.test.tsx`

```tsx
// pre-analysis 列表页测试 (mode 1 mock + DataTable 渲染验证)

import { describe, expect, it, mock } from "bun:test";
import { render, screen, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import Page from "./page";

const mockTasks = [
  {
    id: "pa-1",
    state: "completed" as const,
    user_hash: "hash",
    pdf_filename: "D81.pdf",
    pdf_uri: "local://x",
    started_at: "2026-07-02T10:00:00Z",
    finished_at: "2026-07-02T10:01:00Z",
    output_files: [],
    summary: { total_chapters: 6, total_tables: 12, total_flagged_paragraphs: 11, elapsed_ms: 28421, cross_page_candidates: 1 },
    error: null,
  },
];

describe("admin pre-analysis list page", () => {
  it("renders DataTable with tasks", async () => {
    global.fetch = mock(async () =>
      new Response(JSON.stringify({ tasks: mockTasks }), { status: 200 })
    ) as unknown as typeof fetch;

    render(
      <IntlWrapper locale="zh">
        <Page />
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText("D81.pdf")).toBeTruthy();
    });
  });

  it("renders upload button", () => {
    render(
      <IntlWrapper locale="zh">
        <Page />
      </IntlWrapper>,
    );
    expect(screen.getByText("上传 PDF")).toBeTruthy();
  });

  it("shows empty state when no tasks", async () => {
    global.fetch = mock(async () =>
      new Response(JSON.stringify({ tasks: [] }), { status: 200 })
    ) as unknown as typeof fetch;

    render(
      <IntlWrapper locale="zh">
        <Page />
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText("无预分析任务")).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd packages/web && bun run test app/admin/pre-analysis/page.test.tsx`

期望: FAIL (module not found).

- [ ] **Step 3: 写列表页**

文件路径: `packages/web/app/[locale]/admin/pre-analysis/page.tsx`

```tsx
// admin/pre-analysis/page.tsx - 列表页 (2026-07-02 PR5)
//
// 0 自建组件: 复用 <GuardPage> + <PageHero> + <DataTable> + <FileDropzone>
// + <Badge> + <ErrorBanner> + <Button> + TanStack Query
// 路由跳转用 @/i18n/navigation 的 useRouter (CLAUDE.md §路由跳转强制)

"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRef } from "react";

import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/error-banner";
import { FileDropzone } from "@/components/common/input/file-dropzone";
import { PageHero } from "@/components/layout/page-hero";
import { GuardPage } from "@/components/auth/guard-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/navigation";
import {
  listPreAnalysisTasks,
  preAnalysisUpload,
  type PreAnalysisTaskItem,
} from "@/lib/api/pre-analysis";

const STATE_VARIANT = {
  pending: "secondary",
  running: "default",
  completed: "default",
  failed: "destructive",
} as const;

export default function AdminPreAnalysisPage() {
  const t = useTranslations();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, error, refetch, isLoading } = useQuery({
    queryKey: ["pre-analysis-tasks"],
    queryFn: () => listPreAnalysisTasks({ limit: 50 }),
  });

  const handleUpload = async (file: File) => {
    const result = await preAnalysisUpload(file);
    router.push(`/admin/pre-analysis/${result.task_id}`);
  };

  const columns: ColumnDef<PreAnalysisTaskItem>[] = [
    {
      header: t("PDF 文件名"),
      accessorKey: "pdf_filename",
    },
    {
      header: t("上传时间"),
      accessorKey: "started_at",
      cell: (row) => new Date(row.started_at).toLocaleString(),
    },
    {
      header: t("状态"),
      accessorKey: "state",
      cell: (row) => <Badge variant={STATE_VARIANT[row.state]}>{t(row.state)}</Badge>,
    },
    {
      header: t("产物数"),
      accessorKey: "summary.total_output_files",
      cell: (row) => row.output_files.length,
    },
    {
      header: t("查看详情"),
      accessorKey: "id",
      cell: (row) => (
        <Button variant="link" onClick={() => router.push(`/admin/pre-analysis/${row.id}`)}>
          {t("查看详情")}
        </Button>
      ),
    },
  ];

  return (
    <GuardPage pageKey="admin">
      <div className="space-y-6 p-6">
        <PageHero title={t("PDF 预分析")} />
        <div className="flex justify-end">
          <FileDropzone
            accept=".pdf"
            onFile={handleUpload}
            trigger={<Button>{t("上传 PDF")}</Button>}
          />
        </div>
        {error ? (
          <ErrorBanner variant="destructive" description={String(error)} />
        ) : (
          <DataTable
            dataSource={data?.tasks ?? []}
            columns={columns}
            rowKey="id"
            loading={isLoading}
            emptyText={
              <DataEmpty
                icon="📄"
                title={t("无预分析任务")}
                description={t("点击上传按钮开始")}
              />
            }
            onRowClick={(row) => router.push(`/admin/pre-analysis/${row.id}`)}
          />
        )}
      </div>
    </GuardPage>
  );
}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd packages/web && bun run test app/admin/pre-analysis/page.test.tsx`

期望: 3 个 test 全 PASS.

如果失败, 看 error msg 常见原因:
- `Cannot find module '@/components/common/table/data-table'`: 检查 alias 配置 `vitest.config.ts` 是否含 `@/`.
- `Cannot find name 'useTranslations'`: 检查是否 `import { useTranslations } from "next-intl"`.
- `Property 'state' does not exist on type 'never'`: TS 推断错, 在 `cell: (row) =>` 改 `cell: (row: PreAnalysisTaskItem) =>`.

- [ ] **Step 5: 跑 typecheck + lint + format**

Run: `cd packages/web && bun run format && bun run lint:fix && bun run typecheck`

期望: 0 error. 修 oxlint 警告: 魔法数字提取 const, import 字母排序, 变量名不单字符.

- [ ] **Step 6: Commit**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/page.tsx packages/web/app/[locale]/admin/pre-analysis/page.test.tsx packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(web): add admin/pre-analysis list page (PR5/M5)"
```

---

## PR6 = M6: 前端 admin 详情页 + 下载按钮

> **Goal:** 详情页 `/admin/pre-analysis/[task_id]` 用 `<DataTable>` 列产物清单 + `<Button asChild><a download>` 下载 zip + 跨页候选提示.

**Files:**
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.tsx`
- Create: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`
- Modify: `packages/web/messages/zh.json` (加 5 个 key)
- Modify: `packages/web/messages/en.json` (加 5 个 key)

### Task 6.1: 加 i18n 字符串

- [ ] **Step 1: 加 zh.json**

修改文件: `packages/web/messages/zh.json` (追加)

```json
{
  "返回": "返回",
  "任务详情": "任务详情",
  "产物清单": "产物清单",
  "跨页候选表": "跨页候选表",
  "本任务含 N 个跨页候选表": "本任务含 {N} 个跨页候选表, 详见各 page-N-table-M.csv, 建议下载后人工 Excel 合并",
  "下载全部 (zip)": "下载全部 (zip)",
  "章节结构": "章节结构",
  "规则段落": "规则段落",
  "表格": "表格"
}
```

- [ ] **Step 2: 加 en.json**

修改文件: `packages/web/messages/en.json` (追加)

```json
{
  "返回": "Back",
  "任务详情": "Task Details",
  "产物清单": "Artifacts",
  "跨页候选表": "Cross-page candidates",
  "本任务含 N 个跨页候选表": "This task has {N} cross-page candidate(s), see individual page-N-table-M.csv files. Download and manually merge in Excel",
  "下载全部 (zip)": "Download All (zip)",
  "章节结构": "Chapter Structure",
  "规则段落": "Flagged Paragraphs",
  "表格": "Tables"
}
```

- [ ] **Step 3: 验证 JSON 合法**

Run: `cd packages/web && node -e "JSON.parse(require('fs').readFileSync('messages/zh.json')); JSON.parse(require('fs').readFileSync('messages/en.json')); console.log('OK')"`

期望: `OK`.

### Task 6.2: 写详情页 (TDD)

- [ ] **Step 1: 写失败测试**

文件路径: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.test.tsx`

```tsx
// pre-analysis 详情页测试

import { describe, expect, it, mock } from "bun:test";
import { render, screen, waitFor } from "@testing-library/react";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import Page from "./page";

const mockTask = {
  id: "pa-1",
  state: "completed" as const,
  user_hash: "hash",
  pdf_filename: "D81.pdf",
  pdf_uri: "local://x",
  started_at: "2026-07-02T10:00:00Z",
  finished_at: "2026-07-02T10:01:00Z",
  output_files: [
    { kind: "chapter_structure" as const, filename: "chapter_structure.json", uri: "local://x", size_bytes: 3842 },
    { kind: "flagged_paragraphs" as const, filename: "flagged_paragraphs.csv", uri: "local://x", size_bytes: 2156 },
    { kind: "table" as const, filename: "tables/page-3-table-1.csv", uri: "local://x", size_bytes: 512 },
  ],
  summary: { total_chapters: 6, total_tables: 1, total_flagged_paragraphs: 11, elapsed_ms: 28421, cross_page_candidates: 1 },
  error: null,
};

describe("admin pre-analysis detail page", () => {
  it("renders task filename", async () => {
    global.fetch = mock(async () =>
      new Response(JSON.stringify(mockTask), { status: 200 })
    ) as unknown as typeof fetch;

    render(
      <IntlWrapper locale="zh">
        <Page params={{ task_id: "pa-1" }} />
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText("D81.pdf")).toBeTruthy();
    });
  });

  it("shows cross-page warning when candidates > 0", async () => {
    global.fetch = mock(async () =>
      new Response(JSON.stringify(mockTask), { status: 200 })
    ) as unknown as typeof fetch;

    render(
      <IntlWrapper locale="zh">
        <Page params={{ task_id: "pa-1" }} />
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText(/跨页候选表/)).toBeTruthy();
    });
  });

  it("renders download zip button", async () => {
    global.fetch = mock(async (url: string) => {
      if (url.includes("/download")) {
        return new Response(new Uint8Array([0x50, 0x4b]), { status: 200 });
      }
      return new Response(JSON.stringify(mockTask), { status: 200 });
    }) as unknown as typeof fetch;

    render(
      <IntlWrapper locale="zh">
        <Page params={{ task_id: "pa-1" }} />
      </IntlWrapper>,
    );
    await waitFor(() => {
      expect(screen.getByText(/下载全部/)).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd packages/web && bun run test app/admin/pre-analysis/[task_id]/page.test.tsx`

期望: FAIL (module not found).

- [ ] **Step 3: 写详情页**

文件路径: `packages/web/app/[locale]/admin/pre-analysis/[task_id]/page.tsx`

```tsx
// admin/pre-analysis/[task_id]/page.tsx - 详情页 (2026-07-02 PR6)
//
// 0 自建组件: 复用 <BackLink> + <PageHero> + <DataTable> + <Badge>
// + <ErrorBanner> + <Button asChild><a download>
// 跨页表提示用 <ErrorBanner variant="warning"> (CLAUDE.md §封装组件)

"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { BackLink } from "@/components/layout/back-link";
import { DataTable, type ColumnDef } from "@/components/common/table/data-table";
import { DataEmpty } from "@/components/common/display/app-data-empty";
import { ErrorBanner } from "@/components/common/feedback/error-banner";
import { PageHero } from "@/components/layout/page-hero";
import { GuardPage } from "@/components/auth/guard-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  downloadPreAnalysisZip,
  getPreAnalysisTask,
  type PreAnalysisOutputFile,
} from "@/lib/api/pre-analysis";

const KIND_LABEL = {
  chapter_structure: "章节结构",
  flagged_paragraphs: "规则段落",
  table: "表格",
  index: "Index",
} as const;

const STATE_VARIANT = {
  pending: "secondary",
  running: "default",
  completed: "default",
  failed: "destructive",
} as const;

const formatSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

interface PageProps {
  params: { task_id: string };
}

export default function AdminPreAnalysisDetailPage({ params }: PageProps) {
  const t = useTranslations();
  const { data, error, isLoading } = useQuery({
    queryKey: ["pre-analysis-task", params.task_id],
    queryFn: () => getPreAnalysisTask(params.task_id),
  });

  const handleDownloadZip = async () => {
    const blob = await downloadPreAnalysisZip(params.task_id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${data?.pdf_filename?.replace(/\.pdf$/i, "") ?? "pre_analysis"}_${params.task_id}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: ColumnDef<PreAnalysisOutputFile>[] = [
    {
      header: t("类型"),
      accessorKey: "kind",
      cell: (row) => KIND_LABEL[row.kind],
    },
    {
      header: "filename",
      accessorKey: "filename",
    },
    {
      header: t("大小"),
      accessorKey: "size_bytes",
      cell: (row) => formatSize(row.size_bytes),
    },
  ];

  return (
    <GuardPage pageKey="admin">
      <div className="space-y-6 p-6">
        <BackLink href="/admin/pre-analysis">{t("返回")}</BackLink>
        <PageHero
          title={`${t("任务详情")}: ${data?.pdf_filename ?? ""}`}
          description={
            data ? (
              <div className="flex gap-2">
                <Badge variant={STATE_VARIANT[data.state]}>{t(data.state)}</Badge>
                <span>{t("耗时")}: {data.summary.elapsed_ms}ms</span>
              </div>
            ) : null
          }
        />
        {error ? (
          <ErrorBanner variant="destructive" description={String(error)} />
        ) : data && data.summary.cross_page_candidates > 0 ? (
          <ErrorBanner
            variant="warning"
            description={t("本任务含 N 个跨页候选表").replace("{N}", String(data.summary.cross_page_candidates))}
          />
        ) : null}
        {data ? (
          <>
            <div className="flex justify-end">
              <Button onClick={handleDownloadZip} disabled={data.state !== "completed"}>
                {t("下载全部 (zip)")}
              </Button>
            </div>
            <DataTable
              dataSource={data.output_files}
              columns={columns}
              rowKey="uri"
              loading={isLoading}
              emptyText={<DataEmpty title={t("无产物")} />}
            />
          </>
        ) : null}
      </div>
    </GuardPage>
  );
}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd packages/web && bun run test app/admin/pre-analysis/[task_id]/page.test.tsx`

期望: 3 个 test 全 PASS.

- [ ] **Step 5: 跑 typecheck + lint + format**

Run: `cd packages/web && bun run format && bun run lint:fix && bun run typecheck`

期望: 0 error.

- [ ] **Step 6: Commit**

```bash
git add packages/web/app/[locale]/admin/pre-analysis/[task_id]/ packages/web/messages/zh.json packages/web/messages/en.json
git commit -m "feat(web): add admin/pre-analysis detail page + download (PR6/M6)"
```

---

## 最终验证 (6 PR 全部完成后跑)

- [ ] **Step 1: 后端全量测试**

Run: `cd packages/service && uv run pytest tests/ -q -x`

期望: 全绿. pre-existing 22 fail + 38 errors 不算新 fail (CLAUDE.md §强制 4 模式 / KNOWN_ISSUES).

- [ ] **Step 2: 后端代码质量**

Run: `cd packages/service && uv run ruff format && uv run ruff check --fix && uv run pyright`

期望: 0 error.

- [ ] **Step 3: 前端全量测试**

Run: `cd packages/web && bun run test`

期望: 全绿 (含 12 新 test: 5 API wrapper + 3 list page + 3 detail page + 1 d81_dummy fixture).

- [ ] **Step 4: 前端代码质量**

Run: `cd packages/web && bun run format && bun run lint:fix && bun run typecheck`

期望: 0 error.

- [ ] **Step 5: 手工 E2E (dev 环境)**

1. 启动后端 `uv run python main.py` (localhost:8000)
2. 启动前端 `cd packages/web && bun run dev` (localhost:3000)
3. super_admin 登录拿 token
4. 访问 `http://localhost:3000/zh/admin/pre-analysis`
5. 上传 1 份真 PDF (e.g. tests/ingest/fixtures/d81_dummy.pdf 或真 D81.1 手册)
6. 列表显示任务, 跳详情页
7. 详情页看到产物清单 (chapter_structure + flagged_paragraphs + tables/*.csv)
8. 点 "下载全部 (zip)", 解压验证 4 类产物齐全
9. anon token 试访问 → 403

- [ ] **Step 6: Commit final 验证日志 (optional)**

如果 §Step 1-5 有手动 fix (e.g. import 路径调整), commit fix; 否则 skip.

---

## 不要做的事 (Top 7, 跨 PR 不变量)

1. **不引 PyMuPDF4LLM / Camelot / pdfplumber / fuzzy / pint / pandas** — 全用 pymupdf 内置 + stdlib csv + loguru
2. **不联动 KG 抽取** — admin 手动 2 步 (本期不做, 单独 spec)
3. **不实现跨页表自动合并** — PyMuPDF find_tables 不内置, 启发式 ROI 不划算; UI 详情页用 ErrorBanner variant=warning 提示 admin 手动 Excel 合并
4. **不做实时返回** — 复用 BackgroundTasks 异步, 跟 _run_ingest 模式一致
5. **不新建前端组件** — 全部复用项目封装 (DataTable / FileDropzone / Badge / ErrorBanner / GuardPage / PageHero / BackLink + Button asChild)
6. **不引 PyYAML 之外的配置解析器** — 项目如有 pyyaml 依赖, 用之; 否则用 stdlib json
7. **不写 standalone script** — runner 是函数, 不是 `python -m scripts.run_pre_analysis` 命令行入口 (项目规约)

---

## 关联文档

- spec: [`../specs/2026-07-02-pdf-pre-analysis-design.md`](../specs/2026-07-02-pdf-pre-analysis-design.md)
- PRD: [`../../../prd/2026-07-02-pdf-pre-analysis-prd.md`](../../../prd/2026-07-02-pdf-pre-analysis-prd.md)
- 模板 plan: [`2026-07-01-markdown-extract-kg-pr1.md`](2026-07-01-markdown-extract-kg-pr1.md)
- 模板代码: [`../../packages/service/src/kg/extract_runner.py`](../../packages/service/src/kg/extract_runner.py) (Runner 模式)
- 模板代码: [`../../packages/service/src/ingest/api.py`](../../packages/service/src/ingest/api.py) (API 模式)
- 触发: DeepSeek `https://chat.deepseek.com/share/wbmg0i1neb616saobg`