# P3 维度审计总报告 — ③ 单例/策略/工厂/外观/适配器模式

**审计日期**: 2026-06-28
**范围**: `packages/web/` 全量源文件（排除 `.test.tsx`/`.test.ts`/`.stories.tsx`）
**模式**: 4 个 agent 并行扫描（A=common+ui, B=业务组件, C=页面+API, D=lib+其它）

---

## 1. 总体扫描概览

| 维度 | 数值 |
| --- | --- |
| 总扫描文件 | **~371** (86 common+ui + 49 业务组件 + 154 app + 83 lib+其它) |
| **已正确使用设计模式的位置** | **30+** (lib/ 14 处 + app/ 16 处) |
| 🔴 高 ROI 建议重写 | **2** (跨组件实际净省 1 + A 报告 4 个含 30 调用方风险) |
| 🟡 中 ROI 可选 | **6** |
| ❌ 不建议 / 已用合适模式 | **绝大多数** |

---

## 2. 各 Agent 报告位置

| Agent | 范围 | 文件数 | 报告 |
| --- | --- | --- | --- |
| A | common + ui 封装实现层 | 86 | [`A-common-ui-report.md`](p3-patterns/A-common-ui-report.md) |
| B | 业务组件（chat/knowledge/...） | 49 | [`B-business-components-report.md`](p3-patterns/B-business-components-report.md) |
| C | app/ 页面+API | 154 | [`C-pages-report.md`](p3-patterns/C-pages-report.md) |
| D | lib/ + const/ + i18n/ + scripts/ + proxy | 83 | [`D-lib-report.md`](p3-patterns/D-lib-report.md) |

---

## 3. 现有设计模式资产（已正确使用，不重复建议）

### 3.1 单例模式（5 处）— D 报告
- `lib/store/{app,ui,auth}-store.ts` — zustand 单例（模块级 create 一次）
- `lib/store/use-permissions.ts` — zustand + persist
- `lib/api/query-client.ts` — 浏览器 QueryClient 单例
- `lib/api/rsc-queries.ts:getRscQueryClient()` — React `cache()` 实现 per-request 单例

### 3.2 策略模式（4+ 处）— D 报告
- `lib/chat/factory.ts` — LLM Provider 策略（Dify / OpenAI / llamaindex 三协议）
- `lib/chat/types.ts:ChatProvider` — 策略模式抽象基类
- `lib/parse/parse-{csv,excel,json}.ts` — 文件解析策略
- `lib/api/config.ts:apiFetch vs apiProxy` — 两种 fetch 策略

### 3.3 适配器（3+ 处）— D 报告
- `lib/chat/storage.ts` + `db.ts` — Dexie IDB 适配
- `lib/auth/permission.ts:getPermissions()` — server-only 适配
- `lib/dom/download.ts` — DOM API 适配
- `lib/api/config.ts:apiFetch` — 适配 fetch 标准 API

### 3.4 外观模式（5+ 处）— C + D 报告
- `lib/api/config.ts:apiFetch` — 统一 fetch 外观
- `lib/api/config.ts:apiProxy` — BFF 透传外观
- `lib/chat/api.ts` — TanStack Query hooks 外观
- `app/api/[...path]/route.ts` — catch-all 外观
- `lib/api/auth.server.ts:serverAuthHeaders()` — server-only 单例 cookie 读取

### 3.5 装饰器（2 处）— D 报告
- `lib/chat/memory-integration.ts:withMemoryHooks()` — **教科书级装饰器**，给任意 ChatProvider 加长期记忆
- `lib/api/config.ts:apiFetch` — 错误归一化装饰器

### 3.6 业务层（common+ui）— A 报告
- `ErrorBanner` / `AppTooltip` / `StatusBadge` 已是 Record lookup 实现的策略模式
- `Form` + `useFormCtx` 装饰器模式已正确实现
- `PageHeader` + `PageHero` 共存合理

**结论**: 项目设计模式**应用充分**，核心架构层（lib/）已是优秀样板。

---

