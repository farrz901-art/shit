"""RAG 项目全部"魔法字符串"默认值的唯一来源

代码里禁止直接写死 URL/port/默认值常量, 必须从这个文件 import。
理由:
1. 集中改动, 改一个默认值不需要在 6 个文件里找
2. 单元测试可以 monkeypatch 整个模块
3. 配置文件 / env var / 代码默认值的优先级一目了然

约定:
- 常量名 = "DEFAULT_" + 用法
- 数字默认值用 int/float 类型, 别用字符串 (避免 int() 调用)
- 空字符串默认值用空串, 含义是"用户没配, 让 lib 自己报错"
"""

from __future__ import annotations

# =============================================================================
# OpenAI / LLM
# =============================================================================
DEFAULT_OPENAI_API_KEY: str = ""  # 空 = 没配, OpenAI SDK 会 401
DEFAULT_OPENAI_BASE_URL: str = ""  # 空 = 用 OpenAI 官方
DEFAULT_LLM_MODEL_OPENAI: str = "gpt-4o-mini"
DEFAULT_LLM_MODEL_OLLAMA: str = "llama3"
DEFAULT_LLM_TYPE: str = "openai"  # openai / ollama
# (2026-06-26 ERR-005) OpenAILLM 默认 max_tokens 兜底, 防止用户提交任意长 prompt
# 导致 token 计费无限生成. 4096 是大多数 OpenAI 模型一次回复的上限.
DEFAULT_OPENAI_MAX_TOKENS: int = 4096

# =============================================================================
# Embedding
# =============================================================================
# 只走 OpenAI 兼容协议 (HF 已移除)
DEFAULT_EMBED_MODEL_OPENAI: str = "text-embedding-3-small"
DEFAULT_EMBED_BATCH_SIZE: int = 32
# EMBED_DIMENSIONS 没设 = None, 让 SDK 用模型自带维度 (text-embedding-3-small=1536)

# =============================================================================
# pgvector
# =============================================================================
DEFAULT_PG_HOST: str = "localhost"
DEFAULT_PG_PORT: int = 5432
DEFAULT_PG_USER: str = "postgres"
DEFAULT_PG_PASSWORD: str = "postgres"
DEFAULT_PG_DATABASE: str = "rag"

# =============================================================================
# Neo4j
# =============================================================================
DEFAULT_NEO4J_URI: str = "bolt://localhost:7687"
DEFAULT_NEO4J_USER: str = "neo4j"
DEFAULT_NEO4J_PASSWORD: str = "neo4j"
DEFAULT_NEO4J_DATABASE: str = "neo4j"
# (2026-06-26 ERR-002) Neo4j 驱动超时, 防止宕机时挂 30s 默认值耗尽线程池.
# 与 Redis facade 2s 超时对齐, 量级略宽因 Neo4j 握手更重.
DEFAULT_NEO4J_CONNECTION_TIMEOUT: int = 5
DEFAULT_NEO4J_CONNECTION_ACQUISITION_TIMEOUT: int = 30
# Neo4j driver 推荐连接最大生命周期 30min, 防止 stale 连接
DEFAULT_NEO4J_MAX_CONNECTION_LIFETIME: int = 1800
# (2026-06-26 ERR-004) Neo4j 熔断器窗口 (秒), 跟 Redis facade 30s 对齐.
# 期间 Neo4jStore.driver 直接抛 Neo4jCircuitOpen, 不再尝试 GraphDatabase.driver()
# 避免宕机时每秒数十个请求 spam socket 连接.
DEFAULT_NEO4J_CIRCUIT_OPEN_SECONDS: int = 30

# =============================================================================
# Dify
# =============================================================================
# 接入点: src/rag/integrations/dify_client.py + scripts/batch_rag_eval.py
DEFAULT_DIFY_DATASET_API_KEY: str = ""  # 空 = 没配, DifyClient 构造会抛 ValueError
DEFAULT_DIFY_BASE_URL: str = "http://localhost/v1"  # 自建 Dify 默认; Dify Cloud 用 https://api.dify.ai/v1
DEFAULT_DIFY_USER_ID: str = "rag-eval-script"


# =============================================================================
# Mem0 (self-host pgvector, 2026-06-16)
# =============================================================================
# mem0 self-host: 复用项目已有 pgvector 容器 + embedder, 不需要 MEM0_API_KEY
DEFAULT_MEM0_COLLECTION_NAME: str = "mem0_memories"
DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
DEFAULT_MEM0_SEARCH_LIMIT: int = 5
# mem0 embedder: provider 探测 (ollama 走 ollama, 其它全走 openai 兼容)
# 显式设 MEM0_EMBED_PROVIDER 可强制, 值: openai / ollama
DEFAULT_MEM0_EMBED_PROVIDER: str = ""
# mem0 可用独立 embedder 模型 (不指定时跟主 RAG 共用 EMBED_MODEL)
DEFAULT_MEM0_EMBED_MODEL: str = ""

# =============================================================================
# ODA File Converter (CAD DWG 转换)
# =============================================================================
# 空 = 让 ezdxf 走系统默认 (Windows: C:\Program Files\ODA\ODAFileConverter\...)
# 机器特定路径, 配到 .env 而非 config.toml
DEFAULT_ODA_WIN_PATH: str = ""
DEFAULT_ODA_UNIX_PATH: str = ""

# =============================================================================
# Langfuse
# =============================================================================
DEFAULT_LANGFUSE_PUBLIC_KEY: str = ""
DEFAULT_LANGFUSE_SECRET_KEY: str = ""
DEFAULT_LANGFUSE_HOST: str = "https://cloud.langfuse.com"

# =============================================================================
# Ollama
# =============================================================================
DEFAULT_OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

# =============================================================================
# Chat Share (2026-06-16) — 公开 chat 对话分享链接
# =============================================================================
# 短 share_id 长度 (nanoid 12 字符熵 ~71 bits, 路由 /chat/s/{share_id})
DEFAULT_CHAT_SHARE_ID_LENGTH: int = 12
# 默认 TTL 7 天 (time-boxed share, 过期后自动失效)
DEFAULT_CHAT_SHARE_TTL_DAYS: int = 7
# 公开页 base URL (前端 share 路由前缀), 来自环境变量 WEB_BASE_URL
DEFAULT_WEB_BASE_URL: str = "http://localhost:3000"
# 文件上传大小上限 20MB (跟 Dify Files API 对齐)
DEFAULT_CHAT_FILE_MAX_BYTES: int = 20 * 1024 * 1024
# 默认 locale (前端 share 链接前缀 /{locale}/chat/s/{id})
DEFAULT_CHAT_SHARE_LOCALE: str = "zh"
