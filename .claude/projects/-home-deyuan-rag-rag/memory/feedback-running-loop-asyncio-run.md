---
name: feedback-running-loop-asyncio-run
description: "FastAPI lifespan / async context 调同步函数内含 asyncio.run 会 RuntimeError, 必须拆 async 入口直接 await"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fef3034b-313a-4370-9ec2-f4270e9be5ed
---

在已有 running event loop 的 async context (FastAPI lifespan / Task / async pytest) 里, 调任何**同步**包装函数如果它内部用 `asyncio.run(coro)` 调 async 函数, 都会抛 `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**典型场景**:
- FastAPI `@asynccontextmanager async def _lifespan(app)` 里调 `_setup_dictionaries()` (同步), 内部 `check_consistency()` 用 `asyncio.run(LookupService.list_all_dicts())`
- 任何 async task / async fixture / `asyncio.create_task` 内调 sync 包装
- 单元测试用 `pytest-asyncio` 的 `@pytest.mark.asyncio` 跑 async test 时调 sync helper

**修法**(修法 1, 推荐):
1. 拆出 `async def xxx_async()` 内部直接 `await` 异步函数, 不包 `asyncio.run`
2. 保留 `def xxx()` 同步版给 CLI / 同步测试用, 内部 `asyncio.run(xxx_async())`
3. async context (lifespan / task / async test) 调 `await xxx_async()`; 同步 context 调 `xxx()`

**修法 2**: `nest_asyncio.apply()` 在入口, 不推荐 — 隐藏问题 + Python 3.10+ 不太稳

**修法 3**: 让 xxx 接受外部 loop 参数 — 改的接口多, 不推荐

**真案**: commit `95e7e4ce` 修 `src/core/lifespan.py` + `scripts/check_dictionary_refs.py`. 拆 `check_consistency_async()`, 加 `_async_setup_dictionaries()` 供 lifespan `await`.

**根因历史**: 旧 `main.py` 已知这个问题 (脚本注释里写 "用 main.py 内 inline asyncio.run" 规避), commit `57f2a8df refactor(service)` 把 main.py 迁到 `src/core/lifespan.py` 时**没继承这个保护**, 引入新 bug, 一直到 lifespan 在生产 FastAPI 启动才暴露.

**Why**: 用户多次因 asyncio 同步/异步混用报错, 注释里写的设计意图不跟实际代码同步, 修这种 bug 要拆出 async 入口而不是改用 nest_asyncio 黑魔法.

**How to apply**: 改 lifespan / async context 同步函数时, 优先检查内部是否用 `asyncio.run`. 如果用了, 拆 async 入口. 加新 sync 包装时, 必须显式写注释 "在已有 loop 中调会 RuntimeError, 用 xxx_async() 替代", 跟 [[feedback-debug-search-before-loop]] 的"先看注释里有没有作者已知的设计意图"配套.
