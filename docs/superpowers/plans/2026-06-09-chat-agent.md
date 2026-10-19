# 智能体聊天界面 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 RAG 项目 `web/` 内新增 `/chat` 路由, 外网用户可跟 Dify Chatflow 智能体对话 (流式 SSE + 打字机效果 + 引用块 + 思考过程 + 多会话管理), 通过 `ChatProvider` 接口隔离方便未来切 LlamaIndex, nginx 路径分流 + middleware 兜底做内外网隔离。

**Architecture:**
- 前端: 现有 Next.js 16 + React 19 + shadcn/ui (Default + Slate) + Tailwind v4 + motion, 加 `lib/chat/{types,factory,dify,storage}.ts` 和 `components/chat/*` UI 组件
- 后端 BFF: Next.js Route Handler `/api/chat/messages` 做鉴权 + SSE 转发, 永远不在前端 bundle 暴露 `DIFY_API_KEY`
- 适配器: `ChatProvider` 接口 + `getChatProvider()` 工厂, v1 实现 `DifyChatProvider`, 未来塞 `LlamaIndexChatProvider` 零前端改动
- 部署: 单一 next 实例, nginx 路径分流; `CHAT_PUBLIC_MODE=true` 时 middleware 把非 `/chat*` 一律 404

**Tech Stack:** Next.js 16 (App Router) + React 19 + TypeScript, shadcn/ui, motion, vitest+jsdom+@testing-library/react, Playwright, bun, oxlint/oxfmt/tsgo

**关联 Spec:** `docs/superpowers/specs/2026-06-09-chat-agent-design.md`

**测试约定:** 跟 `web/CLAUDE.md` 一致 — `*.test.ts(x)` 跟实现平铺, 用 vitest 跑单测, Playwright 跑 E2E。所有外部依赖 (Dify, fetch) 必须 mock (test 里用 `vi.fn()` 替 `globalThis.fetch`, 不用 msw 避免拖复杂度)。CLAUDE.md 禁止 shim — provider 不知道 HTTP, route handler 不知道 dify 协议, 工厂不知道业务字段, 严格分层。

---

## 文件结构总览

### 新增 (web/)

```
web/
├── app/
│   ├── chat/
│   │   ├── page.tsx                       # 聊天主页 (client component)
│   │   └── page.test.tsx
│   ├── api/chat/
│   │   ├── messages/route.ts              # POST: 发送消息 (SSE)
│   │   └── messages/route.test.ts
│   └── middleware.ts                      # CHAT_PUBLIC_MODE 内外网分流
│
├── components/chat/
│   ├── ChatShell.tsx                      # 左右栏 layout, 状态机 host
│   ├── ChatShell.test.tsx
│   ├── ConversationList.tsx               # 侧边栏, localStorage 持久化
│   ├── ConversationList.test.tsx
│   ├── MessageList.tsx
│   ├── MessageBubble.tsx                  # 单条消息 (user / assistant)
│   ├── MessageBubble.test.tsx
│   ├── CitationPanel.tsx                  # 引用块折叠面板
│   ├── ThinkingTrace.tsx                  # 思考过程 (节点进度)
│   ├── Composer.tsx                       # 输入框 + 发送/停止
│   └── Composer.test.tsx
│
├── lib/chat/
│   ├── types.ts                           # ChatProvider 接口 + ChatEvent 类型
│   ├── types.test.ts                      # 编译期类型守卫断言
│   ├── factory.ts                         # getChatProvider() (env 决定)
│   ├── factory.test.ts
│   ├── dify.ts                            # DifyChatProvider 实现
│   ├── dify.test.ts                       # 手造 SSE 字节, 8 种 Dify 事件
│   ├── storage.ts                         # localStorage 会话元数据 CRUD
│   ├── storage.test.ts
│   └── copy.ts                            # 文案集中, 后续 i18n 一处改
│
├── components/ui/
│   ├── scroll-area.tsx                    # 新增 (shadcn add)
│   ├── collapsible.tsx                    # 新增 (shadcn add)
│   └── alert-dialog.tsx                   # 新增 (shadcn add)
│
├── lib/api.ts                             # (扩展) 加 chatApi 命名空间
└── e2e/chat.spec.ts                       # Playwright 端到端
```

### 修改

- `web/app/layout.tsx` — 顶 nav 加 `Chat` 链接
- `web/lib/api.ts` — 加 `chatApi.sendMessage()` 走 `/api/chat/messages`
- `web/.env.example` — 追加 `DIFY_*` + `CHAT_*` 条目

### 总体 PR 顺序

- **PR 1**: 工具链 (shadcn add scroll-area/collapsible/alert-dialog) + `lib/chat/types.ts` + factory + env 文档
- **PR 2**: `DifyChatProvider` + 完整单测 (手造 8 种 SSE 字节)
- **PR 3**: `/api/chat/messages` route handler + 鉴权 + zod + 单测
- **PR 4**: `lib/chat/storage.ts` (localStorage CRUD) + 单测
- **PR 5**: 基础 UI 组件 (MessageBubble / Composer / CitationPanel / ThinkingTrace / MessageList)
- **PR 6**: `ConversationList` + `ChatShell` 状态机 + 接入 storage
- **PR 7**: `app/chat/page.tsx` + nav 接入 + Playwright E2E
- **PR 8**: middleware (`CHAT_PUBLIC_MODE`) + 部署文档 + 全量打磨

每个 PR 独立可测, 跑 `cd web && bun run test` + `cd web && bun run typecheck` + `cd web && bun run lint` 全绿。`/chat` 路由在任何 PR 后都允许 disabled (默认 `CHAT_PUBLIC_MODE=false` 兜底, middleware 404)。

---

# PR 1 · 工具链 + 类型契约 + 工厂

**PR 目标**: 加 shadcn/ui 3 个组件, 定义 `ChatProvider` 接口 + `ChatEvent` 联合类型 + 工厂函数 + 完整 env 文档。还没接业务, 但全栈类型契约锁定, 后续 PR 直接照契约实现。

---

## Task 1.1: shadcn add scroll-area / collapsible / alert-dialog

**Files:**
- Create: `web/components/ui/scroll-area.tsx`
- Create: `web/components/ui/collapsible.tsx`
- Create: `web/components/ui/alert-dialog.tsx`

- [ ] **Step 1: 用 shadcn CLI 装**

```bash
cd web
bunx shadcn@latest add scroll-area collapsible alert-dialog
```

按提示选 "Default style + Slate base color" (跟项目 `components.json` 一致)。

- [ ] **Step 2: 验证生成**

Run: `ls web/components/ui/scroll-area.tsx web/components/ui/collapsible.tsx web/components/ui/alert-dialog.tsx`
Expected: 3 个文件都存在, 内容是标准 shadcn 模板 (Radix 包装)。

- [ ] **Step 3: 跑 typecheck 确认 Radix 依赖已加**

Run: `cd web && bun run typecheck`
Expected: 无错误 (shadcn CLI 已把对应 `@radix-ui/react-*` 加进 `package.json`)

- [ ] **Step 4: 提交**

```bash
git add web/components/ui/scroll-area.tsx web/components/ui/collapsible.tsx web/components/ui/alert-dialog.tsx web/package.json web/bun.lock
git commit -m "feat(chat): shadcn add scroll-area + collapsible + alert-dialog"
```

---

## Task 1.2: `lib/chat/types.ts` + 编译期类型守卫测试

**Files:**
- Create: `web/lib/chat/types.ts`
- Create: `web/lib/chat/types.test.ts`

- [ ] **Step 1: 写类型定义**

`web/lib/chat/types.ts`:

```ts
// 智能体聊天 类型契约 (2026-06-09)
// 字段名跟 Dify Chatflow API 1:1 对齐: https://docs.dify.ai/api-reference/对话流/发送对话消息
// 流用 AsyncIterable<ChatEvent> 而非 ReadableStream: 跟 Deno/Node SDK 兼容, 未来切 LlamaIndex 零改上层

/** 用户单次发送消息的请求体 */
export interface SendMessageRequest {
  /** 用户问题 */
  query: string;
  /** 【必填】Chatflow 自定义变量; v1 传 {} */
  inputs: Record<string, unknown>;
  /** 【必填】Dify 用作"应用内唯一标识, 限定数据访问范围"; v1 用前端 UUID */
  user: string;
  /** 续聊传上一条响应里的 conversationId; 首次省略 */
  conversationId?: string;
  /** 【v2】多模态预留; v1 不传 */
  files?: ChatFile[];
  /** 【可选】Dify 自动起会话标题; v1 走 true */
  autoGenerateName?: boolean;
  /** 【可选】指定已发布工作流版本; 省略用最新 */
  workflowId?: string;
}

export interface ChatFile {
  type: "image" | "document" | "audio" | "video" | "custom";
  transferMethod: "remote_url" | "local_file";
  /** remote_url 时必填 */
  url?: string;
  /** local_file 时必填 (先调"上传文件" API) */
  uploadFileId?: string;
}

/** 流式事件: 跨 provider 统一, 把 Dify ~16 种事件归一化到 6 种 */
export type ChatEvent =
  | { type: "message"; delta: string }
  | { type: "message_end"; conversationId: string; citations?: Citation[] }
  | { type: "thinking"; node: string; status: "started" | "finished"; detail?: string }
  | { type: "workflow_done"; status: "succeeded" | "failed" | "partial-succeeded" | "stopped" }
  | { type: "error"; code: string; message: string }
  | { type: "done" };

export interface Citation {
  documentName: string;
  datasetName?: string;
  position?: number;
  score?: number;
  /** Dify: segment.content, 截断到 ~300 字 */
  content: string;
  /** Dify: summary, nullable */
  summary?: string | null;
}

/** Provider 接口: 任何实现都对外暴露同名 sendMessage() */
export interface ChatProvider {
  readonly name: string;
  sendMessage(req: SendMessageRequest, signal: AbortSignal): AsyncIterable<ChatEvent>;
}

/** 前端本地状态用: 一条消息 */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  /** assistant 专属: 引用块 */
  citations?: Citation[];
  /** assistant 专属: 思考过程 (节点开始/结束序列) */
  thinking?: Array<{ node: string; status: "started" | "finished"; detail?: string }>;
  /** 标记: 消息被用户中断, 保留已收 delta */
  interrupted?: boolean;
}

/** 前端本地状态用: 一个会话 */
export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}
```

- [ ] **Step 2: 写编译期类型守卫测试 (vitest 跑不到, 但 tsc 强制覆盖)**

`web/lib/chat/types.test.ts`:

```ts
// 编译期类型守卫: 这些断言如果类型不对 tsc 会报错, 间接保证契约
import { describe, it, expect } from "vitest";
import type {
  ChatEvent, ChatProvider, Citation, SendMessageRequest,
} from "./types";

describe("ChatEvent 类型守卫", () => {
  it("6 种 ChatEvent 都能构造", () => {
    const events: ChatEvent[] = [
      { type: "message", delta: "x" },
      { type: "message_end", conversationId: "c1", citations: [] },
      { type: "thinking", node: "n1", status: "started" },
      { type: "workflow_done", status: "succeeded" },
      { type: "error", code: "c", message: "m" },
      { type: "done" },
    ];
    expect(events).toHaveLength(6);
    expect(events[0].type).toBe("message");
    if (events[0].type === "message") {
      expect(typeof events[0].delta).toBe("string");
    }
  });

  it("Citation summary 接受 null", () => {
    const c: Citation = {
      documentName: "d", content: "x", summary: null, score: 0.8,
    };
    expect(c.summary).toBeNull();
  });
});

describe("ChatProvider 接口形状", () => {
  it("name 必为 readonly string", () => {
    const p: ChatProvider = {
      name: "mock",
      async *sendMessage(_req: SendMessageRequest, _signal: AbortSignal): AsyncIterable<ChatEvent> {
        yield { type: "done" };
      },
    };
    expect(p.name).toBe("mock");
  });
});
```

- [ ] **Step 3: 跑 typecheck 确认契约对**

Run: `cd web && bun run typecheck`
Expected: 无错误 (意味着 SendMessageRequest 必填字段, ChatEvent 联合类型, ChatProvider 接口都自洽)

- [ ] **Step 4: 跑测试**

Run: `cd web && bun run test -- types.test`
Expected: 2 PASS

- [ ] **Step 5: 提交**

```bash
git add web/lib/chat/types.ts web/lib/chat/types.test.ts
git commit -m "feat(chat): 定义 ChatProvider + ChatEvent + 类型守卫测试"
```

---

## Task 1.3: `lib/chat/factory.ts` + 测试

**Files:**
- Create: `web/lib/chat/factory.ts`
- Create: `web/lib/chat/factory.test.ts`

