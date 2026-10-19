"""Embedder 封装 (OpenAI 兼容协议, LangChain)

(2026-06-29 LC 替换) 走 LangChain `langchain_openai.OpenAIEmbeddings`,
base_url 配 EMBED_BASE_URL. EmbedCache (Redis 7d) 包装层保留.

(Spike T0 偏差 #4): bge-m3 (SiliconFlow) 不支持 OpenAI `dimensions` 参数, 且用
XLM-RoBERTa tokenizer (不是 tiktoken). 必须传 `check_embedding_ctx_length=False`
关掉 LC 默认 tiktoken 编码长度检查. 维度通过 init_vectorstore_table(vector_size=)
表达.

所有 embedding 走 OpenAI 兼容协议 (OpenAI / DashScope / SiliconFlow / 其它),
不再支持本地 HF 模型. 配置全部走 env:

  EMBED_MODEL         — 模型名
  EMBED_API_KEY       — API key (独立于 OPENAI_API_KEY, 让 embedding 走不同厂商)
  EMBED_BASE_URL      — endpoint (独立于 OPENAI_BASE_URL, 同样原因)
  EMBED_DIMENSIONS    — 可选, 跟模型输出维度一致 (仅供内省, 不传 LC)
  EMBED_BATCH_SIZE    — 批大小
"""

import asyncio
import os
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from loguru import logger

from ..common import defaults

if TYPE_CHECKING:
    from langchain_openai import OpenAIEmbeddings


class OpenAIEmbedder:
    """OpenAI 兼容 embedder: 走 EMBED_BASE_URL + EMBED_API_KEY (独立 env, 不共用 LLM 的)"""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,  # 保留参数兼容, 但实际不传给 LC OpenAIEmbeddings
    ):
        # env 优先级: 显式参数 > EMBED_* > 代码默认
        self.model = model or os.getenv("EMBED_MODEL", defaults.DEFAULT_EMBED_MODEL_OPENAI)
        self._api_key = (
            api_key or os.getenv("EMBED_API_KEY") or os.getenv("OPENAI_API_KEY") or defaults.DEFAULT_OPENAI_API_KEY
        )
        self._base_url = base_url or os.getenv("EMBED_BASE_URL") or os.getenv("OPENAI_BASE_URL") or ""
        # dimensions 字段保留供 _get_embedding_dimension 等内省调用, 不传给 LC
        env_dims = os.getenv("EMBED_DIMENSIONS")
        self._dimensions = dimensions if dimensions is not None else (int(env_dims) if env_dims else None)
        self._embedder: OpenAIEmbeddings | None = None

    @property
    def embedder(self) -> OpenAIEmbeddings:
        if self._embedder is None:
            # 重依赖 lazy: langchain_openai 冷启动 ~800ms, 非 OpenAI provider 路径不需要
            from langchain_openai import OpenAIEmbeddings  # noqa: E402

            kwargs: dict[str, Any] = {
                "model": self.model,
                "api_key": self._api_key or None,
                # (Spike 偏差 #4) bge-m3 用 XLM-RoBERTa tokenizer 不是 tiktoken
                # 必须关 LC 默认 tiktoken 编码长度检查 (否则 KeyError)
                "check_embedding_ctx_length": False,
            }
            if self._base_url:
                kwargs["base_url"] = self._base_url
            # (Spike 偏差 #4) 不传 `dimensions`: bge-m3 服务端固定 1024 维, 传 dimensions 会 400.
            # OpenAI text-embedding-3 系列私有特性, 其他 OpenAI 兼容端点不支持.
            # 维度通过 init_vectorstore_table(vector_size=) 表达, 不通过 embedder.
            self._embedder = OpenAIEmbeddings(**kwargs)
        return self._embedder

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.embed_documents(texts)

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        """(2026-06-18) 加 EmbedCache 包装: 重复 text 7d 内 0 OpenAI 调用.

        批处理用 asyncio.gather 并发查 cache, 避免 N 次串行 RTT.
        """
        # 重依赖 lazy: embed_cache 触发 Redis client 初始化, 非 embed 调用路径不需要
        from ..core.embed_cache import cache_vector, get_cached_vector  # noqa: E402

        if not texts:
            return []

        # 1. 并发查 cache
        cached_results = await asyncio.gather(*[get_cached_vector(t) for t in texts])
        results: list[list[float] | None] = list(cached_results)
        miss_indices = [i for i, v in enumerate(results) if v is None]

        if not miss_indices:
            return [v for v in results if v is not None]

        # 2. miss 的调底层 embedder (LC OpenAIEmbeddings)
        miss_texts = [texts[i] for i in miss_indices]
        computed = await self.embedder.aembed_documents(miss_texts)

        # 3. 回填 + fire-and-forget 写 cache
        for idx, vec in zip(miss_indices, computed):
            results[idx] = list(vec)
            asyncio.create_task(cache_vector(texts[idx], vec))

        return [v for v in results if v is not None]

    def __call__(self, text: str) -> list[float]:
        return self.embed([text])[0]


def get_embedder(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    batch_size: int | None = None,
) -> OpenAIEmbedder:
    """返回 OpenAI 兼容 embedder.

    batch_size 参数保留向后兼容 (不影响 OpenAI 协议本身, 实际由调用方控制).
    """
    return OpenAIEmbedder(model=model, api_key=api_key, base_url=base_url)


def embed_documents(
    documents: Sequence[Any], embedder: Any, batch_size: int = 32, show_progress: bool = True
) -> list[list[float]]:
    if documents and hasattr(documents[0], "get_content"):
        texts = [d.get_content() for d in documents]
    elif documents and isinstance(documents[0], str):
        texts = list(documents)
    else:
        raise TypeError("documents 必须是 RAGDoc 列表或字符串列表")
    # 重依赖 lazy: batch_utils 引入 tiktoken / tqdm (软依赖), 非批量场景不需要
    from ..common.batch_utils import batch_embed  # noqa: E402

    return batch_embed(texts, embedder, batch_size=batch_size, show_progress=show_progress)


def embed_texts(
    texts: Iterable[str], embedder: Any, batch_size: int = 32, show_progress: bool = True
) -> list[list[float]]:
    # 重依赖 lazy: 同上 batch_utils 软依赖
    from ..common.batch_utils import batch_embed  # noqa: E402

    return batch_embed(texts, embedder, batch_size=batch_size, show_progress=show_progress)


def get_embedding_dimension(embedder: Any) -> int | None:
    if hasattr(embedder, "dimensions"):
        return embedder.dimensions
    return None


def is_embedder_ready(embedder: Any) -> bool:
    try:
        result = embedder(["./__health_check__"])
        return isinstance(result, list) and len(result) == 1
    except Exception:
        logger.warning("is_embedder_ready 检查失败, embedder 可能无法使用")
        return False
