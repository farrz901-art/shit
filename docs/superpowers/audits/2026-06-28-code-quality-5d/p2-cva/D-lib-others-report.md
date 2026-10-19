# P2 维度 ② CVA 重写机会 — Agent D (lib+其它 ~89 files)

> 审计时间: 2026-06-28
> 审计范围: `packages/web/` 下除 `components/`、`app/`、`tests/` 之外的所有 `.ts`/`.tsx` 文件 (排除 `.test.ts*`)
> 审计目标: 找出能用 CVA (Class Variance Authority) 重写的 UI 变体组件

## 扫描概览

| 指标 | 数值 |
|---|---|
| 总文件数 | **89** |
| 纯 TS 逻辑 (不适用 CVA) | **87 (97.8%)** |
| 含 JSX 的文件 (可能适用) | **2** |
| 可用 CVA 重写的文件 | **0** |
| 高 ROI 发现 | **0** |

## 关键发现

本范围几乎全部是业务逻辑层 / 数据层 / 客户端层, **与 UI 变体无关**:

- **lib/api/* (23)** — 纯 fetch 客户端 / 类型定义 / React Query 封装 (`query-keys`, `query-client`, `rsc-queries`)
- **lib/chat/* (13)** — 业务适配器 / SSE 解析 / 状态机 (Dify / OpenAI 协议封装)
- **lib/hooks/* (11)** — 纯 React hooks (use-dialog / use-confirm / use-pagination / use-polling 等)
- **lib/store/* (5)** — zustand store (app-store / auth-store / ui-store) + 1 个 Context Provider
- **lib/auth/* (3)** — 权限/角色类型与工具
- **lib/buyer-profile/* (2)** — 业务类型与 hooks
- **lib/dom/* (2)** — DOM 工具 (download)
- **lib/evaluate/* (2)** — 评估类型与导出
- **lib/parse/* (3)** — CSV / Excel / JSON 解析
- **lib/server/* (1)** — RSC 服务端 evaluate
- **lib/theme/* (3)** — 主题配置 + useTheme 转发到 `@/components/theme-provider`
- **lib/test-utils/* (2)** — 测试 wrapper + 导出
- **lib 顶层 (11)** — `utils.ts` (cn 函数) / `motion.ts` (framer-motion variants object) / `schema-types.ts` / `log.ts` / `dify-datasets.ts` / `rate-limiter.ts` 等
- **const/index.ts (1)** — 全局常量 (数字/时间/HTTP 状态码)
- **i18n/* (5)** — `navigation.ts` / `provider.tsx` / `request.ts` / `routing.ts` + 1 个测试 (i18n/provider.tsx 含 1 处 JSX Provider, 不适用 CVA)
- **scripts/duplication-report.ts (1)** — 构建时脚本
- **proxy.ts (1)** — Next.js middleware (路由守卫 + next-intl)

## 含 JSX 文件详细分析 (2 个)

| 文件 | JSX 类型 | CVA 适用性 |
|---|---|---|
| `lib/store/app-data.tsx` | `<Ctx value={...}>{children}</Ctx>` Context Provider | ❌ **不适用** — 单一 className (无), 仅传递数据, 无 UI 变体 |
| `lib/test-utils/intl-wrapper.tsx` | `<NextIntlClientProvider locale={...} messages={...}>{children}</NextIntlClientProvider>` 测试 wrapper | ❌ **不适用** — 单一 className (无), 测试环境 Provider, 无 UI 变体 |

## 边界场景检查

### `lib/motion.ts` (v3: 1 处提到 framer-motion variants object)
**❌ 不适用 CVA** — 这是 framer-motion variants object (含 `hidden`/`show` 状态的 motion 配置), 不是 className 变体管理. `RADIUS`/`SHADOW` 是 Tailwind class 常量表, 但:
- 用途是跨业务组件复用, 而非组件内部变体切换
- 没有 intent/size/variant 维度的 `cva` 模式调用
- 已经做了设计 token 集中 (单一事实源), 再套 cva 反而是过度抽象

### `lib/theme/themes.ts` (v3: 提到主题配置)
**❌ 不适用 CVA** — 主题数据 (`{ name, label, icon, colors }`), 通过 next-themes 切换 CSS variables, 跟 CVA 变体管理是两回事.

### `lib/store/app-data.tsx` (Context Provider)
**❌ 不适用** — Provider 不渲染 UI, 只传数据. 即使有样式, 单一形态无变体.

### `lib/store/ui-store.ts` (zustand store, 类型推测含样式状态)
**❌ 不适用** — 状态管理 (布尔/枚举), 不直接产 className, 无 CVA 必要.

### `proxy.ts` (Next.js middleware)
**❌ 不适用** — 路由重写/重定向逻辑, 无 JSX.

## ROI 判定汇总

| 等级 | 数量 | 文件示例 |
|---|---|---|
| ❌ 不适用 (纯 TS 逻辑) | 87 | `lib/api/*.ts`, `lib/chat/*.ts`, `lib/hooks/*.ts`, `lib/store/*.ts`, `lib/theme/*.ts`, `const/index.ts`, `proxy.ts`, `scripts/duplication-report.ts`, 等 |
| ❌ 不适用 (Provider 无变体) | 2 | `lib/store/app-data.tsx`, `lib/test-utils/intl-wrapper.tsx` |
| 🟢 低 ROI (无可优化空间) | 0 | — |
| 🔴 高 ROI (值得 CVA) | 0 | — |

## 结论

**本范围 0 个文件值得用 CVA 重写.**

`lib/` 区是**业务逻辑层** (API 客户端 / 状态管理 / hooks / 工具函数 / 类型定义 / middleware), 与**样式变体管理**无关. 即便存在少量 `.tsx` 文件 (2 个 Provider), 也是纯数据传递/测试包装, 不含 className 变体逻辑.

**P3-P5 维度审计时同样可跳过 `lib/`、`const/`、`i18n/`、`scripts/`、`proxy.ts` 范围**, 除非审计目标转向 API 设计 / 类型安全 / 中间件逻辑.

## 扫描方法说明

1. 用 `find` (bash) 列举 `lib/`、`const/`、`i18n/`、`scripts/` 下的所有 `.ts`/`.tsx` (排除 `.test.ts*`)
2. 用 `find ... ! -name "*.test.ts*"` 过滤测试文件
3. 定位 2 个含 JSX 的文件 (`lib/store/app-data.tsx` + `lib/test-utils/intl-wrapper.tsx`), 用 Read 工具逐一验证
4. 验证边界场景: `lib/motion.ts` (variants object) / `lib/theme/themes.ts` (主题数据) / `proxy.ts` (middleware)
5. 抽样确认 `lib/api/*`、`lib/hooks/*`、`lib/store/*` 为纯逻辑, 无 className 变体

**审计断言**: 如果未来 `lib/store/` 或 `lib/theme/` 下出现带 className 变体的组件 (size/variant/intent 多维), 应回头重新审计本范围. 当前快照下 0 个目标.