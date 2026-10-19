# 后端已知问题 (KNOWN_ISSUES)

> 维护说明: 这里记 pre-existing pytest fail / errors, 跟某个 spec 无直接关系, 留给后续 spec / phase 处理.
> 改这里的内容时, 请同步更新对应行的 "已修" 状态 (修了删行, 加 commit hash).

---

## 2026-06-19 code-quality phase2 完成

跑 `uv run pytest -m "not integration"` 的最终状态:

- **passed: 1093** (从 baseline 1075, +18 通过)
- **failed: 0** (从 22 → 0, 全部修)
- **errors: 0** (从 38 → 0, 全部修)
- **skipped: 52**
- **deselected: 42** (标 `@pytest.mark.integration` 的, 默认 CI 不跑)

### 主要修复

| 类别 | 改动 |
|---|---|
| 全局 mock fixture | `tests/conftest.py` 加 autouse `mock_all_db_connections` (engine/session_scope/redis/object_store/neo4j) |
| 全局 helpers | `tests/helpers.py::mock_current_user()` 工厂 |
| Memory router | `tests/memory/test_router.py` mock service 实例 + dependency_overrides[require_account] |
| OpenAPI | `tests/openapi/test_openapi_metadata.py` 改用 TestClient 不依赖 localhost:8000 |
| Pydantic 字段补描述 | `src/chat/schemas.py::Backup{Conversation,Message}`, `src/lookups/schemas.py` (Patch/Create) 补 `Field(description=)` |
| ORM model 索引重复 | `src/kg/audit_models.py` 去掉 `index=True`, 保留 `__table_args__` 显式 Index |
| 前期 test_session 修 | `tests/storage/test_session.py` 3 fail 修复 (改用更精确 mock) |

### 标 `@pytest.mark.integration` 的测试 (CI 默认不跑, 需 PG/Redis env)

| 文件 | 原因 |
|---|---|
| `tests/integration/test_db_session_fixture.py` | 用 `db_session` fixture (PG 事务回滚) |
| `tests/integration/test_account_settings_models.py` | inspect 真 alembic 表 |
| `tests/integration/test_minio_e2e.py` | 真 MinIO container |
| `tests/integration/test_mineru_retry_e2e.py` | 5-8 分钟真任务 |
| `tests/db/test_log_tables.py` | log 表 schema + immutability trigger |
| `tests/middleware/test_cors_credentials.py` | 真起 PG users 表 |
| `tests/middleware/test_auth.py::test_resolve_user_token_*` (2) | 真 PG users 表 + resolve_user 链路 |
| `tests/health/test_router.py` | reset_storage_engine + Base.metadata.create_all |
| `tests/ingest/test_api.py` | reset_storage_engine + create_test_users 真表 |
| `tests/approvals/test_repo.py` | SQLAlchemy ORM 测真 SQLite (跟 PG-only JSONB 冲突) |

### 跑法

- 默认 (CI / 本机快跑): `uv run pytest` → 1093 passed, 52 skipped, 42 deselected
- 集成测试 (需 PG_HOST 5 env): `uv run pytest -m integration`
- 全部跑: `uv run pytest --override-ini="markers="`

---

## 2026-07-08 code-quality post-fix audit

跑 `uv run pytest` (无 integration marker) 的状态: **1075 passed, 3 env-failed**. 修完 18 个 inline (A1+A2 web_apis + B1+B2 lookups + C1 chat-shell + D datasets-table + E oxlint + C2 openapi) 后, 剩 3 个 env-only fail.

### 环境依赖 fail (非代码问题)

| 测试 | 原因 | 修法 |
|---|---|---|
| `tests/ingest/test_cad_converter.py::TestEzdxfConverter::test_convert_dwg_runs_with_real_oda_when_installed` | 沙箱无 ODA File Converter (`OdaNotInstalledError`) | 装 ODA File Converter + 配 `ODA_WIN_PATH` / `ODA_UNIX_PATH` |
| `tests/ingest/test_cad_oda.py::TestReadCadWithOda::test_dwg_does_not_raise_oda_not_installed_when_installed` | 同上 | 同上 |
| `tests/integration/test_mineru_retry_e2e.py::test_mineru_retry_e2e_experiment_d` | 沙箱无外网, Docker Hub 拉 `mineru:latest` 镜像 403 Forbidden | CI 预 pull mineru 镜像到本地 registry, 或预缓存到 host docker images |

这 3 条 fail 跟代码无关, 等 CI 沙箱补齐环境依赖. 业务代码已 mock 兜底, 不影响 dev / 本机跑.

### 启动顺序 / 复杂依赖

`tests/conftest.py` 的 autouse `mock_all_db_connections` mock 了:

1. `src.storage.engine._engine = None` (关单例)
2. `src.storage.session_scope` + namespace alias (`src.core.audit.session_scope`, `src.kg.audit.session_scope`)
3. `src.core.redis_client.get_redis` → fakeredis (业务 safe_* 自动走假 redis)
4. `src.storage.object_store.get_object_store` → MagicMock
5. `src.knowledge_graph.neo4j_client.get_neo4j` → None (try/except 模块不存在跳过)
6. `src.permissions.cache.permission_cache.get` → True (require_page 不回退 PG)

测试可用 monkeypatch 覆盖任一项 (test_redis_client.py reload module 测 lazy init).

---

## 关联文档

- 测试隔离 4 模式: [packages/service/CLAUDE.md §测试隔离 4 模式](./CLAUDE.md)
- spec: [docs/superpowers/specs/2026-06-19-code-quality-phase2.md](../../docs/superpowers/specs/2026-06-19-code-quality-phase2.md)
- plan: [docs/superpowers/plans/2026-06-19-code-quality-phase2.md](../../docs/superpowers/plans/2026-06-19-code-quality-phase2.md)

---

## 2026-07-01 pre-existing 3 fail (master HEAD `a1bf907a` 已在, 非新 fail)

跑 `uv run pytest -m "not integration"` 在干净 master 上已 fail 这 3 个, **不在 user 表 tok-* 污染修复范围**:

| 文件:行 | 原因 | 修法建议 |
|---|---|---|
| `tests/storage/test_engine.py::TestInitDb::test_disabled_by_default` | `init_db()` 内部 `get_engine()` 触发真连 PG 验连接, docker 密码 `postgres:postgres` (默认值, 见 `db_url.py:28`) 跟实际 `deyuan888` 不一致 → OperationalError 上抛 → capsys 抓不到 logger.info | (a) `.env.local` 补 `PG_PASSWORD=deyuan888`; (b) test 改用 mock `get_engine` 跳过真连 |
| `tests/storage/test_engine.py::TestInitDb::test_enabled_prints_warn` | 同上, 跟 `test_disabled_by_default` 同一根因 | 同上 |
| `tests/chat_share/test_service.py::test_revoke_share_owner_succeeds` | `MagicMock(user_id="42")` 配错 (str 跟 int 比较), `share.user_id != current_user_id` 走 `"42" != 42` = True → 误 raise ShareNotFound | 改成 `MagicMock(user_id=42)` (int) 即可通过 |

**清理 dev DB users 表的 tok-* 污染** (2026-07-01 同次修复): 81 行假 user (3 前缀各 27 行) + 54 行关联 conversation, 来源 `tests/chat/test_models.py` 走真 PG 直 commit. 修法: 改该文件走 mock 单测 (验 ORM 字段, 不依赖 SQL 行为), FK/CASCADE 类 SQL 行为测试 skip 并标"留给 tmp_pg_schema spec". 修 commit 后 DB users 总数 49 (全 hex 64 合法), 0 污染.
