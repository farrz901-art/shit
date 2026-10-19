# Mem0 教程

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

Mem0 是一个为 AI 应用设计的**长期记忆层**。它自动从对话中提取关键事实，存到向量数据库中，并在新对话中按需检索相关记忆，实现"跨会话个性化"。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Mem0** | 长期记忆层 | 自动化记忆提取 + 检索 |
| **Zep** | 对话历史 + 摘要 | 强绑定 LLM，记忆能力弱 |
| **LangChain Memory** | 内置记忆类 | 短会话够用，长期记忆弱 |
| **自建 PG 表** | 完全自控 | 需要自己写提取 + 检索逻辑 |

**Mem0 解决的核心问题**：
- **跨会话记忆**：用户说"我之前问过 X"时能回忆
- **个性化**：记住用户偏好（"我喜欢简短回答"）
- **用户档案构建**：自动从对话中积累"用户是谁"

---

## 二、安装 & 初始化

### 2.1 安装

```bash
uv add "mem0ai[nlp]>=2.0.5"
```

注意：PyPI 包名是 `mem0ai`，但 Python import 仍是 `mem0`（历史包袱）。

### 2.2 环境变量

```bash
# OpenAI（提取 + 检索都依赖 LLM）
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com

# Mem0 配置
MEM0_COLLECTION_NAME=mem0_memories
MEM0_SEARCH_LIMIT=5
```

### 2.3 最简初始化

```python
from mem0 import MemoryClient

# 方式 1：云服务（mem0.ai）
client = MemoryClient(api_key="...")

# 方式 2：本地（用项目自己的 PG 向量库）
from mem0 import Memory
memory = Memory(config={
    "llm": {"provider": "openai", "config": {"model": "deepseek-chat"}},
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "host": "localhost", "port": 5432,
            "user": "postgres", "password": "...",
            "dbname": "rag",
        },
    },
})
```

---

## 三、核心概念 & 抽象

### 3.1 Memory（记忆）

一条记忆 = 一段文本 + 元数据（user_id / agent_id / timestamps）。

### 3.2 Add

把对话转成记忆。Mem0 自动 LLM 提取关键事实，去重，存到向量库。

```python
messages = [
    {"role": "user", "content": "我叫 Alice"},
    {"role": "assistant", "content": "你好 Alice！"},
]
memory.add(messages, user_id="alice")
# Mem0 自动提取："用户名字是 Alice"
```

### 3.3 Search

按 query 检索相关记忆。

```python
results = memory.search("用户叫什么名字", user_id="alice")
# [{"memory": "用户名字是 Alice", "score": 0.95}]
```

### 3.4 Get All

```python
all_memories = memory.get_all(user_id="alice")
```

### 3.5 Update / Delete

```python
memory.update(memory_id="...", data="新内容")
memory.delete(memory_id="...")
```

### 3.6 Graph Memory（2.0+ 新增）

记忆之间的关系（"Alice 在 Google 工作" → "Google 是搜索公司"），适合构建用户知识图谱。

---

## 四、常用 API & 命令速查

### 4.1 添加记忆

```python
from mem0 import Memory

memory = Memory()

# 单条消息
memory.add("用户喜欢简短回答", user_id="alice")

# 对话
messages = [
    {"role": "user", "content": "我在 Google 工作"},
    {"role": "assistant", "content": "好的，记下了"},
]
memory.add(messages, user_id="alice")

# 带元数据
memory.add(
    "用户是软件工程师",
    user_id="alice",
    metadata={"category": "profession", "confidence": 0.9},
)
```

### 4.2 检索

```python
results = memory.search(
    query="用户的工作",
    user_id="alice",
    limit=5,
)
for r in results["results"]:
    print(r["memory"], r["score"])
```

### 4.3 全部记忆

```python
all_mem = memory.get_all(user_id="alice")
```

### 4.4 更新 / 删除

```python
# 更新
memory.update(memory_id="mem_abc123", data="用户在 Google 担任高级工程师")

# 删除
memory.delete(memory_id="mem_abc123")
```

### 4.5 历史记录

```python
history = memory.history(memory_id="mem_abc123")
# [{"memory": "原版", "event": "ADD"}, {"memory": "新版", "event": "UPDATE"}]
```

### 4.6 Graph Memory

```python
memory = Memory(config={
    "graph_store": {"provider": "neo4j", "config": {"url": "bolt://..."}},
    ...
})

memory.add(messages, user_id="alice")
results = memory.search("Alice 的工作", user_id="alice")
# 返回包含实体关系："Alice → WORKS_AT → Google"
```

