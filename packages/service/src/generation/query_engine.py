"""QueryEngine 封装 (LangChain LCEL)

build_query_engine 返 _LCQueryEngine, 公开 .query / .aquery 接口.
内部走 LCEL RunnableParallel: 一次跑 retriever, 同时拿 docs + LLM response, 不双跑.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


@dataclass
class QueryResult:
    """结构化查询响应.

    - response: LLM 输出 str
    - sources: list[dict] (file_path / page_label / text), 前端依赖
    - source_nodes: LC Document 列表 (内部用; 项目内 0 真实调用方)
    - metadata: dict (保留 backward compat)
    """

    response: str
    sources: list[dict] = field(default_factory=list)
    source_nodes: Any = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_response(cls, response: str, source_docs: list | None = None) -> QueryResult:
        sources = []
        if source_docs:
            for doc in source_docs:
                entry: dict = {}
                meta = getattr(doc, "metadata", {}) or {}
                entry["file_path"] = meta.get("file_path", "")
                entry["page_label"] = meta.get("page_label", "")
                content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                entry["text"] = content[:200] + "..." if len(content) > 200 else content
                sources.append(entry)
        return cls(response=response, sources=sources, source_nodes=source_docs, metadata={})


class _LCQueryEngine:
    """LCEL chain 适配器, 公开 .query / .aquery 跟老 BaseQueryEngine 对齐."""

    def __init__(self, chain_with_docs: Runnable):
        # chain_with_docs.invoke(question) -> dict {"response": str, "docs": list[Document]}
        self._chain = chain_with_docs

    def query(self, question: str, **kwargs: Any) -> QueryResult:
        result = self._chain.invoke(question)
        return QueryResult.from_response(result["response"], source_docs=result["docs"])

    async def aquery(self, question: str, **kwargs: Any) -> QueryResult:
        result = await self._chain.ainvoke(question)
        return QueryResult.from_response(result["response"], source_docs=result["docs"])


def get_llm(llm_type: str | None = None, model: str | None = None, **kwargs: Any) -> Any:
    """返回 LC LLM 实例 (ChatOpenAI / ChatOllama)."""
    # 重依赖 lazy: defaults 模块加载读 env (side-effect), llm 模块触发 langchain_openai 装载
    from ..common import defaults  # noqa: E402
    from .llm import LocalLLM, OpenAILLM  # noqa: E402

    llm_type = llm_type or defaults.DEFAULT_LLM_TYPE
    model = model or defaults.DEFAULT_LLM_MODEL_OPENAI
    if llm_type == "openai":
        return OpenAILLM(model=model, **kwargs).llm
    return LocalLLM(model=model, **kwargs).llm


def build_query_engine(
    vector_store: Any,
    embedder: Any,
    llm: Any = None,
    top_k: int = 5,
    **kwargs: Any,
) -> _LCQueryEngine:
    """构造 LCEL chain. retriever 一次跑, docs 跟 response 一起返."""
    # 重依赖 lazy: langchain_core 冷启动 ~500ms, 非 query engine 路径不需要
    from langchain_core.output_parsers import StrOutputParser  # noqa: E402
    from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
    from langchain_core.runnables import RunnableLambda, RunnableParallel  # noqa: E402

    # vector_store 是项目 PGVectorStore (包装), 内部 .vector_store 是 LC PGVectorStore
    if hasattr(vector_store, "vector_store"):
        if vector_store._embedder is None:
            vector_store._embedder = embedder
        retriever = vector_store.vector_store.as_retriever(search_kwargs={"k": top_k})
    else:
        # 容错: 直接是 LC PGVectorStore (test mock 路径)
        retriever = vector_store.as_retriever(search_kwargs={"k": top_k})

    if llm is None:
        llm = get_llm()

    prompt = ChatPromptTemplate.from_template(
        "根据以下上下文回答。\n\n上下文：\n{context}\n\n问题：{question}\n\n回答："
    )

    def format_docs(docs: list) -> str:
        return "\n\n".join(d.page_content for d in docs)

    response_chain = prompt | llm | StrOutputParser()

    # RunnableParallel: 同时跑 retriever + passthrough question, 然后 .assign 算 response
    chain = RunnableParallel(
        question=RunnableLambda(lambda x: x),
        docs=retriever,
    ).assign(
        response=lambda x: response_chain.invoke(
            {
                "context": format_docs(x["docs"]),
                "question": x["question"],
            }
        )
    )

    return _LCQueryEngine(chain)


def query(question: str, query_engine: Any, **kwargs: Any) -> QueryResult:
    return query_engine.query(question, **kwargs)


async def aquery(question: str, query_engine: Any, **kwargs: Any) -> QueryResult:
    return await query_engine.aquery(question, **kwargs)