- [ ] **Step 1: 写红测试**

`web/lib/chat/factory.test.ts`:

```ts
// factory 行为: env CHAT_PROVIDER 决定返哪个 provider
// v1 只支持 "dify"; 其他值/缺失值都抛错 (不静默回退, CLAUDE.md 反对 shim)
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { getChatProvider } from "./factory";

describe("getChatProvider", () => {
  const ORIGINAL = process.env.CHAT_PROVIDER;

  beforeEach(() => {
    delete process.env.CHAT_PROVIDER;
  });
  afterEach(() => {
    if (ORIGINAL === undefined) delete process.env.CHAT_PROVIDER;
    else process.env.CHAT_PROVIDER = ORIGINAL;
  });

  it("CHAT_PROVIDER=dify 返 name='dify' 的 provider", () => {
    process.env.CHAT_PROVIDER = "dify";
    const p = getChatProvider();
    expect(p.name).toBe("dify");
  });

  it("CHAT_PROVIDER 未设抛错 (不静默回退)", () => {
    expect(() => getChatProvider()).toThrow(/CHAT_PROVIDER/);
  });

  it("CHAT_PROVIDER=llamaindex 抛 '未实现' (v1 故意不兜底)", () => {
    process.env.CHAT_PROVIDER = "llamaindex";
    expect(() => getChatProvider()).toThrow(/llamaindex/);
  });

  it("CHAT_PROVIDER=garbage 抛 'unknown provider'", () => {
    process.env.CHAT_PROVIDER = "garbage";
    expect(() => getChatProvider()).toThrow(/unknown provider/);
  });
});
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd web && bun run test -- factory.test`
Expected: FAIL — `Cannot find module './factory'`

- [ ] **Step 3: 实现 factory**

`web/lib/chat/factory.ts`:

```ts
// 工厂: env CHAT_PROVIDER 决定返哪个 ChatProvider
// v1: dify (实装, 见 ./dify.ts)
// v2: llamaindex (留空, 调用即抛错; 等真实实现再加, 严禁 shim 占位)
import type { ChatProvider } from "./types";

export function getChatProvider(): ChatProvider {
  const name = process.env.CHAT_PROVIDER;
  if (!name) {
    throw new Error("CHAT_PROVIDER 未设置; 在 .env 里加 CHAT_PROVIDER=dify");
  }
  switch (name) {
    case "dify": {
      // 动态 import 避免在 factory 文件静态拉 dify 模块, 后续切 provider 不用改 factory
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const mod = require("./dify") as typeof import("./dify");
      return new mod.DifyChatProvider();
    }
    case "llamaindex":
      throw new Error("llamaindex provider 未实现 (v1 只支持 dify)");
    default:
      throw new Error(`unknown provider: ${name}`);
  }
}
```

- [ ] **Step 4: 跑测试确认 PASS (最后一个测试会因为 dify.ts 还没建而失败)**

Run: `cd web && bun run test -- factory.test`
Expected: 第 1 个 (dify) 会 FAIL (Cannot find module './dify'), 2-4 应该 PASS
**注意**: 这是预期的, 后面 PR 2 加 `dify.ts` 后所有测试都过

- [ ] **Step 5: 提交 (factory + factory.test, dify 那条 PR 2 再补)**

```bash
git add web/lib/chat/factory.ts web/lib/chat/factory.test.ts
git commit -m "feat(chat): factory 走 env 选 provider, v1 仅 dify"
```

---

## Task 1.4: `.env.example` 追加 chat 条目

**Files:**
- Modify: `web/.env.example` (或 `web/.env.local.example`, 取项目现有约定)

- [ ] **Step 1: 确认现有 env 文件名**

```bash
ls web/.env* 2>&1
```

Read 现有文件, 看命名约定。如果只有 `.env.example`, 就改它。

- [ ] **Step 2: 追加 chat 段**

在文件末尾追加 (中文注释, 跟现有风格一致):

```bash
# --- 智能体聊天 (2026-06-09 新增) ---
# Dify 凭据: 仅放 server env, 严禁加 NEXT_PUBLIC_ 前缀
DIFY_API_KEY=app-xxx                                  # dify 后台 API 访问 → 应用 → API 密钥
DIFY_API_URL=https://api.dify.ai/v1                   # dify 服务地址 (自部署改这个)
DIFY_CHATFLOW_APP_ID=                                 # dify 后台 URL 末段 16 位 hash

# 工厂开关: dify (实装) | llamaindex (留空)
CHAT_PROVIDER=dify

# 公网 anti-abuse 共享 token; 前端通过 NEXT_PUBLIC_CHAT_TOKEN 读, 走 x-chat-token 头
# 不是"私钥", nginx rate limit 是主防线; 仅防最笨的爬虫
CHAT_PUBLIC_TOKEN=
NEXT_PUBLIC_CHAT_TOKEN=

# middleware 切换内外网模式
# 内网 dev/staging: false (放行所有路径)
# 公网 prod: true (非 /chat* 全部 404)
CHAT_PUBLIC_MODE=false
```

- [ ] **Step 3: 提交**

```bash
git add web/.env.example
git commit -m "docs(chat): .env.example 追加 DIFY_*/CHAT_* 条目"
```

---

## Task 1.5: PR 1 验证

- [ ] **Step 1: 跑 typecheck + lint + test**

```bash
cd web && bun run typecheck && bun run lint && bun run test
```

Expected: typecheck 无错, lint 无错, test 全过 (factory 那 1 条预期 FAIL 也行, PR 2 修)

- [ ] **Step 2: 跑 dev server 确认 404 兜底还正常**

```bash
cd web && bun run dev
# 浏览器: http://localhost:3000/chat → 预期 404 (页面还没建)
# 浏览器: http://localhost:3000/ → 预期 200
```

Expected: `/chat` 404 (页面 PR 7 才建), `/` 200。

- [ ] **Step 3: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 4 个新 commit (T1.1 shadcn / T1.2 types / T1.3 factory / T1.4 env)

下一步: PR 2 — `DifyChatProvider` 实装 + 8 种 SSE 事件测试。

---

# PR 2 · DifyChatProvider + SSE 归一化

**PR 目标**: 实现 `DifyChatProvider`, 把 Dify Chatflow ~16 种 SSE 事件归一化到 6 种 `ChatEvent`。单测用手造 Dify SSE 字节 (跟 [feedback-python-zipfile-setpassword-doesnt-encrypt-on-write](feedback-python-zipfile-setpassword-doesnt-encrypt-on-write.md) 思路: 不信 mock 替身, 测真字节), 覆盖 `message` / `message_end` (含 retriever_resources) / `workflow_started` / `node_started` / `node_finished` / `workflow_finished` / `error` / `ping` 8 种。

---

## Task 2.1: `dify.test.ts` 红测试 (手造 8 种 SSE 字节)

**Files:**
- Create: `web/lib/chat/dify.test.ts`

- [ ] **Step 1: 写红测试**

`web/lib/chat/dify.test.ts`:

```ts
// DifyChatProvider 测试: 手造 Dify SSE 字节, 验证归一化
// 不信 mock SSE 库: 真字节 → 真解析 → 验 ChatEvent 流
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { DifyChatProvider } from "./dify";
import type { SendMessageRequest } from "./types";

/** 造 Dify 风格 SSE 字节流 (multipart bytes) */
function sseBytes(...lines: string[]): ReadableStream<Uint8Array> {
  const text = lines.join("\n") + "\n\n";
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
}

/** 造分块 SSE 字节: 模拟"半行"边界 */
function sseBytesChunked(lines: string[], chunkSize: number): ReadableStream<Uint8Array> {
  const text = lines.join("\n") + "\n\n";
  return new ReadableStream({
    start(controller) {
      for (let i = 0; i < text.length; i += chunkSize) {
        controller.enqueue(new TextEncoder().encode(text.slice(i, i + chunkSize)));
      }
      controller.close();
    },
  });
}

/** 把 AsyncIterable<ChatEvent> 收集成数组 */
async function collect<T>(it: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const x of it) out.push(x);
  return out;
}

const REQ: SendMessageRequest = {
  query: "1LE 电机怎么选?",
  inputs: {},
  user: "user-1",
  conversationId: undefined,
  autoGenerateName: true,
};

describe("DifyChatProvider", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    process.env.DIFY_API_KEY = "app-test";
    process.env.DIFY_API_URL = "https://dify.test/v1";
    process.env.DIFY_CHATFLOW_APP_ID = "abc123";
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });
  afterEach(() => vi.restoreAllMocks());

  it("构造时 name='dify'", () => {
    expect(new DifyChatProvider().name).toBe("dify");
  });

  it("message 事件归一化为 { type: 'message', delta: answer }", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: message`,
        `data: {"event":"message","id":"m1","task_id":"t1","answer":"你好","created_at":1700000000}`,
      ),
    });
    const p = new DifyChatProvider();
    const events = await collect(p.sendMessage(REQ, new AbortController().signal));
    const messages = events.filter((e) => e.type === "message");
    expect(messages).toEqual([{ type: "message", delta: "你好" }]);
  });

  it("message_end 归一化为带 conversationId + citations (retriever_resources)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: message_end`,
        `data: ${JSON.stringify({
          event: "message_end",
          id: "m1",
          task_id: "t1",
          conversation_id: "conv-xyz",
          metadata: {
            retriever_resources: [
              {
                position: 1,
                dataset_id: "ds1",
                dataset_name: "电机手册",
                document_id: "doc1",
                document_name: "1LE1023.pdf",
                segment_id: "s1",
                score: 0.87,
                content: "1LE 系列电机根据功率选型...",
                summary: null,
              },
              {
                position: 2,
                dataset_id: "ds1",
                dataset_name: "电机手册",
                document_id: "doc2",
                document_name: "选型指南.pdf",
                segment_id: "s2",
                score: 0.81,
                content: "选型步骤...",
                summary: null,
              },
            ],
          },
          created_at: 1700000000,
        })}`,
      ),
    });
    const p = new DifyChatProvider();
    const events = await collect(p.sendMessage(REQ, new AbortController().signal));
    const end = events.find((e) => e.type === "message_end");
    expect(end).toBeDefined();
    if (end?.type !== "message_end") return;
    expect(end.conversationId).toBe("conv-xyz");
    expect(end.citations).toHaveLength(2);
    expect(end.citations?.[0]).toMatchObject({
      documentName: "1LE1023.pdf",
      datasetName: "电机手册",
      score: 0.87,
      position: 1,
    });
  });

  it("workflow_started + node_started + node_finished + workflow_finished 归一化为 thinking/workflow_done", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: workflow_started`,
        `data: {"event":"workflow_started","task_id":"t1","workflow_run_id":"w1","created_at":1700000000}`,
        ``,
        `event: node_started`,
        `data: {"event":"node_started","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"knowledge-retrieval","title":"检索知识库","index":0,"created_at":1700000001}`,
        ``,
        `event: node_finished`,
        `data: {"event":"node_finished","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"knowledge-retrieval","title":"检索知识库","index":0,"status":"succeeded","elapsed_time":0.42,"created_at":1700000002}`,
        ``,
        `event: workflow_finished`,
        `data: {"event":"workflow_finished","task_id":"t1","workflow_run_id":"w1","status":"succeeded","elapsed_time":1.23,"total_tokens":100,"total_steps":1,"created_at":1700000003}`,
      ),
    });
    const events = await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    const thinkings = events.filter((e) => e.type === "thinking");
    expect(thinkings).toEqual([
      { type: "thinking", node: "n1", status: "started", detail: "knowledge-retrieval" },
      { type: "thinking", node: "n1", status: "finished", detail: "succeeded" },
    ]);
    const done = events.find((e) => e.type === "workflow_done");
    expect(done).toEqual({ type: "workflow_done", status: "succeeded" });
  });

  it("node_finished status=failed 归一化为 thinking finished+fail (detail 带 reason)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: node_started`,
        `data: {"event":"node_started","task_id":"t1","workflow_run_id":"w1","node_id":"n1","node_type":"llm","title":"LLM","index":0,"created_at":1700000001}`,
        ``,
        `event: node_finished`,
        `data: ${JSON.stringify({
          event: "node_finished",
          task_id: "t1",
          workflow_run_id: "w1",
          node_id: "n1",
          node_type: "llm",
          title: "LLM",
          index: 0,
          status: "failed",
          error: "rate_limit",
          elapsed_time: 0.1,
          created_at: 1700000002,
        })}`,
      ),
    });
    const events = await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    const failed = events.filter((e) => e.type === "thinking" && e.status === "finished");
    expect(failed).toHaveLength(1);
    if (failed[0].type !== "thinking") return;
    expect(failed[0].detail).toContain("failed");
  });

  it("error 事件归一化为 { type: 'error', code, message }", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: error`,
        `data: {"event":"error","task_id":"t1","message_id":"m1","status":"error","code":"provider_quota_exceeded","message":"quota exhausted"}`,
      ),
    });
    const events = await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    expect(events).toContainEqual({
      type: "error",
      code: "provider_quota_exceeded",
      message: "quota exhausted",
    });
  });

  it("ping 事件必须被忽略, 不上抛为 ChatEvent", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: ping`,
        `data: {"event":"ping","task_id":"t1","created_at":1700000000}`,
        ``,
        `event: message`,
        `data: {"event":"message","id":"m1","task_id":"t1","answer":"hi","created_at":1700000001}`,
      ),
    });
    const events = await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    // ping 不应出现
    expect(events.some((e) => e.type === "ping")).toBe(false);
    // message 仍正常
    expect(events).toContainEqual({ type: "message", delta: "hi" });
  });

  it("message_replace 归一化为 message (覆盖语义靠前端覆盖 content)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(
        `event: message`,
        `data: {"event":"message","id":"m1","task_id":"t1","answer":"违规内容","created_at":1700000000}`,
        ``,
        `event: message_replace`,
        `data: {"event":"message_replace","task_id":"t1","message_id":"m1","answer":"已替换内容","created_at":1700000001}`,
      ),
    });
    const events = await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    const messages = events.filter((e) => e.type === "message");
    expect(messages).toEqual([
      { type: "message", delta: "违规内容" },
      { type: "message", delta: "已替换内容" },
    ]);
  });

  it("HTTP 401 抛错 (不返流)", async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 401, text: async () => "unauthorized" });
    await expect(
      collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal)),
    ).rejects.toThrow(/401/);
  });

  it("请求体包含 query/inputs/user/response_mode='streaming' + Bearer 鉴权", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(`event: message`, `data: {"event":"message","id":"m1","task_id":"t1","answer":"x","created_at":1}`),
    });
    await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://dify.test/v1/chat-messages");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer app-test");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({
      query: REQ.query,
      inputs: {},
      user: REQ.user,
      response_mode: "streaming",
      auto_generate_name: true,
    });
    expect(body.conversation_id).toBeUndefined();  // v1 首次不带
  });

  it("续聊带 conversationId → 请求体 conversation_id 字段", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      body: sseBytes(`event: message`, `data: {"event":"message","id":"m1","task_id":"t1","answer":"x","created_at":1}`),
    });
    await collect(
      new DifyChatProvider().sendMessage(
        { ...REQ, conversationId: "conv-prev" },
        new AbortController().signal,
      ),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.conversation_id).toBe("conv-prev");
  });

  it("SSE 字节跨块拼接正确 (1 字节/块, 解析仍归一化)", async () => {
    const lines = [
      `event: message`,
      `data: {"event":"message","id":"m1","task_id":"t1","answer":"abc","created_at":1}`,
    ];
    fetchMock.mockResolvedValueOnce({ ok: true, body: sseBytesChunked(lines, 1) });
    const events = await collect(new DifyChatProvider().sendMessage(REQ, new AbortController().signal));
    expect(events).toContainEqual({ type: "message", delta: "abc" });
  });

  it("用户 abort → 抛 AbortError (链断 fetch)", async () => {
    fetchMock.mockImplementationOnce((_url, init: RequestInit) =>
      new Promise((_, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      }),
    );
    const controller = new AbortController();
    const it = new DifyChatProvider().sendMessage(REQ, controller.signal);
    setTimeout(() => controller.abort(), 5);
    await expect(collect(it)).rejects.toThrow(/aborted/);
  });
});
```

- [ ] **Step 2: 跑测试确认全 FAIL (dify.ts 还没建)**

Run: `cd web && bun run test -- dify.test`
Expected: 全 FAIL — `Cannot find module './dify'`

- [ ] **Step 3: 提交 (测试先行, 锁定行为)**

```bash
git add web/lib/chat/dify.test.ts
git commit -m "test(chat): DifyChatProvider 8 种 SSE 事件 + abort/拼接/鉴权红测试"
```

---

## Task 2.2: 实现 `dify.ts` 让测试全过

**Files:**
- Create: `web/lib/chat/dify.ts`

- [ ] **Step 1: 实现 provider**

`web/lib/chat/dify.ts`:

```ts
// DifyChatProvider: 把 Dify Chatflow SSE 归一化到 6 种 ChatEvent
// API 参考: https://docs.dify.ai/api-reference/对话流/发送对话消息
//
// Dify 鉴权: Authorization: Bearer {API_KEY} (固定 scheme, 严禁 shim 兼容 x-api-key)
// Dify SSE 格式: "event: <name>\ndata: <json>\n\n", 可分多块; ping 无 data
// 我们解析时用行 buffer, 跨块拼接, 遇空行就 dispatch 一次完整事件
import type { ChatEvent, ChatProvider, Citation, SendMessageRequest } from "./types";

