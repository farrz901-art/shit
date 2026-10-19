---
name: feedback-rsc-fetch-no-browser-cookie
description: "RSC (server component) prefetchQuery 用 apiFetch 永远拿不到浏览器 cookie (浏览器 cookie 还没设), dev 环境必须设 RAG_DEV_AUTH=true 走 dev-default 路径, 否则 401 满屏"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

**RSC prefetchQuery 永远拿不到浏览器 cookie. dev 必须 RAG_DEV_AUTH=true.**

**Why:** 2026-06-14 web 端首屏 RSC 调 `prefetchQuery("/api/ingest/tasks")` 报 401:

```python
# 后端 _check_token (packages/service/src/ingest/api.py:198)
if not x_user_token:
    if os.getenv("RAG_DEV_AUTH", "").lower() in ("1", "true", "yes"):
        return "dev-default"
    raise HTTPException(status_code=401, detail="缺少 x-user-token")
```

**根因链路**:
1. RSC 端 `prefetchQuery` 调 apiFetch → 后端 `_check_token`
2. 后端查 `rag_user_token` cookie → **没有**
3. `RAG_DEV_AUTH` 也没设 → 401
4. AuthBootstrap 是 client useEffect,**RSC 当次 SSR 永远赶不上**

**浏览器 anon cookie 不可能给 RSC**:
- AuthBootstrap 在 client mount 时跑, **晚于 RSC 渲染**
- 即便 RSC 等待 client mount, RSC 端 `cookies()` 读的是浏览器 request cookie, anon bootstrap 写的是 browser-set cookie, 跨了层
- 这是**架构层面的不可能**, 不是时序

**修法 (dev 环境, 简单 1 行)**: `packages/service/.env.local` 加 `RAG_DEV_AUTH=true`, 后端走 dev-default 路径返固定 token

**注意**:
- ⚠️ 生产**必须**关掉, 否则任何人都能调所有 API
- ⚠️ dev 模式 `RAG_DEV_AUTH=true` 意味着 RSC 跟 client 拿不同用户数据 (RSC 用 dev-default, client 用真 anon user) — 仅 task list 这种"通用"数据安全, 用户隔离数据必须走 RAG_DEV_AUTH=false

**验证**:
```bash
curl http://127.0.0.1:8000/api/ingest/tasks
# RAG_DEV_AUTH=true → 200 OK []
# RAG_DEV_AUTH=false → 401 "缺少 x-user-token"
```

**关联**:
- [[feedback-main-py-must-load-dotenv-before-src-imports]] — main.py:14 load_dotenv(".env.local") 在 src.* import 之前
- [[feedback-uvicorn-must-restart-after-route-add]] — 改 env 后必须杀 uvicorn PID 重启
- [[feedback-bff-cookie-must-propagate]] — BFF 透传 set-cookie 是另一回事
- [[feedback-debug-distinguish-root-causes]] — 别把"浏览器 anon 没设上"和"RSC 拿不到 cookie"混在一起
