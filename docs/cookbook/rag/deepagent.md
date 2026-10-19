# Deep Agents 教程

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

Deep Agents 是 LangChain 团队 2025 年开源的"高级 Agent 框架"，在 LangGraph 之上提供预配置的 Agent harness（执行环境），包含规划、子 Agent、上下文管理、文件系统虚拟化等开箱即用能力。

**同类对比：**

| 框架 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Deep Agents** | 高级 Agent harness | LangGraph 之上的快捷方式 |
| **LangGraph** | 底层 Agent 编排 | 见 `cookbook/rag/langgraph.md` |
| **LangChain** | LLM 抽象 | 模型/工具集成的中间层 |
| **CrewAI** | 多 Agent 协作 | 角色 + 任务模式 |
| **AutoGen** | Microsoft 多 Agent | 较新，生态小 |

**Deep Agents 解决的核心问题**：
- **避免重复造轮子**：常见的 "planner + executor + memory" 模式直接用
- **复杂任务分而治之**：自动创建子 Agent 处理子任务
- **上下文管理**：自动压缩 / 裁剪长上下文
- **虚拟文件系统**：Agent 可以读写"文件"作为状态

---

## 二、安装 & 初始化

### 2.1 安装

```bash
uv add deepagents
# 或
pip install deepagents
```

### 2.2 初始化

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-4o",
    tools=[my_search, my_calculator],
    system_prompt="You are a helpful research assistant.",
)
```

### 2.3 环境变量

```bash
# OpenAI
OPENAI_API_KEY=sk-xxx
# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
# Ollama 本地
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 三、核心概念 & 抽象

### 3.1 Agent Harness（执行环境）

Deep Agents 提供一个开箱即用的 Agent "harness"，包含：
- **Task planning**：自动分解复杂任务
- **Sub-agent spawning**：动态创建子 Agent 处理子任务
- **Context management**：自动管理长上下文
- **Virtual file system**：Agent 可读写"文件"作为状态

### 3.2 TodoList

Agent 内部维护 todo list，跟踪子任务进度。

### 3.3 Sub-agents

主 Agent 可以创建"子 Agent"做更细的任务，比如：
- 主 Agent 决定"我需要查 X 数据"
- 派子 Agent 查 X 数据并返回结果

### 3.4 VirtualFileSystem

Agent 用"虚拟文件"作为状态存储，模拟真实工作流（写文件、读文件、grep）。

### 3.5 Tools

Deep Agents 接受 LangChain `@tool` 装饰的函数作为工具，跟 LangChain / LangGraph 完全兼容。

---

## 四、常用 API & 命令速查

### 4.1 最简创建

```python
from deepagents import create_deep_agent
from langchain_core.tools import tool

@tool
def search(query: str) -> str:
    """搜索工具"""
    return f"results for {query}"

agent = create_deep_agent(
    model="openai:gpt-4o",
    tools=[search],
    system_prompt="You are a research assistant.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "查询 RAG"}]})
print(result["messages"][-1].content)
```

### 4.2 流式输出

```python
for event in agent.stream({"messages": [{"role": "user", "content": "..."}]}):
    for node, value in event.items():
        print(f"[{node}] {value}")
```

### 4.3 自定义子 Agent

```python
from deepagents import create_deep_agent
from deepagents.subagents import SubAgent

research_subagent = {
    "name": "research-agent",
    "description": "专门做研究的子 Agent",
    "system_prompt": "You are a research specialist.",
    "tools": [search_tool],
}

agent = create_deep_agent(
    model="openai:gpt-4o",
    tools=[calculator],
    subagents=[research_subagent],
)
```

### 4.4 持久化

```python
from langgraph.checkpoint.postgres import PostgresSaver

saver = PostgresSaver(connection_string="postgresql://...")
graph = create_deep_agent(
    model="openai:gpt-4o",
    tools=[...],
    checkpointer=saver,
)
# 用 thread_id 跨会话
config = {"configurable": {"thread_id": "user-123"}}
result = graph.invoke({"messages": [...]}, config=config)
```

