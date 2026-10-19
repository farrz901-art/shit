"""check_pgvector 连接串必须读 PG_PASSWORD env, 不能用 dataclass 默认值.

Bug 复盘 (2026-06-15):
  - _get_pg_engine() 调 PGVectorConfig() (无参) → password 走 dataclass 默认 "postgres"
  - docker/.env 实际 POSTGRES_PASSWORD=deyuan888, .env.local 配 PG_PASSWORD=deyuan888
  - 结果: sqlalchemy 拼出 postgresql://postgres:postgres@... → psycopg2 认证失败
  - 根因: PGVectorConfig() (无参) 不读 env, 必须用 PGVectorConfig.from_env()
"""

from __future__ import annotations


class TestPgEngineReadsEnv:
    """_get_pg_engine() 必须从 PG_PASSWORD env 读真密码"""

    def test_engine_url_password_comes_from_env(self, monkeypatch):
        """PG_PASSWORD=custom_pwd_xyz → engine.url.password == 'custom_pwd_xyz'"""
        monkeypatch.setenv("PG_PASSWORD", "custom_pwd_xyz")
        # 显式清掉别的可能干扰的 host (用回 dataclass 默认即可)
        from src.health import checks

        engine = checks._get_pg_engine()
        # sqlalchemy 解析后, 明文密码在 engine.url.password
        assert engine.url.password == "custom_pwd_xyz", (
            f"engine.url.password 应等于 env 设的 'custom_pwd_xyz', "
            f"实际: {engine.url.password!r} (说明 _get_pg_engine 没走 env)"
        )

    def test_engine_url_does_not_use_dataclass_default(self, monkeypatch):
        """PG_PASSWORD=custom_pwd_xyz → 连接串绝不能含 'postgres:postgres@'"""
        monkeypatch.setenv("PG_PASSWORD", "custom_pwd_xyz")
        from src.health import checks

        engine = checks._get_pg_engine()
        url = str(engine.url)
        assert "postgres:postgres@" not in url, f"连接串绝不能含 dataclass 默认 'postgres:postgres@', 实际: {url!r}"

    def test_engine_url_includes_env_host_port(self, monkeypatch):
        """PG_HOST/PG_PORT/PG_USER/PG_DATABASE env 改了, 连接串必须跟着改"""
        monkeypatch.setenv("PG_HOST", "10.0.0.99")
        monkeypatch.setenv("PG_PORT", "6543")
        monkeypatch.setenv("PG_USER", "alice")
        monkeypatch.setenv("PG_DATABASE", "mydb")
        monkeypatch.setenv("PG_PASSWORD", "pw")
        from src.health import checks

        engine = checks._get_pg_engine()
        # 注意: str(engine.url) 会把密码 mask 成 ***, 必须读 .host/.port/.username/.password/.database
        assert engine.url.host == "10.0.0.99", f"PG_HOST 没透传: host={engine.url.host!r}"
        assert engine.url.port == 6543, f"PG_PORT 没透传: port={engine.url.port!r}"
        assert engine.url.username == "alice", f"PG_USER 没透传: user={engine.url.username!r}"
        assert engine.url.password == "pw", f"PG_PASSWORD 没透传: password={engine.url.password!r}"
        assert engine.url.database == "mydb", f"PG_DATABASE 没透传: db={engine.url.database!r}"
