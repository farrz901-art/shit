"""项目配置集中管理 (ARCH-003 + ARCH-002 完整迁移).

所有 os.getenv 调用迁移至此, 避免散落 20+ 文件.

调用模式 (2026-06-26 ARCH-002 完整迁移, 30 个文件):
    from src.config.settings import settings
    from src.common import defaults
    # env > settings > defaults 三级 fallback. 保留 os.getenv 兜底让
    # monkeypatch.setenv 测试生效 (settings 单例 reload 不支持).
    value = os.getenv("X") or settings.x or defaults.DEFAULT_X

settings.py 字段定义:
    每个字段 default_factory 同时调用 os.getenv() + defaults fallback,
    所以 settings 字段本身已经带 fallback. 业务代码只读 settings 也对,
    但保留 os.getenv 兜底更稳 (测试 setenv 优先生效).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from src.common import defaults

# ═══════════════════════════════════
# Ingest (Paths / CadConfig / ArchiveConfig) — ARCH-004 迁移
# 旧 src/ingest/config.py + src/config_legacy.py 走 config.toml
# 迁到 env, 业务代码全走 settings.paths / settings.cad_config / settings.archive_config
# ═══════════════════════════════════


@dataclass(frozen=True)
class Paths:
    """路径配置 (ARCH-004: 原 [paths] 段迁到 env)"""

    input_dir: Path
    output_dir: Path


@dataclass(frozen=True)
class CadConfig:
    """CAD 相关配置 (ARCH-004: 原 [cad] 段 + env ODA_WIN_PATH / ODA_UNIX_PATH)

    oda_win_path / oda_unix_path 是用户显式配置的 ODA File Converter 路径.
    空 = 走 ezdxf 系统默认.
    """

    oda_win_path: str
    oda_unix_path: str


@dataclass(frozen=True)
class ArchiveConfig:
    """压缩包解压配置 (ARCH-004: 原 [archive] 段迁到 env)

    max_depth: 嵌套解压深度 (1 = 不递归)
    max_total_size: 解压总大小上限 (字节, 防 zip bomb)
    max_file_count: 解压文件总数上限 (防 zip bomb)
    """

    max_depth: int
    max_total_size: int
    max_file_count: int


@dataclass
class Settings:
    """集中管理 env 配置.

    用法:
        from src.config.settings import settings
        host = settings.redis_host       # 代替 os.getenv("REDIS_HOST", "localhost")
    """

    # ═══════════════════════════════════
    # 环境 / CORS
    # ═══════════════════════════════════
    env: str = field(
        default_factory=lambda: os.getenv("ENV", "development"),
    )
    cors_allow_origins: str = field(
        default_factory=lambda: os.getenv("CORS_ALLOW_ORIGINS", ""),
    )

    # ═══════════════════════════════════
    # Ingest (ARCH-004 迁移)
    # ═══════════════════════════════════
    paths: Paths = field(
        default_factory=lambda: Paths(
            input_dir=Path(os.getenv("INGEST_INPUT_DIR", "./ingest_inputs")),
            output_dir=Path(os.getenv("INGEST_OUTPUT_DIR", "./ingest_outputs")),
        ),
    )
    cad_config: CadConfig = field(
        default_factory=lambda: CadConfig(
            oda_win_path=os.getenv("ODA_WIN_PATH", defaults.DEFAULT_ODA_WIN_PATH).strip(),
            oda_unix_path=os.getenv("ODA_UNIX_PATH", defaults.DEFAULT_ODA_UNIX_PATH).strip(),
        ),
    )
    archive_config: ArchiveConfig = field(
        default_factory=lambda: ArchiveConfig(
            max_depth=int(os.getenv("ARCHIVE_MAX_DEPTH", "1")),
            max_total_size=int(os.getenv("ARCHIVE_MAX_TOTAL_SIZE", str(1 << 30))),
            max_file_count=int(os.getenv("ARCHIVE_MAX_FILE_COUNT", "10000")),
        ),
    )

    # ═══════════════════════════════════
    # Redis
    # ═══════════════════════════════════
    redis_host: str = field(
        default_factory=lambda: os.getenv("REDIS_HOST", "localhost"),
    )
    redis_port: int = field(
        default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")),
    )
    redis_password: str = field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD", ""),
    )
    redis_max_connections: int = field(
        default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "20")),
    )
    redis_socket_timeout: float = field(
        default_factory=lambda: float(os.getenv("REDIS_SOCKET_TIMEOUT", "2")),
    )
    redis_connect_timeout: float = field(
        default_factory=lambda: float(os.getenv("REDIS_CONNECT_TIMEOUT", "2")),
    )
    redis_connect_timeout_pubsub: float = field(
        default_factory=lambda: float(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
    )
    redis_circuit_open_seconds: float = field(
        default_factory=lambda: float(os.getenv("REDIS_CIRCUIT_OPEN_SECONDS", "60")),
    )

    # ═══════════════════════════════════
    # Dify
    # ═══════════════════════════════════
    dify_base_url: str = field(
        default_factory=lambda: os.getenv("DIFY_BASE_URL", defaults.DEFAULT_DIFY_BASE_URL),
    )
    dify_dataset_api_key: str = field(
        default_factory=lambda: os.getenv("DIFY_DATASET_API_KEY", ""),
    )
    dify_chat_api_key: str = field(
        default_factory=lambda: os.getenv("DIFY_CHAT_API_KEY", ""),
    )
    dify_user_id: str = field(
        default_factory=lambda: os.getenv("DIFY_USER_ID", defaults.DEFAULT_DIFY_USER_ID),
    )
    dify_query_cache_ttl: int = field(
        default_factory=lambda: int(os.getenv("DIFY_QUERY_CACHE_TTL", "600")),
    )

    # ═══════════════════════════════════
    # Object Store (MinIO / LocalFS)
    # ═══════════════════════════════════
    object_store_backend: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_BACKEND", "local"),
    )
    object_store_local_root: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_LOCAL_ROOT", "./ingest_uploads"),
    )
    object_store_s3_endpoint: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_S3_ENDPOINT", "http://localhost:9000"),
    )
    object_store_s3_access_key: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_S3_ACCESS_KEY", "minioadmin"),
    )
    object_store_s3_secret_key: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_S3_SECRET_KEY", "minioadmin"),
    )
    object_store_s3_bucket: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest"),
    )
    object_store_s3_region: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_S3_REGION", "us-east-1"),
    )
    object_store_s3_use_ssl: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_S3_USE_SSL", "false"),
    )
    object_store_stage_root: str = field(
        default_factory=lambda: os.getenv("OBJECT_STORE_STAGE_ROOT", "/tmp/minio_stage"),
    )

    # ═══════════════════════════════════
    # LLM (OpenAI / Ollama)
    # ═══════════════════════════════════
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", defaults.DEFAULT_LLM_MODEL),
    )
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", ""),
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", ""),
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", ""),
    )

    # ═══════════════════════════════════
    # Embedding
    # ═══════════════════════════════════
    embed_model: str = field(
        default_factory=lambda: os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_OPENAI),
    )
    embed_api_key: str = field(
        default_factory=lambda: os.getenv("EMBED_API_KEY", ""),
    )
    embed_base_url: str = field(
        default_factory=lambda: os.getenv("EMBED_BASE_URL", ""),
    )
    embed_dimensions: int = field(
        default_factory=lambda: int(os.getenv("EMBED_DIMENSIONS", "1024")),
    )
    embed_cache_ttl: int = field(
        default_factory=lambda: int(os.getenv("EMBED_CACHE_TTL", str(7 * 86400))),
    )

    # ═══════════════════════════════════
    # PG / Postgres
    # ═══════════════════════════════════
    pg_host: str = field(
        default_factory=lambda: os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST),
    )
    pg_port: int = field(
        default_factory=lambda: int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))),
    )
    pg_user: str = field(
        default_factory=lambda: os.getenv("PG_USER", defaults.DEFAULT_PG_USER),
    )
    pg_password: str = field(
        default_factory=lambda: os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD),
    )
    pg_database: str = field(
        default_factory=lambda: os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE),
    )

    # ═══════════════════════════════════
    # Neo4j
    # ═══════════════════════════════════
    neo4j_uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", defaults.DEFAULT_NEO4J_URI),
    )
    neo4j_user: str = field(
        default_factory=lambda: os.getenv("NEO4J_USER", defaults.DEFAULT_NEO4J_USER),
    )
    neo4j_password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", defaults.DEFAULT_NEO4J_PASSWORD),
    )
    neo4j_database: str = field(
        default_factory=lambda: os.getenv("NEO4J_DATABASE", defaults.DEFAULT_NEO4J_DATABASE),
    )

    # ═══════════════════════════════════
    # Auth / Password / Token
    # ═══════════════════════════════════
    rag_admin_token: str = field(
        default_factory=lambda: os.getenv("RAG_ADMIN_TOKEN", ""),
    )
    rag_dev_auth: str = field(
        default_factory=lambda: os.getenv("RAG_DEV_AUTH", ""),
    )
    rag_auto_create_schema: str = field(
        default_factory=lambda: os.getenv("RAG_AUTO_CREATE_SCHEMA", ""),
    )
    password_min_length: int = field(
        default_factory=lambda: int(os.getenv("PASSWORD_MIN_LENGTH", "8")),
    )
    password_bcrypt_rounds: int = field(
        default_factory=lambda: int(os.getenv("PASSWORD_BCRYPT_ROUNDS", "12")),
    )
    password_reset_expires_hours: int = field(
        default_factory=lambda: int(os.getenv("PASSWORD_RESET_EXPIRES_HOURS", "1")),
    )
    invite_expires_days: int = field(
        default_factory=lambda: int(os.getenv("INVITE_EXPIRES_DAYS", "7")),
    )
    deletion_grace_days: int = field(
        default_factory=lambda: int(os.getenv("DELETION_GRACE_DAYS", "7")),
    )
    email_change_expires_days: int = field(
        default_factory=lambda: int(os.getenv("EMAIL_CHANGE_EXPIRES_DAYS", "7")),
    )
    deletion_restore_expires_days: int = field(
        default_factory=lambda: int(os.getenv("DELETION_RESTORE_EXPIRES_DAYS", "7")),
    )
    token_cache_ttl: int = field(
        default_factory=lambda: int(os.getenv("TOKEN_CACHE_TTL", "21600")),
    )

    # ═══════════════════════════════════
    # Mem0
    # ═══════════════════════════════════
    mem0_collection_name: str = field(
        default_factory=lambda: os.getenv("MEM0_COLLECTION_NAME", defaults.DEFAULT_MEM0_COLLECTION_NAME),
    )
    mem0_ready_ttl: int = field(
        default_factory=lambda: int(os.getenv("MEM0_READY_TTL", "3600")),
    )

    # ═══════════════════════════════════
    # Permission Cache
    # ═══════════════════════════════════
    perm_cache_ttl: int = field(
        default_factory=lambda: int(os.getenv("PERM_CACHE_TTL", "60")),
    )

    # ═══════════════════════════════════
    # Rate Limiting
    # ═══════════════════════════════════
    rl_login_window: int = field(
        default_factory=lambda: int(os.getenv("RL_LOGIN_WINDOW", "900")),
    )
    rl_login_threshold: int = field(
        default_factory=lambda: int(os.getenv("RL_LOGIN_THRESHOLD", "5")),
    )
    rl_forgot_password_window: int = field(
        default_factory=lambda: int(os.getenv("RL_FORGOT_PASSWORD_WINDOW", "900")),
    )
    rl_forgot_password_threshold: int = field(
        default_factory=lambda: int(os.getenv("RL_FORGOT_PASSWORD_THRESHOLD", "5")),
    )
    rl_reset_window: int = field(
        default_factory=lambda: int(os.getenv("RL_RESET_WINDOW", "3600")),
    )
    rl_reset_threshold: int = field(
        default_factory=lambda: int(os.getenv("RL_RESET_THRESHOLD", "3")),
    )
    rl_dict_admin_window: int = field(
        default_factory=lambda: int(os.getenv("RL_DICT_ADMIN_WINDOW", "60")),
    )
    rl_dict_admin_threshold: int = field(
        default_factory=lambda: int(os.getenv("RL_DICT_ADMIN_THRESHOLD", "60")),
    )

    # ═══════════════════════════════════
    # Logging
    # ═══════════════════════════════════
    log_json: str = field(
        default_factory=lambda: os.getenv("LOG_JSON", "false"),
    )
    log_to_db: str = field(
        default_factory=lambda: os.getenv("LOG_TO_DB", "true"),
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
    )
    grafana_enabled: str = field(
        default_factory=lambda: os.getenv("GRAFANA_ENABLED", "false"),
    )

    # ═══════════════════════════════════
    # Web
    # ═══════════════════════════════════
    web_base_url: str = field(
        default_factory=lambda: os.getenv("WEB_BASE_URL", defaults.DEFAULT_WEB_BASE_URL),
    )

    # ═══════════════════════════════════
    # Lookups / Dictionary
    # ═══════════════════════════════════
    dictionary_readonly: str = field(
        default_factory=lambda: os.getenv("DICTIONARY_READONLY", ""),
    )

    # ═══════════════════════════════════
    # Telemetry / Langfuse
    # ═══════════════════════════════════
    langfuse_public_key: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    )
    langfuse_secret_key: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", ""),
    )
    langfuse_host: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_HOST", defaults.DEFAULT_LANGFUSE_HOST),
    )


# 单例, 启动时加载一次
settings = Settings()
