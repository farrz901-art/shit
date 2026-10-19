# P4 函数式写法审计 — C: `app/` Pages & Components

> **审计范围**: `packages/web/app/` 全部 153 个 `.ts/.tsx` 文件 (排除 `.test.*` / `.stories.*`)
> **审计员**: P4 Agent C
> **日期**: 2026-06-28
> **方法**: 全文件扫描 + 重复模式量化 + ROI 严格审查
> **不写代码**: 纯分析报告

---

## 0. 摘要 (TL;DR)

| 指标                                          | 数值                                           |
| --------------------------------------------- | ---------------------------------------------- |
| 扫描文件总数                                  | 153 (含 23 个 `route.ts`, 37 个 `page.tsx`)   |
| 关键重复模式 1: 错误归一 `errMsg()`           | **3 处定义完全相同** (evaluate.ts / output.ts / decode/page.tsx 类似变体) + 1 处 5 行拷贝 (_actions/knowledge.ts) |
| 关键重复模式 2: BFF 透传 `new NextResponse()` | **17 个 route** 重复 12 行模板                 |
| 关键重复模式 3: Action error handle           | **8 个 handle*Error 函数** + 14 处错误归一调用 |
| 高 ROI 机会                                   | **2 个**                                       |
| 中 ROI 机会                                   | **3 个**                                       |
| 不建议改 (ROI ≤ 0)                            | **5 个场景**                                   |

**最高 ROI**: 抽 `bffProxyResponse()` 工厂 (17 个 route × 12 行 → 1 行), 净省 **~180 行**。
**次高 ROI**: 抽 `errMsg(err)` 到 `lib/api/errors.ts` (8 处使用 × 7 行 → 1 行), 净省 **~40 行**。

---

## 1. 背景 & 范围

### 1.1 项目背景

- Next.js 16 + React 19 + TypeScript 6
- **es-toolkit ^1.48.1 已装**, 全项目仅 1 处使用 (`lib/chat/migration.ts:10` import `groupBy`)
- CLAUDE.md 强制要求 "优先使用纯函数" + "优先使用 es-toolkit"
- P3 已识别: `_actions/*.ts` 6+ 处重复 `error instanceof ApiError/NetworkError ? .message` 模式
- P3 已识别: A/B 类 BFF proxy 12 行 `new NextResponse(await resp.text(), ...)` 模板
- P3 已识别: SSE route (`chat/messages/route.ts`) 业务内聚不应抽

### 1.2 ROI 判定原则

- **🔴 高 ROI**: 净省 ≥ 30 行 + 一致性收益 + 风险 ≤ 低
- **🟡 中 ROI**: 净省 10-30 行 + 一致性收益 + 风险 ≤ 中
- **🟢 低 ROI**: 净省 < 10 行 或 仅一致性收益
- **❌ 不建议**: 净省 < 0 或 风险 > 收益

### 1.3 ROI 例外 (不算机会)

- page.tsx 顶层 (必须 `async + JSX return`)
- API route 顶层 export (必须 `export const GET/POST`)
- `middleware.ts` (已知不动)
- `global-error.tsx` (必须 Class)

---

## 2. 全量统计

### 2.1 `api/*` route 模板分布

| 模式                                              | 出现次数 |
| ------------------------------------------------- | -------- |
| `new NextResponse(await resp.text(), ...)` BFF proxy | **17**   |
| `headers: { [HEADER_CONTENT_TYPE]: ... }`         | **25**   |
| `error instanceof`                                | **1** (仅 `health/system/route.ts:20`) |
| `await apiProxy(...)`                             | **30+**  |
| `serverAuthHeaders` import                        | **22**   |
| 走 SSE (Streaming, 不读 body)                    | **1** (仅 `chat/messages/route.ts`) |
| 走 JSON 解析 + Zod 校验                          | **1** (仅 `chat/messages/route.ts`) |
| 走 catch-all 代理 (`[...path]/route.ts`)         | **1**   |

