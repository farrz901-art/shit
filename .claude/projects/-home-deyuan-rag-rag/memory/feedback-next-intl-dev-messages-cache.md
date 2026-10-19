---
name: feedback-next-intl-dev-messages-cache
description: "next-intl dev 模式 cache 翻译, 改 messages/*.json 不 HMR; 报 MISSING_MESSAGE 先重启 bun run dev + 浏览器 hard refresh, 不是代码 bug"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f0fa30f9-9387-49ab-ae40-4882cc1720ae
---

next-intl (4.x + App Router) 在 dev 模式下 **cache 翻译文件** (`web/messages/{zh,en}.json`), 改了 JSON 不会自动 HMR. 表现: `IntlError: MISSING_MESSAGE: Could not resolve \`xxx\` in messages for locale \`zh\`` 即使 zh.json 里 key 已经在.

**Why:** 2026-06-18 真实事故. 用户加 `t("登录中…")` 后同步 zh.json 加 `"登录中…": "登录中…"`, 但浏览器报 MISSING_MESSAGE. 字节级验证 (Python 读 zh.json + page.tsx) 两边字符完全一致 (`[0x767b, 0x5f55, 0x4e2d, 0x2026]`), 排除字符不匹配. 根因是 next-intl dev 模式 cache 没刷新. 重启 `bun run dev` + 浏览器 hard refresh 即好.

**How to apply:**
1. **改 `messages/*.json` 后**不要相信 HMR — 主动重启 dev server: `Ctrl+C` 当前 `bun run dev` + 重新 `bun run dev` + 浏览器 `Ctrl+Shift+R` hard refresh
2. **MISSING_MESSAGE 报错的诊断步骤**:
   - 字节级验证 key 字符一致 (Python `hex(ord(c))` 对比 page.tsx 跟 zh.json)
   - 验证 JSON 合法 (`bun -e "JSON.parse(readFileSync(...))"`)
   - 验证 key 在文件里 (`Object.keys(z).includes(key)`)
   - 排除上面 3 个后才考虑 dev cache
3. **不要**改 `i18n/request.ts` 的 getRequestConfig 试图"修" cache — 这是 next-intl 4.x 的 dev 行为, 不是 bug
4. **生产环境 (next build + start)** 不会有这个问题, 因为编译时静态加载 messages

**跟 [[feedback-turbopack-postcss-panic-10054]] 同模式**: dev infra 抓不到某些代码/资源改动, 重启 dev server 即可, 不是代码 bug. 类似还有:
- [[feedback-uvicorn-must-restart-after-route-add]] (Python 后端加 router 后 uvicorn 不 reload)
- [[feedback-turbopack-postcss-panic-10054]] (PostCSS worker 子进程崩溃)

**预防**:
- 加新 `t("中文 key")` 时, 同步加 zh/en.json 后, 在 commit message 提一句"i18n: 需重启 dev server 验证"提醒 reviewer
- 改 messages/*.json 后, 主动重启 dev server, 不要等用户报 MISSING_MESSAGE 才修

**反模式**:
- ❌ 看到 MISSING_MESSAGE 立刻改 `i18n/request.ts` 加 revalidate / watch (治标不治本, 还可能引入新 bug)
- ❌ 怀疑 key 字符不对 (UTF-8 BOM / GBK / 全角 vs 半角) 浪费时间重写 (字节级一致就排除)
- ❌ 改 tsconfig / next.config 加 webpack watch (跟 next-intl cache 无关, 浪费精力)
