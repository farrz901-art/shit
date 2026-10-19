"""Dify 对话工作流 API 客户端

封装 Dify 的 /v1/chat-messages 端点 (blocking 模式),
返回 (answer, contexts) 供 RAGAS 评估用。

⚠️ ========== 接入点 (请按需改这里) ========== ⚠️
  1. DIFY_BASE_URL  → 你的 Dify 服务地址
     - Dify Cloud:  https://api.dify.ai/v1
     - 自建 Dify:    http://localhost/v1  (或你的内网地址)
  2. DIFY_DATASET_API_KEY   → Dify 应用的 API Key
     - Dify 控制台: 工作室 → 你的应用 → 左侧 "API Access" → "API Key"
  3. DIFY_USER_ID   → 任意字符串, 标识"调用者", Dify 用来分组日志
  4. inputs 字段    → 如果你的工作流定义了输入变量 (如 knowledge_base_id),
                      在 achat() 里显式传 inputs={...}
⚠️ ============================================ ⚠️

网络请求带 tenacity 重试 (3 次指数退避, 超时/断连/5xx 重试).
"""

from __future__ import annotations

import os
import re

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..common import defaults

# (2026-06-11) Dify 工作流返的 answer 可能含 <think>...</think> 推理块
# 评估表格不需要展示中间推理 (太长+不直观), 客户端层正则过滤
# 匹配: <think>...</think> 非贪婪跨行, re.DOTALL 让 . 匹配换行
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