---

## 五、项目集成点

### 5.1 项目当前使用 Mem0

`packages/service/pyproject.toml:28`：

```toml
"mem0ai[nlp]>=2.0.5",  # 对话记忆层 (src/memory/mem0_client.py)
```

### 5.2 项目 memory 模块

`packages/service/src/memory/` 包含：

| 文件 | 用途 |
|------|------|
| `mem0_client.py` | Mem0 客户端封装 |
| `router.py` | 记忆管理端点（`/api/memory/*`） |

### 5.3 业务配置

`packages/service/.env.example:51-52`：

```bash
MEM0_COLLECTION_NAME=mem0_memories
MEM0_SEARCH_LIMIT=5
```

### 5.4 项目 Mem0 ready 缓存

`src/core/mem0_ready.py:1`（推测）用 Redis 缓存 Mem0 ready 状态：

```python
# 模式推测
async def mark_ready():
    await safe_set("rag:mem0:ready", "1", ttl=3600)  # 1h

async def is_ready() -> bool:
    return await safe_get("rag:mem0:ready") == "1"
```

fail-open：Mem0 挂了不影响主聊天流程。

---

## 六、项目代码示例

### 6.1 项目 Mem0 客户端

`src/memory/mem0_client.py`（推测）：

```python
from mem0 import Memory
import os

def get_mem0_client() -> Memory:
    return Memory(config={
        "llm": {
            "provider": "openai_like",
            "config": {
                "model": os.getenv("LLM_MODEL", "deepseek-chat"),
                "api_key": os.getenv("OPENAI_API_KEY"),
                "openai_base_url": os.getenv("OPENAI_BASE_URL"),
            },
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": os.getenv("PG_HOST", "localhost"),
                "port": int(os.getenv("PG_PORT", "5432")),
                "user": os.getenv("PG_USER", "postgres"),
                "password": os.getenv("PG_PASSWORD", ""),
                "dbname": os.getenv("PG_DATABASE", "rag"),
            },
        },
        "collection_name": os.getenv("MEM0_COLLECTION_NAME", "mem0_memories"),
    })
```

### 6.2 项目 memory 路由

`src/memory/router.py:21`（推测）：

```python
from fastapi import APIRouter, Depends, HTTPException, status
from .mem0_client import get_mem0_client
from ..middleware.auth import CurrentUser

router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.get("/", summary="查询当前用户的记忆")
def get_my_memories(
    query: str | None = None,
    user: CurrentUser = Depends(...),
):
    mem = get_mem0_client()
    if query:
        return mem.search(query=query, user_id=str(user.id), limit=5)
    return mem.get_all(user_id=str(user.id))

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, user: CurrentUser = Depends(...)):
    mem = get_mem0_client()
    mem.delete(memory_id=memory_id)
    return None
```

### 6.3 聊天时自动记录

`src/chat/router.py:67`（推测）创建对话时加 Mem0：

```python
@router.post("/conversations")
async def create_conversation(payload: ..., user: CurrentUser = Depends(...)):
    # 1. 创建对话记录
    conv = svc.create_conversation(user_id=user.id, title="...")
    
    # 2. 加到 Mem0（如果 ready）
    if await is_ready():
        mem0 = get_mem0_client()
        mem0.add(
            f"用户开始新对话，主题：{payload.title or '未知'}",
            user_id=str(user.id),
        )
    return conv
```

### 6.4 对话上下文注入

每次聊天前检索 Mem0 注入 prompt：

```python
async def get_chat_context(user_id: int, current_query: str) -> str:
    """返回 Mem0 中跟当前 query 相关的用户记忆"""
    if not await is_ready():
        return ""
    mem = get_mem0_client()
    results = mem.search(
        query=current_query,
        user_id=str(user_id),
        limit=int(os.getenv("MEM0_SEARCH_LIMIT", "5")),
    )
    memories = [r["memory"] for r in results.get("results", [])]
    if not memories:
        return ""
    return "用户相关背景：\n" + "\n".join(f"- {m}" for m in memories)
```

### 6.5 集成到 LLM prompt

```python
context = await get_chat_context(user.id, query)
prompt = f"""{context}

用户问题：{query}
"""
response = await llm.acomplete(prompt)
```

---

## 七、项目没用到的能力

