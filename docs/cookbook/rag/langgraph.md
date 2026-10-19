# LangGraph 教程

> 📅 创建日期：2026-06-19
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`（后端源码在 `packages/service/src/` 下）
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师，需要理解本项目为什么这样用、能怎么扩展

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

LangGraph 是 LangChain 团队开发的有状态 AI Agent 编排框架，提供基于有向图（DAG）的计算模型来构建多步、有状态的 LLM 应用。

**同类对比：**

| 框架 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **LangGraph** | 有状态 Agent 图编排 | 复杂工作流需要明确状态机时使用 |
| **LlamaIndex** | RAG 检索 + 索引 + 查询一站式 | 本项目**主力框架**，覆盖检索、生成、评估 |
| **LangChain** | LLM 抽象 + 工具链 | LangGraph 的前身，但图编排更灵活 |
| **自建 Workflow** | 轻量顺序/多步 RAG | 本项目有 SimpleRAGWorkflow + MultiStepRAGWorkflow |

**LangGraph 专注解决的问题**：传统的 LLM 调用是"请求-响应"模式，无状态、无中间步骤。LangGraph 的图计算模型让开发者能精确控制每一步：
- 状态持久化（一个 Agent 可以在多轮交互中维护状态）
- 条件分支（根据 LLM 输出决定下一步走向）
- Human-in-the-loop（在关键节点暂停，等人批准后再继续）
- 细粒度流式输出（逐 token、逐步输出中间结果）

---

## 二、安装 & 初始化

### 2.1 安装

```bash
# pip
pip install -U langgraph

# uv（本项目包管理器）
uv add langgraph
```

> ⚠️ **本项目当前未使用 LangGraph**。如果是给本项目加新功能，先跟团队确认是否需要引入 LangGraph，还是用已有的 LlamaIndex Workflow 或自建 Workflow 能满足需求。

### 2.2 基本初始化

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from typing import TypedDict, Literal

# 定义状态类型
class AgentState(TypedDict):
    messages: list
    next_step: str

# 创建图
graph = StateGraph(AgentState)

# 后续：添加节点、边、编译
```

### 2.3 环境变量

LangGraph 本身不直接调用 LLM，需要配合 LangChain 或其他 LLM 库。项目支持两种 LLM 模式：

- **OpenAI 兼容协议**（默认）：通过 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 配置（可指向 DeepSeek、DashScope 等）
- **Ollama 本地部署**：通过 `OLLAMA_BASE_URL` 配置（项目 `packages/service/src/generation/llm.py`）

```bash
# OpenAI 兼容（DeepSeek 示例）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com

# 或 Ollama 本地
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 三、核心概念 & 抽象

### 3.1 State（状态）

LangGraph 中所有数据都通过 State 流动。State 是一个 TypedDict，定义了节点的输入输出契约：

```python
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # add_messages 是 reducer
    next_action: str
    context: list[str]
```

`Annotated[list, add_messages]` 中的 `add_messages` 是 reducer 函数——当多个节点都想追加消息时，reducer 决定如何合并。

### 3.2 Node（节点）

Node 是图中的一个计算单元，接收状态、返回状态更新：

```python
def retrieve_node(state: AgentState) -> dict:
    query = state["messages"][-1].content
    docs = retrieve_docs(query)  # 实际业务中替换为检索逻辑
    return {"context": docs, "next_action": "generate"}
```

### 3.3 Edge（边）

Edge 连接节点，定义执行流。普通边（固定路径）和条件边（分支）：

```python
# 普通边
graph.add_edge("retrieve", "generate")

# 条件边
graph.add_conditional_edges(
    "checker",
    lambda state: "retry" if state.get("retry_count", 0) < 3 else "final",
    {"retry": "retrieve", "final": END}
)
```

### 3.4 Checkpoint（检查点/持久化）

LangGraph 内置持久化支持。每次图执行到节点边界时，自动将状态保存到 Checkpointer：

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = graph.compile(checkpointer=checkpointer)
```

支持多种后端：`MemorySaver`（内存）、`SqliteSaver`（文件）、`PostgresSaver`（数据库）。

### 3.5 Thread（线程）

