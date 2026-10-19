# Vercel AI SDK 教程

> 📅 创建日期：2026-06-26
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：A-AI 库
> 🎯 读者：中高级 Python 工程师（前端技术背景或配合前端开发）

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

**Vercel AI SDK** 是 Vercel 团队维护的 TypeScript 工具包，为构建 AI 驱动的应用提供统一的 API 抽象层。它的设计理念是：**一次编写，任意 LLM 后端**。

### 解决的核心问题

| 问题 | AI SDK 方案 |
|------|------------|
| 每个 LLM provider 有各自 SDK 和 API 格式 | 统一 `generateText` / `streamText` / `useChat` 接口 |
| 流式输出需要手动处理 SSE / WebSocket | `streamText` + `useChat` 自动处理 |
| chat 状态管理（消息列表、loading、错误） | `useChat` hook 封装完整状态 |
| 结构化输出解析繁琐 | `generateObject` + Zod schema 一步到位 |
| tool calling 多轮交互要自己写循环 | `maxSteps` 自动处理多轮 tool roundtrip |

### 同类对比

| 项目 | 定位 | 语言 | 前端集成 |
|------|------|------|----------|
| **AI SDK** | LLM 统一 TS 接口 + React hooks | TypeScript | 一等公民（`useChat` / `useCompletion`） |
| LangChain | LLM 编排框架（Chain / Agent / Tool） | Python/TS | 无专用 hooks，需自己管理状态 |
| LlamaIndex | 数据索引 + RAG 框架 | Python/TS | 无专用 hooks |
| Dify | 低代码 LLM 应用平台 | Python | 提供 REST API，前端自己调用 |

**核心差异**：AI SDK 是**前端优先**的 LLM 工具包，React hooks 是它的招牌能力；LangChain/LlamaIndex 更侧重后端编排。

---

## 二、安装 & 初始化

### 安装

当前项目使用 Bun，已安装的 AI SDK 相关包（[packages/web/package.json](packages/web/package.json)）：

```bash
# core SDK + React hooks（项目中已安装）
bun add ai @ai-sdk/react
```

项目 `packages/web/package.json:29` 中已锁定：

```json
"@ai-sdk/react": "^3.0.210",
"ai": "^6.0.208",
```

### provider 安装

AI SDK 需要配合具体的 LLM provider 使用。常见的 provider 包：

```bash
bun add @ai-sdk/openai      # OpenAI / Azure OpenAI
bun add @ai-sdk/anthropic    # Anthropic Claude
bun add @ai-sdk/google       # Google Gemini
bun add @ai-sdk/deepseek     # DeepSeek
bun add @ai-sdk/groq         # Groq
```

### 环境变量

在 `.env.local` 中配置 API Key：

```bash
# 如果使用 Vercel AI Gateway（默认）
AI_GATEWAY_API_KEY=your_key_here

# 如果使用具体 provider
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
DEEPSEEK_API_KEY=sk-xxx
```

### 最小的 Next.js 路由（Route Handler）

创建 `app/api/chat/route.ts`：

```typescript
import {
  streamText,
  UIMessage,
  convertToModelMessages,
  createUIMessageStreamResponse,
  toUIMessageStream,
} from 'ai';

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json();

  const result = streamText({
    model: "xai/grok-build-0.1",  // Vercel AI Gateway 默认模型
    messages: await convertToModelMessages(messages),
  });

  return createUIMessageStreamResponse({
    stream: toUIMessageStream({ stream: result.stream }),
  });
}
```

---

## 三、核心概念 & 抽象

AI SDK 的架构分为三层，理解这三层是上手的关键：

### 1. AI SDK Core — 核心 LLM 调用

| 抽象 | 用途 | 类比 |
|------|------|------|
| `generateText` | 非流式文本生成 | 类似 OpenAI `chat.completions.create` |
| `streamText` | 流式文本生成 + tool calling | 类似 SSE 流式响应 |
| `generateObject` | 结构化数据生成（JSON） | 类似 Instructor / Outlines |
| `tool` | 定义 LLM 可调用的工具 | 类似 OpenAI function calling |
| `Agent` | 多步 agent 执行单元 | 类似 LangGraph 的 Agent |

### 2. AI SDK UI — 前端集成

| 抽象 | 用途 |
|------|------|
| `useChat` | Chat 交互状态管理（消息列表、输入、loading、错误、重试） |
| `useCompletion` | 非对话式补全（类似 Cursor 的 inline 补全） |
| `useObject` | 流式 JSON 对象消费 |

