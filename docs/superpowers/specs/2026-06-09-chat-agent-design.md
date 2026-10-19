# 智能体聊天界面 设计

**日期**: 2026-06-09
**状态**: 设计已批准, 待实施
**作者**: 设计对话沉淀

## Context

项目已有 Dify 知识库 + Neo4j 图谱的「录入管理页」([2026-06-08-knowledge-management-page-design.md](2026-06-08-knowledge-management-page-design.md)), 解决了「业务人员怎么把 FAQ/产品手册喂给 Dify」「工程师怎么写三元组」两个录入痛点。

但**「最终用户怎么跟这套知识资产对话」**这个最外层场景目前完全缺失:
- 外网用户/客户碰到产品选型问题, 没有自助入口, 只能找销售/工程师
- 业务方做 demo 给客户看时, 还在用 Dify 自带控制台 (跟现有 web/ 风格割裂)
- 当前 web/ 的所有页面是**给内网运维/工程师用的管理后台**, 不适合直接对外

本设计在现有 web/ next 项目内新增 `/chat` 路由, 复用同一套 tailwind/shadcn/工具链, 解决「外网用户跟智能体对话」最后一环, 并通过 nginx 路径分流做到内外网隔离 (同一个 next 实例)。

**关键需求**:
- v1 后端用 Dify Chatflow (`/v1/chat-messages` 流式)
- 设计**适配器抽象** (`ChatProvider` 接口), 未来切换 LlamaIndex 不破坏前端

## 目标

1. **外网用户能跟智能体对话** — 输入问题 → 流式打字效果 → 看到 AI 答案 + 引用块 + 思考过程
2. **多会话管理** — 侧边栏历史列表, localStorage 持久化, 刷新不丢
3. **适配器隔离** — `ChatProvider` 接口, 当前实现是 Dify, 未来塞 LlamaIndex 只增不改
4. **流式 SSE** — 打字机效果, 用户体验对标 ChatGPT/Claude.ai
5. **复用现有栈** — shadcn/ui (Default + Slate) + Tailwind v4 + motion + bun + vitest + oxlint
6. **可停可控** — 停止按钮 abort 流, 中断后保留已收 delta

## 非目标 (YAGNI)

- **用户账号/登录** (v1 无, 纯 token 鉴权; 防滥用靠 nginx rate limit)
- **后端持久化会话** (v1 全部 localStorage, 刷新=换浏览器=丢, 这是用户能接受的取舍)
- **多模态 (图片/文件上传)** (v1 只文本输入)
- **语音输入/输出** (v1 文本)
- **分享/导出对话** (v1 私聊)
- **Markdown 富文本编辑器** (输入框 textarea 即可, 输出端 react-markdown 渲染)
- **多语言 i18n** (v1 中文)
- **Dify 工作流编排 UI** (v1 调用, 不编排)
- **Token 用量统计/计费** (v1 不显示)
- **LlamaIndex 实际实现** (本期只定义接口 + 工厂 + Dify 实现, 留 placeholder)

## 架构总览

### 部署: 单一 next 实例 + nginx 路径分流

```
                  ┌──── 内网 (10.x.x.x) ────┐
nginx ──── /  ────►  next  ─── /decode
                  │          ─── /output
                  │          ─── /knowledge
                  │          ─── /api/knowledge/*
                  │
                  └──── 公网 (暴露 /chat) ─┐
                  │          ─── /chat
                  │          ─── /api/chat/*
```

**middleware 兜底** (`app/middleware.ts`): 部署期通过 `CHAT_PUBLIC_MODE=true` 切换。公网模式下, 非 `/chat*` 路径一律返 404, 防攻击者猜到后台存在。

### 运行时: 两层架构

