"""llm 测试"""

from unittest.mock import patch


def test_openai_llm_init():
    from src.generation.llm import OpenAILLM

    llm = OpenAILLM(model="gpt-4o-mini")
    assert llm.model == "gpt-4o-mini"
    assert llm._llm is None


def test_openai_llm_lazy_loads():
    from src.generation.llm import OpenAILLM

    llm = OpenAILLM(model="gpt-4o-mini")
    # _llm is None before accessing .llm property (lazy)
    assert llm._llm is None


def test_local_llm_init():
    from src.generation.llm import LocalLLM

    llm = LocalLLM(model="llama3", base_url="http://localhost:11434/v1")
    assert llm.model == "llama3"
    assert llm.base_url == "http://localhost:11434/v1"
    assert llm._llm is None


class TestLLMEnvOverride:
    """(2026-06-26 ARCH-002) 通过 settings 单例读 env

    (2026-06-29) deepeval 插件 import 时自动 load .env.local 注入 env, 这里
    每个 test 显式 delenv 清掉相关 env, 防止 os.getenv() 优先级压过 settings.
    """

    def test_openai_llm_reads_settings(self, monkeypatch):
        """OpenAILLM 不传参时读 settings.llm_model"""
        from src.config.settings import settings
        from src.generation.llm import OpenAILLM

        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.setattr(settings, "llm_model", "gpt-4o")
        llm = OpenAILLM()
        assert llm.model == "gpt-4o"

    def test_openai_llm_uses_api_key_from_settings(self, monkeypatch):
        """OpenAILLM.llm 触发 lazy load 时从 settings.openai_api_key 读 key, settings.openai_base_url 读 base url"""
        from src.config.settings import settings
        from src.generation.llm import OpenAILLM

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setattr(settings, "openai_api_key", "sk-env")
        monkeypatch.setattr(settings, "openai_base_url", "https://custom.example.com/v1")
        llm = OpenAILLM(model="gpt-4o-mini")
        # (2026-06-29 LC 替换) 内部切到 ChatOpenAI
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        call_kwargs = mock_openai.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-env"
        assert call_kwargs["base_url"] == "https://custom.example.com/v1"

    def test_local_llm_reads_settings(self, monkeypatch):
        """LocalLLM 不传参时读 settings.llm_model / settings.ollama_base_url"""
        from src.config.settings import settings
        from src.generation.llm import LocalLLM

        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.setattr(settings, "llm_model", "qwen2.5:7b")
        monkeypatch.setattr(settings, "ollama_base_url", "http://ollama.internal:11434/v1")
        llm = LocalLLM()
        assert llm.model == "qwen2.5:7b"
        assert llm.base_url == "http://ollama.internal:11434/v1"


class TestLocalLLMProperty:
    """LocalLLM.llm property 懒加载"""

    def test_local_llm_lazy_loads_ollama(self, monkeypatch):
        """.llm 触 ChatOllama 初始化"""
        from src.generation.llm import LocalLLM

        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        llm = LocalLLM(model="llama3")
        assert llm._llm is None

        with patch("langchain_ollama.ChatOllama") as mock_ollama:
            _ = llm.llm
        mock_ollama.assert_called_once_with(
            model="llama3",
            base_url="http://localhost:11434/v1",
            temperature=0.0,
        )

    def test_local_llm_caches_llm(self):
        """二次访问 .llm 返回缓存实例"""
        from src.generation.llm import LocalLLM

        llm = LocalLLM(model="llama3", base_url="http://localhost:11434/v1")
        with patch("langchain_ollama.ChatOllama") as mock_ollama:
            first = llm.llm
            second = llm.llm
        assert first is second
        assert mock_ollama.call_count == 1


class TestOpenAILLMProperty:
    """OpenAILLM.llm property 懒加载"""

    def test_openai_llm_with_max_tokens(self, monkeypatch):
        """OpenAILLM 传 max_tokens → kwargs 含 max_tokens"""
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        llm = OpenAILLM(model="gpt-4o-mini", max_tokens=4096)
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        call_kwargs = mock_openai.call_args.kwargs
        assert call_kwargs["max_tokens"] == 4096

    def test_openai_llm_default_max_tokens(self, monkeypatch):
        """(2026-06-26 ERR-005) OpenAILLM 不传 max_tokens → 自动用 defaults.DEFAULT_OPENAI_MAX_TOKENS=4096,
        防止用户提交任意长 prompt 导致无限 token 计费."""
        from src.common import defaults
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        llm = OpenAILLM(model="gpt-4o-mini")  # 不传 max_tokens
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        assert mock_openai.call_args.kwargs["max_tokens"] == defaults.DEFAULT_OPENAI_MAX_TOKENS

    def test_openai_llm_with_explicit_api_key(self, monkeypatch):
        """OpenAILLM 显式传 api_key → 不读 env"""
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-wrong")
        llm = OpenAILLM(model="gpt-4o-mini", api_key="sk-explicit")
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        assert mock_openai.call_args.kwargs["api_key"] == "sk-explicit"

    def test_openai_llm_no_base_url(self, monkeypatch):
        """OPENAI_BASE_URL 未设置 → kwargs base_url 为 defaults 默认 (空或自定义)"""
        from src.common import defaults
        from src.config.settings import settings
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        # (2026-06-29) deepeval 注入 .env.local, 显式清掉 settings.openai_base_url
        monkeypatch.setattr(settings, "openai_base_url", "")
        llm = OpenAILLM(model="gpt-4o-mini")
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        # (2026-06-29 LC 替换) ChatOpenAI 用 base_url 字段
        assert mock_openai.call_args.kwargs["base_url"] == defaults.DEFAULT_OPENAI_BASE_URL

    def test_openai_llm_caches_llm(self, monkeypatch):
        """二次访问 .llm 返回缓存实例"""
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        llm = OpenAILLM(model="gpt-4o-mini")
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            first = llm.llm
            second = llm.llm
        assert first is second
        assert mock_openai.call_count == 1

    def test_openai_llm_with_temperature(self, monkeypatch):
        """OpenAILLM 传 temperature → kwargs 含 temperature"""
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        llm = OpenAILLM(model="gpt-4o-mini", temperature=0.7)
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        assert mock_openai.call_args.kwargs["temperature"] == 0.7

    def test_openai_llm_deepseek_beta_url_suffix(self, monkeypatch):
        """(2026-06-24) deepseek base_url 自动追加 /beta (completions API 要求)"""
        from src.generation.llm import OpenAILLM

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        llm = OpenAILLM(model="deepseek-chat")
        with patch("langchain_openai.ChatOpenAI") as mock_openai:
            _ = llm.llm
        assert mock_openai.call_args.kwargs["base_url"] == "https://api.deepseek.com/beta"