## 4. 🔴 高 ROI 建议（2 个）

### 4.1 `StandaloneQueryProvider` 抽封装 — B 报告

**问题**: 3 处完全相同的 `useState(() => new QueryClient(...))` + `<QueryClientProvider>` 样板：
- `components/knowledge/dataset-switcher.tsx:38-53` (16 行)
- `components/knowledge/domain-switcher.tsx:55-71` (17 行)
- `components/common/display/app-health-dot.tsx:40-55` (16 行)
- **合计**: 49 行重复

**重构方案**: 抽 `StandaloneQueryProvider` (~25 行) 到 `components/common/providers/`
```tsx
export const StandaloneQueryProvider = ({ children }: { children: ReactNode }) => {
  const [qc] = useState(() => new QueryClient({ defaultOptions: STANDALONE_QC_OPTIONS }));
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};
```

**收益**: **净省 ~14 行 + 单点修改价值**（改 queryClient 默认配置只改 1 处）
**判定**: 🔴 **强烈建议**

### 4.2 弹层族外观统一 — A 报告（含 30 调用方风险）

**问题**: `AppDialog` + `AppDrawer` + `AppConfirm` 3 文件重复 "border-b header + flex-1 overflow + border-t footer" layout（合计 200 行）

**重构**: 抽 `OverlayShell` 共享组件 → 150 行（净省 -50 行）

**风险**: ⚠️ **30 个调用方改 API 风险高**，且项目当前未报 bug
**判定**: 🟡 **中 ROI，暂不做**（等触碰弹层族时顺手做）

---

## 5. 🟡 中 ROI 可选（6 个）

| 建议 | 来源 | 收益 | 风险/备注 |
| --- | --- | --- | --- |
| 弹层族外观统一 | A | -50 行 | 30 调用方风险高 |
| `app-status-badge` × `app-task-status-badge` × `evaluate/status-badge` 合并 | A | -41 行 | 先做 P2 硬编码色阶 token 化 |
| `PageHeader` 删除改用 `PageHero` (v2 已支持 backHref) | A | -27 行 | 调用方 3 处，需改 props |
| `StandaloneQueryProvider` 抽取（见 4.1） | B | -14 行 | 🔴 已升级 |
| `composer-attachments.tsx` ActivePanel 三分支字典化 | B | -6 行 | 仅当未来加第 4 类附件 |
| `lib/api/*.ts` headers 签名统一 + serverApiFetch 抽工厂 | D | -30 行 | 16+ 文件签名统一 |
| `app/api/*` BFF proxy 12 行响应包装模板抽 `bffJsonResponse()` 工厂 | C | ~10 行（净 +18） | 9 个 route 用，可拍板时再做 |

---

## 6. 🟢 低 ROI / ❌ 不建议

### 6.1 错误识别为"需要模式"但实际不适用

| 提议 | 原因 |
| --- | --- |
| `message-bubble.tsx` 拆装饰器（HOC） | user/ai 两种气泡分支极不对称（9 行 vs 60+ 行），拆不开 |
| `chat-shell.tsx` Facade 套娃 | 自身就是最外层 View 组合，套娃变 God Component |
| `json-view.tsx` + `json-diff.tsx` 策略统一 | 共享部分仅 ~15 行，已下沉 utils.ts |
| `GuardPage` + `GuardClient` 工厂 | Server 抛 forbidden vs Client router.replace 业务语义不同，不是可替换策略 |
| `motion/*` 抽共用 hook | 项目 2026-06-28 motion-a11y-refactor 已重构 |
| `auth Provider` 单例 | zustand 已是单例等价物 |
| `evaluate/status-badge.tsx` CVA | 已是 3 Record lookup，CLAUDE.md §业务 enum 走 lookup 已满足 |
| `lib/store/*` 4 个 zustand 抽 factory | 净省 2 行但牺牲可读性 + 类型推导 |
| `lib/parse/*` 抽 `IParser` 接口 | 签名差异大（async File / sync ArrayBuffer / sync text），抽接口牺牲类型推导 |

