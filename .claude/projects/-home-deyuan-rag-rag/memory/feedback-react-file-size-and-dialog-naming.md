---
name: feedback-react-file-size-and-dialog-naming
description: "React 组件单文件不超过 300 行, Dialog 拆为独立文件 (文件名 kebab-case, 见 [[feedback-filename-kebab-case-strict]])"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 298dc759-254d-43ee-a841-71ccb0b25682
---

React 组件单文件代码不得超过 300 行。Dialog 等弹框组件不要混在页面里, 拆成独立文件后通过页面 import。

**文件命名**: 一律 kebab-case (`xx-dialog.tsx`, 不是 `XxDialog.tsx`)。组件标识符仍用 PascalCase (`export function XxDialog`)。规则详见 [[feedback-filename-kebab-case-strict]]。

**Why:** 单文件过大难维护, 拆分让职责单一; 弹框跟页面 state 紧耦合反而难复用 — 拆出去强制理清 props 接口。

**How to apply:**
1. 写 React 组件时先估行数, 接近 300 就拆。
2. 弹框统一 `xxx-dialog.tsx`, 不许内联在页面。
3. 用 [[feedback-filename-kebab-case-strict]] 的命名规则起新文件。