Thread 是 LangGraph SDK（服务端）的概念。部署后，每次对话创建一个 Thread，同一个 Thread 内的所有图执行共享 Checkpoint 历史。客户端的 `thread_id` 参数将多次调用关联到同一个会话：

```python
config = {"configurable": {"thread_id": "user-session-123"}}
result = graph.invoke(input, config=config)
```

### 3.6 Subgraph（子图）

大图可以嵌套子图。子图的输入/输出通过 `StateGraph` 的边界暴露：

```python
sub_graph = StateGraph(SubState)
# ... 定义子图节点和边

main_graph.add_node("sub", sub_graph)  # 子图作为 main 的一个节点
```

### 3.7 Compile（编译）

定义完节点和边之后，需要编译图才能执行。编译过程做拓扑排序、验证可达性、注入持久化：

```python
app = graph.compile(checkpointer=checkpointer)
```

---

## 四、常用 API & 命令速查

### 4.1 创建并执行简单图

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class State(TypedDict):
    messages: list[str]

def node_a(state: State) -> dict:
    return {"messages": state["messages"] + ["processed by A"]}

def node_b(state: State) -> dict:
    return {"messages": state["messages"] + ["processed by B"]}

builder = StateGraph(State)
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)
graph = builder.compile()

result = graph.invoke({"messages": ["hello"]})
print(result["messages"])
# ['hello', 'processed by A', 'processed by B']
```

### 4.2 带条件分支

```python
def router(state: State) -> str:
    if "urgent" in state["messages"][-1].lower():
        return "escalate"
    return "normal_reply"

builder.add_conditional_edges("router", router, {
    "escalate": "expert_node",
    "normal_reply": "auto_reply_node",
})
```

### 4.3 带 Checkpoint 持久化

```python
from langgraph.checkpoint.memory import MemorySaver

saver = MemorySaver()
graph = builder.compile(checkpointer=saver)

# 第一次执行
config = {"configurable": {"thread_id": "thread-1"}}
result1 = graph.invoke({"messages": ["你好"]}, config)

# 第二次执行（同一 thread，状态延续）
result2 = graph.invoke({"messages": ["接着说"]}, config)
```

### 4.4 流式输出

```python
for event in graph.stream({"messages": ["讲个故事"]}, config):
    for key, value in event.items():
        print(f"节点 {key} 输出: {value}")
```

---

## 五、项目集成点

### 5.1 本项目不使用 LangGraph

**本项目当前未接入 LangGraph。** AI 工作流使用 LlamaIndex 驱动：

| 组件 | 项目使用的方案 | LangGraph 等效概念 |
|------|---------------|-------------------|
| RAG 单步检索 | `SimpleRAGWorkflow` (`packages/service/src/orchestration/simple_rag.py`) | `StateGraph` + retrieve/generate 节点 |
| RAG 多步检索 | `MultiStepRAGWorkflow` (`packages/service/src/orchestration/multi_step_rag.py`) | 条件边 + 循环 |
| 状态管理 | 类成员变量 + `ResponseEvent` | `TypedDict` State + reducer |
| 持久化 | `session_scope()` + PG | `Checkpointer` |
| 流式 | FastAPI `StreamingResponse` | `graph.stream()` |

### 5.2 如果用 LangGraph 重构现有 Workflow

项目现有的 `BaseWorkflow` 在 `packages/service/src/orchestration/base.py`：

```python
class BaseWorkflow:
    def __init__(self, events: list[type] | None = None):
        self._events = events

    async def arun(self, query: str, **kwargs) -> ResponseEvent:
        raise NotImplementedError
```

如果要迁移到 LangGraph，每个 `node` 函数对应现有 `arun` 中的一个步骤，`State` 的 `messages` 字段替代 `_events`，`Checkpointer` 替代手动的事件拼接。

---

## 六、项目代码示例

### 6.1 项目的 SimpleRAGWorkflow（当前实现）

`packages/service/src/orchestration/simple_rag.py:8-29` 展示了项目当前的简单 RAG 流程：

```python
class SimpleRAGWorkflow(BaseWorkflow):
    async def arun(self, query: str, **kwargs) -> ResponseEvent:
        # 1. 检索
        index = VectorStoreIndex.from_vector_store(
            self._vector_store, embed_model=self._embedder)
        retriever = VectorIndexRetriever(index=index, similarity_top_k=self._top_k)
        nodes = retriever.retrieve(query)

        # 2. 生成
        context_str = "\n\n".join(
            n.get_content() if hasattr(n, "get_content") else str(n) for n in nodes)
        prompt = f"上下文：\n{context_str}\n\n问题：{query}\n\n回答："
        response_obj = self._llm.complete(prompt)
        response_text = response_obj.text if hasattr(response_obj, "text") else str(response_obj)
        return ResponseEvent(response=response_text, source_nodes=nodes, steps_used=["retrieve", "generate"])