const DEFAULT_API_URL = "https://api.dify.ai/v1";

interface RawEvent {
  event: string;
  [k: string]: unknown;
}

export class DifyChatProvider implements ChatProvider {
  readonly name = "dify";

  async *sendMessage(
    req: SendMessageRequest,
    signal: AbortSignal,
  ): AsyncIterable<ChatEvent> {
    const apiKey = process.env.DIFY_API_KEY;
    const apiUrl = process.env.DIFY_API_URL ?? DEFAULT_API_URL;
    const appId = process.env.DIFY_CHATFLOW_APP_ID;
    if (!apiKey) throw new Error("DIFY_API_KEY 未设置");
    if (!appId) throw new Error("DIFY_CHATFLOW_APP_ID 未设置");

    const res = await fetch(`${apiUrl}/chat-messages`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: req.query,
        inputs: req.inputs,
        user: req.user,
        response_mode: "streaming",
        conversation_id: req.conversationId,
        files: req.files,
        auto_generate_name: req.autoGenerateName ?? true,
        workflow_id: req.workflowId,
      }),
      signal,
    });
    if (!res.ok || !res.body) {
      const text = res.body ? await (res as Response).text() : "";
      throw new Error(`Dify ${res.status}: ${text}`);
    }

    yield* this.parseStream(res.body, signal);
  }

  /** 把 ReadableStream 解析成 ChatEvent; ping 忽略, 其他归一化 */
  private async *parseStream(
    body: ReadableStream<Uint8Array>,
    signal: AbortSignal,
  ): AsyncIterable<ChatEvent> {
    const reader = body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    try {
      while (true) {
        if (signal.aborted) {
          reader.cancel();
          throw new DOMException("aborted", "AbortError");
        }
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // 拆 "\n\n" 切分完整事件
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const ev = parseBlock(block);
          if (ev) yield* this.normalize(ev);
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  private *normalize(ev: RawEvent): Iterable<ChatEvent> {
    switch (ev.event) {
      case "message":
        yield { type: "message", delta: String(ev.answer ?? "") };
        return;
      case "message_replace":
        // Dify 替换语义: 整段换. 我们发新 message delta, 前端按"覆盖"处理
        yield { type: "message", delta: String(ev.answer ?? "") };
        return;
      case "message_end": {
        const meta = (ev.metadata ?? {}) as { retriever_resources?: RawRetrieverResource[] };
        const citations: Citation[] | undefined = meta.retriever_resources?.map(toCitation);
        yield {
          type: "message_end",
          conversationId: String(ev.conversation_id ?? ""),
          citations,
        };
        return;
      }
      case "workflow_started":
        // 不映射为 thinking (没 node 信息)
        return;
      case "node_started":
        yield {
          type: "thinking",
          node: String(ev.node_id ?? ""),
          status: "started",
          detail: ev.node_type ? String(ev.node_type) : undefined,
        };
        return;
      case "node_finished": {
        const detail = ev.error
          ? `failed: ${String(ev.error)}`
          : ev.status
            ? String(ev.status)
            : undefined;
        yield {
          type: "thinking",
          node: String(ev.node_id ?? ""),
          status: "finished",
          detail,
        };
        return;
      }
      case "workflow_finished":
        yield {
          type: "workflow_done",
          status: String(ev.status ?? "succeeded") as
            | "succeeded"
            | "failed"
            | "partial-succeeded"
            | "stopped",
        };
        return;
      case "error":
        yield {
          type: "error",
          code: String(ev.code ?? "unknown"),
          message: String(ev.message ?? ""),
        };
        return;
      case "ping":
      case "tts_message":
      case "tts_message_end":
        // 忽略: 音频/v1 不用
        return;
      default:
        // 未知事件: 忽略, 留 log 给 dev 排查
        // eslint-disable-next-line no-console
        console.warn(`[dify] 未知事件: ${ev.event}`);
        return;
    }
  }
}

interface RawRetrieverResource {
  position?: number;
  dataset_name?: string;
  document_name?: string;
  score?: number;
  content?: string;
  summary?: string | null;
}

function toCitation(r: RawRetrieverResource): Citation {
  return {
    documentName: r.document_name ?? "",
    datasetName: r.dataset_name,
    position: r.position,
    score: r.score,
    content: r.content ?? "",
    summary: r.summary ?? null,
  };
}

/** 解析单个 SSE block → RawEvent; 格式不合法返 null */
function parseBlock(block: string): RawEvent | null {
  const lines = block.split("\n");
  let event = "";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event: ")) {
      event = line.slice("event: ".length).trim();
    } else if (line.startsWith("data: ")) {
      data += line.slice("data: ".length);
    } else if (line.startsWith("data:")) {
      // Dify 有时省略空格, 容忍
      data += line.slice("data:".length).trimStart();
    }
  }
  if (!event || !data) return null;
  try {
    return JSON.parse(data) as RawEvent;
  } catch {
    return null;
  }
}
```

- [ ] **Step 2: 跑测试确认全过**

Run: `cd web && bun run test -- dify.test`
Expected: 13 PASS

- [ ] **Step 3: 跑 factory 测试, 现在 dify 那条也应该过**

Run: `cd web && bun run test -- factory.test`
Expected: 4 PASS

- [ ] **Step 4: 跑全量**

Run: `cd web && bun run test && bun run typecheck && bun run lint`
Expected: 全过

- [ ] **Step 5: 提交**

```bash
git add web/lib/chat/dify.ts
git commit -m "feat(chat): DifyChatProvider + SSE 归一化 (8 种事件 + abort + 跨块)"
```

---

## Task 2.3: PR 2 验证

- [ ] **Step 1: 跑 typecheck + lint + 全量测试**

```bash
cd web && bun run typecheck && bun run lint && bun run test
```

Expected: 全过

- [ ] **Step 2: 跑 dev server 写一个临时脚本手动触发一次流, 看不报错 (可选)**

如果 Dify 凭据没配, 跳过本步; PR 8 部署文档会讲真凭据配置。

- [ ] **Step 3: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 2 个新 commit (T2.1 红测试 / T2.2 dify 实装)

下一步: PR 3 — route handler + 鉴权 + SSE 转发。

---

# PR 3 · Route Handler + 鉴权 + SSE 转发

**PR 目标**: 实现 `app/api/chat/messages` POST 端点, 校验 `x-chat-token` 头 + zod 校验 body, 拿 provider 拉流, 把 `ChatEvent` 包成 `data: {json}\n\n` SSE 块转发给前端。单测覆盖: 鉴权失败 401 / 缺字段 400 / 流透传 / error 事件透传 / 401 Dify 错误降级到 502。

---

## Task 3.1: `route.test.ts` 红测试

**Files:**
- Create: `web/app/api/chat/messages/route.test.ts`

- [ ] **Step 1: 写红测试**

`web/app/api/chat/messages/route.test.ts`:

```ts
// Route handler 测试: mock provider, 验证 SSE 头 + 鉴权 + zod + 透传
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { POST } from "./route";
import type { ChatEvent } from "@/lib/chat/types";

// mock factory, 让 route handler 拿一个 stub provider
vi.mock("@/lib/chat/factory", () => ({
  getChatProvider: vi.fn(),
}));

// 解析 SSE 响应体成 ChatEvent 数组
async function parseSSE(body: ReadableStream<Uint8Array>): Promise<ChatEvent[]> {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";
  const out: ChatEvent[] = [];
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      const json = dataLine.slice("data: ".length);
      if (json === "[DONE]") continue;
      out.push(JSON.parse(json));
    }
  }
  return out;
}

import { getChatProvider } from "@/lib/chat/factory";

