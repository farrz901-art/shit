---
name: feedback-nextjs-metadata-must-be-object-or-generatemetadata
description: "Next.js App Router 动态 metadata 函数必须叫 generateMetadata, 命名 metadata 会静默崩成 RSC $$typeof undefined"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 623e8a0b-5f11-4892-8333-52384121101e
---

Next.js App Router 的 `export const metadata = async () => {...}` 写法是**错的**, Next.js 不会报"无效 export", 而是把函数对象当 Metadata 用 → title 为 undefined → React 19 序列化层走 `value.$$typeof` 检查 → 炸出 `TypeError: undefined is not an object (evaluating 'value.$$typeof')`, digest 类似 `3075709123`, server stack 空, env=Server, owner 指向 Next.MetadataOutlet。

**正确写法只有两种**:
```typescript
// ✅ 静态对象
export const metadata = { title: "..." };

// ✅ 异步函数必须叫 generateMetadata
export const generateMetadata = async () => ({ title: "..." });
// 或
export async function generateMetadata() { return { title: "..." }; }
```

**Why**: 2026-06-24 实战, `app/[locale]/output/page.tsx:12` 写成 `export const metadata = async () => {...}` 导致整页 LocaleError boundary 不停抛 `$$typeof undefined`。RSC payload 里 `21:E{"digest":"3075709123","name":"TypeError","env":"Server"}` 跟 `Next.MetadataOutlet` owner=$1a 关联, 项目里其它 8 个动态 metadata 都正确叫 generateMetadata, 唯独 output/page.tsx 写错。

**How to apply**:
1. 新加 metadata 时, 异步必用 `generateMetadata`, 静态用 `metadata = {...}` 对象字面量。
2. 看到 `$$typeof undefined` + digest + server stack 空 + RSC row owner 指向 Next.MetadataOutlet/Next.Metadata → 直接 grep `export const metadata = async`, 漏改的就是凶手。
3. 排查工具: 抓 Network `?_rsc=` 请求 response, 找 `<id>:E{...}` 行的 `owner` 字段, $1a 之类的 ref 往上回溯 row 19/31 这种 `Next.MetadataOutlet` / `Next.Metadata` 节点, 锁定到 metadata pipeline。

关联 [[feedback-rsc-dollartypeof-not-hydrationboundary]] (2026-06-22 也是 $$typeof 但根因不同), [[feedback-next-intl-dev-messages-cache]] (next-intl messages dev 不 HMR 也会让 metadata 里 tr() 返 undefined 二次触发同类错)。
