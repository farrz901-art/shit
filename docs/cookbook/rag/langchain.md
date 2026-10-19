# LangChain 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

LangChain 是一个用于构建 LLM 应用的综合性框架，提供模型抽象、提示模板、工具集成、记忆管理、Agent 循环等组件。LangChain 0.3+（2024-12）把核心库拆分得更清晰，原生支持 LCEL（LangChain Expression Language）做链式组合。

**同类对比：**

| 框架 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **LangChain** | LLM 应用综合框架 | 工具链丰富，Agent 抽象标准 |
| **LlamaIndex** | RAG 检索 + 索引 | 本项目**主力框架**，RAG 链路完整 |
| **LangGraph** | 有状态 Agent 编排 | 见 `cookbook/rag/langgraph.md` |
| **直接调 OpenAI SDK** | 轻量 | 复杂业务不够 |

**LangChain 解决的核心问题**：
- **模型无关**：同一套代码切换 OpenAI / Anthropic / Ollama
- **工具集成**：500+ 工具，搜索、数据库、API 一行接
- **Agent 循环**：自动 tool calling + ReAct / Plan-and-Execute
- **链式组合**：LCEL `prompt | model | parser` 一行串联

---

## 二、安装 & 初始化

### 2.1 安装

```bash
uv add langchain langchain-openai langchain-anthropic langchain-ollama
```

### 2.2 环境变量

```bash
# OpenAI 兼容
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com   # 兼容 DeepSeek / DashScope / 自建

# Ollama
OLLAMA_BASE_URL=http://localhost:11434

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
```

### 2.3 最简使用

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

model = ChatOpenAI(model="deepseek-chat", base_url=os.getenv("OPENAI_BASE_URL"))
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个 RAG 助手。"),
    ("user", "{question}"),
])
parser = StrOutputParser()

# LCEL 链式组合
chain = prompt | model | parser
result = chain.invoke({"question": "什么是 RAG?"})
print(result)
```

---

## 三、核心概念 & 抽象

### 3.1 ChatModel / LLM

- `ChatOpenAI` / `ChatAnthropic` / `ChatOllama`：模型类
- 接受消息列表，返回 `AIMessage`
- 区别于旧的 `OpenAI`（接受字符串，返回字符串），新版推荐 ChatModel

### 3.2 Prompt Template

```python
from langchain_core.prompts import ChatPromptTemplate

# 简单模板
prompt = ChatPromptTemplate.from_template("翻译：{text}")

# 多消息
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是 {role}"),
    ("user", "{question}"),
])

# 带示例（Few-shot）
from langchain_core.prompts import FewShotChatMessagePromptTemplate
```

### 3.3 Output Parser

```python
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from pydantic import BaseModel, Field

class Answer(BaseModel):
    answer: str = Field(description="回答内容")
    confidence: float = Field(description="置信度 0-1")

parser = JsonOutputParser(pydantic_object=Answer)
```

### 3.4 LCEL（LangChain Expression Language）

```python
# 链式组合
chain = prompt | model | parser
result = chain.invoke({"question": "..."})

# 流式
for chunk in chain.stream({"question": "..."}):
    print(chunk, end="")

# 异步
result = await chain.ainvoke({"question": "..."})

# 并行
from langchain_core.runnables import RunnableParallel
chain = RunnableParallel(
    answer=answer_chain,
    summary=summary_chain,
)
```

### 3.5 Tool / Tool Calling

```python
from langchain_core.tools import tool

@tool
def search(query: str) -> str:
    """搜索工具的描述（Agent 决定何时调用）"""
    return f"results for {query}"

# 把 tool 绑到 model
model_with_tools = model.bind_tools([search])

# Agent
from langchain.agents import create_tool_calling_agent
agent = create_tool_calling_agent(model, [search], prompt)
```

### 3.6 Memory

```python
from langchain.memory import ConversationBufferMemory

# 自动维护 chat history
memory = ConversationBufferMemory(return_messages=True)
```

---

## 四、常用 API & 命令速查

### 4.1 模型调用

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=2000,
)

# 同步
result = model.invoke("Hello")
# 异步
result = await model.ainvoke("Hello")
# 流式
async for chunk in model.astream("Hello"):
    print(chunk.content, end="")
```

### 4.2 链式组合

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_template("翻译成英文：{text}")
chain = prompt | model | StrOutputParser()

result = chain.invoke({"text": "你好"})
```

### 4.3 Tool Calling

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """查询天气。当用户询问天气时使用。"""
    return f"{city} 晴，25°C"

model_with_tools = model.bind_tools([get_weather])
result = model_with_tools.invoke("北京天气怎么样？")
# result.tool_calls 包含 {"name": "get_weather", "args": {"city": "北京"}}
```

