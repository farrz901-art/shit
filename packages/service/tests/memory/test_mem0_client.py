"""mem0_client.py 测试: self-host config + per-user_id Mem0Store 缓存"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest


def test_build_config_reads_env(monkeypatch):
    """_build_config 必须读 env: MEM0_COLLECTION_NAME, LLM_MODEL, OPENAI_API_KEY, PG_*"""
    from src.memory.mem0_client import _build_config

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MEM0_COLLECTION_NAME", "test_mem")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("PG_HOST", "pg.test")
    monkeypatch.setenv("PG_PORT", "6543")
    monkeypatch.setenv("PG_USER", "u")
    monkeypatch.setenv("PG_PASSWORD", "p")
    monkeypatch.setenv("PG_DATABASE", "d")

    cfg = _build_config()

    assert cfg["llm"]["config"]["api_key"] == "sk-test"
    assert cfg["llm"]["config"]["model"] == "gpt-4o"
    assert cfg["vector_store"]["provider"] == "pgvector"
    assert cfg["vector_store"]["config"]["host"] == "pg.test"
    assert cfg["vector_store"]["config"]["port"] == 6543
    assert cfg["vector_store"]["config"]["collection_name"] == "test_mem"


def test_build_config_uses_defaults_when_env_missing(monkeypatch):
    """env 没配时用 defaults.py 常量"""
    from src.common import defaults
    from src.memory.mem0_client import _build_config

    monkeypatch.delenv("MEM0_COLLECTION_NAME", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    cfg = _build_config()
    assert cfg["vector_store"]["config"]["collection_name"] == defaults.DEFAULT_MEM0_COLLECTION_NAME
    assert cfg["llm"]["config"]["model"] == defaults.DEFAULT_LLM_MODEL


def test_default_factory_uses_build_config(monkeypatch):
    """_default_mem0_factory 必须调 Memory.from_config(_build_config())"""
    from src.memory import mem0_client

    fake_memory = MagicMock()
    with patch.object(mem0_client, "Memory", create=True) as mock_memory_cls:
        # Memory 在模块内 lazy import, 走 mock 即可
        mock_memory_cls.from_config.return_value = fake_memory
        result = mem0_client._default_mem0_factory("u1")

    assert result is fake_memory
    mock_memory_cls.from_config.assert_called_once()
    cfg_arg = mock_memory_cls.from_config.call_args[0][0]
    assert cfg_arg["vector_store"]["provider"] == "pgvector"


def test_default_factory_warmup_calls_search_with_magic_args(monkeypatch):
    """启动期 warmup: 构造完 Memory 必须立刻 .search() 走 spacy + embedder + vector_store 链路

    用专属 user_id='__mem0_warmup__' 隔离, 不污染真实用户数据.
    """
    from src.memory import mem0_client

    fake_memory = MagicMock()
    with patch.object(mem0_client, "Memory", create=True) as mock_memory_cls:
        mock_memory_cls.from_config.return_value = fake_memory
        result = mem0_client._default_mem0_factory("u1")

    # warmup 调过 search, 1 次, 参数固定 (别随便改 magic 字符串, 跟日志 grep 联动)
    fake_memory.search.assert_called_once_with(
        query="__mem0_warmup__",
        filters={"user_id": "__mem0_warmup__"},
        top_k=1,
    )
    assert result is fake_memory


def test_default_factory_warmup_systemexit_raises_runtime_error(monkeypatch):
    """warmup 抛 SystemExit (spacy 缺失走 sys.exit 路径) → 包 RuntimeError, 错误信息含排查提示

    根因 (2026-06-17 真实 500): mem0 spacy_models 内部 except Exception 抓不到 SystemExit
    (SystemExit 是 BaseException 子类), 错误一路冒泡到 FastAPI 500. 启动期包 RuntimeError
    才能让运维早死早超生.
    """
    from src.memory import mem0_client

    fake_memory = MagicMock()
    fake_memory.search.side_effect = SystemExit(1)
    with patch.object(mem0_client, "Memory", create=True) as mock_memory_cls:
        mock_memory_cls.from_config.return_value = fake_memory
        with pytest.raises(RuntimeError, match="warmup 失败") as exc_info:
            mem0_client._default_mem0_factory("u1")

    # 错误信息必须含排查方向, 不能只贴原异常 (根因: spacy 缺模型 / embedder 错配 / pgvector 不通)
    msg = str(exc_info.value)
    assert "en_core_web_sm" in msg
    assert "pgvector" in msg
    # 链式异常保留原 SystemExit
    assert isinstance(exc_info.value.__cause__, SystemExit)


def test_default_factory_warmup_exception_raises_runtime_error(monkeypatch):
    """warmup 抛普通 Exception (embedder 401 / pgvector 连不上等) → 也包 RuntimeError"""
    from src.memory import mem0_client

    fake_memory = MagicMock()
    fake_memory.search.side_effect = RuntimeError("pgvector connection refused")
    with patch.object(mem0_client, "Memory", create=True) as mock_memory_cls:
        mock_memory_cls.from_config.return_value = fake_memory
        with pytest.raises(RuntimeError, match="warmup 失败"):
            mem0_client._default_mem0_factory("u1")


def test_embedder_config_openai_provider_when_text_embedding(monkeypatch):
    """EMBED_MODEL=text-embedding-* → 自动选 openai provider, 复用 OPENAI_API_KEY"""
    from src.memory.mem0_client import _build_embedder_config

    monkeypatch.delenv("MEM0_EMBED_PROVIDER", raising=False)
    monkeypatch.delenv("EMBED_API_KEY", raising=False)  # _build_embedder_config or-fallback, 防 .env 干扰
    monkeypatch.delenv("EMBED_BASE_URL", raising=False)
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    cfg = _build_embedder_config()

    assert cfg["provider"] == "openai"
    assert cfg["config"]["model"] == "text-embedding-3-small"
    assert cfg["config"]["api_key"] == "sk-test"


def test_embedder_config_openai_provider_with_explicit_base_url(monkeypatch):
    """OPENAI_BASE_URL 配了 → openai config 透传 (Azure/代理/自建兼容)"""
    from src.memory.mem0_client import _build_embedder_config

    monkeypatch.delenv("MEM0_EMBED_PROVIDER", raising=False)
    monkeypatch.delenv("EMBED_API_KEY", raising=False)  # _build_embedder_config or-fallback, 防 .env 干扰
    monkeypatch.delenv("EMBED_BASE_URL", raising=False)
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://proxy.example.com/v1")

    cfg = _build_embedder_config()

    assert cfg["provider"] == "openai"
    assert cfg["config"]["openai_base_url"] == "https://proxy.example.com/v1"


def test_embedder_config_ollama_provider_when_model_prefixed(monkeypatch):
    """EMBED_MODEL=ollama/* → 自动选 ollama provider, 复用 OLLAMA_BASE_URL"""
    from src.memory.mem0_client import _build_embedder_config

    monkeypatch.delenv("MEM0_EMBED_PROVIDER", raising=False)
    monkeypatch.setenv("EMBED_MODEL", "ollama/nomic-embed-text")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    cfg = _build_embedder_config()

    assert cfg["provider"] == "ollama"
    assert cfg["config"]["model"] == "nomic-embed-text"
    assert cfg["config"]["ollama_base_url"] == "http://localhost:11434/v1"


def test_embedder_config_explicit_provider_overrides_autodetect(monkeypatch):
    """MEM0_EMBED_PROVIDER=openai 显式设了 → 走 openai, 即使模型名是 HF 风格也走 openai"""
    from src.memory.mem0_client import _build_embedder_config

    monkeypatch.setenv("MEM0_EMBED_PROVIDER", "openai")
    # EMBED_MODEL 是旧 HF 名字, 但强制 openai 应该按 openai 处理
    monkeypatch.setenv("EMBED_MODEL", "BAAI/bge-m3")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    cfg = _build_embedder_config()

    assert cfg["provider"] == "openai"


def test_embedder_config_unknown_prefix_falls_back_to_openai(monkeypatch):
    """未识别的前缀 (原 HF 风格) → 自动走 openai 兜底 (HF provider 已移除)"""
    from src.memory.mem0_client import _build_embedder_config

    monkeypatch.delenv("MEM0_EMBED_PROVIDER", raising=False)
    monkeypatch.setenv("EMBED_MODEL", "BAAI/bge-m3")  # 旧 HF 模型名
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")

    cfg = _build_embedder_config()

    assert cfg["provider"] == "openai"  # 不再走 huggingface
    assert cfg["config"]["model"] == "BAAI/bge-m3"  # 模型名原样透传
    assert cfg["config"]["openai_base_url"] == "https://api.siliconflow.cn/v1"


def test_build_config_includes_embedder_section(monkeypatch):
    """_build_config 顶层必须有 embedder 键, 由 _build_embedder_config 拼"""
    from src.memory.mem0_client import _build_config

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")

    cfg = _build_config()

    assert "embedder" in cfg
    assert cfg["embedder"]["provider"] == "openai"


def test_mem0_store_init_stores_user_id():
    """Mem0Store 必须接收 user_id 初始化, 不从 env 读"""
    from src.memory.mem0_client import Mem0Store

    store = Mem0Store(user_id="u1")
    assert store._user_id == "u1"
    # memory 是 lazy property, 初始为 None
    assert store._memory is None


def test_mem0_store_memory_lazy_cached(monkeypatch):
    """Mem0Store.memory 第一次调走 factory, 后续返缓存"""
    from src.memory import mem0_client
    from src.memory.mem0_client import Mem0Store

    fake_memory = MagicMock()
    with patch.object(mem0_client, "_default_mem0_factory", return_value=fake_memory) as mock_factory:
        store = Mem0Store(user_id="u1")
        m1 = store.memory
        m2 = store.memory

    assert m1 is fake_memory
    assert m2 is fake_memory
    mock_factory.assert_called_once_with("u1")


def test_mem0_store_search_uses_filters_and_top_k():
    """Mem0Store.search 走 self-host API: filters={user_id}, top_k (不是 limit/user_id=)"""
    from src.memory.mem0_client import Mem0Store

    fake_memory = MagicMock()
    fake_memory.search.return_value = [{"id": "1", "memory": "hello", "score": 0.9}]
    with patch.object(Mem0Store, "memory", new_callable=PropertyMock, return_value=fake_memory):
        store = Mem0Store(user_id="u1")
        results = store.search("query", limit=3)

    assert results == [{"id": "1", "memory": "hello", "score": 0.9}]
    fake_memory.search.assert_called_once_with(query="query", filters={"user_id": "u1"}, top_k=3)


def test_mem0_store_add_passes_user_id_and_infer():
    """Mem0Store.add 走 self-host API: user_id 直接传, infer=True"""
    from src.memory.mem0_client import Mem0Store

    fake_memory = MagicMock()
    with patch.object(Mem0Store, "memory", new_callable=PropertyMock, return_value=fake_memory):
        store = Mem0Store(user_id="u1")
        store.add(
            messages=[{"role": "user", "content": "hi"}],
            metadata={"conversation_id": "c1"},
        )

    fake_memory.add.assert_called_once_with(
        messages=[{"role": "user", "content": "hi"}],
        user_id="u1",
        infer=True,
        metadata={"conversation_id": "c1"},
    )
