# 常量审计 + 全量清理设计 (2026-06-25)

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：以 `c:/doc/Code/rag/packages/web` 当前 master (e2ebb616) 为准
> 🎯 范围：`packages/web` 整个 Next.js 项目（不含 `node_modules` / `.next` / 测试文件 / `e2e/`）
> 📊 调研方法：5 路 Explore agent 并行扫描（app/api, lib/api, app/_actions, components+hooks, lib+app/[locale]）

---

## 一、目标 & 范围

**目标**：扫 `packages/web` 全部魔法数字字面量、字符串字面量、局部 `const` 定义，按"是否跨文件复用 + 语义是否通用"判定应否挪到 `const/index.ts`，给出**完整整改方案 + 优先级 + 验收门**。

**核心约束**：
- ✅ 走 `packages/web/const/index.ts` 已有的「魔法数字字面量」定位
- ✅ 跨文件复用 + 通用语义 → 全局常量
- ✅ 业务专属 → 业务模块自己的 `const.ts` 或原地内联
- ✅ 配置/部署相关（env 兜底、URL base） → 保留在 route.ts
- ❌ 不动 `lib/chat/types.ts`、`lib/auth/role.ts` 等业务枚举（语义契约）
- ❌ 不动 `messages/{zh,en}.json` 里的 i18n 文案
- ❌ 不动 Tailwind className 字符串（业务专属）
- ❌ 不动测试 fixture 数字

---

## 〇、前置改动（spec 写完之前的对话产物）

> ⚠️ 在本 spec 调研阶段之前（对话早期），用户曾要求我"把 `app/api/[...path]/route.ts` 里的常量提取到 `const/index.ts`"，我已**实际修改了 2 个文件**。本节把这次改动明确化，避免后续实施时与 spec 冲突。

### 改动文件

| 文件 | 改动 |
|---|---|
| `packages/web/const/index.ts` | 新增 `HTTP_BAD_GATEWAY = 502`（跟 200/201/.../500 同段） |
| `packages/web/app/api/[...path]/route.ts` | 删除 4 处局部 const，顶部 `import { HTTP_BAD_GATEWAY, HTTP_NO_CONTENT, HTTP_NOT_FOUND, ZERO } from "@/const"` |

### 已替换的 4 处局部常量

| 原 const | 新引用 | 位置 |
|---|---|---|
| `NOT_FOUND = 404` | `HTTP_NOT_FOUND` | `notFoundResponse()` L34 |
| `EMPTY_LENGTH = 0` | `ZERO` | `buildApiPath()` L41 |
| `PROXY_ERROR = 502` | `HTTP_BAD_GATEWAY` | `proxyErrorResponse()` L96 |
| `NO_CONTENT = 204` | `HTTP_NO_CONTENT` | `OPTIONS` handler L167 |

### 保留在 route.ts（不挪到 const/index.ts）

| const | 理由 |
|---|---|
| `BACKEND_URL` | 部署配置，env 兜底链（`RAG_BACKEND_URL ?? FASTAPI_BASE ?? NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000"`），不属于跨模块共用字面量 |
| `ALLOWED_METHODS` | catch-all 代理专属协议白名单 |

### 跟本 spec 的关系

- ✅ **符合本 spec 第三章 3.1**（HTTP_BAD_GATEWAY 在 §3.1 列出）
- ✅ **符合本 spec 第四章 Phase 2**（删除重复定义 const）
- ⚠️ **`BACKEND_URL_DEFAULT` 字符串值** 还没从 route.ts 提到 const/index.ts；按 spec §3.1 应挪但**还没动**（避免范围蔓延，留给后续 Phase）
- ⚠️ **`ALLOWED_METHODS`** 在 spec §3.5 明确"保留本地"，本次对话决策保留 route.ts 内联 → **一致**

### 验收

- [x] `bun run typecheck` 0 error（已验证）
- [x] `bun run lint` 0 error（hint 级别是 IDE LSP 滞后，不影响构建）
- [ ] 未 commit（用户决策中）

