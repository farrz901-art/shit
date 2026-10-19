---
name: feedback-design-docs-in-chinese
description: User cannot read English; all design docs/specs/architecture output must be in Chinese
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a1ddf00a-bc33-44aa-8d4b-18546d7edaa0
---

User 在 2026-06-30 streamdown 头脑风暴中明确表示: "英文的我看不懂，翻译成中文，文档必须用中文写". 适用范围:

- 头脑风暴过程里的设计草案 / 架构图描述 / 组件名/调用方说明
- 最终落盘的 `docs/superpowers/specs/*.md` 设计文档
- `docs/superpowers/plans/*.md` 实施计划

**Why:** 用户不懂英文, 之前所有英文起草的设计 + 流图都得现场重译, 浪费时间且容易丢信息.

**How to apply:**
- 写 spec / plan / design discussion 一律中文为主, 包括流图说明、错误处理、API 差异、权衡对比
- 代码标识符 (组件名 / prop 名 / 文件名) 保持英文, 那是项目规约
- 引文 / 第三方文档原文 (如 streamdown 官方文档) 可以保留英文 quote, 但周围解释必须中文
- AskUserQuestion 里的选项描述也用中文
- 例外: 用户显式说 "用英文" 时才切英文

**Why 不动到代码注释:** 代码注释用中文是项目 CLAUDE.md 既定规约, 跟本文档要求方向一致, 不会被覆盖.
