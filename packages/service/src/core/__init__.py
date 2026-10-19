"""跨子系统公共组件 (2026-06-17 logging spec)

- logging_context: contextvars 持有请求级 request_id / user_id
- logging: loguru 配置 + InterceptHandler + PG sinks + PII scrub
- middleware: RequestIDMiddleware
- audit: @audited decorator + AuditContext
- errors: FastAPI global exception handlers
"""