```

这是一个两步顺序流程：检索 → 生成。如果用 LangGraph 实现，会写成两个独立的 Node，通过 Edge 串联。

### 6.2 项目的 MultiStepRAGWorkflow（当前实现）

`packages/service/src/orchestration/multi_step_rag.py:17-44` 展示了多步 RAG：

```python
class MultiStepRAGWorkflow(BaseWorkflow):
    async def arun(self, query: str, **kwargs) -> ResponseEvent:
        for step_idx in range(self._max_steps):
            # 检索
            nodes = retriever.retrieve(current_query)
            all_nodes.extend(nodes)
            # 生成
            response = self._llm.complete(prompt)
            if len(response.text) >= 20 and unique_nodes:
                return ResponseEvent(response=response.text, ...)
            # 反思：生成更精确的追问
            current_query = self._llm.complete(followup_prompt).text
        return ResponseEvent(response=response.text, ...)
```

这个循环+条件判断的模式正是 LangGraph 条件边的用武之地。LangGraph 版本会有一个 `conditional_edge` 来检查结果并决定是继续检索还是生成最终回答。

### 6.3 项目的 LLM 接口

`packages/service/src/generation/llm.py:25-73` 定义了项目的 LLM 调用接口（`LocalLLM` 和 `OpenAILLM` 两种实现）。如果集成 LangGraph，可以用 LangChain 的 `ChatOllama` 或 `ChatOpenAI` 作为适配层：

```python
# 项目现有：packages/service/src/generation/llm.py
from llama_index.core.llms import LLM

# LangGraph 集成用：
from langchain_ollama import ChatOllama
llm = ChatOllama(model="qwen2.5:7b", temperature=0)

