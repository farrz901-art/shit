# 评估页重设计 + 异步后端 + Admin Token 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/evaluate` 从"读 `reports/rag_eval/report.json` 的一次性静态报告"重写成"上传 CSV → 异步跑评估 → 历史可查 → 可取消"工作流, 含 3 个前端页面 (列表/上传/详情) + FastAPI 异步运行器 + admin token 调试机制。

**Architecture:**
- 后端: `src/rag/eval/runner.py` (搬 `scripts/batch_rag_eval.py` 异步逻辑, 改成落 `Evaluation` + `EvaluationSample` 表), `src/rag/eval/router.py` (FastAPI routes), `src/rag/middleware/auth.py` (CurrentUser + resolve_user). 状态机: `pending → running → completed | failed | cancelled`. 取消走进程内 `dict[int, asyncio.Event]`.
- 前端: 3 个 Next.js 页面 (列表/上传/详情), 用 SWR 轮询 running, papaparse 解析 CSV, Editorial 设计风格沿用现有 `web/components/evaluate/`.
- Admin 鉴权: `RAG_ADMIN_TOKEN` env, `x-admin-token` header 命中即返回 `is_admin=True` 的虚拟 user, 业务 router 自动放行.

**Tech Stack:** FastAPI 0.136 / SQLAlchemy 2.0 / Pydantic v2 / Next.js 16 (App Router) / React 19 / SWR 2.4 / papaparse 5.5 / Tailwind 4.

**Windows note:** `uv run pytest` 在 Windows trampoline 有 bug, 一律用 `uv run --no-sync python -m pytest` (跟 storage plan 一致). `init_db()` 默认关闭, 测试 fixture 显式 `create_all`.

---

## 任务地图 (14 task)

按"地基 → 解析 → 运行器 → 路由 → 前端"分块, 每块可独立 commit + 测试:

| Block | Task | 主题 |
|---|---|---|
| 基础 | 1 | `CurrentUser` + `resolve_user` 中间件 (admin 优先, 客户端 token 兜底) |
| 基础 | 2 | `csv_parser.py` (文件大小/行数/列名/编码校验) |
| 基础 | 3 | `template.py` (生成 `eval_template.csv` 内容) |
| 运行器 | 4 | `runner.py` (搬 `scripts/batch_rag_eval.py` 异步逻辑, 改落 DB) |
| 运行器 | 5 | `runner.py` 状态机 + 取消机制 (Event dict) |
| 运行器 | 6 | `router.py` (4 endpoint: 列表/上传/详情/取消 + 模板下载) |
| 前端 | 7 | `web/lib/evaluate/types.ts` (加 `EvaluationRun` + `EvaluationStatus` 枚举) |
| 前端 | 8 | `web/app/api/evaluate/runs/route.ts` (BFF: GET 列表 / POST 上传) |
| 前端 | 9 | `web/app/api/evaluate/runs/[id]/route.ts` + `cancel/route.ts` (BFF) |
| 前端 | 10 | `web/app/api/evaluate/template/route.ts` (BFF 模板下载) |
| 前端 | 11 | `web/components/evaluate/StatusBadge.tsx` + `EvalListRow.tsx` |
| 前端 | 12 | 3 个页面: `/evaluate`, `/evaluate/new`, `/evaluate/[id]` |
| 测试 | 13 | E2E `04-evaluate.spec.ts` (Playwright 走通上传→详情→取消) |
| 测试 | 14 | 启动时 `running` → `failed` 恢复机制 + `.env` 文档 + README |

---

### Task 1: `CurrentUser` + `resolve_user` 中间件

**Files:**
- Create: `src/rag/middleware/__init__.py`
- Create: `src/rag/middleware/auth.py`
- Test: `tests/rag/middleware/__init__.py`
- Test: `tests/rag/middleware/test_auth.py`

- [ ] **Step 1: 写 `__init__.py`**

```python
"""HTTP 中间件层: 鉴权 / 限流 / 日志 等"""
```

- [ ] **Step 2: 写测试 (TDD: 先失败)**

`tests/rag/middleware/test_auth.py`:
```python
"""CurrentUser + resolve_user 测试"""
from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_resolve_admin_token(reset_storage_engine, monkeypatch):
    """配 RAG_ADMIN_TOKEN + 请求带 x-admin-token → is_admin=True, id=0"""
    from src.rag.middleware.auth import resolve_user, CurrentUser
    from starlette.requests import Request

    monkeypatch.setenv("RAG_ADMIN_TOKEN", "secret-admin-123")
    req = Request({"type": "http", "headers": [(b"x-admin-token", b"secret-admin-123")]})
    user = resolve_user(req)
    assert user.is_admin is True
    assert user.id == 0
    assert user.public_token == "secret-admin-123"


def test_resolve_user_token_valid(reset_storage_engine, monkeypatch):
    """RAG_ADMIN_TOKEN 留空 + 有效 x-user-token → 落库 user, is_admin=False"""
    from src.rag.middleware.auth import resolve_user
    from src.rag.auth.models import User
    from src.rag.storage import Base
    from src.rag.storage.engine import get_engine
    from starlette.requests import Request
    Base.metadata.create_all(get_engine())

    monkeypatch.setenv("RAG_ADMIN_TOKEN", "")
    with __import__("src.rag.storage.session", fromlist=["session_scope"]).session_scope() as s:
        s.add(User(public_token="client-tok-abc"))
    req = Request({"type": "http", "headers": [(b"x-user-token", b"client-tok-abc")]})
    user = resolve_user(req)
    assert user.is_admin is False
    assert user.public_token == "client-tok-abc"
    assert user.id > 0  # 落库后有 id


def test_resolve_user_token_missing_401(monkeypatch):
    """无 admin + 无 user header → 401"""
    from src.rag.middleware.auth import resolve_user
    from starlette.requests import Request

    monkeypatch.setenv("RAG_ADMIN_TOKEN", "")
    req = Request({"type": "http", "headers": []})
    with pytest.raises(HTTPException) as exc:
        resolve_user(req)
    assert exc.value.status_code == 401


def test_resolve_user_token_invalid_401(reset_storage_engine, monkeypatch):
    """DB 不存在的 token → 401"""
    from src.rag.middleware.auth import resolve_user
    from src.rag.storage import Base
    from src.rag.storage.engine import get_engine
    from starlette.requests import Request
    Base.metadata.create_all(get_engine())

    monkeypatch.setenv("RAG_ADMIN_TOKEN", "")
    req = Request({"type": "http", "headers": [(b"x-user-token", b"never-existed")]})
    with pytest.raises(HTTPException) as exc:
        resolve_user(req)
    assert exc.value.status_code == 401


def test_admin_token_mismatch_falls_through(monkeypatch):
    """x-admin-token 错 → 不会 raise, 而是继续走 x-user-token 校验"""
    from src.rag.middleware.auth import resolve_user
    from starlette.requests import Request

    monkeypatch.setenv("RAG_ADMIN_TOKEN", "correct")
    req = Request({"type": "http", "headers": [(b"x-admin-token", b"wrong")]})
    with pytest.raises(HTTPException) as exc:
        resolve_user(req)
    assert exc.value.status_code == 401  # 没 user token, 自然 401
```

- [ ] **Step 3: 跑测试, 验证失败**

```bash
uv run --no-sync python -m pytest tests/rag/middleware/test_auth.py -v
```
预期: ImportError 或 ModuleNotFoundError (没建 middleware 包).

- [ ] **Step 4: 实现 `src/rag/middleware/auth.py`**

```python
"""鉴权: 解析 admin token / 客户端 token → CurrentUser

- Admin 优先: RAG_ADMIN_TOKEN 配了 + header 命中 → 虚拟 user (id=0, is_admin=True)
- 客户端 token: x-user-token 头, 在 users 表里查得到才放行
- 鉴权失败统一 401

为什么 admin 走虚拟 user 不入库: 见 docs/superpowers/specs/2026-06-09-storage-layer-design.md "Admin 虚拟 User" 节.
"""
from __future__ import annotations

import os

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..auth.models import User
from ..storage.session import session_scope


class CurrentUser(BaseModel):
    """当前请求的鉴权上下文

    - admin: id=0 (User.id 从 1 自增, 不冲突), public_token=env 配的值
    - 普通: id 来自 users 表, public_token=客户端存的 32 字节 hex
    """
    id: int
    public_token: str
    is_admin: bool = False


def resolve_user(request: Request) -> CurrentUser:
    """FastAPI Depends 用的鉴权函数

    优先级:
    1. RAG_ADMIN_TOKEN env 非空 + x-admin-token header 匹配 → admin
    2. x-user-token header 落库存在 → 普通 user
    3. 都没 → 401
    """
    # 1. admin 优先
    admin_token = os.getenv("RAG_ADMIN_TOKEN", "")
    if admin_token and request.headers.get("x-admin-token") == admin_token:
        return CurrentUser(id=0, public_token=admin_token, is_admin=True)

    # 2. 普通客户端 token
    user_token = request.headers.get("x-user-token", "")
    if not user_token:
        raise HTTPException(401, "missing x-user-token (or x-admin-token)")

    with session_scope() as s:
        user = s.query(User).filter_by(public_token=user_token).first()
    if not user:
        raise HTTPException(401, "invalid user token")
    return CurrentUser(id=user.id, public_token=user_token, is_admin=False)
```

- [ ] **Step 5: 跑测试, 验证通过**

```bash
uv run --no-sync python -m pytest tests/rag/middleware/test_auth.py -v
```
预期: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/rag/middleware/ tests/rag/middleware/
git commit -m "feat(auth): add CurrentUser + resolve_user (admin token + client token)"
```

---

### Task 2: `csv_parser.py` (文件大小/行数/列名/编码校验)

**Files:**
- Create: `src/rag/eval/csv_parser.py`
- Test: `tests/rag/eval/test_csv_parser.py`

- [ ] **Step 1: 写测试**

`tests/rag/eval/test_csv_parser.py`:
```python
"""CSV 评估集解析 / 校验"""
from __future__ import annotations

import io
import pytest

from src.rag.eval.csv_parser import parse_eval_csv, CSVParsingError


def test_parse_valid_csv_with_ground_truth():
    """标准 CSV: question + ground_truth, 全部非空"""
    content = b"question,ground_truth\n1LE0001,siemens\n3RT2026,contactor\n"
    rows = parse_eval_csv(content, filename="test.csv")
    assert len(rows) == 2
    assert rows[0] == {"question": "1LE0001", "ground_truth": "siemens"}


def test_parse_valid_csv_without_ground_truth():
    """question 列必填, ground_truth 可选"""
    content = b"question\nq1\nq2\n"
    rows = parse_eval_csv(content, filename="t.csv")
    assert len(rows) == 2
    assert rows[0] == {"question": "q1", "ground_truth": None}


def test_parse_rejects_missing_question_column():
    """没有 question 列 → 报错"""
    content = b"prompt,answer\nq1,a1\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="bad.csv")
    assert "question" in str(exc.value)


def test_parse_rejects_empty_question():
    """某行 question 是空串 → 报错 (行号提示)"""
    content = b"question,ground_truth\nq1,ok\n,q2\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="bad.csv")
    assert "第 2 行" in str(exc.value)


def test_parse_rejects_oversize_file():
    """> 5MB → 报错"""
    content = b"question\n" + b"x" * (5 * 1024 * 1024 + 1) + b"\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="big.csv")
    assert "5MB" in str(exc.value)


def test_parse_rejects_too_many_rows():
    """> 200 行 → 报错"""
    content = "question\n" + "\n".join(f"q{i}" for i in range(201))
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content.encode("utf-8"), filename="huge.csv")
    assert "200" in str(exc.value)


