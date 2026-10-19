# P4 维度 ④ 函数式写法 — Agent D (lib/ + const/ + i18n/ + scripts/)

**审计日期**: 2026-06-28
**范围**: `packages/web/lib/` (~70 文件) + `packages/web/const/` + `packages/web/i18n/` + `packages/web/scripts/`
**已装 FP 库**: `es-toolkit ^1.48.1` (全项目仅 1 处使用: `lib/chat/migration.ts:10`)
**未装**: Ramda / lodash / fp-ts

---

## 1. 扫描概览

| 维度 | 数值 |
| --- | --- |
| 总扫描文件 | **~75** (lib 子目录 70 + const 1 + i18n 5 + scripts 2) |
| 已正确使用 FP 模式的位置 | **8** (chat-utils / dify / memory-integration / motion / theme / buyer-profile / log) |
| 已识别但无需重构的位置 | **6** (factory switch / use-chat-state hooks / auth cache / utils.ts) |
| 🔴 高 ROI 建议重写 | **2** (净省 ~30 行 + 单点修改价值) |
| 🟡 中 ROI 可选 | **4** (净省 ~35 行，类型推导与风险需权衡) |
| 🟢 低 ROI / ❌ 不建议 | 多数 |

---

## 2. 已正确使用 FP 模式（不要重复建议）

### 2.1 `lib/chat/migration.ts` — 唯一用 es-toolkit 的地方（样板）
```typescript
import { groupBy } from "es-toolkit";
messages_by_conv: groupBy(messages, (msg) => msg.conversationId ?? "")
```
**优点**: es-toolkit `groupBy` 是 O(n) + 类型推导，完胜手写 reduce。
**对比**: `lib/chat/storage.ts:75-86` 用手写 for-of 累加实现同样功能（idx-based 累加），可考虑迁移。

### 2.2 `lib/chat/dify.ts:87-128` — switch dispatcher（已合理）
P3 §11.3 已识别：`normalize()` 把每个 case 抽成独立 generator (`normalizeMessage` / `normalizeMessageEnd` / ...)，复杂度从 30 降到 ~5。**switch 在 case ≥ 6 + 每个 case 独立逻辑时保持合理**（查表 dispatch 的边界收益被 generator 闭包抵消）。

### 2.3 `lib/chat/chat-utils.ts:30-55` — 纯函数风格（已合理）
`computeEffectiveConversations` / `getNextConversationId` / `newId` 全部是纯函数，参数化对话列表返回新数组。**这是 FP 化的样板**，其他模块应参考（保持小颗粒纯函数）。

### 2.4 `lib/api/config.ts:84-93, 99-117` — 内部函数式纯化（已合理）
`resolveUrl` / `serializeRequest` / `parseErrorDetail` / `parseResponseBody` 都是纯函数 (string→string + object→headers) + 单一职责 + 内部 helper。`apiFetch` 顶层是 facade 但内部已 FP 化。

### 2.5 `lib/motion.ts` — 配置 + 工厂函数（已合理）
`stagger(delay) => variant`、`rowStagger(delay) => variant` 是典型 FP 风格：参数化 → 返回新对象。**适合 use-motion 抽象**。

### 2.6 `lib/theme/themes.ts:71-77` — `getThemeConfig` 查表（已合理）
`themes.find(entry => entry.name === name)` 是单行表达式查找，比 Record 字典更合适（只有 2 个主题，索引建表浪费）。

### 2.7 `lib/buyer-profile/hooks.ts` — TanStack Query 标准化封装（已合理）
所有 hook 都是单一职责 + queryKey + staleTime 约定。**已用 RQ factory 模式**，无进一步 FP 机会。

### 2.8 `lib/log.ts` — 闭包 + 字典查表（已合理）
```typescript
const COLOR_BY_LEVEL: Record<Level, string> = { debug: ..., error: ..., info: ..., warn: ... };
```
**教科书级查表 dispatch**，level→color 一行表达。

---

## 3. 🔴 高 ROI（建议重写）— 2 处

