# 2026-06-14 typecheck 全量扫描

## 摘要

| 维度              | 命令                                    | 错误数 | 状态      |
| ----------------- | --------------------------------------- | ------ | --------- |
| 前端类型          | `bun run typecheck` (= `tsgo --noEmit`) | **0**  | ✅        |
| 后端类型          | `uv run pyright src`                    | **0**  | ✅        |
| 前端 lint error   | `bun run lint` (= `oxlint .`)           | **30** | ❌        |
| 后端 lint error   | `uv run ruff check src tests scripts`   | **3**  | ⚠️        |
| 前端 lint warning | `bun run lint`                          | ~2700  | ⚠️ 技术债 |

**结论: 类型层 0 错. lint 是真正的债.** 30 个 error 全可一次性 fix (24 个 unused-vars + 5 个 complexity + 1 个 mjs 未用 import + 3 个 ruff I001).

## A. 前端 lint error (30 个, 29 个文件)

### A1. `no-unused-vars` (24 个, 100% 可自动修)

都是 import / 局部变量 / 形参 写了没用, 全在前几次 commit 改文件后没清理.

| 文件                                                                                          | 行    | 名字                                              | 类别                          |
| --------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------- | ----------------------------- |
| `app/api/auth/anon/proxy.test.ts`                                                             | 8     | `NextResponse` (import)                           | 测完了没删                    |
| `components/chat/ChatShell.tsx`                                                               | 103   | 形参 `cur`                                        | 抽 helper 时漏改              |
| `components/common/dialog/app-dialog.test.tsx`                                                | 36    | 局部 `container`                                  | 删了断言没删变量              |
| `components/common/form/form.tsx`                                                             | 18    | 函数 `getByPath`                                  | 删了调用方没删函数            |
| `components/knowledge/DatasetSwitcher.test.tsx`                                               | 1     | `fireEvent` (import)                              | 改测试方案时漏删              |
| `components/knowledge/SchemaFieldRenderer.tsx`                                                | 10    | `NodeDef` / `RelationDef` (type import)           | 改 SchemaFieldRenderer 时漏删 |
| `components/settings/settings-dialog.test.tsx`                                                | 3     | `userEvent` (import)                              | 同上                          |
| `app/[locale]/admin/users/_components/AdminUsersTable.tsx`                                    | 20    | 形参 `onChanged`                                  | Props 改完回调签名没改        |
| `app/[locale]/health/_components/HealthClient.test.tsx`                                       | 5     | `waitFor` (import)                                | 改断言时漏删                  |
| `app/[locale]/knowledge/batch/page.tsx`                                                       | 15    | `CSS_EASE_STR` (import)                           | 删动画时漏删                  |
| `app/[locale]/knowledge/dataset-documents/[dataset_id]/_components/DatasetDocumentsTable.tsx` | 43    | 局部 `setError`                                   | 改错误处理时漏删              |
| `app/[locale]/knowledge/nodes/_components/NodesTable.tsx`                                     | 6     | `CSS_EASE` / `DUR` (import)                       | 同 batch                      |
| `app/[locale]/output/new/page.test.tsx`                                                       | 2     | `fireEvent` (import)                              | 同上                          |
| `app/[locale]/output/new/page.tsx`                                                            | 8, 12 | `motion` / `AnimatePresence` / `DUR` / `CSS_EASE` | 删 framer-motion 时漏删       |
| `app/[locale]/output/page.tsx`                                                                | 8     | `API_BASE` (import)                               | 改 BFF 透传时漏删             |
| `app/[locale]/reset-password/page.tsx`                                                        | 13    | 局部 `t` (翻译 hook)                              | 改 UI 时漏删                  |
| `app/[locale]/submissions/_components/ApprovalRow.test.tsx`                                   | 26    | 形参 `queryKey`                                   | 抽 mock 时漏改                |
| `e2e/01-decode.spec.ts`                                                                       | 10    | 局部 `health`                                     | 改 e2e 时漏删                 |
| `scripts/refactor-api-base.mjs`                                                               | 8     | `glob` (import)                                   | 重构完 mjs 没清理             |

