"""tests/ 顶层 conftest

pytest 找 conftest 向父级走, tests/<subdir>/conftest.py 不会被顶层这个 re-export.
每个需要 PG 的 test 自己用 `from tests.integration.conftest import db_session`.
这里**不**re-export 任何 autouse fixture, 跟 dev DB 共享的项目不允许全局副作用.

但非 autouse 的 PG fixtures (pg_engine / reset_storage_engine / tmp_db_url) 显式
re-export, 让子目录 conftest 能 import 到 (pytest 找 conftest 不会跨 sibling, 不
re-export 的话 tests/auth/ 等子目录的 fixture 拿不到). 这是 pytest fixture 机制
的硬约束, 跟"加 autouse 清表"是两回事.

**Mock 矩阵** (mock_all_db_connections autouse fixture):

| 资源           | mock 方式                                | 作用                                 |
|----------------|------------------------------------------|--------------------------------------|
| PG engine      | `_engine = None`                         | 防止意外复用真正连接                  |
| session_scope  | `MagicMock` 全局替换                     | audit / hot path 不真连 PG           |
| Redis          | `fakeredis.FakeRedis` 或 safe_*  fallback| token_cache / rate_limiter 不卡      |
| ObjectStore    | `MagicMock`                              | 避免 MinIO/LocalFS 初始化            |
| Neo4j          | `get_neo4j -> None`                      | 连接不初始化                         |
| Permission cache | `permission_cache.get -> True`        | require_page 不回退到 PG             |

**2026-06-19 code-quality phase2**: 加全局 mock_all_db_connections autouse fixture,
确保所有 test 默认不直连 PG/Redis/Neo4j. 集成测试标记 @pytest.mark.integration 时
此 fixture 自动失效 (由 integration 子目录自己的 conftest 覆盖).

**设计原则**:
- 只 mock 被动资源 (engine 单例 / redis 连接 / object_store / neo4j)
- 不 mock 主动业务函数如 session_scope / get_session — 这些由各 test 自己决定
- permission_cache.get 统一 mock 防止 require_page 因 cache miss 回退到 PG
"""

from __future__ import annotations

import pytest

