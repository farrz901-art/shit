"""dify_datasets.py 单元测试"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.integrations.dify_datasets import DifyDatasets


@pytest.mark.asyncio
async def test_create_document_by_text_success():
    with (
        patch("src.integrations.dify_datasets.defaults.DEFAULT_DIFY_DATASET_API_KEY", "sk-test"),
        patch("src.integrations.dify_datasets.defaults.DEFAULT_DIFY_BASE_URL", "https://dify.example.com"),
        patch("src.integrations.dify_datasets._post_dify") as mock_post,
    ):
        mock_post.return_value = {"document": {"id": "doc-1"}}

        result = await DifyDatasets.createDocumentByText("ds-1", "test", "content")
        assert result["id"] == "doc-1"


@pytest.mark.asyncio
async def test_create_document_by_text_4xx_raises():
    with (
        patch("src.integrations.dify_datasets.defaults.DEFAULT_DIFY_DATASET_API_KEY", "sk-test"),
        patch("src.integrations.dify_datasets.defaults.DEFAULT_DIFY_BASE_URL", "https://dify.example.com"),
        patch("src.integrations.dify_datasets._post_dify") as mock_post,
    ):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        # httpx.HTTPStatusError is raised by raise_for_status when status >= 400
        mock_post.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        from src.integrations.dify_client import DifyAPIError

        with pytest.raises(DifyAPIError, match="404"):
            await DifyDatasets.createDocumentByText("ds-1", "test", "content")


@pytest.mark.asyncio
async def test_create_document_by_text_network_error():
    """网络错误 (重试耗尽) 应抛 DifyAPIError"""
    with (
        patch("src.integrations.dify_datasets.defaults.DEFAULT_DIFY_DATASET_API_KEY", "sk-test"),
        patch("src.integrations.dify_datasets.defaults.DEFAULT_DIFY_BASE_URL", "https://dify.example.com"),
        patch("src.integrations.dify_datasets._post_dify") as mock_post,
    ):
        mock_post.side_effect = httpx.TimeoutException("Connection timed out")

        from src.integrations.dify_client import DifyAPIError

        with pytest.raises(DifyAPIError, match="重试后"):
            await DifyDatasets.createDocumentByText("ds-1", "test", "content")
