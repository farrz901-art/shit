# Langfuse 教程

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

Langfuse 是开源的 LLM 可观测性 + 评估平台。它通过 OpenTelemetry 协议自动捕获每次 LLM 调用的输入、输出、token 数、延迟、成本，并在 Web Dashboard 提供 trace 可视化、prompt 管理、评估指标、用户反馈。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Langfuse** | 开源 LLM 可观测 + 评估 | 自部署友好（MIT 协议），功能完整 |
| **LangSmith** | LangChain 官方 | 强绑定 LangChain |
| **Helicone** | LLM 代理 + 监控 | 简单代理模式 |
| **Phoenix (Arize)** | LLM tracing + 评估 | 实验性，自部署稍复杂 |
| **OpenLLMetry** | OpenTelemetry 标准 | 需自己搭 dashboard |

**Langfuse 解决的核心问题**：
- **Trace 追踪**：每个请求的完整调用链（retriever → LLM → tool）
- **Token + 成本监控**：按用户 / 模型 / 时间维度统计
- **Prompt 版本管理**：团队共享 prompt 模板，记录每次用哪个版本
- **评估**：用 LLM-as-judge 给每次 trace 打分
- **用户反馈**：前端集成"👍/👎"按钮，写回 trace

---

## 二、安装 & 初始化

### 2.1 安装

```bash
uv add langfuse
# 或
pip install langfuse
```

### 2.2 SaaS 注册

去 https://cloud.langfuse.com 注册账号，拿到：
- `LANGFUSE_PUBLIC_KEY=pk-lf-...`
- `LANGFUSE_SECRET_KEY=sk-lf-...`
- `LANGFUSE_HOST=https://cloud.langfuse.com`

### 2.3 自部署（可选）

```bash
docker run -d --name langfuse \
  -p 3000:3000 \
  -e DATABASE_URL=postgresql://... \
  -e NEXTAUTH_SECRET=... \
  langfuse/langfuse:latest
```

### 2.4 环境变量

```bash
# packages/service/.env
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 三、核心概念 & 抽象

### 3.1 Trace（追踪）

一次完整请求的调用链。包含多个 Span / Generation / Event。

```
Trace: chat_request_42
├── Span: retrieve (200ms)
│   ├── Event: query_rewrite
│   └── Event: similarity_search
├── Generation: llm_call_1 (500ms, 200 tokens)
│   ├── Input: prompt
│   └── Output: response
├── Span: rerank (50ms)
└── Generation: llm_call_2 (300ms, 150 tokens)
```

### 3.2 Span（区间）

有开始 / 结束时间的操作，可以嵌套（span 里套 span）。

### 3.3 Generation（LLM 调用）

特殊的 Span，专用于 LLM 调用。自动记录：input、output、model、token 数、cost。

### 3.4 Event（事件）

无持续时间的离散事件（"cache hit"、"user feedback"）。

### 3.5 Score（评分）

附加到 Trace 或 Span 的评估分（faithfulness=0.85, relevance=0.92, user_rating=👍）。

### 3.6 Prompt（提示模板）

Langfuse 的 prompt 仓库，支持版本管理 + A/B 跟踪。

---

## 四、常用 API & 命令速查

### 4.1 Python SDK 基础

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="https://cloud.langfuse.com",
)

# 1. 简单 trace
trace = langfuse.trace(name="rag_query", user_id="user-42")
trace.update(input="什么是 RAG?", output="RAG 是...")

# 2. Span + Generation
span = trace.span(name="retrieve", input={"query": "..."})
span.end(output={"docs": [...]})

generation = trace.generation(
    name="llm_call",
    model="deepseek-chat",
    input=[{"role": "user", "content": "..."}],
    output={"role": "assistant", "content": "..."},
    usage={"input": 100, "output": 200, "unit": "TOKENS"},
)
```

### 4.2 Decorator 风格

```python
from langfuse.decorators import observe, langfuse_context

@observe()
def rag_query(question: str) -> str:
    # 自动追踪整个函数
    docs = retrieve(question)
    answer = llm.complete(question, docs)
    return answer

# 嵌套 span
@observe()
def retrieve(query: str) -> list[str]:
    return vectorstore.search(query)

# 访问当前 trace
@observe()
def llm_complete(prompt: str) -> str:
    langfuse_context.update_current_observation(
        model="deepseek-chat",
        usage={"input": 100, "output": 200, "unit": "TOKENS"},
    )
    return model.invoke(prompt)
```

