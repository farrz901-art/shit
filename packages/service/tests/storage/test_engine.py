"""engine.py 单元测试 (PG only, 2026-06-15 / 2026-06-18 refactor)

URL 走 src.common.db_url.get_rag_db_url() (PG_* 5 env), 不再读 RAG_DB_URL.
get_rag_db_url 本身的 10 个单测在 tests/common/test_db_url.py, 这里只测
engine 模块的 pool 配置 + init_db 行为.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_module_engine(monkeypatch):
    """每个 test 前 reset 模块级 _engine 单例, 避免上一个 test 的 engine 串到下一个."""
    import src.storage.engine as eng_mod

    eng_mod._engine = None
    yield
    eng_mod._engine = None


class TestMakeEngine:
    """_make_engine 不再有 SQLite 特化."""

    def test_pg_engine_has_no_check_same_thread(self):
        from sqlalchemy.pool import QueuePool

        from src.storage.engine import _make_engine

        eng = _make_engine("postgresql+psycopg://u:p@localhost:5432/rag")
        # 走 QueuePool (默认) 不用 NullPool
        assert isinstance(eng.pool, QueuePool)
        # pool_pre_ping 必须在
        assert eng.pool._pre_ping is True
        # URL 正确解析成 PG (不抛错, dialect 是 postgresql)
        assert eng.dialect.name == "postgresql"


class TestInitDb:
    """init_db 受 RAG_AUTO_CREATE_SCHEMA 开关."""

    def test_disabled_by_default(self, monkeypatch):
        """不配 RAG_AUTO_CREATE_SCHEMA=1 时 init_db 跳过.

        (2026-07-08) init_db 走 loguru, stdlib capsys/caplog 抓不到. 改 mock logger 实例,
        断言 .info 被调用 + message 含 'skipped', 跟旧 capsys 行为等价.
        """
        from unittest.mock import MagicMock

        monkeypatch.delenv("RAG_AUTO_CREATE_SCHEMA", raising=False)
        fake_logger = MagicMock()
        monkeypatch.setattr("src.storage.engine.logger", fake_logger)

        from src.storage.engine import init_db

        init_db()
        # 源码 message 是 "[storage] 已跳过 init_db (设置 RAG_AUTO_CREATE_SCHEMA=1 启用)"
        info_msg = fake_logger.info.call_args.args[0]
        assert "已跳过" in info_msg
        assert "RAG_AUTO_CREATE_SCHEMA" in info_msg

    def test_enabled_prints_warn(self, monkeypatch):
        """配 RAG_AUTO_CREATE_SCHEMA=1 时打印 WARN.

        (2026-06-29) mock Base.metadata.create_all 避免真连 PG, 让单测 Windows 也能跑通.
        test 本意只验证 'init_db 在开关开时打 WARN 字符串', 不验证 create_all 真行为
        (create_all 是 SQLAlchemy 内部, 不用我们测).

        (2026-07-08) 改 mock logger 替代 capsys (loguru 走自己 handler, stdlib capfd 也漏).
        """
        from unittest.mock import MagicMock

        monkeypatch.setenv("RAG_AUTO_CREATE_SCHEMA", "1")
        # mock create_all 阻止真连 PG
        monkeypatch.setattr("src.storage.engine.Base.metadata.create_all", MagicMock())
        # 也 mock get_engine 避免初始化 engine 时真连 (engine_init 在 import 时已跑)
        monkeypatch.setattr("src.storage.engine.get_engine", MagicMock())
        fake_logger = MagicMock()
        monkeypatch.setattr("src.storage.engine.logger", fake_logger)

        from src.storage.engine import init_db

        init_db()
        fake_logger.warning.assert_called_once()
        warn_msg = fake_logger.warning.call_args.args[0]
        # loguru 自己加 WARN 等级前缀, 不在 message 里; 只验中文业务文案
        assert "自动建表" in warn_msg
        assert "dev/test" in warn_msg


class TestEngineUsesGetRagDbUrl:
    """get_engine() URL 走 get_rag_db_url() (PG_* 5 env 派生), 不再读 RAG_DB_URL."""

    def test_rag_db_url_ignored(self, monkeypatch):
        """即使设 RAG_DB_URL 也被忽略, engine 走 get_rag_db_url()."""
        monkeypatch.setenv("RAG_DB_URL", "postgresql+psycopg://should-be-ignored:x@host:1234/db")
        monkeypatch.setenv("PG_HOST", "test-pg")
        monkeypatch.setenv("PG_PORT", "5432")
        monkeypatch.setenv("PG_USER", "alice")
        monkeypatch.setenv("PG_PASSWORD", "pw")
        monkeypatch.setenv("PG_DATABASE", "rag")

        from src.common.db_url import get_rag_db_url

        # RAG_DB_URL 存在但 get_rag_db_url 不读它
        url = get_rag_db_url()
        assert "should-be-ignored" not in url
        assert "test-pg" in url
        assert "alice" in url