def _is_retryable_dify_error(exc: BaseException) -> bool:
    """仅重试网络超时/断连 以及 Dify 5xx 服务端错误, 4xx 直接透传."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


def _strip_think(answer: str | None) -> str | None:
    """删 Dify answer 中的 <think>...</think> 块, 保留其余文本

    边界:
    - None → 返 None
    - 空串 → 返空串
    - 无 think 块 → 原样返回
    - 多个 think 块 → 全部删除
    """
    if answer is None:
        return None
    cleaned = _THINK_PATTERN.sub("", answer).strip()
    return cleaned


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable_dify_error),
    before_sleep=lambda retry_state: logger.warning("重试 dify achat attempt={}", retry_state.attempt_number),
)
async def _achat_post(client: httpx.AsyncClient, url: str, headers: dict, payload: dict) -> httpx.Response:
    """带 tenacity 重试的 Dify /chat-messages POST 请求 (最多 3 次指数退避).

    只重试网络超时/断连/5xx; 4xx 和 业务错直接透出让 achat 方法处理.
    """
    resp = await client.post(url, headers=headers, json=payload)
    # 5xx 服务端错误触发重试; 4xx 直接透传 (不需要 raise_for_status)
    if resp.status_code >= 500:
        resp.raise_for_status()
    return resp


class DifyAPIError(RuntimeError):
    """Dify API 返回非 message 事件 (workflow 失败 / 鉴权错 / 网络错)"""


class DifyClient:
    """Dify 对话工作流 (chatflow / agent) 客户端, blocking 模式

    Args:
        api_key: Dify Chatflow API Key (app-xxx). 留空则读 DIFY_CHAT_API_KEY env.
        base_url: Dify API base URL. 留空则读 DIFY_BASE_URL env.
        user_id: 标识调用者. 留空则读 DIFY_USER_ID env.
        timeout: 单次请求超时 (秒). 默认 60.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        user_id: str | None = None,
        timeout: float = 60.0,
    ):
        # 所有默认值从 src/rag/common/defaults.py 来, 别在这里写字面量
        # (项目 lint 规则 test_no_magic_string_default_outside_defaults_py)
        # DifyClient 调 chat-messages → 必须用 Chatflow API Key (app-xxx)
        # DIFY_DATASET_API_KEY 是 Dataset Key (dataset-xxx), 不能调 chatflow, 不要 fallback
        self._api_key = api_key or os.getenv("DIFY_CHAT_API_KEY") or defaults.DEFAULT_DIFY_DATASET_API_KEY
        self._base_url = (base_url or os.getenv("DIFY_BASE_URL", defaults.DEFAULT_DIFY_BASE_URL)).rstrip("/")
        self._user_id = user_id or os.getenv("DIFY_USER_ID", defaults.DEFAULT_DIFY_USER_ID)
        self._timeout = timeout

        # 同步 httpx.Client: health/checks.py check_dify() 用 asyncio.to_thread 包装调用
        # 跟 achat() 的 async httpx.AsyncClient 独立, 避免共享连接状态
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self._timeout,
        )

        if not self._api_key:
            raise ValueError(
                "DIFY_CHAT_API_KEY 未配置. 在 .env 里加 DIFY_CHAT_API_KEY=app-...", "或显式传 api_key 参数."
            )

    async def achat(
        self,
        query: str,
        inputs: dict | None = None,
        conversation_id: str = "",
    ) -> dict:
        """异步调一次 Dify 对话工作流, 返回结构化响应

        Args:
            query: 用户问题 (Dify 把它喂给工作流的 "sys.query" 节点)
            inputs: 工作流自定义输入变量 (Dify 工作室里 "开始" 节点定义的)
            conversation_id: 续聊时传上次的 id; 单轮评测传空串即可

        Returns:
            {
                "answer": str,                # Dify 工作流最终输出 (已 strip <think>)
                "contexts": list[str],        # 检索到的上下文 (给 RAGAS 评估用)
                "sources": list[dict],        # 召回到的文件元数据 (给前端表格展示)
                                            # [{name, position, score, snippet}, ...]
                "conversation_id": str,
                "raw": dict,                  # Dify 完整 JSON 响应, 方便排查
            }

        Raises:
            DifyAPIError: 鉴权错 / 工作流失败 / 网络错

        Note:
            30 题串行 30-60 分钟 (Dify + RAGAS 评估都调 LLM, 单题 1-2 分钟).
            配合 asyncio.Semaphore 限并发跑, 30 题 ≈ 5-10 分钟.
        """
        url = f"{self._base_url}/chat-messages"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "blocking",  # 单次同步响应, 配合外层 asyncio 并发
            "conversation_id": conversation_id,
            "user": self._user_id,
        }

        # 每次调用建一个新 AsyncClient: 30 题 30 次实例化, 开销可忽略
        # 高频场景再换成 self._client 复用 + close()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await _achat_post(client, url, headers, payload)
        except httpx.HTTPStatusError as e:
            raise DifyAPIError(f"Dify HTTP {e.response.status_code}: {e.response.text[:500]}") from e
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            raise DifyAPIError(f"网络错误 (重试后): {e}") from e

        data = resp.json()

        # 业务错: workflow 失败 / 输入参数错
        if data.get("event") != "message":
            raise DifyAPIError(
                f"Dify 返回非 message 事件: event={data.get('event')!r}, message={data.get('message', '')!r}"
            )

        # 提取 contexts + sources: Dify 把检索结果放在 metadata.retriever_resources
        # - content 字段: chunk 全文 → contexts (给 RAGAS 评估用)
        # - document_name/position/score + 截短的 content → sources (给前端表格展示「召回到」)
        contexts: list[str] = []
        sources: list[dict] = []
        retriever_resources = data.get("metadata", {}).get("retriever_resources", []) or []
        for r in retriever_resources:
            content = r.get("content")
            if content:
                contexts.append(content)
                # (2026-06-11) sources: 截短 content 为 snippet (前 120 字符), 避免前端展示长 chunk
                snippet = content if len(content) <= 120 else content[:117] + "…"
                sources.append(
                    {
                        "name": r.get("document_name") or r.get("document_id") or "(未知文档)",
                        "position": r.get("position"),
                        "score": r.get("score"),
                        "snippet": snippet,
                    }
                )

        return {
            "answer": _strip_think(data.get("answer", "")) or "",
            "contexts": contexts,
            "sources": sources,
            "conversation_id": data.get("conversation_id", ""),
            "raw": data,
        }