**修法**: `bun run lint:fix` 自动修全部 (oxlint 支持 `no-unused-vars` autofix).

### A2. `complexity > 20` (5 个, 需手动拆)

oxlint 不会自动降复杂度, 只能拆函数. 列出来供下次 plan 排期:

| 文件                                                             | 函数                          | 复杂度 | 来源                                             |
| ---------------------------------------------------------------- | ----------------------------- | ------ | ------------------------------------------------ |
| `lib/api/config.ts`                                              | `apiFetch`                    | 25     | 核心封装, 6 个 try/catch 分支 + 4xx/5xx 不同处理 |
| `lib/chat/dify.ts`                                               | `*normalize` (private method) | 30     | 归一化逻辑, 多次 if/else 链                      |
| `app/[locale]/decode/page.tsx`                                   | `DecodePage`                  | 22     | 页面里有 3 个 useState + 多分支渲染              |
| `app/[locale]/knowledge/triples/_components/TriplesForm.tsx`     | 匿名 fn                       | 23     | submit 路径分支多                                |
| `app/[locale]/output/[task_id]/_components/TaskDetailClient.tsx` | `TaskDetailClient`            | 22     | 页面状态机多分支                                 |

**修法**: 抽 helper, 不用动业务. 复杂度从 25 降到 ~12 拆 3 个 fn 即可.

## B. 后端 ruff I001 (3 个, 100% 可自动修)

```
src\retrieval\vector_store.py:105:9 - imports 块乱
```

**修法**: `uv run ruff check --fix src tests scripts` 自动修.

## C. 前端 lint warning (~2700 条)

按规则 top10:

| 规则                   | 数量 | 性质                                              |
| ---------------------- | ---- | ------------------------------------------------- |
| `id-length`            | 579  | 单字母变量 `i`/`j`/`x` 触发, 项目里大量存在       |
| `no-magic-numbers`     | 571  | 数字字面量未提常量, 真实业务需求                  |
| `sort-imports`         | 430  | import 排序, 跟 oxfmt 重复 (oxfmt 已排, 规则冲突) |
| `func-style`           | 298  | `const fn = () =>` vs `function fn()` 不统一      |
| `sort-keys`            | 277  | 对象字面量 key 排序                               |
| `no-ternary`           | 242  | 嵌套三元被禁                                      |
| `capitalized-comments` | 84   | 注释首字母小写, 业务注释用中文常首字不是大写      |
| `curly`                | 63   | 单行 if 必须加大括号                              |
| `new-cap`              | 55   | `new Map()` 必须大写调用                          |
| `max-statements`       | 24   | 函数内语句过多                                    |

**结论**: warning 不阻塞 commit, 但累积到 ~2700 时 lint 跑出来是噪音. 至少把 `id-length` 和 `sort-imports` 关掉 (跟 oxfmt 重复且触发面太大), 留 `no-magic-numbers` / `func-style` / `curly` 当代码质量护栏.

## D. 跟之前 audit 的关系

`docs/audit/2026-06-14-full-test-suite-scan.md` 记的是测试 fail 修完 (49→0). 本次是 typecheck/lint 层.

## 修法优先级 (建议直接修, 不另开 plan)

1. **本轮 1 个 commit**: `bun run lint:fix` + `uv run ruff check --fix` (一次清 ~27 个)
2. **本轮 1 个 commit**: 拆 5 个 complexity 高的函数 (动结构, 单独 batch)
3. **下一轮 plan**: warning 治理 (关 2 个规则 + 把 id-length 调到 ≥2)
4. **本轮 1 个 commit**: 修 `web/CLAUDE.md` 里 "next-themes 0.4.x" 老约定, 改成 "自实现 theme provider"