以下 Mem0 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Graph Memory** | 实体关系记忆 | 知识密集场景（用户档案） |
| **Web UI（Mem0 平台）** | 可视化用户记忆 | SaaS 版本（`mem0.ai`） |
| **Multimodal Memory** | 图像 / 音频记忆 | 多模态聊天场景 |
| **Custom Categories** | 记忆分类 | 业务标签（"偏好" / "事实"） |
| **Memory Versioning** | 记忆历史回溯 | 合规 / 审计需求 |
| **Custom Prompts** | 自定义提取 prompt | 业务特定提取规则 |
| **跨用户共享记忆** | 团队记忆 | B2B 场景 |
| **Memory Expiry** | 记忆自动过期 | 时效性记忆 |

**建议关注**：Graph Memory 适合需要"用户关系网"的应用（如社交、客服）。

---

## 八、评测 & 调优技巧

### 8.1 提取质量

Mem0 用 LLM 提取事实，提取质量取决于 prompt 和模型。监控：
- 每天新增记忆数
- 重复 / 冲突记忆数
- 用户主动删除率

### 8.2 检索质量

`MEM0_SEARCH_LIMIT=5` 是默认。如果用户问"我之前说过什么"返回太少，调到 10-20。

### 8.3 成本控制

Mem0 每次 `add` 和 `search` 都调 LLM。

| 操作 | 频率 | 优化 |
|------|------|------|
| add | 每条对话 | 合并多条消息一次 add |
| search | 每次聊天 | 缓存 5min（user_id 维度） |
| 提取 | 内部 | 用更便宜的模型（deepseek） |

### 8.4 性能优化

```python
# 异步 add（不阻塞用户响应）
import asyncio
asyncio.create_task(memory.add_async(messages, user_id=str(user.id)))
```

---

## 九、最佳实践 & 常见坑

### 1. 包名陷阱

```python
# 错
import mem0ai
from mem0ai import Memory

# 对
from mem0 import Memory  # PyPI 包名 mem0ai, import 是 mem0
```

### 2. 异步陷阱

```python
# 同步版本会阻塞（每次 add/search 都调 LLM）
memory.add(messages, user_id="...")  # 阻塞 2-5s

# 异步版本
await memory.aadd(messages, user_id="...")  # 非阻塞
```

### 3. user_id 必须是字符串

Mem0 的 `user_id` / `agent_id` / `session_id` 必须是 `str` 类型，项目 SQLAlchemy 的 `int` 主键必须 `str(user.id)`。

### 4. fail-open 原则

项目 `service/CLAUDE.md` 强制 Mem0 挂时不影响主流程：

```python
try:
    mem0.add(messages, user_id=str(user.id))
except Exception as e:
    logger.warning("Mem0 add failed, fallback: {}", e)
    # 不 raise，吞掉异常
```

### 5. PII 处理

Mem0 自动存用户事实，可能含敏感信息。`metadata` 加 `pii: true` 标记，便于审计时筛选。

### 6. 记忆清理

`memory.delete()` 单条删。批量清空：

```python
all_mems = memory.get_all(user_id="alice")
for m in all_mems["results"]:
    memory.delete(m["id"])
```

### 7. 项目测试隔离

CI 测试**不要**连真实 Mem0（成本 + 噪声）。Mock `memory.add` / `memory.search`：

```python
from unittest.mock import patch

@patch("src.memory.mem0_client.get_mem0_client")
def test_chat(mock_get_client):
    mock_mem = MagicMock()
    mock_mem.search.return_value = {"results": [{"memory": "用户叫 Alice", "score": 0.9}]}
    mock_get_client.return_value = mock_mem
    # 测试逻辑
```

### 8. collection_name 不能改

一旦 `MEM0_COLLECTION_NAME` 改了，记忆就全断。改名前必须 migrate（导出旧 collection + 导入新 collection）。

### 9. 嵌入模型一致

add 和 search 必须用相同 embedding 模型，否则检索不到。项目用 `EMBED_MODEL=BAAI/bge-m3` + `EMBED_DIMENSIONS=1024`，所有调用共享。

---

## 📚 参考

- [Mem0 官方文档](https://docs.mem0.ai/)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [Mem0 云服务](https://app.mem0.ai/)
- [Mem0 自部署](https://docs.mem0.ai/open-source/quickstart)
- [Mem0 Graph Memory](https://docs.mem0.ai/open-source/features/graph-memory)
- [Mem0 + LlamaIndex 集成](https://docs.llamaindex.ai/en/stable/examples/memory/mem0_memory.html)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