---

## 五、项目集成点

### 5.1 项目当前未使用 Deep Agents

**项目当前未集成 Deep Agents**。Agent 编排走自建 Workflow 基类 + LlamaIndex（见 `cookbook/rag/langgraph.md` 和 `cookbook/rag/llama-index.md`）。

### 5.2 项目 AI 栈现状

| 组件 | 项目使用 | Deep Agents 等效 |
|------|---------|----------------|
| LLM 调用 | LlamaIndex `LLM` | `create_deep_agent(model=...)` |
| 工具 | LlamaIndex `QueryEngineTool` | LangChain `@tool` |
| 工作流 | `BaseWorkflow` | 自动 planning |
| 状态 | `ResponseEvent` | `VirtualFileSystem` + Checkpoint |
| 多 Agent | 单 Agent | Sub-agents |

### 5.3 集成建议

如果将来需要复杂多 Agent 协作（如"研究 Agent + 写作 Agent + 审核 Agent"），Deep Agents 是最省力的方案。

---

## 六、项目代码示例

### 6.1 项目当前 LLM 接口

`packages/service/src/generation/llm.py:25-73` 定义了项目的 LLM（`OpenAILLM` + `LocalLLM`）。如果集成 Deep Agents，可以用类似配置：

```python
# Deep Agents 集成
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:deepseek-chat",                    # 跟项目 LLM_MODEL 一致
    base_url=os.getenv("OPENAI_BASE_URL"),            # 复用 OPENAI_BASE_URL
    api_key=os.getenv("OPENAI_API_KEY"),
    tools=[rag_search_tool, calculator_tool],
)
```

### 6.2 项目检索作为工具

`packages/service/src/retrieval/vector_store.py:102` 的 `store.query()` 可以包装成 LangChain tool：

```python
from langchain_core.tools import tool

@tool
def rag_search(query: str) -> str:
    """在项目知识库里检索相关内容"""
    embedder = OpenAIEmbedder()
    store = get_vector_store()
    embedding = embedder.get_text_embedding(query)
    results = store.query(query_embedding=embedding, top_k=5)
    return "\n\n".join(r.text for r in results.nodes)
```

### 6.3 项目当前 Workflow（对比）

`packages/service/src/orchestration/simple_rag.py:8-29`：

```python
class SimpleRAGWorkflow(BaseWorkflow):
    async def arun(self, query: str, **kwargs) -> ResponseEvent:
        index = VectorStoreIndex.from_vector_store(self._vector_store, embed_model=self._embedder)
        retriever = VectorIndexRetriever(index=index, similarity_top_k=self._top_k)
        nodes = retriever.retrieve(query)
        context_str = "\n\n".join(n.get_content() if hasattr(n, "get_content") else str(n) for n in nodes)
        prompt = f"上下文：\n{context_str}\n\n问题：{query}\n\n回答："
        response_obj = self._llm.complete(prompt)
        response_text = response_obj.text if hasattr(response_obj, "text") else str(response_obj)
        return ResponseEvent(response=response_text, source_nodes=nodes, steps_used=["retrieve", "generate"])
```

Deep Agents 等价代码：

```python
from deepagents import create_deep_agent

@tool
def retrieve(query: str) -> str:
    """在项目知识库里检索"""
    # ... 同上 ...
    return "\n\n".join(r.text for r in results.nodes)

agent = create_deep_agent(
    model="openai:deepseek-chat",
    tools=[retrieve],
    system_prompt="你是一个 RAG 助手。回答用户问题时，先用 retrieve 工具检索。",
)
```

Deep Agents 自动：
1. 解析用户问题
2. 决定何时调 `retrieve` 工具
3. 把检索结果拼到 prompt
4. 多次迭代直到答完

### 6.4 Langfuse 追踪集成