### 后续处理

下一步行动**不在本 spec 范围**，由用户决定：
- **选项 A**：跟 spec 一起 commit，作为本次审计的"探路改动"
- **选项 B**：单独 commit，跟 spec 的 Phase 1 拆分
- **选项 C**：revert 掉，回到干净 master 状态，让后续实施从零开始

---

## 二、当前现状

### 2.1 `const/index.ts` 已有内容

**5 段共 35 项**：
1. 基础数字 `ZERO / ONE / ... / THOUSAND` (13 项)
2. 时间换算 `MS_PER_SECOND / SECONDS_PER_MINUTE / ... / ONE_HOUR_MS` (15 项)
3. HTTP 状态码 `HTTP_OK / ... / HTTP_BAD_GATEWAY` (15 项，2026-06-19 已加 502)
4. 端口/分页 `DEFAULT_DEV_PORT / DEFAULT_API_PORT / DEFAULT_PAGE_SIZE / ONE_KB / ONE_MB / ONE_GB` (7 项)
5. localStorage key `ANON_USER_ID_KEY` (1 项)

### 2.2 扫描规模

| 维度 | 文件数 | 发现数 | 已用全局 |
|---|---|---|---|
| **D1: app/api** | 24 个 route.ts | 数字字面量 15 / 局部 const 14 / 高频字符串 30+ 处 | 3 个文件已用 |
| **D2: lib/api** | 22 个 .ts | 数字 47 / const 8 / 字符串 89 | 局部零散 |
| **D3: app/_actions** | 5 个 .ts | 数字 11 / const 13 | **重复定义** const/index.ts 已有值 |
| **D4: components+hooks** | 78 个 .tsx/.ts | 局部 const 29 处 | 10 个文件已规范 |
| **D5: lib+app/[locale]** | 194 个 lib 文件 + 48 个 page | 数字 62 / const 38 / 字符串 47 / 正则 2 | 零散 |
| **合计** | ~370 个文件 | 数字 145 / const 102 / 字符串 200+ | <10% 覆盖率 |

### 2.3 关键问题（按严重度）

**🔴 P0 - 严重（重复定义全局已有常量，违反 DRY）**

| 问题 | 位置 |
|---|---|
| `app/[locale]/_actions/account.ts` 重新定义 `SECONDS_PER_MINUTE=60 / MINUTES_PER_HOUR=60 / HOURS_PER_DAY=24` | L23-25 |
| `app/[locale]/_actions/account.ts` 重新定义 `HTTP_UNAUTHORIZED=401` | L28 |
| `app/[locale]/_actions/account-settings.ts` 重新定义 `HTTP_UNPROCESSABLE_ENTITY=422 / HTTP_BAD_REQUEST=400` | L27-28 |
| `lib/hooks/use-lookup.ts` 重新定义 `MS_PER_SECOND=1000 / SECONDS_PER_MINUTE=60 / MINUTES_PER_HOUR=60` | L15-17 |
| `lib/hooks/use-pagination.ts` 重新定义 `DEFAULT_PAGE_SIZE=20` | L3 |
| `components/common/table/use-table-pagination.ts` 重新定义 `PAGE_SIZE_DEFAULT=20` | — |
| `components/common/input/app-file-dropzone.tsx` 重新定义 `KILOBYTE=1024` | — |
| `components/ui/progress.tsx` 重新定义 `HUNDRED_PERCENT=100` | — |
| `app/api/knowledge/batch/route.ts` `NO_FAILURES=0` 应直接用 `ZERO` | L25 |
| `app/api/chat/messages/route.ts` `MIN_STR_LENGTH=1` 应直接用 `ONE` | L15 |

**🟠 P1 - 高频跨文件复用字符串**

