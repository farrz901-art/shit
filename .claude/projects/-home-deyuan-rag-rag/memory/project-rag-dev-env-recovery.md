---
name: project-rag-dev-env-recovery
description: "拉新代码/重置后端 DB 后, 必须跑 alembic upgrade head, 否则 SQLite 缺表 → 500 \"Internal Server Error\" plain text"
metadata: 
  node_type: memory
  type: project
  originSessionId: 860be275-5c0d-4dee-802a-5fa67ad95f6c
---

`packages/service/data/app.db` 是 SQLite, 表通过 alembic migration 创建 (`alembic.ini` script_location = `src/storage/migrations`)。任何后端代码用了新表/新字段但没跑 migration, 启动会成功但第一个 SQL 查询 500。

**症状链**:
- 后端 uvicorn 返 `text/plain` "Internal Server Error" (不是 JSON, 因为是 uvicorn 兜的, 不是 FastAPI HTTPException)
- BFF route 透传 500 (BFF 没主动降级)
- Next.js RSC `rscGet` 抛 → 整页 `__next_error__` + digest + 500
- Playwright/浏览器看到 500 页 + `id="__next_error__"`

**复现命令**:
```bash
cd packages/service && uv run python -c "
import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv('.env.local')
from src.storage.session import session_scope
from src.eval.models import Evaluation
with session_scope() as s:
    s.query(Evaluation).all()  # OperationalError: no such table: evaluations
"
```

**Why**: alembic 启动时不自动建表, 必须显式 `alembic upgrade head`。uvicorn 不像 Django 有 ORM auto-create。

**How to apply**:
- 第一次拉代码 → `cd packages/service && uv run alembic upgrade head`
- 加了新 SQLAlchemy model / 新 migration → 同上
- 看到 "no such table" 错 → 跑 migration
- 不要重新 init `data/app.db` (会丢 users / 已有 evaluation 行), 用 alembic

**记忆点**:
- 不要写 shim 把 `OperationalError` 转成友好空数组 (`feedback-no-shim-no-minimal-changes`)
- BFF 看到后端 5XX 必须透传 (`feedback-bff-must-propagate-502-not-silently-zero`), 别吞
- 加 model 同步加 migration, 别只改 model 就 commit (`feedback-check-pyproject-deps-match-actual-imports` 同级)
