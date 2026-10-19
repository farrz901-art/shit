# Navigation Submenu + Permission Tree Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add submenu support to the top navigation, refactor the permission matrix to a tree-shaped checkbox UI, and keep the existing data dictionary mechanism intact.

**Architecture:** Zero DB schema change. Extend `page_key` items via `metadata_json` (parent_id / is_group / icon). Add a pure-function `buildNavTree()` to assemble the tree on the frontend. Reuse existing `AppDropdownMenu` for desktop hover dropdowns. New generic `<TreeCheckbox>` for the permission matrix. Phase-1 migration keeps existing `require_page("admin")` guards; sub-pages don't enter `role_permissions`.

**Tech Stack:**
- Backend: Python 3.14, SQLAlchemy 2.0, FastAPI, Redis cache
- Frontend: TypeScript 8, React 19, Next.js 16, TanStack Query 5, shadcn/ui (Radix), lucide-react, vitest + jsdom, Playwright

**Spec:** [docs/superpowers/specs/2026-07-02-nav-submenu-design.md](../specs/2026-07-02-nav-submenu-design.md)

**Plan structure:** 8 PRs, each ≤300 lines diff, independently rollback-able. Plan split into per-PR files for clarity.

| PR | File | Scope | Estimated diff |
|---|---|---|---|
| PR1 | [2026-07-02-nav-submenu-pr1-backend.md](2026-07-02-nav-submenu-pr1-backend.md) | Backend cache metadata passthrough + yaml seed + tests | ~80 lines |
| PR2 | [2026-07-02-nav-submenu-pr2-nav-tree.md](2026-07-02-nav-submenu-pr2-nav-tree.md) | buildNavTree pure function + types + 15 tests | ~250 lines |
| PR3 | [2026-07-02-nav-submenu-pr3-header.md](2026-07-02-nav-submenu-pr3-header.md) | Header desktop hover dropdown + 8 tests | ~200 lines |
| PR4 | [2026-07-02-nav-submenu-pr4-mobile.md](2026-07-02-nav-submenu-pr4-mobile.md) | Mobile hamburger drawer + 3 tests | ~180 lines |
| PR5 | [2026-07-02-nav-submenu-pr5-tree-checkbox.md](2026-07-02-nav-submenu-pr5-tree-checkbox.md) | Generic TreeCheckbox + 6 tests | ~250 lines |
| PR6 | [2026-07-02-nav-submenu-pr6-matrix-tree.md](2026-07-02-nav-submenu-pr6-matrix-tree.md) | Permission matrix tree + 10 tests | ~280 lines |
| PR7 | [2026-07-02-nav-submenu-pr7-invalidate.md](2026-07-02-nav-submenu-pr7-invalidate.md) | Cache invalidation on dict edit | ~40 lines |
| PR8 | [2026-07-02-nav-submenu-pr8-e2e.md](2026-07-02-nav-submenu-pr8-e2e.md) | E2E + docs + final regression | ~150 lines |

**Execution sequence:**
1. PR1 → backend foundation (can land first, no UI dependencies)
2. PR2 → frontend pure logic (independent of Header)
3. PR3 → desktop UI (depends on PR2)
4. PR4 → mobile UI (depends on PR3)
5. PR5 → generic component (independent)
6. PR6 → permission matrix (depends on PR2 + PR5)
7. PR7 → cache wiring (depends on PR1 + PR6)
8. PR8 → E2E + docs (depends on all above)

**Why split into 8 PRs:**
- Per project CLAUDE.md: single fix >500 lines → stop and ask user. We split to keep each PR small.
- Per project CLAUDE.md: every commit must pass lint/typecheck/test independently. Splitting ensures each PR is verifiable on its own.
- Per user feedback [feedback-commit-in-batches-for-large-changes.md]: >10 file changes should be split by logical unit (rename / bug fix / new infra / lib / app / tests).

**Out of scope (follow-up specs):**
- Decoupling `/admin/*` sub-pages from `require_page("admin")` so each sub-page has its own page_key guard
- Multi-level (3+) nested menus
- Per-role default permissions on role creation