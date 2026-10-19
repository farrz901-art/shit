# P4 维度 ④ 函数式写法审计 — Agent B (业务组件 ~50 files)

> 审计日期: 2026-06-28
> 范围: `packages/web/components/` 下除 `common/` `ui/` 之外的所有业务组件 + `lib/chat/chat-utils.ts`
> 总文件数: ~50, 共 ~3 600 行
> 工具: es-toolkit ^1.48.1 (已装, 全项目仅 `lib/chat/migration.ts:10` 1 处使用)
> 核心原则: 业务组件的"展示+交互"难以纯化; **内部 helper 函数** 才是 FP 改造目标, 拒绝"为用而用"

## 扫描概览

| 子目录 | 文件 | 行数 | FP 改造潜力 |
|---|---|---|---|
| `chat/` (components) | 13 | 1929 | 🟡 中 |
| `lib/chat/chat-utils.ts` | 1 | 507 | 🟡 中 (applyEvent P3 已高 ROI) |
| `knowledge/` | 5 | 317 | 🟢 低 (P3 QueryClient 已知) |
| `json/` | 6 | 297 | 🟡 中 |
| `decode/` | 1 | 30 | ❌ 无 |
| `evaluate/` | 1 | 46 | ❌ 无 (Record lookup 已用) |
| `settings/` | 2 | 90 | 🟢 低 |
| `auth/` | 4 | 130 | 🟢 低 |
| `layout/` | 2 | 86 | 🟢 低 |
| `i18n/` | 1 | 29 | 🟢 低 |
| `motion/` | 14 | 457 | ❌ 无 (2026-06-28 已重构) |
| 顶层 (page-guard / theme-provider / user-menu) | 3 | ~430 | 🟡 中 |

### 关键判定原则 (严格 ROI)

1. **React 组件本身**: 不纯, 不硬拆 FP
2. **React hook**: 不纯, 不为纯函数化改 hook
3. **内部 helper 函数** (顶级 const fn): 是 FP 改造目标
4. **P3 已标记高 ROI**: 不重复 (applyEvent / composer ActivePanel / QueryClient)
5. **🟡 中 ROI**: 真实净省 1-3 行 + 真实提升可读性 才算
6. **❌ 不建议**: 反向增加行数, 或拆完可读性变差

---

## 🔴 高 ROI (强烈建议)

### 1. `thinking-trace.tsx:renderStep` 状态 class 二分支 → Record lookup

**位置**: `components/chat/thinking-trace.tsx:12-29`

**现状** (18 行):
```tsx
const renderStep = (step: Step, idx: number) => {
  const isFinished = step.status === "finished";
  let statusClass = "";
  if (isFinished) {
    statusClass = FINISHED_CLASS;
  } else {
    statusClass = STARTED_CLASS;
  }
  return (
    <div key={idx} className="flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs">
      <Badge variant="outline" className={statusClass}>
        {step.status}
      </Badge>
      <span className="num text-muted-foreground">{step.node}</span>
      {step.detail && <span className="text-muted-foreground/70">· {step.detail}</span>}
    </div>
  );
};
```

**FP 改法** (Record lookup):
```tsx
// 单一查找表 — 跟 stagger-item.tsx VARIANT_MAP 风格一致
const STATUS_CLASS: Record<Step["status"], string> = {
  finished: FINISHED_CLASS,
  started: STARTED_CLASS,
};

const renderStep = (step: Step, idx: number) => (
  <div key={idx} className="flex items-baseline gap-2 rounded-md bg-muted/30 px-2 py-1 text-xs">
    <Badge variant="outline" className={STATUS_CLASS[step.status]}>
      {step.status}
    </Badge>
    <span className="num text-muted-foreground">{step.node}</span>
    {step.detail && <span className="text-muted-foreground/70">· {step.detail}</span>}
  </div>
);
```

**ROI 评估**:
- **净省行数**: -5 行 (18 → 13), 整个 `let statusClass = ""` 块消失
- **一致性收益**: 与同项目 `stagger-item.tsx:13-17` `VARIANT_MAP` 风格一致 (项目已有范例)
- **类型安全**: `Record<Step["status"], string>` 强制穷尽, 未来加 status 时 TS 立即报错
- **风险**: 零 (纯展示组件, 2 状态)

**分类**: 🔴 **高 ROI** — 状态字典是项目强制规约 (CLAUDE.md §业务 enum 走 lookup), 现状违反. 跟 `evaluate/status-badge.tsx:16-37` 3 Record lookup 同型.

