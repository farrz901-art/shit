---
name: feedback-alembic-env-requires-load-dotenv
description: "alembic 子进程不继承 main.py 的 load_dotenv, 必须 env.py 显式 load_dotenv, 否则 PG_* env 全空走默认 postgres:postgres 密码错"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bbd38558-9e99-4b93-b8fc-d4e462b4c307
---

**症状**: `alembic upgrade head` 报 `password authentication failed for user "postgres"`, 但 .env.local 已经正确配置 `PG_PASSWORD=deyuan888`.

**根因**: alembic 是独立子进程, 不继承 main.py 顶部 `load_dotenv(".env.local")` 调用. 启动时 `os.environ` 是空的, `get_rag_db_url()` 走 defaults (`postgres:postgres`), 跟 docker 实际密码 (`deyuan888`) 不匹配, PG 报 auth failed.

**修法**:
1. `packages/service/src/storage/migrations/env.py` 顶部加:
   ```python
   from dotenv import load_dotenv
   load_dotenv(".env.local", override=False)
   ```
2. env.py 用 `# ruff: noqa: E402` (load_dotenv 必须在其他 import 前)
3. 3 段 try/except 包 关键步骤 (URL 构造 / engine 创建 / migration 执行), 各自给具体修复提示 (`.env.local 配 PG_*` / `PG 不可达` / `migration 文件语法错`)

**Why**:
- 跟 main.py 行为不一致: main.py 启动顺序是 `load_dotenv` → import models → get_rag_db_url (有 env). alembic 跳过了 load_dotenv.
- 同样的代码路径 (`get_rag_db_url()`) 行为却不一致, 排错时间 1h+.

**How to apply**:
- 任何独立 Python 子进程 (alembic, celery worker, manage.py 等) 都需要在 entry script 顶部 `load_dotenv`, 跟 main.py 保持一致
- 检查 `if sys.argv[0].endswith("alembic")` 或类似 runtime 标志, 决定要不要在共享 module 顶层 load_dotenv
- CI 跑 alembic 也得加 `pip install python-dotenv` + 配 `.env.local` 路径

**2026-06-22 真实 bug**: 拉 PG 表, alembic 一直报密码错, 排查 1h 才发现是子进程不读 env.
修法后: alembic env.py load_dotenv + 友好错误提示, 未来类似问题 5 分钟内定位.
