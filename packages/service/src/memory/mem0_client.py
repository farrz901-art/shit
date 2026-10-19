"""Mem0 记忆层封装 (self-host pgvector 模式, 2026-06-16)

跟项目已有 pgvector 容器 + embedder 复用. 每个 (user_id) 缓存一个 Memory 实例.
embedder 从 EMBED_MODEL / EMBED_API_KEY / EMBED_BASE_URL 读配置 (跟主 RAG embedding 共用).
不发明新的 env key.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger
from mem0 import Memory  # mem0ai PyPI 包, import 路径仍是 mem0

from ..common import defaults

# 诊断日志 (2026-06-17): 排查 memory add 静默失败, 打印拼出来的 pgvector/embedder/llm 配置 (脱敏).
# (2026-06-23) 加 _mask_key 脱敏常量: api_key 前 4 + **** + 后 4
FOUR = 4
EIGHT = 8


def _build_embedder_config() -> dict[str, Any]:
    """拼 mem0 embedder config. provider 只支持 openai / ollama.

    读 EMBED_MODEL / EMBED_API_KEY / EMBED_BASE_URL (跟主 RAG embedding 共用, 不额外发明 env).
    """
    model = os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_OPENAI)
    lower = model.lower()
    if lower.startswith("ollama/"):
        return {
            "provider": "ollama",
            "config": {
                "model": model.removeprefix("ollama/"),
                "ollama_base_url": os.getenv("OLLAMA_BASE_URL", defaults.DEFAULT_OLLAMA_BASE_URL),
            },
        }

    # 其它全部走 openai 兼容协议
    cfg: dict[str, Any] = {
        "provider": "openai",
        "config": {
            "model": model,
            "api_key": os.getenv("EMBED_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""),
        },
    }
    base_url = os.getenv("EMBED_BASE_URL", "").strip() or os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        cfg["config"]["openai_base_url"] = base_url
    return cfg


def _build_config() -> dict[str, Any]:
    """从 env + defaults 拼 mem0 self-host config.

    关键约束 (跟 hosted API MemoryClient 不同):
    - vector_store.provider 必须是 'pgvector'
    - embedder 只支持 openai / ollama (HF 已移除)
    - llm 走 openai 协议, 复用 OPENAI_API_KEY
    """
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "model": os.getenv("LLM_MODEL", defaults.DEFAULT_LLM_MODEL),
            },
        },
        "embedder": _build_embedder_config(),
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST),
                "port": int(os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))),
                "user": os.getenv("PG_USER", defaults.DEFAULT_PG_USER),
                "password": os.getenv("PG_PASSWORD", defaults.DEFAULT_PG_PASSWORD),
                "dbname": os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE),
                "collection_name": os.getenv("MEM0_COLLECTION_NAME", defaults.DEFAULT_MEM0_COLLECTION_NAME),
                "embedding_model_dims": int(os.getenv("EMBED_DIMENSIONS", "1024")),
            },
        },
        "version": "v1.1",
    }


def _mask_key(key: str) -> str:
    """脱敏 api_key: 前 4 + **** + 后 4. 空串直接返 '(unset)'."""
    if not key:
        return "(unset)"
    if len(key) <= EIGHT:
        return "****"
    return f"{key[:FOUR]}****{key[-FOUR:]}"


def _default_mem0_factory(user_id: str) -> Memory:
    """默认 factory: 走 self-host config 创建 Memory. user_id 仅用于日志/debug.

    启动期 warmup 断言 (2026-06-17): 从 from_config 拿到 Memory 后立刻 .search() 一次,
    走通 spacy lemmatize + embedder + vector_store 整条链路, 失败立刻抛 RuntimeError
    带可读排查信息, 别让 spacy 模型缺失 / embedder 错配 / pgvector 连不上这类错误
    拖到第一个 user 请求才暴露 (commit 6f9bf8c 之后的 500 教训).
    """
    cfg = _build_config()
    try:
        mem = Memory.from_config(cfg)
    except Exception as e:
        logger.opt(exception=True).warning("mem0 构造失败 user_id={} err={}", user_id, e)
        raise
    # 启动期 warmup: 跑一次 search() 走 spacy + embedder + vector_store 全链路.
    # 用专属 user_id 隔离, 不会污染真实用户数据 (search 不写库, 只查).
    try:
        mem.search(query="__mem0_warmup__", filters={"user_id": "__mem0_warmup__"}, top_k=1)
    except BaseException as e:
        # (2026-06-23) 失败时打印脱敏诊断: api_key / base_url / pg 5 项, 帮用户定位.
        # 不在 except 块 import 避免循环, 直接读 os.environ
        embed_key = _mask_key(os.getenv("EMBED_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""))
        llm_key = _mask_key(os.getenv("OPENAI_API_KEY", ""))
        embed_base = os.getenv("EMBED_BASE_URL", "").strip() or os.getenv("OPENAI_BASE_URL", "").strip() or "(unset)"
        llm_model = os.getenv("LLM_MODEL", defaults.DEFAULT_LLM_MODEL)
        embed_model = os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_OPENAI)
        pg_host = os.getenv("PG_HOST", defaults.DEFAULT_PG_HOST)
        pg_port = os.getenv("PG_PORT", str(defaults.DEFAULT_PG_PORT))
        pg_db = os.getenv("PG_DATABASE", defaults.DEFAULT_PG_DATABASE)
        logger.error(
            "mem0 warmup 失败 user_id={} err={}\n"
            "诊断信息:\n"
            "  embedder: model={} base_url={} api_key={}\n"
            "  llm:      model={} api_key={}\n"
            "  pgvector: host={} port={} dbname={}\n"
            "排查方向:\n"
            "  1) uv pip list | grep en_core_web_sm (spacy 模型装了没)\n"
            "  2) EMBED_API_KEY / OPENAI_API_KEY 是否配对 (阿里云 DashScope / OpenAI / DeepSeek)\n"
            "  3) pgvector 容器是否起 + 网络可达 (docker compose ps)",
            user_id,
            e,
            embed_model,
            embed_base,
            embed_key,
            llm_model,
            llm_key,
            pg_host,
            pg_port,
            pg_db,
        )
        raise RuntimeError(
            f"mem0 启动期 warmup 失败: {e}. 详细诊断见 ERROR 日志, "
            "常见原因: 1) EMBED_API_KEY / OPENAI_API_KEY 错 2) spacy en_core_web_sm 缺 3) pgvector 不可达"
        ) from e
    logger.info("mem0 就绪 user_id={}", user_id)
    return mem


class Mem0Store:
    """per-user_id 的 Memory 实例缓存 (2026-06-18 加 Redis ready 标记).

    mem0 self-host 内部按 user_id 隔离数据, 多个 user 可安全共享同一 Memory 实例.
    缓存避免每次 search/add 都重新构造 (构造要连 pgvector + load embedder, 慢).

    Redis ready 标记: 实例不可序列化 (pgvector 连接), 仅做跨 worker decorrelation
    — 防 N worker 同时 warmup 同一 user (warmup 慢 ~5s). 标记本身不影响功能.
    """

    def __init__(self, user_id: str):
        if not user_id:
            raise ValueError("user_id 不能为空")
        self._user_id = user_id
        self._memory: Memory | None = None
        self._ready_marked: bool = False

    @property
    def memory(self) -> Memory:
        if self._memory is None:
            self._memory = _default_mem0_factory(self._user_id)
            # (2026-06-18 redis spec §5.4) fire-and-forget 标记 ready, 跨 worker decorrelation.
            # 仅首次构造触发 (lazy + flag), 不阻塞 memory 返回. Redis 挂 = facade fail-open.
            # 注: sync 测试上下文无 running event loop, 跳过 task 调度即可 (功能无影响,
            # 进程内 _ready_marked 仍会确保只尝试一次).
            if not self._ready_marked:
                self._ready_marked = True
                self._try_schedule_mark_ready()
        return self._memory

    def _try_schedule_mark_ready(self) -> None:
        """尝试 fire-and-forget 调度 ready 标记 task. sync 上下文无 event loop 时静默跳过."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # 无 running event loop (sync 测试 / 启动期), 跳过 ready 标记
            return
        asyncio.create_task(self._mark_ready())

    async def _mark_ready(self) -> None:
        """异步标记 Redis ready 1h. 失败不抛 (facade 已 catch + log)."""
        from src.core.mem0_ready import mark_ready

        try:
            await mark_ready(self._user_id)
        except Exception as e:
            logger.opt(exception=True).warning(
                "mem0 ready 标记失败 user_id={} err={}",
                self._user_id,
                e,
            )

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """走 mem0 self-host search API: filters={user_id} (不是直接 user_id=), top_k (不是 limit)."""
        results: Any = self.memory.search(query=query, filters={"user_id": self._user_id}, top_k=limit)
        if not results:
            return []
        # mem0 self-host 返 list[dict] | list[str] (两种格式), 统一成 list[dict]
        return [r if isinstance(r, dict) else {"memory": str(r)} for r in results]

    def add(self, messages: list[dict], metadata: dict | None = None) -> None:
        """走 mem0 self-host add API: user_id 直接传, infer=True 让 LLM 抽事实."""
        kwargs: dict[str, Any] = {"messages": messages, "user_id": self._user_id, "infer": True}
        if metadata:
            kwargs["metadata"] = metadata
        self.memory.add(**kwargs)