| 字符串 | 出现次数 | 文件 |
|---|---|---|
| `"content-type"` / `"Content-Type"`（大小写混用） | 30+ | 所有 route.ts |
| `"application/json"` | 18+ | 所有 route.ts |
| `"rag_user_token"` (cookie) | 3 处 | `[...path]/route.ts`, `auth.server.ts`, `account.ts` |
| `"x-user-token"` (header) | 3 处 | `[...path]/route.ts`, `auth.server.ts`, `memory-integration.ts` |
| `"x-chat-token"` (header) | 1 处 | `chat/messages/route.ts` |
| `"x-forwarded-for"` (header) | 1 处 | `lib/rate-limiter.ts` |
| `"/login"`, `"/account/settings"`, `"/health"`, 9 个 `/knowledge/*`, 4 个 `/admin/*` | 15+ 处 | 多个 components/pages |

**🟡 P2 - 业务专属跨模块常量（建议加 const/index.ts 或独立模块）**

- Dify / OpenAI 默认 endpoint / model
- Dexie / Zustand 持久化 key 系列
- TanStack Query 默认 staleTime
- ID 生成参数（base36, length）
- BFF 鉴权 cookie 名称

**🟢 P3 - 业务专属保留本地**

- 业务枚举字符串（角色 / 状态 / 类型）
- 业务路由 path（`/buyers/...` 等）
- 动画参数（`lib/motion.ts`）
- 业务专属表单校验（密码长度 8 跨 4 处 → 但属业务，挪全局或独立 `lib/auth/const.ts`）

---

## 三、const/index.ts 应新增的常量（按段组织）

### 3.1 HTTP 协议 / MIME / Storage 段（新增 8 项，按 grep 真跨文件数筛选）

> **筛选标准**：`grep` 实际跨 2+ 个生产文件（去测试文件 / e2e）。低于此阈值的一律不抽（判定为过度设计）。

```typescript
// ──────────────── HTTP 协议字符串 (跨 2+ 文件) ────────────────
export const HEADER_CONTENT_TYPE = "content-type";       // 27+ 文件 (含测试, 业务 17+)
export const HEADER_X_USER_TOKEN = "x-user-token";       // 3 业务文件
export const HEADER_X_CHAT_TOKEN = "x-chat-token";       // 2 业务文件
export const COOKIE_USER_TOKEN = "rag_user_token";       // 4 业务文件

// ──────────────── MIME 类型 (跨 2+ 文件) ────────────────
export const MIME_JSON = "application/json";             // 22+ 文件 (业务 17+)

// ──────────────── localStorage key (跨 2+ 文件) ────────────────
export const LS_KEY_WAS_LOGGED_IN = "rag_was_logged_in"; // 2 业务文件

// ──────────────── Chat 协议 (跨 2+ 文件) ────────────────
export const SSE_DELIMITER_LENGTH = 2;                   // 2 文件 (sse + openai)
export const INDEX_NOT_FOUND = -1;                       // 3 文件 (sse + openai + storage)
```

**不抽的**（单文件或 0 文件复用，验证后删掉）：
- ~~`HEADER_CONTENT_DISPOSITION`~~ 1 文件
- ~~`HEADER_SET_COOKIE`~~ 1 文件
- ~~`HEADER_X_FORWARDED_FOR`~~ 1 文件
- ~~`HEADER_X_ADMIN_TOKEN`~~ 0 文件（仅注释引用，已废弃）
- ~~`MIME_ZIP`~~ 1 文件
- ~~`MIME_CSV`~~ 1 文件
- ~~`MIME_EVENT_STREAM`~~ 1 文件
- ~~`COOKIE_NEXT_LOCALE`~~ 0 文件（next-intl 内部用，不暴露）
- ~~`LS_KEY_THEME`~~ 1 文件
- ~~`LS_KEY_APP_STORE`~~ 1 文件
- ~~`LS_KEY_AUTH_STORE`~~ 1 文件
- ~~`LS_KEY_MIGRATION_DEBOUNCE`~~ 1 文件
- ~~`IDB_NAME_CHAT`~~ 1 文件
- ~~`IDB_VERSION_CHAT`~~ 1 文件
- ~~`DEFAULT_DIFY_BASE_URL`~~ 1 文件
- ~~`DEFAULT_OPENAI_BASE_URL`~~ 1 文件
- ~~`DEFAULT_OPENAI_MODEL`~~ 1 文件
- ~~`DIFY_INPUT_MEMORY_CONTEXT`~~ 1 文件
- ~~`DIFY_INPUT_BUYER_PROFILE`~~ 1 文件
- ~~`MEMORY_SEARCH_LIMIT`~~ 1 文件
- ~~`CHAT_MAX_MESSAGES_PER_CONV`~~ 1 文件
- ~~`SSE_LOG_MAX_LENGTH`~~ 1 文件
- ~~`CHAT_BACKUP_FILE_PREFIX`~~ 1 文件
- ~~`MIGRATION_TOAST_ID`~~ 1 文件