### 3.1 `lib/api/query-client.ts:17-25` + 多处重复的 `errorMessage(error: unknown)` — 抽统一 helper + 复用

**问题**: 5 处定义基本同形的 `errorMessage(error: unknown)`:

| 文件 | 行号 | 形态 | 是否导出 |
| --- | --- | --- | --- |
| `lib/api/query-client.ts:17-25` | 17-25 | `if ApiError/NetworkError → .message; if Error → .message; else String(error)` | ❌ private |
| `lib/api/config.ts:43` | 43 | `error instanceof Error ? error.message : String(error)` (inline) | — |
| `lib/api/ingest.ts:72-76` | 72-76 | `if Error → message; else String` (inline, 包 NetworkError) | — |
| `lib/api/rsc-queries.ts:58` | 58 | `error instanceof Error ? error.message : String(error)` (inline) | — |
| `lib/api/chat.ts:36` | 36 | `new Error(`chat api ${res.status}: ${text}`)` (包 fetch 错误) | — |
| `lib/dify-datasets.ts:57` | 57 | `new DifyApiError(res.status, text)` (包 fetch 错误) | — |
| `app/admin/invites/_components/admin-invites-table.tsx:31` | 31 | `getErrorMessage(error)` 组件内 helper | — |
| `app/admin/dicts/_components/dict-item-create-dialog.tsx:35` | 35 | `getErrorMessage(err, translate)` 组件内 helper | — |
| `app/evaluate/new/_components/evaluate-new-form.tsx:67` | 67 | `getErrorMessage(error)` 组件内 helper | — |
| `components/common/form/app-field.tsx:78` | 78 | `getErrorMessage(rawError)` 组件内 helper | — |

**重复估算**: 5 处 lib/api 内 + 4 处组件内 = **9 处重复 helper**，平均 5-10 行/处 = **45-90 行重复**。

**当前 `lib/api/query-client.ts:17-25` 已经是最完整版本**（区分 ApiError/NetworkError/Error/fallback），但 **未导出**。

**建议重构**:

```typescript
// lib/api/errors.ts (新增)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof ApiError || error instanceof NetworkError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
};
```

**调用方简化**:
```typescript
// lib/api/config.ts:43-44 (旧)
const errorMessageText = error instanceof Error ? error.message : String(error);
throw new NetworkError(errorMessageText);
// ↓ 重构后
throw new NetworkError(getErrorMessage(error));

// lib/api/rsc-queries.ts:58 (旧)
const msg = error instanceof Error ? error.message : String(error);
log.warn(`[prefetchQuery] 失败 ${path}: ${msg}`);
// ↓ 重构后
log.warn(`[prefetchQuery] 失败 ${path}: ${getErrorMessage(error)}`);

// lib/api/ingest.ts:69-77 (旧)
let errorMessage: string;
if (error instanceof Error) {
  errorMessage = error.message;
} else {
  errorMessage = String(error);
}
throw new NetworkError(errorMessage);
// ↓ 重构后
throw new NetworkError(getErrorMessage(error));
```

**额外价值**: 4 处组件内 helper 也可以 import `getErrorMessage`：
- `app/admin/invites/_components/admin-invites-table.tsx:31`
- `app/admin/dicts/_components/dict-item-create-dialog.tsx:35` (传 translate 是另一回事 — 单独处理)
- `app/evaluate/new/_components/evaluate-new-form.tsx:67`
- `components/common/form/app-field.tsx:78`

**ROI 评估**:
- **净省代码**: lib/api 内 3 处 × ~5 行 + 组件内 3 处 × ~5 行 = **~30 行**
- **单点修改价值**: 错误归一化策略只改 1 处（比如未来要支持 Error.cause 链追溯）
- **风险**: 🟢 低（纯函数，行为不变，仅集中）
- **类型安全**: ✅ 不影响（unknown → string 已是标准）

**判定**: 🔴 **强烈建议**

---

### 3.2 `lib/api/ingest.ts:79-95` — 重复 `parseErrorDetail` 逻辑抽 helper