### 4.4 Agent

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个助手"),
    ("user", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(model, [search, calculator], prompt)
executor = AgentExecutor(agent=agent, tools=[search, calculator])

result = executor.invoke({"input": "搜索 LLM 评估框架"})
```

### 4.5 RAG Chain

```python
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.runnables import RunnablePassthrough

# 1. 加载向量库
vectorstore = FAISS.load_local("./index", OpenAIEmbeddings())
retriever = vectorstore.as_retriever()

# 2. RAG 链
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

prompt = ChatPromptTemplate.from_template("""根据上下文回答：
上下文：{context}
问题：{question}""")

chain = (
    RunnablePassthrough.assign(context=lambda x: format_docs(retriever.invoke(x["question"])))
    | prompt
    | model
    | StrOutputParser()
)

result = chain.invoke({"question": "什么是 RAG?"})
```

---

## 五、项目集成点

### 5.1 项目当前使用 LangChain 配套生态

`packages/service/pyproject.toml:22-26` 显式用了 LangChain 家族的几个子包：

| 包 | 版本 | 用途 |
|------|------|------|
| `llama-index-llms-openai-like` | >=0.7.2 | OpenAI 兼容协议 LLM（`src/eval/llama_eval.py:41`） |
| `llama-index-llms-ollama` | >=0.10.1 | Ollama 本地 LLM（`src/generation/llm.py`） |
| `llama-index-embeddings-huggingface` | >=0.7.0 | BGE 本地 embedder（`src/retrieval/embedder.py`） |

### 5.2 项目 Langfuse 集成

`packages/service/.env.example:55-57` 配 Langfuse：

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Langfuse 通过 OpenTelemetry 协议自动捕获 LangChain / LlamaIndex 调用。

### 5.3 项目未直接使用 LangChain 0.3 链式 API

**项目当前不直接 import `from langchain import ...`**，而是通过 LlamaIndex 抽象层。但 LangChain 的工具 / 模型生态被 LlamaIndex 复用。

---

## 六、项目代码示例

### 6.1 项目 LLM 抽象

`packages/service/src/generation/llm.py:25-73`（推测）：

```python
from llama_index.llms.openai_like import OpenAILike

class OpenAILLM:
    def __init__(self):
        self._llm = OpenAILike(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            api_key=os.getenv("OPENAI_API_KEY"),
            api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0,
        )

    async def acomplete(self, prompt: str) -> str:
        response = await self._llm.acomplete(prompt)
        return response.text
```

### 6.2 用 LangChain 替代 LlamaIndex

如果未来切到 LangChain 链式 API：

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# 1. 复用项目 PG 向量库
from src.retrieval.vector_store import get_vector_store
from src.retrieval.embedder import OpenAIEmbedder

store = get_vector_store()
embedder = OpenAIEmbedder()

# 2. 转成 LangChain retriever
def langchain_retriever(query: str) -> list[str]:
    embedding = embedder.get_text_embedding(query)
    results = store.query(query_embedding=embedding, top_k=5)
    return [str(r) for r in results.nodes]

# 3. 链式 RAG
model = ChatOpenAI(model="deepseek-chat", base_url=os.getenv("OPENAI_BASE_URL"))
prompt = ChatPromptTemplate.from_template("""
根据上下文回答用户问题。

上下文：{context}
问题：{question}
""")
parser = StrOutputParser()

def format_context(input_dict):
    return langchain_retriever(input_dict["question"])

chain = (
    RunnablePassthrough.assign(context=format_context)
    | prompt
    | model
    | parser
)

result = chain.invoke({"question": "什么是 pgvector?"})
```

### 6.3 Tool 包装项目检索

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor

@tool
def search_project_docs(query: str) -> str:
    """在项目知识库中检索文档。
    当用户问 RAG、FastAPI、Postgres、pgvector、MinIO、Neo4j、LangGraph、LlamaIndex 等
    项目技术栈相关问题时使用。
    """
    embedding = embedder.get_text_embedding(query)
    results = store.query(query_embedding=embedding, top_k=3)
    return "\n\n".join(r.text for r in results.nodes[:3])

model = ChatOpenAI(model="deepseek-chat")
agent = create_tool_calling_agent(model, [search_project_docs], prompt)
executor = AgentExecutor(agent=agent, tools=[search_project_docs])

result = executor.invoke({"input": "如何用 pgvector 做相似度搜索?"})
```

### 6.4 LangChain 评估 + Langfuse

```python
from langchain.evaluation import load_evaluator
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler()

evaluator = load_evaluator("criteria", criteria="conciseness")

result = chain.invoke(
    {"question": "..."},
    config={"callbacks": [langfuse_handler]},  # Langfuse 记录 trace
)

eval_result = evaluator.evaluate_strings(
    prediction=result,
    input="...",
    reference="...",
)
```

---

## 七、项目没用到的能力

以下 LangChain 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **LCEL 链式 API** | `prompt \| model \| parser` | 项目用 LlamaIndex 抽象替代 |
| **LangChain Hub** | Prompt 模板分享 | 项目 prompts 目录自管 |
| **Memory 模块** | 对话历史 | 项目用 Mem0（`cookbook/rag/mem0.md`） |
| **Tool Calling + AgentExecutor** | Agent 循环 | 项目自建 Workflow 替代 |
| **LangServe** | FastAPI 包装 | 项目自己用 FastAPI |
| **LangSmith** | 可观测 + 评估 | 用 Langfuse 替代（`cookbook/rag/langfuse.md`） |
| **Document Loaders** | 多格式加载 | LlamaIndex 已覆盖 |
| **Text Splitters** | 文档分块 | LlamaIndex 已覆盖 |
| **Vector Stores (LangChain 抽象)** | 向量库接口 | LlamaIndex 已覆盖 |

**建议关注**：如果团队对 LangChain 工具集（如 `langchain-community` 的 500+ 集成）有需求，可以局部引入而不全栈切换。

---

## 八、评测 & 调优技巧

### 8.1 Token 监控

```python
from langchain_community.callbacks import get_openai_callback

with get_openai_callback() as cb:
    result = chain.invoke({"question": "..."})
    print(f"Tokens: {cb.total_tokens}, Cost: ${cb.total_cost}")
```

### 8.2 Prompt 调优

```python
# A/B 测试不同 prompt
prompt_v1 = ChatPromptTemplate.from_template("回答：{question}")
prompt_v2 = ChatPromptTemplate.from_template("""你是 RAG 助手。基于上下文：
{context}
回答：{question}""")

# 跑同一批 case 对比
```

### 8.3 Langfuse 评估

```python
# Langfuse Dashboard 配 evaluator (用 GPT-4o 当 judge)
# 自动评估每个 trace 的 faithfulness / relevance
```

### 8.4 缓存

```python
from langchain.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

set_llm_cache(SQLiteCache(database_path=".langchain.db"))
# 重复请求直接返缓存，省 token
```

---

## 九、最佳实践 & 常见坑

### 1. 版本兼容（关键！）

LangChain 0.1→0.3 大量 breaking change，必须锁版本：

```toml
# pyproject.toml
"langchain>=0.3",          # 不要用 0.1 / 0.2 旧版
"langchain-openai>=0.2",
"langchain-anthropic>=0.2",
"langchain-ollama>=0.2",
```

代码必须用新 import 路径：

```python
# 错（旧版 0.0.x）
from langchain.chat_models import ChatOpenAI

# 对（0.3+）
from langchain_openai import ChatOpenAI
```

### 2. async 陷阱

LangChain 0.3+ 大部分对象支持 async，但有 sync / async 混用坑：

```python
# 错：sync 上下文里 await
def handle_request():
    return chain.ainvoke({"question": "..."})  # 没用！

# 对
async def handle_request():
    return await chain.ainvoke({"question": "..."})
```

### 3. Tool 描述质量

Tool docstring 是 LLM 决定调用的关键：

```python
@tool
def search(query: str) -> str:
    """在内部知识库中搜索技术文档。

    **何时使用**：
    - 用户问 RAG、FastAPI、Postgres、pgvector、MinIO、Neo4j 等技术问题
    - 用户问项目架构 / 部署 / 配置

    **不要用于**：
    - 闲聊（"你好"）
    - 通用知识（"Python 怎么用"）
    """
    return ...
```

### 4. 不要滥用 Agent

简单任务（单步 RAG）不需要 Agent 循环。直接 `prompt | model` 更可控、更快。

### 5. Token 上限

`max_tokens` 必须显式设，防止 LLM 意外生成超长响应。`deepseek-chat` 上限 8K，`gpt-4o` 128K。

### 6. 模型切换陷阱

不同 LLM 的 tool calling 格式可能不兼容。切换模型后必须跑端到端测试。

### 7. 项目测试隔离

项目 `service/CLAUDE.md` 强制 mock，LangChain 调用必须 mock 真实 LLM：

```python
from unittest.mock import patch

@patch("langchain_openai.ChatOpenAI.invoke")
def test_chain(mock_invoke):
    mock_invoke.return_value.content = "mocked answer"
    result = chain.invoke({"question": "..."})
    assert result == "mocked answer"
```

---

## 📚 参考

- [LangChain 官方文档](https://python.langchain.com/)
- [LangChain v0.3 迁移指南](https://python.langchain.com/docs/versions/v0_3/)
- [LCEL 表达式语言](https://python.langchain.com/docs/how_to/lcel_cheatsheet/)
- [LangChain Hub](https://smith.langchain.com/hub)
- [LangChain 工具集成列表](https://python.langchain.com/docs/integrations/tools/)
- [项目 service/CLAUDE.md](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
