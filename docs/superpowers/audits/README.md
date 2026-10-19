# docs/audit/ — 审计与代码体检目录

> 维护说明: 每次全栈审计创建一份日期命名的 checklist 文档, 走 `- [ ]` / `- [x]` 维护.

## 文档列表

| 文档 | 用途 | 状态 |
|---|---|---|
| [2026-06-28-findings.md](2026-06-28-findings.md) | 2026-06-28 cva 改写专项 — 9 条 finding (3 high + 3 medium + 3 low) | 活跃 |
| [2026-06-28/](2026-06-28/) | 2026-06-28 cva 改写专项: D5 scan + AUDIT-REPORT + P3 spec 草稿 | 完整 |
| [2026-06-26-findings.md](2026-06-26-findings.md) | 2026-06-26 /full-stack-audit — 39 条 finding | 活跃 |
| [2026-06-26/](2026-06-26/) | 2026-06-26 详细 finding (6 维度) + AUDIT-REPORT + 5 份 spec 草稿 | 完整 |
| [2026-06-24-findings.md](2026-06-24-findings.md) | 2026-06-24 全栈审计 — 日常维护 checklist | 活跃 |
| [2026-06-24/](2026-06-24/) | 2026-06-24 详细 finding (6 维度) + AUDIT-REPORT + 5 份 spec 草稿 + scan-brief | 完整 |
| [2026-06-10-shadcn-coverage.md](2026-06-10-shadcn-coverage.md) | 历史 - shadcn 组件覆盖率审计 | 历史 |
| [2026-06-14-full-test-suite-scan.md](2026-06-14-full-test-suite-scan.md) | 历史 - 全量测试扫描 + 修复 | 历史 |
| [2026-06-14-react19-refactor.md](2026-06-14-react19-refactor.md) | 历史 - React 19 重构审计 | 历史 |
| [2026-06-14-typecheck.md](2026-06-14-typecheck.md) | 历史 - 全量类型检查扫描 | 历史 |
| [2026-06-15-web-data-fetch.md](2026-06-15-web-data-fetch.md) | 历史 - 前端数据获取审计 | 历史 |

## 命名约定

- checklist 文件名: `YYYY-MM-DD-findings.md` (放在 docs/audit/ 根, 日常维护用)
- 完整审计产出 (finding 详情 + report + spec 草稿): `docs/audit/YYYY-MM-DD/` 子目录
- checkbox 语义:
  - `- [ ]` 未处理 (默认)
  - `- [x]` 已处理 (后面跟 commit hash)
- 严重度分组: Critical / High / Medium / Low / Info

## 处理流程

1. 修一个问题 → 改对应行 `- [ ]` → `- [x] <commit-hash>`
   例: `- [x] **SEC-001** ... — abc1234`
2. 改完进度表对应维度 +1
3. 大块修复 (≥10 条) 走 spec → plan → implement 循环, 完成后批量勾
4. 误报 / 不修: 保留 `- [ ]`, 在后面加 `(won't fix: 理由)`, 不勾掉

## 关联文档

- 详细 audit 报告: `docs/audit/YYYY-MM-DD/AUDIT-REPORT.md`
- 设计 spec: `docs/superpowers/specs/2026-06-24-full-stack-audit-design.md`
- 实施 plan: `docs/superpowers/plans/2026-06-24-full-stack-audit.md`
