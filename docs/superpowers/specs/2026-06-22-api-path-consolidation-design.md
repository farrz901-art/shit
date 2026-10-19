# API 路径统一设计方案

**日期**: 2026-06-22
**目标**: 消除所有硬编码 `"/api/..."` 路径，统一走 `lib/api/` 封装

---

## 当前问题

所有 `"/api/..."` 路径散落在各层代码中：

| 位置 | 文件数 | 示例 |
|------|--------|------|
| `_actions/` | 5 | `account.ts`, `evaluate.ts`, `account-settings.ts` |
| `[locale]/pages/` | ~57 | admin/dicts, evaluate, health, knowledge, output, submissions |
| `components/` | 11 | auth-bootstrap, chat-shell, health-dot |
| `lib/`（非 lib/api） | 9 | `lib/chat/dify.ts`, `lib/buyer-profile/api.ts` |
| 根目录 | 4 | `proxy.ts`, `hooks/use-lookup.ts` |

**约 78 个文件需要修改。**

## 规则

1. **`lib/api/config.ts`** — 唯一持有 `apiFetch` / `apiProxy` 定义
2. **`lib/api/<domain>.ts`** — 每个后端模块一个 wrapper 文件，封装所有 API 调用
3. **所有 `.ts`/`.tsx` 文件** — 只能 `import { xxx } from "@/lib/api/<domain>"`，禁止直接出现 `"/api/"` 字符串
4. **`_actions/*` 也走 lib/api** — server action 不直调 apiFetch

## 目标文件结构

```
lib/api/
  config.ts          ← apiFetch / apiProxy（已有，不动）
  errors.ts          ← ApiError / NetworkError（已有，不动）
  approvals.ts       ← 已有
  auth.server.ts     ← 已有（server-only）
  buyer-profile.ts   ← 新建（从 lib/buyer-profile/api.ts 移过来）
  chat.ts            ← 已有
  chat-share.ts      ← 已有
  decode.ts          ← 新建
  dicts.ts           ← 新建（admin/dicts 相关）
  dify.ts            ← 新建（从 lib/chat/dify.ts 移过来）
  evaluate.ts        ← 已有
  health.ts          ← 已有
  health-pages.ts    ← 新建（health 页面组件用）
  ingest.ts          ← 已有
  knowledge.ts       ← 已有
  lookups.ts         ← 已有
  memory.ts          ← 已有
  query-client.ts    ← 已有
  query-keys.ts      ← 已有
  rsc-queries.ts     ← 已有
  submissions.ts     ← 新建（审核相关）
  system.ts          ← 已有
```

## 迁移步骤

### Phase 1: 新建缺失的 6 个 wrapper

新建 `lib/api/{decode,dicts,dify,health-pages,submissions,buyer-profile}.ts`，把散落在各处的 API 调用封装进来。

| 新文件 | 替代的文件 |
|--------|-----------|
| `lib/api/decode.ts` | `decode/page.tsx`, `decode/series-dialog.tsx` |
| `lib/api/dicts.ts` | admin/dicts 下 7 个组件 |
| `lib/api/dify.ts` | `lib/chat/dify.ts`（移过来） |
| `lib/api/health-pages.ts` | health/ 下 health-client, services-grid 等 |
| `lib/api/submissions.ts` | submissions/ 下 approval-row, submissions-tabs 等 |
| `lib/api/buyer-profile.ts` | `lib/buyer-profile/api.ts`（移过来） |

### Phase 2: 修改 78 个文件的 import

每个文件只改 import 行，不改逻辑。例如：

```typescript
// 改前
import { apiFetch } from "@/lib/api/config";
const res = await apiFetch<Data>("/api/knowledge/datasets");

// 改后
import { fetchDatasets } from "@/lib/api/knowledge";
const res = await fetchDatasets();
```

### Phase 3: 删除被替代的文件

- 删除 `lib/buyer-profile/api.ts`（转到 `lib/api/buyer-profile.ts`）
- 保留 `lib/chat/dify.ts`（它还包含 class DifyChatProvider，不只是 API 调用）
- 保留 `lib/buyer-profile/api.ts` 的删除在确认无引用后

### Phase 4: 验证

```bash
# 1. 确保没有残留的硬编码路径（允许在 lib/api/ 和测试文件内）
grep -rn '"/api' --include="*.ts" --include="*.tsx" packages/web/ \
  | grep -v "node_modules\|\.test\|\.next\|lib/api/\|app/api/\|\.d\.ts" \
  || echo "0 violations ✅"

# 2. 全量测试
cd packages/web && bun run test:coverage
# Expected: 0 failed

# 3. Lint
cd packages/web && bun run lint
# Expected: 0 warnings
```

## 不处理（明确保留）

- `app/api/[...path]/route.ts` — BFF 代理路由，需要硬编码路径
- `playwright.config.ts` — E2E 配置，非业务代码
- `vitest.setup.ts` — 测试配置
- `proxy.ts` — 开发代理配置

## 执行计划

`grep -rn '"/api' | grep -v node_modules | grep -v lib/api | grep -v app/api` = 0 为完成标准。

迁移后预计总改动：**约 78 个文件，~150 行 import 改动，0 行逻辑改动。**