### 3.2 时间 / 限流 / 配置段（新增 1 项）

```typescript
// ──────────────── 业务时间参数 (跨 2+ 文件) ────────────────
export const MIN_PASSWORD_LENGTH = 8;                    // 2 业务文件 (account + account-settings)
```

**不抽的**（业务专属或单文件）：
- ~~`FIVE_THOUSAND_MS` / `MIGRATION_DEBOUNCE_MS`~~ 1 文件
- ~~`AUTH_COOKIE_EXPIRY_DAYS` / `AUTH_COOKIE_MAX_AGE_SECONDS`~~ 1 文件
- ~~`SIXTY = 60`~~ 已有 `SECONDS_PER_MINUTE = 60`，语义重复
- ~~`DEFAULT_STALE_TIME_MS = 60_000`~~ 已有 `SECONDS_PER_MINUTE * MS_PER_SECOND = 60_000`，可内联（Phase 5 直接用算式）

### 3.3 路由 path 段（**不抽**，判定为过度设计）

> ❌ **不抽**。验证后只有 2 个路由跨多文件复用（`/login` + `/account/settings`），但**两次上下文不同**：跳转行为 ≠ 字符串复用，更适合封装成 `goToLogin()` / `goToSettings()` 导航函数，**不是**字符串常量。
>
> 验证依据（grep `"/login"` 等 16 个路由）：
> - `"/login"` 跨 2 文件：`components/user-menu.tsx`（未登录跳转）+ `app/[locale]/reset-password/page.tsx`（重置后跳转）
> - `"/account/settings"` 跨 2 文件：同上模式
> - 其他 14 个路由**全部单文件内部使用**（多数在 `knowledge-tabs.tsx` 的 `TABS` 数组里）
>
> **判定**：
> - ❌ 不建 `lib/routes.ts`（间接层无价值）
> - ❌ 不加 `ROUTE_*` 到 const/index.ts
> - ✅ 业务代码继续用 `<LocalizedLink href="/login">` 直写（next-intl 自动加 locale 前缀）
> - 后续如出现"统一跳转行为"需求 → 抽 `lib/navigation.ts` 函数，不是字符串

### 3.4 Dify / OpenAI / SSE 业务配置段（**不抽**，判定为过度设计）

> ❌ **不抽**。验证后 12 项里只有 **2 项真跨文件**：
> - `SSE_DELIMITER_LENGTH=2` 跨 `lib/chat/sse.ts` + `lib/chat/openai.ts` (2 文件)
> - `INDEX_NOT_FOUND=-1` 跨 `lib/chat/sse.ts` + `lib/chat/openai.ts` + `lib/chat/storage.ts` (3 文件)
>
> 其他 10 项都是单文件局部 const（如 `DEFAULT_DIFY_BASE_URL` 只在 `lib/chat/dify.ts`）。
>
> **判定**：
> - ❌ 不建 `lib/chat/const.ts`（新文件无价值，2 项放进去不达"模块常量文件"门槛）
> - ✅ 这 2 项**加到 `const/index.ts`** 的新段"Chat 协议"（4 行）
> - ✅ 其他 10 项业务专属**保留本地**，各自 const.ts 已有就改文件名 / 还没有就加

