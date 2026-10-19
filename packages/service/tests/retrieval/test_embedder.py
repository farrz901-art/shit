"""retrieval/embedder.py 单元测试 (mode 1, mock embedding model)"""

from unittest.mock import MagicMock, patch

from src.retrieval.embedder import (
    OpenAIEmbedder,
    get_embedding_dimension,
    is_embedder_ready,
)


class TestOpenAIEmbedder:
    def test_init_defaults(self):
        embedder = OpenAIEmbedder()
        assert embedder.model is not None

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_embedder_lazy_load(self, mock_emb):
        embedder = OpenAIEmbedder(model="text-embedding-3-small")
        _ = embedder.embedder
        mock_emb.assert_called_once()

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_embed(self, mock_emb):
        mock_emb.return_value.embed_documents.return_value = [[0.1, 0.2]]
        embedder = OpenAIEmbedder(model="text-embedding-3-small")
        result = embedder.embed(["test"])
        assert len(result) == 1

    @patch("langchain_openai.OpenAIEmbeddings")
    def test_call(self, mock_emb):
        mock_emb.return_value.embed_documents.return_value = [[0.1]]
        embedder = OpenAIEmbedder(model="test")
        result = embedder("hello")
        assert len(result) == 1


class TestEmbedFunctions:
    def test_get_embedding_dimension_from_dimensions(
        self,
    ):
        embedder = MagicMock(spec=[])
        embedder.dimensions = 512
        assert get_embedding_dimension(embedder) == 512

    def test_is_embedder_ready_true(self):
        embedder = MagicMock()
        embedder.return_value = [[0.1]]
        assert is_embedder_ready(embedder) is True

    def test_is_embedder_ready_false(self):
        embedder = MagicMock()
        embedder.side_effect = Exception("fail")
        assert is_embedder_ready(embedder) is False