**问题**: `lib/api/config.ts:123-134` 已有 `parseErrorDetail(res)` helper，**但 ingest.ts:79-95 因为走 apiProxy() 而非 apiFetch()，必须自己实现一遍**:

```typescript
// lib/api/ingest.ts:79-95 (旧)
if (!res.ok) {
  const text = await res.text().catch(() => "");
  let detail: string;
  try {
    const body = JSON.parse(text);
    if (typeof body === "object" && body && "detail" in body) {
      detail = String(body.detail);
    } else {
      detail = res.statusText;
    }
  } catch {
    detail = res.statusText;
  }
  throw new ApiError(res.status, detail);
}
```

vs `lib/api/config.ts:123-134`:
```typescript
const parseErrorDetail = async (res: Response): Promise<string> => {
  const text = await res.text().catch(() => "");
  try {
    const body = JSON.parse(text);
    if (typeof body === "object" && body && "detail" in body) {
      return String(body.detail);
    }
  } catch {
    // 非 JSON, 走 statusText
  }
  return res.statusText;
};
```

**完全同形**，只是 ingest.ts 把 `return` 换成了 `detail =`。**ingest.ts 12 行 vs config.ts 10 行**。

**建议重构**: `parseErrorDetail` 从 `lib/api/config.ts` **export**（现为 private），ingest.ts 复用：

```typescript
// lib/api/config.ts:123
// 旧: const parseErrorDetail = ...
// ↓ 重构后
export const parseErrorDetail = async (res: Response): Promise<string> => { ... };

// lib/api/ingest.ts:79-95 (旧) → (新)
if (!res.ok) {
  throw new ApiError(res.status, await parseErrorDetail(res));
}
```

**ROI 评估**:
- **净省代码**: ingest.ts 省 10 行 + config.ts 加 export 1 行 = **净省 ~9 行**
- **单点修改价值**: detail 解析策略只改 1 处
- **风险**: 🟢 低（纯函数 + 已实现）

**判定**: 🔴 **强烈建议**（与 3.1 配套 — 都是 lib/api 错误处理统一化）

---

## 4. 🟡 中 ROI（可选）— 4 处

### 4.1 `lib/chat/chat-utils.ts:137-160` — `applyEvent` 的 ev.type 分支改对象 dispatch

**当前** (line 137-160):
```typescript
state.setMessagesByConv((msgs) => {
  const list = msgs[cid] ?? [];
  const updated = list.map((msg) => {
    if (msg.id !== msgId) return msg;
    if (ev.type === "message") {
      return { ...msg, content: msg.content + ev.delta };
    }
    if (ev.type === "thinking") {
      const thinking = [...(msg.thinking ?? []), { detail: ev.detail, node: ev.node, status: ev.status }];
      return { ...msg, thinking };
    }
    if (ev.type === "error") {
      return { ...msg, content: `${msg.content}\n\n[${ev.code}] ${ev.message}` };
    }
    return msg;
  });
  deps.persistMessages(cid, updated);
  return { ...msgs, [cid]: updated };
});
```

**问题**: 3 个 if 链 + 一个 fall-through `return msg`。扩展性差：加新 event type 需改 map 内部 + 加 return 分支。

**对象 dispatch 改法**:
```typescript
type MessageEvent = Extract<ChatEvent, { type: "message" | "thinking" | "error" }>;
const MESSAGE_UPDATERS: Record<MessageEvent["type"], (msg: Message, ev: MessageEvent) => Message> = {
  message:  (msg, ev) => ({ ...msg, content: msg.content + ev.delta }),
  thinking: (msg, ev) => ({
    ...msg,
    thinking: [...(msg.thinking ?? []), { detail: ev.detail, node: ev.node, status: ev.status }],
  }),
  error:    (msg, ev) => ({ ...msg, content: `${msg.content}\n\n[${ev.code}] ${ev.message}` }),
};
// 用法:
const updater = MESSAGE_UPDATERS[ev.type as MessageEvent["type"]];
const updated = list.map((msg) => (msg.id === msgId && updater ? updater(msg, ev as MessageEvent) : msg));
```

