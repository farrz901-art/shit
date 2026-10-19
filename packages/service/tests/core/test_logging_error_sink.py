"""error_logs sink JSONB bindparam 修复 (2026-06-25 json-jsonb spec Task A)

测试模式 1 (mock): 验证 _error_sink_sync 用 bindparam(type_=JSONB) 包装 stmt,
不走真 PG.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from sqlalchemy.dialects.postgresql import JSONB

from src.core.logging import _error_sink_sync


def test_error_sink_uses_jsonb_bindparam():
    """_error_sink_sync 写 error_logs.context 必须用 bindparam(type_=JSONB).

    防回归: 不加 bindparam 时, psycopg3 传非空 dict 会抛
    'cannot adapt type dict using placeholder %s'.
    """
    captured_stmt = {}

    class _FakeSession:
        def execute(self, stmt, params):
            captured_stmt["stmt"] = stmt
            captured_stmt["params"] = params

    class _CtxMgr:
        def __enter__(self):
            return _FakeSession()

        def __exit__(self, *a):
            return False

    with patch("src.storage.session_scope", return_value=_CtxMgr()):
        req = MagicMock()
        req.url.path = "/api/foo"
        req.method = "POST"
        _error_sink_sync("ERROR", RuntimeError("boom"), req)

    stmt = captured_stmt["stmt"]
    # SQLAlchemy TextClause.bindparams 标过类型后, _bindparams dict 含 ctx 项 + type_ 是 JSONB
    bind = stmt._bindparams.get("ctx")
    assert bind is not None, "ctx 参数未声明 bindparam"
    assert isinstance(bind.type, JSONB), f"ctx 应是 JSONB, 实际 {type(bind.type).__name__}"
