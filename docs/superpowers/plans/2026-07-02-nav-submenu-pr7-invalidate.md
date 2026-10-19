# PR7 — Cache Invalidation on Dict Edit

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When super_admin edits a `page_key` dictionary item via `/admin/dicts`, invalidate the frontend's `permissions` query so the next navigation re-fetches with new parent_id / is_group / icon metadata.

**Files:**
- Modify: `packages/web/lib/api/permissions.ts` (add `invalidatePermissions` helper)
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx` (call invalidation onSuccess)
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx` (call invalidation onSuccess)

---

## Task 7.1: Add invalidatePermissions helper

**Files:**
- Modify: `packages/web/lib/api/permissions.ts`

- [ ] **Step 1: Read current file**

Run: `cat packages/web/lib/api/permissions.ts`

- [ ] **Step 2: Add helper**

Append at end of `packages/web/lib/api/permissions.ts`:

```typescript
// (2026-07-02 nav spec §6) dict 编辑后失效权限缓存
import { queryClient } from "./query-client"; // 假设已有, 不存在则用全局 queryClient 实例

/** 失效 /api/permissions/me 的 query, 让下次 usePermissions 自动重 fetch. */
export const invalidatePermissions = (): void => {
  queryClient.invalidateQueries({ queryKey: ["permissions"] });
};
```

If `query-client.ts` doesn't expose a singleton, replace with the project's existing pattern (likely TanStack Query has a singleton via `QueryClient` provider). Run:

```bash
grep -r "new QueryClient" packages/web --include="*.tsx" --include="*.ts" -l 2>/dev/null | head -3
```

Use whatever pattern exists.

- [ ] **Step 3: Commit helper**

```bash
cd c:/doc/Code/rag
git add packages/web/lib/api/permissions.ts
git commit -m "feat(perm): add invalidatePermissions helper (PR7/1)"
```

---

## Task 7.2: Wire invalidate to dict edit/create dialogs

**Files:**
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx`
- Modify: `packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx`

- [ ] **Step 1: Read both files**

Run:
```bash
cat packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx
echo "---"
cat packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx
```

Look for `onSuccess` callback in mutation hooks.

- [ ] **Step 2: Add import**

In both files, add at top:

```typescript
import { invalidatePermissions } from "@/lib/api/permissions";
```

- [ ] **Step 3: Add invalidation call**

Find the `onSuccess` handler (likely in `useMutation({ onSuccess: () => { ... } })`). Add:

```typescript
onSuccess: () => {
  // 现有逻辑
  // (2026-07-02) dict 编辑后失效权限缓存 (仅 page_key dict 才需要, 但失效开销低, 全失效)
  if (dictCode === "page_key") {
    invalidatePermissions();
  }
},
```

If the dialog component doesn't have direct access to `dictCode`, find the prop chain.

- [ ] **Step 4: Run dicts tests**

Run: `cd packages/web && bun run test -- "app/[locale]/admin/dicts/" 2>&1 | tail -10`

Expected: existing tests pass.

- [ ] **Step 5: Commit invalidation**

```bash
cd c:/doc/Code/rag
git add "packages/web/app/[locale]/admin/dicts/_components/dict-item-editor.tsx" "packages/web/app/[locale]/admin/dicts/_components/dict-item-create-dialog.tsx"
git commit -m "feat(dicts): invalidate permissions cache on page_key edit (PR7/2)

super_admin 改 page_key 字典后, 下次导航自动拉新 metadata."
```

---

## Task 7.3: Verify no regressions

- [ ] **Step 1: Run full frontend test suite**

Run: `cd packages/web && bun run test 2>&1 | tail -15`

Expected: 764 baseline passed, no new failures.

- [ ] **Step 2: Run lint + format**

Run: `cd packages/web && bun run lint && bun run format:check`

Expected: 0 errors.

- [ ] **Step 3: Final commit if any fix**

```bash
cd c:/doc/Code/rag
git status
# 如有 lint/format, git add -u && git commit -m "chore(pr7): final lint/format"
```

---

## PR7 Definition of Done

- [ ] `invalidatePermissions()` helper added
- [ ] Dict edit + create dialogs trigger invalidation on page_key dict
- [ ] All tests still pass
- [ ] Ready for PR8 (E2E + docs)