**ROI 评估**:
- **净省代码**: 现状 12 行 → 重构后 13 行 = **净 +1 行**（但加新 type 只改 1 处）
- **可读性**: 三个分支独立纯函数，易测试
- **风险**: 🟡 中（需要正确收窄 discriminated union；ev 在 updater 中需要 type-guard）

**判定**: 🟡 **中 ROI**（P3 §11.1 已识别）— 行数差不多但**扩展性 + 测试性显著提升**。**值得做**。

---

### 4.2 `lib/chat/chat-utils.ts:416-442` — `processStream` + `handleStreamError` 事件流可考虑 pipe

**当前** (line 416-442):
```typescript
export const processStream = async ({...}): Promise<void> => {
  try {
    for await (const ev of parseSseStream(stream, ac.signal)) {
      applyEvent({ cid: convId, deps, ev, msgId: assistantId, state });
    }
  } catch (error) {
    handleStreamError({ assistantId, convId, error, deps, state });
  } finally {
    cleanup?.();
  }
};
```

**pipe 视角**: 数据流 `sseStream → events → applyEvent(state)`。可考虑：
```typescript
// 概念性 pipe:
await pipe(
  parseSseStream(stream, ac.signal),
  forEachAsync((ev) => applyEvent({ ..., ev, ... })),
).catch((error) => handleStreamError({ ..., error, ... }));
```

**ROI 评估**:
- **净省代码**: 当前 9 行 → pipe 版 5 行 = **净省 4 行**
- **可读性**: 数据流方向更清晰（`parseSseStream → applyEvent`）
- **风险**: 🟡 中（需要引入 es-toolkit `pipe` 或自实现；async generator + 错误处理需要适配）

**判定**: 🟡 **中 ROI，谨慎评估**。AsyncIterable pipe 模式有跨 polyfill 兼容问题（abort signal 透传），且当前 for-await 已足够清晰。**保持现状**更稳。

---

### 4.3 `lib/parse/parse-{eval-csv,excel,json}.ts` — curry 公共参数机会（弱）

**问题**: 3 个解析器各自独立函数：
- `parseEvalCsv(file: File)` — 无公共参数
- `parseExcelBuffer(buf: ArrayBuffer)` — 无公共参数
- `parseJsonText(text: string)` — 无公共参数

**P3 已识别**: 签名差异大（async File / sync ArrayBuffer / sync text），**强抽接口牺牲类型推导**。

**FP 角度**: 用 curry 提取公共参数（如 maxRows / encoding）…但 3 个解析器的"公共参数"语义不同：
- CSV: maxRows（已 hardcode 200 在内部）
- Excel: 无
- JSON: 无

**结论**: 抽不出真正的公共参数。**不建议改**。

**ROI**: ❌ 净增代码（必须先抽 parameter interface，再 curry）。

---

### 4.4 `lib/hooks/use-lookup.ts:44` — `Object.fromEntries(items.map(...))` 可考虑 `keyBy`

**当前** (line 44):
```typescript
const byKey = Object.fromEntries(items.map((item) => [item.key, item])) as Record<string, LookupItem>;
```

**es-toolkit 改法**:
```typescript
import { keyBy } from "es-toolkit";
const byKey = keyBy(items, (item) => item.key);
```

**ROI 评估**:
- **净省代码**: 1 行 → 1 行 = **净 0 行**
- **可读性**: 🟢 +1（更直白表达意图）
- **类型推导**: ✅ 不变
- **风险**: 🟢 低

**判定**: 🟡 **低收益，建议顺带改**（与 groupBy 形成一致的 es-toolkit 风格）。**单点改，可选**。

---

## 5. 🟢 低 ROI / ❌ 不建议 — 多数

### 5.1 `lib/chat/chat-utils.ts:94-135` — `applyEvent` 的 `message_end` 分支独立 if 不改 dispatch

**当前** (line 94): `if (ev.type === "message_end") { ... return; }` 是大块（含 `setConversations` + `persistAssistantToServer` 调 setMessagesByConv 套娃）。

