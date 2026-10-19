---
name: feedback-uvicorn-must-restart-after-route-add
description: uvicorn 改**任何**代码后都要重启 (router/函数体/dep 切换), 旧进程内存里的代码不更新 → 静默 bug 难诊断
metadata:
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

正在跑的 `uvicorn main:app` 进程**不会自动加载新代码** — 不只新 router, 任何 .py 改动 (函数体/refactor/dep 替换/import 路径变) 都要 kill + 重启.

**Why:** Uvicorn 没有内置文件 watcher (除非 `--reload`), 内存里 app 对象和模块缓存都是启动时的快照. 旧进程跑旧代码, 新 bug 在它身上看不到, 容易误以为"改完没生效".

**典型症状链 (路由器缺失)**:
1. BFF `/api/knowledge/schema` 报 `HTTP 502: schema 加载失败`
2. BFF 日志显示 FastAPI 返了非 2xx → 转 502
3. 直接 `curl http://localhost:8000/api/kg/schema` 返 **404 Not Found**
4. 但 `uv run python -c "from src.product_decoders import create_app; app=create_app(); print([r.path for r in app.routes])"` 能看到路由

**典型症状链 (函数体改动) (2026-06-15 真实踩坑)**: pynvml→nvidia-ml-py 切换后改 `_sample_gpu()` 适配 `str` 返回值, 但 uvicorn 没重启 → `/api/health/system` 一直返 `"gpu": []`. 直接 `uv run python -c "from src.health.checks import _sample_gpu; print(_sample_gpu())"` 能拿到 GPU 数据, 进一步确认是进程没重启. 杀 PID 39400 → 重启 → API 返 GPU 数据.

**How to apply:**
- 改**任何** backend .py 后: `netstat -ano | findstr ":8000.*LISTENING"` 找 PID → `taskkill //PID xxx //F` → `uv run python main.py` 重起
- 调试时如果"直接调函数对, HTTP 端不对" → 第一反应是 uvicorn 没重启, 不是代码 bug
- (2026-06-12) **同类陷阱: .env.local 也是同样问题** — `main.py:14 load_dotenv(".env.local")` 启动时一次性加载, 后续**新建/修改** .env.local 不会重读, 必须重启 uvicorn. 症状: 报 "DIFY_CHAT_API_KEY 未配置" 但文件存在 + 配对了 → 检查 uvicorn 启动时间 vs .env.local 修改时间, 重启. 验证: `cd packages/service && uv run --active python -c "import os; print(os.getenv('DIFY_CHAT_API_KEY'))"` 看 SET/UNSET
