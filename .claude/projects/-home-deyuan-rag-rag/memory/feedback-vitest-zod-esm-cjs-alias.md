---
name: feedback-vitest-zod-esm-cjs-alias
description: vitest 下 zod v4 ESM 重导出 z 为 undefined，需要在 vitest.config.ts 强制走 CJS 入口，否则 4+ 个 suite 级失败
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

## 问题

zod v4 `"type": "module"` + 多层 re-export → vitest 4.x jsdom 环境下 `import { z } from "zod"` 得到 `undefined`
- 典型报错: `TypeError: undefined is not an object (evaluating 'z.object')`
- 影响范围: 所有顶层 `import z from "zod"` 的测试文件 (parse-json / schema-types / qa page / chat route 等)

## 修复

在 `vitest.config.ts` 的 `resolve.alias` 中强制走 CJS 入口:

```ts
resolve: {
  alias: {
    "zod": path.resolve(__dirname, "node_modules/zod/index.cjs"),
  },
},
```

**Why:** zod v4 ESM 入口 `index.js` 内 `import * as z from "./v4/classic/external.js"` 在 vitest 预构建链中被解析为 `{ default: undefined }`. CJS 入口 `index.cjs` 无此问题.

**How to apply:** 项目升级 vitest 或 zod 时, 先删 alias 跑全量 test; 如果全绿则 alias 不再需要. 否则保留.

**关联:** [[feedback-record-errors-and-lessons]]