### 3.5 不应挪（保留本地）

| 常量 | 位置 | 理由 |
|---|---|---|
| `BACKEND_URL` env 兜底 + `BACKEND_URL_DEFAULT` | `[...path]/route.ts` | 部署配置，env 链 |
| `ALLOWED_METHODS` | `[...path]/route.ts` | catch-all 协议专属 |
| `SUCCESS_THRESHOLD = 0.8` / `RADIX = 36` / `ID_LENGTH = 14` | `knowledge/batch/route.ts` | 单一调用点，私有 |
| `RATE_LIMIT_MAX = 20` / `RATE_LIMIT_WINDOW_MS = 60_000` | `chat/messages/route.ts` | chat 端专属 |
| `MAX_QUERY_LENGTH = 16_000` / `MAX_USER_LENGTH = 64` | `chat/messages/route.ts` | chat 业务专属 |
| 业务枚举 (`"user" / "super_admin"` / `"done" / "running"` 等) | 各模块 types.ts | 语义契约 |
| `EXAMPLE = "1LE0001-1AA42-1AA4"` | `decode/page.tsx` | 业务专属示例 |
| `INDEX_COL_WIDTH = 56` 等列宽 | `buyers/page.tsx` | 业务专属 |
| 动画参数 | `lib/motion.ts` | 设计 token，业务专属 |
| `motion.ts` 里的贝塞尔曲线 / spring 参数 | `lib/motion.ts` | 业务专属 |

---

## 四、整改任务分解

### Phase 1 - const/index.ts 增量更新（1 个 commit）

**目标**：加 §3.1 (8 项) + §3.2 (1 项) = **9 项常量**。

**改动**：
- `packages/web/const/index.ts` 新增 2 段（HTTP 协议/MIME/Storage 7 项 + Chat 协议 2 项 + 鉴权 1 项 = 9 项）
- 文件改动量 < 30 行（仅追加，不动现有）

**验收**：
- `bun run typecheck` 0 error
- `bun run lint` 0 error
- 不影响任何调用方（只新增，不删旧）

**Commit**: `refactor(const): 新增 9 项跨文件常量 (HTTP/MIME/Cookie/Storage/Chat/鉴权)`

---

### Phase 2 - 修复 const 重复定义（P0 严重项，1 个 commit）

**目标**：删除 §2.3 表格里 10 处"重复定义全局已有常量"的代码，全部改 import。

**改动清单**：

| 文件 | 现状 | 改成 |
|---|---|---|
| `app/[locale]/_actions/account.ts` | L23-28 自己定义 `SECONDS_PER_MINUTE / MINUTES_PER_HOUR / HOURS_PER_DAY / HTTP_UNAUTHORIZED` | 顶部加 `import { ... } from "@/const"`，删局部 |
| `app/[locale]/_actions/account-settings.ts` | L27-28 自己定义 `HTTP_UNPROCESSABLE_ENTITY / HTTP_BAD_REQUEST` | 同上 |
| `lib/hooks/use-lookup.ts` | L15-17 自己定义 `MS_PER_SECOND / SECONDS_PER_MINUTE / MINUTES_PER_HOUR` | 同上 |
| `lib/hooks/use-pagination.ts` | L3 自己定义 `DEFAULT_PAGE_SIZE` | 同上 |
| `components/common/table/use-table-pagination.ts` | `PAGE_SIZE_DEFAULT = 20` | 用 `DEFAULT_PAGE_SIZE` |
| `components/common/input/app-file-dropzone.tsx` | `KILOBYTE = 1024` | 用 `ONE_KB` |
| `components/ui/progress.tsx` | `HUNDRED_PERCENT = 100` | 用 `HUNDRED` |
| `app/api/knowledge/batch/route.ts` | `NO_FAILURES = 0` | 用 `ZERO` |
| `app/api/chat/messages/route.ts` | `MIN_STR_LENGTH = 1` | 用 `ONE` |
| `app/[locale]/reset-password/page.tsx` | `PASSWORD_MIN_LENGTH = 8` 重复 | 用 `MIN_PASSWORD_LENGTH`（待 §3.2 加） |

