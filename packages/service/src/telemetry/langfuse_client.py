"""Langfuse 可观测性封装"""

import os
from dataclasses import dataclass, field
from typing import Any

from ..common import defaults

# ----------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------


@dataclass
class LangfuseConfig:
    """Langfuse 连接配置"""

    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"

    @classmethod
    def from_env(cls) -> LangfuseConfig:
        return cls(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", defaults.DEFAULT_LANGFUSE_PUBLIC_KEY),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", defaults.DEFAULT_LANGFUSE_SECRET_KEY),
            host=os.getenv("LANGFUSE_HOST", defaults.DEFAULT_LANGFUSE_HOST),
        )


# ----------------------------------------------------------------------
# Langfuse Client
# ----------------------------------------------------------------------


class LangfuseClient:
    """Langfuse 客户端封装（惰性初始化）"""

    _instance: LangfuseClient | None = None

    def __init__(self, config: LangfuseConfig | None = None):
        self._config = config or LangfuseConfig.from_env()
        self._client: Any = None

    @property
    def client(self) -> Any:
        """懒加载 Langfuse Python SDK client"""
        if self._client is None:
            try:
                # 软依赖: langfuse 未装降级到本地 logger, 不抛 ImportError
                from langfuse import Langfuse  # noqa: E402
            except ImportError as e:
                raise ImportError("langfuse 未安装。请运行: pip install langfuse") from e

            self._client = Langfuse(
                public_key=self._config.public_key,
                secret_key=self._config.secret_key,
                host=self._config.host,
            )
        return self._client

    def trace(
        self,
        name: str,
        metadata: dict | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
    ) -> Trace:
        """开启一个 trace"""
        return Trace(
            client=self.client,
            name=name,
            metadata=metadata or {},
            user_id=user_id,
            session_id=session_id,
            tags=tags,
        )

    def event(
        self,
        name: str,
        input: Any = None,
        output: Any = None,
        metadata: dict | None = None,
    ) -> None:
        """记录一个独立事件"""
        self.client.event(
            name=name,
            input=input,
            output=output,
            metadata=metadata or {},
        )

    def get_callback_handler(self) -> Any:
        """返回 Langfuse CallbackHandler (兼容 LangChain LCEL chain 的 callbacks=[] 注入)"""
        return self.client.get_callback_handler()

    def flush(self) -> None:
        """手动刷新，将 pending 的 trace 发送到 Langfuse 服务"""
        if self._client is not None and hasattr(self._client, "flush"):
            self._client.flush()

    def __enter__(self) -> LangfuseClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.flush()


class Trace:
    """Langfuse Trace 上下文管理器"""

    def __init__(
        self,
        client: Any,
        name: str,
        metadata: dict,
        user_id,
        session_id,
        tags,
    ):
        self._client = client
        self._name = name
        self._metadata = metadata
        self._user_id = user_id
        self._session_id = session_id
        self._tags = tags
        self._trace: Any = None

    def __enter__(self) -> Trace:
        self._trace = self._client.trace(
            name=self._name,
            metadata=self._metadata,
            user_id=self._user_id,
            session_id=self._session_id,
            tags=self._tags,
        )
        return self

    def __exit__(self, *args: Any) -> None:
        if self._trace is not None and hasattr(self._trace, "end"):
            self._trace.end()

    def span(
        self,
        name: str,
        input: Any = None,
        output: Any = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> Span:
        """在当前 trace 内开启一个 span"""
        return Span(
            trace=self._trace,
            name=name,
            input=input,
            output=output,
            metadata=metadata or {},
            **kwargs,
        )

    def update(self, **kwargs: Any) -> None:
        """更新 trace 元数据"""
        if self._trace is not None and hasattr(self._trace, "update"):
            self._trace.update(**kwargs)


class Span:
    """Langfuse Span 上下文管理器"""

    def __init__(
        self,
        trace: Any,
        name: str,
        input: Any,
        output: Any,
        metadata: dict,
        **kwargs: Any,
    ):
        self._trace = trace
        self._name = name
        self._input = input
        self._output = output
        self._metadata = metadata
        self._kwargs = kwargs
        self._span: Any = None

    def __enter__(self) -> Span:
        if self._trace is not None and hasattr(self._trace, "span"):
            self._span = self._trace.span(
                name=self._name,
                input=self._input,
                output=self._output,
                metadata=self._metadata,
                **self._kwargs,
            )
        return self

    def __exit__(self, *args: Any) -> None:
        if self._span is not None and hasattr(self._span, "end"):
            self._span.end(output=self._output)

    def update(self, **kwargs: Any) -> None:
        """更新 span 元数据"""
        if self._span is not None and hasattr(self._span, "update"):
            self._span.update(**kwargs)


def get_langfuse_client(config: LangfuseConfig | None = None) -> LangfuseClient:
    """从配置初始化 LangfuseClient（单例）"""
    if LangfuseClient._instance is None:
        LangfuseClient._instance = LangfuseClient(config)
    return LangfuseClient._instance


@dataclass
class RAGTraceContext:
    """RAG 流程追踪上下文

    记录一个完整 RAG 查询的全生命周期数据。
    """

    query: str
    trace_id: str = ""
    retrieve_latency_ms: float = 0.0
    generate_latency_ms: float = 0.0
    retrieved_nodes_count: int = 0
    top_k: int = 0
    response: str = ""
    sources: list[dict] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "trace_id": self.trace_id,
            "retrieve_latency_ms": self.retrieve_latency_ms,
            "generate_latency_ms": self.generate_latency_ms,
            "retrieved_nodes_count": self.retrieved_nodes_count,
            "response": self.response,
            "sources": self.sources,
            "error": self.error,
        }


def trace_rag_step(
    client: LangfuseClient,
    step_name: str,
    input_data: Any = None,
    output_data: Any = None,
    metadata: dict | None = None,
) -> Span:
    """追踪单个 RAG 步骤（简化版）

    用法：
        with trace_rag_step(lf, "retrieve", input=query) as span:
            nodes = retriever.retrieve(query)
            span.update(output={"node_count": len(nodes)})
    """
    return client.trace("rag_flow").span(
        name=step_name,
        input=input_data,
        output=output_data,
        metadata=metadata or {},
    )
