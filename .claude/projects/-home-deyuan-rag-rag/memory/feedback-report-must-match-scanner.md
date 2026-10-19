---
name: feedback-report-must-match-scanner
description: "跨 subagent 报告\"覆盖率/完整度\"必须用同 scanner；4 agent 各定义 PASS/MISS 必出大数差，2026-06-29 P5b 教训"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04c90ace-3037-4d78-89b5-cf5b537f4d60
---

跨 subagent / 跨 plan 报"覆盖率"或"完成度"数字, **必须**保证:
1. 所有 agent 用**同一个 scanner** (同一脚本同一参数)
2. 报告"X/Y PASS"前**自己**跑一次 scanner 复验, 不能信 subagent 自报
3. 数字差异 > 2 倍时, 必须停下来 review scanner 规则, 不能直接合并

**Why**: 2026-06-29 P5 阶段, 4 个 subagent 并行扫描各模块注释覆盖率, 各自定义"head 有注释就算 PASS" — 实际是把 `// (2026-06-14) 改走 X` 误判 PASS. 汇总报"lib/ 0 P0", 我自己跑出 132 个 MISS, 修 scanner 后真值是 12. 4 agent 报告口径不一, 必出大数差.

**How to apply**:
- 任何 multi-agent 审计任务, 派 agent 前**先**写 1 个共享 scanner (e.g. `coverage.py`), 让所有 agent 跑同一脚本
- 汇总报告时**自己**跑 scanner 复验, 数字必须跟子报告一致
- 数字对不上时, 第一时间查 scanner 规则不一致, **不要**当 "subagent 偷懒" 处理

**配套**: [[feedback-coverage-scanner-cant-use-head-1]] scanner 自身设计规范