def test_parse_rejects_too_few_rows():
    """0 行 (只有表头) → 报错"""
    content = b"question,ground_truth\n"
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="empty.csv")
    assert "1" in str(exc.value)  # "至少 1 行"


def test_parse_rejects_bad_encoding():
    """非 UTF-8 → 报错"""
    content = b"question\n\xb1\xfe"  # 非法 UTF-8 序列
    with pytest.raises(CSVParsingError) as exc:
        parse_eval_csv(content, filename="gbk.csv")
    assert "UTF-8" in str(exc.value)


def test_parse_strips_whitespace():
    """question 周围空白自动 trim"""
    content = b"question\n  q1  \nq2\t\n"
    rows = parse_eval_csv(content, filename="t.csv")
    assert rows[0]["question"] == "q1"
    assert rows[1]["question"] == "q2"
```

- [ ] **Step 2: 跑测试, 验证失败**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_csv_parser.py -v
```
预期: ModuleNotFoundError / ImportError.

- [ ] **Step 3: 实现 `src/rag/eval/csv_parser.py`**

```python
"""CSV 评估集解析: 校验 + 清洗

设计目标: 拒绝一切 schema/编码/大小不合规, 失败给出可读中文错.
供 FastAPI multipart 上传和 scripts 都用.
"""
from __future__ import annotations

import csv
import io

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MIN_ROWS = 1
MAX_ROWS = 200


class CSVParsingError(ValueError):
    """CSV 校验失败, 抛出时带可读中文 message"""


def parse_eval_csv(content: bytes, filename: str = "<upload>") -> list[dict]:
    """解析评估集 CSV, 返回 [{question, ground_truth}, ...]

    Args:
        content: 文件原始字节
        filename: 仅用于错误信息 (不读盘)

    Returns:
        list[dict], 每条必须有 question 键, ground_truth 可为 None

    Raises:
        CSVParsingError: 任何 schema/编码/大小不合规
    """
    # 1. 文件大小
    if len(content) > MAX_FILE_SIZE:
        raise CSVParsingError(
            f"文件 {filename} 超过 5MB (实际 {len(content) // 1024}KB), 请精简数据"
        )

    # 2. 编码 (UTF-8 strict)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as e:
        raise CSVParsingError(
            f"文件 {filename} 不是 UTF-8 编码 ({e.reason}). 请用 Excel 另存为 CSV UTF-8"
        ) from e

    # 3. 解析 + 校验
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "question" not in reader.fieldnames:
        raise CSVParsingError(
            f"文件 {filename} 缺 'question' 列. 必须有表头: question,ground_truth"
        )

    rows: list[dict] = []
    for line_no, raw in enumerate(reader, start=2):  # 第 1 行是表头
        q = (raw.get("question") or "").strip()
        gt = (raw.get("ground_truth") or "").strip() or None
        if not q:
            raise CSVParsingError(
                f"文件 {filename} 第 {line_no} 行 question 为空"
            )
        rows.append({"question": q, "ground_truth": gt})

    # 4. 行数
    if len(rows) < MIN_ROWS:
        raise CSVParsingError(
            f"文件 {filename} 只有表头, 至少需要 {MIN_ROWS} 行数据"
        )
    if len(rows) > MAX_ROWS:
        raise CSVParsingError(
            f"文件 {filename} 有 {len(rows)} 行, 最多 {MAX_ROWS} 行"
        )

    return rows
```

- [ ] **Step 4: 跑测试, 验证通过**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_csv_parser.py -v
```
预期: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rag/eval/csv_parser.py tests/rag/eval/test_csv_parser.py
git commit -m "feat(eval): CSV 解析器 (文件大小/行数/列名/编码校验)"
```

---

### Task 3: `template.py` (生成 `eval_template.csv` 内容)

**Files:**
- Create: `src/rag/eval/template.py`
- Test: `tests/rag/eval/test_template.py`

- [ ] **Step 1: 写测试**

`tests/rag/eval/test_template.py`:
```python
"""评估 CSV 模板生成"""
from __future__ import annotations

from src.rag.eval.template import build_eval_template_csv


def test_template_has_csv_header():
    """模板首行是表头, 含 question + ground_truth"""
    csv_text = build_eval_template_csv()
    first_line = csv_text.splitlines()[0]
    assert first_line == "question,ground_truth"


def test_template_has_at_least_one_example():
    """模板至少 1 条示例 (给用户参考格式)"""
    csv_text = build_eval_template_csv()
    lines = csv_text.strip().splitlines()
    assert len(lines) >= 2  # 表头 + 至少 1 行


def test_template_uses_utf8_encodable_chinese():
    """模板含中文示例, 能 UTF-8 编码"""
    csv_text = build_eval_template_csv()
    encoded = csv_text.encode("utf-8")
    assert b"\xe8\xa5\xbf\xe9\x97\xa8\xe5\xad\x90" in encoded  # 西门子


def test_template_is_valid_csv():
    """模板内容能被 csv.DictReader 解析"""
    import csv
    import io
    csv_text = build_eval_template_csv()
    reader = csv.DictReader(io.StringIO(csv_text))
    assert "question" in (reader.fieldnames or [])
    rows = list(reader)
    assert len(rows) >= 1
    for r in rows:
        assert r.get("question"), f"示例行 question 为空: {r}"
```

- [ ] **Step 2: 跑测试, 验证失败**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_template.py -v
```
预期: ModuleNotFoundError.

- [ ] **Step 3: 实现 `src/rag/eval/template.py`**

```python
"""评估 CSV 模板生成

供 GET /api/evaluate/template 返回, 也供前端展示下载预览.
模板内容跟 spec "新建评估" 节里的示例 1:1 对齐, 用户改完即可上传.
"""
from __future__ import annotations

# 示例题目来自西门子 1LE0 电机产品手册 (tests/fixtures/rag_eval/qa_dataset.yaml 同款)
_EXAMPLE_ROWS = [
    ('"1LE0001-1AA4 是什么系列?""', '"西门子 1LE0 低压高效电机"'),
    ('"3RT2026 是接触器还是断路器?""', '"西门子 3RT 接触器系列"'),
    ('"请解释 1FK7 伺服电机的编码器类型"', '"1FK7 编码器类型取决于订货号后缀, 常见为增量式 TTL/HTL"'),
]


def build_eval_template_csv() -> str:
    """生成模板 CSV 文本 (UTF-8, 含表头 + 示例)

    Returns:
        多行字符串, 第一行表头, 后跟示例行
    """
    lines = ["question,ground_truth"]
    lines.extend(f"{q},{gt}" for q, gt in _EXAMPLE_ROWS)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: 跑测试, 验证通过**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_template.py -v
```
预期: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rag/eval/template.py tests/rag/eval/test_template.py
git commit -m "feat(eval): CSV 模板生成 (含 3 条西门子示例)"
```

---

### Task 4: `runner.py` - 异步评估执行 (搬 `scripts/batch_rag_eval.py` 逻辑, 改落 DB)

**Files:**
- Create: `src/rag/eval/runner.py`
- Test: `tests/rag/eval/test_runner.py`

- [ ] **Step 1: 写测试 (mock Dify + RAGAS, 不走真实 LLM)**

`tests/rag/eval/test_runner.py`:
```python
"""异步评估运行器: 调 Dify + RAGAS, 落 Evaluation + EvaluationSample

⚠️ Dify + RAGAS 都要 mock, 避免真实 LLM 调用. mock 方式:
- runner 接受 dify + evaluator 参数注入, 测试时传 MagicMock
- 这样 spec 写"调 Dify + 调 RAGAS" 也能 1:1 覆盖
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.rag.auth.models import User
from src.rag.eval.models import Evaluation, EvaluationSample
from src.rag.eval.runner import run_evaluation
from src.rag.storage import Base
from src.rag.storage.engine import get_engine
from src.rag.storage.session import session_scope


@pytest.fixture
def user_id(reset_storage_engine):
    """建一个测试用户, 返回 id"""
    Base.metadata.create_all(get_engine())
    with session_scope() as s:
        u = User(public_token="runner-tok")
        s.add(u)
        s.flush()
        return u.id


def _mock_dify_client():
    """返回 (dify_mock, answers)"""
    dify = MagicMock()
    dify.achat = AsyncMock(side_effect=lambda q: {
        "answer": f"答: {q}",
        "contexts": [f"ctx-for-{q}"],
        "conversation_id": "",
        "raw": {},
    })
    return dify


def _mock_evaluator():
    """返回 mock RAGASEvaluator, 4 指标都给 0.8"""
    ev = MagicMock()
    metrics = MagicMock()
    metrics.to_dict = MagicMock(return_value={
        "faithfulness": 0.8,
        "answer_relevancy": 0.8,
        "context_precision": 0.8,
        "context_recall": 0.8,
    })
    ev.evaluate_single = MagicMock(return_value=metrics)
    return ev


def test_run_evaluation_creates_evaluation_and_samples(user_id):
    """跑 2 题 → 1 条 Evaluation + 2 条 EvaluationSample, status=completed"""
    dataset = [
        {"question": "Q1", "ground_truth": "A1"},
        {"question": "Q2", "ground_truth": "A2"},
    ]
    asyncio.run(run_evaluation(
        user_id=user_id,
        dataset_name="test.csv",
        dataset=dataset,
        concurrency=2,
        dify=_mock_dify_client(),
        evaluator=_mock_evaluator(),
    ))

    with session_scope() as s:
        evals = s.query(Evaluation).all()
        assert len(evals) == 1
        e = evals[0]
        assert e.status == "completed"
        assert e.total_samples == 2
        assert e.successful == 2
        assert e.failed == 0
        assert e.user_id == user_id
        assert e.dataset_name == "test.csv"
        assert e.avg_metrics == {
            "faithfulness": 0.8,
            "answer_relevancy": 0.8,
            "context_precision": 0.8,
            "context_recall": 0.8,
        }
        assert e.duration_seconds is not None
        assert e.finished_at is not None

        samples = s.query(EvaluationSample).filter_by(evaluation_id=e.id).order_by("index").all()
        assert len(samples) == 2
        assert samples[0].index == 0
        assert samples[0].question == "Q1"
        assert samples[0].answer == "答: Q1"
        assert samples[0].contexts == ["ctx-for-Q1"]
        assert samples[0].metrics == samples[1].metrics  # mock 返回值
        assert samples[0].error is None


def test_run_evaluation_continues_on_dify_error(user_id):
    """Dify 失败时: 该 sample 写 error, 其他 sample 正常, status=completed"""
    dify = MagicMock()
    async def achat_with_fail(q):
        if q == "BAD":
            from src.rag.integrations.dify_client import DifyAPIError
            raise DifyAPIError("dify down")
        return {"answer": f"ok-{q}", "contexts": ["c"], "conversation_id": "", "raw": {}}
    dify.achat = AsyncMock(side_effect=achat_with_fail)

    dataset = [
        {"question": "GOOD1", "ground_truth": "a"},
        {"question": "BAD", "ground_truth": "b"},
        {"question": "GOOD2", "ground_truth": "c"},
    ]
    asyncio.run(run_evaluation(
        user_id=user_id, dataset_name="t.csv", dataset=dataset,
        concurrency=1, dify=dify, evaluator=_mock_evaluator(),
    ))

    with session_scope() as s:
        e = s.query(Evaluation).one()
        assert e.status == "completed"
        assert e.successful == 2
        assert e.failed == 1
        bad = s.query(EvaluationSample).filter_by(index=1).one()
        assert "DifyAPIError" in (bad.error or "")
        assert bad.metrics is None
        assert bad.answer is None or bad.answer == ""


def test_run_evaluation_continues_on_ragas_error(user_id):
    """RAGAS 失败时: 落 answer/contexts, metrics=None, error 含 RAGASError"""
    dify = _mock_dify_client()
    ev = MagicMock()
    def eval_with_fail(**kwargs):
        if "fail-me" in kwargs.get("question", ""):
            raise RuntimeError("ragas broke")
        m = MagicMock()
        m.to_dict = MagicMock(return_value={"faithfulness": 0.9, "answer_relevancy": 0.9, "context_precision": 0.9, "context_recall": 0.9})
        return m
    ev.evaluate_single = MagicMock(side_effect=eval_with_fail)

    dataset = [
        {"question": "ok-q", "ground_truth": None},
        {"question": "fail-me", "ground_truth": None},
    ]
    asyncio.run(run_evaluation(
        user_id=user_id, dataset_name="t.csv", dataset=dataset,
        concurrency=1, dify=dify, evaluator=ev,
    ))

    with session_scope() as s:
        e = s.query(Evaluation).one()
        assert e.successful == 1
        assert e.failed == 1
        bad = s.query(EvaluationSample).filter_by(index=1).one()
        assert "ragas broke" in (bad.error or "")


def test_run_evaluation_persists_cancelled_status(user_id):
    """传入 cancelled event → 第 1 题前检测, 跳出, status=cancelled"""
    ev = _mock_evaluator()
    dify = _mock_dify_client()
    event = asyncio.Event()
    event.set()  # 提前 set, 模拟"用户取消"

    dataset = [{"question": f"Q{i}", "ground_truth": None} for i in range(3)]
    asyncio.run(run_evaluation(
        user_id=user_id, dataset_name="t.csv", dataset=dataset,
        concurrency=1, dify=dify, evaluator=ev,
        cancel_event=event,
    ))

    with session_scope() as s:
        e = s.query(Evaluation).one()
        assert e.status == "cancelled"
        assert e.successful == 0
        # 不应生成任何 sample
        assert s.query(EvaluationSample).count() == 0


def test_run_evaluation_status_runs_through_states(user_id):
    """running 中外部可查到 status='running' (用事件触发: 起 task 后 query)"""
    import threading

    dataset = [{"question": f"Q{i}", "ground_truth": None} for i in range(2)]

    async def main():
        task = asyncio.create_task(run_evaluation(
            user_id=user_id, dataset_name="t.csv", dataset=dataset,
            concurrency=1, dify=_mock_dify_client(), evaluator=_mock_evaluator(),
        ))
        # 让 main task 跑一帧
        await asyncio.sleep(0)
        with session_scope() as s:
            e = s.query(Evaluation).one()
            running_status = e.status
        await task
        return running_status

    observed = asyncio.run(main())
    assert observed == "running"
    with session_scope() as s:
        e = s.query(Evaluation).one()
        assert e.status == "completed"
```