**为什么不改**: 
- message_end 是单独 fast-path（提前 return），不走 map 更新分支
- 内部逻辑跨 `setMessagesByConv` + `setConversations` 双 setState + `persistMessages` + `persistAssistantToServer`，**单一 case 难抽成纯函数**

**结论**: ❌ 不建议改 dispatch。

---

### 5.2 `lib/chat/use-chat-state.ts:185-198` — `msg.role === "system"` 改角色映射

**当前** (line 185-198):
```typescript
const adapted: Message[] = currentDetail.messages.map((msg) => {
  let role: "user" | "assistant" = "user";
  if (msg.role === "system") {
    role = "user";
  } else {
    ({ role } = msg);
  }
  return {
    content: msg.content,
    createdAt: Date.parse(msg.created_at),
    id: msg.id,
    role,
  };
});
```

**对象 lookup 改法**:
```typescript
const ROLE_ADAPTER: Record<"user" | "assistant" | "system", "user" | "assistant"> = {
  assistant: "assistant",
  system: "user",
  user: "user",
};
const adapted: Message[] = currentDetail.messages.map((msg) => ({
  content: msg.content,
  createdAt: Date.parse(msg.created_at),
  id: msg.id,
  role: ROLE_ADAPTER[msg.role],
}));
```

**ROI 评估**:
- **净省代码**: 14 行 → 8 行 = **净省 6 行**
- **可读性**: 🟢 +1（意图清晰）
- **风险**: 🟢 低

**判定**: 🟢 **低 ROI，可顺带改**。3 种角色变 2 种的语义非常清晰，未来加新角色类型时只改 Record。

---

### 5.3 `lib/chat/factory.ts:18-33` — switch-case 已合理（P3 已识别）

**当前**: switch 4 cases，default 抛错。P3 §11.2 已识别 — switch 在 case 数量 3-5 时等价甚至更清晰（typescript exhaustive 检查靠 switch）。

**判定**: ❌ 不改 dispatch。

---

### 5.4 `lib/store/{app,ui,auth}-store.ts` — zustand 已合理

P3 §6.1 已识别：抽 factory 净省 2 行但牺牲类型推导。

**判定**: ❌ 不动。

---

### 5.5 `lib/auth/permission.ts:26-43` — `getPermissions()` React cache 已合理

**判定**: ❌ 不动。React `cache()` 是 per-request 记忆化的最优解。

---

### 5.6 `lib/auth/role.ts` — 谓词已极简

```typescript
export const isAdminLevel = (user: UserLike | null | undefined): boolean =>
  user != null && user.role !== "user";
export const isSuperAdmin = (user: UserLike | null | undefined): boolean =>
  user?.role === "super_admin";
```

**判定**: ❌ 已是最简。`cond` chain 是 over-engineering（只有 2 个简单谓词）。

---

### 5.7 `lib/hooks/{use-confirm,use-dialog,use-pagination,use-polling,use-query-params,use-permissions}.ts` — 单一职责 hook

每个 5-30 行，纯 React 状态封装。**判定**: ❌ 已合理。

---

### 5.8 `lib/utils.ts` — `cn()` 已最简

```typescript
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
```

**vs es-toolkit**: es-toolkit 没有 cn 等价物（class-merge 是 shadcn 专有组合 clsx+twMerge）。

**判定**: ❌ 已合理。

---

### 5.9 `lib/dom/download.ts:6-25` — `triggerBrowserDownload` 已合理

副作用集中在一个函数（DOM 操作 + URL revoke），不可拆纯。

**判定**: ❌ 已合理。

---

### 5.10 `lib/chat/{dify,openai,memory-integration,storage,db,api,sse,types,index}.ts` — 业务核心

每个文件都是单一职责 + 类型契约 + 流式生成器。**判定**: ❌ 不动。

---

### 5.11 `lib/server/evaluate.ts:15-25` — `deleteRunById` 裸 fetch

