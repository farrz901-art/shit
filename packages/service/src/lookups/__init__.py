"""字典模块: DB 唯一事实源, 通用业务字典 (2026-06-19 lookup spec)

模块组成:
- models: Dictionary / DictionaryItem SQLAlchemy 模型
- schemas: Pydantic schema (T5 写)
- service: LookupService (CRUD + cache 协同 + audit)
- cache: LookupCache (Redis L2 + 进程内 L1)
- safety_guard: 6 层防御 (鉴权 + readonly + 二次确认 + 引用 + 乐观锁 + rate limit)
- exceptions: LookupSafetyError / LookupNotFoundError
- audit: 复用 audit_log 表写字典变更
- router: GET /api/lookups/* (T5)
- admin_router: POST/PATCH/DELETE /api/admin/dicts/* (T6)

业务使用 (T4 已就绪):
    from src.lookups.service import LookupService
    items = await LookupService.get("approval_review_status", only_active=True, lang="both")
"""