describe("/api/chat/messages", () => {
  beforeEach(() => {
    process.env.CHAT_PUBLIC_TOKEN = "secret-123";
    vi.mocked(getChatProvider).mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("缺 x-chat-token 头返 401", async () => {
    const req = new Request("http://localhost/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "q", user: "u", inputs: {} }),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it("x-chat-token 错返 401", async () => {
    const req = new Request("http://localhost/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-chat-token": "wrong" },
      body: JSON.stringify({ query: "q", user: "u", inputs: {} }),
    });
    const res = await POST(req);
    expect(res.status).toBe(401);
  });

  it("缺 query 返 400", async () => {
    const req = new Request("http://localhost/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-chat-token": "secret-123" },
      body: JSON.stringify({ user: "u", inputs: {} }),
    });
    const res = await POST(req);
    expect(res.status).toBe(400);
  });

  it("happy path: 鉴权 + provider 流透传 + SSE 头正确", async () => {
    async function* mockStream(): AsyncIterable<ChatEvent> {
      yield { type: "message", delta: "你" };
      yield { type: "message", delta: "好" };
      yield { type: "message_end", conversationId: "c1", citations: [] };
      yield { type: "done" };
    }
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: mockStream,
    });

    const req = new Request("http://localhost/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-chat-token": "secret-123" },
      body: JSON.stringify({ query: "1LE 电机?", user: "user-1", inputs: {} }),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("text/event-stream");
    expect(res.headers.get("Cache-Control")).toBe("no-cache, no-transform");
    const events = await parseSSE(res.body!);
    expect(events).toEqual([
      { type: "message", delta: "你" },
      { type: "message", delta: "好" },
      { type: "message_end", conversationId: "c1", citations: [] },
      { type: "done" },
    ]);
  });

  it("error 事件透传, 不会让流崩", async () => {
    async function* mockStream(): AsyncIterable<ChatEvent> {
      yield { type: "error", code: "provider_quota_exceeded", message: "quota" };
      yield { type: "done" };
    }
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: mockStream,
    });
    const req = new Request("http://localhost/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-chat-token": "secret-123" },
      body: JSON.stringify({ query: "q", user: "u", inputs: {} }),
    });
    const res = await POST(req);
    const events = await parseSSE(res.body!);
    expect(events[0]).toEqual({
      type: "error",
      code: "provider_quota_exceeded",
      message: "quota",
    });
  });

  it("provider 抛错 → 流里 yield error 事件 + [DONE]", async () => {
    async function* mockStream(): AsyncIterable<ChatEvent> {
      throw new Error("Dify 502");
    }
    vi.mocked(getChatProvider).mockReturnValue({
      name: "mock",
      sendMessage: mockStream,
    });
    const req = new Request("http://localhost/api/chat/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-chat-token": "secret-123" },
      body: JSON.stringify({ query: "q", user: "u", inputs: {} }),
    });
    const res = await POST(req);
    expect(res.status).toBe(200);
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    const all = (await reader.read()).value!;
    const text = decoder.decode(all);
    expect(text).toContain('"code":"upstream_error"');
    expect(text).toContain("[DONE]");
  });
});
```

- [ ] **Step 2: 跑测试确认全 FAIL**

Run: `cd web && bun run test -- route.test`
Expected: FAIL — `Cannot find module './route'`

- [ ] **Step 3: 提交 (测试先行)**

```bash
git add web/app/api/chat/messages/route.test.ts
git commit -m "test(chat): /api/chat/messages route handler 红测试 (鉴权/zod/流透传/错误降级)"
```

---

## Task 3.2: 实现 `route.ts`

**Files:**
- Create: `web/app/api/chat/messages/route.ts`

- [ ] **Step 1: 实现 route handler**

`web/app/api/chat/messages/route.ts`:

```ts
// /api/chat/messages POST 端点 (BFF for Dify / LlamaIndex)
// 1. x-chat-token 头校验 (env CHAT_PUBLIC_TOKEN) - 401 if mismatch
// 2. zod 校验 body - 400 if invalid
// 3. getChatProvider() - 工厂选 provider
// 4. for-await ChatEvent, 包成 data: {json}\n\n 转发
// 5. 流结束/出错 → data: [DONE]\n\n
// 鉴权: x-chat-token 是公网 anti-abuse, 不是私钥; nginx rate limit 是主防线
// DIFY_API_KEY 永远在 server env, 不进 bundle
import { NextRequest } from "next/server";
import { z } from "zod";
import { getChatProvider } from "@/lib/chat/factory";
import type { ChatEvent } from "@/lib/chat/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";  // SSE 需要长连接, 不能 edge

const BodySchema = z.object({
  query: z.string().min(1).max(16000),
  inputs: z.record(z.string(), z.unknown()).optional().default({}),
  user: z.string().min(1).max(64),
  conversationId: z.string().optional(),
  autoGenerateName: z.boolean().optional(),
});

function unauthorized(): Response {
  return new Response(JSON.stringify({ error: "unauthorized" }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  });
}

function badRequest(detail: string): Response {
  return new Response(JSON.stringify({ error: detail }), {
    status: 400,
    headers: { "Content-Type": "application/json" },
  });
}