- [ ] **Step 2: 跑测试, 验证失败**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_runner.py -v
```
预期: ImportError (没建 runner.py).

- [ ] **Step 3: 实现 `src/rag/eval/runner.py`**

```python
"""异步评估运行器: 跑 Dify + RAGAS, 落 Evaluation + EvaluationSample

设计要点 (从 scripts/batch_rag_eval.py 复盘):
1. Dify + RAGAS 整体限并发 (之前漏 sem 块导致 6 个 achat 全开)
2. RAGAS 走 asyncio.to_thread 释放事件循环
3. sample 按 index 入库, 详情页查得有序
4. 任何题失败不影响其他题, 最终聚合 successful/failed
5. 取消机制: cancel_event (asyncio.Event) 在每题前检查
6. 状态机: pending (行级 INSERT) → running → completed | failed | cancelled
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..auth.models import User
from ..integrations.dify_client import DifyAPIError
from ..storage.session import session_scope
from .models import Evaluation, EvaluationSample

# 评估结果落库的 4 个指标 key (跟 RAGAMetrics.to_dict 对齐)
_METRIC_KEYS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


async def _evaluate_one(
    index: int,
    item: dict,
    dify: Any,
    evaluator: Any,
    sem: asyncio.Semaphore,
) -> dict:
    """单题评估, 返回结果 dict (不直接落库, 由 caller 决定)"""
    question = item["question"]
    ground_truth = item.get("ground_truth")

    async with sem:
        # 1. 调 Dify
        try:
            dify_resp = await dify.achat(question)
        except DifyAPIError as e:
            return {
                "index": index, "question": question, "ground_truth": ground_truth,
                "answer": None, "contexts": None, "metrics": None,
                "error": f"DifyAPIError: {e}",
            }
        answer = dify_resp.get("answer", "")
        contexts = dify_resp.get("contexts", [])

        # 2. 调 RAGAS (丢线程池)
        try:
            metrics_obj = await asyncio.to_thread(
                evaluator.evaluate_single,
                question=question, answer=answer, contexts=contexts,
                ground_truth=ground_truth,
            )
        except Exception as e:
            return {
                "index": index, "question": question, "ground_truth": ground_truth,
                "answer": answer, "contexts": contexts, "metrics": None,
                "error": f"RAGASError: {e}",
            }

    return {
        "index": index, "question": question, "ground_truth": ground_truth,
        "answer": answer, "contexts": contexts, "metrics": metrics_obj.to_dict(),
        "error": None,
    }


async def run_evaluation(
    user_id: int,
    dataset_name: str,
    dataset: list[dict],
    concurrency: int,
    dify: Any,
    evaluator: Any,
    evaluation_id: int | None = None,
    cancel_event: asyncio.Event | None = None,
) -> int:
    """跑一次评估, 落库; 返回 evaluation.id

    Args:
        user_id: 发起评估的用户 id
        dataset_name: 数据集名 (CSV 文件名)
        dataset: [{question, ground_truth}, ...]
        concurrency: 同时跑多少题
        dify: DifyClient 实例
        evaluator: RAGASEvaluator 实例
        evaluation_id: 已存在的 Evaluation.id (重启恢复场景), 默认新建
        cancel_event: 取消信号, set 后跳出循环

    Returns:
        evaluation.id (int)
    """
    sem = asyncio.Semaphore(concurrency)
    start = time.perf_counter()

    # 1. 落 Evaluation 行 (status=pending) + 立刻翻 running
    with session_scope() as s:
        if evaluation_id is None:
            e = Evaluation(
                user_id=user_id,
                dataset_name=dataset_name,
                status="pending",
                total_samples=len(dataset),
                concurrency=concurrency,
            )
            s.add(e)
            s.flush()
            evaluation_id = e.id
        else:
            e = s.get(Evaluation, evaluation_id)
            e.status = "running"
            e.total_samples = len(dataset)

    # 2. 检查取消
    if cancel_event is not None and cancel_event.is_set():
        with session_scope() as s:
            e = s.get(Evaluation, evaluation_id)
            e.status = "cancelled"
            e.finished_at = datetime.now(UTC)
        return evaluation_id

    # 3. 切 running
    with session_scope() as s:
        e = s.get(Evaluation, evaluation_id)
        e.status = "running"

    # 4. 异步跑题 (边完成边落 sample)
    sample_results: list[dict] = []

    async def run_with_cancel_check(idx: int, item: dict) -> dict | None:
        if cancel_event is not None and cancel_event.is_set():
            return None
        result = await _evaluate_one(idx, item, dify, evaluator, sem)
        # 完成一条立刻落 sample
        with session_scope() as s:
            sample = EvaluationSample(
                evaluation_id=evaluation_id,
                index=result["index"],
                question=result["question"],
                ground_truth=result["ground_truth"],
                answer=result["answer"],
                contexts=result["contexts"],
                metrics=result["metrics"],
                error=result["error"],
            )
            s.add(sample)
        return result

    tasks = [run_with_cancel_check(i, item) for i, item in enumerate(dataset)]
    results = await asyncio.gather(*tasks)

    # 5. 取消 → 终止 (results 里 None 是被取消的)
    if cancel_event is not None and cancel_event.is_set():
        sample_results = [r for r in results if r is not None]
        with session_scope() as s:
            e = s.get(Evaluation, evaluation_id)
            e.status = "cancelled"
            e.successful = sum(1 for r in sample_results if r["error"] is None)
            e.failed = sum(1 for r in sample_results if r["error"] is not None)
            e.finished_at = datetime.now(UTC)
            e.duration_seconds = time.perf_counter() - start
        return evaluation_id

    # 6. 正常完成 → 聚合
    sample_results = [r for r in results if r is not None]  # type: ignore[misc]
    valid_metrics = [r["metrics"] for r in sample_results if r["metrics"]]
    avg = {k: None for k in _METRIC_KEYS}
    for k in _METRIC_KEYS:
        vals = [m[k] for m in valid_metrics if m.get(k) is not None]
        avg[k] = sum(vals) / len(vals) if vals else None

    successful = sum(1 for r in sample_results if r["error"] is None)
    failed = sum(1 for r in sample_results if r["error"] is not None)

    with session_scope() as s:
        e = s.get(Evaluation, evaluation_id)
        e.status = "completed"
        e.successful = successful
        e.failed = failed
        e.avg_metrics = avg
        e.duration_seconds = time.perf_counter() - start
        e.finished_at = datetime.now(UTC)

    return evaluation_id
```

- [ ] **Step 4: 跑测试, 验证通过**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_runner.py -v
```
预期: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rag/eval/runner.py tests/rag/eval/test_runner.py
git commit -m "feat(eval): 异步评估运行器 (Dify + RAGAS, 落 DB + 取消支持)"
```

---

### Task 5: `runner_registry.py` - 进程内取消事件表 + 重启恢复

**Files:**
- Create: `src/rag/eval/runner_registry.py`
- Test: `tests/rag/eval/test_runner_registry.py`

- [ ] **Step 1: 写测试**

`tests/rag/eval/test_runner_registry.py`:
```python
"""进程内取消事件表 + 启动时 running 标 failed"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.rag.auth.models import User
from src.rag.eval.models import Evaluation
from src.rag.eval.runner_registry import (
    request_cancel, register_cancel_event, unregister_cancel_event,
    recover_orphaned_running,
)
from src.rag.storage import Base
from src.rag.storage.engine import get_engine
from src.rag.storage.session import session_scope


def _create_running_eval(user_id: int) -> int:
    """插一条 status='running' 的 evaluation 行 (模拟重启前残留)"""
    with session_scope() as s:
        e = Evaluation(
            user_id=user_id, dataset_name="orphan.csv", status="running",
            total_samples=5, concurrency=3,
        )
        s.add(e)
        s.flush()
        return e.id


def test_register_and_request_cancel():
    """注册 → 取消 → 注销 全套"""
    import asyncio
    event = asyncio.Event()
    register_cancel_event(42, event)
    assert request_cancel(42) is True
    assert event.is_set()
    unregister_cancel_event(42)
    assert request_cancel(42) is False  # 已注销


def test_request_cancel_unknown_id():
    """未注册的 id → False"""
    assert request_cancel(99999) is False


def test_recover_orphaned_running_marks_failed(reset_storage_engine):
    """启动恢复: status='running' 的全部标 failed + 写 error_message"""
    Base.metadata.create_all(get_engine())
    with session_scope() as s:
        u = User(public_token="recover-tok")
        s.add(u)
        s.flush()
        uid = u.id

    eid = _create_running_eval(uid)
    recover_orphaned_running()

    with session_scope() as s:
        e = s.get(Evaluation, eid)
        assert e.status == "failed"
        assert "服务重启" in (e.error_message or "")
        assert e.finished_at is not None


