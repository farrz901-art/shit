---
name: git-hooks-executable-bit
description: git hook 文件必须带 +x，否则被 silently ignore（带 warning），不阻塞 commit
metadata: 
  node_type: memory
  type: reference
  originSessionId: fb312146-519f-4c9c-98dd-096100f548d2
---

# git hooks 必须有可执行权限

git 启动 hook 前会检查 `+x`。**没有 `+x` 时不会拒绝 commit，但会跳过 hook 并打 warning**：

```
hint: The '.husky/pre-commit' hook was ignored because it's not set as executable.
```

早期 git 版本是静默跳过，2.9+ 加了 warning 但仍然不阻塞。所以"以前能用"是错觉——早期根本就没跑。

修复：

```sh
chmod +x .husky/pre-commit .husky/commit-msg
```

**诊断命令**（必跑，别只看 `git config --get`）：

```sh
GIT_TRACE=1 GIT_TRACE_HOOKS=1 git commit --allow-empty -m "trace"
```

看是否有 `run_command: .husky/pre-commit`（跑了）或 `hook was ignored`（被忽略）。

相关 [[husky-config-core-hookspath-not-effective]]。