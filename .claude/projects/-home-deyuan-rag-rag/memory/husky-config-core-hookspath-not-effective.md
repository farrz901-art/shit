---
name: husky-config-core-hookspath-not-effective
description: "排查 \"git config core.hooksPath 无效\" 的步骤顺序——配置本身极少有问题，优先查可执行位"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fb312146-519f-4c9c-98dd-096100f548d2
---

# 排查 `git config core.hooksPath .husky` "无效" 的标准顺序

**Why:** 第一性原理：git 2.9+ 对 `core.hooksPath` 支持是稳的，配置层面 99% 没问题。"无效"几乎都是 hook 文件层的问题。先验证再下结论，不要凭印象。

**How to apply:** 用户报"hooksPath 无效"时按这个顺序查，跳过任何一个都会误诊：

1. **确认配置生效**：`git config --show-origin --get core.hooksPath` —— 必须看到 `file:.git/config`
2. **确认文件存在**：`.husky/pre-commit` `.husky/commit-msg`
3. **⭐ 确认文件 +x**：`ls -la .husky/` —— 没有 `+x` 就被 silently ignore（带 warning）。这是**最常见根因**
4. **真触发一次**：`GIT_TRACE=1 GIT_TRACE_HOOKS=1 git commit --allow-empty -m trace` —— 看 trace 里有 `run_command: .husky/pre-commit` 还是 `hook was ignored`
5. 只有以上都正常但 hook 行为仍不对，才去查 hook 脚本本身（set -e、cd、bunx 找不到等）

**反例（我犯过的错）：** 第一轮我曾说"git 不要求 hook 文件 +x"，那是错的——git 自始至终都要求 +x，只是新版本加了 warning。详见 [[git-hooks-executable-bit]]。