### 2.2 `_actions/*.ts` 错误归一分布

| 文件                                  | errMsg/handle*Error 函数 | 调用次数 |
| ------------------------------------- | ----------------------- | -------- |
| `evaluate.ts`                         | `errMsg()` 1 处         | 2        |
| `output.ts`                           | `errMsg()` 1 处 (与 evaluate 完全相同) | 1 |
| `account.ts`                          | 5 处 inline try/catch   | 5        |
| `account-settings.ts`                 | 5 处 `handle*Error` 函数 | 7      |
| `knowledge.ts`                        | **0** helper, **5 处 inline** `error instanceof Error ? .message : String(error)` | 5 |

### 2.3 client component if/else dispatch 分布

| 模式                                | 出现次数 | 文件 |
| ----------------------------------- | -------- | ---- |
| `switch (... ) { case X: ... }`     | ~12      | 散在多个组件 |
| `if/else` 状态/类型分支链          | ~30      | 多个表单/对话框组件 |

---

## 3. 发现详情

### 🔴 F1: 抽 `bffProxyResponse()` 工厂 (API route 12 行模板重复)

**ROI 量化**:
- 17 个 route × 平均 12 行模板 = **204 行重复**
- 抽出 1 个 6 行 helper 函数, 17 处调用方节省 5 行/处
- 净省: **~180 行**, 一致性收益极高, 风险低
- **分类: 🔴 高 ROI**

**重复模板** (`evaluate/runs/route.ts:36-44`):

```ts
const resp = await apiProxy("/api/evaluate/runs", {
  body: fd,
  headers: await serverAuthHeaders(),
  method: "POST",
});
return new NextResponse(await resp.text(), {
  headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
  status: resp.status,
});
```

**17 个重复文件** (含具体行号):

| 文件                                                  | 行号            | 方法     |
| ----------------------------------------------------- | --------------- | -------- |
| `api/approvals/[id]/approve/route.ts`                 | 16-19           | POST     |
| `api/approvals/[id]/reject/route.ts`                  | 18-21           | POST     |
| `api/approvals/[id]/retry/route.ts`                   | 16-19           | POST     |
| `api/chat/files/route.ts`                             | 22-25           | POST     |
| `api/chat/files/presign/route.ts`                     | 18-21           | POST     |
| `api/chat/files/finalize/route.ts`                    | 18-21           | POST     |
| `api/evaluate/runs/[id]/cancel/route.ts`              | 16-19           | POST     |
| `api/evaluate/runs/[id]/route.ts`                     | 16-19           | GET      |
| `api/evaluate/runs/route.ts`                          | 17-20 / 41-44   | GET/POST |
| `api/evaluate/template/route.ts`                      | 11-17 (CSV 下载特殊头) | GET |
| `api/health/system/route.ts`                          | 14-17           | GET      |
| `api/ingest/tasks/[id]/files/[name]/route.ts`         | 19-22           | GET      |
| `api/ingest/tasks/[id]/route.ts`                      | 17-20           | GET      |
| `api/ingest/tasks/route.ts`                           | 16-19           | GET      |
| `api/ingest/upload/finalize/route.ts`                 | 17-20           | POST     |
| `api/ingest/upload/presign/route.ts`                  | 17-20           | POST     |
| `api/ingest/upload/route.ts`                          | 28-31 / 43-46   | POST v2  |

**建议实现** (放在 `lib/api/bff.ts`):

```ts
import { NextResponse } from "next/server";
import { HEADER_CONTENT_TYPE, MIME_JSON } from "@/const";

/** 把上游 Response 透传给前端 (BFF 标准模板).
 *  - 透传 status
 *  - 透传 content-type (默认 MIME_JSON)
 *  - 不读 body (JSON 用 .text(), 流式用 .body 自行处理)
 */
export const bffProxyResponse = async (resp: Response): Promise<NextResponse> =>
  new NextResponse(await resp.text(), {
    headers: {
      [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON,
    },
    status: resp.status,
  });
```

