# P3 维度 ③ 单例/策略/工厂模式 — Agent B (业务组件 ~49 files)

> 审计日期: 2026-06-28
> 范围: `packages/web/components/` 下除 `common/` `ui/` `*.test.*` `index.ts` 之外的所有业务组件
> 总文件数: 49 (.tsx/.ts, 不含测试 + barrel), 共 3 369 行
> 核心问题: 这些组件**绝大多数已经是 UI 编排**, 强行套设计模式会反向增加抽象成本.

## 扫描概览

| 子目录 | 生产文件 | 代码行 | 已有设计模式 |
|---|---|---|---|
| chat/ | 13 | 1929 | 装饰器 (withMemoryHooks), 策略 (factory.ts 已有) |
| motion/ | 14 | 457 | 已经是封装库, 无业务 |
| knowledge/ | 5 | 317 | 单例 (QueryClient 自包) — **重复 3 处** |
| auth/ | 4 | 130 | Context Provider (zustand 等价单例) |
| layout/ | 2 | 86 | 无 |
| settings/ | 2 | 90 | 无 |
| json/ | 6 | 297 | 已是单一职责展示组件 |
| evaluate/ | 1 | 46 | Record lookup (已是状态字典) |
| decode/ | 1 | 30 | 单组件 |
| i18n/ | 1 | 29 | 无 |
| **顶层** (page-guard/theme-provider/user-menu 等) | — | — | 单例 / Facade 已用 |
| **合计** | **49** | **3 369** | — |

### 关键发现: 已有设计模式覆盖充分

1. **chat 策略模式已落地** — `lib/chat/factory.ts:11-34` `getChatProvider()` 已用 switch 实现 Dify / OpenAI / llamaindex 三路策略, `ChatProvider` 接口 (types.ts:39-42) 是抽象基类. UI 层完全感知不到协议差异.
2. **chat 装饰器已落地** — `lib/chat/memory-integration.ts` `withMemoryHooks()` 给任意 ChatProvider 套长期记忆能力, 这是教科书 Decorator 模式.
3. **chat 存储 Facade 已落地** — `lib/chat/storage.ts` 把 IndexedDB / 旧 localStorage 封装成纯 Conversation[] API.
4. **auth 单例已落地** — zustand store (`useAuthStore` / `usePermissionsStore`) + `PermissionHydrate` (RSC→Client 桥).
5. **knowledge 单例已落地** — 但**重复 3 次** (见下).

## 按子模块列出

### chat/ (13 files, 1929 行) — 设计模式主战场, **但已饱和**

#### 1. 多 LLM 协议适配: **已有策略模式, UI 无需再包**
- `lib/chat/factory.ts` switch-case 已封装 Dify/OpenAI/llamaindex 三协议
- `lib/chat/dify.ts` + `lib/chat/openai.ts` 实现 `ChatProvider` 接口
- 装饰器 `withMemoryHooks` 给任意 provider 加记忆能力
- **判断**: 业务组件层不需再包策略模式, 已经全部下沉到 lib. **若再抽"UI 策略"会重复抽象**.

#### 2. 4 种气泡: user/ai/system/error — 装饰器/高阶组件价值?

- `components/chat/message-bubble.tsx` 154 行, 内部 `isUser = role === "user"` 后是 if/else (79-100 行), 用户气泡只显示文本, 助手气泡走 `parseThinkTag` + `ReactMarkdown` + 引用 + 反馈 + interrupted 徽章.
- **关键事实**: 4 种气泡里, **只有 user 和 assistant 两种真实使用** (Message 类型 `role` 限定 `"user" | "assistant"` 在 `types.ts:46`). "system" / "error" 在代码里**没有真实数据流入**, 注释里提到只是防御性.
- **若用装饰器/HOC**:
  - 重构前: 1 个组件 154 行, 内含 if/else
  - 重构后: `<UserBubble>` + `<AssistantBubble>` + `<MessageBubble>` 路由 (3 文件, ~180 行, 反而增 26 行)
- **判断**: 🟢 **低 ROI, 不建议**. 两种真实气泡分支极不对称 (user 9 行 vs assistant 60+ 行), 装饰器拆不开. 项目规约 (CLAUDE.md §业务 enum) 也未要求拆.

#### 3. 5+ 种附件类型: image/file/voice — 策略模式?