### 6.2 A 类报告的"不建议"清单（77+ 文件）
- 全部 shadcn 原语 (`ui/*`) 禁止改（破坏 cli 重新生成）
- 纯展示组件（Spinner/Skeleton/BreathingDot/ImagePreview）
- React 组件不能单例化（ErrorBoundary 必须用 Class）
- 业务无关外观（Tabs/Toggle/Select/DropdownMenu/Search/FileDropzone）已 antd 风格封装到位

### 6.3 页面层不适合设计模式
- 全部 `page.tsx` 是 RSC 组合层，无运行时分支
- `_components` 是业务容器，静态组合
- `middleware.ts` 只有 25 行/2 分支，无需链式抽象
- SSE 流式 route 不能抽工厂（业务内聚，拆碎阅读流）

---

## 7. ROI 总结（严格审查）

| 类别 | 数量 | 净省代码 |
| --- | --- | --- |
| 🔴 高 ROI 推荐做 | **1** (StandaloneQueryProvider) | -14 行 + 单点修改价值 |
| 🟡 中 ROI 可选 | **6** | 合计 ~-150 行（含 30 调用方风险） |
| ❌ 不建议 | **绝大多数** | 0 |
| **总计实际可做** | **1 高 + 1-3 中** | **-50 ~ -100 行** |

**真实判断**: 项目架构层（lib/）设计模式应用已**很到位**，业务层大多是 UI 编排不需要模式。**唯一净推荐的高 ROI 是 `StandaloneQueryProvider`**。

---

## 8. P3 关键洞察（给后续审计参考）

1. **项目架构层已是设计模式样板**:
   - 策略（多 LLM 协议）+ 装饰器（withMemoryHooks）+ 外观（apiFetch/apiProxy）+ 单例（zustand + QueryClient）齐全
   - lib/chat/factory.ts 是教科书级策略模式
   - lib/chat/memory-integration.ts 是经典装饰器
   - lib/api/config.ts 双重适配（Adapter + Facade）

2. **业务层大多是 UI 编排**，强行套设计模式会反向增加抽象成本（chat-shell Facade 套娃变 God Component）

3. **React 组件不能单例化**（必须 Class），用 zustand/Context 已等价

4. **A 报告发现的 StatusBadge ×3 合并**应**先做 P2 硬编码色阶 token 化**，否则合并只是形式变化

5. **弹层族外观统一**有 30 调用方风险 + 50 行节省，**ROI 中等但实施风险高**

6. **真正的高 ROI 是消除样板代码**（如 StandaloneQueryProvider），而不是抽新模式

---

## 9. 强烈推荐执行顺序

### ✅ 立即做（1 个）

1. **`StandaloneQueryProvider` 抽取** — B 报告 🔴 高 ROI（净省 14 行 + 改配置只改 1 处）

### ⚠️ 谨慎评估（2-3 个）

2. **StatusBadge 三处合并** — 必须先做 P2 硬编码色阶 token 化（避免合并只是形式变化）
3. **`lib/api/*.ts` headers 签名统一** — D 报告，~30 行节省（净降认知负担）
4. **`PageHeader` 删除改用 `PageHero`** — A 报告，3 调用方，相对安全

### ❌ 暂不做（风险大于收益）

- **弹层族外观统一**（30 调用方 API 改写风险）
- **`message-bubble` HOC 拆分**（user/ai 不对称）
- **`motion/*` 再次重构**（刚做完 a11y 重构）
- **zustand factory**（净省 2 行）
- **`lib/parse/*` `IParser` 接口**（类型推导劣化）

---

## 11. 用户洞察：if/else 链改对象模式（高 ROI）

用户反馈：很多条件语句可以用对象模式更优雅。让我深入挖掘——发现以下**真实存在**的高 ROI 场景：

### 11.1 `lib/chat/chat-utils.ts:applyEvent()` — ev.type 分支改对象 dispatch

