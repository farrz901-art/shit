# Dify 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师

---

## 目录

- [一、是什么 & 适用什么问题](#一是什么--适用什么问题)
- [二、安装 & 初始化](#二安装--初始化)
- [三、核心概念 & 抽象](#三核心概念--抽象)
- [四、常用 API & 命令速查](#四常用-api--命令速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、评测 & 调优技巧](#八评测--调优技巧)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用什么问题

Dify 是一款开源的 LLM 应用开发平台，提供可视化的工作流编排、知识库管理、Agent 编排。它把 LLM 应用拆成"节点"（LLM 节点 / 知识检索节点 / 代码节点 / 条件分支），让非工程师也能搭 AI 应用。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Dify** | 可视化 LLM 应用平台 | 项目**主力 LLM 编排**（`src/integrations/dify_client.py`）|
| **LangChain** | Python LLM 框架 | 项目用其子包，但编排走 Dify |
| **Flowise** | 可视化 LLM 编排 | 跟 Dify 类似，生态略小 |
| **自建 LangGraph** | 代码编排 | 复杂度高，非可视化 |
| **Coze** | 字节跳动 LLM 平台 | SaaS 化，不适合自部署 |

**Dify 解决的核心问题**：
- **可视化编排**：复杂 LLM 流程图所见即所得
- **知识库 RAG**：上传文档 → 自动分块 + 嵌入 → 检索
- **多模型支持**：同一工作流换 GPT / Claude / Ollama 不用改代码
- **API 化**：工作流发布成 REST API，任意语言调
- **运维简化**：web UI 看 trace / log / 成本

---

## 二、安装 & 初始化

### 2.1 自部署（推荐）

```bash
cd docker
git clone https://github.com/langgenius/dify.git
cd dify/docker
docker compose up -d
# 访问 http://localhost/install 初始化 admin
```

### 2.2 SaaS

去 https://cloud.dify.ai 注册账号，拿 API key。

### 2.3 项目配置

`packages/service/.env.example:54-56`：

```bash
DIFY_BASE_URL=http://localhost/v1
DIFY_USER_ID=rag-eval-script
DIFY_DATASET_API_KEY=app-...
DIFY_CHAT_API_KEY=
```

### 2.4 Python SDK

```bash
uv add httpx  # 项目用 httpx 而非官方 SDK
```

项目没有用 `dify-sdk`，自己封装了 httpx 客户端（`src/integrations/dify_client.py`）。

---

## 三、核心概念 & 抽象

### 3.1 应用（App）

Dify 的核心。一个 App 包含：
- **Prompt 模板**：系统提示 + 用户输入变量
- **变量**：用户传入的参数
- **知识库**：可选，RAG 检索源
- **模型配置**：LLM provider + 模型 + 参数
- **工具**：可选，function calling

App 类型：
- **Chatflow**：多轮对话（带历史）
- **Workflow**：单轮执行
- **Completion**：简单问答
- **Agent**：智能体（工具调用 + ReAct）

### 3.2 知识库（Dataset）

RAG 的"文档存储"。上传文档 → 自动切块 + 嵌入 → 存入向量库（默认 Qdrant，可换 PG / Milvus / Weaviate）。

### 3.3 节点（Node）

工作流的最小单元：
- **Start / End**：入口 / 出口
- **LLM**：调 LLM
- **Knowledge Retrieval**：知识库检索
- **Code**：跑 Python / Node.js 代码
- **IF/ELSE**：条件分支
- **Iteration**：循环
- **Template Transform**：Jinja 模板
- **HTTP Request**：调外部 API
- **Tool**：自定义工具

### 3.4 Variables（变量）

工作流中的数据流变量。类型：
- `string` / `number` / `boolean`
- `object` / `array[object]`
- `file`

### 3.5 Conversation（对话）

Chatflow 的多轮对话由 `conversation_id` 维护，客户端不需自己存历史。

---

## 四、常用 API & 命令速查

### 4.1 Chat API（Chatflow）

```bash
curl -X POST "$DIFY_BASE_URL/chat-messages" \
  -H "Authorization: Bearer $DIFY_CHAT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {},
    "query": "什么是 RAG?",
    "user": "user-42",
    "response_mode": "streaming"
  }'
```

流式响应：SSE（`data: {...}\n\n`），最后一行 `data: [DONE]`。

### 4.2 Completion API（单轮）

```bash
curl -X POST "$DIFY_BASE_URL/completion-messages" \
  -H "Authorization: Bearer $DIFY_CHAT_API_KEY" \
  -d '{"inputs": {"q": "..."}, "user": "user-42", "response_mode": "blocking"}'
```

### 4.3 知识库 Dataset API

```bash
# 创建 dataset
curl -X POST "$DIFY_BASE_URL/datasets" \
  -H "Authorization: Bearer $DIFY_DATASET_API_KEY" \
  -d '{"name": "RAG docs"}'

# 上传文档
curl -X POST "$DIFY_BASE_URL/datasets/{dataset_id}/document/create_by_file" \
  -H "Authorization: Bearer $DIFY_DATASET_API_KEY" \
  -F "data='{\"indexing_technique\":\"high_quality\",\"process_rule\":{\"mode\":\"automatic\"}}'" \
  -F "file=@/path/to/doc.pdf"

# 检索
curl -X POST "$DIFY_BASE_URL/datasets/{dataset_id}/retrieve" \
  -H "Authorization: Bearer $DIFY_DATASET_API_KEY" \
  -d '{"query": "RAG", "top_k": 5}'
```

### 4.4 Workflow API

```bash
curl -X POST "$DIFY_BASE_URL/workflows/run" \
  -H "Authorization: Bearer $DIFY_WORKFLOW_API_KEY" \
  -d '{"inputs": {"q": "..."}, "user": "user-42", "response_mode": "blocking"}'
```

---

## 五、项目集成点

### 5.1 项目**主力 LLM 编排**

`packages/service/src/integrations/dify_client.py`（推测位置）：

```python
# 项目用 httpx 调 Dify，而非官方 SDK
import httpx
from loguru import logger

class DifyClient:
    def __init__(self):
        self._base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
        self._api_key = os.getenv("DIFY_CHAT_API_KEY")
        self._user_id = os.getenv("DIFY_USER_ID", "rag-eval-script")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def chat(self, query: str, conversation_id: str | None = None, inputs: dict | None = None) -> str:
        payload = {
            "inputs": inputs or {},
            "query": query,
            "user": self._user_id,
            "response_mode": "blocking",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        res = await self._client.post(
            f"{self._base_url}/chat-messages",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
        )
        res.raise_for_status()
        return res.json()["answer"]
```

### 5.2 项目业务场景

| 场景 | 调用的 Dify App |
|------|----------------|
| 产品订货号解析 | Completion App（`product_decoders`）|
| 评估 RAG | Chatflow App（`src/eval/llama_eval.py:41`）|
| 知识问答 | Chatflow + 知识库 |

### 5.3 缓存机制

`src/core/dify_query_cache.py`（推测）用 Redis 缓存 Dify 响应（10min TTL），减少重复查询：

```python
from src.core.redis_client import safe_get, safe_set

async def cached_dify_chat(client: DifyClient, query: str) -> str:
    cache_key = f"rag:dify:q:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
    cached = await safe_get(cache_key)
    if cached:
        return cached
    result = await client.chat(query)
    await safe_set(cache_key, result, ttl=600)  # 10min
    return result
```

### 5.4 产品订货号解析（业务核心）

`src/product_decoders/router.py`（推测）：

```python
@router.post("/decode", summary="解码产品订货号")
async def decode(payload: DecodeRequest):
    client = DifyClient()
    result = await client.chat(
        query=payload.order_code,
        inputs={"order_code": payload.order_code, "config": "default"},
    )
    return {"decoded": result}
```

### 5.5 评估流程

`src/eval/router.py:23`（推测）用 Dify 跑评估：

```python
@router.post("/", summary="上传评估数据集 + 跑 Dify 评估")
async def evaluate(file: UploadFile):
    csv = pd.read_csv(file.file)
    results = []
    client = DifyClient()
    for _, row in csv.iterrows():
        answer = await client.chat(query=row["question"])
        # 跟 expected_answer 比对，算 faithfulness / relevancy
        score = compute_metrics(answer, row["expected_answer"])
        results.append({"question": row["question"], "answer": answer, **score})
    return {"results": results}
```

---

## 六、项目代码示例

### 6.1 Dify 客户端封装

`src/integrations/dify_client.py`（项目风格）：

```python
import os
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

class DifyClient:
    def __init__(self):
        self._base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1").rstrip("/")
        self._api_key = os.getenv("DIFY_CHAT_API_KEY", "")
        self._dataset_api_key = os.getenv("DIFY_DATASET_API_KEY", "")
        self._user_id = os.getenv("DIFY_USER_ID", "rag-user")
        self._client = httpx.AsyncClient(timeout=30.0)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def chat(self, query: str, conversation_id: str | None = None, inputs: dict | None = None) -> dict:
        """调 Chatflow / Completion App"""
        payload = {
            "inputs": inputs or {},
            "query": query,
            "user": self._user_id,
            "response_mode": "blocking",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        res = await self._client.post(
            f"{self._base_url}/chat-messages",
            headers=self._headers(),
            json=payload,
        )
        res.raise_for_status()
        return res.json()

    async def chat_stream(self, query: str, conversation_id: str | None = None):
        """流式 Chatflow (SSE)"""
        payload = {
            "inputs": {},
            "query": query,
            "user": self._user_id,
            "response_mode": "streaming",
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat-messages",
            headers=self._headers(),
            json=payload,
        ) as res:
            async for line in res.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    async def retrieve(self, dataset_id: str, query: str, top_k: int = 5) -> list[dict]:
        """知识库检索"""
        res = await self._client.post(
            f"{self._base_url}/datasets/{dataset_id}/retrieve",
            headers={"Authorization": f"Bearer {self._dataset_api_key}"},
            json={"query": query, "top_k": top_k},
        )
        res.raise_for_status()
        return res.json().get("records", [])

    async def close(self):
        await self._client.aclose()
```

### 6.2 流式响应处理

```python
# FastAPI StreamingResponse 包装 Dify SSE
from fastapi.responses import StreamingResponse
from src.integrations.dify_client import DifyClient

@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    client = DifyClient()
    async def event_generator():
        async for chunk in client.chat_stream(payload.query, conversation_id=payload.conversation_id):
            if chunk == "[DONE]":
                yield "data: [DONE]\n\n"
                break
            yield f"data: {chunk}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 6.3 缓存 + 重试

```python
import hashlib
from src.core.redis_client import safe_get, safe_set
from src.core.dify_query_cache import CACHE_TTL

async def cached_chat(client: DifyClient, query: str, user_id: str = "default") -> str:
    """带缓存的 Dify chat (10 min TTL)"""
    cache_key = f"rag:dify:q:{hashlib.sha256(f'{user_id}:{query}'.encode()).hexdigest()[:16]}"
    cached = await safe_get(cache_key)
    if cached:
        logger.debug("Dify cache hit key={}", cache_key)
        return cached
    result = await client.chat(query)
    await safe_set(cache_key, result, ttl=CACHE_TTL)
    return result
```

### 6.4 评估流程

`src/eval/llama_eval.py:41`（推测）：

```python
import pandas as pd
from llama_index.llms.openai_like import OpenAILike
from llama_index.core.evaluation import FaithfulnessEvaluator, RelevancyEvaluator
from src.integrations.dify_client import DifyClient

async def run_dify_evaluation(csv_path: str) -> list[dict]:
    """上传 CSV → 调 Dify → LlamaIndex 评估 4 指标"""
    df = pd.read_csv(csv_path)
    client = DifyClient()
    judge_llm = OpenAILike(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base=os.getenv("OPENAI_BASE_URL"),
    )
    faith = FaithfulnessEvaluator(llm=judge_llm)
    rel = RelevancyEvaluator(llm=judge_llm)

    results = []
    for _, row in df.iterrows():
        question = row["question"]
        expected = row["expected_answer"]
        contexts = row.get("context", "").split("\n")
        # 1. 调 Dify
        answer = await client.chat(question)
        # 2. LlamaIndex 评估
        faith_score = faith.evaluate(query=question, response=answer, contexts=contexts).score
        rel_score = rel.evaluate(query=question, response=answer, contexts=contexts).score
        results.append({
            "question": question,
            "answer": answer,
            "expected": expected,
            "faithfulness": faith_score,
            "relevancy": rel_score,
        })
    return results
```

---

## 七、项目没用到的能力

以下 Dify 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Dify Agent** | 工具调用 + ReAct | 复杂业务场景 |
| **Multi-modal（图像 / 音频）** | 多模态 App | 项目当前纯文本 |
| **Dify Workflows API** | 复杂工作流 | 业务复杂时升级 |
| **Dify Plugin System** | 自定义节点 | 特殊业务逻辑 |
| **Dify Webhook** | 异步回调 | 长时间任务 |
| **App Blueprint 模板** | 复用 App 配置 | 多个相似 App 时 |
| **Dify Logs / Monitoring** | 自带 dashboard | 调试 / 监控 |
| **Dataset Auto-sync** | 自动同步外部源 | 数据动态更新 |

**建议关注**：Dataset auto-sync（自动从 S3 / DB 同步文档）能省手动上传。

---

## 八、评测 & 调优技巧

### 8.1 Dify App 性能监控

Dify 自带 dashboard：
- 平均响应时间
- Token 用量
- 错误率
- 用户反馈（👍/👎）

### 8.2 项目评估流程

1. 准备 CSV（question, expected_answer, context）
2. 上传到 `/api/evaluate`
3. 后台 worker 调 Dify + LlamaIndex 4 指标（Faithfulness / Relevancy / Correctness / Similarity）
4. 写 PG `eval_results` 表
5. Admin UI 看结果

### 8.3 调优方向

| 慢 | 调优 |
|----|------|
| Dify 响应慢 | 切小模型 / 减少节点 / 知识库分块策略 |
| Token 太多 | prompt 精简 / 关 verbose 节点 |
| 知识库不准 | 换 embedding 模型 / 调 top_k / 加 rerank |
| 幻觉多 | 强化 prompt"基于上下文" / temperature=0 |
| 成本高 | 用小模型（deepseek-chat 比 gpt-4o 便宜 50x）|

### 8.4 缓存策略

项目 `DIFY_QUERY_CACHE_TTL=600`（10min）适合：
- 重复 query 多（FAQ 机器人）
- 评估数据集（同一问题跑多次）

不适合：
- 个性化对话（每条 query 都不一样）
- 时效性内容（天气 / 股价）

---

## 九、最佳实践 & 常见坑

### 1. 错误处理

```python
from httpx import HTTPStatusError, TimeoutException

try:
    result = await client.chat(query)
except HTTPStatusError as e:
    logger.error("Dify {} error: {} body={}", e.response.status_code, e, e.response.text)
    raise
except TimeoutException:
    logger.warning("Dify timeout, retry...")
    raise
```

### 2. 重试策略

`tenacity` 库，项目已装：

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def chat_with_retry(self, query: str):
    return await self.chat(query)
```

### 3. async 上下文

DifyClient 必须用 `httpx.AsyncClient`，**不能**用 sync 客户端（会阻塞 event loop）：

```python
# ✅ 对
async with httpx.AsyncClient() as client:
    res = await client.post(...)
```

### 4. 环境变量

`DIFY_BASE_URL` 必须以 `/v1` 结尾：

```bash
DIFY_BASE_URL=http://localhost/v1     # ✅
DIFY_BASE_URL=http://localhost        # ❌ 缺 /v1
DIFY_BASE_URL=http://localhost/v1/    # ⚠️ 末尾斜杠可能 404
```

### 5. API Key 隔离

- **Chat API key**：给 Chatflow / Completion
- **Dataset API key**：给知识库管理
- **Workflow API key**：给 Workflow

不同 App 不同 key，项目用环境变量隔离。

### 6. 对话历史

Dify Chatflow 自动管理历史，**不要**自己拼接 `messages` 数组。

```python
# ✅ 对：传 conversation_id
await client.chat(query, conversation_id=conv_id)

# ❌ 错：自己拼历史
await client.chat(full_history_as_string)
```

### 7. 流式 vs 阻塞

- **阻塞**（`response_mode=blocking`）：简单，等全部结果
- **流式**（`response_mode=streaming`）：LLM streaming + SSE，适合聊天 UI

### 8. PII 处理

Dify 输入会进 LLM，不要传：
- 密码 / token / API key
- 完整身份证 / 银行卡
- 邮箱（如必须，用 `***@x.com` 脱敏）

### 9. 失败 fallback

```python
async def chat_with_fallback(client: DifyClient, query: str) -> str:
    try:
        return await client.chat(query)
    except Exception as e:
        logger.warning("Dify failed, fallback to direct LLM: {}", e)
        # 降级到直接调 OpenAI / Ollama
        return await direct_llm_call(query)
```

### 10. 项目测试隔离

CI 测试**不要**连真实 Dify（避免噪声 + 费用）。Mock `DifyClient.chat`：

```python
from unittest.mock import AsyncMock, patch

@patch("src.integrations.dify_client.DifyClient.chat")
async def test_decode(mock_chat):
    mock_chat.return_value = {"answer": "{\"model\": \"X\"}"}
    # 测试逻辑
```

### 11. SSE 解析

流式响应是 SSE 格式，**不是** WebSocket。客户端：

```typescript
const eventSource = new EventSource("/api/chat/stream");
eventSource.onmessage = (e) => {
  const chunk = JSON.parse(e.data);
  console.log(chunk.answer);
};
```

后端要 `data: <json>\n\n` 格式。

### 12. Dify 限流

Dify 自部署默认无内置限流，生产环境加 Nginx / API gateway 限流。

---

## 📚 参考

- [Dify 官方文档](https://docs.dify.ai/)
- [Dify API 参考](https://docs.dify.ai/api-reference/)
- [Dify GitHub](https://github.com/langgenius/dify)
- [Dify Self-host](https://docs.dify.ai/getting-started/install-self-hosted/docker-compose)
- [Dify SDKs](https://docs.dify.ai/guides/tools/tool-advanced)
- [项目 service/CLAUDE.md](../../packages/service/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