from tests.storage.conftest import (  # noqa: F401  # 暴露给子目录 conftest 用
    reset_storage_engine,
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """(2026-07-09) 默认跳过 @pytest.mark.slow 标记的测试.

    原因:
      - 真 PDF / contract 扫描 / Docker 容器 e2e 单测动辄 30s ~ 3 分钟,
        拖垮开发反馈循环 (项目 memory `feedback-no-full-vitest-during-dev.md`)
      - 默认跳过, 跑全量: `uv run pytest -m slow` (只跑慢的) 或 `uv run pytest -m ""` (全跑)
      - CI: 默认跑所有不带 slow 的 + 单独一个 job 跑 slow

    Raises:
      pytest.UsageError: slow marker 未注册 (pyproject.toml 必须有 markers 配置)
    """
    # 显式 -m slow → 全跑 slow; -m "" 或不加 marker → 默认跑 + 跳过 slow
    markexpr = config.option.markexpr
    if markexpr == "slow":
        return  # 全跑 slow
    if markexpr and markexpr != "":
        return  # 显式 marker expression (例 "not integration"), 不动 slow

    skip_slow = pytest.mark.skip(reason="@pytest.mark.slow 默认跳过, 跑用 `uv run pytest -m slow`")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(autouse=True)
def mock_all_db_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    """全局 autouse fixture: 每个 test 跑前 mock 资源连接.

    阻止意外直连 PG/Redis/Neo4j.
    被 @pytest.mark.integration 标记的 test 会由 integration/conftest.py 覆盖.
    """
    # ---- PG: 关 engine 单例, 防止意外复用真正连接 ----
    monkeypatch.setattr("src.storage.engine._engine", None)

    # ---- session_scope: 全局 mock 防止 audit / hot path 真去连 PG ----
    # _persist_audit (in src.core.audit) 走 `from src.storage import session_scope` 写 audit_logs.
    # 测试若 mock 业务模块 session_scope 但漏 mock audit 走的 src.storage 入口, 会真连 PG → hang.
    # 全局 mock session_scope 返 MagicMock, 业务 / audit / log 都不会真打表.
    # 各 test 内若需要更精确的 mock (验证 session.add / session.flush), 可以用 patch
    # 覆盖本 mock — pytest monkeypatch 以最内层为准.
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_scope = MagicMock()
    mock_scope.__enter__ = lambda self: mock_session
    mock_scope.__exit__ = lambda self, *args: False

    def _mock_session_scope():
        return mock_scope

    # (2026-07-01) session_scope 定义在 src.storage.session (不是 src.storage).
    # 业务代码 `from src.storage import session_scope` 走父模块 re-export, patch 它
    # 就拦截. 但 tests/storage/test_session.py 等子模块显式
    # `from src.storage.session import session_scope` 想测真函数行为, 不能 patch 子模块
    # (会破坏 mock 测试). 所以只 patch 父模块, 子模块保持原状;
    # tests/chat/test_models.py 旧 fixture 走真 PG 改写为 mock 单测 (不依赖此 patch).
    monkeypatch.setattr("src.storage.session_scope", _mock_session_scope)

    # 各 namespace 里 import session_scope 也要 mock (避免「import 时拷贝」)
    for module_path in (
        "src.core.audit",
        "src.kg.audit",
        "src.ingest.pre_analysis.runner",  # (2026-07-06) 之前漏了, runner 真连 PG 卡死
        "src.ingest.pre_analysis.stage_store",  # 同上
        "src.ingest.pre_analysis.store",  # 同上
        "src.ingest.pre_analysis.router",  # (2026-07-06) 从 api.py 拆出
        "src.ingest.pdf_processing.router",  # (2026-07-06) ingest 路由
    ):
        try:
            monkeypatch.setattr(f"{module_path}.session_scope", _mock_session_scope)
        except AttributeError, ImportError, ModuleNotFoundError:
            pass

    # ---- Redis: 用 fakeredis 接管 get_redis (业务 safe_* 自动走 fakeredis) ----
    # 单测里 token_cache / rate_limiter 等 await get_redis().xxx 时, 真去连 redis 会卡住
    # (Windows 上常见). fakeredis 提供完整 async API, 跟真 redis 接口一致.
    # 各 test 自己 monkeypatch.setattr(redis_client, "get_redis", ...) 覆盖时优先生效.
    try:
        from fakeredis.aioredis import FakeRedis as FakeAsyncRedis

        # 单进程内共享一个实例 — 跟真 Redis 多客户端连同一服务一致
        fake_redis = FakeAsyncRedis(decode_responses=True)
        monkeypatch.setattr("src.core.redis_client.get_redis", lambda: fake_redis)
        # 也把 src.core.redis_client._pool 重置, 避免上次 test 残留
        monkeypatch.setattr("src.core.redis_client._pool", None)
        # (2026-06-29 BE-11 fix) 熔断 state 也是 module-level, test 之间共享.
        # 前一个 test 触发 _trip_circuit → _circuit_open_until = future, 后续 test safe_get 短路返 None.
        # 每个 test 跑前重置, 保证 fakeredis 调用真正走通.
        monkeypatch.setattr("src.core.redis_client._circuit_open_until", 0.0)
        monkeypatch.setattr("src.core.redis_client._circuit_first_failure_logged", False)
    except ImportError:
        # fakeredis 没装就 fallback: mock safe_* 走 None / False (rate_limiter 限流不工作但不挂)
        async def _async_none(*args, **kwargs):  # noqa: ARG001
            return None

        async def _async_false(*args, **kwargs):  # noqa: ARG001
            return False

        async def _async_zero(*args, **kwargs):  # noqa: ARG001
            return 0

        monkeypatch.setattr("src.core.redis_client.safe_get", _async_none)
        monkeypatch.setattr("src.core.redis_client.safe_set", _async_false)
        monkeypatch.setattr("src.core.redis_client.safe_delete", _async_zero)
        monkeypatch.setattr("src.core.redis_client.safe_incr", _async_zero)

    # ---- ObjectStore: mock 避免 MinIO/LocalFS 初始化 ----
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    monkeypatch.setattr("src.storage.object_store.get_object_store", lambda: mock_store)

    # ---- Neo4j: mock 连接 (模块可能不存在) ----
    try:
        monkeypatch.setattr("src.knowledge_graph.neo4j_client.get_neo4j", lambda: None)
    except Exception:
        pass  # 模块不存在就跳过

    # ---- Permission cache: 统一 mock require_page 防回退到 PG ----
    try:
        from src.permissions.cache import permission_cache

        monkeypatch.setattr(permission_cache, "get", lambda role, key: True)
    except Exception:
        pass