### 4.3 集成 LangChain / LlamaIndex

```python
# LangChain 集成
from langfuse.callback import CallbackHandler
from langchain_openai import ChatOpenAI

langfuse_handler = CallbackHandler()
model = ChatOpenAI(model="gpt-4o")
result = model.invoke("Hello", config={"callbacks": [langfuse_handler]})

# LlamaIndex 集成（项目用）
from llama_index.core import Settings
from langfuse.llama_index import LlamaIndexCallbackHandler

Settings.callback_manager = CallbackManager([LlamaIndexCallbackHandler()])
```

### 4.4 评分

```python
# 在 trace 上打分
trace.score(name="faithfulness", value=0.85, comment="跟上下文一致")
trace.score(name="user_rating", value=1, data_type="CATEGORICAL")  # 1=👍, 0=👎

# 在 span 上打分
span.score(name="retrieval_precision", value=0.7)
```

### 4.5 Prompt 管理

```python
# 从 Langfuse 拉 prompt 模板
prompt = langfuse.get_prompt("rag_system_prompt", label="production")
compiled = prompt.compile(question="什么是 RAG?", context="...")

# 用 Langfuse prompt 替代硬编 prompt
```

---

## 五、项目集成点

### 5.1 项目当前配置 Langfuse

`packages/service/.env.example:55-57`：

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 5.2 项目 RAG query 缓存

`src/core/dify_query_cache.py`（推测）用了 Langfuse 类似概念做 query 缓存：

> 实际是项目内部用 Langfuse 的"score + comment"做 query 复盘

### 5.3 项目 LLM 调用追踪

`src/generation/llm.py:25-73` 的 `OpenAILLM` / `LocalLLM` 在生产环境会通过 callback manager 自动上报到 Langfuse。

### 5.4 项目评估流程

```bash
# 项目评估流程
1. 上传 CSV 到 /api/evaluate
2. 后台跑 LlamaIndex 4 指标
3. 写结果到 DB
4. （可选）通过 Langfuse SDK 写 score 到 trace
```

---

## 六、项目代码示例

### 6.1 项目 LLM 调用追踪

`src/generation/llm.py:25-73`（推测）：

```python
from langfuse.llama_index import LlamaIndexCallbackHandler
from llama_index.core import Settings, CallbackManager
from llama_index.llms.openai_like import OpenAILike

# 1. 初始化 callback handler
langfuse_handler = LlamaIndexCallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)
Settings.callback_manager = CallbackManager([langfuse_handler])

# 2. LLM 调用（自动上报）
llm = OpenAILike(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base=os.getenv("OPENAI_BASE_URL"),
)

response = await llm.acomplete(prompt)
# 自动在 Langfuse dashboard 出现 trace
```

### 6.2 项目 RAG 评估 trace

`src/eval/router.py:23`（推测）：

```python
from langfuse import Langfuse

langfuse = Langfuse()

@router.post("/api/evaluate", summary="跑评估并上传 Langfuse")
async def run_evaluation(file: UploadFile, ...):
    # 1. 读 CSV
    cases = parse_csv(file)

    # 2. 每个 case 创建 trace
    for case in cases:
        trace = langfuse.trace(
            name="rag_evaluation",
            user_id=user.id,
            metadata={"case_id": case.id},
        )

        # 3. 跑 RAG
        answer = await workflow.arun(case.question)
        trace.update(input=case.question, output=answer.response)

        # 4. 算指标 + 上报
        score = compute_faithfulness(answer, case)
        trace.score(name="faithfulness", value=score)

    return {"task_id": "..."}
```

### 6.3 用户反馈集成

前端"👍/👎"按钮（`packages/web/app/api/feedback/route.ts` 推测）：

```typescript
// BFF route
export async function POST(request: Request) {
  const { trace_id, rating } = await request.json();
  await fetch(`${process.env.LANGFUSE_HOST}/api/public/scores`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(
        `${process.env.LANGFUSE_PUBLIC_KEY}:${process.env.LANGFUSE_SECRET_KEY}`
      ).toString("base64")}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      traceId: trace_id,
      name: "user_rating",
      value: rating === "up" ? 1 : 0,
      dataType: "CATEGORICAL",
    }),
  });
}
```

### 6.4 Prompt 版本管理

`prompts/rag_system_v1.txt` 当前文件，Langfuse prompt 仓库备份：

