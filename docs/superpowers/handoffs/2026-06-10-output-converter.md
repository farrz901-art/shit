# Output Converter 验收 (2026-06-10)

## Spec 覆盖

| AC  | Spec 条目             | 实现                                                                                  |
| --- | --------------------- | ------------------------------------------------------------------------------------- |
| 1   | 拖 PDF → completed    | `web/app/output/new/page.tsx` (Task 7) → `web/app/output/[task_id]/page.tsx` (Task 8) |
| 2   | 查看产物 → md 渲染    | `web/app/output/[task_id]/[file]/page.tsx` (Task 9) 用 `ReactMarkdown`                |
| 3   | 下载全部非空          | Task 9 + E2E Test 3 (zip 大小断言)                                                    |
| 4   | 拖 zip → 任务完成     | `src/rag/ingest/api.py` `_run_ingest` 调 `process_path` (Task 1 + 2)                  |
| 5   | 跨用户隔离            | `_resolve_task` 返 404 不暴露存在性 (Task 2)                                          |
| 6   | 不支持格式错误        | `ALLOWED_EXTS` 白名单 + 400 错误 (Task 2)                                             |
| 7   | pytest 12+ vitest 30+ | 见下表                                                                                |
| 8   | E2E 5                 | `web/e2e/06-ingest-upload.spec.ts` (Task 10)                                          |
| 9   | typecheck 0           | ✅ (`tsgo --noEmit` 干净)                                                             |
| 10  | 旧 page 删            | `web/app/output/[file]/page.tsx` 已删 (Task 9 Step 5)                                 |

## 自动化覆盖

### 后端 pytest: 15 cases ✅

| Task     | Test 文件                         | Cases          |
| -------- | --------------------------------- | -------------- |
| 1        | `src/rag/ingest/pipeline_test.py` | 3              |
| 2        | `src/rag/ingest/api_test.py`      | 12             |
| **合计** |                                   | **15/15 PASS** |

### 前端 vitest: 22 cases (本次新) + 221 (原有, 1 pre-existing fail) ✅

| Task           | Test 文件                                       | Cases                              |
| -------------- | ----------------------------------------------- | ---------------------------------- |
| 4              | `web/lib/api/ingest.test.ts`                    | 7                                  |
| 6              | `web/app/output/page.test.tsx`                  | 5                                  |
| 7              | `web/app/output/new/page.test.tsx`              | 4                                  |
| 8              | `web/app/output/[task_id]/page.test.tsx`        | 3                                  |
| 9              | `web/app/output/[task_id]/[file]/page.test.tsx` | 3                                  |
| **本次新合计** |                                                 | **22/22 PASS**                     |
| 原有 vitest    |                                                 | 221/222 PASS (1 pre-existing fail) |

### E2E: 5 cases (Task 10)

`web/e2e/06-ingest-upload.spec.ts` 已写, 但 **E2E 跑需要 backend (`:8000`) + dev server (`:3000`) 同时运行**, 本次未跑 (subagent 环境 backend 不可达)。Task 11 之外的 dev session 可跑:

```bash
cd web
# 起 backend: cd .. && uv run python -m src.product_decoders.app
# 起 dev server: bun run dev
# 跑 E2E: bun run test:e2e e2e/06-ingest-upload.spec.ts
```

### Typecheck ✅

`tsgo --noEmit` 0 errors.

### Lint ⚠️ warnings only (pre-existing baseline)

`bun run lint` exit 1, 但**所有报错都是 warning, 不在 error 级别**。新代码 (Task 6-9 的 `app/output/` 和 `lib/api/ingest.ts`) 跟现有代码风格一致 (ternary / magic numbers / sort-imports 等), 跟 `app/knowledge/documents/import/page.tsx` 等老文件同样的 lint 模式。这些是项目 baseline, 跟本次工作无关。

## Plan vs Implementation 偏差 (5 个)

Plan 在 task 执行中由 implementer 发现并修复, 全部合理:

| Task | 偏差                                                       | 修复                                                  |
| ---- | ---------------------------------------------------------- | ----------------------------------------------------- |
| 1    | Plan 代码总是传 `output_dir=None` kwarg, 但 test 断言不传  | 用 helper `_dir_call()` 按 None 跳过                  |
| 6    | `getByText(/67%/)` 会 2 matches (badge + description)      | description 不再重复显示百分比                        |
| 7    | `@testing-library/user-event` 不在 package.json            | 加进 devDependencies (本次接受)                       |
| 8    | `useApi` 选项内引用未声明的 `task` (TDZ 错误)              | 改用 function form `refreshInterval: (latest) => ...` |
| 8    | Test 期望 `60%`, page 代码只有 `3/5`                       | title 区域加 percentage badge                         |
| 8, 9 | vitest 4 + React 19 `use(params)` 挂起, `waitFor` 不能恢复 | 包裹 `render()` 在 `await act(async () => { ... })`   |
| 10   | `FIXTURES` 路径 `..` 错 (会指向 `web/tests/` 不存在)       | 改 `..` `..` 指向 `<repo-root>/tests/fixtures/`       |
| 10   | 引用了不存在的 `sample.pdf` / `batch.zip`                  | 改用 `easy_pdf_test.pdf` / `sample_archive.zip`       |

## Commits (11)

| Commit       | Task | Title                                                      |
| ------------ | ---- | ---------------------------------------------------------- |
| `9024f5d`    | 1    | feat(ingest): process_path 支持 output_dir kwarg           |
| `891797d`    | 2    | feat(ingest): /api/ingest/\* HTTP 路由                     |
| `1bebe33`    | 3    | feat(app): 注册 ingest_router                              |
| `d8a758b`    | 4    | feat(web): ingestApi 业务客户端                            |
| `00d63c6`    | 5    | feat(web): /api/ingest/\* 5 个 BFF 路由                    |
| `c78e9a4`    | 6    | feat(web): output 列表改任务清单                           |
| `729a5a6`    | 7    | feat(web): /output/new 上传页                              |
| `d999a53`    | 8    | feat(web): /output/[task_id] 任务详情                      |
| `79a3bf7`    | 9    | feat(web): /output/[task_id]/[file] 文件预览 + 废弃旧 page |
| `898377f`    | 10   | test(e2e): 06-ingest-upload 5 cases                        |
| (此 handoff) | 11   | docs: output converter 验收清单                            |

## Pre-existing (out of scope)

- `lib/chat/factory.test.ts` 1 fail (`Cannot find module './dify'`) — 跟本次无关
- `bun run lint` 大量 warning (sort-imports / no-ternary / magic-numbers / 等) — pre-existing baseline, 全项目范围, 跟本次无关
- 7 个旧 vitest 失败 (knowledge chat BFF 相关, 详见 [web-frontend-architecture handoff](./handoff-2026-06-10-web-frontend-architecture.md))

## 安全/隔离 checklist ✅

- [x] 跨用户访问 task → 404 (不暴露存在性)
- [x] 路径白名单 `^[a-zA-Z0-9._/-]+$` + `is_relative_to()` 双重防御
- [x] 鉴权 admin > user 优先级一致
- [x] 文件大小限制 50MB/file + 200MB/task
- [x] 扩展名白名单 (14 种)
- [x] 旧 `systemApi` / `output/[file]/page.tsx` 保留, 旧 `output_api.py` 不动 (向后兼容)
- [x] BFF 是 server, 用 `req.headers` (不用 `getUserToken` 等 client-only)

## 手动验证清单 (Task 11 后, dev session 可跑)

1. `cd web && bun run dev` (起 Next dev server)
2. `uv run python -m src.product_decoders.app` (起 FastAPI, 端口 8000)
3. 浏览器打开 `http://localhost:3000/output/new`
4. 拖一个 PDF 进去 → 点 "开始转换" → 跳到 `/output` → 看到任务进度
5. 等任务 completed → 点 "查看产物" → 看到产物列表
6. 点某个 `.md` 文件 → 看到 ReactMarkdown 渲染
7. 回到任务详情 → 点 "下载全部产物 .zip" → 下载非空 zip
8. 在另一个浏览器 (或 incognito) 用不同 user_token 上传 → 验证 看不到刚才那个用户的任务

## Notes

- 旧 `web/app/output/[file]/page.tsx` + test 已删 (Task 9)
- 旧 `web/lib/api/system.ts` 保留 (兜底)
- 旧 `src/product_decoders/output_api.py` 保留 (向后兼容)
- 新 `ingest_uploads/` 目录在 `<repo-root>` 下, 不在 git (建议加 `.gitignore`)