**验收**：
- `grep -rn "= 1024" packages/web/components` 返回 0 匹配（除 `ONE_KB` 定义）
- `grep -rn "= 100;$" packages/web` 返回 0 匹配（除 `HUNDRED` 定义）
- `bun run typecheck` + `bun run lint` + `bun run test` 全过

**Commit**: `refactor: 删除 10 处重复定义全局常量的局部 const (改 import)`

---

### Phase 3 - 字符串字面量替换（3 个 commit）

**目标**：把 §3.1 + §3.2 新增的 9 项常量替换到业务代码。

**3a. MIME / Header（1 个 commit）**：
- `"application/json"` (22+ 处) → `MIME_JSON`
- `"content-type"` / `"Content-Type"` (27+ 处, 大小写混用) → `HEADER_CONTENT_TYPE`（统一小写）
- 目标文件：所有 app/api 下 22 个 route.ts（除 tests）+ `lib/api/config.ts` + `lib/chat/memory-integration.ts`

**3b. Cookie / Auth header（1 个 commit）**：
- `"rag_user_token"` (4 处) → `COOKIE_USER_TOKEN`
- `"x-user-token"` (3 处) → `HEADER_X_USER_TOKEN`
- `"x-chat-token"` (2 处) → `HEADER_X_CHAT_TOKEN`
- 目标文件：`app/api/[...path]/route.ts` + `lib/api/auth.server.ts` + `app/[locale]/_actions/account.ts` + `lib/chat/memory-integration.ts` + `app/api/chat/messages/route.ts` + `lib/api/chat.ts`

**3c. localStorage + 鉴权（1 个 commit）**：
- `"rag_was_logged_in"` (2 处) → `LS_KEY_WAS_LOGGED_IN`
- `8` (password min) (2 处) → `MIN_PASSWORD_LENGTH`
- 目标文件：`components/auth/auth-bootstrap.tsx` + `components/user-menu.tsx` + `app/[locale]/_actions/account.ts` + `app/[locale]/_actions/account-settings.ts` + `app/[locale]/reset-password/page.tsx`

**验收**：
- `grep -rn '"application/json"' packages/web/app packages/web/lib | grep -v const/index.ts | wc -l` ≤ 5（剩余 shadcn 模板）
- `bun run typecheck` + `bun run lint` + `bun run test` 全过
- E2E 1 个测试手动验

**Commit**:
- `refactor: 替换 22+ 处 application/json + 27+ 处 content-type 字面量为全局常量`
- `refactor: 替换 cookie/auth header 字面量为全局常量 (4+3+2 处)`
- `refactor: 替换 localStorage key + 密码长度常量化`

---

### ~~Phase 4 - 路由常量抽离（1 个 commit）~~ ❌ **删除**

> 验证后判定为过度设计（详见 §3.3）。改为业务代码继续用 `<LocalizedLink href="/login">` 直写。

### ~~Phase 5 - lib/chat/const.ts 业务专属常量（1 个 commit）~~ ❌ **删除**

> 验证后 12 项里只有 2 项真跨文件（SSE_DELIMITER_LENGTH + INDEX_NOT_FOUND），且 Phase 1 已加到 const/index.ts。其他 10 项单文件用，**保留本地**。详见 §3.4。

---

## 五、关键文件清单