### 3. Provider — LLM 后端接入

每个 provider 包导出模型实例，格式统一：

```typescript
import { openai } from '@ai-sdk/openai';
import { anthropic } from '@ai-sdk/anthropic';
import { deepseek } from '@ai-sdk/deepseek';

model: openai('gpt-5.1')          // → OpenAI
model: anthropic('claude-sonnet-4-6-20251001')  // → Claude
model: deepseek('deepseek-reasoner')           // → DeepSeek R1
```

### 消息生命周期（完整流程）

```
User Input → useChat.sendMessage()
          → POST /api/chat（发送 UIMessage[]）
          → server: convertToModelMessages() 清洗 UI 元数据
          → server: streamText() 调用 LLM
          → server: toUIMessageStream() + createUIMessageStreamResponse() 返回
          → client: useChat 自动解析流、更新 messages、status
          → UI 重渲染
```

---

## 四、常用 API & 命令速查

### 服务端：非流式文本生成

```typescript
import { generateText } from 'ai';

const { text, usage } = await generateText({
  model: openai('gpt-5.1'),
  prompt: '用中文解释什么是 RAG',
  maxTokens: 1024,
});
```

### 服务端：流式文本生成 + Tool Calling

```typescript
import { streamText, tool } from 'ai';
import { z } from 'zod';

const result = streamText({
  model: openai('gpt-5.1'),
  messages: [{ role: 'user', content: '北京现在几度？' }],
  tools: {
    getWeather: tool({
      description: '获取城市天气',
      inputSchema: z.object({ city: z.string() }),
      execute: async ({ city }) => fetchWeather(city),
    }),
  },
  maxSteps: 5,  // 自动处理多轮 tool call
});
```

### 客户端：Chat UI（`useChat`）

```typescript
'use client';
import { useChat } from '@ai-sdk/react';

function ChatPage() {
  const { messages, status, sendMessage, input, setInput, stop } = useChat({
    transport: new DefaultChatTransport({ api: '/api/chat' }),
  });

  return (
    <div>
      {messages.map(m => (
        <div key={m.id}>
          <b>{m.role === 'user' ? '👤' : '🤖'}:</b>
          {m.parts.filter(p => p.type === 'text').map(p => p.text)}
        </div>
      ))}
      {status === 'streaming' && <button onClick={stop}>停止</button>}
      <form onSubmit={e => { e.preventDefault(); sendMessage({ text: input }); }}>
        <input value={input} onChange={e => setInput(e.target.value)} />
      </form>
    </div>
  );
}
```

### 结构化输出（`generateObject`）

```typescript
import { generateObject } from 'ai';
import { z } from 'zod';

const { object } = await generateObject({
  model: openai('gpt-5.1'),
  schema: z.object({
    title: z.string(),
    tags: z.array(z.string()),
    summary: z.string(),
  }),
  prompt: '给这篇文档生成结构化摘要：...',
});
```

---

## 五、项目集成点

### 当前项目状态

本项目 **已安装 AI SDK 包但未在生产代码中使用**：

- `packages/web/package.json:29` — `@ai-sdk/react ^3.0.210`
- `packages/web/package.json` — `ai ^6.0.208`
- 实际的 Chat 功能使用 Dify API（通过 `packages/web/lib/chat/dify.ts` 直接调用 Dify REST API）

### 如果要在项目中使用 AI SDK

需要增加：

1. **安装 provider 包**：根据需求安装 `@ai-sdk/openai` 或 `@ai-sdk/anthropic` 等
2. **创建 Route Handler**：在 `app/api/chat/route.ts` 中实现流式代理
3. **替换/扩展 Dify Chat**：当前 `packages/web/lib/chat/use-chat-state.ts` 管理了 chat 状态，可接入 AI SDK 的 `useChat` 统一状态管理

### 架构建议

```
浏览器页面 → useChat → POST /api/chat → Route Handler → AI SDK → LLM Provider
                          ↑
                    可在此层增加：RAG 检索、prompt 组装、多模型路由
```

---

## 六、项目代码示例

### 示例1：后端 LLM 调用（纯 Node.js）

AI SDK Core 可在 Next.js Route Handler 或独立的 Node.js 服务中使用。以下是一个带 tool calling 的流式生成：

