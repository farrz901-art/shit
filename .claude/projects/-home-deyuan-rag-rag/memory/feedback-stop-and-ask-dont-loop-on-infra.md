---
name: feedback-stop-and-ask-dont-loop-on-infra
description: "卡在工具/环境/infra 问题上 30 分钟没突破, 立刻 STOP 报告用户, 不要继续死循环; 用户原话 '遇到困难解决不了就提出来, 不要每次一直死循环一样修什么都没改好, 甚至七八个小时都没有commit'"
metadata:
  node_type: memory
  type: feedback
---
**卡在工具/环境/infra 问题上 30 分钟没突破, 立刻 STOP 报告用户 + 给出 3 方案, 不要继续死循环.**

**Why:** 2026-06-14 web 前端大改动 (proxy rename + apiFetch 封装 + 50+ 文件重构),按用户指示"分批次提交"。我陷入 4 小时 死循环:
- Batch 1 staging 完, pre-commit hook 失败 → debug hook
- Hook 是 lint-staged 写错命令 (`vitest` 不在 PATH, 应是 `bun x vitest`) → 修
- 提交又失败: `vitest --changed` 跑无关历史测试, 触发 1 个 React key warning
- 修历史 React key warning → 又触发 5s timeout 测试
- 修 timeout → 又触发 missing translation 测试
- 修 translation → 又触发 URL 双拼 bug (apiFetch 收到完整 URL 仍拼 base)
- ... 无限循环, 0 个 batch 真正 commit
- 用户 3 次打断: "8 小时 还没 commit" / "分批次提交" / "不要死循环"

**根因**: 我把"分批 commit"理解成"每批都要 pre-commit hook 完美通过",然后每次失败都自己去修下一个 blocker。**没意识到 hook 失败 ≠ 代码错**,可能只是历史测试问题或 hook 配置 bug。

**How to apply:**

```ts
// 卡住自检 (30 分钟 / 3 次相同失败就触发)
// 1. 是不是 pre-commit / CI / 工具链问题, 不是代码逻辑?
//    → 立刻 STOP, 列出失败原因, 给用户 3 方案
// 2. 是不是用户没明确给权 (e.g. --no-verify / 改 hook / 跳测试)?
//    → 不要默认推断, 直接问
// 3. 是不是方案本身太复杂 (e.g. 试图让 5 个无关历史测试全绿)?
//    → 降级: 单开 chore commit 修 infra, 跟本批解耦
```

**3 方案模板** (卡住时套用):
- 方案 A: 继续修 (预期耗时 + 风险)
- 方案 B: 简化范围 (跳某些 blocker, 留 TODO)
- 方案 C: 改规则 (e.g. 改 hook, 走 `--no-verify` 需用户明确授权)

**反模式 (避免重蹈)**:
- ❌ 每次失败都自己 debug, 寄希望"下一个就是最后一个 blocker"
- ❌ 把不相关的修复塞进当前 commit (e.g. lint-staged 修跟 proxy 重命名同 commit)
- ❌ 测试 timeout/key warning/缺翻译 等历史问题, 想在本批里一起清
- ❌ 用户的"分批 commit"被理解成"必须每个 commit hook 全绿"

**正确流程**:
1. **Pre-audit 一次**: `vitest --changed` 跑一遍, 列所有失败
2. **分类**: 跟本批相关 / pre-existing infra / hook 兼容性
3. **3 方案 + 1 分钟问用户**
4. **用户拍板后执行**, 不再绕

**关联**:
- [[feedback-commit-in-batches-for-large-changes]] — 大改动分批但单批要自洽
- [[feedback-windows-lint-staged-cwd-bug]] — pre-commit hook Windows 已知坑, 别用 --no-verify 绕过, 报告 BLOCKED
- [[feedback-check-old-code-before-refactor]] — 重构前纪律