| 文件 | 改动类型 | Phase |
|---|---|---|
| `packages/web/const/index.ts` | 改：加 9 项（§3.1+§3.2） | P1 |
| `packages/web/app/api/chat/messages/route.ts` | 改：替换 5 处 HTTP 状态 + 4 处 Content-Type/application/json + 4 处常量 | P2 + P3a + P3b |
| `packages/web/app/api/knowledge/batch/route.ts` | 改：替换 2 处 HTTP 状态 + NO_FAILURES 用 ZERO | P2 + P3a |
| `packages/web/app/api/health/system/route.ts` | 改：替换 2 处 HTTP 状态 | P3a |
| `packages/web/app/api/[...path]/route.ts` | 改：替换 content-type/application/json + 1 处 COOKIE_USER_TOKEN + 1 处 HEADER_X_USER_TOKEN | P3a + P3b |
| `packages/web/app/[locale]/_actions/account.ts` | 改：删 5 个重复 const + 替换 cookie + password | P2 + P3b + P3c |
| `packages/web/app/[locale]/_actions/account-settings.ts` | 改：删 2 个重复 const + 替换 password | P2 + P3c |
| `packages/web/lib/api/auth.server.ts` | 改：2 处 COOKIE_USER_TOKEN + 1 处 HEADER_X_USER_TOKEN | P3b |
| `packages/web/lib/chat/memory-integration.ts` | 改：替换 application/json/content-type + cookie + auth header | P3a + P3b |
| `packages/web/lib/chat/sse.ts` | 改：替换 SSE_DELIMITER_LENGTH + INDEX_NOT_FOUND | （无 Phase, 局部内联就够了, 不抽） |
| `packages/web/lib/chat/openai.ts` | 改：同上 | 同上 |
| `packages/web/lib/chat/storage.ts` | 改：替换 INDEX_NOT_FOUND | 同上 |
| `packages/web/lib/hooks/use-lookup.ts` | 改：删 3 个重复 const | P2 |
| `packages/web/lib/hooks/use-pagination.ts` | 改：删 1 个重复 const | P2 |
| `packages/web/components/auth/auth-bootstrap.tsx` | 改：1 处 LS_KEY_WAS_LOGGED_IN | P3c |
| `packages/web/components/user-menu.tsx` | 改：1 处 LS_KEY_WAS_LOGGED_IN | P3c |
| `packages/web/components/common/table/use-table-pagination.ts` | 改：1 处 PAGE_SIZE | P2 |
| `packages/web/components/common/input/app-file-dropzone.tsx` | 改：KILOBYTE/FIRST_INDEX 复用 | P2 |
| `packages/web/components/ui/progress.tsx` | 改：HUNDRED_PERCENT 复用 | P2 |
| `packages/web/app/[locale]/reset-password/page.tsx` | 改：password 8 → MIN_PASSWORD_LENGTH | P3c |

---

## 六、风险 & 缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|------|------|------|
| R1 | content-type 替换破坏 Next.js fetch header 大小写语义 | 中 | 高 | **统一为小写**（HTTP/2 RFC 7540 要求小写，浏览器 fetch 自动归一） |
| R2 | ~~路由常量改动漏掉一处导致死链~~ | ~~中~~ | ~~高~~ | **删除**（Phase 4 已删除） |
| R3 | ~~localStorage key 改名导致老用户数据丢失~~ | ~~低~~ | ~~高~~ | **删除**（Phase 3c 只改 1 个 key，且老用户影响小） |
| R4 | `MIN_PASSWORD_LENGTH` 跨 4 处不一致 | 低 | 中 | Phase 2 一次性统一，不会出现不一致 |
| R5 | 单阶段改 > 500 行 | 中 | 中 | 按 Phase 拆分，每个 Phase 都 < 200 行 |
| R6 | oxlint no-magic-numbers 报警 | 高 | 低 | 全局常量是引用，magic-numbers 规则不触发 |
| R7 | 跟 master 的 lookup commit 冲突 | 低 | 高 | 全在新分支 `refactor/2026-06-25-const-cleanup`，最后 PR 合回 |
| R8 | `messages/{zh,en}.json` 误改 | 低 | 低 | 本 spec 不动 i18n，只动 const |
| R9 | shadcn ui/ 文件被改（项目规约禁止） | 低 | 高 | Phase 2 不动 `components/ui/`（shadcn 模板），`progress.tsx` 例外（项目已二次包装过） |
| R10 | ~~chat SSE 协议常量改错~~ | ~~低~~ | ~~高~~ | **删除**（Phase 5 已删除, SSE_DELIMITER_LENGTH/INDEX_NOT_FOUND 直接加 const/index.ts） |