```python
# 把项目 prompt 同步到 Langfuse
from langfuse import Langfuse
from pathlib import Path

langfuse = Langfuse()
prompt_text = Path("prompts/rag_system.txt").read_text()

langfuse.create_prompt(
    name="rag_system",
    prompt=prompt_text,
    labels=["production"],
    config={"model": "deepseek-chat", "temperature": 0},
)

# 拉取用
prompt = langfuse.get_prompt("rag_system", label="production")
```

---

## 七、项目没用到的能力

以下 Langfuse 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Trace Dashboard** | Web 可视化 | 已配 SaaS 账号即可用 |
| **Token / Cost 监控** | 按用户 / 模型统计 | Dashboard 实时显示 |
| **Prompt 版本管理** | 团队共享 + A/B 测试 | 当前 prompts 目录自管 |
| **Dataset + Evaluation** | 评估数据集管理 | 走 CSV + DeepEval 替代 |
| **User Feedback（👍/👎）** | 用户反馈回写 | 待集成 |
| **LLM-as-Judge Score** | 自动评估每个 trace | DeepEval 替代 |
| **Experiment（A/B 测试）** | 对比两个 prompt | 关键改动时使用 |
| **Session Replay** | 复盘完整对话 | 调试用户问题 |

**建议关注**：User Feedback（前端加 👍/👎 按钮）是产品迭代最直接的信号。

---

## 八、评测 & 调优技巧

### 8.1 Token 监控

Langfuse Dashboard 实时显示：
- 总 token 用量
- 按模型 / 用户 / 时间切分
- 单次调用成本

### 8.2 Prompt 调优

```python
# 1. 创建 prompt v1
langfuse.create_prompt(name="rag_v1", prompt=old_prompt, labels=["production"])

# 2. 测试新 prompt
new_prompt = "..."  # 改进了
langfuse.create_prompt(name="rag_v1", prompt=new_prompt, labels=["staging"])

# 3. 跑评估对比
# Langfuse 实验功能可对比两个 prompt 的指标
```

### 8.3 慢请求定位

Dashboard 按 p50 / p95 / p99 延迟排序，找到慢的 trace 排查。

### 8.4 成本控制

按用户 / session 维度查 token 用量，识别滥用 / 异常请求。

---

## 九、最佳实践 & 常见坑

### 1. API Key 安全

- 永远不要把 Langfuse API Key commit 到 Git
- 生产环境用 env 注入（`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`）
- 前端调用必须通过 BFF，不能暴露 secret

### 2. async / sync 混用

```python
# 错：在 async 函数里用 sync Langfuse SDK
async def handle():
    langfuse.trace(...)  # 阻塞！
# 对：用异步版本（@observe 装饰器自动处理）
```

### 3. 网络失败

Langfuse SDK 本地 buffer，网络挂了不阻塞主流程（类似 Loguru）。但要监控 buffer 是否堆积。

### 4. PII 处理

trace 默认会记录 LLM 输入输出，可能含用户邮箱 / 手机号。配置 `mask` 函数脱敏：

```python
langfuse = Langfuse(mask={"input": lambda s: s.replace(email, "***")})
```

### 5. 采样

高 QPS 时不必每个请求都 trace，按概率采样：

```python
import random
if random.random() < 0.1:  # 10% 采样
    trace = langfuse.trace(...)
```

### 6. 评估延迟

LLM-as-Judge 评估是异步的，几分钟才能在 Dashboard 看到 score，别误以为没生效。

### 7. 项目 LLM 调用必须用 callback manager

直接 `await llm.acomplete(prompt)` 不会自动上报。必须：

```python
Settings.callback_manager = CallbackManager([LlamaIndexCallbackHandler()])
```

### 8. 项目测试隔离

CI 测试**不要**连真 Langfuse（避免产生噪声数据 + 浪费 token）。Mock `langfuse.trace(...)` 等。

---

## 📚 参考

- [Langfuse 官方文档](https://langfuse.com/docs)
- [Langfuse Python SDK](https://langfuse.com/docs/sdk/python)
- [Langfuse LlamaIndex 集成](https://langfuse.com/docs/integrations/llama-index)
- [Langfuse LangChain 集成](https://langfuse.com/docs/integrations/langchain)
- [Langfuse OpenLLMetry 集成](https://langfuse.com/docs/integrations/openllmetry)
- [Langfuse 自部署](https://langfuse.com/docs/deployment/self-host)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
