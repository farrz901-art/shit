"""FastAPI app factory

从 product_decoders/app.py 提取 create_app() 工厂, 剥离 ConfigLoader / ProductDecoder 业务逻辑.
提供无业务依赖的 FastAPI 应用创建入口, 供 main.py 和测试使用.

本文件约定:
- 业务代码使用 loguru (2026-06-17 logging spec)
- 不在本文件引入 ConfigLoader / ProductDecoder
- lifespan 由 src.core.lifespan 提供
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from .lifespan import _lifespan


async def _sa_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """SQLAlchemy 全局兜底 (2026-06-18): 登录 500 时让 traceback 真正可读.

    参数类型故意写 Exception 不是 SQLAlchemyError: FastAPI add_exception_handler
    的 ExceptionHandler 类型签名要 Callable[[Request, Exception], Response],
    写 SQLAlchemyError (narrower) pyright 不认. 运行时仍只接 SQLAlchemyError 实例
    (add_exception_handler(SQLAlchemyError, ...) 按类注册).

    之前 /api/permissions/me 报 500, 控制台只见 SQL 详情 (SELECT ... WHERE id=131)
    和 SQLAlchemy 链下层堆栈, 看不到真正的 exception type / message, 排查要靠猜.

    行为:
    1. exc_info=True 强制 logger 吐完整 traceback (含根因 __cause__ / __context__ 链)
    2. 响应只返 {detail: <类型>}, 不泄露原始 SQL/字段, 避免生产环境泄漏 schema
    3. 不阻断 FastAPI 默认 500 行为, 仅多一份可读日志
    """
    logger.opt(exception=True).error(
        "SQLAlchemy 未捕获异常: {} | {} {}",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"数据库错误: {type(exc).__name__}"},
    )


def create_app() -> FastAPI:
    """FastAPI 工厂: 返回完整配置的 FastAPI 应用实例"""
    app = FastAPI(
        title="RAG + 产品订货号解析服务",
        summary="RAG 检索增强 + 产品订货号解析的统一后端 API",
        version="0.2.0",  # 硬编, 后续 ops spec 改动态
        description=(
            "## 服务范围\n\n"
            "本服务为前端 Dify 工作流和管理后台提供以下能力:\n\n"
            "- **RAG 检索增强生成** (`/api/v1/*`): 查询 / 摄取 (LangChain LCEL)\n"
            "- **产品订货号解码** (`/decode` `/series`): 配置驱动的多厂商解析\n"
            "- **记忆系统** (`/api/memory/*`): Mem0 集成, 跨会话用户记忆\n"
            "- **知识图谱** (`/api/kg/*`): Neo4j 集成, 三元组 CRUD\n"
            "- **评估批** (`/api/evaluate/*`): 上传 CSV 跑 DeepEval 评估\n"
            "- **Ingest 子系统** (`/api/ingest/*`): 文件格式转换 (PDF/DOCX/CAD)\n"
            "- **聊天分享 + 文件上传** (`/api/chat/*`): 对话快照 + MinIO 集成\n"
            "- **审核工作流** (`/api/approvals/*`): 提交 / 批准 / 拒绝 / 重试\n"
            "- **权限管理** (`/api/permissions/*` + `/api/roles/*`): RBAC 配置\n"
            "- **用户管理** (`/api/admin/*`): super_admin 后台\n"
            "- **账号系统** (`/api/account/*`): 登录 / 登出 / 找回密码\n"
            "- **监控检查** (`/api/health/*`): 5 类系统指标\n\n"
            "## 鉴权\n\n"
            "大部分端点依赖 `CurrentUser` 依赖项, 通过 `x-user-token` header "
            "或 `rag_user_token` cookie 鉴权. 详情见各端点说明.\n\n"
            "## 错误码\n\n"
            "| 码 | 含义 | 触发场景 |\n"
            "|----|------|----------|\n"
            "| 400 | 请求参数错误 | 文件类型不支持 / 路径越权 / reset token 失效 |\n"
            "| 401 | 未登录 / token 无效 | `x-user-token` 缺失或不在 users 表 |\n"
            "| 403 | 权限不足 | require_page 失败 / require_super_admin 失败 |\n"
            "| 404 | 资源不存在 | task / approval / role / user 不存在 |\n"
            "| 409 | 状态冲突 | 创建重复 / 操作非法状态机转换 |\n"
            "| 413 | 文件过大 | ingest / chat 文件超过 20-200MB |\n"
            "| 422 | Pydantic 校验失败 | 字段类型错 / 长度越界 / 枚举值非法 |\n"
            "| 500 | 服务器内部错误 | LLM 拒抽 / Dify 503 / 未捕获异常 |\n"
            "| 503 | 外部依赖不可用 | MinIO / Neo4j / Dify / Mem0 不可达 |\n"
        ),
        contact={
            "name": "RAG Backend Team",
            "url": "https://github.com/forkai/rag",
            "email": "rag-team@example.com",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        openapi_tags=[
            {"name": "rag", "description": "RAG 检索 + 摄取 (LangChain LCEL, 内部脚本用)"},
            {"name": "kg", "description": "知识图谱 CRUD (Neo4j 驱动)"},
            {"name": "evaluate", "description": "评估批管理 (上传 CSV + DeepEval 5 指标)"},
            {"name": "ingest", "description": "文档摄取 (PDF/DOCX/CAD/Archive -> Markdown/JSON)"},
            {"name": "auth", "description": "匿名 token + 老 cookie 迁移 (灰度期)"},
            {"name": "account", "description": "账号登录 / 登出 / 找回密码 / 当前用户"},
            {"name": "admin", "description": "用户 + 邀请管理 (super_admin 限定)"},
            {"name": "invite", "description": "公开 invite 兑换 (无需登录)"},
            {"name": "approvals", "description": "审核工作流 (提交 -> 批准 -> 后台应用)"},
            {"name": "memory", "description": "Mem0 记忆管理 (登录用户限定)"},
            {"name": "chat-share", "description": "聊天快照分享 + 文件直传 MinIO"},
            {"name": "permissions", "description": "RBAC 角色 + 权限矩阵 (super_admin 限定)"},
            {"name": "health", "description": "系统级监控检查 (super_admin 限定)"},
            {"name": "output", "description": "Pipeline 产物只读 API (管理后台用)"},
        ],
        servers=[
            {"url": "http://localhost:8000", "description": "本地开发"},
            {"url": "https://staging-rag.example.com", "description": "Staging"},
            {"url": "https://rag.example.com", "description": "生产"},
        ],
        lifespan=_lifespan,
    )

    # SEC-005: ENV 隔离, production 只从 CORS_ALLOW_ORIGINS 白名单读
    # development 自动放行 localhost, 不依赖环境变量
    # 注意: 这里直接读 os.getenv 不走 settings 单例, 因为 settings 在 import 时已 freeze,
    # test 用 patch.dict("os.environ") 改 ENV 需要 create_app() 时重新读 env, 否则永远拿到启动时的值.
    env_value = os.getenv("ENV", "development")
    if env_value == "production":
        cors_str = os.getenv("CORS_ALLOW_ORIGINS", "")
        allow_origins = [o.strip() for o in cors_str.split(",") if o.strip()] if cors_str else []
    else:
        allow_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,  # 显式列表, 不用 *
        allow_credentials=True,  # 关键: 允许 cookie 跨域 (P0 任务 8 灰度期)
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["content-type"],
        max_age=600,
    )

    # 注册 SQLAlchemy 全局异常 handler (2026-06-18): 让 500 的 traceback 真可读
    app.add_exception_handler(SQLAlchemyError, _sa_exception_handler)

    # 注入 RequestID + user_id contextvars (2026-06-17 logging spec §6)
    # 防循环: middleware 顶层 import 会触发 middleware 整模块装载
    from src.core.middleware import RequestIDMiddleware  # noqa: E402

    app.add_middleware(RequestIDMiddleware)

    # 全局 exception handler (2026-06-17 logging spec §7): 处理 HTTPException / validation / 5xx
    # 防循环: errors 模块顶层装载触发 handler 注册链路
    from src.core.errors import install_error_handlers  # noqa: E402

    install_error_handlers(app)

    # 挂载管理后台只读 API (本模块自有)
    # 重依赖 lazy: product_decoders 启动慢 (~300ms 含 yaml loader + schema 校验)
    from src.product_decoders.output_api import router as output_router  # noqa: E402

    app.include_router(output_router)

    # 挂载解码器路由 (/decode, /series, /health)
    # 重依赖 lazy: 同上 product_decoders
    from src.product_decoders.router import router as decoder_router  # noqa: E402

    app.include_router(decoder_router)

    # 挂载所有 RAG 子模块路由
    # 防循环: src.__init__ 顶层注 router 触发所有 router 模块装载
    from src import register_routers  # noqa: E402

    register_routers(app)

    return app