- `components/chat/composer-attachments.tsx` 319 行
- 三入口对应三个 React 子组件 (`<FileDropzone image>` / `<FileDropzone file>` / `<VoiceRecorder>`), 内部用 `activeSlot` state 切换.
- 核心逻辑链: `SlotButtons` (3 个 icon 按钮) → `ActivePanel` (if-else 三分支渲染) → `uploadAndAdd` (统一上传流程).
- **若用策略模式**: 抽 `AttachmentSlot = { id, accept, Component, icon }`, 用字典替代 if-else.
- **重构对比**:
  - 当前 `ActivePanel` if-else 链 (189-225 行, 36 行)
  - 字典: `SLOT_MAP: Record<SlotId, { accept, Component }>`, 渲染循环
  - **预估净省**: ~6 行 (字典 + lookup 比 if-else 短约 10 行, 但要加 SLOT type 定义 / icon 映射)
- **判断**: 🟡 **中 ROI 但优先级低**. 现有 if-else 三个分支清晰, 字典化收益小. **若未来加第 4 类 (视频/粘贴) 则立即升级为 🔴**.

#### 4. chat-shell.tsx — Facade 候选?

- `chat-shell.tsx` 131 行, 编排 ConversationList + ChatHeader + MessageList + Composer + 3 dialog.
- **判断**: ❌ **已是编排者, 不再需要 Facade 套娃**. 自身就是最外层 View 组合.

#### 5. thinking-trace.tsx — 简单 List+Item

- 34 行, 单一职责. 无重复. **❌ 不适用**.

#### 6. message-feedback.tsx — 折叠态 / 展开态切换

- 213 行, 内部 `FeedbackButtons` / `FeedbackForm` 两个子组件按 `open` 切换.
- 无重复逻辑. **❌ 不适用**.

### knowledge/ (5 files, 317 行) — **🔴 高 ROI 唯一候选**

#### **🔴 高 ROI: 抽出共享 QueryClientProvider 包装**

- **3 处完全相同**的 `useState(() => new QueryClient(...))` + `<QueryClientProvider client={qc}>` 样板:
  - `components/knowledge/dataset-switcher.tsx:38-53` (16 行)
  - `components/knowledge/domain-switcher.tsx:55-71` (17 行)
  - `components/common/display/app-health-dot.tsx:40-55` (16 行) — 范围外但同型
- **重复代码**: 49 行 (3 处 × ~16 行), **3 处完全一致**.
- **重构方案**: 在 `components/common/display/` (或新建 `components/common/providers/`) 抽 `StandaloneQueryProvider` 组件.
  ```tsx
  // 新文件 components/common/providers/standalone-query-provider.tsx (~25 行)
  export const STANDALONE_QC_OPTIONS = {
    queries: { gcTime: 0, retry: false, staleTime: Infinity },
  } as const;
  export const StandaloneQueryProvider = ({ children }: { children: ReactNode }) => {
    const [qc] = useState(() => new QueryClient({ defaultOptions: STANDALONE_QC_OPTIONS }));
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
  ```
- **重构后代码**:
  - 每个使用方从 16 行 → 1 行 import + 1 个 wrapper (3-4 行)
  - **净省: 3 处 × 12 行 = 36 行**
  - 加上新文件 25 行, **净省 11 行** (但**一致性收益巨大**: 改默认配置只改 1 处, 4 处对齐)
- **判断**: 🔴 **高 ROI 推荐**. 重复度满分 (3 处), 单点修改价值 > 单纯的行数省.

#### schema-field-renderer.tsx — 4 字段类型 (含 2 picker)

- 45 行, 单一职责. **❌ 不适用**.

#### schema-browser.tsx / knowledge-tabs.tsx — 单一职责

- 无重复. **❌ 不适用**.

### json/ (6 files, 297 行) — 策略模式候选, 但 ROI 低

#### json-view.tsx (74 行) vs json-diff.tsx (131 行) — 是否可用策略模式统一?

- **相同部分**: safeStringify 兜底, resolveCssDimension, container 渲染, shiki theme.
- **不同部分**: json-view 用 `codeToHtml` 一把梭; json-diff 用 `diffLines` + `codeToTokens` 逐行 tokenize.
- **若用策略模式**: 抽 `JsonRenderer` 接口 `{ render(data, theme): Promise<ReactNode> }`, 两个实现.
- **重构对比**:
  - 抽接口 + 实现 2 个 + dispatcher: ~50 行新代码
  - 当前: 各自独立 ~200 行
  - **净省: 反而 +20 行** (接口 + 类型 > 共享部分行数)
- **判断**: 🟢 **低 ROI**. **共享部分只有 ~15 行** (safeStringify 已经下沉到 utils.ts, container 是 8 行 div). 强行策略化是**过早抽象**.

#### diff-row.tsx — 3 Record lookup 已是最优

- 56 行, `BG_MAP` / `GUTTER_COLOR_MAP` / `GUTTER_SIGN_MAP` 3 个 Record (已经是状态字典, 不需要再抽).

