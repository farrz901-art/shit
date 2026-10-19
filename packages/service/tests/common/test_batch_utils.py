"""batch_utils 测试"""

from unittest.mock import MagicMock


def test_estimate_tokens_english():
    from src.common.batch_utils import estimate_tokens

    assert estimate_tokens("hello world") >= 2


def test_estimate_tokens_chinese():
    from src.common.batch_utils import estimate_tokens

    assert estimate_tokens("你好世界") >= 2


def test_estimate_tokens_empty():
    from src.common.batch_utils import estimate_tokens

    assert estimate_tokens("") == 0


def test_truncate_text_under_limit():
    from src.common.batch_utils import truncate_text

    assert truncate_text("short", max_chars=10) == "short"


def test_truncate_text_over_limit():
    from src.common.batch_utils import truncate_text

    result = truncate_text("a" * 100, max_chars=20)
    assert len(result) < 100
    assert "省略" in result


def test_batch_embed_empty():
    from src.common.batch_utils import batch_embed

    mock = MagicMock()
    assert batch_embed([], mock) == []


def test_batch_embed_single():
    from src.common.batch_utils import batch_embed

    mock = MagicMock()
    mock.get_embeddings.return_value = [[0.1, 0.2]]
    result = batch_embed(["hello"], mock, show_progress=False)
    assert result == [[0.1, 0.2]]
    mock.get_embeddings.assert_called_once_with(["hello"])


def test_batch_embed_multiple_batches():
    from src.common.batch_utils import batch_embed

    mock = MagicMock()
    # 5 items, batch_size=2 → 3 batches
    mock.get_embeddings.side_effect = [
        [[0.1, 0.2], [0.3, 0.4]],
        [[0.5, 0.6], [0.7, 0.8]],
        [[0.9, 1.0]],
    ]
    result = batch_embed(["a", "b", "c", "d", "e"], mock, batch_size=2, show_progress=False)
    assert len(result) == 5
    assert mock.get_embeddings.call_count == 3


def test_batch_iter_direct():
    """_batch_iter 直接测试"""
    from src.common.batch_utils import _batch_iter

    items = [1, 2, 3, 4, 5, 6, 7]
    batches = list(_batch_iter(items, batch_size=3))
    assert batches == [[1, 2, 3], [4, 5, 6], [7]]


def test_batch_iter_empty():
    """_batch_iter 空列表"""
    from src.common.batch_utils import _batch_iter

    assert list(_batch_iter([], batch_size=3)) == []


def test_batch_iter_exact():
    """_batch_iter 正好整除"""
    from src.common.batch_utils import _batch_iter

    assert list(_batch_iter([1, 2, 3, 4], batch_size=2)) == [[1, 2], [3, 4]]


async def _async_embedder(chunks):
    """异步 embedding 模拟"""
    return [[0.1] * 3 for _ in chunks]


class AsyncEmbedder:
    """带 aget_embeddings 的 mock embedder"""

    async def aget_embeddings(self, chunks):
        return [[0.1 * i, 0.2 * i, 0.3 * i] for i in range(len(chunks))]


class SyncEmbedder:
    """只有同步 get_embeddings 的 mock embedder (也标记 aget_embeddings 为 coroutinefunction)"""

    def get_embeddings(self, chunks):
        return [[0.5, 0.6, 0.7] for _ in chunks]


def test_batch_embed_with_async_embedder():
    """batch_embed 使用 async embedder (aget_embeddings)"""
    from src.common.batch_utils import batch_embed

    embedder = AsyncEmbedder()
    result = batch_embed(["a", "b"], embedder, batch_size=2, show_progress=False)
    assert len(result) == 2
    assert result[0] == [0.0, 0.0, 0.0]
    assert result[1] == [0.1, 0.2, 0.3]


def test_batch_embed_sync_fallback():
    """batch_embed embedder 只有 get_embeddings (无 aget_embeddings) 走同步"""
    from src.common.batch_utils import batch_embed

    embedder = SyncEmbedder()
    result = batch_embed(["x", "y"], embedder, batch_size=2, show_progress=False)
    assert len(result) == 2
    assert result[0] == [0.5, 0.6, 0.7]
