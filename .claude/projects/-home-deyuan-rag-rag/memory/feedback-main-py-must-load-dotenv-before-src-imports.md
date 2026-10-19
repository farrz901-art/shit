---
name: feedback-main-py-must-load-dotenv-before-src-imports
description: "main.py 必须在所有 src.* import 之前 module-level 调 load_dotenv(\".env.local\"), 不然 Neo4jStore 拿到 None env → AuthError"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

`main.py` 是 `uvicorn main:app` 启动入口。**`load_dotenv(".env.local")` 必须写在 `from src.*` 之前**（即 module-level, 顶部），不然 `Neo4jStore` 模块加载时 `os.getenv("NEO4J_PASSWORD")` 拿到 None → AuthError。

症状链：
1. 用户"明明 .env.local 配了 NEO4J_PASSWORD=31500900"
2. `curl http://localhost:8000/api/kg/stats` → 500
3. uvicorn 日志: `neo4j.exceptions.AuthError: The client is unauthorized due to authentication failure.`
4. `uv run python -c "import os; print(os.getenv('NEO4J_PASSWORD'))"` 在 shell 里**能**拿到值 (因为 shell 启动时 bash 已 source 过)

**Why:** Python 启动时 `os.environ` = 父进程 (shell) 的 env。`uv run uvicorn` 不会自动读 `.env.local` (那是 dotenv 的活)。`Neo4jStore.__init__` 调 `_config_from_env()` 在 import 链中触发，把 None 锁进单例了。

**How to apply:**
- main.py 顶部第 1 个非 docstring 语句: `from dotenv import load_dotenv; load_dotenv(".env.local")`
- `from src.product_decoders import create_app` 一定排在它后面
- 测试要 2 步: (1) 源文件静态检查 `load_dotenv(".env.local")` 在 `from src.` 之前 (2) subprocess 验 `load_dotenv('.env.local')` 真把内容灌进 `os.environ`
- 不要用 `reload(main)` 测 (会引入太多副作用); 静态源码检查 + subprocess 测 dotenv 真行为已够
