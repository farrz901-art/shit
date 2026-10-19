"""LLM 封装 (LangChain ChatOpenAI / ChatOllama)

ChatOpenAI 配 base_url 走任何 OpenAI 兼容端点 (DeepSeek / SiliconFlow / 本地 vllm 等),
不走 OpenAI 模型白名单.

(2026-06-26 ARCH-002) 改从 src.config.settings 读配置 (单一事实源).
Settings 单例在 import 时 cache env, 但保留 os.getenv() 直接调用作为兜底
(让 monkeypatch.setenv 在测试中能生效 — settings 单例 reload 不支持).
"""

import os
from typing import TYPE_CHECKING, Any

from ..common import defaults
from ..config.settings import settings

if TYPE_CHECKING:
    from langchain_ollama import ChatOllama
    from langchain_openai import ChatOpenAI


def _llm_model() -> str:
    """env 直接读 (兜底 settings cache, 测试可用 monkeypatch.setenv)"""
    return os.getenv("LLM_MODEL") or settings.llm_model or defaults.DEFAULT_LLM_MODEL_OPENAI


def _openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or settings.openai_api_key or defaults.DEFAULT_OPENAI_API_KEY


def _openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL") or settings.openai_base_url or defaults.DEFAULT_OPENAI_BASE_URL


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL") or settings.ollama_base_url or defaults.DEFAULT_OLLAMA_BASE_URL


def _ollama_model() -> str:
    return os.getenv("LLM_MODEL") or settings.llm_model or defaults.DEFAULT_LLM_MODEL_OLLAMA


class OpenAILLM:
    """OpenAI 兼容协议 LLM (DeepSeek / SiliconFlow / OpenAI / ...).

    `self.llm` 返 `langchain_openai.ChatOpenAI` 实例, 调用接口:
    - resp = self.llm.invoke(prompt) → AIMessage (用 resp.content 取文本)
    - resp = await self.llm.ainvoke(prompt) → AIMessage
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        # (2026-06-26 ERR-005) 默认走 defaults 兜底, 防止 token 计费失控.
        # 显式传 0 也允许 (某些模型 max_tokens=0 是合法值), 显式 None 表示"不传"
        # (由调用方全权负责 token 预算).
        max_tokens: int | None = defaults.DEFAULT_OPENAI_MAX_TOKENS,
    ):
        # (2026-06-26 ARCH-002) env 优先, settings 兜底
        self.model = model or _llm_model()
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._llm: ChatOpenAI | None = None

    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            # 重依赖 lazy: langchain_openai 冷启动 ~800ms, 非 OpenAI provider 路径不需要
            from langchain_openai import ChatOpenAI  # noqa: E402

            base_url = _openai_base_url()
            # DeepSeek completions API 走 /beta 端点 (chat API 走默认)
            if base_url and "deepseek" in base_url and not base_url.endswith("/beta"):
                base_url = base_url.rstrip("/") + "/beta"

            kwargs: dict[str, Any] = {
                "model": self.model,
                "api_key": self._api_key or _openai_api_key(),
                "base_url": base_url,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                kwargs["max_tokens"] = self._max_tokens
            self._llm = ChatOpenAI(**kwargs)
        return self._llm


class LocalLLM:
    """本地 Ollama LLM. `self.llm` 返 `langchain_ollama.ChatOllama`."""

    def __init__(self, model: str | None = None, base_url: str | None = None, temperature: float = 0.0):
        # (2026-06-26 ARCH-002) env 优先, settings 兜底
        self.model = model or _ollama_model()
        self.base_url = base_url or _ollama_base_url()
        self._temperature = temperature
        self._llm: ChatOllama | None = None

    @property
    def llm(self) -> ChatOllama:
        if self._llm is None:
            # 重依赖 lazy: langchain_ollama 冷启动 ~600ms, 非 Ollama provider 路径不需要
            from langchain_ollama import ChatOllama  # noqa: E402

            self._llm = ChatOllama(model=self.model, base_url=self.base_url, temperature=self._temperature)
        return self._llm
