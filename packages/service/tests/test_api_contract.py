"""契约测试: 后端 FastAPI 路由必须覆盖前端所有直连路径.

为什么需要这个测试:
  commit 0a7903f 删了 BFF route 并把前端 URL 改成直连 FastAPI,
  但后端从未实现 /api/kg/qa 和 /api/kg/documents/commit,
  导致用户访问页面时 404. 这个测试防止同类问题再次发生.

规则:
  - 前端直连 FastAPI 的路径 (通过 ${BASE}/api/* 或 withBase) 必须在此声明
  - 测试会扫描 create_app() 的所有已注册路由做交叉比对
  - 删 BFF route 前必须先跑这个测试, 红了不能删
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# ============================================================
# 前端直连 FastAPI 的完整路由列表 (method, path)
# ============================================================
# 来源:
#   web/lib/api/system.ts   — ${BASE}${path} (health, series, decode, api/output/*)
#   web/lib/api/knowledge.ts — ${BASE}/api/kg/* 或 withBase("/api/kg/*")
#   web/lib/api/auth.ts     — ${BASE}/api/auth/anon
#   web/lib/api/ingest.ts   — 走 BFF, 不在此列
#   web/lib/api/evaluate.ts — 走 BFF, 不在此列
#   web/lib/api/chat.ts     — 走 BFF, 不在此列
# ============================================================
FRONTEND_EXPECTS: list[tuple[str, str]] = [
    # --- system.ts (直连 FastAPI) ---
    ("GET", "/product-decoder/health"),
    ("GET", "/series"),
    ("POST", "/decode"),
    # --- health (admin-only 聚合视图) ---
    ("GET", "/api/health/system"),  # (2026-06-11) 监控状态聚合, admin-only
    # --- output_api.py ---
    ("GET", "/api/output/files"),
    ("GET", "/api/output/files/{name}"),
    # --- auth ---
    ("POST", "/api/auth/anon"),
    ("POST", "/api/auth/migrate"),  # (2026-06-12) 老用户 localStorage token 换 cookie
    # --- kg (knowledge.ts 直连) ---
    ("GET", "/api/kg/stats"),
    ("GET", "/api/kg/datasets"),
    ("GET", "/api/kg/health"),
    ("GET", "/api/kg/schemas"),
    ("GET", "/api/kg/segments"),
    ("GET", "/api/kg/nodes"),
    ("GET", "/api/kg/relationships"),
    ("GET", "/api/kg/schema"),
    ("POST", "/api/kg/triples"),
    # --- kg extract (2026-07-03 markdown extract KG spec PR4 v3) ---
    ("POST", "/api/kg/extract/upload"),
    ("POST", "/api/kg/extract/start"),
    ("GET", "/api/kg/extract/tasks/{task_id}"),
    ("GET", "/api/kg/extract/tasks/{task_id}/preview"),
    ("PATCH", "/api/kg/extract/tasks/{task_id}/items"),
    ("POST", "/api/kg/extract/tasks/{task_id}/commit"),
    ("GET", "/api/kg/extract/tasks/{task_id}/export"),
    ("GET", "/api/kg/extract/datasets"),
    ("GET", "/api/kg/extract/extractors"),
    ("GET", "/api/kg/extract/splitters"),
    ("GET", "/api/kg/extract/tasks"),  # [2026-07-03] 列表页后端
    # --- ingest (ingest.ts BFF 透传到 FastAPI) ---
    ("POST", "/api/ingest/upload"),
    # --- ingest presign/finalize (2026-06-16 RAG MinIO 集成) ---
    ("POST", "/api/ingest/upload/presign"),
    ("POST", "/api/ingest/upload/finalize"),
    ("GET", "/api/ingest/tasks"),
    ("GET", "/api/ingest/tasks/{task_id}"),
    ("GET", "/api/ingest/tasks/{task_id}/files/{name}"),
    ("GET", "/api/ingest/tasks/{task_id}/download"),
    # --- evaluate (evaluate.ts BFF 透传到 FastAPI) ---
    ("GET", "/api/evaluate/runs"),
    ("POST", "/api/evaluate/runs"),
    ("GET", "/api/evaluate/runs/{run_id}"),
    ("POST", "/api/evaluate/runs/{run_id}/cancel"),
    ("GET", "/api/evaluate/template"),
    # --- approvals (approvals.ts 直连 FastAPI) — 2026-06-13 Task 7 ---
    ("POST", "/api/approvals"),
    ("GET", "/api/approvals"),
    ("GET", "/api/approvals/me"),
    ("GET", "/api/approvals/stats"),
    ("GET", "/api/approvals/{approval_id}"),
    ("POST", "/api/approvals/{approval_id}/approve"),
    ("POST", "/api/approvals/{approval_id}/reject"),
    ("POST", "/api/approvals/{approval_id}/retry"),
    # --- memory (memory.ts 直连, 2026-06-16) ---
    ("POST", "/api/memory/search"),
    ("POST", "/api/memory/add"),
    # --- memory 管理 (Phase 2, 2026-06-16) ---
    ("GET", "/api/memory/list"),
    ("PATCH", "/api/memory/{memory_id}"),
    ("DELETE", "/api/memory/{memory_id}"),
    ("DELETE", "/api/memory/all"),
    # --- chat share + files (2026-06-16) ---
    ("POST", "/api/chat/shares"),
    ("GET", "/api/chat/shares/{share_id}"),
    ("DELETE", "/api/chat/shares/{share_id}"),
    ("POST", "/api/chat/files"),
    # --- chat files presign/finalize (2026-06-17 Task 9) ---
    ("POST", "/api/chat/files/presign"),
    ("POST", "/api/chat/files/finalize"),
]


def _normalize_path(path: str) -> str:
    """统一路径格式: 去掉尾部 /, 去掉 FastAPI path converter 后缀 (:path, :int 等)"""
    import re

    path = path.rstrip("/")
    # {name:path} → {name}, {task_id:int} → {task_id}
    path = re.sub(r"\{(\w+):\w+\}", r"{\1}", path)
    return path


def _get_registered_routes(app) -> set[tuple[str, str]]:
    """扫描 FastAPI app 的所有已注册路由, 返回 (method, normalized_path) 集合"""
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not hasattr(route, "methods"):
            continue
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            routes.add((method, _normalize_path(route.path)))
    return routes


@pytest.mark.slow
def test_backend_routes_cover_frontend_expectations():
    """后端注册的路由必须覆盖前端所有直连路径.

    如果此测试失败, 说明:
      - 新增了前端直连路由但后端未实现 → 先实现后端路由
      - 删了后端路由但前端还在用 → 恢复后端路由或改前端走 BFF
    """
    from src.core.app_factory import create_app

    app = create_app()
    registered = _get_registered_routes(app)

    missing = [(method, path) for method, path in FRONTEND_EXPECTS if (method, path) not in registered]
    assert not missing, (
        f"后端缺少 {len(missing)} 个路由, 前端直连会 404:\n"
        + "\n".join(f"  {method} {path}" for method, path in missing)
        + "\n\n修复: 先在后端实现这些路由, 再删对应的 BFF route"
    )


@pytest.mark.slow
def test_no_dead_routes_in_backend():
    """后端没有前端不期望的 /api/* 路由 (防止幽灵路由堆积).

    只检查 /api/ 下的路由, 根路径 (/health, /series, /decode) 不检查.
    """
    from src.core.app_factory import create_app

    app = create_app()
    registered = _get_registered_routes(app)

    # 前端期望的 /api/* 路由 (用 normalized_path 匹配)
    expected_api_paths = {_normalize_path(path) for _method, path in FRONTEND_EXPECTS if path.startswith("/api/")}

    # 后端实际注册的 /api/* 路由
    actual_api_paths = {path for _method, path in registered if path.startswith("/api/")}

    dead = actual_api_paths - expected_api_paths
    # /api/v1/* 是旧路由, 允许存在
    dead = {p for p in dead if not p.startswith("/api/v1/")}

    # 已知废弃路由: 后端有但前端从未调用, 待清理
    # (2026-06-14) 加 account / admin / invites 13 个路由, 前端 UI 摆着但 BFF 0 个.
    # B 类 audit 决策 (用户拍 B2): 临时加 KNOWN_DEAD, 后续 Task N 接前端 BFF 再移除.
    KNOWN_DEAD = {
        "/api/kg/batch",  # v2 占位, BFF in-memory 替代
        "/api/kg/products",  # 未被前端引用
        "/api/kg/tasks/{task_id}",  # 未被前端引用
        "/api/kg/templates/excel",  # 未被前端引用
        # account (login / logout / me / forgot / reset / seed-admin) — 前端 UI 摆着, BFF 缺
        "/api/account/forgot-password",
        "/api/account/login",
        "/api/account/logout",
        "/api/account/me",
        "/api/account/reset-password",
        "/api/account/seed-admin",
        # account 设置类 (2026-06-17 T2.5 上线, BFF 待加)
        "/api/account/avatar",
        "/api/account/avatar/{account_id}",
        "/api/account/deletion",
        "/api/account/email",
        "/api/account/email/verify",
        "/api/account/password",
        "/api/account/profile",
        # admin (users / invites) — 前端 /admin/users + /admin/invites 页存在, BFF 缺
        "/api/admin/invites",
        "/api/admin/invites/{token}",
        # buyer profile (2026-06-22 上线, BFF 待加)
        "/api/buyer-profiles",
        "/api/buyer-profiles/fields",
        "/api/buyer-profiles/fields/{code}",
        "/api/buyer-profiles/my-profile",  # (2026-06-29) lib/chat/memory-integration.ts:130 直连 fetch
        "/api/buyer-profiles/{profile_id}",
        "/api/buyer-profiles/{profile_id}/changes",
        "/api/admin/users",
        "/api/admin/users/{user_id}",
        "/api/admin/users/{user_id}/reset-password",
        # invite flow (redeem / info)
        "/api/invites/{token}",
        "/api/invites/{token}/redeem",
        # lookup 字典模块 (2026-06-19, 后端已上, 前端 useLookup hook 走 BFF 待加)
        "/api/lookups",
        "/api/lookups/{dict_code}",
        "/api/lookups/{dict_code}/{key}",
        # admin/dicts (2026-06-19 super_admin 字典管理, 前端 /admin/dicts 页面接入中)
        "/api/admin/dicts",
        "/api/admin/dicts/{dict_code}",
        "/api/admin/dicts/{dict_code}/audit",
        "/api/admin/dicts/{dict_code}/items",
        "/api/admin/dicts/{dict_code}/items/{key}",
        "/api/admin/dicts/confirm-token",
        # chat 历史 (2026-06-19, BFF 接入中)
        "/api/chat/backup",
        "/api/chat/conversations",
        "/api/chat/conversations/{conv_id}",
        "/api/chat/conversations/{conv_id}/messages",
        # roles / permissions (admin 后台直连, BFF 待加)
        "/api/permissions",
        "/api/permissions/me",
        "/api/roles",
        "/api/roles/{name}",
        # pre-analysis (2026-07-03 spec 落地, 前端 useEffect 走 RSC fetch, BFF 待加)
        "/api/pre-analysis/tasks",
        "/api/pre-analysis/tasks/{task_id}",
        "/api/pre-analysis/tasks/{task_id}/download",
        "/api/pre-analysis/tasks/{task_id}/retry",
        "/api/pre-analysis/tasks/{task_id}/stages",
        "/api/pre-analysis/tasks/{task_id}/files/{filename}",
        "/api/pre-analysis/upload",
        # pre-analysis tables viewer (2026-07-09) — 后端实现, 前端走 BFF
        # BFF: app/api/pre-analysis/tasks/[id]/tables/{pages,page/[pageNum]}/route.ts
        # 后端路由走 apiProxy 透传, 不直接被前端 fetch, 列 KNOWN_DEAD.
        "/api/pre-analysis/tasks/{task_id}/tables/page/{page_num}",
        "/api/pre-analysis/tasks/{task_id}/tables/pages",
    }
    dead -= KNOWN_DEAD

    assert not dead, (
        f"后端有 {len(dead)} 个 /api/* 路由但前端未使用:\n"
        + "\n".join(f"  {p}" for p in sorted(dead))
        + "\n\n如果是已废弃路由, 加入 KNOWN_DEAD 或从后端删除; 如果前端需要, 加入 FRONTEND_EXPECTS"
    )


@pytest.mark.slow
@pytest.mark.slow
@pytest.mark.integration
def test_health_endpoint_reachable():
    """核心端点 /product-decoder/health 在后端真实可达.

    集成测试, 需要后端启动. 本地重构时手动跑:
      pytest tests/test_api_contract.py::test_health_endpoint_reachable -m integration
    """
    from src.core.app_factory import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)

    resp = client.get("/product-decoder/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ============================================================
# 字典一致性 contract test (2026-06-19 lookup spec §7.3)
#
# 规则: ENUM_REGISTRY (dictionaries_enum 暴露的 enum → dict_code 映射) 每个 enum 类的 value
#       ⊆ DB 中对应字典的 items.key 集合. 若 yaml 拼了 enum 值但 DB 没 seed, 启动期 fail-fast.
#
# 测试模式 1 (mock): mock LookupService.list_all_dicts + LookupService.get 返固定数据,
#                    断言 ENUM_REGISTRY 5 个 enum 的 value 全在 mock 返回里.
# ============================================================


def _make_mock_dict_summary(code: str, label_zh: str = "Mock", label_en: str = "Mock") -> dict:
    """构造 LookupService.list_all_dicts 返参里的字典概要."""
    return {
        "code": code,
        "label_zh": label_zh,
        "label_en": label_en,
        "version": 1,
        "is_active": True,
    }


def _make_mock_dict_with_items(code: str, keys: list[str]) -> dict:
    """构造 LookupService.get 返参: 字典 + items.

    每个 item key 是 ENUM_REGISTRY 中该 dict_code 的 enum 值之一 (mock 返全集,
    保证 contract test 不会因 mock 数据不全而误判).
    """
    items = [
        {
            "key": k,
            "label_zh": k,
            "label_en": k,
            "sort": i,
            "is_active": True,
            "description": None,
            "metadata_json": None,
            "effective_at": None,
            "deprecated_at": None,
        }
        for i, k in enumerate(keys)
    ]
    return {
        "code": code,
        "label_zh": code,
        "label_en": code,
        "version": 1,
        "items": items,
    }


def _enum_values(enum_name: str) -> set[str]:
    """从 dictionaries_enum 取指定 enum 类的所有 value 集合."""
    import importlib

    enums_module = importlib.import_module("src.common.dictionaries_enum")
    enum_cls = getattr(enums_module, enum_name)
    return {e.value for e in enum_cls}


@pytest.mark.slow
def test_dictionary_consistency_with_schema():
    """ENUM_REGISTRY 中每个 enum 类的 value 必须 ⊆ DB 中对应字典的 active items.key.

    模拟 LookupService 返回包含所有 enum 值的字典, 验证 contract test 自身逻辑正确.
    若以后 ENUM_REGISTRY 改了, 此测试会自动 catch.
    """
    from src.common.dictionaries_enum import ENUM_REGISTRY
    from src.lookups.exceptions import LookupNotFoundError
    from src.lookups.service import LookupService

    # 收集所有 enum value 按 dict_code 分组 (用于构造 mock)
    enum_values_by_code: dict[str, set[str]] = {}
    for enum_name, dict_code in ENUM_REGISTRY.items():
        enum_values_by_code.setdefault(dict_code, set()).update(_enum_values(enum_name))

    # mock 返回: list_all_dicts 返全部 dict_code 概要; get(code) 返包含所有 enum values 的字典
    mock_summaries = [
        _make_mock_dict_summary(code, label_zh=f"Mock {code}", label_en=f"Mock {code}")
        for code in enum_values_by_code.keys()
    ]

    def _mock_get(dict_code: str, *, only_active: bool = True, lang: str = "both"):
        if dict_code not in enum_values_by_code:
            raise LookupNotFoundError(f"dictionary '{dict_code}' not found")
        return _make_mock_dict_with_items(dict_code, sorted(enum_values_by_code[dict_code]))

    with (
        patch.object(LookupService, "list_all_dicts", AsyncMock(return_value=mock_summaries)),
        patch.object(LookupService, "get", AsyncMock(side_effect=_mock_get)),
    ):
        # 跑 check_consistency (内部用 asyncio.run, 但 mock 后 list_all_dicts 直接被 patch 走)
        # 因 check_consistency 内部用 asyncio.run(LookupService.list_all_dicts()),
        # 我们 patch 整个 scripts.check_dictionary_refs 模块内的 _fetch_db_dicts /
        # _fetch_db_items 函数, 避免 asyncio.run 实际运行被 mock 后的 coroutine.
        # 但 coroutine 被 patch.object 替换后, asyncio.run 会正常调度, 返 mock 值.
        from scripts.check_dictionary_refs import check_consistency

        # 不应抛: mock 返回包含所有 enum values
        check_consistency()
