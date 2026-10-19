# code-quality-2026-06-19 阶段交付 (2026-06-20 暂停)

## 状态

- **分支**: `code-quality-2026-06-19`
- **最后一次 commit**: `ce9a329 fix: resolve B7 merge conflicts — 0 fail 0 typecheck`
- **当前工作树**: 有大量 B23-B31/chat/header 等 unstaged 改动 + 18 个 rename staged 但 import 还没全改完

## 已完成 (5/5 phase)

### Phase A — 测试隔离 ✅
- 1093 passed / 0 fail / 0 errors
- `packages/service/tests/conftest.py` 全局 autouse fixture `mock_all_db_connections`
- mock 了: `src.storage.engine._engine` / `session_scope` (4 个 namespace) / fakeredis / object_store / neo4j / permission_cache
- 修了 `src/kg/audit_models.py` 重复 index bug

### Phase B — oxlint 清零 ⚠️ 进行中 (~525/3415 完成)
- 基础线 3415 → 当前剩余 ~2725 warning
- 已完成: B6/B7 (lib/chat 重写, MERGE_CONFLICT 修完) / B11-B22 部分 / B23-B31 部分
- **B32 (filename case 扫尾) 未开始**: 126 文件 PascalCase → kebab-case (admin/ 路由 + components 根 + lib/)
- **B33 (final verification) 未开始**

### Phase C — 覆盖率 ⚠️ 未开始
- 后端 74.1% → 目标 80%
- 前端 66.75% → 目标 75%

### Phase D — CI workflow ✅
- `.github/workflows/ci.yml`
- services: pgvector/pgvector:pg18 + redis:7-alpine
- jobs: backend (ruff/pyright/alembic/pytest) + frontend (oxfmt/oxlint/tsgo/vitest)

### Phase E — CLAUDE.md ✅
- 3 个 CLAUDE.md 都加了 "Phase A 测试隔离" + "Phase B 零 lint" 段落
- 项目级 CLAUDE.md 锁了 ruff/pyright/oxlint/tsgo 0 error 才 commit

## 关键技术决策

1. **worktree 并行 B 阶段**: B7-B31 拆成 5 个 agent 并发跑 (B7/B11/B12/B13/B14-B22/B23-B31)
2. **不绕 oxlint**: 用户明确反对 `eslint-disable-next-line sort-imports` 当 workaround
3. **kebab-case 文件名强制**: 18 个 rename 已 staged (PascalCase → kebab-case), 但 import 修复仅 3 个 (AdminInvitesTable / ChatShell / UserMenu)
4. **重复 index 修复**: `kg/audit_models.ts` `ts` 列去 `index=True`, 保留 `__table_args__` 显式 index
5. **Magic 字符串提取**: `packages/web/const/index.ts` 集中常量 (ZERO/HTTP_OK/FIVE/MS_PER_SECOND 等)

## 未完成清单 (按优先级)

### 1. 当前 staged 18 个 rename 收尾
- 3 个 typecheck 错误已修 (AdminInvitesTable / ChatShell / UserMenu)
- **还需要 grep 全仓** `import .*ChatShell|UserMenu|PageGuard|ClientPageGuard|ConversationList|MessageBubble|MessageFeedback|MessageList|ThinkingTrace|MessageList|MessageFeedback|CitationPanel|Composer|AdminInvitesTable` 找遗漏
- 实际 typecheck 跑过 0 error, 应该是搜索 grep 验证完整

### 2. 2 个 vitest fail
- 错误位置: `beginWork` 渲染错 (某个 RSC 组件 import path 错)
- 1 个 test file 失败 / 155 passed
- 2 个 case 失败 / 717 passed
- 详情没拿到 (test 跑完没看到 FAIL 名字, 需重跑 grep)

### 3. B32 filename-case (126 文件)
- 18 个已 staged (chat/ + components 根 + admin/invites)
- 剩余 ~108 个在 `app/[locale]/admin/{permissions,users,dicts,knowledge}/` + `lib/chat/*` + `components/common/*` + `components/chat/*` 等

### 4. Phase C 覆盖率
- 后端 74.1% → 80% 差 ~6%, 主要漏点: chat router / auth handlers / kg service
- 前端 66.75% → 75% 差 ~8%, 主要漏点: RSC pages / 表单组件 / 数据获取 hook

### 5. 收尾 commit 策略
- 当前 unstaged 文件 = B23-B31/chat/header agent 跑完的成果, 还没验证通过
- 应先跑 typecheck + test + lint 全套, 再分批 commit:
  - `chore: rename PascalCase → kebab-case (B32 part 1)`
  - `chore: rename PascalCase → kebab-case (B32 part 2)`
  - `refactor: B23-B31 oxlint cleanup`
  - `refactor: B12 components/common cleanup`
  - `refactor: B13 components/chat cleanup`
  - `test: Phase C 覆盖率提升`

## 背景 agent 状态

6 个 agent 在跑 (B7-B31), 启动时通知 completed:
- B7: af80ffad396b59228
- B11: a08b5b9c92bec336d
- B12: a4840b5c8da847f41
- B13: a6035ca948b76f318
- B14-B22: aebd7ad141ae793bc
- B23-B31: a08261897feddb2c0

跑完结果散落在工作树 (unstaged), 验证 + commit 没做。

## 注意事项

- **不要**把 `→` 换成别的 (oxlint no-arrow-function-return 不会要求改箭头)
- **不要**用 `// eslint-disable-next-line sort-imports` 绕过 — 实际排序
- 文件名强制 kebab-case, 禁止 PascalCase/camelCase/underscore
- magic 数字 → `packages/web/const/index.ts` 命名常量
- i18n key 用中文 (`t("中文 key")`), zh.json identity, en.json 翻译
- 路由跳转必须 `@/i18n/navigation` 的 useRouter
- husky pre-commit 跑 lint-staged + tsgo + vitest + format:check, 0 error 才 commit
- pre-existing test fail 列 `KNOWN_ISSUES.md`, 不雪崩修
- 别人 worktree stash → 不 reset / 不 checkout
