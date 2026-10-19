# 常量审计 + 全量清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `packages/web` 项目里做一次常量审计 + 整改: 复用 `const/index.ts` 现有 35 项常量, 修复 10 处"重复定义"违规 (P0), 新增 9 项"真跨多文件"字符串常量 (P1), 把高频字符串字面量替换为 import 的全局常量. 总改动 ~30 个文件, 5 个 commit.

**Architecture:** 1 个新分支 `refactor/2026-06-25-const-cleanup`, 3 个 Phase 顺序执行: P1 (const 增量, 9 项) → P2 (删重复, 10 处) → P3 (替换, 3 个 commit 按 cookie/header/storage 分组). 每个 Phase 内部按"前置验证 → 改文件 → grep 验证 → 全套质量门 → commit"模式. 不动路由 path (过度设计), 不建 `lib/chat/const.ts` (过度设计).

**Tech Stack:** React 19 / Next.js 16 / TypeScript 8 / oxlint / oxfmt / tsgo / vitest / Bun

---

## 前置约束

### 项目铁律

```bash
cd packages/web
bun run format       # 0 报错
bun run lint:fix     # 0 报错
bun run typecheck    # 0 error
bun run test         # 0 新 fail (跟 baseline 对比)
```

husky pre-commit 自动跑 lint-staged + tsgo + vitest + format:check, 不需要手动跑全套.