**当前** (line 143-156)：
```ts
if (ev.type === "message") { ... }
if (ev.type === "thinking") { ... }
if (ev.type === "error") { ... }
```
**3 个 if 链**，每个分支独立 mutate message，结构重复

**对象模式**：
```ts
const MESSAGE_UPDATERS: Record<EventType, (msg, ev) => Message> = {
  message:  (msg, ev) => ({ ...msg, content: msg.content + ev.delta }),
  thinking: (msg, ev) => ({ ...msg, thinking: [...(msg.thinking ?? []), ev] }),
  error:    (msg, ev) => ({ ...msg, content: `${msg.content}\n\n[${ev.code}] ${ev.message}` }),
};
const updater = MESSAGE_UPDATERS[ev.type];
if (updater) { updated = list.map((msg) => msg.id === msgId ? updater(msg, ev) : msg); }
```

**收益**：3 个 if → 1 个对象查表 + 1 个 if；新增 event type 只改 1 处。

### 11.2 `lib/chat/factory.ts:getChatProvider()` — switch 已可优化（但当前合理）

**当前** (line 18-33)：switch-case 已经清晰，加新 provider 时一目了然
**判断**：✅ **当前 switch 合理**，无需改 Record（switch 在 case 数量 3-5 时等价甚至更清晰）

### 11.3 `lib/chat/dify.ts:normalize()` — switch 已是 dispatcher（已用查表）

**当前** (line 87-128)：注释明确说明"查表 dispatch: 每个 case 抽到独立 generator"
**判断**：✅ **已用对象模式思维**，每个 case 抽成独立函数，复杂度从 30 降到 ~5

### 11.4 `lib/chat/handleStreamError()` — if (AbortError) / else 改对象

**当前** (line 364)：if (error.name === "AbortError") ... else ...
**判断**：✅ **2 个分支，if/else 已是最简**，无需改对象

### 11.5 项目级规则

**判断标准**：
| 场景 | 推荐 |
|------|------|
| 分支数 ≥ 4 + 每个分支独立逻辑 | **对象 dispatch**（如 EVENT_UPDATERS） |
| 分支数 2-3 | if/else 或 switch 均可 |
| 分支内有复杂业务逻辑（如 case "message_end" 80 行） | **保持 switch**，抽函数 |
| 分支仅决定返回值 / 一行表达式 | 对象 lookup（如 STATUS_COLORS） |

**真实机会**：
1. ✅ **`chat-utils.ts:applyEvent` 的 ev.type 分支**（3 个 if → 对象 dispatch，净省 ~5 行 + 未来扩展）
2. ✅ **`use-chat-state.ts` 的 role 分支**（msg.role === "system" / "assistant" 检查）
3. ⚠️ `api/ingest.ts:72` 和 `api/config.ts:43` 的 `error instanceof Error ? .message : String(error)` — **2 个文件相同模式**，可抽 `lib/api/errors.ts:getErrorMessage()` helper

### 11.6 综合 P4 函数式写法的方向

P4 应**重点扫描**：
1. **对象 dispatch 替代 if/else 链**（如上 11.1、11.5）
2. **currying** — 多次相同参数的不同后续函数（如 `apiFetch(path)(init)`）
3. **pipe/compose** — 多步数据变换（如 `normalizeEvent → enrichEvent → saveEvent`）
4. **cond 分支** — 用 `R.cond` 或自实现替代 if/else 链
5. **partial application** — 预绑定部分参数

---

## 12. P3 + P4 协同：真正的 ROI 集中区

| 场景 | 当前 | 推荐改法 | ROI |
|------|------|---------|-----|
| `chat-utils.ts:applyEvent` 的 ev.type 分支 | 3 个 if 链 | 对象 dispatch | 🔴 高（5 行 + 扩展性） |
| `api/{config,ingest}.ts` 的 `error.message` 提取 | 2 处重复 | 抽 helper | 🔴 高（消除重复） |
| `use-chat-state.ts` 的 role 检查 | 2 处相同模式 | 对象 lookup | 🟡 中 |
| `factory.ts` switch-case | 已合理 | 保持 | ❌ 不动 |