```
┌─────────────────────── Browser (chat page) ───────────────────┐
│  ChatShell (左右栏 layout)                                    │
│  ├─ ConversationList   (侧边栏, localStorage 持久化)          │
│  └─ MessageStream      (打字机式渲染, 引用/思考折叠)          │
└────────────────────────┬──────────────────────────────────────┘
                         │ fetch + ReadableStream (SSE)
┌────────────────────────▼──────────────────────────────────────┐
│ Next Route Handler /api/chat/messages                         │
│  ├─ 鉴权: x-chat-token 头校验 (env CHAT_PUBLIC_TOKEN)         │
│  └─ getChatProvider() ── 工厂                                 │
│      └─ DifyChatProvider (v1)                                 │
│         └─ fetch Dify /v1/chat-messages (SSE)                  │
│         └─ 归一化 SSE 字节 → ChatEvent 流                      │
└───────────────────────────────────────────────────────────────┘
```

**核心约束**:
- `DIFY_API_KEY` 永远不出现在前端 bundle
- 前端代码**禁止** import `@/lib/chat/dify`, 只 import `@/lib/chat/types` + 工厂
- 未来加 `LlamaIndexChatProvider` 时: 实现 `ChatProvider` 接口 + 工厂加 case, 前端零改动

## 视觉与交互

### 视觉风格: 复用现有 editorial 体系
- 沿用 web/ 现有配色 (paper 底 + ink 字 + clay/moss 强调色) + Instrument Serif 斜体大标题 + JetBrains Mono 数字
- shadcn/ui (Default + Slate) 全程使用, 通过 `bunx shadcn@latest add` 增量补
- 跟上现有 4 个页面的设计语言, 不开第二套视觉系统

### 布局: 左右栏 (B)

```
┌──────────────────┬────────────────────────────────────────┐
│ RAG · atlas      │ [新对话]                          [⋮]  │
│                  │ ──────────────────────────────────     │
│ + 新对话         │  10:32 · 1LE 系列电机怎么选?           │
│                  │                                        │
│ 电机选型      ●  │  你: 1LE 系列电机怎么选型?            │
│  2 分钟前         │                                        │
│  12 条消息        │  AI: 根据功率需求选 1LE...             │
│                  │     [考虑上下文，检索了 3 条]            │
│ 产品报价         │   - 产品手册 1LE1023 §3.2 (0.87)        │
│  昨天             │   - 选型指南 §1.4 (0.81)               │
│  3 条消息         │                                        │
│                  │     ──────────────────────────         │
│ 故障排查         │     [输入框...]               [⏎]    │
│  3 天前           │                                        │
│                  │                                        │
└──────────────────┴────────────────────────────────────────┘
```

- **左栏 (16rem)**: 标题 + 新对话按钮 + 历史会话列表 (按最近活动时间倒序)
- **右栏 (flex-1)**: 当前会话消息流 + 底部 Composer (输入框 + 发送/停止)
- **响应式**: < 768px 折叠侧边栏为汉堡按钮

### 组件清单 (shadcn/ui)

| 用途 | 组件 | 状态 |
|---|---|---|
| 侧边栏 | `ScrollArea` + `Button` (ghost) | **新增** shadcn add |
| 消息气泡 | 自写 `MessageBubble`, 包 `Card` | 现有 |
| 输入框 | `Textarea` + `Button` | 现有 |
| 引用块 | `Collapsible` | **新增** shadcn add |
| 思考过程 | `Collapsible` + `Badge` | **新增** shadcn add |
| 打字光标 | `motion.span` 自写 | 现有 motion |
| 错误 toast | `sonner` | 现有 |
| 会话删除确认 | `AlertDialog` | **新增** shadcn add |

## 核心接口契约 (`lib/chat/types.ts`)