### Baseline 测试快照 (Phase 1 前必跑)

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/baseline-test.log
```

记录 fail 数. 每个 Phase 末尾跑 `bun run test` 跟 baseline 对比, fail 数不能增加.

### 分支策略

```bash
git checkout -b refactor/2026-06-25-const-cleanup
```

PR 合回 master.

### 命名约定 (跟 packages/web/CLAUDE.md 一致)

- 组件声明: `const Component = () => {}`, 禁止 `function Component(){}`
- 变量名: 无单字符 (`idx` 替代 `i`, `val` 替代 `v`)
- 魔法数字: 提取到顶层 `const` 或 import from `@/const`
- import: 按字母排序 (oxlint sort-imports)
- 注释: 中文
- 改文件前先 Read, 用 Edit 不用 cat >

### 改动总览 (3 个 Phase, 5 个 commit)

| Commit | Phase | 主题 | 改动文件数 |
|---|---|---|---|
| 1 | P1 | const/index.ts 加 9 项常量 | 1 文件 |
| 2 | P2 | 删 10 处重复定义 const | 9 文件 |
| 3 | P3a | 替换 content-type/application/json | ~22 文件 |
| 4 | P3b | 替换 cookie/auth header | 6 文件 |
| 5 | P3c | 替换 localStorage key + 密码长度 | 5 文件 |

**总改动**: ~35 文件, 单 commit < 200 行 (R5 风险门)

### 0 后端 / messages / shadcn 模板改动 (硬约束)

- `packages/service/**` 不能动 (后端常量)
- `packages/web/messages/{zh,en}.json` 不能动 (i18n)
- `components/ui/**` 除 `progress.tsx` 已二次包装可动外, 其他不动 (R9)
- 测试文件 `.test.ts/.test.tsx` 不能动

---

## 文件结构总览

```
packages/web/
  ├── const/index.ts                      # 改: +9 项 (P1)
  ├── components/
  │   ├── ui/progress.tsx                 # 改: HUNDRED_PERCENT → HUNDRED (P2)
  │   ├── auth/auth-bootstrap.tsx         # 改: LS_KEY (P3c)
  │   ├── user-menu.tsx                   # 改: LS_KEY (P3c)
  │   └── common/
  │       ├── table/use-table-pagination.ts  # 改: PAGE_SIZE_DEFAULT (P2)
  │       └── input/app-file-dropzone.tsx    # 改: KILOBYTE + FIRST_INDEX (P2)
  ├── lib/
  │   ├── hooks/
  │   │   ├── use-lookup.ts               # 改: 3 个重复 const (P2)
  │   │   └── use-pagination.ts           # 改: DEFAULT_PAGE_SIZE (P2)
  │   ├── api/auth.server.ts              # 改: cookie + header (P3b)
  │   └── chat/memory-integration.ts      # 改: content-type/json + cookie + header (P3a+P3b)
  └── app/
      ├── api/
      │   ├── [...path]/route.ts          # 改: content-type/json + cookie + header (P3a+P3b)
      │   ├── chat/messages/route.ts      # 改: 5 处 HTTP 状态 + json/ct (P2+P3a+P3b)
      │   ├── knowledge/batch/route.ts    # 改: NO_FAILURES (P2)
      │   └── health/system/route.ts      # 改: content-type/json (P3a)
      └── [locale]/
          ├── _actions/
          │   ├── account.ts              # 改: 5 个重复 const + cookie + password (P2+P3b+P3c)
          │   └── account-settings.ts     # 改: 2 个重复 const + password (P2+P3c)
          └── reset-password/page.tsx     # 改: password 8 → MIN_PASSWORD_LENGTH (P3c)
```

---

### Task 1 (P1): const/index.ts 增量更新 (1 commit)

**Files**:
- Modify: `packages/web/const/index.ts`

**目标**: 加 §3.1 (8 项) + §3.2 (1 项) = **9 项常量**.

**改动**:

- [ ] **Step 1.1: 前置验证**

```bash
cd packages/web
bun run typecheck   # 必须 0 error
bun run lint        # 必须 0 error
```

- [ ] **Step 1.2: 编辑 const/index.ts**

打开 `packages/web/const/index.ts`, 找到最后一行 `export const ANON_USER_ID_KEY = "rag.chat.anon-user-id.v1";`, 在它**之后**追加以下代码 (注意保留原文件所有注释和空行):

```typescript

// ──────────────── HTTP 协议字符串 (跨 2+ 文件) ────────────────
// (2026-06-25 const-cleanup spec §3.1) 复用度阈值: 跨 2+ 生产文件
export const HEADER_CONTENT_TYPE = "content-type";
export const HEADER_X_USER_TOKEN = "x-user-token";
export const HEADER_X_CHAT_TOKEN = "x-chat-token";
export const COOKIE_USER_TOKEN = "rag_user_token";
export const MIME_JSON = "application/json";
export const LS_KEY_WAS_LOGGED_IN = "rag_was_logged_in";

// ──────────────── Chat 协议 (跨 2+ 文件) ────────────────
export const SSE_DELIMITER_LENGTH = 2;
export const INDEX_NOT_FOUND = -1;

// ──────────────── 鉴权 / 业务上限 (跨 2+ 文件) ────────────────
export const MIN_PASSWORD_LENGTH = 8;
```

注意: 
- 9 项常量, 每项一行 export
- 不要写 `const SIXTY = 60` (跟 `SECONDS_PER_MINUTE` 重复)
- 不要写 `MIME_ZIP / MIME_CSV / MIME_EVENT_STREAM / HEADER_CONTENT_DISPOSITION / HEADER_SET_COOKIE` (单文件, 过度设计)

- [ ] **Step 1.3: 验证**

```bash
cd packages/web
bun run typecheck   # 0 error
bun run lint        # 0 error
bun run test        # 跟 baseline 一致 (新 const 不影响现有测试)
```

预期: 全部通过, 因为 const/index.ts 只新增不删旧.

- [ ] **Step 1.4: Commit**

```bash
git add packages/web/const/index.ts
git commit -m "refactor(const): 新增 9 项跨文件常量 (HTTP/MIME/Cookie/Storage/Chat/鉴权)

- HEADER_CONTENT_TYPE (跨 27+ 文件, 统一小写)
- HEADER_X_USER_TOKEN (3 文件)
- HEADER_X_CHAT_TOKEN (2 文件)
- COOKIE_USER_TOKEN (4 文件)
- MIME_JSON (22+ 文件)
- LS_KEY_WAS_LOGGED_IN (2 文件)
- SSE_DELIMITER_LENGTH (2 文件)
- INDEX_NOT_FOUND (3 文件)
- MIN_PASSWORD_LENGTH (2 文件)

来源: docs/superpowers/specs/2026-06-25-const-audit-design.md §3.1 + §3.2
不抽单文件项 (MIME_ZIP 等) 避免过度设计.
不建 lib/routes.ts / lib/chat/const.ts (本 spec 已删 Phase 4/5)."
```

---

### Task 2 (P2): 修复 const 重复定义 (1 commit, 改 9 文件)

**Files**:
- Modify: `packages/web/app/[locale]/_actions/account.ts`
- Modify: `packages/web/app/[locale]/_actions/account-settings.ts`
- Modify: `packages/web/lib/hooks/use-lookup.ts`
- Modify: `packages/web/lib/hooks/use-pagination.ts`
- Modify: `packages/web/components/common/table/use-table-pagination.ts`
- Modify: `packages/web/components/common/input/app-file-dropzone.tsx`
- Modify: `packages/web/components/ui/progress.tsx`
- Modify: `packages/web/app/api/chat/messages/route.ts`
- Modify: `packages/web/app/api/knowledge/batch/route.ts`

**目标**: 删除 10 处"重复定义 const/index.ts 已有常量"的代码, 改 import.

**改动**:

- [ ] **Step 2.1: 改 app/[locale]/_actions/account.ts**

打开文件, 找到 L22-31 段:

```typescript
// --- 常量 ---
const SECONDS_PER_MINUTE = 60;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;
const COOKIE_EXPIRY_DAYS = 7;
const COOKIE_MAX_AGE = SECONDS_PER_MINUTE * MINUTES_PER_HOUR * HOURS_PER_DAY * COOKIE_EXPIRY_DAYS; // 7 天
const HTTP_UNAUTHORIZED = 401;
const MIN_PASSWORD_LENGTH = 8;

const COOKIE_NAME = "rag_user_token";
```

**改动**:
1. 文件顶部 import 区 (已经有别的 import), 在合适位置加:
   ```typescript
   import { HTTP_UNAUTHORIZED, MIN_PASSWORD_LENGTH, COOKIE_USER_TOKEN, SECONDS_PER_MINUTE, MINUTES_PER_HOUR, HOURS_PER_DAY } from "@/const";
   ```
   (按字母排序放; 跟现有 import 不冲突就新增一行)
2. 删 L23-29 的 6 个 const (`SECONDS_PER_MINUTE` / `MINUTES_PER_HOUR` / `HOURS_PER_DAY` / `HTTP_UNAUTHORIZED` / `MIN_PASSWORD_LENGTH` / `COOKIE_NAME` 中除 `COOKIE_EXPIRY_DAYS` 和 `COOKIE_MAX_AGE` 外)
3. `COOKIE_MAX_AGE` 的计算改成:
   ```typescript
   const COOKIE_MAX_AGE = COOKIE_EXPIRY_DAYS * HOURS_PER_DAY * MINUTES_PER_HOUR * SECONDS_PER_MINUTE;
   ```
   (复用 import 的全局常量)
4. 文件下面所有引用 `COOKIE_NAME` → `COOKIE_USER_TOKEN` (用 Edit replace_all 或逐处改)

**注意**: `COOKIE_EXPIRY_DAYS = 7` 保留 (单文件用, 不抽全局).

- [ ] **Step 2.2: 改 app/[locale]/_actions/account-settings.ts**

找文件顶部 const 区 (PASSWORD_MIN_LENGTH=8 等), 删本地 `HTTP_UNPROCESSABLE_ENTITY=422 / HTTP_BAD_REQUEST=400` 定义, 改 import.

如果 `HTTP_UNPROCESSABLE_ENTITY` / `HTTP_BAD_REQUEST` 在 const/index.ts 里**已有** (查 const/index.ts 第 49-50 行):
```typescript
export const HTTP_BAD_REQUEST = 400;
export const HTTP_UNPROCESSABLE_ENTITY = 422;
```
✅ 已有, 删局部, import.

如果**没有** (查完发现没), 跳过本 step (不用改这个文件).

- [ ] **Step 2.3: 改 lib/hooks/use-lookup.ts**

L15-19:
```typescript
const MINUTES = 5;
const SECONDS_PER_MINUTE = 60;
const MS_PER_SECOND = 1000;
// 5 分钟 = 后端 Redis LookupCache TTL; staleTime 内不重复发请求.
const FIVE_MIN = MINUTES * SECONDS_PER_MINUTE * MS_PER_SECOND;
```

**改动**:
1. 顶部 import 加 `SECONDS_PER_MINUTE, MS_PER_SECOND` from "@/const"
2. 删局部 `SECONDS_PER_MINUTE` 和 `MS_PER_SECOND` (留 `MINUTES = 5` 和 `FIVE_MIN` 计算)
3. `FIVE_MIN` 计算改成复用 import 的全局:
   ```typescript
   const FIVE_MIN = FIVE * SECONDS_PER_MINUTE * MS_PER_SECOND;
   ```
   (因为全局有 `FIVE = 5`)

- [ ] **Step 2.4: 改 lib/hooks/use-pagination.ts**

L3 `const DEFAULT_PAGE_SIZE = 20;` → 删, 顶部加 `import { DEFAULT_PAGE_SIZE } from "@/const"`.

- [ ] **Step 2.5: 改 components/common/table/use-table-pagination.ts**

L21 `const PAGE_SIZE_DEFAULT = 20;` → 删, L4 已有 `import { ZERO } from "@/const/index";`, 改成 `import { DEFAULT_PAGE_SIZE, ZERO } from "@/const";`, L29 引用改 `PAGE_SIZE_DEFAULT` → `DEFAULT_PAGE_SIZE`.

注意 L22 `const PAGE_STEP = 1;` **保留** (业务专属, 单文件用).

- [ ] **Step 2.6: 改 components/common/input/app-file-dropzone.tsx**

L61-63:
```typescript
const KILOBYTE = 1024;
const BYTES_PER_MB = KILOBYTE * KILOBYTE;
const FIRST_INDEX = 0;
```

**改动**:
1. 顶部加 import `ONE_KB, ZERO` from "@/const"
2. 删局部 `KILOBYTE` 和 `FIRST_INDEX`
3. `BYTES_PER_MB = KILOBYTE * KILOBYTE` 改成 `BYTES_PER_MB = ONE_KB * ONE_KB`
4. L114/L124 引用 `FIRST_INDEX` → `ZERO`

- [ ] **Step 2.7: 改 components/ui/progress.tsx**

L10 `const HUNDRED_PERCENT = 100;` → 删, L26 引用 → `HUNDRED`. L6 已有 `import { ZERO } from "@/const";` 改成 `import { HUNDRED, ZERO } from "@/const";`.

- [ ] **Step 2.8: 改 app/api/chat/messages/route.ts**

L15 `const MIN_STR_LENGTH = 1;` → 删, 顶部 import 加 `ONE`, L 引用 `MIN_STR_LENGTH` → `ONE`.

- [ ] **Step 2.9: 改 app/api/knowledge/batch/route.ts**

L25 `const NO_FAILURES = 0;` → 删, 顶部 import 加 `ZERO`, L 引用 → `ZERO`.

- [ ] **Step 2.10: 全套验证**

```bash
cd packages/web
bun run typecheck
bun run lint
bun run test 2>&1 | tail -10
```

预期: 0 error / 0 error / fail 数 == baseline.

- [ ] **Step 2.11: grep 验证**

```bash
cd packages/web
grep -rn "const HTTP_UNAUTHORIZED\|const HTTP_UNPROCESSABLE_ENTITY\|const SECONDS_PER_MINUTE = \|const MS_PER_SECOND = \|const DEFAULT_PAGE_SIZE = \|const KILOBYTE = \|const HUNDRED_PERCENT\|const MIN_STR_LENGTH\|const NO_FAILURES" --include="*.ts" --include="*.tsx" | grep -v "const/index.ts"
```

预期: **0 匹配** (除 const/index.ts 定义外).

- [ ] **Step 2.12: Commit**

```bash
git add packages/web/app/\[locale\]/_actions/account.ts \
        packages/web/app/\[locale\]/_actions/account-settings.ts \
        packages/web/lib/hooks/use-lookup.ts \
        packages/web/lib/hooks/use-pagination.ts \
        packages/web/components/common/table/use-table-pagination.ts \
        packages/web/components/common/input/app-file-dropzone.tsx \
        packages/web/components/ui/progress.tsx \
        packages/web/app/api/chat/messages/route.ts \
        packages/web/app/api/knowledge/batch/route.ts

git commit -m "refactor: 删除 9 处重复定义全局常量的局部 const (改 import)

修复 P0 严重项 (spec §2.3):
- _actions/account.ts: 6 个 (SECONDS/MINUTES/HOURS + HTTP_UNAUTHORIZED + MIN_PASSWORD + COOKIE_NAME)
- _actions/account-settings.ts: 2 个 (HTTP_BAD_REQUEST + HTTP_UNPROCESSABLE_ENTITY)
- hooks/use-lookup.ts: 2 个 (SECONDS_PER_MINUTE + MS_PER_SECOND)
- hooks/use-pagination.ts: 1 个 (DEFAULT_PAGE_SIZE)
- use-table-pagination.ts: 1 个 (PAGE_SIZE_DEFAULT)
- app-file-dropzone.tsx: 2 个 (KILOBYTE + FIRST_INDEX)
- ui/progress.tsx: 1 个 (HUNDRED_PERCENT)
- chat/messages/route.ts: 1 个 (MIN_STR_LENGTH)
- knowledge/batch/route.ts: 1 个 (NO_FAILURES)

0 行为变化 (只是把定义挪到 const/index.ts), 0 测试改动."
```

---

### Task 3 (P3a): 替换 content-type / application.json 字面量 (1 commit)

**Files** (改 ~22 个 route.ts + 2 个 lib 文件):

app/api 下所有用 `content-type` / `Content-Type` / `application/json` 的文件, 加上 `lib/api/config.ts` 和 `lib/chat/memory-integration.ts`.

**目标**: 把字符串字面量替换为 `HEADER_CONTENT_TYPE` 和 `MIME_JSON`, **统一小写**.

**改动**:

- [ ] **Step 3.1: 前置验证**

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/baseline-test-p3.log
```

- [ ] **Step 3.2: 用 Grep 列待改文件清单**

```bash
cd packages/web
grep -rln '"content-type"\|"Content-Type"' --include="*.ts" --include="*.tsx" app lib 2>&1 | grep -v ".test."
```

预期: ~22 个文件.

- [ ] **Step 3.3: 改每个文件 (逐文件 Edit)**

每个文件的改动模式相同:

```typescript
// 改前
headers: { "Content-Type": "application/json" }
// 或
headers: { "content-type": "application/json" }

// 改后 (统一小写)
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";
headers: { [HEADER_CONTENT_TYPE]: MIME_JSON }
```

**对每个目标文件**:
1. Read 文件, 找 `"Content-Type"` / `"content-type"` / `"application/json"` 出现位置
2. 顶部 import 区 (若无 `@/const` import) 加 `import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";` (按字母排序)
3. 用 Edit replace_all 替换所有 `"content-type"` → `HEADER_CONTENT_TYPE` 和 `"Content-Type"` → `HEADER_CONTENT_TYPE`
4. 用 Edit replace_all 替换所有 `"application/json"` → `MIME_JSON`

**特别文件 `app/api/[...path]/route.ts`** (已经有部分 import):
- 已经有 `import { HTTP_BAD_GATEWAY, HTTP_NO_CONTENT, HTTP_NOT_FOUND, ZERO } from "@/const";`
- 改成 `import { HEADER_CONTENT_TYPE, HTTP_BAD_GATEWAY, HTTP_NO_CONTENT, HTTP_NOT_FOUND, MIME_JSON, ZERO } from "@/const";` (按字母排序)
- 改 content-type (3 处) + application/json (2 处)

**特别文件 `lib/chat/memory-integration.ts`**:
- Read 看现有 import 区, 加 `HEADER_CONTENT_TYPE, MIME_JSON`
- 改 content-type + application/json 字面量

- [ ] **Step 3.4: 全套验证**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
bun run test 2>&1 | tail -10
```

预期: fail 数 == baseline.

- [ ] **Step 3.5: grep 验证**

```bash
cd packages/web
grep -rn '"application/json"\|"Content-Type"\|"content-type"' --include="*.ts" --include="*.tsx" app lib 2>&1 | grep -v ".test." | grep -v "const/index.ts"
```

预期: **0 匹配** (除 const 定义).

- [ ] **Step 3.6: Commit**

```bash
git add -A packages/web/app packages/web/lib
git diff --cached --stat  # 确认改动范围

git commit -m "refactor: 替换 22+ 处 application/json + 27+ 处 content-type 字面量

- 统一 content-type 为小写 (HTTP/2 RFC 7540)
- 改用 import HEADER_CONTENT_TYPE / MIME_JSON from @/const
- 覆盖: 所有 app/api route.ts + lib/api/config.ts + lib/chat/memory-integration.ts

验证: grep 0 匹配除 const/index.ts 定义外
0 测试改动, fail 数 == baseline."
```

---

### Task 4 (P3b): 替换 cookie / auth header 字面量 (1 commit)

**Files** (6 个):
- `app/api/[...path]/route.ts` (1 处 COOKIE_USER_TOKEN + 1 处 HEADER_X_USER_TOKEN)
- `lib/api/auth.server.ts` (2 处 COOKIE_USER_TOKEN + 1 处 HEADER_X_USER_TOKEN)
- `app/[locale]/_actions/account.ts` (1 处 COOKIE_USER_TOKEN)
- `lib/chat/memory-integration.ts` (1 处 COOKIE_USER_TOKEN + 1 处 HEADER_X_USER_TOKEN)
- `app/api/chat/messages/route.ts` (1 处 HEADER_X_CHAT_TOKEN)
- `lib/api/chat.ts` (1 处 HEADER_X_CHAT_TOKEN)

**改动**:

- [ ] **Step 4.1: 前置验证**

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/baseline-test-p3b.log
```

- [ ] **Step 4.2: 改 6 个文件**

每个文件改动模式:

```typescript
// 改前
const user = jar.get("rag_user_token")?.value;
out["x-user-token"] = tokenValue;

// 改后
import { COOKIE_USER_TOKEN, HEADER_X_USER_TOKEN } from "@/const";
const user = jar.get(COOKIE_USER_TOKEN)?.value;
out[HEADER_X_USER_TOKEN] = tokenValue;
```

**逐文件**:

1. **`app/api/[...path]/route.ts`** (已有 `HEADER_CONTENT_TYPE, MIME_JSON` import, 加 `COOKIE_USER_TOKEN, HEADER_X_USER_TOKEN`):
   - L61 `jar.get("rag_user_token")` → `jar.get(COOKIE_USER_TOKEN)`
   - L65 `out["x-user-token"] = tokenValue;` → `out[HEADER_X_USER_TOKEN] = tokenValue;`

2. **`lib/api/auth.server.ts`**:
   - Read 文件, 顶部 import 加 `COOKIE_USER_TOKEN, HEADER_X_USER_TOKEN`
   - L10 `jar.get("rag_user_token")` → `jar.get(COOKIE_USER_TOKEN)`
   - L21 `jar.get("rag_user_token")` → 同上 (replace_all)
   - L25 `headers["x-user-token"]` → `headers[HEADER_X_USER_TOKEN]`

3. **`app/[locale]/_actions/account.ts`** (P2 已改 import, 加 `COOKIE_USER_TOKEN`):
   - 已经有 import `COOKIE_USER_TOKEN` from "@/const" (P2 Step 2.1 加的)
   - 文件内引用 `COOKIE_NAME` → `COOKIE_USER_TOKEN` (replace_all, P2 已改)

4. **`lib/chat/memory-integration.ts`** (P3a 已加 HEADER_CONTENT_TYPE/MIME_JSON import):
   - Read 看现有 import, 顶部 import 加 `COOKIE_USER_TOKEN, HEADER_X_USER_TOKEN`
   - L49 `getCookie("rag_user_token")` → `getCookie(COOKIE_USER_TOKEN)`
   - L52 `"x-user-token"` → `HEADER_X_USER_TOKEN`

5. **`app/api/chat/messages/route.ts`** (P3a 已改 content-type, P2 已加 ONE):
   - Read 看现有 import, 顶部 import 加 `HEADER_X_CHAT_TOKEN`
   - L63 `"x-chat-token"` → `HEADER_X_CHAT_TOKEN`

6. **`lib/api/chat.ts`**:
   - Read 文件, 顶部 import 加 `HEADER_X_CHAT_TOKEN`
   - L29 `"x-chat-token"` → `HEADER_X_CHAT_TOKEN`

- [ ] **Step 4.3: 全套验证**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
bun run test 2>&1 | tail -10
```

- [ ] **Step 4.4: grep 验证**

```bash
cd packages/web
grep -rn '"rag_user_token"\|"x-user-token"\|"x-chat-token"' --include="*.ts" --include="*.tsx" app lib 2>&1 | grep -v ".test." | grep -v "const/index.ts"
```

预期: **0 匹配**.

- [ ] **Step 4.5: Commit**

```bash
git add packages/web/app/api/\[...path\]/route.ts \
        packages/web/lib/api/auth.server.ts \
        packages/web/app/\[locale\]/_actions/account.ts \
        packages/web/lib/chat/memory-integration.ts \
        packages/web/app/api/chat/messages/route.ts \
        packages/web/lib/api/chat.ts

git commit -m "refactor: 替换 cookie/auth header 字面量为全局常量

- COOKIE_USER_TOKEN (4 文件, 跨 account.ts + memory-integration.ts + auth.server.ts + catch-all)
- HEADER_X_USER_TOKEN (3 文件, 同上)
- HEADER_X_CHAT_TOKEN (2 文件, chat/messages/route.ts + lib/api/chat.ts)

验证: grep 0 匹配除 const/index.ts 定义外."
```

---

### Task 5 (P3c): 替换 localStorage key + 密码长度 (1 commit)

**Files** (5 个):
- `components/auth/auth-bootstrap.tsx` (1 处 LS_KEY_WAS_LOGGED_IN)
- `components/user-menu.tsx` (1 处 LS_KEY_WAS_LOGGED_IN)
- `app/[locale]/_actions/account.ts` (P2 已用 MIN_PASSWORD_LENGTH, P3b 已用 COOKIE_USER_TOKEN; 本 task 不用再改这个文件)
- `app/[locale]/_actions/account-settings.ts` (1 处 MIN_PASSWORD_LENGTH)
- `app/[locale]/reset-password/page.tsx` (1 处 MIN_PASSWORD_LENGTH)

**改动**:

- [ ] **Step 5.1: 前置验证**

```bash
cd packages/web
bun run test 2>&1 | tee /tmp/baseline-test-p3c.log
```

- [ ] **Step 5.2: 改 5 个文件**

**逐文件**:

1. **`components/auth/auth-bootstrap.tsx`**:
   - Read 文件, 顶部 import 加 `LS_KEY_WAS_LOGGED_IN` from "@/const"
   - 替换 `"rag_was_logged_in"` → `LS_KEY_WAS_LOGGED_IN` (replace_all)

2. **`components/user-menu.tsx`**:
   - Read 文件, 顶部 import 加 `LS_KEY_WAS_LOGGED_IN` from "@/const"
   - 替换 `"rag_was_logged_in"` → `LS_KEY_WAS_LOGGED_IN` (replace_all)

3. **`app/[locale]/_actions/account.ts`** (P2 已改, 无需再动; skip)

4. **`app/[locale]/_actions/account-settings.ts`** (P2 已加 import):
   - 检查现有 import 是否已含 `MIN_PASSWORD_LENGTH`, 没有则加
   - 替换 `const PASSWORD_MIN_LENGTH = 8;` → 删, L197 引用 → `MIN_PASSWORD_LENGTH`

5. **`app/[locale]/reset-password/page.tsx`**:
   - Read 文件, 顶部 const 区 `const PASSWORD_MIN_LENGTH = 8;` → 删
   - 顶部 import 加 `MIN_PASSWORD_LENGTH` from "@/const"
   - L 引用 → `MIN_PASSWORD_LENGTH`

- [ ] **Step 5.3: 全套验证**

```bash
cd packages/web
bun run format
bun run lint:fix
bun run typecheck
bun run test 2>&1 | tail -10
```

- [ ] **Step 5.4: grep 验证**

```bash
cd packages/web
grep -rn '"rag_was_logged_in"\|const PASSWORD_MIN_LENGTH\|const MIN_PASSWORD_LENGTH' --include="*.ts" --include="*.tsx" 2>&1 | grep -v ".test." | grep -v "const/index.ts"
```

预期: **0 匹配**.

- [ ] **Step 5.5: Commit**

```bash
git add packages/web/components/auth/auth-bootstrap.tsx \
        packages/web/components/user-menu.tsx \
        packages/web/app/\[locale\]/_actions/account-settings.ts \
        packages/web/app/\[locale\]/reset-password/page.tsx

git commit -m "refactor: 替换 localStorage key + 密码长度常量化

- LS_KEY_WAS_LOGGED_IN (2 文件, auth-bootstrap + user-menu)
- MIN_PASSWORD_LENGTH (3 文件, account.ts + account-settings.ts + reset-password.tsx)

验证: grep 0 匹配除 const/index.ts 定义外."
```

---

## 验收总表

| 维度 | 验收命令 | 预期 |
|---|---|---|
| const/index.ts 增量 | `grep -c '^export const' packages/web/const/index.ts` | 35 + 9 = 44 项 |
| 重复定义清理 | `grep -rn "const HTTP_UNAUTHORIZED\|const KILOBYTE\|const HUNDRED_PERCENT\|const NO_FAILURES" packages/web --include="*.ts" --include="*.tsx" \| grep -v const/index.ts \| wc -l` | 0 |
| content-type / json 替换 | `grep -rn '"application/json"\|"content-type"\|"Content-Type"' packages/web/app packages/web/lib --include="*.ts" \| grep -v const/index.ts \| wc -l` | 0 |
| cookie / header 替换 | `grep -rn '"rag_user_token"\|"x-user-token"\|"x-chat-token"' packages/web --include="*.ts" \| grep -v const/index.ts \| grep -v .test. \| wc -l` | 0 |
| LS_KEY / password 替换 | `grep -rn '"rag_was_logged_in"\|const PASSWORD_MIN_LENGTH' packages/web --include="*.ts" --include="*.tsx" \| grep -v const/index.ts \| wc -l` | 0 |
| format | `bun run format` | 0 报错 |
| lint | `bun run lint` | 0 报错 |
| typecheck | `bun run typecheck` | 0 error |
| 全套测试 | `bun run test` | fail 数 == baseline |
| 调用方 0 改动 (硬约束) | `git diff packages/web/messages packages/web/components/ui/alert-dialog.tsx` 等 | 空 |

## 关联文档

- Spec: [docs/superpowers/specs/2026-06-25-const-audit-design.md](../../specs/2026-06-25-const-audit-design.md)
- 上游 spec: [docs/superpowers/specs/2026-06-19-code-quality-cleanup-design.md](../../specs/2026-06-19-code-quality-cleanup-design.md)
- 项目铁律: [packages/web/CLAUDE.md](../../../../packages/web/CLAUDE.md)
- const/index.ts 命名规范: 现有文件头部注释 (基础数字 / 时间换算 / HTTP 状态码 / 端口 / 分页 / localStorage key)

## Self-Review

### Spec coverage

| Spec 章节 | 覆盖 task |
|---|---|
| §〇 前置改动 | 已 commit (`f3f445e3`), 不在本 plan 范围 |
| §2.3 P0 重复定义 | Task 2 (9 文件 / 10 处) |
| §3.1 HTTP/MIME/Storage | Task 1 (8 项) + Task 3 + Task 4 |
| §3.2 鉴权 | Task 1 (1 项 MIN_PASSWORD_LENGTH) + Task 5 |
| §3.3 路由 (不抽) | 不实施 (已判定过度设计) |
| §3.4 chat 业务 (不抽 lib/chat/const.ts) | Task 1 (2 项 SSE_DELIMITER_LENGTH + INDEX_NOT_FOUND 加到 const/index.ts) |
| §四 Phase 1 | Task 1 |
| §四 Phase 2 | Task 2 |
| §四 Phase 3a | Task 3 |
| §四 Phase 3b | Task 4 |
| §四 Phase 4 (删除) | 不实施 |
| §四 Phase 5 (删除) | 不实施 |
| §六 R1 content-type 小写 | Task 3 Step 3.3 |
| §七 验收门 | 验收总表 |

✅ 全部覆盖, 不漏 Phase 4/5 (已删)

### Placeholder scan

- ✅ 0 TBD / TODO / "fill in"
- ✅ 每个 Step 有具体文件路径 + 行号 + 命令
- ✅ import 按字母排序 (符合 oxlint sort-imports)
- ✅ 0 测试 fixture 改动
- ✅ 0 messages/{zh,en}.json 改动

### Type consistency

- ✅ `HEADER_CONTENT_TYPE` / `HEADER_X_USER_TOKEN` / `HEADER_X_CHAT_TOKEN` / `COOKIE_USER_TOKEN` / `MIME_JSON` / `LS_KEY_WAS_LOGGED_IN` / `SSE_DELIMITER_LENGTH` / `INDEX_NOT_FOUND` / `MIN_PASSWORD_LENGTH` 9 项类型一致 (字面量类型或 number)
- ✅ 复用现有 `SECONDS_PER_MINUTE / MINUTES_PER_HOUR / HOURS_PER_DAY / ONE / ZERO / ONE_KB / HUNDRED / DEFAULT_PAGE_SIZE / HTTP_UNAUTHORIZED / HTTP_BAD_REQUEST / HTTP_UNPROCESSABLE_ENTITY` 11 项 (P2 用)
- ✅ Task 2 Step 2.1 用 `COOKIE_USER_TOKEN` 替换 `COOKIE_NAME` (P2 + P3b 合并)

## 执行 handoff

Plan 完成. 2 种执行方式:

1. **Subagent-Driven (推荐)**: 派 subagent 实施 Task 1-5, 主会话 review
2. **Inline Execution**: 当前会话按 Task 1 → 2 → 3 → 4 → 5 顺序跑

由于本 plan 是 5 个独立 commit, 2 种方式差异明显:
- **Subagent**: 5 个 subagent 各跑 1 个 Task (并行, 但 git 历史会复杂)
- **Inline**: 当前会话串行 (每 commit < 200 行, 总改动 ~30 文件, 估算 5 个 commit × 10 min = ~50 min)

推荐 **inline execution**: Task 1-5 全部在当前会话, 每个 commit 前跑全套验证. Subagent 适合"已写好代码让 review", 不适合"边写边测".

请选择执行方式.
