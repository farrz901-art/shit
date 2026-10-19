---
name: feedback-cleanup-worktree-after-merge
description: "任务完成后 / 代码合并到 master 后, 立刻 git worktree remove 清理"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bbd38558-9e99-4b93-b8fc-d4e462b4c307
---

任务完成 + 代码已经合并到 master 后, **立刻清理 worktree**:

```bash
git worktree list
git worktree remove .claude/worktrees/agent-XXXXX --force
git worktree list  # 确认只剩 master + baseline-check
```

**Why**: 
- agent worktree 堆在 `.claude/worktrees/` 目录, 几个月不清会占大量空间
- 残留 worktree 的分支还在 git 里, 容易误操作或误以为代码没合并
- 项目跟其他工作并行时, 老 worktree 分支可能跟 master 冲突

**How to apply**:
- subagent-driven-development / parallel agent 派发完成 → 主流程确认代码进 master → **同一回合就清理**
- 不要等用户提醒才清理, 这是 task 完成的标准动作
- baseline-check 那个 detached HEAD worktree (在 `C:/Users/abcuc/AppData/Local/Temp/baseline-check`) 不要动, 不是 agent 创建的