# 在 Node 中使用
def generate_node(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
```

### 6.4 项目向量检索

`packages/service/src/retrieval/vector_store.py:102` 和 `packages/service/src/retrieval/embedder.py` 提供了检索和嵌入能力。LangGraph 的检索节点可以直接复用这些：

```python
from src.retrieval.embedder import OpenAIEmbedder
from src.retrieval.vector_store import PGVectorStore, get_vector_store

# 在 LangGraph Node 中复用
def retrieve_node(state: AgentState) -> dict:
    embedder = OpenAIEmbedder()
    store: PGVectorStore = get_vector_store()
    query = state["messages"][-1].content
    # 复用项目的 embedding + 检索逻辑
    embedding = embedder.get_text_embedding(query)
    results = store.query(query_embedding=embedding, top_k=5)
    return {"context": [str(r) for r in results.nodes]}
```

---

## 七、项目没用到的能力

以下为 LangGraph 核心能力，项目当前未使用（**待评估**）：

| 能力 | 用途 | 什么场景会用到 |
|------|------|---------------|
| **Subgraph（子图）** | 将复杂图拆成可复用的子图模块 | 多 Agent 协作（一个子图负责检索，一个负责生成） |
| **Human-in-the-loop（中断）** | 在关键节点暂停执行，等人工审批 | 审核工作流（`packages/service/src/approvals/` 当前用状态机，LangGraph 可做更动态的流程） |
| **Time Travel（时间旅行）** | 回退到前一个 Checkpoint 重新执行 | Agent 出错时回滚到好的状态重跑 |
| **LangGraph Platform（Server SDK）** | 将 LangGraph 部署为微服务 | 如果将来需要独立 Agent 服务 |
| **Long-term Memory** | 跨会话持久化到外部存储 | 项目已有 Mem0（`packages/service/src/memory/`），功能重叠 |

**建议优先关注**：Human-in-the-loop 能力。项目当前审核工作流（`packages/service/src/approvals/`）用状态机实现，如果需要更灵活的"人介入"流程（如在关键决策点暂停等待审批），LangGraph 的条件边 + Checkpoint 组合会非常合适。

---

## 八、评测 & 调优技巧

### 8.1 延迟监控

LangGraph 自带 tracing 集成（通过 LangSmith）。每个 Node 的执行时间、输入输出大小都可观察：

```python
# 设置 LangSmith tracing（LangGraph 自动上报）
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_API_KEY"] = "lsv2_..."
```

### 8.2 Token 控制

在 Node 中注入 token 计数器：

```python
def llm_node(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    total_tokens = response.usage_metadata["total_tokens"]
    logger.info("LLM 调用消耗 {} tokens", total_tokens)
    return {"messages": [response]}
```

### 8.3 Prompt 迭代

LangGraph 的结构化节点设计让 prompt 迭代更清晰——每个 Node 的 prompt 独立维护，不影响其他节点。

### 8.4 成本控制建议

- 使用条件边尽早退出：`max_steps` / `max_tokens` 阈值检查节点应在循环图的前端
- Checkpoint 频率：`MemorySaver` 是内存操作，但 `PostgresSaver` 每次 checkpoint 写一次 DB，高频图要合理设置

---

## 九、最佳实践 & 常见坑

### 1. 版本兼容（LangGraph 0.1 → 0.3+ 重大变更）

LangGraph 在 2025 年经历了多次 API 变更：
- **0.1.x**：`StateGraph` 尚在实验期，API 不稳定
- **0.2.x**：引入 `add_conditional_edges` 替代旧的 `cond_edge`
- **0.3.x+**（当前）：`MessagesState` 成为默认 State，`START`/`END` 节点改用模块顶层常量
- **2026**：文档迁移到 `docs.langchain.com`，旧域名 `langchain-ai.github.io/langgraph` 重定向

```python
# 当前推荐写法（0.3+）：
from langgraph.graph import StateGraph, MessagesState, START, END
# 不要用：
# from langgraph.graph import Graph  # 0.1 旧 API
```

### 2. async 陷阱

```python
# 正确：Node 可以是 async 函数
async def retrieve_node(state: AgentState) -> dict:
    docs = await vector_store.asearch(...)
    return {"context": docs}

# 正确：用 ainvoke
result = await graph.ainvoke(input)
```

Node 函数支持 sync 和 async 混用——LangGraph 会自动 await async 节点。

### 3. Checkpoint 持久化选择

- **开发测试**：`MemorySaver`（0 配置，重启丢失）
- **单机持久**：`SqliteSaver`（SQLite 文件）
- **生产多实例**：`PostgresSaver`（共享存储，支持水平扩展）

```python
from langgraph.checkpoint.postgres import PostgresSaver

saver = PostgresSaver(connection_string="postgresql://...")
# 首次运行需要建表
saver.setup()
```

### 4. State 不变量

不修改 State 中已存在的字段值（除非用 reducer）。修改已赋值字段会导致 reducer 冲突：

```python
class State(TypedDict):
    messages: Annotated[list, add_messages]  # 用 reducer 追加
    counter: int                              # 覆盖式赋值

# 节点对 messages 只能追加，不能替换：
def bad_node(state: State) -> dict:
    return {"messages": ["new"]}  # 错误！会叠加到已有 messages

def good_node(state: State) -> dict:
    return {"new_field": "value"}  # 正确：新字段覆盖
```

### 5. 循环图必须包含终止条件

LangGraph 支持循环（通过条件边回到前序节点），但必须确保存在终止路径。项目 `MultiStepRAGWorkflow` 的 `max_steps` 模式就是良好实践：

```python
# 相当于 LangGraph 的条件边 + max_steps
def should_continue(state: AgentState) -> str:
    if state["step_count"] >= state["max_steps"]:
        return "final"
    if len(state["messages"][-1].content) >= 20:
        return "final"
    return "retry"
```

---

## 📚 参考

- [LangGraph 官方文档](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph 概念指南](https://docs.langchain.com/oss/python/langgraph/concepts/high_level)
- [LangGraph Cookbook](https://docs.langchain.com/oss/python/langgraph/tutorials)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [LlamaIndex 官方文档](https://docs.llamaindex.ai/)——本项目主力框架

---

**状态：** 🚧 样例

**最后更新：** 2026-06-19