**当前**:
```typescript
const resp = await fetch(`${API_BASE}/api/evaluate/runs/${encodeURIComponent(id)}`, {
  headers,
  method: "DELETE",
});
if (!resp.ok) {
  throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
}
return resp.json() as Promise<unknown>;
```

**问题**: 没走 `apiFetch()` + `parseErrorDetail` + `getErrorMessage` 统一处理。

**ROI**:
- 重构后用 `apiFetch<unknown>(url, { headers, method: "DELETE" })` 净省 ~5 行 + 错误归一
- 但是：注释明确说"server-only 直连后端不走 BFF"是有意设计

**判定**: 🟢 **可改但有架构考虑** — 改完用 `apiFetch` 而不是裸 fetch，统一错误处理；server 直连后端仍然成立（`apiFetch` 就是 transport，不强制走 BFF）。

---

### 5.12 `lib/api/{account,permissions,users,memory,invites}.ts` — `headers?: Record<string, string>` 签名重复

P3 §4.1 已识别：16+ 文件 × 重复的 `headers?` 签名。

**FP 视角**: 用 partial application 预绑定 headers:
```typescript
// 概念性 curry:
const apiFetchWithAuth = (headers: Record<string, string>) => <T>(path: string, init?: ApiFetchInit) =>
  apiFetch<T>(path, { ...init, headers });
```

**ROI**:
- 实际行数净省 ~30 行（每文件 1-2 行 boilerplate）
- 但调用方语法变 `apiFetchWithAuth(headers)(path, init)` 反而更绕

**判定**: ❌ 不建议 — 调用方语义更清晰（直接传 headers）。P3 中 ROI 评估为 🟡 中 ROI，**与 P3 结论对齐**。

---

### 5.13 `lib/api/{knowledge,buyer-profile,lookups,system,chat-share,health}.ts` — pure CRUD wrappers

每个文件都是 `apiFetch<T>(path, init)` 单行包装。**判定**: ❌ 不可压缩。

---

### 5.14 `lib/rate-limiter.ts:27-37` — `pruneExpired` 手写 for-of

**当前**:
```typescript
const pruneExpired = (): void => {
  if (store.size <= MAX_STORE_SIZE) return;
  const now = Date.now();
  for (const [entryKey, entryval] of store) {
    if (entryval.resetAt <= now) {
      store.delete(entryKey);
    }
  }
};
```

**ROI**: 7 行，手写清晰。es-toolkit 没有 `pruneMap` 专用 API。**判定**: ❌ 已合理。

---

### 5.15 `lib/evaluate/types.ts:4-11` — `EvaluationStatus` 字典

```typescript
export const EvaluationStatus = {
  Cancelled: "cancelled",
  Completed: "completed",
  Failed: "failed",
  Pending: "pending",
  Running: "running",
} as const;
```

**判定**: ❌ 已合理（CLAUDE.md §业务 enum 走 lookup 字典模块，符合规范）。

---

### 5.16 `const/index.ts` — 常量定义

纯配置，**判定**: ❌ 已合理。

---

### 5.17 `i18n/{routing,request,navigation,provider}.tsx` — next-intl 配置

**判定**: ❌ next-intl 官方约定，无 FP 改造空间。

---

### 5.18 `scripts/duplication-report.ts` — Node 工具脚本

**判定**: ❌ 工具脚本，单次跑，不优化。

---

## 6. ROI 总结

| 类别 | 数量 | 净省代码 | 备注 |
| --- | --- | --- | --- |
| 🔴 高 ROI | **2** | **~39 行** + 单点修改价值 | `getErrorMessage` 统一 + `parseErrorDetail` 复用 |
| 🟡 中 ROI | **4** | **~10 行** + 可读性 | `applyEvent` dispatch / pipe 评估 / keyBy / role adapter |
| 🟢 低 ROI | 2 | **~5 行** | 顺带改 |
| ❌ 不建议 | 多数 | 0 | lib/chat 业务核心 + zustand + cache + hooks 已合理 |

**真实可做的高 ROI 集中在 lib/api 错误处理统一化**（2 处合计 ~39 行）。其他多为可选优化。

---

## 7. 强烈推荐执行顺序