```typescript
// app/api/chat/route.ts（示意代码）
import { streamText, tool, convertToModelMessages, toUIMessageStream, createUIMessageStreamResponse } from 'ai';
import { openai } from '@ai-sdk/openai';
import { z } from 'zod';

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    model: openai('gpt-5.1'),
    messages: await convertToModelMessages(messages),
    tools: {
      searchKnowledge: tool({
        description: '从 RAG 知识库搜索相关信息',
        inputSchema: z.object({
          query: z.string().describe('搜索查询'),
          topK: z.number().default(5),
        }),
        execute: async ({ query, topK }) => {
          // 调用项目的知识库搜索服务
          return { results: [] };
        },
      }),
    },
    maxSteps: 3,
  });

  return createUIMessageStreamResponse({
    stream: toUIMessageStream({
      stream: result.stream,
      sendReasoning: true,    // 发送推理过程（DeepSeek R1 / Claude 可用）
      sendSources: true,      // 发送来源引用
    }),
  });
}
```

**关键点**：
- `convertToModelMessages` 将 UI 元数据剥离后再传给 LLM
- `toUIMessageStream(stream)` 包一层将模型输出转回 UI 可消费的格式
- `maxSteps` 控制 tool calling 的最大轮次，避免无限循环

### 示例2：useChat 自定义传输

```typescript
// app/chat/page.tsx（示意代码）
'use client';

import { useChat } from '@ai-sdk/react';

export default function ChatPage() {
  const {
    messages,
    input,
    setInput,
    status,
    sendMessage,
    stop,
    error,
    regenerate,
  } = useChat({
    transport: new DefaultChatTransport({
      api: '/api/chat',
      headers: { 'X-Project-ID': 'rag-project' },
      body: {
        temperature: 0.7,
        max_tokens: 2048,
      },
    }),
  });

  if (error) {
    return <div className="text-red-500">出错了: {error.message}</div>;
  }

  return (
    <div className="flex flex-col h-[600px] max-w-2xl mx-auto p-4">
      <div className="flex-1 overflow-y-auto space-y-4">
        {messages.map(message => (
          <div key={message.id} className="whitespace-pre-wrap">
            <div className="font-bold">
              {message.role === 'user' ? '👤 你' : '🤖 AI'}
            </div>
            {message.parts
              .filter(part => part.type === 'text')
              .map((part, i) => (
                <div key={i} className="mt-1">{part.text}</div>
              ))}
          </div>
        ))}
      </div>

      <div className="border-t pt-4 mt-4">
        {status === 'streaming' && (
          <button onClick={stop} className="mb-2 text-red-500">
            ⏹ 停止生成
          </button>
        )}
        <form
          onSubmit={e => {
            e.preventDefault();
            if (status === 'ready' || status === 'error') {
              sendMessage({ text: input });
              setInput('');
            }
          }}
        >
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="输入消息..."
            className="w-full p-2 border rounded"
          />
        </form>
        {status === 'ready' && messages.length > 0 && (
          <button onClick={regenerate} className="mt-2 text-sm text-blue-500">
            🔄 重新生成
          </button>
        )}
      </div>
    </div>
  );
}
```

**关键点**：
- `status` 有四个值：`submitted` → `streaming` → `ready` / `error`
- 只有在 `ready` 或 `error` 状态下才能发送新消息或重新生成
- `stop()` 在 `streaming` 状态下中断响应

---

## 七、项目没用到的能力

### 1. Agent（自主执行）

AI SDK 支持 `Agent` 抽象，用于构建自主 agent：

```typescript
import { Agent } from 'ai';
import { openai } from '@ai-sdk/openai';

const agent = new Agent({
  model: openai('gpt-5.1'),
  tools: {
    search: searchTool,
    calculator: calculateTool,
  },
  system: '你是一个 AI 助手，可以使用工具回答用户问题。',
});

const { text } = await agent.run({ prompt: '搜索并计算...' });
```

### 2. Middleware（中间件）

支持在 LLM 调用链中插入自定义逻辑（RAG 注入、Guardrails、日志等）：

```typescript
import { middleware } from 'ai';

const ragMiddleware = middleware({
  onGenerate: async ({ prompt }) => {
    const context = await retrieveRelevantDocs(prompt);
    return { prompt: `${context}\n\n${prompt}` };
  },
});
```

### 3. Telemetry（OpenTelemetry 集成）

内置 OpenTelemetry 支持，可追踪每次 LLM 调用的耗时、token 消耗：

```typescript
import { experimental_withTracing } from 'ai';

const tracedGenerate = experimental_withTracing(generateText, {
  name: 'llm-call',
  attributes: { project: 'rag' },
});
```

### 4. File Uploads（多模态文件上传）

`useChat` 内置文件上传支持：

