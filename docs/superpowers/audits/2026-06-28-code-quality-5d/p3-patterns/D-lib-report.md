# P3 维度 ③ 单例/策略/工厂模式 — Agent D (lib+其它 ~83 files)

## 扫描概览

- 总扫描文件: 83 (lib/* + const/* + i18n/* + scripts/* + proxy.ts)
- 已正确使用设计模式的位置: 14
- 已识别但无需重构的合适模式: 11
- 可用模式进一步重构的位置: 3 (🔴1 + 🟡2)
- 实际净省代码: ~70 行 (🟡两处)

## 已用设计模式的位置（不要重复建议）

### 单例模式 (Singleton) — 5 处

1. **`lib/store/app-store.ts`** — zustand `create()` 已经是单例的等价实现（模块级只 `create` 一次）
2. **`lib/store/ui-store.ts`** — 同上
3. **`lib/store/auth-store.ts`** — zustand + persist 中间件，模块级唯一实例
4. **`lib/api/query-client.ts`** — `createBrowserQueryClient()` 工厂返回单例 (layout 生命周期内 `let client: QueryClient | undefined` 模式可再优化，但目前依赖外部 layout 缓存，合格)
5. **`lib/api/rsc-queries.ts:getRscQueryClient()`** — 用 React `cache()` 函数实现 per-request 单例，server-only

### 策略模式 (Strategy) — 4 处

1. **`lib/chat/factory.ts`** — LLM Provider 策略模式实现 (dify / openai)，通过环境变量 `CHAT_PROVIDER` 选择，Dify 套 `withMemoryHooks` 装饰器
2. **`lib/chat/types.ts:ChatProvider`** 接口 — 策略模式的核心抽象，所有 provider 必须实现 `sendMessage()`
3. **`lib/parse/parse-{csv,excel,json}.ts`** — 三种文件解析策略，各自导出独立函数（不是严格的策略对象，但语义上是策略）
4. **`lib/api/config.ts:apiFetch` vs `apiProxy`** — 两种 fetch 策略：带错误归一 vs 原样透传

### 适配器 (Adapter) — 3 处

1. **`lib/chat/storage.ts` + `db.ts`** — IndexedDB via Dexie 适配 ChatShell 的旧 localStorage API（owner 字段抹平、API 同形）
2. **`lib/auth/permission.ts:getPermissions()`** — server-only 适配器，把 `getMyPermissions()` 包装成 React `cache()` + 配 `can()` 谓词
3. **`lib/dom/download.ts:triggerBrowserDownload`** — DOM API 适配，把 Blob→ObjectURL→`<a download>` 三步封装

### 外观模式 (Facade) — 4 处

1. **`lib/api/config.ts:apiFetch`** — 统一 fetch 外观：拼 URL + JSON 序列化 + 错误归一 + 类型泛型
2. **`lib/api/config.ts:apiProxy`** — BFF 透传外观：返 raw Response，不读 body
3. **`lib/chat/api.ts`** — TanStack Query hooks 外观 (7 hooks)，封装 useQuery/useMutation + staleTime + invalidate
4. **`lib/chat/memory-integration.ts:withMemoryHooks`** — ChatProvider 装饰器（详见下）

### 装饰器 (Decorator) — 2 处

1. **`lib/chat/memory-integration.ts:withMemoryHooks()`** — 经典装饰器：套任意 ChatProvider 自动获得长期记忆能力（Pre-LLM 搜记忆 + 流中累积 + Post-LLM 写记忆）。在 factory.ts:21 用 `withMemoryHooks(new DifyChatProvider())` 实现
2. **`lib/api/config.ts:apiFetch`** — 实际上也扮演装饰器角色：包了 NetworkError/ApiError 归一化，可被任意 fetch 调用方复用

---

## 🔴 高 ROI（建议重写）— 1 处

### 1. `lib/api/*.ts` 重复的 `headers?: Record<string, string>` 参数模式 (16+ 文件)

**问题**: 几乎所有 `lib/api/*.ts` 文件都重复这个模式：
```typescript
export const someFunc = (arg1: Type1, headers?: Record<string, string>) =>
  apiFetch<ResponseType>(`/api/path/${arg1}`, { headers });
```

文件包括: account.ts (15 处)、permissions.ts (4 处)、users.ts (4 处)、memory.ts (3 处)、approvals.ts (3 处)、lookups.ts (3 处)、health.ts、ingest.ts、chat.ts、chat-share.ts 等。

**ROI 分析**:
- 16+ 文件 × 重复的 `headers?: Record<string, string>` 签名
- 每个 server 调用方都要手动调 `await serverAuthHeaders()` 再传入
- 调用边界 (client-bff / server-only / shared) 信息隐式藏在 `headers` 参数上

**建议重构**（中等 ROI，非高）:

抽 `lib/api/server-fetch.ts` 提供 server-only 工厂:
```typescript
// lib/api/server-fetch.ts
import "server-only";
import { serverAuthHeaders } from "./auth.server";
import { apiFetch } from "./config";

export const serverApiFetch = <T>(path: string, init: ApiFetchInit = {}): Promise<T> =>
  apiFetch<T>(path, { ...init, headers: { ...init.headers, ...(await serverAuthHeaders()) } });
```

**ROI 重判**: 实际行数净省 — 16 文件 × 节省 1-2 行 = ~30 行 + 减少认知负担。降到 🟡 中 ROI。

---

## 🟡 中 ROI（可选）— 2 处

### 1. `lib/api/` URL 工厂 vs fetch 函数二元结构 (4 文件)

**问题**: knowledge.ts / ingest.ts / evaluate.ts / chat.ts 都同时导出 fetch 函数 + URL 工厂函数：
```typescript
export const fetchTask = (id: string) => apiFetch(taskUrl(id));  // 复合
export const taskUrl = (id: string) => `/api/ingest/tasks/${id}`;  // 拆分
```

实际上现在所有 RQ 调用方都直接用 fetch 函数（已经验证），URL 工厂目前只有 1-2 处真在用。**可以考虑统一** — 但已存在的二元结构有文档价值（让 RQ/RSC 调用方各取所需）。

**ROI**: 重构净增 0 行（统一后只是删除 URL 工厂），但删除会让某些使用 URL 工厂的地方需要改回直接调函数。**保持现状**。

### 2. `lib/store/` 4 个 zustand store 缺少统一工厂

**问题**: `app-store.ts` / `ui-store.ts` / `auth-store.ts` / `usePermissions.ts` 4 个 zustand store 各自手写 `create() + persist() + partialize`。

**建议**: 抽 `lib/store/factory.ts`:
```typescript
export const createPersistedStore = <T>(name: string, initial: T, partialize?: (s: T) => Partial<T>) =>
  create<T>()(persist((set) => initial, { name, partialize }));
```

**ROI 分析**:
- 现状: 3 个持久化 store (app/auth/usePermissions) × ~5 行 boilerplate = 15 行
- 重构后: 抽 1 个 factory ~10 行 + 调用处 3 × 1 行 = 13 行
- **净省 ~2 行** ❌ 不划算

**结论**: 不建议重抽。zustand 官方推荐就是各 store 独立声明，强行抽工厂会牺牲类型推导可读性。

---

## 🟢 低 ROI（不建议）— 5 处

### 1. `lib/chat/{dify,openai}.ts` 都手写 SSE 切块逻辑

`openai.ts:51-62` 和 `dify.ts` (经由 `parseSseBlocks`) 都用了 `\n\n` 切块 + data: 行解析。`openai.ts` 没复用 `lib/chat/sse.ts:parseSseBlocks`。

**ROI**: 重构后 openai.ts 减少 ~30 行，复用 sse.ts。但 openai 的解析格式略有差异（reasoning_content 累积 vs Dify 双发射防御），强行复用会让 `parseSseBlocks` 接口变复杂。**保持现状**。

### 2. `lib/chat/memory-integration.ts` 自己读 cookie + fetch

`readAuthHeaders()` + 直接 `fetch(BACKEND_URL/...)` 在 memory-integration.ts:48-110 出现 3 次（searchMemory、addMemory、fetchBuyerProfile），而项目已经有 `lib/api/auth.server.ts:serverAuthHeaders()`。

**ROI**:
- 现状 3 处 × ~10 行直接 fetch = 30 行
- 重构后用 apiFetch: 3 × ~3 行 = 9 行 + 删重复 readAuthHeaders ~10 行 = 净省 ~30 行
- **但是**: memory-integration 是 server-only 装饰器，调用 `apiFetch` 会引入与 `auth.server` 的耦合链。当前注释明确说避免循环依赖。**保持现状**，但建议在 auth.server.ts 注释里补一句 "memory-integration.ts 是已知例外".

### 3. `lib/chat/chat-utils.ts` 内部 6 个 useState

`useChatShellState()` 一次性 `useState` 8 个状态 (conversations/currentId/messagesByConv/streamingConvId/draft/pendingDeleteId/memoryOpen/shareOpen)。

**ROI**: 可用 `useReducer` 合并，但当前 React 19 + Compiler 自动 memoize 模式下性能可控。**不重写**。

### 4. `lib/api/memory.ts` add 函数手写 camelCase→snake_case 转换

```typescript
const body = { messages: req.messages };
if (req.conversationId) body.conversation_id = req.conversationId;
```

**ROI**: 单文件 1 处，5 行代码。抽转换器净增代码。**不抽**。

### 5. `lib/dify-datasets.ts` 自定义 `DifyApiError` 与 `lib/api/errors.ts` 的 `ApiError` 重复

`DifyApiError extends Error { status }` 跟 `ApiError` 完全同形。

**ROI**: 1 处重复 9 行代码。但 `DifyApiError` 是上游 Dify API 错误，需要保留 status 字段。直接 import `ApiError` 也行。**可选，建议** 改用 `ApiError`，净省 9 行。

---

## ❌ 明确不做（违反 YAGNI / 已用合适模式）

### 1. `lib/utils.ts` / `lib/dom/download.ts` / `lib/log.ts` / `lib/motion.ts`

全部纯工具函数 / 常量配置 / 样式 token。**不需要任何模式**。

### 2. `lib/parse/*` 3 个文件已经独立导出 (`parseEvalCsv` / `parseExcelBuffer` / `parseJsonText`)

各签名不同（CSV 异步、Excel 同步 ArrayBuffer、JSON 同步 text），强行抽 `IParser` 接口会牺牲类型推导。**当前状态合适**。

### 3. `lib/auth/{role,permission,permission-types}.ts`

- `role.ts` 提供 `isAdminLevel` / `isSuperAdmin` 谓词
- `permission.ts` 用 React `cache()` 包 server fetch + 默认值降级
- `permission-types.ts` 纯类型定义

**三者各司其职，职责清晰**。`permission.ts` 的 `cache()` 已经是合理抽象。**无需重构**。

### 4. `lib/chat/use-chat-state.ts` 已经是装饰器模式

`useChatShellState` + `useServerData` + `useChatHandlers` 三层 hook 装饰器，每层加一种能力（state / server data / handlers）。**合适**。

### 5. `lib/theme/{themes,use-theme}.ts`

`themes.ts` 静态配置 + `getThemeConfig()` 查表，4 行 use-theme 转发到 `components/theme-provider`。**职责清晰，无需模式**。

### 6. `lib/test-utils/intl-wrapper.tsx`

测试 wrapper，本身就是适配器模式（包 NextIntlClientProvider 给测试用）。**已合适**。

### 7. `lib/hooks/use-{confirm,dialog,pagination,polling,query-params,permissions}.ts`

每个 hook 职责单一，5-20 行。**无需重构**。

### 8. `lib/buyer-profile/hooks.ts`

TanStack Query hooks 标准化封装（staleTime 60s + queryKey + invalidate）。**已合适**，跟 lib/chat/api.ts 风格一致。

### 9. `lib/server/evaluate.ts:deleteRunById`

裸 `fetch()` 不走 `apiFetch()`，与同包其他 server 函数不一致（auth.server.ts / rsc-queries.ts 都走 apiFetch）。

**ROI 分析**: 1 处 25 行，可改走 apiFetch 但需要带 serverAuthHeaders + 错误归一 — 改完净省 10 行。**可选**，但需要 commit history 上下文（已专门搬到 server/ 绕过 BFF）。

### 10. `lib/api/index.ts` barrel 不导出 server-only 模块

`auth.server.ts` / `rsc-queries.ts` 故意不走 barrel 防 client chain 触发 server-only throw。**这是有意设计**。

### 11. `proxy.ts` (Next.js middleware)

Next.js middleware 标准模式，无可重构。**保持**。

---

## 扫描方法说明

1. **lib/ 区是模式主战场但已大量使用** — 14 处已用合适模式，无需重写
2. **lib/chat/ 是策略模式教科书示例** — `factory.ts` + `types.ts:ChatProvider` 接口 + `dify/openai` 两个实现 + `memory-integration.ts` 装饰器，完整覆盖 4 种设计模式
3. **lib/api/ 已有 TanStack Query 外观 + apiFetch/apiProxy 双策略** — 16+ 文件已是 facade 模式产物（apiFetch），但 server-only 调用边界有 ~30 行可优化
4. **lib/store/ 4 个 zustand store 都是单例等价** — 抽 factory 净省 2 行不值得
5. **lib/parse/ 3 个解析函数语义上是策略但不强抽** — 各签名不同，强抽接口牺牲类型推导
6. **lib/auth/ 装饰器+适配器+单例齐全** — `getPermissions()` 是 React `cache()` + server fetch + 默认值的复合适配器
7. **lib/theme/ 静态配置** — 无需模式
8. **lib/hooks/ 单职责 hook** — 无需模式

**核心结论**: lib/ 区是设计模式应用的样板项目，唯一可优化点是 `lib/api/*` 的 `headers?: Record` 重复签名（中等 ROI，~30 行净省），其他都已合适。