---

### 2. `theme-provider.tsx` 4 处同样的 theme 校验 → 提纯 `isValidTheme` predicate

**位置**: `components/theme-provider.tsx:115-117, 202-204, 209-211, 257-260` (4 处散落)

**现状 (重复 4 次)**:
```ts
// L115-117
if (stored === LIGHT || stored === DARK || stored === SYSTEM) { return stored; }
// L202-204
if (next !== LIGHT && next !== DARK && !(enableSystem && next === SYSTEM)) { return prev; }
// L209-211 (跟 L202-204 几乎一样)
if (value !== LIGHT && value !== DARK && !(enableSystem && value === SYSTEM)) { return; }
// L257-260
if (event.newValue === LIGHT || event.newValue === DARK || (enableSystem && event.newValue === SYSTEM)) { ... }
```

**FP 改法** (抽 pure predicate + 类型谓词):
```ts
// 顶层 helper, 跟 readStored (L91) 同区域
const isValidTheme = (val: unknown, enableSystem: boolean): val is ThemeName =>
  val === LIGHT || val === DARK || (enableSystem && val === SYSTEM);
```

调用处:
```ts
// L115
if (isValidTheme(stored, /*enableSystem*/ ?)) return stored;
// L202 / L209
if (!isValidTheme(next, enableSystem)) return prev; // 同 L209
// L257
if (isValidTheme(event.newValue, enableSystem)) setThemeState(event.newValue);
```

**ROI 评估**:
- **净省行数**: -8 行 (4 处 × 1 行 if → 1 行, 加 helper 5 行, 净省 8 行)
- **一致性收益**: 改白名单 (加 "high-contrast" 等) 改 1 处, 4 处对齐
- **类型安全**: `val is ThemeName` 类型谓词替代手 cast, 杜绝 4 处手写重复
- **风险**: 低 (基座, 但语义是纯白名单校验, 改完 4 处逻辑统一, 测试覆盖)

**分类**: 🔴 **高 ROI** — 重复 4 次完全同型, 类型安全升级, 单点修改价值大.

---

## 🟡 中 ROI (可选 / 顺手做)

### 3. `chat/composer-attachments.tsx` 重复 `prev.map(item => if (id === tempId) ...)` 2 次 → 抽 `updateById`

**位置**: `components/chat/composer-attachments.tsx:258-280` (2 处共 20 行)

**现状 (重复)**:
```ts
// L258-271 (成功)
setItems((prev) => prev.map((item) => {
  if (item.id === tempId) return { ...item, id: uploadFileId, status: "done", uploadFileId, url: uri || item.url };
  return item;
}));
// L273-280 (失败) - 几乎一样, 只改 status
setItems((prev) => prev.map((item) => {
  if (item.id === tempId) return { ...item, status: "error" };
  return item;
}));
```

**FP 改法** (抽 helper, 跟 chat-utils.ts:applyEvent 同型模式):
```ts
// 顶层 helper, 在 L41 inferType 旁
const updateById = <T extends { id: string }>(items: T[], id: string, patch: Partial<T>): T[] =>
  items.map((item) => (item.id === id ? { ...item, ...patch } : item));

// 调用处 (成功)
setItems((prev) => updateById(prev, tempId, { id: uploadFileId, status: "done", uploadFileId, url: uri || undefined }));
// 调用处 (失败)
setItems((prev) => updateById(prev, tempId, { status: "error" }));
```

**ROI 评估**:
- **净省行数**: -3 行 (20 → 17), 新建 updateById 3 行
- **一致性收益**: React 状态管理 **经典 helper**, 全项目可推广 (lib/chat/storage-extra.ts 等同型处也用)
- **风险**: 极低, 纯 helper
- **建议**: 🟡 **顺手做**, 仅 composer 用收益微, **等 lib/chat/storage.ts 也用同型 helper 时一起抽**

---

### 4. `chat/share-dialog.tsx` 2 处 `let + if/else` 反模式 → ternary

**位置**: `components/chat/share-dialog.tsx:79-106` (renderCreateButton, renderEmpty)

**现状**:
```ts
// L79-86 (renderCreateButton)
const renderCreateButton = () => {
  let createLabel = "";
  if (creating) { createLabel = CREATING_TEXT; }
  else { createLabel = translation("分享"); }
  return <Button ...>{createLabel}</Button>;
};
// L98-106 (renderEmpty) - 同型
```

