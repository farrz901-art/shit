---
name: feedback-react-entrycard-has-internal-link
description: "EntryCard 组件内部已经渲染 Next.js <Link>, 调用方不要再包一层 <Link> 包裹 EntryCard, 否则产生 <a> 嵌 <a> 触发 React 19 hydration error 且 link role 多匹配"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

EntryCard (web/components/knowledge/EntryCard.tsx) 内部已经用 `<Link href={href}>` 渲染, 调用方传 `href` prop 即可, 不要再写 `<Link href="..."><EntryCard href="..." /></Link>`.

**Why:** 2026-06-10 我在 web/app/knowledge/documents/page.tsx 给"导入数据"卡套了外层 Link 想"提升可点击区域", 产生 `<a>` 嵌 `<a>`. 结果:
1. React 19 hydration error (`<a> cannot be a descendant of <a>`)
2. `getByRole("link", { name })` 找到 2 个 link, 测试报"Found multiple elements"

**How to apply:** 调用 EntryCard 直接 `<EntryCard href={...} icon={...} title={...} desc={...} index={...} />`, 不要外层包 Link. 如果需要"整卡可点 + 更大 hit area", 改 EntryCard 内部 (HoverLift 已经覆盖整卡), 不要在调用方加壳. 类似组件 (StatCard 已被 Link 包裹用于点击跳转) 需要先看组件实现再决定是否外层包.