def test_recover_skips_completed_evals(reset_storage_engine):
    """completed 的不动"""
    Base.metadata.create_all(get_engine())
    with session_scope() as s:
        u = User(public_token="r-tok-2")
        s.add(u)
        s.flush()
        uid = u.id

    with session_scope() as s:
        completed = Evaluation(
            user_id=uid, dataset_name="done.csv", status="completed",
            total_samples=1, successful=1, failed=0, avg_metrics={"faithfulness": 0.9},
            duration_seconds=1.0, finished_at=datetime.now(UTC),
        )
        s.add(completed)
        s.flush()
        cid = completed.id

    recover_orphaned_running()

    with session_scope() as s:
        e = s.get(Evaluation, cid)
        assert e.status == "completed"
        assert e.error_message is None
```

- [ ] **Step 2: 跑测试, 验证失败**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_runner_registry.py -v
```
预期: ModuleNotFoundError.

- [ ] **Step 3: 实现 `src/rag/eval/runner_registry.py`**

```python
"""进程内运行状态表

- 取消信号: dict[evaluation_id -> asyncio.Event], 后台 task 在每题前检查
- 重启恢复: 启动时扫 status='running' 的记录, 标 failed (写 "服务重启中断")
  避免"僵尸 running" 永久挂在前端

⚠️ 多 worker 部署 (uvicorn --workers N) 不支持, 需换 Redis. 本 spec YAGNI 单进程.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from .models import Evaluation
from ..storage.session import session_scope

# evaluation_id -> asyncio.Event (set = 取消信号)
_cancel_events: dict[int, asyncio.Event] = {}


def register_cancel_event(evaluation_id: int, event: asyncio.Event) -> None:
    """后台 task 启动时注册 (覆盖式: 同 id 重启时替换)"""
    _cancel_events[evaluation_id] = event


def unregister_cancel_event(evaluation_id: int) -> None:
    """后台 task 结束时清理 (completed / failed / cancelled 都调)"""
    _cancel_events.pop(evaluation_id, None)


def request_cancel(evaluation_id: int) -> bool:
    """HTTP cancel handler 调, 触发取消

    Returns:
        True = 成功 set (后台 task 还活着)
        False = id 不在表里 (已结束或从未注册)
    """
    event = _cancel_events.get(evaluation_id)
    if event is None:
        return False
    event.set()
    return True


def recover_orphaned_running() -> int:
    """启动时调一次: 把所有 status='running' 的 evaluation 标 failed

    Returns:
        修复的记录数
    """
    count = 0
    with session_scope() as s:
        orphans = s.query(Evaluation).filter(Evaluation.status == "running").all()
        for e in orphans:
            e.status = "failed"
            e.error_message = "服务重启中断"
            e.finished_at = datetime.now(UTC)
            count += 1
    return count
```

- [ ] **Step 4: 跑测试, 验证通过**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_runner_registry.py -v
```
预期: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/rag/eval/runner_registry.py tests/rag/eval/test_runner_registry.py
git commit -m "feat(eval): 进程内取消事件表 + 重启恢复 (orphan running → failed)"
```

---

### Task 6: `router.py` (4 endpoint: 列表/上传/详情/取消 + 模板下载)

**Files:**
- Create: `src/rag/eval/router.py`
- Test: `tests/rag/eval/test_router.py`

- [ ] **Step 1: 写测试**

`tests/rag/eval/test_router.py`:
```python
"""/api/evaluate/* 路由测试: 鉴权 + 业务流

用 FastAPI TestClient 模拟 HTTP, 不真起 server.
"""
from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.rag.auth.models import User
from src.rag.eval.models import Evaluation
from src.rag.eval.router import router as eval_router
from src.rag.middleware.auth import resolve_user
from src.rag.storage import Base
from src.rag.storage.engine import get_engine
from src.rag.storage.session import session_scope


@pytest.fixture
def app(monkeypatch):
    """建一个最小 FastAPI app + 注入 resolve_user 依赖"""
    a = FastAPI()
    a.include_router(eval_router)
    return a


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def user_id(reset_storage_engine):
    Base.metadata.create_all(get_engine())
    with session_scope() as s:
        u = User(public_token="router-tok-user")
        s.add(u)
        s.flush()
        return u.id


def _csv_bytes() -> bytes:
    return b"question,ground_truth\nQ1,A1\nQ2,A2\n"


def test_list_runs_requires_auth(client):
    """没 header → 401"""
    r = client.get("/api/evaluate/runs")
    assert r.status_code == 401


def test_list_runs_returns_empty_for_new_user(client, user_id, monkeypatch):
    """新用户没评估 → 空列表"""
    r = client.get(
        "/api/evaluate/runs",
        headers={"x-user-token": "router-tok-user"},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body == []


def test_upload_creates_pending_evaluation(client, user_id, monkeypatch):
    """上传 CSV → 落 status=pending + 返回 id"""
    # mock run_evaluation 后台启动 (避免真跑 Dify)
    import asyncio
    from src.rag.eval import runner

    async def fake_run(**kwargs):
        return kwargs.get("evaluation_id") or 1
    monkeypatch.setattr(runner, "run_evaluation", fake_run)
    # background task 用 asyncio.create_task, 我们 patch 后立刻 return

    r = client.post(
        "/api/evaluate/runs",
        headers={"x-user-token": "router-tok-user"},
        files={"file": ("t.csv", _csv_bytes(), "text/csv")},
        data={"concurrency": "3"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "id" in body
    assert body["status"] == "pending"

    with session_scope() as s:
        e = s.get(Evaluation, body["id"])
        assert e.user_id == user_id
        assert e.dataset_name == "t.csv"
        assert e.status == "pending"
        assert e.concurrency == 3
        assert e.total_samples == 2


def test_upload_rejects_oversize(client, user_id):
    """> 5MB → 400"""
    big = b"question,ground_truth\n" + b"x," * (3 * 1024 * 1024) + b"\n"
    r = client.post(
        "/api/evaluate/runs",
        headers={"x-user-token": "router-tok-user"},
        files={"file": ("big.csv", big, "text/csv")},
        data={"concurrency": "3"},
    )
    assert r.status_code == 400
    assert "5MB" in r.json()["detail"]


def test_get_run_returns_with_samples(client, user_id):
    """GET /runs/{id} 返回 evaluation + samples (按 index 排序)"""
    with session_scope() as s:
        e = Evaluation(
            user_id=user_id, dataset_name="x.csv", status="completed",
            total_samples=2, successful=2, failed=0,
            avg_metrics={"faithfulness": 0.9}, duration_seconds=1.5,
        )
        s.add(e)
        s.flush()
        eid = e.id
        s.add_all([
            __import__("src.rag.eval.models", fromlist=["EvaluationSample"]).EvaluationSample(
                evaluation_id=eid, index=0, question="Q1", answer="A1", metrics={"faithfulness": 0.9}
            ),
            __import__("src.rag.eval.models", fromlist=["EvaluationSample"]).EvaluationSample(
                evaluation_id=eid, index=1, question="Q2", answer="A2", metrics={"faithfulness": 0.8}
            ),
        ])

    r = client.get(
        f"/api/evaluate/runs/{eid}",
        headers={"x-user-token": "router-tok-user"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == eid
    assert body["status"] == "completed"
    assert len(body["samples"]) == 2
    assert body["samples"][0]["index"] == 0


def test_get_run_404_for_other_user(client, user_id):
    """别人的 evaluation → 404 (避免泄露存在性)"""
    with session_scope() as s:
        s.add(User(public_token="other-user"))
        s.flush()
        other_u = s.query(User).filter_by(public_token="other-user").one()
        e = Evaluation(
            user_id=other_u.id, dataset_name="x.csv", status="completed",
            total_samples=1, successful=1, failed=0,
            avg_metrics={}, duration_seconds=1.0,
        )
        s.add(e)
        s.flush()
        eid = e.id

    r = client.get(
        f"/api/evaluate/runs/{eid}",
        headers={"x-user-token": "router-tok-user"},
    )
    assert r.status_code == 404


def test_get_run_admin_sees_all(client, user_id, monkeypatch):
    """admin 能看所有用户的 evaluation"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "admin-secret")
    with session_scope() as s:
        s.add(User(public_token="alice"))
        s.flush()
        alice = s.query(User).filter_by(public_token="alice").one()
        e = Evaluation(
            user_id=alice.id, dataset_name="alice.csv", status="completed",
            total_samples=1, successful=1, failed=0, avg_metrics={}, duration_seconds=1.0,
        )
        s.add(e)
        s.flush()
        eid = e.id

    r = client.get(
        f"/api/evaluate/runs/{eid}",
        headers={"x-admin-token": "admin-secret"},
    )
    assert r.status_code == 200


def test_cancel_returns_true_when_registered(client, user_id):
    """已注册的 evaluation → 取消成功 True"""
    from src.rag.eval import runner_registry
    import asyncio
    runner_registry.register_cancel_event(123, asyncio.Event())

    r = client.post(
        "/api/evaluate/runs/123/cancel",
        headers={"x-user-token": "router-tok-user"},
    )
    assert r.status_code == 200
    assert r.json() == {"cancelled": True}
    runner_registry.unregister_cancel_event(123)


def test_cancel_returns_false_when_not_registered(client, user_id):
    """未注册的 (e.g. 已完成) → 取消失败 False"""
    r = client.post(
        "/api/evaluate/runs/99999/cancel",
        headers={"x-user-token": "router-tok-user"},
    )
    assert r.status_code == 200
    assert r.json() == {"cancelled": False}


def test_template_endpoint_no_auth(client):
    """GET /template 不需要鉴权"""
    r = client.get("/api/evaluate/template")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    assert body.startswith("question,ground_truth")


def test_list_runs_admin_returns_all(client, user_id, monkeypatch):
    """admin 列表不按 user_id 过滤"""
    monkeypatch.setenv("RAG_ADMIN_TOKEN", "admin-secret")
    with session_scope() as s:
        s.add(User(public_token="bob"))
        s.flush()
        bob = s.query(User).filter_by(public_token="bob").one()
        s.add(Evaluation(
            user_id=bob.id, dataset_name="b.csv", status="completed",
            total_samples=1, successful=1, failed=0, avg_metrics={}, duration_seconds=1.0,
        ))

    r = client.get(
        "/api/evaluate/runs",
        headers={"x-admin-token": "admin-secret"},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
```