**FP 改法 (直接 ternary)**:
```ts
const createLabel = creating ? CREATING_TEXT : translation("分享");
// renderEmpty 同理
const hint = convId ? translation("我的分享") : "—";
```

**ROI 评估**:
- **净省行数**: -4 行 (2 处 × 2 行)
- **风险**: 零, 反模式清理
- **建议**: 🟡 **顺手做**, 不需要 es-toolkit

**分类**: 🟢 **顺手做** (低 ROI 但代码质量提升)

---

### 5. `chat/memory-management-dialog.tsx:useMemoryFilter` IIFE → ternary

**位置**: `components/chat/memory-management-dialog.tsx:55-65` (10 行)

**现状**:
```ts
const useMemoryFilter = (memories: MemoryHit[]) => {
  const [filter, setFilter] = useState("");
  const filtered = (() => {
    if (!filter) return memories;
    const query = filter.toLowerCase();
    return memories.filter((m) => m.text.toLowerCase().includes(query));
  })();
  return { filter, filtered, setFilter };
};
```

**FP 改法** (提纯成 ternary, 拒绝 curry 多此一举):
```ts
const useMemoryFilter = (memories: MemoryHit[]) => {
  const [filter, setFilter] = useState("");
  const filtered = !filter
    ? memories
    : memories.filter((m) => m.text.toLowerCase().includes(filter.toLowerCase()));
  return { filter, filtered, setFilter };
};
```

**ROI 评估**:
- **净省行数**: -1 行 (IIFE 4 行 → 1 行 ternary)
- **风险**: 零
- **建议**: 🟢 **顺手做**, 不需要 curry

---

### 6. `voice-recorder.tsx:getFileExtension` 2 分支 if → Record lookup

**位置**: `components/chat/voice-recorder.tsx:34-39` (6 行)

**现状**:
```ts
const getFileExtension = (mimeType: string): string => {
  if (mimeType.includes("mp4")) return "m4a";
  return "webm";
};
```

**FP 改法** (跟 PREFERRED_MIMES 旁定义):
```ts
const EXTENSION_BY_MIME: Record<string, string> = {
  "audio/mp4": "m4a",
  "audio/webm": "webm",
  "audio/webm;codecs=opus": "webm",
};
const getFileExtension = (mimeType: string): string => EXTENSION_BY_MIME[mimeType] ?? "webm";
```

**ROI 评估**:
- **净省行数**: 0 行 (5 行 → 5 行, 但 if 链 → 数据驱动)
- **建议**: 🟡 **与 §1 一起做才划算**

---

### 7. `lib/chat/chat-utils.ts:computeEffectiveConversations` filter+map 链 → pipe

**位置**: `lib/chat/chat-utils.ts:30-55`

**现状**:
```ts
const localIds = new Set(conversations.map((conv) => conv.id));
const serverOnly = serverConvs
  .filter((conv) => !localIds.has(conv.id))
  .map((conv) => ({ createdAt: Date.parse(conv.created_at), id: conv.id, ... }));
return [...conversations, ...serverOnly];
```

**FP 改法** (pipe + differenceBy):
```ts
import { differenceBy, map, pipe } from "es-toolkit";

const toLocalConv = (server: ServerConv): Conversation => ({
  createdAt: Date.parse(server.created_at),
  id: server.id, messageCount: server.message_count, title: server.title,
  updatedAt: Date.parse(server.updated_at),
});

export const computeEffectiveConversations = (
  conversations: Conversation[], serverConvs: ServerConv[], isAccount: boolean,
): Conversation[] => {
  if (!isAccount) return conversations;
  return [...conversations, ...pipe(serverConvs, differenceBy(conversations, (c) => c.id), map(toLocalConv))];
};
```

**ROI 评估**:
- **净省行数**: -2 行
- **副作用**: `Date.parse` 仍是 impure, 跟原版一样
- **风险**: 🟡 中 (chat-utils 是 P3 已标 applyEvent 高 ROI 文件, **整体推 es-toolkit 才有意义**)
- **建议**: 🟡 **跟 applyEvent 一起改**

---

## ❌ 不建议 (拒绝"为用而用")

### `theme-provider.tsx:resolveTheme` 3 分支 if-else → `cond`

**位置**: `theme-provider.tsx:122-133` (12 行)