### decode/ (1 file, 30 行)

- `chunks-preview.tsx` — 单一职责小组件. **❌ 不适用**.

### evaluate/ (1 file, 46 行)

- `status-badge.tsx` — **5 状态映射已经是 Record lookup** (`CUSTOM_STYLE` / `LABEL` / `VARIANT` 各 1 个 Record). 项目规约 (CLAUDE.md §业务 enum 走 lookup) 已满足. **❌ 不适用**.

### settings/ (2 files, 90 行)

- `settings-dialog.tsx` + `theme-toggle.tsx` — 无重复. **❌ 不适用**.

### auth/ (4 files, 130 行) — 单例已用

- `permission-hydrate.tsx` (28 行): Context Provider 桥 — 已是单例模式 (zustand store 单例 + RSC hydrate).
- `auth-bootstrap.tsx` (58 行): 副作用触发, 无重复.
- `guard-client.tsx` (19 行) + `guard-page.tsx` (19 行): **Server / Client 守卫对偶**, 看似可以工厂模式, 但实际:
  - `GuardPage` 是 RSC, 调 `forbidden()` 抛错
  - `GuardClient` 是 Client, 调 `router.replace("/404")` 跳转
  - **业务语义完全不同**: 一个是 403, 一个是 fallback. 不是可替换策略, 是**职责分离**.
- **判断**: ❌ **不建议工厂化**. 强行抽象会变成 if Server/Client 模板, 反而损失类型安全.

### motion/ (14 files, 457 行) — 已经是设计模式成果

- 14 个原子组件 (FadeUp / AnimateUp / Reveal / Stagger / ButtonLift / HoverLift / Pressable / Pulse / CountUp / ...), 每个都是 `motion.X` 的包装.
- **本质**: 已经是**装饰器模式** (每个 motion.X 包一层 reduce-motion 兼容 + 默认 props).
- **重复?** `FadeUp` (45 行) vs `AnimateUp` (54 行) vs `Reveal` (38 行): 都用 `fadeUp` variants, 差别是显隐时机 / AnimatePresence.
- **重构对比**: 若抽 `useFadeUpVariants({ initial, animate, exit })` hook:
  - 3 个组件各 ~12 行 hook 调用替代 ~25 行手写 variants
  - **净省: 3 处 × 13 行 = 39 行**
  - **但**: 这些组件每个职责清晰 (FadeUp = 立即显示; AnimateUp = 出场动画; Reveal = 滚动入场), 项目已经在 2026-06-28 motion-a11y-refactor 重构过, 没必要二次抽象.
- **判断**: 🟢 **低 ROI**. motion 库是稳定基座, 重构风险 > 收益.

### layout/ (2 files, 86 行) + i18n/ (1 file, 29 行) + 顶层

- `header.tsx` 73 行 — 无重复.
- `footer.tsx` 13 行 — RSC 极简, **❌ 不适用**.
- `localized-link.tsx` 29 行 — 已是单一职责.
- 顶层 `page-guard.tsx` (21 行) — RSC 守卫, 单文件.
- 顶层 `theme-provider.tsx` (285 行, 含测试) — **已是单例 (Context)**, 项目基座.
- 顶层 `user-menu.tsx` (127 行) — 用户菜单, 无重复.

## 🔴 高 ROI（建议重写）

### 1. knowledge/ QueryClient 自包样板 — 抽 `StandaloneQueryProvider`

| 项 | 当前 | 重构后 |
|---|---|---|
| 重复处 | dataset-switcher.tsx + domain-switcher.tsx (+ common/display/app-health-dot.tsx) | 同 3 处, 通过组件复用 |
| 重复代码 | 3 × 16 = 48 行 | 3 × 3 = 9 行 (3 处 import + wrap) |
| 新增 | 0 | 1 个新组件 ~25 行 |
| **净行数** | 48 | 34 |
| **净省** | — | **14 行** |
| 一致性 | 默认配置散落 3 处, 改一处要改 3 处 | 改 1 处即可 |
| 单点测试 | 3 套 mock | 1 套 |

**ROI 等级**: 🔴 **高** — 重复度满分, 单点修改价值大, 风险低.

**建议文件路径**: `packages/web/components/common/providers/standalone-query-provider.tsx` (在 common/ 因为会被 common/display/app-health-dot 也复用).

## 🟡 中 ROI（可选, 优先级低)

### 1. composer-attachments.tsx ActivePanel 三分支 → 字典化

**仅当未来加第 4 类附件 (视频/粘贴/...) 时升级**. 当前 3 类用 if-else 已经清晰.

### 2. motion/ FadeUp + AnimateUp + Reveal 共用 hook