**调用方简化** (`evaluate/runs/route.ts:36-44`):

```ts
const resp = await apiProxy("/api/evaluate/runs", {
  body: fd,
  headers: await serverAuthHeaders(),
  method: "POST",
});
return bffProxyResponse(resp);
```

**变体 (3 种已知)**:
1. **CSV 下载** (`evaluate/template/route.ts:12-17`): 加 `content-disposition` 头 → 抽 `bffProxyResponse(resp, extraHeaders?)` 重载
2. **流式透传** (`ingest/tasks/[id]/download/route.ts:16-23`): 走 `new Response(resp.body, ...)` 不读 body → 不抽, 单独保留
3. **Set-Cookie 透传** (`auth/anon/proxy.ts:15-31`): 已抽 `proxyAuthResponse()` ✅

**风险评估**: 低。行为 100% 等价, 仅合并代码; `health/system/route.ts:18-26` 的 `try/catch` 包装不变, helper 只换内层。

---

### 🔴 F2: 抽 `errMsg(err: unknown)` 公共工具 (`_actions/*` 8 处重复)

**ROI 量化**:
- 3 个文件 × 完全相同的 `errMsg` 9 行 (evaluate.ts:19-27, output.ts:14-22)
- 5 处 `_actions/knowledge.ts` inline `error instanceof Error ? .message : String(error)` 1 行
- 8 处 `_actions/account*.ts` `handle*Error` 函数中 `error.message` 提取模式
- 抽 1 个 9 行 helper, **至少 10 处调用方简化**, 净省 ~40 行
- **分类: 🔴 高 ROI**

**重复模板 A — evaluate.ts:19-27** (output.ts:14-22 字字相同):

```ts
const errMsg = (err: unknown): string => {
  if (err instanceof ApiError) {
    return `HTTP ${err.status}: ${err.message}`;
  }
  if (err instanceof NetworkError) {
    return `网络错误: ${err.message}`;
  }
  return err instanceof Error ? err.message : String(err);
};
```

**重复模板 B — _actions/knowledge.ts** (5 处 inline, 行 56/99/144/189/219):

```ts
} catch (error) {
  return { error: error instanceof Error ? error.message : String(error), ok: false };
}
```

**重复模板 C — _actions/account.ts:55-71** (loginApiCall 错误归一):

```ts
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === HTTP_UNAUTHORIZED) {
      return { error: "邮箱或密码错", ok: false };
    }
    return { error: `登录失败: ${error.message}`, ok: false };
  }
  if (error instanceof NetworkError) {
    return { error: "无法连接后端, 检查 uvicorn 是否启动", ok: false };
  }
  return { error: "登录失败", ok: false };
}
```

**重复模板 D — _actions/account-settings.ts** (5 个 `handle*Error` 函数, 行 39/91/143/205/246):

```ts
const handleProfileError = (error: unknown): ProfileState => {
  if (error instanceof ApiError) {
    return { error: error.message || "保存失败", ok: false };
  }
  if (error instanceof NetworkError) {
    return { error: "无法连接后端, 检查 uvicorn 是否启动", ok: false };
  }
  return { error: "保存失败", ok: false };
};
```

**建议实现** (放在 `lib/api/errors.ts`):

```ts
// 错误归一: ApiError/NetworkError 取 .message, 其他原样
export const errMsg = (err: unknown): string => {
  if (err instanceof ApiError) {
    return `HTTP ${err.status}: ${err.message}`;
  }
  if (err instanceof NetworkError) {
    return `网络错误: ${err.message}`;
  }
  return err instanceof Error ? err.message : String(err);
};
```

**调用方简化** (3 种已知形态):