**判断**: ❌ **基座已重构, 单点改风险 > 收益**. cond 包 5-7 行 vs if 链 12 行, **等价但**:
- theme-provider 2026-06-14 整体重构过
- 这是基座, 改 1 行可能影响所有页面切换
- **仅在 P5 整体推 es-toolkit 时顺手改**

---

### `conversation-list.tsx:formatRelativeTime` 4 分支 if-else → `cond`

**位置**: `components/chat/conversation-list.tsx:24-36` (13 行)

**判断**: 🟢 **低 ROI**. Date.now() 副作用是 ROI 瓶颈, **if→cond 只是表面文章**. 注入 clock 收益微, 不纯化它改 if 链无意义.

---

### `chat/composer-attachments.tsx:inferType` 3 分支 MIME 前缀 → `cond`

**位置**: `chat/composer-attachments.tsx:41-49` (9 行)

**判断**: 🟢 **3 行 if 链已清晰**, cond 包 5-7 行反而绕. 拒绝"为用而用".

---

### `chat/composer-attachments.tsx:doUpload` try/catch → `tryCatch`

**位置**: `composer-attachments.tsx:86-95`

**判断**: ❌ **网络 IO 边界项目惯例是 try/catch**, 改 tryCatch 风险高于收益 (后者吞嵌套错误). 跟 `lib/chat/chat-utils.ts:persistAssistantToServer` 风格保持一致.

---

### `i18n/localized-link.tsx:prependLocale` 3 分支 if → pipe

**位置**: `i18n/localized-link.tsx:19-27` (9 行)

**判断**: 🟢 **3 分支 if 链已清晰** (空/已带 locale/未带), pipe 化增 +5 行包装.

---

### `chat/shared-chat-view.tsx` `Date.parse` / 临时 id

**位置**: `shared-chat-view.tsx:23, 47-48`

**判断**: 🟢 **RSC 一次渲染, 副作用可接受**. `id: \`shared-${idx}\`` 用索引作 key 已是 React anti-pattern 但 RSC 列表只读无重排, **不影响生产**. 改 `crypto.randomUUID` 反而每 render 变 id 触发警告.

---

### `user-menu.tsx:handleLogout` 副作用 + 业务混

**位置**: `user-menu.tsx:31-43`

**判断**: ❌ **网络 + 副作用 + 跳转, pipe 化反而失去"线性步骤"可读性**. 项目惯例写法.

---

### `chat/chat-utils.ts:newId` 改 `crypto.randomUUID`

**位置**: `lib/chat/chat-utils.ts:22-27`

**判断**: ❌ **项目已有 fallback 链** (`typeof crypto !== "undefined" && "randomUUID" in crypto`), 已是最优解. 强制改 `crypto.randomUUID()` 在 SSR 报错.

---

### `voice-recorder.tsx:stopAllTracks` for-of → `forEach`

**位置**: `voice-recorder.tsx:41-45`

**判断**: ❌ **for-of 是合法 ES**, 跟 forEach 性能/可读性等效, **无 ROI**.

---

### `knowledge-tabs.tsx:visibleNav` filter 链 + `layout/header.tsx` 同型

**位置**: `knowledge-tabs.tsx:46-62`, `layout/header.tsx:24-26`

**判断**: 🟢 **单点 filter, 2 条件合并已最简**. es-toolkit `filter` API 跟原生同形, 无 ROI.

---

## ❌ P3 已声明, 不重复

| P3 结论 | 状态 |
|---|---|
| `chat-utils.ts:applyEvent` 3 if 链 → 对象 dispatch | 🔴 P3 高 ROI, **本次不重复** |
| `composer-attachments.tsx:ActivePanel` 三分支 → 字典 | 🟡 P3 中 ROI (需加第 4 类升级), **不重复** |
| `knowledge/` 3 处 QueryClient 样板 → 抽 `StandaloneQueryProvider` | 🔴 P3 高 ROI, **不重复** |
| `message-bubble.tsx` user/ai 拆装饰器 | ❌ P3 不建议, **不重复** |
| `json-view + json-diff` 策略统一 | 🟢 P3 低 ROI, **不重复** |
| `motion/` 14 组件再抽 (FadeUp+AnimateUp+Reveal 抽 hook) | ❌ P3 不建议 (2026-06-28 刚重构), **不重复** |
| `evaluate/status-badge.tsx` 5 状态再抽模式 | ❌ P3 不建议 (已 Record lookup), **不重复** |
| `chat-shell.tsx` Facade 套娃 | ❌ P3 不建议, **不重复** |
| `GuardPage + GuardClient` 工厂模式 | ❌ P3 不建议 (业务语义不同), **不重复** |

