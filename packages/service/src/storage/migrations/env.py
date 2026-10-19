# ruff: noqa: E402
# alembic 子进程不继承 main.py 的 load_dotenv, 显式加载
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv(".env.local", override=False)

from logging.config import fileConfig

from alembic import context

from src.approvals.models import Approval  # noqa: F401  # pyright: ignore[reportUnusedImport]

# 显式 import 业务 model, 让 Base.metadata 注册它们 (Alembic autogenerate 才能识别)
# noqa 标记避免 ruff/pyright 未使用 import 警告 (import 的副作用是 model 注册)
from src.auth.models import User  # noqa: F401  # pyright: ignore[reportUnusedImport]
from src.chat.models import Conversation, Message  # noqa: F401  # pyright: ignore[reportUnusedImport]
from src.common.db_url import get_rag_db_url
from src.eval.models import Evaluation, EvaluationSample  # noqa: F401  # pyright: ignore[reportUnusedImport]
from src.ingest.pdf_processing.models import (
    IngestTask,  # noqa: F401  # pyright: ignore[reportUnusedImport]  # (2026-07-06) commit 247e63c2 移到了 pdf_processing/ 子包
)
from src.kg.audit_models import KgAudit  # noqa: F401  # pyright: ignore[reportUnusedImport]
from src.storage import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_rag_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section) or {}
    try:
        db_url = get_rag_db_url()
    except Exception as e:
        raise RuntimeError(
            f"无法构造 PG URL: {type(e).__name__}: {e}\n"
            f"  请检查 packages/service/.env.local 是否配置 PG_HOST/PG_PORT/"
            f"PG_USER/PG_PASSWORD/PG_DATABASE"
        ) from e
    configuration["sqlalchemy.url"] = db_url
    try:
        connectable = engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    except Exception as e:
        raise RuntimeError(
            f"无法创建 SQLAlchemy engine: {type(e).__name__}: {e}\n"
            f"  常见原因:\n"
            f"  1. PG 密码错 / PG 未启动 / .env.local 未配置\n"
            f"  2. PG_HOST 写成了带 scheme 的 URL (例如 http://192.168.3.52),"
            f" 应留裸 host (192.168.3.52); SA 解析 port 失败会得到空字符串"
        ) from e

    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()
    except Exception as e:
        raise RuntimeError(
            f"alembic migration 执行失败: {type(e).__name__}: {e}\n"
            f"  常见原因: PG 不可达 / 数据库不存在 / migration 文件语法错"
        ) from e


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
