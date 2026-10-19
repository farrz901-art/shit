# 前端测试覆盖率 70.87% → 75% 设计方案

## 现状

| 维度 | 当前值 | 目标 |
|------|--------|------|
| Lines | **70.87%** (4077/5752) | ≥ 75% (4314/5752) |
| Statements | 70.64% | — |
| Branches | 58.27% | — |
| Functions | 68.22% | — |

**缺口：~237 lines**（5752 × 5%）。

## 选文件原则

1. **只选有业务逻辑的文件** — 不测 shadcn 模板代码（form、calendar、command 等）
2. **优先低覆盖 + 易测** — mock 成本低，jsdom 可跑
3. **每批写完才跑覆盖率** — 不中途跑

## 目标文件

| 优先级 | 文件 | 当前 Lines | 未覆盖行 | 测试策略 | 预估贡献 |
|--------|------|-----------|----------|----------|----------|
| P0 | `lib/chat/openai.ts` | 13.2% | ~87 行 | mock apiProxy + ReadableStream + TextDecoder，构造 SSE 流测试 async generator | ~80 行 |
| P0 | `lib/chat/migration.ts` | 38.88% | ~62 行 | mock Dexie + sonner toast，测 performAnonToLoginMigration / downloadLocalBackup | ~55 行 |
| P1 | `lib/api/knowledge.ts` | 81.48% | ~34 行 | mock fetch，测每个 API 方法 | ~34 行 |
| P1 | `lib/api/ingest.ts` | 80.76% | ~32 行 | mock fetch，测 uploadViaPresign / taskDownload 异常路径 | ~32 行 |
| P2 | `components/common/dialog/app-dialog.tsx` | 22.22% | ~56 行 | 渲染测试 + open/close 受控 | ~56 行 |
| P2 | `components/common/dialog/app-confirm.tsx` | 15% | ~68 行 | 渲染测试 + confirm/cancel 回调 | ~68 行 |

**预估总贡献：~325 行，超出 ~88 行作为安全边际。**

## 不测的文件（明确排除）

- `app/api/[...path]/route.ts` — Next.js BFF 路由，需完整 Request 对象，jsdom 不支持
- `app/_actions/*` — server-only，vitest 不支持
- `components/ui/{form,calendar,command,popover,separator}.tsx` — shadcn 模板代码，纯渲染无业务价值
- `app/[locale]/error.tsx`、`loading.tsx`、`not-found.tsx` — Next.js 页面模板

## 批次计划

### 第 1 批：4 个测试文件（核心业务）

| 测试文件 | 对应源文件 | 策略 |
|----------|-----------|------|
| `lib/chat/openai.test.ts` | `lib/chat/openai.ts` | mock `apiProxy` 返 mock Response，构造 SSE 块测试流式解析 |
| `lib/chat/migration-extra.test.ts` | `lib/chat/migration.ts` | mock Dexie + sonner，测 performAnonToLoginMigration + downloadLocalBackup |
| `lib/api/knowledge-extra.test.ts` | `lib/api/knowledge.ts` | mock fetch，测每个 API 方法（createTriples / fetchDatasets / fetchStats 等） |
| `lib/api/ingest-extra.test.ts` | `lib/api/ingest.ts` | mock fetch，测 uploadViaPresign / taskDownload 异常路径 / parseFilename |

### 第 2 批（如果第 1 批不够）：2 个测试文件

| 测试文件 | 对应源文件 | 策略 |
|----------|-----------|------|
| `components/common/dialog/app-dialog.test.tsx` | `components/common/dialog/app-dialog.tsx` | 渲染 + open/close 受控 |
| `components/common/dialog/app-confirm.test.tsx` | `components/common/dialog/app-confirm.tsx` | 渲染 + confirm/cancel 回调 |

### 执行顺序

1. 写第 1 批 4 个测试文件
2. `bun run lint` 检查（0 warning）
3. **跑一次覆盖率验证**（3 分钟）
4. 如果不足 75%，写第 2 批 2 个文件
5. 再次跑覆盖率验证
6. 达到目标后合并

## 风险

- `openai.ts` 的 async generator 在 jsdom 下 mock ReadableStream 可能不稳定，如果太难测则跳过 `sendMessage` 方法，只测构造函数和 name 属性
- `migration.ts` 的 `downloadLocalBackup` 依赖 `document.createElement("a")`，jsdom 支持，但 click 后下载不触发（不影响覆盖率统计）