---

## 📊 总评

### 高 ROI 清单 (本次新发现, P3 未标记)

| # | 文件:位置 | 净省 | 一致性收益 | 风险 |
|---|---|---|---|---|
| 1 | `chat/thinking-trace.tsx:12-29` 状态 class → Record | -5 | 满足项目规约 | 零 |
| 2 | `theme-provider.tsx:115/202/209/257` 4 处 theme 校验 → `isValidTheme` | -8 | 白名单改 1 处, 4 处对齐 | 低 (类型谓词更安全) |

**合计净省**: -13 行 + 一致性大幅提升 (状态字典化 + 类型谓词).

### 中 ROI (顺手做, 不需 es-toolkit)

| # | 文件 | 净省 | 备注 |
|---|---|---|---|
| 3 | `composer-attachments.tsx` `updateById` helper | -3 | 等 storage-extra.ts 同型时一起抽 |
| 4 | `share-dialog.tsx` 2 处 let + if/else → ternary | -4 | 反模式清理 |
| 5 | `memory-management-dialog.tsx:useMemoryFilter` IIFE → ternary | -1 | 不需要 curry |
| 6 | `voice-recorder.tsx:getFileExtension` → Record | 0 | 跟 §1 一起做 |

### 不建议清单 (新增)

- ❌ `theme-provider.tsx:resolveTheme` 3 if → cond (基座风险)
- ❌ `conversation-list.tsx:formatRelativeTime` 4 if → cond (Date.now 副作用是瓶颈)
- ❌ `inferType` 3 if → cond (3 行已清晰)
- ❌ `doUpload` try/catch → tryCatch (项目惯例)
- ❌ `prependLocale` 3 if → pipe (已清晰)
- ❌ `user-menu.tsx:handleLogout` pipe 化 (IO+副作用线性步骤)
- ❌ `newId` 改 `crypto.randomUUID` (项目已有 fallback 链)
- ❌ `stopAllTracks` for-of → forEach (无 ROI)
- ❌ `visibleNav` filter 链 (单点 filter, es-toolkit 无收益)
- ❌ `shared-chat-view.tsx` Date.parse / 临时 id (RSC 一次渲染可接受)
- ❌ `chat-utils.ts` 散落 `Date.now()` (helper 内副作用无法纯化, 注入 clock 收益微)

### 关键原则总结

1. **拒绝"为用而用" es-toolkit** — 3 行 if 链不必强拆 cond/pipe
2. **P3 标高 ROI 不重复** (applyEvent / QueryClient / ActivePanel)
3. **基座组件** (theme-provider / motion) 风险 > 收益, 不单独改
4. **Date.now() 副作用是 ROI 瓶颈**, 不解决副作用只换 if 链 = 表面文章
5. **let + if/else 反模式清理可做** (share-dialog 等), 但非 es-toolkit 范畴

### 建议执行优先级

1. **P4.1** (🔴 高, 单点改): `thinking-trace.tsx:STATUS_CLASS` 字典化
2. **P4.2** (🔴 高, 4 处): `theme-provider.tsx:isValidTheme` 提纯 (基座, 改完跑 motion-a11y 测试)
3. **P4.3** (🟢 顺手): `share-dialog.tsx` 2 处 ternary 化 + `voice-recorder.tsx:getFileExtension` 字典化 + `memory-management-dialog.tsx` IIFE 简化
4. **P4.4** (🟡 整体): 等 P3 决定的 `applyEvent` 改造时, 顺带改 `computeEffectiveConversations` / `formatRelativeTime` / `inferType` 几处
5. **P5 不动**: `composer-attachments.tsx:doUpload` 保持 try/catch (项目惯例); `motion/` 不二次重构 (2026-06-28 已重构完)

### 关联文档

- P3 报告: `p3-patterns/B-business-components-report.md` (设计模式维度)
- P4 Agent A 报告: `p4-functional/A-common-ui-report.md` (common/ + ui/ 范围)
- P4 Agent C 报告: `p4-functional/C-pages-report.md` (页面层)
- P4 Agent D 报告: `p4-functional/D-lib-report.md` (lib/ 范围)
- 项目规约: `CLAUDE.md` §业务 enum 走 lookup / §函数封装 (3 行重复 3 次抽)