`src/core/lifespan.py:35-44` 用 loguru + Langfuse。如果用 Deep Agents，Langfuse 集成通过 `langfuse_callback`：

```python
from langfuse.callback import CallbackHandler

langfuse = CallbackHandler()
result = agent.invoke(
    {"messages": [{"role": "user", "content": "..."}]},
    config={"callbacks": [langfuse]},
)
```

---

## 七、项目没用到的能力

以下 Deep Agents 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Sub-agents** | 多 Agent 协作 | 复杂任务分解时使用 |
| **TodoList 自动管理** | 任务进度跟踪 | 长任务场景 |
| **VirtualFileSystem** | 状态外部化 | 需要持久化 Agent 状态时 |
| **Harness 中间件** | 自定义 Agent 行为 | 高度定制时 |
| **Human-in-the-loop** | 中断 + 人工审批 | `langgraph` interrupt + Deep Agents 包装 |
| **Long-term Memory** | 跨会话记忆 | 已有 Mem0（`cookbook/rag/mem0.md`） |
| **Streaming output** | token-by-token 输出 | 适合 LLM 流式场景 |

**建议关注**：Sub-agents 适合"研究 → 写作 → 审核"的多 Agent 流程。

---

## 八、评测 & 调优技巧

### 8.1 延迟监控

Deep Agents 自动通过 LangGraph tracing 上报每个 Node 耗时。在 Langfuse / LangSmith 看每个 sub-agent 调用时长。

### 8.2 Token 控制

```python
agent = create_deep_agent(
    model="openai:deepseek-chat",
    tools=[...],
    max_tokens=4096,          # 单次响应上限
    max_iterations=10,        # 工具调用迭代上限
)
```

### 8.3 成本控制建议

- **限制 max_iterations**：防止 Agent 无限循环
- **使用 cheaper model** 做规划，expensive model 做执行
- **工具结果压缩**：返回的搜索结果如果太长，先 LLM summarize 再传给主 Agent

### 8.4 评估

跟普通 Agent 一样用 Langfuse / LangSmith 评估：
- 任务完成率
- 平均迭代次数
- 工具调用正确率

---

## 九、最佳实践 & 常见坑

### 1. 版本兼容

Deep Agents 跟 LangGraph 紧耦合，跟 LangGraph 0.3+ 配套使用。LangChain 0.1+ 配套。

```python
# 错误：用了 LangGraph 0.1 API
from langgraph.graph import Graph  # 0.1 旧 API
# 正确：0.3+ API
from langgraph.graph import StateGraph
```

### 2. async 陷阱

```python
# 同步调用
result = agent.invoke({"messages": [...]})

# 异步调用（FastAPI 上下文必须 async）
result = await agent.ainvoke({"messages": [...]})
```

### 3. 工具设计

工具的 `docstring` 是 Agent 决定何时调用的关键：

```python
@tool
def search(query: str) -> str:
    """在内部知识库中搜索相关文档。
    当用户询问需要事实/数据/历史信息的问题时使用。
    输入：用户问题的关键词
    输出：相关文档片段
    """
    # ...
```

### 4. 避免无限循环

Agent 可能陷入"调工具 → 没答案 → 再调工具"的循环，必须设 `max_iterations`。

### 5. Token 上限

Deep Agents 自动管理上下文，但单次 LLM 调用仍有 `max_tokens` 限制。设 `max_tokens=4096` 防止单次调用过大。

### 6. 持久化选型

- **开发**：`MemorySaver`（内存，重启丢失）
- **生产**：`PostgresSaver`（跨进程共享）

---

## 📚 参考

- [Deep Agents GitHub](https://github.com/langchain-ai/deepagents)
- [Deep Agents 文档](https://docs.langchain.com/oss/python/deepagents/overview)
- [LangGraph 文档](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangChain Tools 文档](https://python.langchain.com/docs/how_to/custom_tools/)
- [Langfuse 集成](https://langfuse.com/docs/integrations/langchain)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
