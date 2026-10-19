"""langfuse_client.py 单元测试 (mode 1, mock langfuse import)"""

from unittest.mock import patch

from src.telemetry.langfuse_client import (
    LangfuseClient,
    LangfuseConfig,
    RAGTraceContext,
    get_langfuse_client,
)


def test_config_from_env():
    with patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk-test", "LANGFUSE_SECRET_KEY": "sk-test"}):
        cfg = LangfuseConfig.from_env()
        assert cfg.public_key == "pk-test"


class TestLangfuseClient:
    def test_init_no_config(self):
        client = LangfuseClient()
        assert client._config is not None

    @patch("langfuse.Langfuse")
    def test_client_lazy_load(self, mock_lf):
        client = LangfuseClient(LangfuseConfig())
        _ = client.client
        mock_lf.assert_called_once()

    @patch("langfuse.Langfuse")
    def test_event(self, mock_lf):
        client = LangfuseClient(LangfuseConfig())
        _ = client.client
        client.event("test_event", input="q", output="a")
        mock_lf.return_value.event.assert_called_once()

    @patch("langfuse.Langfuse")
    def test_trace_returns_trace(self, mock_lf):
        client = LangfuseClient(LangfuseConfig())
        t = client.trace("test_trace")
        assert t is not None

    @patch("langfuse.Langfuse")
    def test_flush(self, mock_lf):
        client = LangfuseClient(LangfuseConfig())
        _ = client.client
        client.flush()
        mock_lf.return_value.flush.assert_called_once()

    def test_get_singleton(self):
        LangfuseClient._instance = None
        c1 = get_langfuse_client()
        c2 = get_langfuse_client()
        assert c1 is c2


class TestRAGTraceContext:
    def test_defaults(self):
        ctx = RAGTraceContext(query="test")
        assert ctx.retrieve_latency_ms == 0.0

    def test_to_dict(self):
        ctx = RAGTraceContext(query="q", response="a")
        d = ctx.to_dict()
        assert d["query"] == "q"
        assert d["response"] == "a"