**不建议**: 3 个组件职责明确 (立即 / 出场 / 滚动入场), 项目刚在 2026-06-28 重构完, 再次抽象风险 > 收益.

## 🟢 低 ROI（不建议）

### 1. message-bubble.tsx user/ai 拆装饰器

- 154 行单一组件, 两种气泡内容差异极大. 拆 HOC 会**增加代码反而更复杂**.

### 2. json-view.tsx + json-diff.tsx 策略统一

- 共享部分仅 ~15 行, 已经下沉到 utils.ts. 强行抽象增 +20 行.

## ❌ 明确不做（违反 YAGNI / 增加复杂度）

### 1. chat-chat shell Facade 套娃

- `chat-shell.tsx` 已是编排者, 不需要再包一层. 套娃会成"God Component 反模式".

### 2. GuardPage + GuardClient 工厂模式

- Server / Client 守卫业务语义不同 (forbidden 抛错 vs router.replace 跳转), 不是可替换策略, 是**职责分离**.

### 3. message-feedback.tsx 状态机装饰器

- 折叠/展开是两个 React 子组件按 `open` 切换, 已经是正确写法. 状态机反而引入新概念.

### 4. status-badge.tsx 5 状态再抽模式

- 已经是 3 个 Record lookup (`CUSTOM_STYLE` / `LABEL` / `VARIANT`), 项目规约 §业务 enum 走 lookup 已满足.

### 5. composer-attachments.tsx 上传链 (presign → fallback → error) 装饰器

- 装饰器适合**多步骤横切** (withMemoryHooks), 当前上传链是线性 if-try-catch, 加装饰器反而**降低可读性**.

### 6. auth Provider 抽单例

- zustand store **已经是单例模式等价物** (React 19 推荐做法). Context Provider 已被 store 取代.

## 扫描方法说明

### 数据来源

- **文件清单**: `find packages/web/components/{chat,knowledge,json,decode,evaluate,settings,motion,auth,layout,i18n} -maxdepth 1 -type f \( -name "*.tsx" -o -name "*.ts" \) ! -name "*.test.*" ! -name "index.ts"`, 共 49 个生产文件, 3 369 行.
- **代码阅读**: 逐文件 Read 完整内容 (除 chat-shell.tsx / shared-chat-view.tsx 等少数简单文件抽 Read 部分行).
- **重复点搜索**:
  - `QueryClient|QueryClientProvider` → 发现 3 处完整相同的 useState 工厂单例 + Provider 样板
  - `staleTime: Infinity|gcTime: 0` → 3 处默认配置完全一致
  - `useTranslations|translation\(` → 仅是 i18n 调用, 无模式重复
  - `renderEmpty|EMPTY_HINT|EMPTY_PLACEHOLDER` → 仅是字符串常量, 不是模式重复
  - `renderStep|renderRow|renderItem` → 各自组件内 1 处, 无横向重复
- **lib/ 已有模式调研**: `lib/chat/factory.ts` (策略) + `lib/chat/memory-integration.ts` (装饰器) + `lib/chat/storage.ts` (Facade) + `lib/parse/parse-{json,excel,csv}.ts` (3 个并行解析器, **当前未统一为策略**) + `lib/theme/use-theme.ts` (Context 单例).

### ROI 判定方法

1. **重复度量化**: 用 Grep 计数模式出现次数 (QueryClient 自包 3 处, EMPTY_HINT 4 处但语义不同).
2. **行数对比**: 估算重构前后代码行 (含新增抽象文件 + 调用方修改).
3. **风险评估**: 业务组件 vs 基座组件 (motion 库、auth Provider 是基座, 改动需谨慎; 业务编排组件风险低).
4. **项目规约核对**: CLAUDE.md §业务 enum 走 lookup / §函数封装 (3 行重复 3 次抽) / §TDD 测试驱动 / §不改基座.

### 不在本次审计范围

- `components/common/` (已审, 报告 p1/p2 涵盖)
- `components/ui/` (shadcn 封装, 项目规约禁止改)
- `*.test.tsx` 测试文件
- `lib/` 下设计模式 (已在 P3 子任务 Agent A / C 范围)
- 后端 Python (packages/service/) 的设计模式 (非本次范围)

### 总评

- **业务组件层设计模式覆盖度已经很高**, 主要的策略/装饰器/Facade 都已经下沉到 `lib/` 层.
- **唯一高 ROI 候选**: knowledge/ QueryClient 样板 (3 处重复).
- **其余**: 都是单一职责 UI 编排, 不适合抽模式. **强行套模式会违反 CLAUDE.md §严禁绕过规则 §YAGNI**.