---

## 七、验收门

每个 Phase 结束：
- [ ] `git diff --stat` 报告改动量（< 200 行）
- [ ] `bun run typecheck` 0 error
- [ ] `bun run lint` 0 error
- [ ] `bun run test` 0 新 fail（pre-existing fail 不算）
- [ ] 单 Phase 改 > 500 行 → 停下问用户 review

P1-P3 全部结束（最终验收）：
- [ ] `const/index.ts` 含 6 段共 44 项常量（35 已有 + 9 新增）
- [ ] ~~`lib/routes.ts`~~ 不存在（删除）
- [ ] ~~`lib/chat/const.ts`~~ 不存在（删除）
- [ ] `grep -rn "= 100;$\|= 1024$" packages/web` 返回 0 匹配（除 const 定义）
- [ ] `grep -rn '"application/json"' packages/web/app packages/web/lib | grep -v const/index.ts` ≤ 5 匹配（剩余 shadcn 模板）
- [ ] `grep -rn '"rag_user_token"\|"x-user-token"\|"x-chat-token"' packages/web` 返回 0 业务匹配
- [ ] `bun run test` 维持 719 passed + 0 fail
- [ ] `bun run test:e2e` 18 个用例全过
- [ ] `refactor/2026-06-25-const-cleanup` branch 推到 origin
- [ ] 跟 master 提 PR

---

## 八、不做（明确范围外）

- ❌ 不升级 oxlint/oxfmt/tsgo/vitest 任何版本
- ❌ 不动 `messages/{zh,en}.json` i18n 文案
- ❌ 不动业务枚举（`lib/chat/types.ts` / `lib/auth/role.ts`）
- ❌ 不动 `lib/motion.ts` 动画参数（业务专属）
- ❌ 不动 `components/ui/` shadcn 模板（除 `progress.tsx` 已二次包装）
- ❌ 不动测试 fixture 数字
- ❌ 不改 CI/CD
- ❌ 不动后端（`packages/service`）常量
- ❌ 不强制 100% 覆盖率（保留本地 const.ts 是个合理妥协）
- ❌ 不动 Dify / OpenAI / SSE 协议字面量（属业务契约）
- ❌ **不建 `lib/routes.ts`**（路由 path 不抽，详见 §3.3）
- ❌ **不建 `lib/chat/const.ts`**（chat 业务专属不抽，详见 §3.4）

---

## 九、本 spec 与历史 spec 关系

- **2026-06-19 code-quality-cleanup-design.md**（已实施）：本期是它之后第二阶段，专注 const/index.ts 扩充 + 重复定义清理 + 字符串常量抽离
- **2026-06-24 full-stack-audit-design.md**（设计中）：本 spec 是其中"Architecture & Convention (D6)"维度下"重复代码 / 违反 CLAUDE.md"的具体执行方案
- **2026-06-19 chat spec**：本期 P3 改 `lib/chat/*` 时同步遵循 chat spec 的"匿名 → IDB"约定

---

## 十、参考

- `packages/web/const/index.ts` 现有命名规范注释（基础数字 / 时间换算 / HTTP 状态码 / 端口 / 分页 / localStorage）
- `packages/web/CLAUDE.md` 「封装组件」「主题系统」「i18n」段
- `packages/web/CLAUDE.md` 「零 lint warning 规范」（2026-06-19 phase2）
- `docs/superpowers/specs/2026-06-19-code-quality-cleanup-design.md` 风格参考
- `docs/superpowers/specs/2026-06-24-full-stack-audit-design.md` 风格参考