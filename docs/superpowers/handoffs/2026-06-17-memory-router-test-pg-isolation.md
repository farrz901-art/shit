# Memory router 测试 PG 隔离 handoff (2026-06-17)

## 背景

排查 `/api/memory/search` 返回 500 根因 (spacy `en_core_web_sm` 缺失) 时, 顺手跑全量 memory test 发现 11 个 `tests/memory/test_router.py` 失败, **失败根因跟 spacy 无关, 是测试隔离的预存在 bug**.

## 根因链

`tests/memory/test_router.py::test_*_dev_mode` → `os.environ["RAG_DEV_AUTH"] = "true"` → 走 FastAPI TestClient → `resolve_user()` (`src/middleware/auth.py:67`) → `_ensure_dev_user()` (`auth.py:34`) → `session_scope()` (`src/storage/session.py:26`) → `get_engine()` (`src/storage/engine.py:45`) → 实际连 `postgres:postgres@localhost:5432` → **docker PG 密码是 `deyuan888`, auth 失败** (跟你之前在 `feedback-config-dataclass-needs-from-env` 修过的 PG 密码漂移同一个根因).

**完整失败 11 个**: `test_search_200_dev_mode`, `test_search_returns_empty_on_service_degradation`, `test_search_400_on_invalid_body`, `test_add_204_dev_mode`, `test_add_400_on_empty_messages`, `test_list_200_dev_mode`, `test_update_200_dev_mode`, `test_update_403_on_cross_user`, `test_delete_200_dev_mode`, `test_delete_403_on_cross_user`, `test_delete_all_200_dev_mode`.

## 为什么不在本 spec 修

- 跟 [[2026-06-16-test-isolation]] 的 pre-existing 30+ test 失败**同一类问题**: 测试依赖 dev PG 实际可达, 违反 CLAUDE.md "测试 100% mock" 硬规则
- 本 spec 的目标是修 500 根因 (spacy 模型 + 启动期 warmup), 已达成
- 11 个 test 修法需要给 `app_with_memory` fixture 加 mock (1 行) 或改 `resolve_user` 注入点 (中等), 是独立可分离的工作

## 接手者: 修法建议 (任选一)

| 方案 | 改在哪 | 工作量 | 备注 |
|---|---|---|---|
| A | `tests/memory/test_router.py::app_with_memory` fixture 加 `monkeypatch.setattr(auth, "_ensure_dev_user", lambda: None)` | 1 行 | 最小, dev mode 跳过 User 表 FK 兜底, 不动业务代码 |
| B | `app_with_memory` fixture mock `session_scope` 返 `MagicMock`, 让 `User.query` 返 dev user | ~10 行 | 更彻底, 覆盖未来加 DB 查询的代码 |
| C | 11 个 test 加 `@pytest.mark.integration` + 在 pyproject 配 skip-default | 1 行 + 配置 | 但违反 "全 mock" 原则, 不推荐 |

**推荐 A**, 跟现有 mock 风格一致, 改 1 行 fixture 即解.

## 验证步骤 (修完后)

```bash
cd packages/service
uv run pytest tests/memory/test_router.py -v
# 期望: 16 passed (含已有的 5 个非 dev-mode test)
```

## 相关改动 (本 spec 已完成, 跟本 handoff 独立)

- 装 `en_core_web_sm` wheel (pyproject.toml + `uv sync`)
- `_default_mem0_factory` 加启动期 warmup search 断言 (`src/memory/mem0_client.py`)
- 加 3 个 warmup 单元测试 (`tests/memory/test_mem0_client.py`)

## 不影响

- `test_mem0_client.py` 16 个 test 全绿 (纯 mock, 无 PG 依赖)
- 业务代码: `src/memory/router.py`, `src/memory/service.py`, `src/memory/mem0_client.py` 跟测试隔离无关