### ✅ 立即做（2 个 — 都是 lib/api 错误处理）

1. **`lib/api/errors.ts` 导出 `getErrorMessage(error: unknown)`** — 抽 `query-client.ts:17` 的现有 private helper，3 处 lib/api + 4 处组件复用
2. **`lib/api/config.ts` 导出 `parseErrorDetail(res)`** — `ingest.ts:79-95` 复用，省 10 行

### ⚠️ 谨慎评估（1-2 个 — lib/chat 业务核心）

3. **`lib/chat/chat-utils.ts:applyEvent` 的 ev.type dispatch**（4.1）— P3 §11.1 已识别，行数差不多但扩展性 + 测试性提升
4. **`lib/chat/use-chat-state.ts:185` role adapter**（5.2）— 净省 6 行，可顺带改

### ❌ 暂不做（风险 > 收益 或 已有合适模式）

- **lib/chat/factory.ts switch** — 当前 switch 合理
- **lib/parse/* curry** — 抽不出真公共参数
- **lib/store/* factory** — 净省 2 行但牺牲类型推导
- **lib/auth/permission.ts cache** — React cache 已是 per-request 记忆化最优
- **lib/hooks/* FP 化** — 已是单一职责 hook
- **lib/utils.ts cn** — shadcn 专有组合，es-toolkit 无等价
- **lib/dom/download.ts** — DOM 副作用集中

---

## 8. 关键洞察

1. **lib/api 错误处理是最真实的高 ROI 集中区** — `getErrorMessage` + `parseErrorDetail` 抽 2 个 helper + 复用，可净省 ~39 行 + 单点修改价值。这是本审计**最推荐的 2 处重写**。

2. **lib/chat/chat-utils.ts 已是 FP 化的样板** — `applyEvent` / `computeEffectiveConversations` / `getNextConversationId` / `newId` / `ensureConversation` / `initMessages` / `setupAbortController` 全部是纯函数 + 显式 deps/state 参数注入。**这是项目最接近"FP 风格"的模块**，其他模块可参考。

3. **项目对 es-toolkit 使用极度保守**（仅 1 处）— 这与 CLAUDE.md §优先使用 es-toolkit 的强制要求**有偏差**。建议在 `lib/chat/migration.ts` 已建立的 groupBy 模板基础上，**至少把 `keyBy` 推到 use-lookup.ts**（5.4），保持渐进迁移。

4. **对象 dispatch vs switch 已合理分工** — `chat-utils.ts:applyEvent` 的 3 个 if 是真机会（4.1 🟡），`dify.ts:normalize()` 的 switch 已合理（2.2），`factory.ts` 的 switch 已合理（5.3）。**判断标准是"case 内逻辑是否独立纯函数"**。

5. **P3 模式报告与 P4 FP 报告协同** — P3 识别的 `headers?` 签名重复（5.12）在 FP 视角下"用 curry 也不划算"，与 P3 "净省 2 行不值得" 结论**完全对齐**。P3 识别的 `applyEvent` if 链（4.1）在 FP 视角下"行数差不多但扩展性提升"，与 P3 "高 ROI" 结论**部分升级**。

6. **P3 的"chat-message-persistence"代码已成 FP 样板** — `persistAssistantToServer` / `persistUserToServer` (chat-utils.ts:458-506) 是纯函数 + 接收 deps 作为参数，是 `use-chat-state.ts` 中所有持久化调用的"FP 化入口"。**未来如果要做更深的 FP 改造，应以这两个函数为锚点**。

---

## 9. 范围外声明

- ❌ `proxy.ts` (Next.js middleware) — 已在 P4 Agent C 范围，本 agent 不审
- ❌ `app/` 与 `components/` — 由 P4 Agent A/B/C 审
- ❌ `.test.ts/.test.tsx` — 测试文件
- ❌ `i18n/request.ts` / `i18n/provider.tsx` — next-intl 配置，不审
- ❌ `messages/*.json` — i18n 翻译资源
- ❌ `scripts/e2e-up.sh` — shell 脚本