- [ ] **Step 2: 跑测试, 验证失败**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_router.py -v
```
预期: ImportError (router.py 还没建).

- [ ] **Step 3: 实现 `src/rag/eval/router.py`**

```python
"""/api/evaluate/* 路由: 评估批的 CRUD + 异步启动

- GET    /api/evaluate/runs          列表 (admin 看全部, 普通看自己)
- POST   /api/evaluate/runs          上传 CSV, 启动后台 task, 返回 {id, status}
- GET    /api/evaluate/runs/{id}     详情 + samples
- POST   /api/evaluate/runs/{id}/cancel  取消 running
- GET    /api/evaluate/template      下载 CSV 模板 (无需鉴权)

⚠️ admin 虚拟 user (id=0) 在 users 表里不存在, 所以 admin 列表用 is_admin 短路.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..generation.llm import OpenAILLM
from ..integrations.dify_client import DifyClient
from ..middleware.auth import CurrentUser, resolve_user
from ..storage.session import get_session, session_scope
from ..telemetry.ragas_evaluator import RAGASEvaluator
from .csv_parser import CSVParsingError, parse_eval_csv
from .models import Evaluation, EvaluationSample
from .runner import run_evaluation
from .runner_registry import request_cancel
from .template import build_eval_template_csv

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])

DATASETS_DIR = Path("data/eval_datasets")


# ---- Pydantic 响应 ----
class SampleOut(BaseModel):
    id: int
    index: int
    question: str
    ground_truth: str | None = None
    answer: str | None = None
    contexts: list[str] | None = None
    metrics: dict | None = None
    error: str | None = None
    duration_ms: int | None = None

    class Config:
        from_attributes = True


class EvaluationOut(BaseModel):
    id: int
    user_id: int
    dataset_name: str
    dataset_path: str | None = None
    status: str
    total_samples: int
    successful: int
    failed: int
    concurrency: int
    avg_metrics: dict | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    samples: list[SampleOut] = []

    class Config:
        from_attributes = True


def _eval_to_dict(e: Evaluation) -> dict:
    """Evaluation + samples → dict (供 router 返回)"""
    return {
        "id": e.id,
        "user_id": e.user_id,
        "dataset_name": e.dataset_name,
        "dataset_path": e.dataset_path,
        "status": e.status,
        "total_samples": e.total_samples,
        "successful": e.successful,
        "failed": e.failed,
        "concurrency": e.concurrency,
        "avg_metrics": e.avg_metrics,
        "duration_seconds": e.duration_seconds,
        "error_message": e.error_message,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "finished_at": e.finished_at.isoformat() if e.finished_at else None,
        "samples": [
            {
                "id": s.id, "index": s.index, "question": s.question,
                "ground_truth": s.ground_truth, "answer": s.answer,
                "contexts": s.contexts, "metrics": s.metrics,
                "error": s.error, "duration_ms": s.duration_ms,
            }
            for s in sorted(e.samples, key=lambda x: x.index)
        ],
    }


# ---- 端点 ----
@router.get("/template")
def get_template() -> PlainTextResponse:
    """下载 CSV 模板 (无鉴权, 模板里没数据)"""
    return PlainTextResponse(
        content=build_eval_template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": 'attachment; filename="eval_template.csv"'},
    )


@router.get("/runs")
def list_runs(
    current: CurrentUser = Depends(resolve_user),
    db: Session = Depends(get_session),
):
    """历史评估列表 (admin 看全部, 普通看自己)"""
    q = db.query(Evaluation)
    if not current.is_admin:
        q = q.filter(Evaluation.user_id == current.id)
    return [
        _eval_to_dict(e) for e in q.order_by(Evaluation.created_at.desc()).all()
    ]


@router.post("/runs")
async def upload_run(
    file: UploadFile = File(..., description="CSV 文件, ≤ 5MB, 1-200 行"),
    concurrency: int = Form(5, ge=1, le=10),
    current: CurrentUser = Depends(resolve_user),
):
    """上传 CSV, 启动后台 task, 返回 {id, status: 'pending'}"""
    content = await file.read()

    # 1. 解析 + 校验
    try:
        rows = parse_eval_csv(content, filename=file.filename or "upload.csv")
    except CSVParsingError as e:
        raise HTTPException(400, str(e)) from e

    # 2. 落盘 data/eval_datasets/{uuid}.csv (后续重跑可恢复)
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    dataset_path = DATASETS_DIR / f"{uuid.uuid4().hex}.csv"
    dataset_path.write_bytes(content)
    dataset_name = file.filename or "upload.csv"

    # 3. 落 Evaluation 行 (pending)
    with session_scope() as s:
        e = Evaluation(
            user_id=current.id,
            dataset_name=dataset_name,
            dataset_path=str(dataset_path),
            status="pending",
            total_samples=len(rows),
            concurrency=concurrency,
        )
        s.add(e)
        s.flush()
        evaluation_id = e.id

    # 4. 启动后台 task
    cancel_event = asyncio.Event()
    from . import runner_registry
    runner_registry.register_cancel_event(evaluation_id, cancel_event)

    async def _background() -> None:
        try:
            dify = DifyClient()
            judge_llm = OpenAILLM().llm
            evaluator = RAGASEvaluator(llm=judge_llm)
            await run_evaluation(
                user_id=current.id,
                dataset_name=dataset_name,
                dataset=rows,
                concurrency=concurrency,
                dify=dify,
                evaluator=evaluator,
                evaluation_id=evaluation_id,
                cancel_event=cancel_event,
            )
        except Exception as exc:
            with session_scope() as s:
                ee = s.get(Evaluation, evaluation_id)
                if ee.status not in ("completed", "cancelled", "failed"):
                    ee.status = "failed"
                    ee.error_message = f"runner crash: {exc}"
                    ee.finished_at = datetime.now(UTC)
        finally:
            runner_registry.unregister_cancel_event(evaluation_id)

    asyncio.create_task(_background())

    return {"id": evaluation_id, "status": "pending"}


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    current: CurrentUser = Depends(resolve_user),
    db: Session = Depends(get_session),
):
    """单次评估详情 + samples"""
    e = db.get(Evaluation, run_id)
    if e is None:
        raise HTTPException(404, f"evaluation {run_id} 不存在")
    if not current.is_admin and e.user_id != current.id:
        raise HTTPException(404, f"evaluation {run_id} 不存在")  # 避免泄露
    return _eval_to_dict(e)


@router.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: int,
    current: CurrentUser = Depends(resolve_user),
    db: Session = Depends(get_session),
):
    """取消正在跑的评估 (admin 可取消任何, 普通仅自己)"""
    e = db.get(Evaluation, run_id)
    if e is None or (not current.is_admin and e.user_id != current.id):
        raise HTTPException(404, f"evaluation {run_id} 不存在")
    cancelled = request_cancel(run_id)
    return {"cancelled": cancelled}
```

- [ ] **Step 4: 跑测试, 验证通过**

```bash
uv run --no-sync python -m pytest tests/rag/eval/test_router.py -v
```
预期: 12 passed.

- [ ] **Step 5: 把 router 挂到主 FastAPI app**

修改 `src/rag/api/routes.py` 顶部加 import + 末尾 include:

```python
# 在文件顶部 import 区加:
from ..eval.router import router as eval_router

# 在文件末尾追加 (跟现有 router 并列):
eval_router_v1 = eval_router  # 名字占位, 实际走原 prefix
```

不对, 改更干净的方式 — 在 `src/rag/api/__init__.py` 的 `__all__` 加 `eval_router`. 但 `eval_router` 已经在自己模块暴露, 业务代码只 `from src.rag.eval.router import router`. 真正的 main.py / app.py 怎么挂是后续问题, 本 task 不动.

- [ ] **Step 6: Commit**

```bash
git add src/rag/eval/router.py tests/rag/eval/test_router.py
git commit -m "feat(eval): FastAPI 路由 (列表/上传/详情/取消/模板, admin + client 鉴权)"
```

---

### Task 7: `web/lib/evaluate/types.ts` - `EvaluationRun` + `EvaluationStatus` 枚举

**Files:**
- Modify: `web/lib/evaluate/types.ts`

- [ ] **Step 1: 在文件顶部加 enum, 末尾加 `EvaluationRun` interface**

`web/lib/evaluate/types.ts` 替换为:

```typescript
// RAGAS 评估类型定义 (2026-06-09)
// 跟 src/rag/eval/router.py 响应结构 1:1 对齐

export const EvaluationStatus = {
  Pending: "pending",
  Running: "running",
  Completed: "completed",
  Failed: "failed",
  Cancelled: "cancelled",
} as const;
export type EvaluationStatus = (typeof EvaluationStatus)[keyof typeof EvaluationStatus];

export interface ReportMetrics {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
  context_recall: number | null;
}

export interface SampleResult {
  index: number;
  question: string;
  ground_truth: string;
  answer: string;
  contexts_count?: number;
  metrics: ReportMetrics | null;
  error?: string;
}

export interface EvalReport {
  dataset_path: string;
  total_samples: number;
  successful: number;
  failed: number;
  concurrency: number;
  duration_seconds: number;
  avg_metrics: ReportMetrics;
  per_sample: SampleResult[];
}

// ---- 新增: 异步评估批 ----
export interface EvaluationSample {
  id: number;
  index: number;
  question: string;
  ground_truth: string | null;
  answer: string | null;
  contexts: string[] | null;
  metrics: ReportMetrics | null;
  error: string | null;
  duration_ms: number | null;
}

export interface EvaluationRun {
  id: number;
  user_id: number;
  dataset_name: string;
  dataset_path: string | null;
  status: EvaluationStatus;
  total_samples: number;
  successful: number;
  failed: number;
  concurrency: number;
  avg_metrics: ReportMetrics | null;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
  finished_at: string | null;
  samples: EvaluationSample[];
}

// 列表行简版 (不嵌 samples, 减 payload)
export type EvaluationRunSummary = Omit<EvaluationRun, "samples">;
```

- [ ] **Step 2: 跑 web typecheck 验证**

```bash
cd web && npx tsc --noEmit
```
预期: 0 error.

- [ ] **Step 3: Commit**

```bash
git add web/lib/evaluate/types.ts
git commit -m "feat(web): add EvaluationRun + EvaluationStatus enum to types"
```

---

### Task 8: BFF - `web/app/api/evaluate/runs/route.ts` (GET 列表 / POST 上传)

**Files:**
- Create: `web/app/api/evaluate/runs/route.ts`
- Test: 走前端单测 (Task 13 统一做)

- [ ] **Step 1: 创建文件**

`web/app/api/evaluate/runs/route.ts`:
```typescript
// 评估批 BFF: 列表 / 上传
// - GET  → 透传到 FastAPI /api/evaluate/runs
// - POST → 透传 multipart (file + concurrency) 到 FastAPI
import { NextRequest, NextResponse } from "next/server";
import { getUserToken, getAdminToken } from "@/lib/evaluate/headers";

export const dynamic = "force-dynamic";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://localhost:8000";

export async function GET(_req: NextRequest) {
  const headers: Record<string, string> = {
    "x-user-token": getUserToken(),
  };
  // 调试用: localStorage 配了 admin token 就用
  const admin = getAdminToken();
  if (admin) headers["x-admin-token"] = admin;
  const resp = await fetch(`${BACKEND}/api/evaluate/runs`, {
    headers,
    cache: "no-store",
  });
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" },
  });
}

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const file = form.get("file");
  const concurrency = form.get("concurrency") ?? "5";
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "缺少 file 字段" }, { status: 400 });
  }

  // 构造 multipart 给 FastAPI
  const fd = new FormData();
  fd.append("file", file);
  fd.append("concurrency", String(concurrency));

  const headers: Record<string, string> = {
    "x-user-token": getUserToken(),
  };
  const admin = getAdminToken();
  if (admin) headers["x-admin-token"] = admin;

  const resp = await fetch(`${BACKEND}/api/evaluate/runs`, {
    method: "POST",
    headers,
    body: fd,
  });
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" },
  });
}
```

- [ ] **Step 2: 创建 `web/lib/evaluate/headers.ts`**

`web/lib/evaluate/headers.ts`:
```typescript
// 客户端读取 localStorage 里的 token (admin + 普通 user)
// 浏览器侧: 必须在 client component 里调, 顶层 import 会触发 SSR 报错
"use client";

const ADMIN_KEY = "rag_admin_token";
const USER_KEY = "rag_user_token";

export function getUserToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(USER_KEY) ?? "";
}

export function getAdminToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ADMIN_KEY) ?? "";
}

export function setUserToken(tok: string): void {
  if (typeof window === "undefined") return;
  if (tok) window.localStorage.setItem(USER_KEY, tok);
  else window.localStorage.removeItem(USER_KEY);
}

export function setAdminToken(tok: string): void {
  if (typeof window === "undefined") return;
  if (tok) window.localStorage.setItem(ADMIN_KEY, tok);
  else window.localStorage.removeItem(ADMIN_KEY);
}
```

- [ ] **Step 3: 跑 web typecheck 验证**

```bash
cd web && npx tsc --noEmit
```
预期: 0 error.

- [ ] **Step 4: Commit**

```bash
git add web/app/api/evaluate/runs/route.ts web/lib/evaluate/headers.ts
git commit -m "feat(web): BFF /api/evaluate/runs (GET 列表 + POST 上传) + token headers 工具"
```

---

### Task 9: BFF - `web/app/api/evaluate/runs/[id]/route.ts` + `cancel/route.ts`

**Files:**
- Create: `web/app/api/evaluate/runs/[id]/route.ts`
- Create: `web/app/api/evaluate/runs/[id]/cancel/route.ts`

- [ ] **Step 1: 创建详情 route**

`web/app/api/evaluate/runs/[id]/route.ts`:
```typescript
// 评估批详情 BFF: 透传 GET /api/evaluate/runs/{id} 给 FastAPI
import { NextRequest, NextResponse } from "next/server";
import { getUserToken, getAdminToken } from "@/lib/evaluate/headers";

export const dynamic = "force-dynamic";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://localhost:8000";

export async function GET(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const headers: Record<string, string> = { "x-user-token": getUserToken() };
  const admin = getAdminToken();
  if (admin) headers["x-admin-token"] = admin;

  const resp = await fetch(`${BACKEND}/api/evaluate/runs/${id}`, {
    headers,
    cache: "no-store",
  });
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" },
  });
}
```

- [ ] **Step 2: 创建取消 route**

`web/app/api/evaluate/runs/[id]/cancel/route.ts`:
```typescript
// 评估批取消 BFF
import { NextRequest, NextResponse } from "next/server";
import { getUserToken, getAdminToken } from "@/lib/evaluate/headers";

export const dynamic = "force-dynamic";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://localhost:8000";

export async function POST(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const headers: Record<string, string> = { "x-user-token": getUserToken() };
  const admin = getAdminToken();
  if (admin) headers["x-admin-token"] = admin;

  const resp = await fetch(`${BACKEND}/api/evaluate/runs/${id}/cancel`, {
    method: "POST",
    headers,
  });
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" },
  });
}
```

- [ ] **Step 3: typecheck**

```bash
cd web && npx tsc --noEmit
```
预期: 0 error.

- [ ] **Step 4: Commit**

```bash
git add web/app/api/evaluate/runs/\[id\]/
git commit -m "feat(web): BFF 详情 + 取消路由 (透传到 FastAPI)"
```

---

### Task 10: BFF - `web/app/api/evaluate/template/route.ts`

**Files:**
- Create: `web/app/api/evaluate/template/route.ts`

- [ ] **Step 1: 创建 route**

`web/app/api/evaluate/template/route.ts`:
```typescript
// CSV 模板下载 BFF: 透传 GET /api/evaluate/template, 强制下载头
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND = process.env.RAG_BACKEND_URL ?? "http://localhost:8000";

export async function GET() {
  const resp = await fetch(`${BACKEND}/api/evaluate/template`);
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": 'attachment; filename="eval_template.csv"',
    },
  });
}
```

- [ ] **Step 2: typecheck**

```bash
cd web && npx tsc --noEmit
```
预期: 0 error.

- [ ] **Step 3: Commit**

```bash
git add web/app/api/evaluate/template/route.ts
git commit -m "feat(web): BFF 模板下载 (含 content-disposition 触发浏览器下载)"
```

---

### Task 11: `StatusBadge.tsx` + `EvalListRow.tsx` 组件

**Files:**
- Create: `web/components/evaluate/StatusBadge.tsx`
- Create: `web/components/evaluate/EvalListRow.tsx`

- [ ] **Step 1: 创建 `StatusBadge.tsx`**

`web/components/evaluate/StatusBadge.tsx`:
```tsx
// 评估状态徽章: 5 种状态不同配色 + running 脉动
"use client";
import { EvaluationStatus } from "@/lib/evaluate/types";

interface Props {
  status: EvaluationStatus;
  className?: string;
}

const STYLE: Record<EvaluationStatus, string> = {
  pending: "bg-muted text-muted-foreground border-border/40",
  running: "bg-cyan-50 text-cyan-700 border-cyan-300/40 animate-pulse",
  completed: "bg-moss/10 text-moss border-moss/30",
  failed: "bg-clay/10 text-clay border-clay/30",
  cancelled: "bg-ink/5 text-muted-foreground border-border/40",
};

const LABEL: Record<EvaluationStatus, string> = {
  pending: "排队",
  running: "跑中",
  completed: "完成",
  failed: "失败",
  cancelled: "已取消",
};

export function StatusBadge({ status, className = "" }: Props) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STYLE[status]} ${className}`}
    >
      {LABEL[status]}
    </span>
  );
}
```

- [ ] **Step 2: 创建 `EvalListRow.tsx`**

`web/components/evaluate/EvalListRow.tsx`:
```tsx
// 评估列表行: 点击跳详情
"use client";
import Link from "next/link";
import { StatusBadge } from "./StatusBadge";
import type { EvaluationRunSummary } from "@/lib/evaluate/types";

interface Props {
  run: EvaluationRunSummary;
  index: number;
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${m}-${day} ${hh}:${mm}`;
}

export function EvalListRow({ run, index }: Props) {
  return (
    <Link
      href={`/evaluate/${run.id}`}
      className="grid grid-cols-12 items-center gap-3 rounded-lg border border-border/40 bg-card px-4 py-3 transition-colors hover:bg-muted/30"
    >
      <span className="num col-span-1 text-sm text-muted-foreground">
        {String(index + 1).padStart(2, "0")}
      </span>
      <span className="col-span-5 truncate text-sm font-medium">
        {run.dataset_name}
      </span>
      <span className="col-span-2">
        <StatusBadge status={run.status} />
      </span>
      <span className="num col-span-2 text-sm text-muted-foreground">
        {run.status === "running"
          ? `${run.successful + run.failed}/${run.total_samples}`
          : `${run.total_samples} 题`}
      </span>
      <span className="num col-span-1 text-sm text-muted-foreground">
        {fmtDate(run.created_at)}
      </span>
      <span className="col-span-1 text-right text-muted-foreground">→</span>
    </Link>
  );
}
```

- [ ] **Step 3: typecheck**

```bash
cd web && npx tsc --noEmit
```
预期: 0 error.

- [ ] **Step 4: Commit**

```bash
git add web/components/evaluate/StatusBadge.tsx web/components/evaluate/EvalListRow.tsx
git commit -m "feat(web): StatusBadge + EvalListRow 组件"
```

---

### Task 12: 3 个页面 (列表/上传/详情) + 删旧 `web/app/evaluate/page.tsx`

**Files:**
- Modify: `web/app/evaluate/page.tsx` (改成列表)
- Create: `web/app/evaluate/new/page.tsx`
- Create: `web/app/evaluate/[id]/page.tsx`

- [ ] **Step 1: 重写列表页**

`web/app/evaluate/page.tsx` 完整替换为:
```tsx
// 评估历史列表 (2026-06-09)
"use client";
import Link from "next/link";
import useSWR from "swr";
import { EvalListRow } from "@/components/evaluate/EvalListRow";
import { Reveal, Stagger, StaggerItem } from "@/components/ui/animated";
import type { EvaluationRunSummary } from "@/lib/evaluate/types";

export default function EvaluateListPage() {
  const { data, isLoading, error } = useSWR<EvaluationRunSummary[]>(
    "/api/evaluate/runs",
    { refreshInterval: 0 }, // 列表不轮询
  );

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <Stagger className="space-y-2" delay={0.08}>
        <StaggerItem>
          <div className="flex items-center gap-3">
            <span className="eyebrow">质量评估</span>
            <span className="h-px flex-1 bg-border" />
          </div>
        </StaggerItem>
        <StaggerItem>
          <h1 className="display text-4xl tracking-tight md:text-5xl">评估历史</h1>
        </StaggerItem>
        <StaggerItem>
          <p className="text-muted-foreground">
            上传 CSV, 让大模型作答, 自动评分
          </p>
        </StaggerItem>
      </Stagger>

      <Reveal delay={0.2}>
        <div className="flex items-center gap-3">
          <Link
            href="/evaluate/new"
            className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90"
          >
            + 新建评估
          </Link>
          <a
            href="/api/evaluate/template"
            download="eval_template.csv"
            className="rounded-md border border-border/60 px-4 py-2 text-sm font-medium transition-colors hover:bg-muted/30"
          >
            ↓ 下载模板
          </a>
        </div>
      </Reveal>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          加载失败: {String(error)}
        </div>
      )}

      {isLoading && <div className="text-sm text-muted-foreground">加载中…</div>}

      {data && data.length === 0 && (
        <Reveal delay={0.25}>
          <div className="rounded-lg border border-dashed border-border/60 bg-card/40 p-12 text-center space-y-4">
            <p className="display text-2xl">还没有评估</p>
            <p className="text-sm text-muted-foreground">
              上传一个问答 CSV, 让大模型自动跑评估
            </p>
            <Link
              href="/evaluate/new"
              className="inline-block rounded-md bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-90"
            >
              + 新建评估
            </Link>
          </div>
        </Reveal>
      )}

      {data && data.length > 0 && (
        <Reveal delay={0.3}>
          <div className="space-y-2">
            <div className="grid grid-cols-12 gap-3 px-4 text-xs text-muted-foreground">
              <span className="col-span-1 eyebrow">#</span>
              <span className="col-span-5 eyebrow">名称</span>
              <span className="col-span-2 eyebrow">状态</span>
              <span className="col-span-2 eyebrow">题数</span>
              <span className="col-span-1 eyebrow">时间</span>
              <span className="col-span-1" />
            </div>
            {data.map((r, i) => (
              <EvalListRow key={r.id} run={r} index={i} />
            ))}
          </div>
        </Reveal>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建新建页**

`web/app/evaluate/new/page.tsx`:
```tsx
// 新建评估 (上传 CSV) (2026-06-09)
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Reveal, Stagger, StaggerItem } from "@/components/ui/animated";
import Papa from "papaparse";

type ParsedCsv = { rows: { question: string; ground_truth: string | null }[]; total: number };

function parseClientSide(file: File): Promise<ParsedCsv> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: true,
      complete: (res) => {
        if (!res.meta.fields?.includes("question")) {
          reject(new Error("缺 'question' 列, 表头必须是: question,ground_truth"));
          return;
        }
        const rows = res.data
          .map((r) => ({
            question: (r.question ?? "").trim(),
            ground_truth: (r.ground_truth ?? "").trim() || null,
          }))
          .filter((r) => r.question);
        if (rows.length === 0) {
          reject(new Error("至少 1 行有效数据"));
          return;
        }
        if (rows.length > 200) {
          reject(new Error(`题数 ${rows.length} 超过上限 200`));
          return;
        }
        resolve({ rows, total: rows.length });
      },
      error: (err) => reject(new Error(`CSV 解析失败: ${err.message}`)),
    });
  });
}

export default function NewEvalPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [parsed, setParsed] = useState<ParsedCsv | null>(null);
  const [parseErr, setParseErr] = useState<string | null>(null);
  const [concurrency, setConcurrency] = useState(5);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  async function onPick(f: File) {
    setParseErr(null);
    setParsed(null);
    if (f.size > 5 * 1024 * 1024) {
      setParseErr("文件超过 5MB");
      return;
    }
    setFile(f);
    try {
      const p = await parseClientSide(f);
      setParsed(p);
    } catch (e) {
      setParseErr(String((e as Error).message));
    }
  }

  async function onSubmit() {
    if (!file || !parsed) return;
    setUploading(true);
    setUploadErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("concurrency", String(concurrency));
      const resp = await fetch("/api/evaluate/runs", { method: "POST", body: fd });
      const body = await resp.json();
      if (!resp.ok) throw new Error(body.detail ?? "上传失败");
      router.push(`/evaluate/${body.id}`);
    } catch (e) {
      setUploadErr(String((e as Error).message));
      setUploading(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <Stagger className="space-y-2" delay={0.08}>
        <StaggerItem>
          <Link href="/evaluate" className="text-sm text-muted-foreground hover:text-foreground">
            ← 返回
          </Link>
        </StaggerItem>
        <StaggerItem>
          <div className="flex items-center gap-3">
            <span className="eyebrow">新建评估</span>
            <span className="h-px flex-1 bg-border" />
          </div>
        </StaggerItem>
        <StaggerItem>
          <h1 className="display text-4xl tracking-tight md:text-5xl">上传问答 CSV</h1>
        </StaggerItem>
      </Stagger>

      <Reveal delay={0.2}>
        <label className="block rounded-lg border-2 border-dashed border-border/60 bg-card/40 p-8 text-center cursor-pointer transition-colors hover:bg-muted/20">
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onPick(e.target.files[0])}
          />
          <p className="text-sm">拖拽 CSV 到这里 / 点击选择</p>
          <p className="mt-1 text-xs text-muted-foreground">
            仅支持 .csv, 最多 5MB, 1-200 行
          </p>
          <a
            href="/api/evaluate/template"
            download="eval_template.csv"
            className="mt-3 inline-block text-xs text-muted-foreground underline hover:text-foreground"
            onClick={(e) => e.stopPropagation()}
          >
            ↓ 没模板? 下载
          </a>
        </label>
      </Reveal>

      {parseErr && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {parseErr}
        </div>
      )}

      {parsed && file && (
        <Reveal delay={0.3}>
          <div className="space-y-4">
            <div className="text-sm">
              文件名: <span className="num">{file.name}</span> ({parsed.total} 行)
            </div>
            <div className="rounded-lg border border-border/40 bg-card overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs text-muted-foreground">
                  <tr>
                    <th className="eyebrow px-3 py-2 text-left">question</th>
                    <th className="eyebrow px-3 py-2 text-left">ground_truth</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.rows.slice(0, 3).map((r, i) => (
                    <tr key={i} className="border-t border-border/30">
                      <td className="max-w-md truncate px-3 py-2">{r.question}</td>
                      <td className="max-w-md truncate px-3 py-2 text-muted-foreground">
                        {r.ground_truth ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted-foreground">并发数:</span>
              <button
                type="button"
                onClick={() => setConcurrency(Math.max(1, concurrency - 1))}
                className="rounded-md border border-border/60 px-3 py-1 hover:bg-muted/30"
              >
                −
              </button>
              <span className="num w-8 text-center">{concurrency}</span>
              <button
                type="button"
                onClick={() => setConcurrency(Math.min(10, concurrency + 1))}
                className="rounded-md border border-border/60 px-3 py-1 hover:bg-muted/30"
              >
                +
              </button>
            </div>
          </div>
        </Reveal>
      )}

      {uploadErr && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {uploadErr}
        </div>
      )}

      <Reveal delay={0.4}>
        <div className="flex items-center justify-end gap-3">
          <Link
            href="/evaluate"
            className="rounded-md border border-border/60 px-4 py-2 text-sm font-medium transition-colors hover:bg-muted/30"
          >
            取消
          </Link>
          <button
            type="button"
            onClick={onSubmit}
            disabled={!parsed || uploading}
            className="rounded-md bg-foreground px-5 py-2 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {uploading ? "上传中…" : "开始评估 →"}
          </button>
        </div>
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 3: 创建详情页 (改造原 `page.tsx`)**

`web/app/evaluate/[id]/page.tsx`:
```tsx
// 单次评估详情 (2026-06-09) - 改造自原 /evaluate/page.tsx
"use client";
import Link from "next/link";
import { use } from "react";
import useSWR from "swr";
import { StatCard } from "@/components/knowledge/StatCard";
import { MetricBar } from "@/components/evaluate/MetricBar";
import { SampleTable } from "@/components/evaluate/SampleTable";
import { StatusBadge } from "@/components/evaluate/StatusBadge";
import { Reveal, Stagger, StaggerItem } from "@/components/ui/animated";
import type { EvaluationRun, EvaluationStatus } from "@/lib/evaluate/types";

const TERMINAL: EvaluationStatus[] = ["completed", "failed", "cancelled"];

export default function EvaluationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading, error, mutate } = useSWR<EvaluationRun>(
    `/api/evaluate/runs/${id}`,
    {
      refreshInterval: (latest) => {
        if (!latest) return 2000;
        return TERMINAL.includes(latest.status) ? 0 : 2000;
      },
    },
  );

  async function onCancel() {
    if (!data) return;
    if (!confirm("确认取消这次评估? 已跑的题会保留")) return;
    await fetch(`/api/evaluate/runs/${data.id}/cancel`, { method: "POST" });
    mutate();
  }

  return (
    <div className="h-full overflow-y-auto space-y-8">
      <Stagger className="space-y-2" delay={0.08}>
        <StaggerItem>
          <Link href="/evaluate" className="text-sm text-muted-foreground hover:text-foreground">
            ← 返回列表
          </Link>
        </StaggerItem>
        <StaggerItem>
          <div className="flex items-center gap-3">
            <span className="eyebrow">评估详情</span>
            <span className="h-px flex-1 bg-border" />
            {data && <StatusBadge status={data.status} />}
            {data && data.status === "running" && (
              <button
                type="button"
                onClick={onCancel}
                className="rounded-md border border-destructive/40 px-3 py-1 text-xs text-destructive transition-colors hover:bg-destructive/5"
              >
                取消
              </button>
            )}
          </div>
        </StaggerItem>
        <StaggerItem>
          <h1 className="display text-3xl tracking-tight md:text-4xl">
            {data?.dataset_name ?? `评估 #${id}`}
          </h1>
        </StaggerItem>
      </Stagger>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          加载失败: {String(error)}
        </div>
      )}

      {isLoading && <div className="text-sm text-muted-foreground">加载中…</div>}

      {data && data.status !== "completed" && data.status !== "failed" && data.status !== "cancelled" && (
        <Reveal delay={0.1}>
          <div className="rounded-lg border border-cyan-300/30 bg-cyan-50/30 p-4 text-sm text-cyan-700">
            评估进行中, 每 2 秒自动刷新…
            {data.successful + data.failed} / {data.total_samples} 已完成
          </div>
        </Reveal>
      )}

      {data && data.status === "failed" && data.error_message && (
        <div className="rounded-lg border border-clay/30 bg-clay/5 p-4 text-sm text-clay">
          错误: {data.error_message}
        </div>
      )}

      {data && data.avg_metrics && (
        <>
          <Reveal delay={0.15}>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="总样本" value={data.total_samples} accent="indigo" index={0} />
              <StatCard label="成功" value={data.successful} accent="moss" index={1} />
              <StatCard label="失败" value={data.failed} accent="clay" index={2} />
              <StatCard
                label="耗时"
                value={data.duration_seconds ? `${data.duration_seconds.toFixed(1)}s` : "—"}
                accent="ink"
                index={3}
              />
            </div>
          </Reveal>

          <Reveal delay={0.25}>
            <div className="rounded-lg border border-border/40 bg-card p-5 space-y-4">
              <h3 className="text-sm font-medium text-muted-foreground">平均指标</h3>
              <MetricBar label="忠实度 (Faithfulness)" value={data.avg_metrics.faithfulness} />
              <MetricBar label="答案相关性 (Answer Relevancy)" value={data.avg_metrics.answer_relevancy} />
              <MetricBar label="上下文精度 (Context Precision)" value={data.avg_metrics.context_precision} />
              <MetricBar label="上下文召回 (Context Recall)" value={data.avg_metrics.context_recall} />
            </div>
          </Reveal>

          {data.samples.length > 0 && (
            <Reveal delay={0.35}>
              <div>
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">
                  逐条结果 ({data.samples.length} 条)
                </h3>
                <SampleTable
                  samples={data.samples.map((s) => ({
                    index: s.index,
                    question: s.question,
                    ground_truth: s.ground_truth ?? "",
                    answer: s.answer ?? "",
                    metrics: s.metrics,
                    error: s.error ?? undefined,
                  }))}
                />
              </div>
            </Reveal>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 删旧 `web/app/evaluate/page.test.tsx` (如果存在且依赖旧结构)**

```bash
ls web/app/evaluate/page.test.tsx 2>/dev/null && rm web/app/evaluate/page.test.tsx
```

- [ ] **Step 5: typecheck + lint**

```bash
cd web && npx tsc --noEmit
cd web && npm run lint 2>&1 | tail -30
```
预期: tsc 0 error. lint 无 error (可有 warn).

- [ ] **Step 6: Commit**

```bash
git add web/app/evaluate/
git commit -m "feat(web): 评估页 3 路由 (列表/上传/详情) + 状态徽章 + SWR 轮询"
```

---

### Task 13: E2E `04-evaluate.spec.ts` (Playwright)

**Files:**
- Create: `web/e2e/04-evaluate.spec.ts`

- [ ] **Step 1: 写 E2E**

`web/e2e/04-evaluate.spec.ts`:
```typescript
// 评估页 E2E: 走通 列表 → 新建 → 上传 → 详情 → 取消 全链路
//
// ⚠️ 真实 Dify 评估需要 OPENAI_API_KEY + DIFY_API_KEY + 真实 PDF 知识库, CI 跑不了.
//    本 spec 用 mock 后端: 提前在 data/eval_datasets/ 放一个 2 题的 csv + 走脚本种子一个
//    状态为 completed 的 evaluation 行 (user_id=1).
import { test, expect } from "@playwright/test";
import path from "node:path";

const ADMIN_HEADER_KEY = "x-admin-token";

test.describe("评估页 (3 路由)", () => {
  test.beforeEach(async ({ page, context }) => {
    // 注入 admin token (调试模式) + user token
    await context.addInitScript(() => {
      window.localStorage.setItem("rag_admin_token", "e2e-admin-secret");
      window.localStorage.setItem("rag_user_token", "e2e-user-tok");
    });
  });

  test("列表页 mount 不报错", async ({ page }) => {
    await page.goto("/evaluate");
    await expect(page.getByText("评估历史")).toBeVisible();
    await expect(page.getByText("+ 新建评估")).toBeVisible();
  });

  test("下载模板返回 CSV 内容", async ({ page }) => {
    const resp = await page.request.get("/api/evaluate/template");
    expect(resp.status()).toBe(200);
    const body = await resp.text();
    expect(body).toContain("question,ground_truth");
  });

  test("新建页 - 上传合法 CSV 后显示预览", async ({ page }) => {
    await page.goto("/evaluate/new");
    const csv = Buffer.from("question,ground_truth\nQ1,A1\nQ2,A2\n");
    await page.setInputFiles('input[type="file"]', {
      name: "test.csv",
      mimeType: "text/csv",
      buffer: csv,
    });
    await expect(page.getByText("Q1")).toBeVisible();
    await expect(page.getByText("Q2")).toBeVisible();
    await expect(page.getByText("(2 行)")).toBeVisible();
  });

  test("新建页 - 上传非法 CSV (缺 question 列) 报错", async ({ page }) => {
    await page.goto("/evaluate/new");
    const csv = Buffer.from("prompt,answer\nQ1,A1\n");
    await page.setInputFiles('input[type="file"]', {
      name: "bad.csv",
      mimeType: "text/csv",
      buffer: csv,
    });
    await expect(page.getByText("缺 'question' 列")).toBeVisible();
  });

  test("详情页 - 404 兼容", async ({ page }) => {
    const resp = await page.request.get("/api/evaluate/runs/999999", {
      headers: { [ADMIN_HEADER_KEY]: "e2e-admin-secret" },
    });
    expect([403, 404]).toContain(resp.status());
  });
});
```

- [ ] **Step 2: 跑 E2E (用 mock 后端)**

需要在后端服务跑起来 + admin token 配置的情况下. 写一个测试 helper, e2e 跑前在 `.env.test` 配:
```bash
RAG_ADMIN_TOKEN=e2e-admin-secret
```

`web/playwright.config.ts` 已有 webServer 配 backend 的话, 跑:
```bash
cd web && npm run test:e2e -- 04-evaluate.spec.ts
```
预期: 5 passed (列表/模板/新建合法/新建非法/详情 404).

- [ ] **Step 3: Commit**

```bash
git add web/e2e/04-evaluate.spec.ts
git commit -m "test(web): 评估页 E2E (3 路由 + 模板下载 + CSV 校验)"
```

---

### Task 14: 启动时 `running` → `failed` 恢复 + `.env.example` + README

**Files:**
- Create: `src/rag/eval/__init__.py` (暴露 recover_orphaned_running)
- Modify: `src/rag/__init__.py` 或 `src/rag/main.py` (启动时调一次, 视实际 app 启动文件)
- Create: `.env.example` (含 RAG_ADMIN_TOKEN 行)
- Create: `src/rag/eval/README.md`

- [ ] **Step 1: `src/rag/eval/__init__.py` 加 export**

```python
"""评估子系统: 异步评估 + 历史查询 + admin 调试"""
from .runner_registry import recover_orphaned_running

__all__ = ["recover_orphaned_running"]
```

- [ ] **Step 2: 找启动入口并接入恢复**

```bash
grep -rn "FastAPI\|uvicorn" src/rag/main.py 2>/dev/null | head -10
ls src/rag/main.py 2>/dev/null
```

如果 main.py 存在, 在 uvicorn 启动前加:
```python
from .eval import recover_orphaned_running
n = recover_orphaned_running()
if n:
    print(f"[startup] 修复了 {n} 条 zombie running 评估")
```

如果不存在, 在 storage `__init__.py` 暴露, 等真正的 app 启动文件出现再调 (本 task 留 hook).

- [ ] **Step 3: `.env.example` 加 admin token 行**

在仓库根 (或 docs/) 创建 `.env.example`:
```bash
# 调试用 admin token (留空 = 关闭, 生产务必留空!)
# 多个开发者共享同一个值, 生成方式: python -c "import secrets; print(secrets.token_hex(16))"
RAG_ADMIN_TOKEN=

# 现有 storage / Dify / RAGAS env 保持不动
RAG_DB_URL=sqlite:///data/app.db
RAG_AUTO_CREATE_SCHEMA=1
DIFY_API_KEY=
DIFY_BASE_URL=
DIFY_USER_ID=
OPENAI_API_KEY=
```

- [ ] **Step 4: 写 `src/rag/eval/README.md`**

```markdown
# 评估子系统 (src/rag/eval)

异步跑 Dify + RAGAS, 落 SQLite `evaluations` + `evaluation_samples` 表.

## 公开 API

- `GET  /api/evaluate/runs`           列表 (admin 看全部, 普通看自己)
- `POST /api/evaluate/runs`           上传 CSV, 启动后台 task
- `GET  /api/evaluate/runs/{id}`      详情 + samples
- `POST /api/evaluate/runs/{id}/cancel` 取消 running
- `GET  /api/evaluate/template`       下载 CSV 模板

## 状态机

`pending` → `running` → (`completed` | `failed` | `cancelled`)

取消机制: 进程内 `dict[evaluation_id, asyncio.Event]`, 多 worker 不支持 (YAGNI).

## Admin 调试

后端 `.env` 配 `RAG_ADMIN_TOKEN=xxx` (生成: `python -c "import secrets; print(secrets.token_hex(16))"`),
浏览器 devtools 改 header `x-admin-token: xxx` 就能看所有用户数据.

⚠️ **生产部署务必留空**, 见 `docs/superpowers/specs/2026-06-09-evaluate-page-redesign-design.md`.

## 重启恢复

启动时调 `recover_orphaned_running()`, 把 status='running' 的行标 failed + 写 "服务重启中断".
```

- [ ] **Step 5: 跑全量 pytest + tsc + lint 验证**

```bash
# 后端
uv run --no-sync python -m pytest tests/rag/eval/ tests/rag/middleware/ -v
# 前端
cd web && npx tsc --noEmit
cd web && npm run lint 2>&1 | tail -10
```
预期: 后端所有测试通过 (csv_parser 9 + template 4 + runner 5 + registry 4 + router 12 = 34), 前端 tsc/lint 0 error.

- [ ] **Step 6: Commit**

```bash
git add src/rag/eval/__init__.py src/rag/eval/README.md .env.example
git commit -m "docs(eval): README + .env.example + 启动恢复 hook"
```

---

## Self-Review Checklist

### 1. Spec coverage

| Spec 需求 | 覆盖 Task |
|---|---|
| 上传 CSV | Task 6 (POST /runs) + Task 12 (新建页) |
| 模板下载 | Task 3 + Task 6 (GET /template) + Task 10 (BFF) + Task 12 (列表按钮) |
| 历史列表 | Task 6 (GET /runs) + Task 8 (BFF) + Task 11 (EvalListRow) + Task 12 (列表页) |
| SQLite 存储 | storage spec 已有 + Task 4 落库逻辑 |
| 客户端 token 在 localStorage | Task 8 (`web/lib/evaluate/headers.ts`) |
| 异步跑评估 (pending → running → completed) | Task 4 (runner.py) + Task 12 (详情页轮询) |
| 取消支持 | Task 5 (event dict) + Task 6 (cancel endpoint) + Task 12 (取消按钮) |
| Admin token 调试 | Task 1 (resolve_user) + Task 6 (router admin 分支) + Task 14 (README/env example) |
| 重启恢复 | Task 5 (recover_orphaned_running) + Task 14 (启动 hook) |
| Dify + RAGAS 整合 | Task 4 (复用 scripts/batch_rag_eval.py 逻辑) |
| 并发限速 (sem 在 Dify + RAGAS 外面) | Task 4 (`_evaluate_one` 的 `async with sem` 包住两步) |
| 4 指标 + 逐条 | 沿用现有 `MetricBar` / `SampleTable` 组件, 复用 |
| E2E | Task 13 |

✅ 全部 spec 需求覆盖.

### 2. Placeholder scan

- ❌ 没出现 "TBD" / "TODO" / "实现细节见后续" / "类似 Task N".
- ❌ 没 "Add appropriate error handling" 模糊描述, 错误处理都在 `CSVParsingError` / `HTTPException` 显式写出.
- ❌ 没"写测试"无代码, 每个 Task 都有具体测试函数名 + 代码块.

### 3. Type consistency

| 名字 | 定义处 | 使用处 |
|---|---|---|
| `CurrentUser` | Task 1 (`src/rag/middleware/auth.py`) | Task 6 (`router.py` Depends) ✅ |
| `EvaluationStatus` enum | Task 7 (`web/lib/evaluate/types.ts`) | Task 11 (`StatusBadge.tsx`) + Task 12 (详情页 SWR) ✅ |
| `EvaluationRun` | Task 7 | Task 12 (详情页) ✅ |
| `parse_eval_csv` | Task 2 | Task 6 (upload router) ✅ |
| `run_evaluation` | Task 4 | Task 6 (background) ✅ |
| `request_cancel` / `register_cancel_event` | Task 5 | Task 6 (cancel router) ✅ |
| `build_eval_template_csv` | Task 3 | Task 6 (GET /template) ✅ |
| `recover_orphaned_running` | Task 5 | Task 14 (启动 hook) ✅ |
| `getUserToken` / `getAdminToken` | Task 8 (`web/lib/evaluate/headers.ts`) | Task 8/9/10 (BFF routes) ✅ |
| `EvalListRow` | Task 11 | Task 12 (列表页) ✅ |
| `StatusBadge` | Task 11 | Task 12 (列表/详情) ✅ |

✅ 名字一致.

### 4. Risk check

| 风险 | 缓解已写在 plan |
|---|---|
| Dify 超时拖垮整批 | Task 4 默认 60s timeout (沿用 DifyClient 默认), 失败不中断其他题 |
| 后台重启丢失 | Task 5 + Task 14 启动恢复 |
| CSV 大文件 | Task 2 `MAX_FILE_SIZE = 5MB`, Task 12 客户端预检 |
| `RAG_ADMIN_TOKEN` 误提交 | Task 14 `.env.example` 注释, README 警告 |
| 客户端 token spec 未实施 | Task 1 `resolve_user` 接受 `x-user-token` header, 但不要求前端必须发 (后续 spec 接入即可), 现有 401 行为不变 |
| FastAPI multipart 文件名编码 | Task 6 用 `file.filename or "upload.csv"` fallback |
| Test fixture 间 sqlite 句柄泄漏 | 沿用 storage spec Task 6 的 `reset_storage_engine` fixture, 测试结束 dispose |

### 5. Files 总数

| 类别 | 新建 | 修改 |
|---|---|---|
| 后端 Python | 8 (auth/csv_parser/template/runner/runner_registry/router + 2 个 __init__) | 1 (auth/__init__.py / eval/__init__.py 如有) |
| 后端测试 | 6 (auth/4 个 eval/) | 0 |
| 前端 TS | 7 (BFF 4 + 2 组件 + headers.ts + 详情页) | 2 (types.ts + 列表页) |
| E2E | 1 | 0 |
| 文档/配置 | 2 (README + .env.example) | 0 |
| **合计** | **24 新建** | **3 修改** |

✅ 跟 spec "File Structure" 节 1:1 对应.

---

## 实施后置 (不在本 plan)

1. 客户端 token spec (auth 配套) - 独立 plan
2. 聊天 spec (复用 CurrentUser) - 独立 plan
3. 部署时 `RAG_ADMIN_TOKEN` 配 git secret, 留空生产
4. 多 worker 部署时取消信号换 Redis

---

## 14 task 总览

| # | 主题 | 估时 (subagent) | 风险 |
|---|---|---|---|
| 1 | CurrentUser + resolve_user | 8 min | 低 (Pydantic 简单) |
| 2 | CSV parser | 10 min | 低 (纯函数 + 边界条件) |
| 3 | template 生成 | 5 min | 低 (常量字符串) |
| 4 | runner.py (核心) | 25 min | 中 (并发 + DB 落库) |
| 5 | runner_registry | 8 min | 低 |
| 6 | router (5 endpoint) | 25 min | 中 (multipart + 鉴权) |
| 7 | types.ts | 3 min | 低 |
| 8 | BFF 列表/上传 | 8 min | 低 |
| 9 | BFF 详情/取消 | 5 min | 低 |
| 10 | BFF 模板 | 3 min | 低 |
| 11 | StatusBadge + EvalListRow | 8 min | 低 |
| 12 | 3 页面 | 25 min | 中 (form + 状态机 + 路由) |
| 13 | E2E | 10 min | 低 |
| 14 | README + 启动恢复 + .env | 5 min | 低 |

总 ~148 min 串行 / ~70 min 并行 (subagent 并行跑 4-5 task).

---

## 完成后验证

```bash
# 后端
uv run --no-sync python -m pytest tests/rag/eval/ tests/rag/middleware/ tests/rag/storage/ tests/rag/auth/ tests/rag/chat/ -v
# 前端
cd web && npx tsc --noEmit
cd web && npm run lint 2>&1 | tail -10
# E2E (需 backend 启动 + admin token 配置)
cd web && npm run test:e2e -- 04-evaluate.spec.ts
```

预期: 后端 ~60+ 测试全绿, 前端 0 type error / lint error, E2E 5 passed.
