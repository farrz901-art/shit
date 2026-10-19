"""retrieval 子包导出测试"""


def test_embedder_exported():
    from src.retrieval import OpenAIEmbedder, get_embedder

    assert callable(OpenAIEmbedder)
    assert callable(get_embedder)


def test_vector_store_exported():
    from src.retrieval import AsyncPGVectorStore, PGVectorStore, get_vector_store

    assert callable(PGVectorStore)
    assert callable(AsyncPGVectorStore)
    assert callable(get_vector_store)


def test_add_to_vector_store_exported():
    from src.retrieval import add_to_vector_store, delete_from_vector_store

    assert callable(add_to_vector_store)
    assert callable(delete_from_vector_store)