```typescript
sendMessage({
  text: '解释这张图',
  files: fileList,  // 从 <input type="file"> 获取
});
```

### 5. Image Generation（图像生成）

通过 Fal AI / Luma AI 等 provider 生成图像：

```typescript
import { generateImage } from 'ai';
import { fal } from '@ai-sdk/fal';

const { images } = await generateImage({
  model: fal('fast-sdxl'),
  prompt: '...',
});
```

### 6. 推理过程展示

对 DeepSeek R1 / Claude Sonnet 等支持推理的模型，可展示推理步骤：

```typescript
// 服务端：toUIMessageStream 开启 sendReasoning
toUIMessageStream({ stream: result.stream, sendReasoning: true })

// 客户端：messages.parts 包含 type: 'reasoning' 的部分
message.parts
  .filter(p => p.type === 'reasoning')
  .map(p => <div className="text-gray-400 italic">{p.text}</div>)
```

---

## 八、评测 & 调优技巧

### 性能监控

- **OpenTelemetry**：AI SDK 内置 tracing，接入 Jaeger / Datadog 后可追踪每次 LLM 调用的延迟和 token 消耗
- **`usage` 对象**：`generateText` 和 `streamText` 返回 `usage`，包含 `promptTokens`、`completionTokens`、`totalTokens`

### Prompt 优化

- 利用 SDK 的 `system` 参数注入系统提示词，而非拼接在消息数组里
- 结构化输出优先用 `generateObject` + Zod，不要手动解析 JSON（容易被格式破坏）

### Token 控制

- `maxTokens` 限制输出长度
- `maxSteps` 控制 tool calling 轮次（建议 3-5 轮，避免无限循环）
- `temperature` 默认 0.7，知识库问答场景建议 0.1-0.3（更确定）

### 成本控制

- 使用 Vercel AI Gateway 作为统一入口，可做缓存和限流
- `generateObject` 比直接 `generateText` + JSON 解析更快更省钱（SDK 内部用 tool calling 强制结构化输出，减少重试）

---

## 九、最佳实践 & 常见坑

### 1. 版本兼容

- **`ai` v6 + `@ai-sdk/react` v3** 是当前最新大版本，API 与 v5 有较大变化
- v6 使用 `UIMessage` + `convertToModelMessages` 模式，而不是旧版的 `Message` 直接传
- 项目当前锁定 `ai ^6.0.208`、`@ai-sdk/react ^3.0.210` — 不要降级到 v5

### 2. 不要在 RSC 中使用 useChat

`useChat` 是 Client Component hook，必须在 `'use client'` 文件中使用。不要在 Server Component 或 RSC 中 import。

### 3. 不要手动拼接流

新手常见错误是手动解析 SSE 流。直接用 `createUIMessageStreamResponse` + `toUIMessageStream` 即可，SDK 会自动处理流协议。

### 4. 消息格式陷阱

```typescript
// ❌ 错误：直接传旧格式
messages: [{ role: 'user', content: 'hello' }]

// ✅ 正确：使用 UIMessage 格式
messages: await convertToModelMessages(uiMessages)
```

`convertToModelMessages` 会剥离 id、createdAt、parts 等 UI 元数据。

### 5. Tool calling 超时

`execute` 函数默认没有超时。如果调用外部 API（知识库搜索、数据库查询），建议自行加 timeout：

```typescript
execute: async ({ query }) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  const result = await search(query, { signal: controller.signal });
  clearTimeout(timeout);
  return result;
}
```

### 6. 错误处理

```typescript
useChat({
  transport: new DefaultChatTransport({ api: '/api/chat' }),
  onError: (error) => {
    console.error('Chat 请求失败:', error);
    // 可以在这里上报错误到 Sentry 等
  },
  onFinish: ({ message, messages }) => {
    // 可以在完成时持久化对话
    console.log('对话完成, token 使用:', message.metadata);
  },
});
```

---

## 📚 参考

- [AI SDK 官方文档](https://ai-sdk.dev/docs/introduction)
- [AI SDK GitHub (examples)](https://github.com/vercel/ai/tree/main/examples)
- [Getting Started: Next.js App Router](https://ai-sdk.dev/docs/getting-started/nextjs-app-router)
- [useChat API 文档](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot)
- [AI SDK Core 概述](https://ai-sdk.dev/docs/ai-sdk-core/overview)
- [AI SDK 的 llms.txt（给 Cursor/Copilot 用）](https://ai-sdk.dev/llms.txt)

---

**状态：** ✅ 完整文档（待验证）
