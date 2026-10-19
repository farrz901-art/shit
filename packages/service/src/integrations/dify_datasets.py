"""Dify Datasets API 客户端 — 知识库文档/分段管理.

接口契约 (由 approvals executor 调用, 后续会扩展到 createQA/commitDocuments 等业务):
- createDocumentByText(dataset_id, name, text, indexing_technique='high_quality') → { 'id': str, ... }
- list/listDocuments/... 后续按需加

设计原则:
- 静态方法, 跟 DifyClient 实例方法风格保持一致 (DifyClient 是 chatflow, 这个是 datasets)
- 抛 DifyAPIError on 失败 (复用现有错误类)
- base_url/api_key 读 defaults 模块 (跟 DifyClient 一致)
- 网络请求带 tenacity 重试 (3 次退避, 只重试超时/断连/5xx)
"""

from __future__ import annotations

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..common import defaults
from .dify_client import DifyAPIError


def _is_retryable_dify_error(exc: BaseException) -> bool:
    """仅重试网络超时/断连 以及 Dify 5xx 服务端错误, 4xx 直接透传."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable_dify_error),
    before_sleep=lambda retry_state: logger.warning(
        "重试 dify createDocumentByText attempt={}", retry_state.attempt_number
    ),
)
async def _post_dify(url: str, api_key: str, payload: dict) -> dict:
    """带 tenacity 重试的 Dify datasets API POST 请求 (最多 3 次指数退避)."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        return await resp.json()


class DifyDatasets:
    """Dify /v1/datasets 知识库 API 静态客户端"""

    @staticmethod
    async def createDocumentByText(
        dataset_id: str,
        name: str,
        text: str,
        indexing_technique: str = "high_quality",
    ) -> dict:
        """往指定知识库塞一条文档 (text 模式, Dify 自动分段).

        Returns:
            {"id": "doc-xxx", ...} — Dify 返回的 document 资源
        """
        api_key = defaults.DEFAULT_DIFY_DATASET_API_KEY
        if not api_key:
            raise DifyAPIError("DIFY_DATASET_API_KEY 未配置 (defaults.DEFAULT_DIFY_DATASET_API_KEY 为空)")
        base_url = defaults.DEFAULT_DIFY_BASE_URL.rstrip("/")
        url = f"{base_url}/datasets/{dataset_id}/document/create_by_file"
        try:
            data = await _post_dify(
                url,
                api_key,
                {
                    "name": name,
                    "text": text,
                    "indexing_technique": indexing_technique,
                    "process_rule": {"mode": "automatic"},
                },
            )
        except httpx.HTTPStatusError as e:
            raise DifyAPIError(
                f"Dify datasets createDocumentByText HTTP {e.response.status_code}: {e.response.text[:500]}"
            ) from e
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            raise DifyAPIError(f"Dify datasets 请求失败 (重试后): {e}") from e
        document = data.get("document") or data
        return {"id": document.get("id", ""), "raw": data}