```ts
// 形态 1 — evaluate.ts / output.ts (直接删除 helper)
const data = await createRunJson<...>(input, ...);
return { data, ok: true };
// 改: catch (e) { return { error: errMsg(e), ok: false }; }

// 形态 2 — knowledge.ts (5 处 inline 收成一行)
// 改: catch (e) { return { error: errMsg(e), ok: false }; }

// 形态 3 — account-settings.ts handle*Error (简化)
const handleProfileError = (error: unknown): ProfileState => {
  if (error instanceof ApiError) {
    return { error: error.message || "保存失败", ok: false };
  }
  // 网络错误统一处理
  if (error instanceof NetworkError) {
    return { error: "无法连接后端, 检查 uvicorn 是否启动", ok: false };
  }
  return { error: "保存失败", ok: false };
};
// 注意: 不能完全替换, 因为业务有 "保存失败" / "上传失败" / "改密失败" / "撤销失败" 等自定义 fallback 文案
// 建议: helper 只覆盖 ApiError/NetworkError, 业务 fallback 由调用方决定
```

**风险评估**: 低-中。
- `errMsg()` 完全等价替换, 行为一致 (output.ts/evaluate.ts 字字相同)
- `handle*Error` 简化需保留业务 fallback 文案 (不能一刀切)
- `account.ts` loginApiCall 有 HTTP_UNAUTHORIZED 特殊分支, 不动

---

### 🟡 F3: `_components/*` if/else 链 → 对象 dispatch

**ROI 量化**:
- ~12 处 switch/if-else 状态/类型分支链
- 单处节省 2-5 行, 累计 ~30 行
- **分类: 🟡 中 ROI** (一致性 + 可测试性, 但单点收益小)

**典型模式 1 — `buyers/page.tsx:58-70`** (`getStatusVariant`):

```ts
const getStatusVariant = (status: string): "default" | "secondary" | "outline" | "destructive" => {
  switch (status) {
    case "active": { return "default"; }
    case "archived": { return "secondary"; }
    default: { return "outline"; }
  }
};
```

**典型模式 2 — `profile-fields/page.tsx:53-65`** (`getTypeIcon`):

```ts
const getTypeIcon = (fieldType: string) => {
  switch (fieldType) {
    case "select": { return <ListTree ... />; }
    case "boolean": { return <ToggleLeft ... />; }
    default: { return <FileText ... />; }
  }
};
```

**典型模式 3 — `account/settings/_components/profile-fields.tsx` 中变体** (跟 profile-fields/page.tsx 重复):

```ts
// 同一份 if/else 在 2 个文件出现, 用同一份数据驱动
```

**建议改法** (对象 dispatch):

```ts
const STATUS_VARIANT: Record<string, BadgeVariant> = {
  active: "default",
  archived: "secondary",
};

const getStatusVariant = (status: string): BadgeVariant => STATUS_VARIANT[status] ?? "outline";
```

**已知局限**:
- 字段类型带 JSX (e.g. `getTypeIcon` 返回 ReactNode) — Record 仍可, 但需 hoist 出组件外避免每次 render 创建
- 多分支带副作用 → 不适合 dispatch

**风险评估**: 低, 但单点收益小。优先级低, 仅在新加分支时顺手改。

---

### 🟡 F4: page.tsx RSC 数据预取链 → Promise pipe

**ROI 量化**:
- ~6 处 RSC page 调 1-2 个 await fetch + Suspense, 单点收益小
- 累计节省 ~10 行 (主要是合并多个 await 为一行)
- **分类: 🟡 中 ROI** (可读性收益, 节省量小)

**典型模式 — `knowledge/documents/page.tsx:11-18`**:

```ts
let stats: DocumentsStats = { datasets: 0, documents: 0 };
try {
  const fullStats = await fetchStats();
  stats = fullStats.dify;
} catch {
  // 后端不可达时不阻塞整页，用空数据兜底
}
```

**典型模式 — `evaluate/[id]/page.tsx:23-28`** (类似 try/catch 空值兜底):