```typescript
// ---- 输入 ----
// 字段名跟 dify ChatRequest 1:1 对齐 (https://docs.dify.ai/api-reference/对话流/发送对话消息)
export interface SendMessageRequest {
  query: string;                      // 用户问题
  inputs: Record<string, unknown>;     // 【必填】Chatflow 自定义变量; v1 传 {} 即可
  user: string;                       // 【必填】Dify 用作"应用内唯一标识, 限定数据访问范围"
                                       //          v1 用前端生成的 UUID (粘到 localStorage)
  conversationId?: string;            // 续聊传上一条响应里的; 首次省略
  files?: ChatFile[];                 // 【v2】多模态预留; v1 不传
  autoGenerateName?: boolean;         // 【可选】Dify 是否自动生成会话标题; v1 走 true
  workflowId?: string;                // 【可选】指定已发布工作流版本; 省略用最新
}

export interface ChatFile {
  type: "image" | "document" | "audio" | "video" | "custom";
  transferMethod: "remote_url" | "local_file";
  url?: string;                       // remote_url 时必填
  uploadFileId?: string;              // local_file 时必填 (先调"上传文件"API)
}

// ---- 输出: 流式事件 (归一化, 跨 provider 统一) ----
// Dify 原生事件有 ~16 种, 适配器归一化成 6 种, 详见 https://docs.dify.ai/api-reference/对话流/发送对话消息
export type ChatEvent =
  | { type: "message"; delta: string }                  // Dify: message (字段 answer) + message_replace
  | { type: "message_end"; conversationId: string;       // Dify: message_end (含 metadata.retriever_resources)
      citations?: Citation[] }
  | { type: "thinking"; node: string;                    // Dify: workflow_started / node_started /
      status: "started" | "finished";                    //         workflow_finished (succeeded/failed/...)
      detail?: string; }                                 //         node_finished 还含 elapsed_time, status
  | { type: "workflow_done"; status:                     // Dify: workflow_finished 单独抽出来
      "succeeded" | "failed" | "partial-succeeded" | "stopped" }
  | { type: "error"; code: string; message: string }     // Dify: error (HTTP 仍 200)
  | { type: "done" };

export interface Citation {
  documentName: string;
  datasetName?: string;                // Dify: dataset.name, 告诉用户"知识库来源"
  position?: number;
  score?: number;
  content: string;                     // Dify: segment.content, 截断到 ~300 字
  summary?: string | null;             // Dify: summary (nullable, 有就优先用)
}

// ---- Provider 接口 ----
export interface ChatProvider {
  readonly name: string;              // "dify" | "llamaindex" | ...
  sendMessage(
    req: SendMessageRequest,
    signal: AbortSignal,              // 停止按钮走这里
  ): AsyncIterable<ChatEvent>;
}
```

**关键设计决策**:

1. **流用 `AsyncIterable<ChatEvent>` 而非 `ReadableStream`** — provider 不用关心 HTTP, route handler 再统一包成 SSE。LlamaIndex 未来要换 Python/Node SDK 时直接适配。

2. **节点进度独立于 message** — 用户取消时干净退出, 不会丢半个字。

3. **`conversationId` 由 provider 内部管理** — Dify 返 `conversation_id`, LlamaIndex 返自定义 id, 统一在 `message_end` 事件里回吐给前端。

4. **引用块挂在 `message_end` 上** — 同一回复的多个增量 message + 1 个 message_end 是 Dify 标准模式, 前端只在 message_end 渲染一次引用。

5. **不模拟 streaming 进度** (CLAUDE.md 反对 shim 精神) — provider 没有 thinking 事件就不发, 绝不伪造。

## 文件结构

