"""chat_share 子包 — chat 对话公开分享 (2026-06-16)

- schemas:   Pydantic 模型 (CreateShareRequest / ShareResponse / ...)
- models:    SQLAlchemy ORM (ChatShare)
- repo:      ORM CRUD helpers (save / get_by_id / delete)
- service:   业务核心 (create_share / get_share / revoke_share / upload_to_dify)
- router:    FastAPI 4 端点 (POST/GET/DELETE shares + POST files)
"""
