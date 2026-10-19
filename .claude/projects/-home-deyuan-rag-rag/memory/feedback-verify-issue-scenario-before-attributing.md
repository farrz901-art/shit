---
name: feedback-verify-issue-scenario-before-attributing
description: "WebFetch/搜 issue 找到相似症状后, 必须核对 \"issue 描述场景\" 跟 \"项目实际场景\" 是否一致再归因, 关键词命中 ≠ 根因相同"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8016bc34-f2f1-4854-b699-a2a74a5d8cb2
---

WebFetch / WebSearch 找到相似症状的 issue/blog 后, **必须先核对场景是否一致**, 再归因. 关键词命中 ≠ 根因相同.

**Why:** 2026-06-29 全量 audit 报告 反复返工根因分析的真实教训:
- 项目实际: PowerShell → bun → vitest (Windows)
- 我搜到 [Bun issue #28451](https://github.com/oven-sh/bun/issues/28451) "Illegal instruction crash on Windows x64 when running from Git Bash (MINGW64)"
- 关键词 "Windows Illegal instruction" 命中, 我就直接套到项目上
- 用户一句 "为什么要用 bash" 点破 — 项目根本不是 Git Bash 派生, 是 PowerShell
- 浪费 3-4 轮 Edit 改报告

**How to apply:**
1. 搜到 issue/blog 后, 先列出 issue 描述的 **触发场景** (操作系统, shell, binary 类型, 启动方式, runtime)
2. 列出本项目的 **实际场景** (从 `package.json`, 进程树, 环境变量拿, 不要凭印象)
3. 两边对比: 如果场景不匹配, **不能用 issue 的根因**, 只能参考它给的相关线索 (其他 issue, 类似的 stack trace 等)
4. 如果场景匹配, 才归因; 如果不匹配, 把 issue 列为 "类似症状, 根因可能不同, 待诊断"
5. 在 audit/根因报告里**显式标注"根因未明"**比套错 issue 强 100 倍 — 让用户决策而不是误导

**关联:**
- [[feedback-check-official-docs-before-coding]] — 升级版: 查完官方还要核对场景
- [[feedback-debug-distinguish-root-causes]] — 相似症状 ≠ 相同根因
- [[feedback-clarify-ambiguous-instructions]] — "我们项目是不是 X 场景" 模糊时应问, 不要猜
- [[feedback-record-errors-and-lessons]] — 每次归因错误必须记 memory, 不能光在报告里写