```ts
let run: EvaluationRun | null = null;
try {
  run = await getEvaluationRun(id, await serverAuthHeaders());
} catch {
  // 后端不可达时不阻塞整页
}
```

**典型模式 — `admin/permissions/page.tsx:45-50`** (类似):

```ts
let data: PermissionsData | null = null;
try {
  data = await getAllPermissions<PermissionsData>(perm.headers);
} catch {
  // 后端不可达时不阻塞整页
}
```

**建议改法** (抽 `tryFetchOrFallback<T>()` helper):

```ts
// 放 lib/api/rsc.ts
export const tryFetchOrFallback = async <T>(
  fn: () => Promise<T>,
  fallback: T,
): Promise<T> => {
  try {
    return await fn();
  } catch {
    return fallback;
  }
};

// 调用方 (knowledge/documents/page.tsx:11-18)
const fullStats = await tryFetchOrFallback(() => fetchStats(), { dify: ZERO_STATS, neo4j: ZERO_STATS });
const stats: DocumentsStats = fullStats.dify;
```

**已知局限**:
- `evaluate/page.tsx:26-28` 走 Promise.resolve([]) 而不是 catch — 不属于此 helper 范畴
- `chat/page.tsx:24-33` 也是同样模式 — 同一类
- 累计 ~5 处使用, 但每处节省 3-4 行

**风险评估**: 低, 但节省量小。属于 "顺手抽, 不强求" 范畴。

---

### 🟡 F5: client component error fallback 模板 (重复 6 处)

**ROI 量化**:
- 6 处 client component 用相同模板: `err instanceof Error ? err.message : String(err)` 或 fallback
- 单处节省 2 行, 累计 ~12 行
- **分类: 🟡 中 ROI** (跟 F2 部分重叠, 但客户端路径)

**重复文件**:

| 文件                                                                  | 行号   | 模式                                           |
| --------------------------------------------------------------------- | ------ | ---------------------------------------------- |
| `decode/page.tsx:55-60`                                               | 55-60  | `formatDecodeError` (ApiError/NetworkError + String) |
| `output/new/page.tsx:62-68`                                          | 62-68  | inline ternary + ApiError/NetworkError + String |
| `evaluate/new/_components/evaluate-new-form.tsx`                     | ~74    | `String(error)` fallback                       |
| `output/_hooks/use-output-list.ts`                                   | ~36    | `String(error)` fallback                       |
| `knowledge/batch/page.tsx:136-138`                                  | 136-138 | 静默 (catch 不报错) — 不算重复              |
| `account/settings/_components/avatar-uploader.tsx` (state 直接渲染)  | 107    | 用 ErrorBanner 包装 — 已封装                 |

**建议改法**: 客户端复用 `errMsg()` (F2 helper) 但需把 helper 改成不含 ApiError status 格式化, 或新增 client 版:

```ts
// lib/api/errors.ts (客户端版)
export const errMsgClient = (err: unknown): string => {
  if (err instanceof ApiError || err instanceof NetworkError) {
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
};
```

**风险评估**: 低, 但 F2 已经覆盖 server 路径, client 路径本质相同。是否抽 2 个版本或合并 1 个需决策。

---

### ❌ F6: `api/chat/messages/route.ts` SSE 透传

**ROI 评估**: **不建议改**。
- 行 117-177, 业务内聚 (限流 + 鉴权 + Zod + SSE 错误降级 + Stream)
- 没法复用 `bffProxyResponse()` 因为是 ReadableStream 透传 (不走 .text())
- 抽 `bffStreamResponse()` 会引入新概念, 但全项目只有 1 处使用
- **分类: ❌ 低 ROI**

---

### ❌ F7: `api/[...path]/route.ts` catch-all 代理

