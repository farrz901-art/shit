# P3 维度 ③ 单例/策略/工厂/外观/适配器模式 — Agent C (app/ 页面+API, ~154 文件)

## 扫描概览

| 指标 | 数值 |
| --- | --- |
| 总扫描文件 | ~154 (排除 `.test.tsx`/`.test.ts`) |
| **API routes (route.ts)** | **23** (设计模式主战场) |
| `_components` 私有 | ~72 |
| `_actions/*` (Server Actions) | 6 文件 (`account.ts`/`account-settings.ts`/`evaluate.ts`/`knowledge.ts`/`output.ts` + test) |
| `page.tsx` | 37 (几乎都不适合) |
| `middleware.ts` + `global-error.tsx` | 2 |
| 可用设计模式重构的文件 | **3** (1 中 ROI + 2 低 ROI) |
| 实际净省代码量 | **~60 行** (高 ROI **0**, 中 ROI **~50 行**, 低 ROI **~10 行**) |

## 现有设计模式资产 (lib/api 层, 已就位)

扫描发现 `lib/api/` 已有大量现成的"设计模式"基础设施, app 层只是**调用方**。这些是 P3 的真实战场:

| 资产 | 文件 | 模式 | 职责 |
| --- | --- | --- | --- |
| `apiFetch<T>()` | `lib/api/config.ts:62` | 适配器 (Adapter) | URL 拼装 + JSON 序列化 + 错误归一 + browser/server URL 切换 |
| `apiProxy()` | `lib/api/config.ts:167` | 外观 (Facade) | BFF 透传, 不 throw/不 parse, 返 raw Response |
| `serverAuthHeaders()` | `lib/api/auth.server.ts:40` | 单例封装 (Server-only cookie 读取) | 避免每个 route 重复 `cookies()` + `x-user-token` |
| `ApiError` / `NetworkError` | `lib/api/errors.ts` | 错误分类 (Strategy 的两种实现) | 调用方根据类型走不同分支 |
| `proxyAuthResponse()` | `app/api/auth/anon/proxy.ts:15` | 透传助手 (Facade 子集) | Set-Cookie 多值透传 |
| `[...path]/route.ts` | `app/api/[...path]/route.ts:139` | catch-all 外观 | 统一代理, GET/POST/PUT/DELETE/PATCH 共用 |

