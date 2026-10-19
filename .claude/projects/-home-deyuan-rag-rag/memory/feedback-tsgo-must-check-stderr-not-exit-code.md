---
name: feedback-tsgo-must-check-stderr-not-exit-code
description: "tsgo 报错时必须 check stderr 输出, 不能只看 exit code; shell pipe 会吞 error"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e14df16a-a6ec-4603-b9f3-e9386f9c08e5
---

跑 `tsgo --noEmit` (或 tsc) 验证类型时, **不能只看 exit code**, **必须看 stderr/stdout 实际输出**.

**Why**: 2026-06-17 登录页 bug 复盘. 我跑 `tsgo --noEmit` 看到 "EXIT=0" 就以为没错误, 但实际 tsgo 在 stderr 报了 `error TS2305: Module '"next-intl/navigation"' has no exported member 'useRouter'`. EXIT=0 是因为 head/tee 等 shell pipe 让 `$?` 拿到的是 pipe 最后一个命令的 exit code, 不是 tsgo 的.

**How to apply**:
- 跑 typecheck/lint 后**必须** `2>&1 | head -50` 看实际报错, 不能 `> /dev/null` 或只看 `$?`
- bun 跑 `bun run typecheck` 报 exit 1 但实际是 bun 包装, tsgo 本身可能 EXIT=0; 遇到 bun exit 1 先 `./node_modules/.bin/tsgo --noEmit` 直跑看真实状态
- CI 里 typecheck step 必加 `set -e` + `tee` 输出, 不要 `|| true` 吞掉
- shell pipe 后看 `$?` 是看最后一段命令, 不是中间; 用 `PIPESTATUS[0]` (bash) / `$LASTEXITCODE` (pwsh 看 pipeline) 看具体哪段

**真实证据**:
- bun run typecheck 返 exit 1 → 我看 $? 以为是 tsgo 失败
- `./node_modules/.bin/tsgo --noEmit` 直跑 → EXIT=0, 实际是 bun 的 stderr 包装
- 写 broken import 探针 → `./node_modules/.bin/tsgo --noEmit` stderr 报 `error TS2305: ... has no exported member 'useRouter'`
- 说明 tsgo **是**抓到错误, 是我**没看 stderr** 才误判 EXIT=0