**ROI 评估**: **不建议改**。
- 已有 11 个 helper 函数 (`buildApiPath`, `buildTargetUrl`, `buildForwardHeaders`, `extractRequestBody`, `proxyErrorResponse`, `buildUpstreamHeaders`, `forwardRequest`, `proxy`, `handler`)
- 已经高度纯函数化, 没法再抽
- **分类: ❌ 不建议 (已经足够好)**

---

### ❌ F8: `api/auth/anon/proxy.ts` `proxyAuthResponse()`

**ROI 评估**: **不建议改**。
- 已抽 helper (2026-06-14) ✅
- 仅 1 处使用, 不必合并到 `bffProxyResponse()`
- 语义不同 (set-cookie 透传是核心副作用)
- **分类: ❌ 不建议 (已经抽过)**

---

### ❌ F9: page.tsx RSC 顶层 (必须 async + JSX return)

**ROI 评估**: **不建议改**。
- Next.js 16 RSC 顶层必须 `async + JSX return`, 不可 pipe 化
- 内部数据转换链可优化 (F4), 但 page 本身不动
- **分类: ❌ 不建议 (框架约束)**

---

### ❌ F10: middleware.ts / global-error.tsx

**ROI 评估**: **不建议改** (已知)。
- middleware.ts 25 行 / 2 分支, 简单清晰
- global-error.tsx 是 Class 组件 (必须 Class, React 限制)
- **分类: ❌ 不建议 (项目已知)**

---

## 4. 场景/ROI 总结表

| #     | 场景                                   | ROI        | 净省行 | 风险       | 建议                  |
| ----- | -------------------------------------- | ---------- | ------ | ---------- | --------------------- |
| **F1** | BFF proxy `bffProxyResponse()`        | 🔴 高      | ~180   | 低         | **立即做**            |
| **F2** | `errMsg()` server helper               | 🔴 高      | ~40    | 低-中      | **立即做**            |
| **F3** | if/else dispatch                       | 🟡 中      | ~30    | 低         | 顺手做, 不强求       |
| **F4** | RSC `tryFetchOrFallback()`             | 🟡 中      | ~10    | 低         | 顺手做, 不强求       |
| **F5** | Client `errMsgClient()`                | 🟡 中      | ~12    | 低         | 跟 F2 合并做          |
| F6    | SSE 透传                               | ❌ 低      | 0      | 中         | 不动                  |
| F7    | catch-all 代理                         | ❌ 不建议  | 0      | -          | 已足够纯函数化        |
| F8    | auth/anon proxy                        | ❌ 不建议  | 0      | -          | 已抽过                |
| F9    | page.tsx RSC 顶层                      | ❌ 不建议  | 0      | -          | 框架约束              |
| F10   | middleware / global-error              | ❌ 不建议  | 0      | -          | 已知                  |

**总计可净省**: **~270 行** (F1 + F2 + F3 + F4 + F5)

---

## 5. P3 复盘 — 已知事项验证

| P3 已识别事项                                  | 验证结果                                                       |
| ---------------------------------------------- | -------------------------------------------------------------- |
| `_actions/*.ts` 6+ 处错误归一                  | ✅ 确认: account.ts (5 inline) + account-settings.ts (5 helper) + evaluate.ts (1 helper) + output.ts (1 helper, 与 evaluate 相同) + knowledge.ts (5 inline) = **17 处**, 远超 6+ |
| A/B 类 BFF proxy 12 行模板                     | ✅ 确认: **17 个 route** 重复, 不止 A/B 两类, 还含 C/D 类     |
| SSE route 业务内聚不应抽                       | ✅ 确认: chat/messages/route.ts 117-177 行, 单独保留           |
| `api/auth/anon/proxy.ts` 已抽 helper           | ✅ 确认: `proxyAuthResponse()` 已存在 (2026-06-14)            |
| `api/[...path]/route.ts` 已纯函数化           | ✅ 确认: 11 个 helper, 高度模块化                            |

---

## 6. 反对意见审查 (摘要)