export async function POST(req: NextRequest): Promise<Response> {
  // 1. 鉴权
  const expected = process.env.CHAT_PUBLIC_TOKEN;
  if (!expected) return badRequest("server 未配置 CHAT_PUBLIC_TOKEN");
  const got = req.headers.get("x-chat-token");
  if (got !== expected) return unauthorized();

  // 2. zod 校验
  let body: z.infer<typeof BodySchema>;
  try {
    body = BodySchema.parse(await req.json());
  } catch (e) {
    return badRequest(`body 校验失败: ${(e as Error).message}`);
  }

  // 3. provider
  let provider;
  try {
    provider = getChatProvider();
  } catch (e) {
    return new Response(JSON.stringify({ error: (e as Error).message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 4. SSE 流
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      try {
        for await (const ev of provider.sendMessage(
          {
            query: body.query,
            inputs: body.inputs,
            user: body.user,
            conversationId: body.conversationId,
            autoGenerateName: body.autoGenerateName,
          },
          req.signal,
        )) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
        }
      } catch (e) {
        // provider 抛错: 不让前端吃空, 推一个 error 事件
        const errEv: ChatEvent = {
          type: "error",
          code: "upstream_error",
          message: (e as Error).message,
        };
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(errEv)}\n\n`));
        } catch {
          // controller 已关
        }
      } finally {
        try {
          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
          controller.close();
        } catch {
          // ignore
        }
      }
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 2: 跑测试确认全过**

Run: `cd web && bun run test -- route.test`
Expected: 6 PASS

- [ ] **Step 3: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add web/app/api/chat/messages/route.ts
git commit -m "feat(chat): /api/chat/messages route handler (鉴权+zod+SSE+错误降级)"
```

---

## Task 3.3: 扩 `lib/api.ts` 加 chatApi 命名空间

**Files:**
- Modify: `web/lib/api.ts`

- [ ] **Step 1: 读现有 api.ts**

Read `web/lib/api.ts` 看现有 api 客户端风格 (fetcher 错误处理等)。

- [ ] **Step 2: 加 chatApi 命名空间**

在文件末尾追加 (用现有 `fetcher` 复用, 不另写):

```ts
// 智能体聊天 BFF 客户端
// 跟其他 api.* 一样走 Next.js route handler, 鉴权头前端读 NEXT_PUBLIC_CHAT_TOKEN
export const chatApi = {
  /** 拿前端公网 token (env NEXT_PUBLIC_CHAT_TOKEN); 失败返空串 */
  getToken(): string {
    return process.env.NEXT_PUBLIC_CHAT_TOKEN ?? "";
  },
  /** 发消息, 返 ReadableStream<Uint8Array> (SSE 字节) */
  async sendMessage(body: {
    query: string;
    user: string;
    inputs?: Record<string, unknown>;
    conversationId?: string;
  }): Promise<ReadableStream<Uint8Array>> {
    const res = await fetch("/api/chat/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-chat-token": this.getToken(),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`chat api ${res.status}: ${text}`);
    }
    if (!res.body) throw new Error("chat api 无 body");
    return res.body;
  },
};
```

- [ ] **Step 3: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错误

- [ ] **Step 4: 提交**

```bash
git add web/lib/api.ts
git commit -m "feat(chat): lib/api.ts 加 chatApi 命名空间 (走 /api/chat/messages)"
```

---

## Task 3.4: PR 3 验证

- [ ] **Step 1: 跑全量**

```bash
cd web && bun run typecheck && bun run lint && bun run test
```

Expected: 全过

- [ ] **Step 2: 端到端: 起 next dev, 手工 curl 一次 (mock 凭据)**

```bash
cd web && bun run dev
# 终端 2:
curl -i -X POST http://localhost:3000/api/chat/messages \
  -H "Content-Type: application/json" \
  -H "x-chat-token: $CHAT_PUBLIC_TOKEN" \
  -d '{"query":"test","user":"u1","inputs":{}}'
```

预期: 没配 DIFY_API_KEY 时返 500 (server error message); 配了 DIFY 凭据则返 SSE 流。

- [ ] **Step 3: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 4 个新 commit (T3.1 测试 / T3.2 route / T3.3 api 扩展)

下一步: PR 4 — localStorage 会话持久化。

---

# PR 4 · `lib/chat/storage.ts` + 测试

**PR 目标**: 实现 `Conversation` 元数据 localStorage CRUD, 健壮处理 JSON 损坏 (返空数组) + 版本号不匹配 (丢弃) + localStorage 不可用 (静默返空)。TDD: 测 CRUD 4 个动作 + 损坏 + 版本。

---

## Task 4.1: `storage.test.ts` 红测试

**Files:**
- Create: `web/lib/chat/storage.test.ts`

- [ ] **Step 1: 写红测试**

`web/lib/chat/storage.test.ts`:

```ts
// localStorage 会话元数据 CRUD 测试
// 健壮性: 损坏 JSON / 缺版本号 / localStorage 不可用 都要优雅降级
import { describe, it, expect, beforeEach, vi } from "vitest";
import { STORAGE_KEY, loadConversations, saveConversations, upsertConversation, deleteConversation } from "./storage";
import type { Conversation } from "./types";

const SAMPLE: Conversation = {
  id: "c1",
  title: "测试会话",
  createdAt: 1700000000000,
  updatedAt: 1700000000000,
  messageCount: 0,
};

describe("loadConversations", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("空 localStorage 返空数组", () => {
    expect(loadConversations()).toEqual([]);
  });

  it("正常 JSON 返解析后数组", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, items: [SAMPLE] }));
    expect(loadConversations()).toEqual([SAMPLE]);
  });

  it("JSON 损坏返空数组 (不崩)", () => {
    localStorage.setItem(STORAGE_KEY, "{not json");
    expect(loadConversations()).toEqual([]);
  });

  it("版本号不匹配 (v0) 丢弃, 返空数组", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 0, items: [SAMPLE] }));
    expect(loadConversations()).toEqual([]);
  });

  it("缺 version 字段 → 丢弃, 返空数组", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ items: [SAMPLE] }));
    expect(loadConversations()).toEqual([]);
  });

  it("localStorage 不可用 (抛错) 返空数组", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(loadConversations()).toEqual([]);
  });
});

describe("saveConversations", () => {
  beforeEach(() => localStorage.clear());

  it("写后能读回", () => {
    saveConversations([SAMPLE]);
    const raw = localStorage.getItem(STORAGE_KEY);
    expect(raw).toBe(JSON.stringify({ version: 1, items: [SAMPLE] }));
    expect(loadConversations()).toEqual([SAMPLE]);
  });

  it("localStorage 不可用 (抛错) 不上抛, 静默", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(() => saveConversations([SAMPLE])).not.toThrow();
  });
});

describe("upsertConversation", () => {
  beforeEach(() => localStorage.clear());

  it("空列表时插入新 conv", () => {
    upsertConversation(SAMPLE);
    expect(loadConversations()).toEqual([SAMPLE]);
  });

  it("同 id 已存在 → 替换 (不重复)", () => {
    upsertConversation(SAMPLE);
    upsertConversation({ ...SAMPLE, title: "更新后", updatedAt: 1700000001000 });
    const all = loadConversations();
    expect(all).toHaveLength(1);
    expect(all[0].title).toBe("更新后");
  });

  it("不同 id 都插入", () => {
    upsertConversation(SAMPLE);
    upsertConversation({ ...SAMPLE, id: "c2", title: "第二个" });
    expect(loadConversations()).toHaveLength(2);
  });
});

describe("deleteConversation", () => {
  beforeEach(() => localStorage.clear());

  it("删存在的 id", () => {
    upsertConversation(SAMPLE);
    upsertConversation({ ...SAMPLE, id: "c2", title: "B" });
    deleteConversation("c1");
    const all = loadConversations();
    expect(all.map((c) => c.id)).toEqual(["c2"]);
  });

  it("删不存在的 id 是 no-op", () => {
    upsertConversation(SAMPLE);
    deleteConversation("ghost");
    expect(loadConversations()).toHaveLength(1);
  });
});
```

- [ ] **Step 2: 跑测试确认全 FAIL**

Run: `cd web && bun run test -- storage.test`
Expected: 全 FAIL — `Cannot find module './storage'`

- [ ] **Step 3: 提交 (测试先行)**

```bash
git add web/lib/chat/storage.test.ts
git commit -m "test(chat): storage CRUD + 损坏/版本/不可用 红测试"
```

---

## Task 4.2: 实现 `storage.ts`

**Files:**
- Create: `web/lib/chat/storage.ts`

- [ ] **Step 1: 实现**

`web/lib/chat/storage.ts`:

```ts
// localStorage 会话元数据 CRUD
// v1 单用户, 不加密; 敏感对话内容放 messagesByConv (内存, 不持久化)
//
// 健壮性:
// - JSON 损坏 → 返空数组, 不崩
// - version 不匹配 → 丢弃旧数据, 返空数组
// - localStorage 不可用 (Safari 隐私模式等) → 静默降级
//
// schema 升级: 改 VERSION + 加迁移函数; 旧数据走迁移或丢弃
import type { Conversation } from "./types";

export const STORAGE_KEY = "rag.chat.conversations.v1";
const VERSION = 1;

interface StoredShape {
  version: number;
  items: Conversation[];
}

function read(): Conversation[] {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return [];
  }
  if (!raw) return [];
  let parsed: StoredShape;
  try {
    parsed = JSON.parse(raw) as StoredShape;
  } catch {
    return [];
  }
  if (!parsed || parsed.version !== VERSION) return [];
  if (!Array.isArray(parsed.items)) return [];
  return parsed.items;
}

function write(items: Conversation[]): void {
  const payload: StoredShape = { version: VERSION, items };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // 配额满 / 隐私模式: 静默
  }
}

export function loadConversations(): Conversation[] {
  return read();
}

export function saveConversations(items: Conversation[]): void {
  write(items);
}

export function upsertConversation(conv: Conversation): void {
  const all = read();
  const idx = all.findIndex((c) => c.id === conv.id);
  if (idx >= 0) {
    all[idx] = conv;
  } else {
    all.push(conv);
  }
  write(all);
}

export function deleteConversation(id: string): void {
  const all = read().filter((c) => c.id !== id);
  write(all);
}
```

- [ ] **Step 2: 跑测试确认全过**

Run: `cd web && bun run test -- storage.test`
Expected: 12 PASS

- [ ] **Step 3: 跑 typecheck + lint**

Run: `cd web && bun run typecheck && bun run lint`
Expected: 无错

- [ ] **Step 4: 提交**

```bash
git add web/lib/chat/storage.ts
git commit -m "feat(chat): localStorage 会话 CRUD + 损坏/版本/不可用降级"
```

---

## Task 4.3: PR 4 验证

- [ ] **Step 1: 跑全量**

```bash
cd web && bun run test && bun run typecheck && bun run lint
```

Expected: 全过

- [ ] **Step 2: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 2 个新 commit (T4.1 测试 / T4.2 storage)

下一步: PR 5 — 基础 UI 组件 (MessageBubble / Composer / CitationPanel / ThinkingTrace / MessageList)。

---

# PR 5 · 基础 UI 组件

**PR 目标**: 实现 5 个基础 UI 组件, 全用 shadcn/ui, 单测覆盖关键交互 (user/assistant 区分、Enter 发送、引用折叠、思考折叠)。状态机接入留 PR 6。

---

## Task 5.1: `MessageBubble` + 测试

**Files:**
- Create: `web/components/chat/MessageBubble.tsx`
- Create: `web/components/chat/MessageBubble.test.tsx`

- [ ] **Step 1: 写红测试**

`web/components/chat/MessageBubble.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MessageBubble } from "./MessageBubble";
import type { Message } from "@/lib/chat/types";

const USER_MSG: Message = {
  id: "m1",
  role: "user",
  content: "1LE 电机怎么选?",
  createdAt: 1700000000000,
};

const AI_MSG: Message = {
  id: "m2",
  role: "assistant",
  content: "根据功率选...",
  createdAt: 1700000001000,
  citations: [
    { documentName: "1LE1023.pdf", score: 0.87, content: "选型依据功率" },
  ],
  thinking: [
    { node: "n1", status: "started" },
    { node: "n1", status: "finished", detail: "succeeded" },
  ],
};

describe("MessageBubble", () => {
  it("user 消息渲染内容, role=user 标识", () => {
    render(<MessageBubble message={USER_MSG} />);
    expect(screen.getByTestId("message-m1")).toHaveTextContent("1LE 电机怎么选?");
    expect(screen.getByTestId("message-m1").dataset.role).toBe("user");
  });

  it("assistant 消息渲染内容 + role=assistant", () => {
    render(<MessageBubble message={AI_MSG} />);
    expect(screen.getByTestId("message-m2")).toHaveTextContent("根据功率选...");
    expect(screen.getByTestId("message-m2").dataset.role).toBe("assistant");
  });

  it("有 citations 时显示折叠面板 (默认收起)", () => {
    render(<MessageBubble message={AI_MSG} />);
    expect(screen.getByTestId("citation-panel")).toBeInTheDocument();
    // 收起: 文档名不可见
    expect(screen.queryByText("1LE1023.pdf")).not.toBeInTheDocument();
  });

  it("点击折叠面板展开, 显示引用", () => {
    render(<MessageBubble message={AI_MSG} />);
    fireEvent.click(screen.getByTestId("citation-toggle"));
    expect(screen.getByText("1LE1023.pdf")).toBeInTheDocument();
  });

  it("有 thinking 时显示折叠面板", () => {
    render(<MessageBubble message={AI_MSG} />);
    expect(screen.getByTestId("thinking-panel")).toBeInTheDocument();
  });

  it("interrupted=true 时显示中断徽章", () => {
    render(<MessageBubble message={{ ...AI_MSG, interrupted: true }} />);
    expect(screen.getByTestId("interrupted-badge")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认全 FAIL**

Run: `cd web && bun run test -- MessageBubble.test`
Expected: 全 FAIL — 模块未找到

- [ ] **Step 3: 实现 MessageBubble**

`web/components/chat/MessageBubble.tsx`:

```tsx
// 单条消息气泡 (2026-06-09)
// user 靠右, assistant 靠左; assistant 包含 markdown 渲染 + 引用/思考折叠
import ReactMarkdown from "react-markdown";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import type { Message } from "@/lib/chat/types";
import { CitationPanel } from "./CitationPanel";
import { ThinkingTrace } from "./ThinkingTrace";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div
      data-testid={`message-${message.id}`}
      data-role={message.role}
      className={isUser ? "flex justify-end" : "flex justify-start"}
    >
      <div
        className={
          isUser
            ? "max-w-[80%] rounded-2xl bg-ink px-4 py-2.5 text-paper"
            : "max-w-[80%] rounded-2xl border border-border/60 bg-card px-4 py-2.5"
        }
      >
        {/* 内容 */}
        {isUser ? (
          <p className="whitespace-pre-wrap text-base">{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* 中断徽章 */}
        {message.interrupted && (
          <div
            data-testid="interrupted-badge"
            className="mt-2 inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs text-amber-700"
          >
            已中断
          </div>
        )}

        {/* 引用块 */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <Collapsible className="mt-3">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 px-2 text-xs text-muted-foreground"
                data-testid="citation-toggle"
              >
                ▾ 引用 {message.citations.length} 条
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CitationPanel citations={message.citations} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* 思考过程 */}
        {!isUser && message.thinking && message.thinking.length > 0 && (
          <Collapsible className="mt-2">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 px-2 text-xs text-muted-foreground"
                data-testid="thinking-toggle"
              >
                ▾ 思考过程
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ThinkingTrace steps={message.thinking} />
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试 (因 CitationPanel/ThinkingTrace 还没建, 会 fail on import)**

Run: `cd web && bun run test -- MessageBubble.test`
Expected: FAIL on `Cannot find module './CitationPanel'`

---

## Task 5.2: `CitationPanel` + `ThinkingTrace`

**Files:**
- Create: `web/components/chat/CitationPanel.tsx`
- Create: `web/components/chat/ThinkingTrace.tsx`

- [ ] **Step 1: 实现 CitationPanel**

`web/components/chat/CitationPanel.tsx`:

```tsx
// 引用块面板: 列文档名 + score + 截断内容
import type { Citation } from "@/lib/chat/types";

export function CitationPanel({ citations }: { citations: Citation[] }) {
  return (
    <div className="mt-2 space-y-2" data-testid="citation-panel">
      {citations.map((c, i) => (
        <div
          key={i}
          className="rounded-lg border border-border/40 bg-muted/30 px-3 py-2"
        >
          <div className="flex items-baseline justify-between text-xs text-muted-foreground">
            <span className="truncate font-medium">{c.documentName}</span>
            {c.score != null && <span className="num text-clay">score {c.score.toFixed(2)}</span>}
          </div>
          {c.datasetName && (
            <div className="mt-0.5 text-[11px] text-muted-foreground/70">
              来自: {c.datasetName}
            </div>
          )}
          {c.summary && (
            <div className="mt-1 text-sm italic">{c.summary}</div>
          )}
          <p className="mt-1 line-clamp-3 text-sm">{c.content}</p>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 实现 ThinkingTrace**

`web/components/chat/ThinkingTrace.tsx`:

```tsx
// 思考过程: 列每个节点的 started/finished 状态
import { Badge } from "@/components/ui/badge";

interface Step {
  node: string;
  status: "started" | "finished";
  detail?: string;
}

export function ThinkingTrace({ steps }: { steps: Step[] }) {
  return (
    <div className="mt-2 space-y-1" data-testid="thinking-panel">
      {steps.map((s, i) => (
        <div
          key={i}
          className="flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs"
        >
          <Badge
            variant="outline"
            className={
              s.status === "finished"
                ? "border-moss/40 text-moss"
                : "border-amber-300 text-amber-700"
            }
          >
            {s.status}
          </Badge>
          <span className="num text-muted-foreground">{s.node}</span>
          {s.detail && <span className="text-muted-foreground/70">· {s.detail}</span>}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: 跑 MessageBubble 测试, 应该全过**

Run: `cd web && bun run test -- MessageBubble.test`
Expected: 6 PASS

- [ ] **Step 4: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错

- [ ] **Step 5: 提交**

```bash
git add web/components/chat/MessageBubble.tsx web/components/chat/MessageBubble.test.tsx web/components/chat/CitationPanel.tsx web/components/chat/ThinkingTrace.tsx
git commit -m "feat(chat): MessageBubble + CitationPanel + ThinkingTrace (markdown 渲染 + 折叠)"
```

---

## Task 5.3: `Composer` + 测试

**Files:**
- Create: `web/components/chat/Composer.tsx`
- Create: `web/components/chat/Composer.test.tsx`

- [ ] **Step 1: 写红测试**

`web/components/chat/Composer.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Composer } from "./Composer";

describe("Composer", () => {
  it("空字符串按 Enter 不触发 onSend", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("composer-textarea");
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("有内容按 Enter 触发 onSend, onSend 后清空", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("composer-textarea");
    fireEvent.change(ta, { target: { value: "1LE 电机?" } });
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("1LE 电机?");
    expect((ta as HTMLTextAreaElement).value).toBe("");
  });

  it("Shift+Enter 不发送, 加换行", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);
    const ta = screen.getByTestId("composer-textarea");
    fireEvent.change(ta, { target: { value: "line1" } });
    fireEvent.keyDown(ta, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("streaming 时显示停止按钮 (替代发送)", () => {
    const onSend = vi.fn();
    const onStop = vi.fn();
    render(<Composer onSend={onSend} onStop={onStop} disabled={false} streaming={true} />);
    expect(screen.queryByTestId("composer-send")).not.toBeInTheDocument();
    expect(screen.getByTestId("composer-stop")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("composer-stop"));
    expect(onStop).toHaveBeenCalled();
  });

  it("非 streaming 时显示发送按钮", () => {
    render(<Composer onSend={vi.fn()} disabled={false} />);
    expect(screen.getByTestId("composer-send")).toBeInTheDocument();
    expect(screen.queryByTestId("composer-stop")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd web && bun run test -- Composer.test`
Expected: 全 FAIL

- [ ] **Step 3: 实现 Composer**

`web/components/chat/Composer.tsx`:

```tsx
// 消息输入框 + 发送/停止切换 (2026-06-09)
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Props {
  onSend: (text: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
}

export function Composer({ onSend, onStop, disabled, streaming }: Props) {
  const [text, setText] = useState("");

  const handleSend = () => {
    const t = text.trim();
    if (!t) return;
    onSend(t);
    setText("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex items-end gap-2 border-t border-border/60 bg-card/50 px-4 py-3">
      <Textarea
        data-testid="composer-textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={streaming ? "AI 正在回复…" : "输入消息, Enter 发送, Shift+Enter 换行"}
        disabled={disabled}
        rows={1}
        className="min-h-[40px] resize-none"
      />
      {streaming ? (
        <Button
          data-testid="composer-stop"
          onClick={onStop}
          variant="outline"
          className="shrink-0"
        >
          停止
        </Button>
      ) : (
        <Button
          data-testid="composer-send"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="shrink-0"
        >
          发送
        </Button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 跑测试确认全过**

Run: `cd web && bun run test -- Composer.test`
Expected: 5 PASS

- [ ] **Step 5: 提交**

```bash
git add web/components/chat/Composer.tsx web/components/chat/Composer.test.tsx
git commit -m "feat(chat): Composer (Enter 发送 / Shift+Enter 换行 / streaming 切停止)"
```

---

## Task 5.4: `MessageList`

**Files:**
- Create: `web/components/chat/MessageList.tsx`

- [ ] **Step 1: 实现**

`web/components/chat/MessageList.tsx`:

```tsx
// 消息列表: 自动滚到底, 但用户向上滚看历史时停止自动滚
import { useEffect, useRef, useState } from "react";
import { MessageBubble } from "./MessageBubble";
import type { Message } from "@/lib/chat/types";

interface Props {
  messages: Message[];
  streamingMessageId?: string;
}

export function MessageList({ messages, streamingMessageId }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [sticky, setSticky] = useState(true);

  // 滚到底
  useEffect(() => {
    if (!sticky) return;
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, sticky]);

  // 检测用户是否在底部
  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setSticky(distFromBottom < 80);
  };

  return (
    <div
      ref={ref}
      onScroll={onScroll}
      className="flex-1 overflow-y-auto px-4 py-4"
      data-testid="message-list"
    >
      {messages.length === 0 ? (
        <p className="text-center text-sm text-muted-foreground">开始一段新对话 ↓</p>
      ) : (
        <div className="space-y-4">
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
            />
          ))}
          {streamingMessageId && (
            <span className="inline-block h-4 w-1 animate-pulse bg-foreground/60" />
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错

- [ ] **Step 3: 提交**

```bash
git add web/components/chat/MessageList.tsx
git commit -m "feat(chat): MessageList (sticky-bottom 自动滚)"
```

---

## Task 5.5: PR 5 验证

- [ ] **Step 1: 跑全量**

```bash
cd web && bun run test && bun run typecheck && bun run lint
```

Expected: 全过

- [ ] **Step 2: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 3 个新 commit (T5.1-5.2 Bubble+Panel / T5.3 Composer / T5.4 MessageList)

下一步: PR 6 — ConversationList + ChatShell 状态机 + 接入 storage。

---

# PR 6 · ConversationList + ChatShell 状态机

**PR 目标**: 把 5 个基础组件 + storage 装到 `ChatShell`, 实现状态机: conversations / currentId / messagesByConv / streamingByConv (按 conv 隔离的 AbortController) / draft。CRUD 走 storage, 流式归一化 ChatEvent 写到 messagesByConv[currentId]。

---

## Task 6.1: `ConversationList` + 测试

**Files:**
- Create: `web/components/chat/ConversationList.tsx`
- Create: `web/components/chat/ConversationList.test.tsx`

- [ ] **Step 1: 写红测试**

`web/components/chat/ConversationList.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConversationList } from "./ConversationList";
import type { Conversation } from "@/lib/chat/types";

const CONVS: Conversation[] = [
  { id: "a", title: "电机选型", createdAt: 1700000000000, updatedAt: 1700000003000, messageCount: 5 },
  { id: "b", title: "产品报价", createdAt: 1700000001000, updatedAt: 1700000002000, messageCount: 3 },
];

describe("ConversationList", () => {
  it("渲染所有会话 + 标题", () => {
    render(
      <ConversationList
        conversations={CONVS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("电机选型")).toBeInTheDocument();
    expect(screen.getByText("产品报价")).toBeInTheDocument();
  });

  it("按 updatedAt 倒序", () => {
    render(
      <ConversationList
        conversations={CONVS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    const items = screen.getAllByTestId(/^conv-/);
    expect(items[0]).toHaveAttribute("data-testid", "conv-a");
    expect(items[1]).toHaveAttribute("data-testid", "conv-b");
  });

  it("currentId 高亮", () => {
    render(
      <ConversationList
        conversations={CONVS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId("conv-a").className).toContain("border-clay");
  });

  it("点新对话按钮触发 onCreate", () => {
    const onCreate = vi.fn();
    render(
      <ConversationList
        conversations={CONVS}
        currentId="a"
        onSelect={vi.fn()}
        onCreate={onCreate}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("new-conv"));
    expect(onCreate).toHaveBeenCalled();
  });

  it("点会话触发 onSelect(id)", () => {
    const onSelect = vi.fn();
    render(
      <ConversationList
        conversations={CONVS}
        currentId="a"
        onSelect={onSelect}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("conv-b"));
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("无会话时显示空状态", () => {
    render(
      <ConversationList
        conversations={[]}
        currentId={null}
        onSelect={vi.fn()}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByTestId("empty-conv")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd web && bun run test -- ConversationList.test`
Expected: 全 FAIL

- [ ] **Step 3: 实现 ConversationList**

`web/components/chat/ConversationList.tsx`:

```tsx
// 会话侧边栏 (2026-06-09)
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { Conversation } from "@/lib/chat/types";

interface Props {
  conversations: Conversation[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60_000) return "刚刚";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)} 小时前`;
  return `${Math.floor(diff / 86400_000)} 天前`;
}

export function ConversationList({ conversations, currentId, onSelect, onCreate, onDelete }: Props) {
  const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border/60 bg-card/30">
      <div className="border-b border-border/60 px-4 py-3">
        <h2 className="display text-xl italic tracking-tight">Chat</h2>
        <p className="eyebrow mt-0.5 text-muted-foreground/60">与产品智能体对话</p>
      </div>

      <div className="px-3 py-2">
        <Button
          data-testid="new-conv"
          onClick={onCreate}
          variant="outline"
          className="w-full"
        >
          + 新对话
        </Button>
      </div>

      <ScrollArea className="flex-1 px-2">
        {sorted.length === 0 ? (
          <p
            data-testid="empty-conv"
            className="px-2 py-6 text-center text-sm text-muted-foreground"
          >
            开始一段新对话
          </p>
        ) : (
          <ul className="space-y-1">
            {sorted.map((c) => (
              <li key={c.id}>
                <div
                  data-testid={`conv-${c.id}`}
                  onClick={() => onSelect(c.id)}
                  className={cn(
                    "group flex cursor-pointer items-baseline gap-2 rounded-md border border-transparent px-2.5 py-2 transition-colors hover:bg-muted/40",
                    c.id === currentId && "border-clay/40 bg-clay/5",
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{c.title}</div>
                    <div className="num mt-0.5 text-xs text-muted-foreground/60">
                      {formatRelativeTime(c.updatedAt)} · {c.messageCount} 条
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(c.id);
                    }}
                    className="shrink-0 rounded p-1 text-xs text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                    aria-label="删除会话"
                    data-testid={`delete-${c.id}`}
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </ScrollArea>
    </aside>
  );
}
```

- [ ] **Step 4: 跑测试确认全过**

Run: `cd web && bun run test -- ConversationList.test`
Expected: 6 PASS

- [ ] **Step 5: 提交**

```bash
git add web/components/chat/ConversationList.tsx web/components/chat/ConversationList.test.tsx
git commit -m "feat(chat): ConversationList 侧边栏 (倒序/高亮/删除按钮)"
```

---

## Task 6.2: `ChatShell` 状态机 + 测试

**Files:**
- Create: `web/components/chat/ChatShell.tsx`
- Create: `web/components/chat/ChatShell.test.tsx`

- [ ] **Step 1: 写红测试**

`web/components/chat/ChatShell.test.tsx`:

```tsx
// ChatShell 状态机测试
// 关键: 流按 conv 隔离, 停止只停当前 conv
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatShell } from "./ChatShell";
import { STORAGE_KEY } from "@/lib/chat/storage";

// mock chatApi.sendMessage 返受控流
vi.mock("@/lib/api", () => ({
  chatApi: {
    getToken: () => "test-token",
    sendMessage: vi.fn(),
  },
}));

import { chatApi } from "@/lib/api";

function makeStream(events: Array<{ type: string; [k: string]: unknown }>) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const ev of events) {
        controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
      controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
      controller.close();
    },
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(chatApi.sendMessage).mockReset();
});

describe("ChatShell", () => {
  it("初始渲染: 侧边栏 + 提示", () => {
    render(<ChatShell />);
    expect(screen.getByTestId("new-conv")).toBeInTheDocument();
  });

  it("新对话按钮 → 列表出现一个新条目, 切到它", async () => {
    render(<ChatShell />);
    fireEvent.click(screen.getByTestId("new-conv"));
    await waitFor(() => {
      expect(screen.getAllByTestId(/^conv-/).length).toBe(1);
    });
  });

  it("localStorage 恢复会话", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        version: 1,
        items: [
          { id: "restored", title: "历史", createdAt: 1700000000000, updatedAt: 1700000000000, messageCount: 0 },
        ],
      }),
    );
    render(<ChatShell />);
    expect(screen.getByTestId("conv-restored")).toBeInTheDocument();
  });

  it("发消息 → 流过来后 message 渲染, message_end 写 citations", async () => {
    vi.mocked(chatApi.sendMessage).mockResolvedValue(
      makeStream([
        { type: "message", delta: "你" },
        { type: "message", delta: "好" },
        {
          type: "message_end",
          conversationId: "c1",
          citations: [{ documentName: "d.pdf", score: 0.9, content: "x" }],
        },
        { type: "done" },
      ]),
    );

    render(<ChatShell />);
    fireEvent.click(screen.getByTestId("new-conv"));
    const ta = await screen.findByTestId("composer-textarea");
    fireEvent.change(ta, { target: { value: "hi" } });
    fireEvent.keyDown(ta, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByText("你好")).toBeInTheDocument();
    });
    expect(chatApi.sendMessage).toHaveBeenCalledWith(
      expect.objectContaining({ query: "hi" }),
    );
  });

  it("点停止 → abort 当前 conv 的流", async () => {
    // 造一个永不结束的流
    const never = new ReadableStream<Uint8Array>({
      start() { /* 永不 close */ },
    });
    vi.mocked(chatApi.sendMessage).mockResolvedValue(never);

    render(<ChatShell />);
    fireEvent.click(screen.getByTestId("new-conv"));
    const ta = await screen.findByTestId("composer-textarea");
    fireEvent.change(ta, { target: { value: "hi" } });
    fireEvent.keyDown(ta, { key: "Enter" });

    const stopBtn = await screen.findByTestId("composer-stop");
    fireEvent.click(stopBtn);
    // composer 切回发送按钮
    await waitFor(() => {
      expect(screen.getByTestId("composer-send")).toBeInTheDocument();
    });
  });

  it("删 conv → state 清掉, 不影响其他", async () => {
    render(<ChatShell />);
    fireEvent.click(screen.getByTestId("new-conv"));
    await waitFor(() => expect(screen.getAllByTestId(/^conv-/).length).toBe(1));
    const convId = screen.getAllByTestId(/^conv-/)[0].getAttribute("data-testid")!.replace("conv-", "");
    fireEvent.click(screen.getByTestId(`delete-${convId}`));
    await waitFor(() => {
      expect(screen.queryByTestId(`conv-${convId}`)).not.toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: 跑测试确认全 FAIL**

Run: `cd web && bun run test -- ChatShell.test`
Expected: 全 FAIL

- [ ] **Step 3: 实现 ChatShell**

`web/components/chat/ChatShell.tsx`:

```tsx
// 智能体聊天 Shell (2026-06-09) - 状态机 host
// 状态: conversations / currentId / messagesByConv / streamingByConv(按 conv 隔离的 AbortController)
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ConversationList } from "./ConversationList";
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";
import { chatApi } from "@/lib/api";
import {
  loadConversations, upsertConversation, deleteConversation as storageDelete,
} from "@/lib/chat/storage";
import type { ChatEvent, Conversation, Message } from "@/lib/chat/types";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const DRAFT_KEY = "rag.chat.draft.v1";

export function ChatShell() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messagesByConv, setMessagesByConv] = useState<Record<string, Message[]>>({});
  const [streamingConvId, setStreamingConvId] = useState<string | null>(null);
  const aborters = useRef<Record<string, AbortController | null>>({});
  const [draft, setDraft] = useState<string>("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  // 启动: 加载 storage
  useEffect(() => {
    const saved = loadConversations();
    setConversations(saved);
    if (saved.length > 0) setCurrentId(saved[0].id);
    const d = localStorage.getItem(DRAFT_KEY) ?? "";
    setDraft(d);
  }, []);

  // draft 草稿保存
  useEffect(() => {
    try { localStorage.setItem(DRAFT_KEY, draft); } catch { /* ignore */ }
  }, [draft]);

  // 切 conv 时清掉它未完成流的中断标记
  useEffect(() => {
    if (!currentId) return;
    const c = conversations.find((x) => x.id === currentId);
    if (c) {
      // 首次切: 不用动 messages
    }
  }, [currentId, conversations]);

  const persistConv = useCallback((conv: Conversation) => {
    upsertConversation(conv);
    setConversations((prev) => {
      const idx = prev.findIndex((c) => c.id === conv.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = conv;
        return next;
      }
      return [...prev, conv];
    });
  }, []);

  const handleNew = useCallback(() => {
    const conv: Conversation = {
      id: newId(),
      title: "新对话",
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messageCount: 0,
    };
    persistConv(conv);
    setCurrentId(conv.id);
    setMessagesByConv((m) => ({ ...m, [conv.id]: [] }));
  }, [persistConv]);

  const handleDelete = useCallback((id: string) => {
    setPendingDeleteId(id);
  }, []);

  const confirmDelete = useCallback(() => {
    if (!pendingDeleteId) return;
    const id = pendingDeleteId;
    aborters.current[id]?.abort();
    delete aborters.current[id];
    setMessagesByConv((m) => {
      const { [id]: _, ...rest } = m;
      return rest;
    });
    setConversations((prev) => prev.filter((c) => c.id !== id));
    storageDelete(id);
    if (currentId === id) {
      setCurrentId((cur) => {
        const remaining = conversations.filter((c) => c.id !== id);
        return remaining[0]?.id ?? null;
      });
    }
    setPendingDeleteId(null);
  }, [pendingDeleteId, currentId, conversations]);

  const handleSelect = useCallback((id: string) => {
    setCurrentId(id);
  }, []);

  const handleSend = useCallback(async (text: string) => {
    let convId = currentId;
    if (!convId) {
      // 没选: 自动新建
      const conv: Conversation = {
        id: newId(),
        title: text.slice(0, 20),
        createdAt: Date.now(),
        updatedAt: Date.now(),
        messageCount: 1,
      };
      persistConv(conv);
      setCurrentId(conv.id);
      setMessagesByConv((m) => ({ ...m, [conv.id]: [] }));
      convId = conv.id;
    }

    const userMsg: Message = {
      id: newId(),
      role: "user",
      content: text,
      createdAt: Date.now(),
    };
    const assistantId = newId();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      createdAt: Date.now(),
      thinking: [],
    };

    setMessagesByConv((m) => ({
      ...m,
      [convId!]: [...(m[convId!] ?? []), userMsg, assistantMsg],
    }));

    // 更新 conv 元数据
    setConversations((prev) => {
      const idx = prev.findIndex((c) => c.id === convId);
      const next = [...prev];
      if (idx >= 0) {
        const c = { ...next[idx], updatedAt: Date.now(), messageCount: next[idx].messageCount + 2 };
        if (c.title === "新对话" || c.title === text.slice(0, 20) && c.messageCount === 2) {
          c.title = text.slice(0, 20);
        }
        next[idx] = c;
        upsertConversation(c);
      }
      return next;
    });

    // abort 旧流
    aborters.current[convId!]?.abort();
    const ac = new AbortController();
    aborters.current[convId!] = ac;
    setStreamingConvId(convId!);

    try {
      const stream = await chatApi.sendMessage({
        query: text,
        user: convId!,  // v1 用 convId 当 dify user (单一匿名用户)
        inputs: {},
        conversationId: undefined,  // TODO 续聊从 assistantId 读 message_end.conversationId
      });
      const reader = stream.getReader();
      const decoder = new TextDecoder("utf-8");
      let buf = "";

      while (true) {
        if (ac.signal.aborted) {
          reader.cancel();
          break;
        }
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx: number;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const block = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;
          const json = dataLine.slice("data: ".length);
          if (json === "[DONE]") continue;
          const ev = JSON.parse(json) as ChatEvent;
          applyEvent(convId!, assistantId, ev);
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        setMessagesByConv((m) => {
          const list = m[convId!] ?? [];
          return {
            ...m,
            [convId!]: list.map((x) =>
              x.id === assistantId ? { ...x, interrupted: true } : x,
            ),
          };
        });
      } else {
        // 普通错误: 渲染到消息
        applyEvent(convId!, assistantId, {
          type: "error",
          code: "client_error",
          message: (e as Error).message,
        });
      }
    } finally {
      setStreamingConvId((cur) => (cur === convId ? null : cur));
      aborters.current[convId!] = null;
    }

    function applyEvent(cid: string, msgId: string, ev: ChatEvent) {
      setMessagesByConv((m) => {
        const list = m[cid] ?? [];
        return {
          ...m,
          [cid]: list.map((x) => {
            if (x.id !== msgId) return x;
            if (ev.type === "message") {
              return { ...x, content: x.content + ev.delta };
            }
            if (ev.type === "message_end") {
              return { ...x, citations: ev.citations };
            }
            if (ev.type === "thinking") {
              const t = [...(x.thinking ?? []), { node: ev.node, status: ev.status, detail: ev.detail }];
              return { ...x, thinking: t };
            }
            if (ev.type === "error") {
              return { ...x, content: x.content + `\n\n[错误] ${ev.code}: ${ev.message}` };
            }
            // workflow_done / done: 不修改
            return x;
          }),
        };
      });
    }
  }, [currentId, persistConv]);

  const handleStop = useCallback(() => {
    if (streamingConvId) {
      aborters.current[streamingConvId]?.abort();
    }
  }, [streamingConvId]);

  const currentMessages = currentId ? messagesByConv[currentId] ?? [] : [];
  const isStreaming = streamingConvId !== null;

  return (
    <div className="flex h-[calc(100vh-8rem)] w-full" data-testid="chat-shell">
      <ConversationList
        conversations={conversations}
        currentId={currentId}
        onSelect={handleSelect}
        onCreate={handleNew}
        onDelete={handleDelete}
      />
      <div className="flex flex-1 flex-col">
        <MessageList
          messages={currentMessages}
          streamingMessageId={isStreaming ? "current" : undefined}
        />
        <Composer
          onSend={handleSend}
          onStop={handleStop}
          streaming={isStreaming}
          disabled={false}
        />
      </div>

      <AlertDialog open={pendingDeleteId !== null} onOpenChange={(o) => !o && setPendingDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除会话?</AlertDialogTitle>
            <AlertDialogDescription>
              该会话的所有消息将被永久删除, 不可恢复.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground">
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

- [ ] **Step 4: 跑测试**

Run: `cd web && bun run test -- ChatShell.test`
Expected: 6 PASS (可能 1-2 个调整)

- [ ] **Step 5: 跑 typecheck + lint**

Run: `cd web && bun run typecheck && bun run lint`
Expected: 无错

- [ ] **Step 6: 提交**

```bash
git add web/components/chat/ChatShell.tsx web/components/chat/ChatShell.test.tsx
git commit -m "feat(chat): ChatShell 状态机 (流按 conv 隔离 + 停止 + 删除 + 草稿)"
```

---

## Task 6.3: PR 6 验证

- [ ] **Step 1: 跑全量**

```bash
cd web && bun run test && bun run typecheck && bun run lint
```

Expected: 全过

- [ ] **Step 2: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 2 个新 commit (T6.1 List / T6.2 Shell)

下一步: PR 7 — `/chat` page 接入 nav + Playwright E2E。

---

# PR 7 · `/chat` 页面 + Nav + Playwright E2E

**PR 目标**: 新建 `app/chat/page.tsx` 挂 `ChatShell`, 顶 nav 加 Chat 链接, Playwright 端到端走通"输入 → 流 → 引用 → 切回历史"。

---

## Task 7.1: 顶 nav 加 Chat 链接

**Files:**
- Modify: `web/app/layout.tsx`

- [ ] **Step 1: 改 nav**

在现有 `<NavLink href="/knowledge">Knowledge</NavLink>` 后面加:

```tsx
<NavLink href="/chat">Chat</NavLink>
```

- [ ] **Step 2: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错

- [ ] **Step 3: 提交**

```bash
git add web/app/layout.tsx
git commit -m "feat(chat): 顶 nav 加 /chat 链接"
```

---

## Task 7.2: `app/chat/page.tsx` + 单测

**Files:**
- Create: `web/app/chat/page.tsx`
- Create: `web/app/chat/page.test.tsx`

- [ ] **Step 1: 写 page**

`web/app/chat/page.tsx`:

```tsx
// 智能体聊天主页 (2026-06-09)
// 把 ChatShell 当 client island 挂进来; hero 装饰走 editorial 风格
import { ChatShell } from "@/components/chat/ChatShell";
import { Reveal, Stagger, StaggerItem } from "@/components/ui/animated";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <Stagger className="space-y-3" delay={0.08}>
        <StaggerItem>
          <div className="flex items-center gap-3">
            <span className="eyebrow">外网用户 · 智能体对话</span>
            <span className="h-px flex-1 bg-border" />
          </div>
        </StaggerItem>
        <StaggerItem>
          <h1 className="display text-5xl italic tracking-tight md:text-6xl">
            跟产品智能体聊聊<span className="text-clay">.</span>
          </h1>
        </StaggerItem>
        <StaggerItem>
          <p className="max-w-2xl text-base text-muted-foreground">
            选型 / 报价 / 故障排查. 多会话管理, 引用文档可追溯.
          </p>
        </StaggerItem>
      </Stagger>

      <Reveal delay={0.2}>
        <ChatShell />
      </Reveal>
    </div>
  );
}
```

- [ ] **Step 2: 写最小单测 (验证页面能 mount, 渲染 ChatShell)**

`web/app/chat/page.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// mock ChatShell, 因为它内部状态机太复杂, page 层只测集成
vi.mock("@/components/chat/ChatShell", () => ({
  ChatShell: () => <div data-testid="chat-shell-mock">shell</div>,
}));

import ChatPage from "./page";

describe("ChatPage", () => {
  it("mount 渲染 ChatShell + 标题", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("chat-shell-mock")).toBeInTheDocument();
    expect(screen.getByText(/跟产品智能体聊聊/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 跑测试 + typecheck**

Run: `cd web && bun run test -- page.test && bun run typecheck`
Expected: 1 PASS, typecheck 无错

- [ ] **Step 4: 提交**

```bash
git add web/app/chat/page.tsx web/app/chat/page.test.tsx
git commit -m "feat(chat): /chat 页面挂 ChatShell + 单测"
```

---

## Task 7.3: Playwright E2E

**Files:**
- Create: `web/e2e/chat.spec.ts`

- [ ] **Step 1: 写 E2E**

`web/e2e/chat.spec.ts`:

```ts
// /chat 端到端 (2026-06-09)
// 起 next dev, mock /api/chat/messages SSE, 走通主流程
import { test, expect } from "@playwright/test";

test.describe("chat page", () => {
  test.beforeEach(async ({ page }) => {
    // mock /api/chat/messages, 返一段流
    await page.route("**/api/chat/messages", async (route) => {
      const events = [
        { type: "message", delta: "你好" },
        { type: "message", delta: ", 请问" },
        { type: "message_end", conversationId: "mock-conv", citations: [] },
        { type: "done" },
      ];
      const body = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("") + "data: [DONE]\n\n";
      await route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body,
      });
    });
  });

  test("打开 /chat 显示左右栏 + 输入框", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByTestId("new-conv")).toBeVisible();
    await expect(page.getByTestId("composer-textarea")).toBeVisible();
  });

  test("输入 → 发送 → 流过来渲染", async ({ page }) => {
    await page.goto("/chat");
    await page.getByTestId("composer-textarea").fill("1LE 电机?");
    await page.getByTestId("composer-textarea").press("Enter");
    await expect(page.getByText("你好, 请问")).toBeVisible({ timeout: 5000 });
  });

  test("新对话 → 输入 → 切回旧对话保留历史", async ({ page }) => {
    await page.goto("/chat");

    // 第一个会话
    await page.getByTestId("composer-textarea").fill("Q1");
    await page.getByTestId("composer-textarea").press("Enter");
    await expect(page.getByText("你好, 请问")).toBeVisible();

    // 新对话
    await page.getByTestId("new-conv").click();
    await expect(page.getByTestId("composer-textarea")).toBeVisible();

    // 切回第一个 (按 conv-id 找第一个条目)
    const items = page.locator("[data-testid^='conv-']");
    await items.first().click();
    await expect(page.getByText("你好, 请问")).toBeVisible();
  });
});
```

- [ ] **Step 2: 跑 E2E**

```bash
# 终端 1: 起 dev
cd web && bun run dev

# 终端 2: 跑 playwright (确保 playwright 浏览器已装, `bunx playwright install`)
cd web && bun run test:e2e -- chat.spec
```

Expected: 3 PASS

- [ ] **Step 3: 提交**

```bash
git add web/e2e/chat.spec.ts
git commit -m "test(chat): Playwright E2E (输入/流/切回历史)"
```

---

## Task 7.4: PR 7 验证

- [ ] **Step 1: 跑全量**

```bash
cd web && bun run test && bun run typecheck && bun run lint
```

Expected: 全过

- [ ] **Step 2: 起 dev server 手测**

```bash
cd web && bun run dev
# 浏览器: http://localhost:3000/chat
```

预期: 看到左右栏, 输入消息 + 发送 (凭据未配会返 500, UI 弹错误; 配了 dify 凭据则正常流)

- [ ] **Step 3: 验证 git log**

Run: `git log --oneline | head -10`
Expected: 看到 3 个新 commit (T7.1 nav / T7.2 page / T7.3 e2e)

下一步: PR 8 — middleware 内外网分流 + 部署文档。

---

# PR 8 · middleware + 部署文档 + 收尾

**PR 目标**: 加 `app/middleware.ts`, `CHAT_PUBLIC_MODE=true` 时非 `/chat*` 全部 404, 防攻击者扫描后台。写部署文档, 让运维知道怎么配 env + nginx。

---

## Task 8.1: `app/middleware.ts` + 单测

**Files:**
- Create: `web/app/middleware.ts`
- Create: `web/app/middleware.test.ts`

- [ ] **Step 1: 写红测试**

`web/app/middleware.test.ts`:

```ts
// middleware 测试: CHAT_PUBLIC_MODE=true 时非 /chat* 全部 404
// 跟 ChatShell 等 UI 组件不同, middleware 是 server-side, 用 Next.js 测试模式
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { middleware } from "./middleware";
import { NextRequest } from "next/server";

function req(path: string): NextRequest {
  return new NextRequest(new Request(`http://localhost${path}`));
}

describe("middleware", () => {
  const ORIGINAL = process.env.CHAT_PUBLIC_MODE;

  beforeEach(() => {
    process.env.CHAT_PUBLIC_MODE = "true";
  });
  afterEach(() => {
    if (ORIGINAL === undefined) delete process.env.CHAT_PUBLIC_MODE;
    else process.env.CHAT_PUBLIC_MODE = ORIGINAL;
  });

  it("公网模式 + /chat 放行", async () => {
    const res = await middleware(req("/chat"));
    expect(res?.status).not.toBe(404);
  });

  it("公网模式 + /api/chat 放行", async () => {
    const res = await middleware(req("/api/chat/messages"));
    expect(res?.status).not.toBe(404);
  });

  it("公网模式 + / 返回 404", async () => {
    const res = await middleware(req("/"));
    expect(res?.status).toBe(404);
  });

  it("公网模式 + /knowledge 返 404", async () => {
    const res = await middleware(req("/knowledge"));
    expect(res?.status).toBe(404);
  });

  it("公网模式 + /api/knowledge 返 404", async () => {
    const res = await middleware(req("/api/knowledge/stats"));
    expect(res?.status).toBe(404);
  });
});

describe("middleware (内网模式)", () => {
  beforeEach(() => {
    process.env.CHAT_PUBLIC_MODE = "false";
  });

  it("内网模式 + 任何路径都放行 (NextResponse.next)", async () => {
    const res = await middleware(req("/anything"));
    // NextResponse.next() 返 undefined 或 200; 都算放行
    expect(res === undefined || res.status === 200).toBe(true);
  });
});
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd web && bun run test -- middleware.test`
Expected: 全 FAIL — `Cannot find module './middleware'`

- [ ] **Step 3: 实现 middleware**

`web/app/middleware.ts`:

```ts
// 内外网路径分流 middleware (2026-06-09)
// 部署期 CHAT_PUBLIC_MODE=true 启用: 非 /chat* 全部 404, 防攻击者扫描后台
// 内网模式: 放行所有 (跟现状一致)
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/chat", "/api/chat"];

export function middleware(req: NextRequest): NextResponse | undefined {
  if (process.env.CHAT_PUBLIC_MODE !== "true") {
    return undefined;  // 内网模式: 放行
  }
  const { pathname } = req.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (isPublic) return undefined;  // 放行
  return new NextResponse("Not Found", { status: 404 });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 4: 跑测试**

Run: `cd web && bun run test -- middleware.test`
Expected: 7 PASS

- [ ] **Step 5: 跑 typecheck**

Run: `cd web && bun run typecheck`
Expected: 无错

- [ ] **Step 6: 提交**

```bash
git add web/app/middleware.ts web/app/middleware.test.ts
git commit -m "feat(chat): middleware 内外网分流 (CHAT_PUBLIC_MODE=true 启 404 兜底)"
```

---

## Task 8.2: 部署文档 `docs/chat-deployment.md`

**Files:**
- Create: `docs/chat-deployment.md`

- [ ] **Step 1: 写文档**

```markdown
# 智能体聊天界面 部署指南

> 创建于 2026-06-09

## 概述

`/chat` 路由同时支持内网调试 + 公网暴露, 用 **单一 next 实例 + nginx 路径分流** + Next.js middleware 兜底。零额外服务, 跟现有 web/ 共享端口。

## 架构

```
                  ┌──── 内网 (10.x.x.x) ────┐
nginx ──── /  ────►  next  ─── /decode
                  │          ─── /output
                  │          ─── /knowledge
                  │          ─── /api/knowledge/*
                  │          ─── /chat
                  │          ─── /api/chat/*
                  │
                  └──── 公网 (暴露 /chat) ─┐
                  │          ─── /chat
                  │          ─── /api/chat/*
```

`CHAT_PUBLIC_MODE=true` 时, middleware 把非 `/chat*` 一律 404。攻击者即使知道 next 存在, 也猜不到后台路径。

## Nginx 片段

```nginx
server {
    listen 443 ssl;
    server_name your.domain;

    # 静态资源直发
    location /_next/static/ {
        proxy_pass http://127.0.0.1:3000;
    }

    # SSE 必须关 buffer
    location /api/chat/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;  # 长连接
        proxy_set_header Connection '';
        proxy_http_version 1.1;
    }

    # 公网用户只看 /chat
    location /chat {
        proxy_pass http://127.0.0.1:3000;
    }

    # 内网入口
    location / {
        allow 10.0.0.0/8;       # 内网白名单 (按需改)
        deny all;
        proxy_pass http://127.0.0.1:3000;
    }

    # rate limit
    limit_req_zone $binary_remote_addr zone=chat:10m rate=10r/s;
    location /api/chat/ {
        limit_req zone=chat burst=20 nodelay;
        # ... 上面 SSE 配
    }
}
```

## 必配 env

| 变量 | 用途 | 出 bundle? |
|---|---|---|
| `DIFY_API_KEY` | Dify 后台 API 密钥 | ❌ server only |
| `DIFY_API_URL` | Dify 服务地址 (自部署改) | ❌ |
| `DIFY_CHATFLOW_APP_ID` | dify 应用 16 位 hash | ❌ |
| `CHAT_PROVIDER` | 工厂开关 (v1=`dify`) | ❌ |
| `CHAT_PUBLIC_TOKEN` | 公网 anti-abuse (前端读下面的 NEXT_PUBLIC_ 版) | ❌ |
| `NEXT_PUBLIC_CHAT_TOKEN` | 同上, 前端发 `x-chat-token` 头 | ✅ |
| `CHAT_PUBLIC_MODE` | middleware 开关 (公网部署=`true`) | ❌ |

**关键安全约束**:
- `DIFY_API_KEY` **永远**不加 `NEXT_PUBLIC_` 前缀, 否则进前端 bundle 等于公开
- `CHAT_PUBLIC_TOKEN` 不是私钥; 仅防最笨爬虫; nginx rate limit 是主防线
- 公网部署期 `CHAT_PUBLIC_MODE=true`, 否则攻击者可扫到后台

## Dify 后台配置

1. 创建 **Chatflow** (聊天助手) 类型应用
2. 编排工作流 (知识检索 + LLM 节点, 按需)
3. 发布, 拿到 **API 访问** 的密钥 (格式 `app-xxx`)
4. URL 末段 16 位 hash 就是 `DIFY_CHATFLOW_APP_ID`
5. 开启"自动生成会话标题" (默认)

## 端到端验证清单

部署后逐项过:

- [ ] `curl http://localhost:3000/api/chat/messages` 返 401 (无 token)
- [ ] `curl -H "x-chat-token: $CHAT_PUBLIC_TOKEN" -d '{...}' /api/chat/messages` 返 SSE 流
- [ ] 浏览器打开 `/chat`, 输入消息, 看到流式打字效果
- [ ] 引用块可展开, 看到文档名 + score
- [ ] 思考过程可展开, 看到节点进度
- [ ] 停止按钮真能停 (fetch 中断)
- [ ] 刷新页面后历史会话还在 (localStorage)
- [ ] 公网模式下, 浏览器访问 `/` 看到 404

## 已知限制

- v1 localStorage 持久化: 换浏览器/清缓存 = 丢历史
- 无后端账号: 防滥用靠 nginx rate limit
- 不支持图片/文件上传 (v2)
```

- [ ] **Step 2: 提交**

```bash
git add docs/chat-deployment.md
git commit -m "docs(chat): 部署指南 (nginx/env/dify 配置/验证清单)"
```

---

## Task 8.3: 全量打磨 + 最终验证

- [ ] **Step 1: 跑后端全量测试 (无新增, 确认无回归)**

```bash
cd web && bun run test
```

Expected: 全过 (含 PR 1-7 全部测试)

- [ ] **Step 2: 跑 typecheck + lint + format check**

```bash
cd web && bun run typecheck && bun run lint && bun run format:check
```

Expected: 全过 (如有 format 差异, 跑 `bun run format` 修一遍)

- [ ] **Step 3: 起 dev server, 端到端手测 3 个核心场景**

```bash
cd web && bun run dev
# 1. 打开 /chat → 看到左右栏
# 2. 点新对话 → 输入 → 凭据未配时看到 error toast (预期, 不算崩)
# 3. 配 DIFY 凭据后真发消息 → 看到打字效果 + 引用
```

- [ ] **Step 4: 跑 Playwright E2E**

```bash
cd web && bun run test:e2e
```

Expected: 3 PASS

- [ ] **Step 5: 验证 git log 完整**

Run: `git log --oneline | head -20`
Expected: 看到 PR 1-8 所有 commit, 大约 19 个新提交

- [ ] **Step 6: 写 PR 8 总结 commit**

```bash
git commit --allow-empty -m "feat(chat): /chat 路由 + 智能体对话 v1 完整交付

PR 1: 工具链 (shadcn 3 组件) + types + factory + env
PR 2: DifyChatProvider + 8 种 SSE 归一化
PR 3: /api/chat/messages 鉴权 + zod + SSE 转发
PR 4: localStorage 会话 CRUD
PR 5: MessageBubble/Composer/CitationPanel/ThinkingTrace/MessageList
PR 6: ConversationList + ChatShell 状态机
PR 7: /chat page + nav + Playwright E2E
PR 8: middleware 内外网分流 + 部署文档

未实现 (v2 候选): 多模态 (图片/文件), 重命名, 分享, 多语言, 健康检查"
```

---

## 整体回顾

8 个 PR 总计:

| 模块 | 文件数 | 测试数 (估) |
|---|---|---|
| `lib/chat/{types,factory,dify,storage}.ts` | 4 | 30+ |
| `app/api/chat/messages/route.ts` | 1 | 6 |
| `components/chat/*` | 7 | 17+ |
| `app/chat/page.tsx` | 1 | 1 |
| `app/middleware.ts` | 1 | 7 |
| `e2e/chat.spec.ts` | 1 | 3 |
| 部署文档 | 1 | n/a |
| **合计** | **16** | **64+** |

每 PR 独立可测, 跑 `cd web && bun run test && bun run typecheck && bun run lint` 全绿。`/chat` 路由在任何 PR 后都允许 disabled (默认 `CHAT_PUBLIC_MODE=false` 兜底)。

下一步: 进入执行。
