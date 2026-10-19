---
name: feedback-commit-in-batches-for-large-changes
description: "大改动 (>10 文件) 必须分批次提交, 一次 commit 一个逻辑单元, 方便 review/回滚/定位"
metadata:
  node_type: memory
  type: feedback
---
**大改动 (>10 文件) 必须分批次提交, 一次 commit 一个逻辑单元, 方便 review / 回滚 / 定位.**

**Why:** 2026-06-14 一次重构 web 前端 (1) `middleware.ts → proxy.ts` rename + (2) timeZone fix + (3) CSS 404 matcher 修复 + (4) IPv4/IPv6 undici 坑 + (5) 抽 `lib/api/config.ts` 集中 API_BASE + (6) `apiFetch()`/`apiProxy()` 封装 + (7) 改 50+ 文件走封装 — 涉及 50+ 文件. 用户原话: "分批次提交, 并且 memory 中记住, 文件多的时候都要分批次提交".

正确做法: 把改动按**逻辑单元**拆, 每批 1 个 commit:

| 批 | 范围 | 典型文件数 |
|----|------|-----------|
| 1 | 框架升级 (rename + deprecation 处理) | 1-3 |
| 2 | 单个 bug fix (CSS 404 / timeZone / IPv4) | 1-3 |
| 3 | 新基础设施 (`config.ts` + `apiFetch` + `apiProxy` wrapper) | 1-2 |
| 4 | 把 `lib/api/*` 接入新 wrapper | 5-10 |
| 5 | 把 `_actions/*` 接入新 wrapper | 2-5 |
| 6 | 把 BFF `route.ts` 接入 `apiProxy` | 5-15 |
| 7 | 把 `app/**` server/client 组件接入新 wrapper | 10-20 |
| 8 | 测试改写 (删实现细节, 只测行为) | 5-10 |

**How to apply:**

```bash
# 大改动前先看 git status, 按上面的批顺序 commit
git status --short
git add <batch 1 files> && git commit -m "..."
git add <batch 2 files> && git commit -m "..."
# ... 一批一 commit
```

**commit message 模板** (feat / fix / refactor / chore + 简短 why):

```
fix(web): 改用双模式 matcher 修 /zh/_next/* 404

- 单条 /((?!api|_next|...)) 在 path-to-regexp 下漏判 /zh/_next/...
- 拆成根路径 + 带 locale 前缀两条 matcher, 让 rewritePrefixedAsset 接管
- proxy.ts:0 → 0 (启动后), 0 个 404 chunk
```

**自检清单 (commit 前)**:
- [ ] 这个 commit 单独能 revert 而不破坏其他 commit 吗?  (能 = OK, 不能 = 拆错)
- [ ] commit message 写清楚 why (不是 what, what 看 diff) 吗?
- [ ] 单 commit 涉及文件数 < 20 吗?  (>20 = 还没拆够细)

**反模式**:
- "全部重构 + bug fix + 新功能" 一锅端, 100+ 文件 1 个 commit
- 多个不相关改动挤 1 个 commit (review 痛苦, revert 痛苦, bisect 痛苦)
- 改了一半存进度 commit ("WIP" 类) — 跟 [[feedback-no-shim-no-minimal-changes]] 同精神, 别凑合

**关联**:
- [[feedback-check-old-code-before-refactor]] — 重构前的纪律
- [[feedback-no-shim-no-minimal-changes]] — 别在 commit 里塞 "凑合" 改动