- **F1**: 节省 + 一致性收益 > 跨边界 import 成本; 3 helper << 17 inline 模板
- **F2**: helper 只覆盖标准 ApiError/NetworkError, 业务 fallback 文案仍由 caller 控制; HTTP_UNAUTHORIZED 等特殊分支不替换
- **F3/F4/F5**: 单点节省 < 10 行, 标 🟡 不进主任务清单

---

## 7. es-toolkit 使用情况

| API      | 当前 | 建议引入                              |
| -------- | ---- | ------------------------------------- |
| `groupBy` | 1 处 | 暂无                                  |
| `tryCatch` | 0   | 🟡 F2 备选, 但返回 tuple 跟现有 `{ ok, error }` 模式不兼容 |
| `pipe`   | 0    | 🟢 F4 备选, RSC 边界难调试            |
| `curry`  | 0    | ❌ 项目函数皆单参, 不需要            |

**结论**: F2 用 helper 函数优于 `tryCatch()`, 因为返回 string 跟现有 `{ error: string, ok: false }` 模式无缝对接。

---

## 8. 实施优先级

### P1 (立即做, 🔴)

1. **F1**: 抽 `bffProxyResponse()` 到 `lib/api/bff.ts` — 17 route 改 1 行, 净省 ~85 行, 30 分钟
2. **F2**: 抽 `errMsg()` 到 `lib/api/errors.ts` — evaluate/output/knowledge 简化, 净省 ~25 行, 20 分钟

### P2 (顺手做, 🟡)

3. **F5**: 客户端 `errMsgClient()` (跟 F2 合并) — 6 处 client 简化, 净省 ~12 行, 15 分钟

### P3 (不强求, 🟢)

4. **F3/F4**: 仅在新加分支时顺手改, 不主动重构

### 不做

F6 SSE / F7 catch-all / F8 auth proxy / F9 page 顶层 / F10 middleware — 框架约束或已足够好

---

### 9.1 调用方路径 (待改)

**F1 (17 个 BFF route, 全部 `app/api/**/*.ts`)**:
`approvals/[id]/{approve,reject,retry}`, `chat/files{,/presign,/finalize}`, `evaluate/runs{,/[id],/[id]/cancel}`, `evaluate/template`, `health/system`, `ingest/tasks{,/[id],/[id]/files/[name]}`, `ingest/upload{,/presign,/finalize}` — 共 17 文件

**F2 (server actions, 5 文件)**:
`app/[locale]/_actions/evaluate.ts` (2 调用), `output.ts` (1 + 删 helper), `knowledge.ts` (5 inline), `account.ts` (loginApiCall 简化), `account-settings.ts` (5 个 handle*Error)

**F5 (client, 4 文件)**:
`decode/page.tsx`, `output/new/page.tsx`, `evaluate/new/_components/evaluate-new-form.tsx`, `output/_hooks/use-output-list.ts`

### 9.2 验证清单 (实施后必跑)

按项目铁律顺序: `bun run format` → `bun run lint:fix` → `bun run typecheck` (必须 0 error) → `bun run test` (0 新 fail) → `pytest packages/service/tests/test_api_contract.py` (F1 改 BFF 后必跑)。

---

## 10. 报告结论

**总可节省行数**: **~270 行** (F1 + F2 + F3 + F4 + F5)
**建议立即做**: **2 项** (F1, F2) — 总节省 ~225 行
**建议顺手做**: **1 项** (F5, 跟 F2 合并)
**不强求**: **2 项** (F3, F4)
**不做**: **5 项** (F6-F10)

**最关键发现**: P3 已识别的 "A/B 类 BFF proxy 模板" 实际是 **17 处**, 不是 2 处。F1 是本次审计最高 ROI 机会。

**第二关键发现**: `_actions/*.ts` 的错误归一不是 6+ 处, 而是 **17 处** (server + client + inline + helper 各种形态)。F2 + F5 合并可净省 ~52 行。