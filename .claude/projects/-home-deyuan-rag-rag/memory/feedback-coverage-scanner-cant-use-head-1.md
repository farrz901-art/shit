---
name: feedback-coverage-scanner-cant-use-head-1
description: 覆盖率 scanner 严禁 head -1 判定文件注释是否合规；必须 dedup 日期 + 中英文长度门槛 + 跳过 use-directive，2026-06-29 P5b 教训
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04c90ace-3037-4d78-89b5-cf5b537f4d60
---

覆盖率 scanner 严禁用 `head -1` (或 `head -3`) 判定文件首段是否有"功能描述注释". 这种宽规则会把:
- `// 账号系统 Server Actions (login / logout)` + `// (2026-06-14) 改走 apiFetch()` 这种"修改记录型注释"误判 PASS
- `// (2026-06-14) 改走 X` + 无功能描述 的文件漏判 MISS

**Why**: 2026-06-29 P5 阶段, 4 agent 并行扫描 "lib/ 良好 0 P0", 实际有 **9 个 lib/ 零注释文件** (account.ts / users.ts / factory.ts / 4 hooks + intl-wrapper + themes.ts). 我自己也用 `head -10` 跑出 132 个 MISS, 比真值 12 多 11 倍, 严重失实. 修了 scanner (跳过 `"use server";` 带分号 + dedup `(YYYY-MM-DD)` 日期 + 中文 ≥ 6 字符 / 英文 ≥ 25 字符) 才降到真值 12.

**How to apply**: 任何"覆盖率 / 完整度" scanner 必须满足:
1. 跳过 `"use client"` / `"use server"` (含 `;` 变体)
2. dedup `(YYYY-MM-DD)` 日期模式后再判定 (含日期 ≠ 修改记录, 可能是功能描述)
3. 中英文双规则: 中文 ≥ 6 字符 + 至少 1 个汉字 / 英文 ≥ 25 字符
4. 区分 JSDoc `/** */` 块 vs `//` 单行, 都要验证 dedup 后有功能词
5. 报覆盖率数字前**必须**自跑 scanner 一次, 不能信 subagent 自报 PASS/MISS

**配套**: [[feedback-report-must-match-scanner]] 跨 agent 报告口径必须用同 scanner
**P5b plan**: [docs/audit/2026-06-28-code-quality-5d/P5b-comments.md](docs/audit/2026-06-28-code-quality-5d/P5b-comments.md) §3 教训