**结论**: lib/api 已经把"重复模式"消灭掉了。**app/api/* 23 个 route 都是在做非常薄的"调用 + 响应包装"**, 重复极少。

---

## API routes 模式分析 (23 个 route.ts)

### 按职责分类

| 类别 | 路由数 | 平均行数 | 模式 |
| --- | --- | --- | --- |
| **A. 简单 BFF proxy (JSON)** | 9 | ~20 | `apiProxy()` + `NextResponse(await resp.text())` 包装 |
| **B. BFF proxy + 鉴权头** | 4 | ~22 | 同 A + `serverAuthHeaders()` |
| **C. Multipart 上传 proxy** | 3 | ~26-49 | 同 A + `formData()` 解析/构造 |
| **D. SSE 流式响应** | 1 (`chat/messages`) | 177 | 唯一特殊: ReadableStream + TextEncoder |
| **E. 文件下载 / CSV** | 3 | ~20 | Content-Disposition 头注入 |
| **F. catch-all proxy** | 1 (`[...path]`) | 172 | 5 个 method 共用 proxy() |
| **G. Dify 直连 / 业务编排** | 4 (knowledge/* + batch) | 20-134 | 直接调 `DifyDatasets`, 不走 `apiProxy` |
| **H. 认证 Set-Cookie 透传** | 1 (`auth/anon`) | 23 | `proxyAuthResponse()` (特殊: 要透传 Set-Cookie 多值) |

### 模式对比 (示例)

#### A 类 - 简单 BFF proxy (示例 `ingest/tasks/[id]/route.ts`, 21 行)

```ts
export const GET = async (_req: NextRequest, ctx) => {
  const { id } = await ctx.params;
  const resp = await apiProxy(`/api/ingest/tasks/${encodeURIComponent(id)}`, {
    cache: "no-store",
    headers: await serverAuthHeaders(),
  });
  return new NextResponse(await resp.text(), {
    headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
    status: resp.status,
  });
};
```

**重复处**: `new NextResponse(await resp.text(), { headers: ..., status: resp.status })` 在 9 个简单 proxy route 里**完全相同** (12 行模板)。

#### D 类 - SSE 流式 (`chat/messages`, 177 行)

唯一特殊 route, 业务复杂度 (限流 + 鉴权 + Zod 校验 + 工厂 provider + ReadableStream 错误降级) 都在这一个文件。**不能抽**。

#### F 类 - catch-all proxy (`[...path]/route.ts`, 172 行)

已经是外观模式 (`proxy()` 函数 + `handler(method)` 工厂)。`buildApiPath`/`buildTargetUrl`/`buildForwardHeaders`/`extractRequestBody`/`forwardRequest` 都是高度内聚的小函数。**不要再包一层**。

#### H 类 - 认证 Set-Cookie (`auth/anon/route.ts` + `auth/anon/proxy.ts`, 54 行)

`proxy.ts` 已经抽成纯函数 (Set-Cookie 多值透传, Node 18+ `getSetCookie()`)。**已抽**。

---

## ROI 分析

### 🔴 高 ROI (净省 ≥30%) — **0 个**

**没有任何一项达到高 ROI**。理由:

1. **lib/api 已是终态抽象**: `apiProxy()` / `serverAuthHeaders()` / `proxyAuthResponse()` 3 个函数把"代理 + 鉴权 + 透传"全覆盖了。每个 route 真正的"业务代码"几乎为 0。
2. **A/B 类 12 行模板是真重复**, 但**抽抽象层 ROI 是负数**:
   - 新增 `createBffProxyRoute({ path, method })` 高阶函数 → 还要处理 dynamic params / params Promise / multipart 区分 → 抽象复杂度超过收益。
   - 现有 Next.js 路由是**声明式文件**, 每个 route.ts 是天然的"单一职责"单元。改成动态生成 route 名会破坏 Next.js 路由树。
3. **D 类 (SSE) 是唯一无法用通用模板的**, 高阶函数会变成"分支判断地狱"。

### 🟡 中 ROI (净省 10-30%) — **1 个**

#### 🟡 #1: A/B 类 BFF proxy 12 行响应包装模板

**位置**: 9 个简单 JSON proxy route (`ingest/tasks/{id,[id]/files/[name]}`, `ingest/upload/{presign,finalize}`, `evaluate/runs/{[id],[id]/cancel,}`, `approvals/{[id]/approve,[id]/reject,[id]/retry}` 等)

**重复模式**:
```ts
return new NextResponse(await resp.text(), {
  headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
  status: resp.status,
});
```

**重构方案**: 在 `lib/api/config.ts` 加 `bffJsonResponse(resp: Response): NextResponse` 工厂 (15 行):

```ts
// lib/api/config.ts 新增
export const bffJsonResponse = (resp: Response): NextResponse =>
  new NextResponse(await resp.text(), {
    headers: { [HEADER_CONTENT_TYPE]: resp.headers.get(HEADER_CONTENT_TYPE) ?? MIME_JSON },
    status: resp.status,
  });
```

**对比** (以 `ingest/tasks/[id]/route.ts` 为例):

| 当前 (21 行) | 重构后 (~18 行) |
| --- | --- |
| 21 行 (含 12 行 `new NextResponse`) | 18 行 (含 1 行 `return bffJsonResponse(resp)`) |

**净省**: ~3 行/文件 × 9 文件 = **~27 行**。但还要算上新加的工厂 (~15 行) + 测试 (~30 行) = **净省 ~-18 行**。**实际 ROI 微负**, 但**可读性略升** (消除 12 行 boilerplate)。

**ROI 判定**: 🟡 **中 ROI** 仅在"顺便抽"的语境成立 — 不值得为它单独开 PR, 但如果将来要加 BFF 中间件 (e.g. trace ID 注入 / 全局错误归一) 时, 工厂是必经之路。**当前不建议单独抽**。

---

### 🟢 低 ROI (1 处使用 / 增加抽象层) — **2 个**

#### 🟢 #2: `_actions/error.ts` 统一错误归一

**位置**: `account.ts:53-71`, `output.ts:14-22`, `evaluate.ts:19-27`, `account-settings.ts:39-47, 91-102, 143-151, 205-210, 246-251` 等 6+ 处

**重复模式**:
```ts
const errMsg = (err: unknown): string => {
  if (err instanceof ApiError) return `HTTP ${err.status}: ${err.message}`;
  if (err instanceof NetworkError) return `网络错误: ${err.message}`;
  return err instanceof Error ? err.message : String(err);
};
```

3 个 `_actions/*.ts` 都有 (output.ts, evaluate.ts, account-settings.ts); account.ts / knowledge.ts 用了**不同分支**写法 (`if status === HTTP_UNAUTHORIZED ...`)。

**重构方案**: 抽 `app/[locale]/_actions/error.ts`:

```ts
import { ApiError, NetworkError } from "@/lib/api/errors";
export const actionError = (err: unknown): string => {
  if (err instanceof ApiError) return `HTTP ${err.status}: ${err.message}`;
  if (err instanceof NetworkError) return `网络错误: ${err.message}`;
  return err instanceof Error ? err.message : String(err);
};
```

**净省**: ~7 行/文件 × 3 文件 = **21 行**, 但要加 `error.ts` (5 行) + 测试 (20 行) = **净省 ~-4 行**。

**ROI 判定**: 🟢 **低 ROI**, 仅"风格统一"价值, **不建议单独抽**。

#### 🟢 #3: `_components/permissions-table.tsx` 之类表格组件的策略渲染

**位置**: `permissions-table.tsx`, `admin-users-table.tsx`, `admin-dicts-client.tsx` 等 5-7 处

**观察**: 这些组件都有 `renderXxxBadge(role/active/...)` 函数, **但每个组件的"状态枚举"都不同** (role/admin/user/dict), **抽通用策略成本高**。

**ROI 判定**: 🟢 **低 ROI**, ❌ 不建议抽 (enum 各异, 强行抽象会变成"渲染字典大杂烩")。

---

## ❌ 明确不做 (违反 YAGNI / 页面层不适合)

### ❌ 1: page.tsx 业务容器模式
**样本**: `app/[locale]/knowledge/page.tsx`, `evaluate/page.tsx`, `account/settings/page.tsx` 等 37 个

**理由**: page.tsx 是 Next.js App Router 强制文件, **职责是 RSC 数据预取 + 渲染组合**, 不存在"重复"。已是"组合器"角色, 模式上正确。

### ❌ 2: `_components/*` 业务容器
**样本**: `account-settings-client.tsx`, `permissions-admin-client.tsx`, `evaluate-new-form.tsx` 等 ~30 个

**理由**: 90% 是 `<DataTable>` + `<Form>` + `<Dialog>` 的组合, **不涉及业务分支选择**。策略模式需要"运行时根据 state 选择行为", 业务容器是"静态组合"。

### ❌ 3: middleware.ts 链式处理
**当前**: `middleware.ts` 只有 25 行, **2 个分支** (CHAT_PUBLIC_MODE on/off), 链式抽象**负收益**。

### ❌ 4: SSE 流式 route 抽工厂
**样本**: `chat/messages/route.ts` (177 行)

**理由**: 限流 + 鉴权 + Zod + provider 工厂 + ReadableStream 错误降级**都在一个文件**, 是有意识的"业务内聚"。抽工厂需要 4+ 个 type 参数, **会拆碎阅读流**。

### ❌ 5: `auth/anon` + `[...path]` 双外观合并
**理由**: 两者**职责正交** — catch-all 透传所有 path, `auth/anon` 特殊在 Set-Cookie 多值透传 (auth bootstrap)。**强合并会引入条件分支**。

### ❌ 6: knowledge/* 直连 Dify route 改走 apiProxy
**样本**: `knowledge/documents/upload/route.ts`, `knowledge/qa/retrieve/route.ts`, `knowledge/batch/route.ts`

**理由**: 这几个 route 直调 `DifyDatasets.createDocumentByText` / `DifyDatasets.retrieve` 是因为**业务逻辑就是调用 Dify SDK**, 不是 BFF 透传。`apiProxy` 是给"我后端有 FastAPI /api/*"用的, Dify SDK 调用是"我后端有 Dify 服务", **不可替换**。

---

## 设计模式分布总结

| 模式 | 现状 | 评价 |
| --- | --- | --- |
| **单例 (Singleton)** | `queryClient` (`lib/api/query-client.ts`), `serverAuthHeaders` (cookie 单次读取) | ✅ 已实现 |
| **外观 (Facade)** | `apiFetch`, `apiProxy`, `[...path]/route.ts` catch-all | ✅ 已实现, **不要再加** |
| **适配器 (Adapter)** | `apiFetch` browser/server URL 切换, `DifyDatasets` 包装 Dify SDK | ✅ 已实现 |
| **策略 (Strategy)** | `ApiError` vs `NetworkError` 错误分支 | ✅ 已实现 (类型即策略) |
| **工厂 (Factory)** | `getChatProvider()` (`lib/chat/factory.ts`), chat provider 切换 | ✅ 已实现 |
| **代理 (Proxy)** | `apiProxy` 透传, `proxyAuthResponse` Set-Cookie 透传 | ✅ 已实现 |

**核心结论**: **整个项目的设计模式重担已经在 `lib/api/` + `lib/chat/factory.ts` 层完成**。app/ 层是"调用方", **再抽一层是过度设计**。

---

## 🟡 高 ROI 候选 (拍板时再说)

> 严格来说没有 🟡 真实高 ROI。但若要"顺手抽", 1 个候选:

### 候选: `bffJsonResponse(resp)` 工厂 (单一职责)

**实施成本**:
- 新增 `lib/api/config.ts:200` 一段 (~15 行 + JSDoc)
- 测试 `lib/api/config.test.ts` 加 1 case (~15 行)
- 改 9 个 route, 每个省 ~3 行 = 27 行

**总账**: +45 行新基础设施 / -27 行重复 / **净 +18 行**, **但消除了"如果改 Content-Type 默认值要改 9 处"的隐性技术债**。

**ROI 真实评估**: 🟡 **中等** (代码量微涨, 但**未来维护性显著**), **可拍板时再决定**。

---

## 扫描方法说明

1. **逐文件 Read**: 扫了 23 个 API route.ts + `lib/api/config.ts` + `lib/api/auth.server.ts` + 6 个 `_actions/*.ts` + `middleware.ts` + `global-error.tsx`, 全部全文。
2. **模式识别**: 按"职责分类" (A-H 8 类), 抽取共有的 5-7 行模板。
3. **ROI 计算**: 抽取成本 (新文件 + 测试) vs 收益 (route 简化行数), 严格做账。
4. **交叉验证**: 对照 P2 报告 (CVA) 发现 `account-settings/_components` 全是 form 组合, **不适用** 模式。
5. **结论**: 整个 app/ 层已通过 `lib/api/` 完成外观/适配器/单例模式, **再抽一层 ROI 为负**。

**关键原则**: "设计模式不是越多越好" — 项目当前分层 (lib/api 是模式层, app/ 是调用层) 已经是最优结构, 不要破坏。

---

**最终评级**:
- 🔴 高 ROI: **0**
- 🟡 中 ROI: **0 真实** (1 候选可拍板)
- 🟢 低 ROI: **3** (均不建议)
- ❌ 不建议: **6 类**

**净省代码**: **~0 行** (不算基础设施), **设计模式已饱和**。