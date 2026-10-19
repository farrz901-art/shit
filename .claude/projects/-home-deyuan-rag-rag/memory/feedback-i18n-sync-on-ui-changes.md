---
name: feedback-i18n-sync-on-ui-changes
description: "任何改 UI 加 t(\"...\") 文案时, 必须同步 messages/{zh,en}.json, commit 前 git diff 校验"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1dfcdecb-84bb-4149-9ad1-d1b332effa26
---

改 UI 文件 (`.tsx` / `.ts`) 加新 `t("...")` 字符串时, **必须** 同步 `packages/web/messages/zh.json` + `en.json`. zh.json 中文作 key (中文 value 同样), en.json 英文翻译.

**Why:** 之前 Sprint shadcn 改 UI 加 `t("新建任务")` 等文案, 漏同步 messages/{zh,en}.json. not-found.tsx 报 MISSING_MESSAGE 错 ("Could not resolve `你要找的页面可能已被移除或地址有误` in messages for locale `zh`"), 用户 2026-06-14 反馈过 1 次. 错误规律: 改 UI 一气呵成, commit 后才发现 i18n key 没注册, 不得不 fixup commit (`5271398`).

**How to apply:**
1. 改 .tsx / .ts 包含新 `t("...")` 字符串 → 立刻 `git diff messages/zh.json messages/en.json` 看是否同步
2. 新 key 加在 zh.json (中文作 key, value 同样中文) + en.json (英文翻译)
3. 删文案 → 同步删 zh.json / en.json 里的 key
4. 改文案 → 同步改两边
5. commit message 提 "i18n: ..." 或 "refactor: ... (i18n sync)" 提醒
6. 漏改典型: t("新建任务") 用了但 zh.json 没注册 → not-found.tsx 报 MISSING_MESSAGE. 见 `5271398` commit message.
7. 批量校验: `node -e "JSON.parse(...)"` 验 zh.json / en.json 合法

**Related:** [[project-rag-followup-candidates]] 提过 i18n 跳过项; 跟 [[feedback-check-old-code-before-refactor]] 同型 — 改一处别忘同步另一处.