```
web/
├── app/
│   ├── chat/
│   │   ├── page.tsx                  # 聊天主页 (client component)
│   │   └── page.test.tsx             # vitest 单测
│   ├── api/chat/
│   │   ├── messages/route.ts         # POST: 发送消息 (SSE)
│   │   └── stop/route.ts             # POST: 中断标记 (实际 abort 走 AbortController)
│   ├── layout.tsx                    # nav 加 'Chat' 链接
│   └── middleware.ts                 # (新增) 内外网路径分流
│
├── components/chat/
│   ├── ChatShell.tsx                 # 左右栏 layout, 状态机 host
│   ├── ConversationList.tsx          # 侧边栏, localStorage 持久化
│   ├── MessageList.tsx               # 消息列表
│   ├── MessageBubble.tsx             # 单条消息 (user / assistant)
│   ├── CitationPanel.tsx             # 引用块折叠面板
│   ├── ThinkingTrace.tsx             # 思考过程 (节点进度)
│   └── Composer.tsx                  # 输入框 + 发送/停止
│
├── lib/chat/
│   ├── types.ts                      # ChatProvider 接口 + ChatEvent 类型
│   ├── factory.ts                    # getChatProvider() (env 决定)
│   ├── factory.test.ts
│   ├── dify.ts                       # DifyChatProvider 实现
│   ├── dify.test.ts                  # SSE 解析 + 归一化 (用 msw mock fetch)
│   ├── storage.ts                    # localStorage 会话元数据 CRUD
│   └── storage.test.ts
│
├── lib/api.ts                        # (扩展) 加 chatApi 命名空间
├── components.json                   # shadcn 元数据
└── .env.example                      # (追加) DIFY_*, CHAT_*
```

### 职责边界 (CLAUDE.md 反对 shim → 每个模块单一职责)

| 模块 | 做什么 | 不做什么 |
|---|---|---|
| `lib/chat/types.ts` | 定义接口 + 类型 | 不含任何实现 |
| `lib/chat/dify.ts` | Dify SSE → ChatEvent 归一化 | 不知道 HTTP/Router 存在 |
| `lib/chat/factory.ts` | env → 选 provider | 不知道具体业务字段 |
| `app/api/chat/*` | 鉴权、参数校验、SSE 转发 | 不知道 dify 协议细节 |
| `components/chat/*` | 渲染 + 交互 | 不直接 fetch dify, 只调 `/api/chat/messages` |
| `lib/chat/storage.ts` | localStorage CRUD | 不含 React 状态 |

## API 契约

### Next.js Route Handlers (BFF for Dify/LlamaIndex)

| 端点 | 方法 | 用途 | 鉴权 |
|---|---|---|---|
| `/api/chat/messages` | POST | 发送消息, 返 SSE 流 | x-chat-token 头 |
| `/api/chat/stop` | POST | 标记中断 (可选, 实际 abort 走 `AbortController` 由 `req.signal` 触发) | 同上 |

