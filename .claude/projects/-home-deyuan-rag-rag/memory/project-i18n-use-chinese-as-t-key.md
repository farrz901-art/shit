---
name: project-i18n-use-chinese-as-t-key
description: i18n 项目约定 — t() 内的字符串用中文作 key，zh.json 当中文默认值，en.json 做翻译。方便维护时直接 grep 中文定位。
metadata: 
  node_type: memory
  type: project
  originSessionId: 15ad1bed-e505-4a41-9d65-4ac51a5a15c0
---

i18n 项目约定: `t()` 内的字符串**直接用中文**作 key，不用 namespace 路径。

**格式：**
```tsx
// 组件里
<span>{t("加载中…")}</span>
<span>{t("节点列表")}</span>
```

**`web/messages/zh.json`：**
```json
{
  "加载中…": "加载中…",
  "节点列表": "节点列表"
}
```
（zh.json 的 value 就是 key 本身，作为默认值 — 如果翻译缺失就显示 key）

**`web/messages/en.json`：**
```json
{
  "加载中…": "Loading…",
  "节点列表": "Node List"
}
```

**为什么：**
1. **维护简单**：grep "节点列表" 直接定位所有引用点 + zh.json + en.json
2. **不用维护 namespace 树**：避免 `knowledge.nodes.title` 这种 dotted key 命名混乱
3. **缺翻译时 fallback 自然**：缺失 en.json 条目就显示中文 key，不会 crash
4. **TypeScript 类型友好**：key 是 string，不用严格类型检查也能跑（虽然不严格）

**反例（不推荐）：**
```tsx
// 不要这样
t("knowledge.nodes.title")
// 需要维护一个独立的 namespace 树
// 改了 key 后 grep 不到引用
// 缺翻译会显示 "knowledge.nodes.title" 这种技术字符串
```

**实现要求：**
- t() 调用必须 TDD 化（保持 plan 里要求的 "language switch assertion" 测试）
- zh.json 缺失 key 不会显示 fallback，因为 zh.json 的 value 就是 key 本身
- en.json 缺失 key 时 next-intl 默认行为是显示 key（中文）

**Why:** 用户在 2026-06-11 i18n 实施阶段明确要求: "如果项目中要用 t() 的话，t() 中间是应该是中文，这样方便我维护"

**How to apply:**
- 任何 i18n 相关代码（web/ 项目）用 `t("中文 key")` 模式
- zh.json 是 `{ "中文 key": "中文 key" }`（identity）
- en.json 是 `{ "中文 key": "English" }`（翻译）
- plan 文档应明确写这个模式
- 评审代码时如果发现 `t("dotted.namespace.path")` 应建议改成中文 key
