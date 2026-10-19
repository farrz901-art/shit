---
name: feedback-no-namespace-i18n-flat-keys-only
description: "项目强制 flat-key i18n (中文作 key), 禁止 useTranslations(\"namespace\") + t(\"foo.bar\")"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bbd38558-9e99-4b93-b8fc-d4e462b4c307
---

CLAUDE.md 已规定项目 i18n 风格:

> 禁止 `t("knowledge.nodes.title")` 这种 dotted namespace. `t("中文")` 中间直接用中文作 key (zh.json identity, en.json 翻译)

但实际代码里仍有人写 `useTranslations("submissions")` 然后 `t("filters.pending")` —— 期望 zh.json 有 `"submissions": { "filters": { "pending": "..." } }`, 实际是 flat 顶层 `"待审批": "..."`.

**症状**:
- 页面显示原文 (`filters.pending` 字面量) 而不是中文
- 测试通过 (因为 mock 不接 namespace 参数)
- zh.json / en.json 找不到对应 key

**Why**: 
- 跟项目既有风格不一致 (项目其他 100+ 处都是 flat)
- 增加文件维护成本 (新建 namespace 子对象)
- i18n key 调试不友好 (grep "filters.pending" 找不完所有 namespace 链)

**How to apply**:
- 用 `useTranslations()` (空参数, flat 查找)
- zh.json 加 `"待审批": "待审批"` (中文作 key + value)
- en.json 加 `"待审批": "Pending"`
- 检查其他页面是否还残留 namespace: `rg "useTranslations\(\"[a-z]+\." packages/web/app/` 找一遍
- 写新页面不要再用 namespace, 跟项目 flat 风格保持一致

**2026-06-18 真实 bug**: submissions 页 filter 标签和操作按钮全显示英文 namespace 字面量, 4 个 component 用了 `useTranslations("submissions")`. 修复 9 个 zh/en key 同步, 23 tests pass.