**`/api/chat/messages` 行为**:
1. 校验 `x-chat-token` 头, 失败 → 401
2. zod 校验 body (`{ query, conversationId?, userId, inputs? }`)
3. 拿 `provider = getChatProvider()`
4. 创建 `ReadableStream`, for-await `provider.sendMessage(body, req.signal)`, 每条 `ChatEvent` 包成 `data: {json}\n\n` SSE 块
5. 流结束/出错时发 `data: [DONE]\n\n`
6. Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`, `Connection: keep-alive`

### 中间件 (`app/middleware.ts`)

```typescript
// 公网白名单; 部署期 CHAT_PUBLIC_MODE=true 时启用
const PUBLIC_PATHS = ["/chat", "/api/chat"];
```

公网模式: 非 `PUBLIC_PATHS` 全部 404 (防攻击者扫描)
内网模式: middleware 放行所有路径 (跟现状一致)

## 状态机 (前端)

`ChatShell.tsx` 内的状态:

```typescript
type State = {
  conversations: Conversation[];                          // 列表, 按 updatedAt 倒序
  currentId: string;                                       // 当前选中 conv
  messagesByConv: Record<string, Message[]>;               // 消息按 conv 隔离
  streamingByConv: Record<string, AbortController | null>;  // 流的 abort 句柄按 conv 隔离
  draft: string;                                           // 当前输入框草稿
};
```

**关键设计**: streaming **按 conv 隔离** — 用户在 convA 问问题时点 convB 看历史, convA 的流继续跑不打断。每个流有独立 `AbortController`, 停止按钮只 abort 当前 conv 的流。

**动作**:
| 动作 | 行为 |
|---|---|
| `newConversation()` | 创建空 conv, 切到列表头, 写 localStorage |
| `selectConversation(id)` | 切换 currentId, 不动其他 conv |
| `sendMessage(text)` | 推到 messagesByConv[convId], 创建 AbortController, fetch 拉流, 流归一化到 state |
| `stopStreaming()` | abort currentId 对应的 controller |
| `deleteConversation(id)` | 删 messagesByConv[id] + streamingByConv[id]?.abort() + 删 localStorage |

**localStorage key**: `rag.chat.conversations.v1` (JSON, 含 id/title/createdAt/updatedAt)

## 错误处理矩阵

| 场景 | Dify 错误码 | 前端 | 后端 |
|---|---|---|---|
| `CHAT_PUBLIC_TOKEN` 错 | n/a (我们自己的鉴权) | 401 提示 "服务暂时不可用" | 401 + 简单 message |
| Dify 401 (key 错) | n/a | toast "服务暂时不可用" | 502 + error event |
| Dify app 配置错 | `app_unavailable` / `provider_not_initialize` | toast "服务暂时不可用, 请联系管理员" | 502 |
| Dify app 模式错 (用了非 chatflow) | `not_chat_app` | toast "服务暂时不可用" | 502 |
| Dify 配额/限流 | `provider_quota_exceeded` / `too_many_requests` / `rate_limit_error` | toast "请求过多, 稍后重试" + 自动重试 1 次 (退避 1s) | 429 透传 |
| Dify 模型不可用 | `model_currently_not_support` / `completion_request_error` | toast "模型暂时不可用" + 不重试 | 502 |
| 会话已结束/不存在 | `conversation_completed` / `not_found` (会话) | 清空该 conv 状态 + 提示 "会话已结束, 请新建" | 404 |
| 工作流 ID 错 | `bad_request` (workflow_id 格式) | toast "服务暂时不可用" | 400 |
| 用户网络断 | n/a | 重连 1 次 (用 conversationId 重发) | n/a |
| 用户点停止 | n/a | abort controller | 释放 fetch |
| SSE 断流在 message 中间 | n/a | 保留已收 delta, 标记 "已中断" 徽章 | n/a |
| `ping` 保活事件 (10s 一次) | n/a | 忽略, 不上抛 | 透传不解析 |
| `message_replace` (内容审核) | n/a | 替换当前 delta 渲染 | 归一化到 `message` event |

## 部署期 env 清单

`.env.example` 追加:

```bash
# --- Chat (新增) ---
DIFY_API_KEY=app-xxx
DIFY_API_URL=https://api.dify.ai/v1
DIFY_CHATFLOW_APP_ID=                  # dify 后台 URL 末段 (16 位 hash)
CHAT_PROVIDER=dify                     # 工厂开关: dify | llamaindex (留 placeholder)
CHAT_PUBLIC_TOKEN=                     # 前端 x-chat-token 头共享 (内部随机串)
NEXT_PUBLIC_CHAT_TOKEN=                # 暴露给前端 (公网部署时)
CHAT_PUBLIC_MODE=false                 # middleware 切换内外网模式
```

**安全约束**:
- `DIFY_API_KEY` 只能进 server env, **绝不**加 `NEXT_PUBLIC_` 前缀
- `CHAT_PUBLIC_TOKEN` 不是 "私钥", 是公网 anti-abuse 手段; nginx rate limit 是主防线

## 测试策略

CLAUDE.md 强制 TDD + 测真行为 (不能只测 "不崩")。本节定义各层测什么:

| 层级 | 文件 | 测什么 |
|---|---|---|
| `lib/chat/dify.test.ts` | DifyChatProvider | 喂**真实 Dify SSE 字节**(手造, 同 [feedback-python-zipfile-setpassword-doesnt-encrypt-on-write](feedback-python-zipfile-setpassword-doesnt-encrypt-on-write.md) 思路), 验证归一化出 ChatEvent 流, 至少覆盖 8 种 Dify 事件: `message` / `message_end` (含 `retriever_resources` 多条) / `workflow_started` / `node_started` / `node_finished` (succeeded+failed) / `workflow_finished` (succeeded+failed) / `error` / `ping` (必须被忽略) |
| `lib/chat/factory.test.ts` | factory | env=`CHAT_PROVIDER=dify` 返 `DifyChatProvider` 实例; env=空 → 抛 "unknown provider" |
| `lib/chat/storage.test.ts` | localStorage CRUD | CRUD 4 个动作 + JSON 损坏不崩 (返空数组) + 版本号不匹配时迁移/丢弃策略 |
| `app/api/chat/messages/route.test.ts` | route handler | mock provider 返 mock 流, 验证 SSE 头(`Content-Type: text/event-stream`) + 透传每条 event + 鉴权失败返 401 + 缺 query 返 400 |
| `components/chat/MessageBubble.test.tsx` | 单条气泡 | user / assistant 两种类型渲染断言 + 引用块折叠交互 + thinking 折叠交互 |
| `components/chat/Composer.test.tsx` | 输入框 | 输入+回车触发 onSend, 空字符串不触发, 发送中显示停止按钮 |
| `components/chat/ChatShell.test.tsx` | 状态机 | 切换 conv 不打断其他 conv 流; 停止按钮 abort 当前流; 删 conv 清 state |
| `app/chat/page.test.tsx` | 主页 | mount 渲染左右栏 |
| `e2e/chat.spec.ts` | Playwright | 起 next dev, mock `/api/chat/messages` SSE, 走通 "输入 → 打字 → 引用展示 → 新对话 → 切回历史" |

## 主动补的功能清单

1. **侧边栏按更新时间倒序** + 当前 conv 高亮
2. **新对话默认标题** = 第一条用户消息的前 20 字 (可编辑, 暂不实现编辑)
3. **空状态引导** — 无 conv 时左栏显示 "开始一段新对话" 占位
4. **键盘快捷键** — Enter 发送, Shift+Enter 换行, `Cmd/Ctrl+K` 新对话, Esc 停止
5. **流式打字光标** — AI 回复最后字符后跟闪烁 ▍
6. **自动滚动到底部** — 新消息时滚; 用户向上滚看历史时停止自动滚 (sticky-bottom 模式)
7. **重发按钮** — AI 回复气泡 hover 时显示 🔄, 重发同一 query
8. **复制按钮** — AI 回复气泡 hover 时显示 📋, 复制 markdown 原文
9. **消息时间戳** — hover 消息时显示具体时间
10. **会话标题右键菜单** — 重命名/删除 (v1 只做删除 + AlertDialog 确认)
11. **Dify 健康检查指示** — 顶部小圆点, 启动时打一次 `/api/chat/health` (本期暂不实现, 留给 v2)
12. **断网检测** — `navigator.onLine` 监听, 离线时禁用发送按钮
13. **错误边界** — 沿用现有 `components/knowledge/ErrorBoundary.tsx` 复用
14. **i18n 准备** — 文案集中在 `lib/chat/copy.ts`, 后续 i18n 改这一处

## 风险与边界

- **Dify rate limit**: 未明示, 依赖 nginx 层; client 重试 1 次退避 1s
- **大消息**: 单条消息截断到 8000 字 (前端) / 16000 字 (后端) 防滥用
- **SSE 中间代理**: nginx 默认 buffer 会破 SSE, 必须 `proxy_buffering off` + `proxy_cache off`
- **AbortController 跟 provider 内部 fetch 的关联**: route handler 必须把 `req.signal` 透传给 `provider.sendMessage`, provider 内部 fetch 用 `signal` 参数, 链路断则流断
- **Dify `response_mode: "streaming"` 必须显式传** — 不传默认 blocking, 流特性全没
- **`conversationId` 不要用浏览器 fingerprint** — 简单用 `crypto.randomUUID()` 即可, 不持久化到 cookie
- **v1 单 Dify 应用**: `DIFY_CHATFLOW_APP_ID` 单值, 未来多应用时改 env 数组
- **Bearer scheme**: Dify 鉴权必须是 `Authorization: Bearer {API_KEY}`, 不是 `x-api-key`. 写代码时直接固定 scheme, 不留 shim 兼容旧头
- **保活事件**: Dify 10s 一次发 `event: ping` (无 `data:`), 适配器**必须**识别并忽略, 不能上抛为 ChatEvent

## 实施顺序 (建议 PR 拆法)

1. **PR 1**: 工具链 + shadcn add (scroll-area, collapsible, alert-dialog) + `lib/chat/types.ts` + factory 占位
2. **PR 2**: `DifyChatProvider` + 完整单测 (手造 SSE 字节)
3. **PR 3**: `app/api/chat/messages` route handler + 鉴权 + 测试
4. **PR 4**: `lib/chat/storage.ts` + localStorage CRUD + 测试
5. **PR 5**: 基础 UI 组件 (`MessageBubble` / `Composer` / `CitationPanel` / `ThinkingTrace`)
6. **PR 6**: `ChatShell` 状态机 + `ConversationList` 接入
7. **PR 7**: `app/chat/page.tsx` 接入 nav + e2e 测试
8. **PR 8**: middleware + 部署文档 + 收尾打磨

每个 PR 独立可测, 都能跑现有测试套件不挂。`/chat` 路由在任何 PR 后都允许 disabled (env `CHAT_PUBLIC_MODE=false` 兜底)。

## 行业最佳实践引用

- **SSE over WebSocket**: 聊天单向, SSE 够用, 无需双向 WS
- **`AsyncIterable` 抽象流**: 跟 Deno 跟 Node 都兼容, 未来切 LlamaIndex 不用改上层
- **localStorage 版本号前缀**: `.v1` 后缀方便 schema 迁移 ([feedback-check-pyproject-deps-match-actual-imports](feedback-check-pyproject-deps-match-actual-imports.md) 同款 "future-proof" 思路)
- **AbortController 链路**: 浏览器 fetch → route handler req.signal → provider fetch signal, 一条链, 停止按钮真能停
- **shadcn/ui 复用**: 跟 4 个管理页同一份, 不分裂设计系统
- **CLAUDE.md 禁止 shim**: `DifyChatProvider` 不知道 HTTP, route handler 不知道 dify 协议, 工厂不知道业务字段, 严格分层

## 跟现有架构的关联

- 沿用 `web/CLAUDE.md` 的所有约定 (bun / oxlint / oxfmt / tsgo / vitest / Playwright / Tailwind v4 / shadcn)
- 沿用现有 `lib/api.ts` 的 api 客户端风格, 扩展 `chatApi` 命名空间
- 沿用现有 `lib/dify-datasets.ts` 的 Dify 客户端模式 (`DifyChatProvider` 是它的 "聊天版" 同胞, 不复用因为协议不同)
- 沿用 `app/knowledge/layout.tsx` 的 dataset 切换器样式, 复用视觉语言
- 沿用现有 `ErrorBoundary` 组件

## Open Questions (留 PR 实施时确认)

- ~~Dify 端点是否需要 `user` 字段做风控~~ — **已关闭**. 文档明确: `user` **必填**, 用作"应用内唯一标识, 限定数据访问范围". v1 用前端 UUID 已合规.
- **是否启用 Dify `auto_generate_name`** — 默认 `true` (Dify 自动起会话标题). 风险: 标题质量不可控, 业务方后期可能想自定义. 建议 v1 走默认, 真出现质量问题再改 `false` 走前端起名.
- **是否需要 rate limit 提示** — 当前 v1 不做, 依赖 nginx
- **是否需要把停止按钮做成键盘快捷键** (Esc) — 设计里已加, 实施时确认交互
- **是否需要 markdown 表格渲染** — react-markdown 默认支持, 实施时确认 UI 风格
