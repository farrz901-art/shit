# scan-brief — cva 改写专项审计 (2026-06-28)

> 本次是 **专项 audit**, 聚焦"可以用 class-variance-authority (cva) 改写的代码".
> 不是 6 维度全栈 audit, 只跑 D5 frontend 子集.
> 派出 1 个 D5 subagent 扫描, 主线程负责 verify + synthesize.

## 背景

项目用 `class-variance-authority` (cva) + Tailwind v4 + shadcn/ui, 已有 8 个 cva 模板在 `components/ui/` (button/badge/alert/empty/label/sheet/toggle/toggle-group). 规约见 [packages/web/CLAUDE.md §零 lint warning 规范](packages/web/CLAUDE.md) 和 §封装组件.

cva 价值:
- 变体配置单一事实源 (single source of truth)
- TypeScript 自动推导 props (`VariantProps<typeof xxx>`)
- 跟 shadcn/ui 模板对齐
- 避免 `if (intent === 'a') className += '...'` 的脏拼字符串

## 通用约束 (D5 subagent 遵守)

### 你的角色

你是 **D5 Frontend — cva 改写专项** 的扫描 agent. 严格只读 (Read / Grep / Glob), 禁用 Edit / Write / NotebookEdit / WebSearch / WebFetch.

### 工作目录

- 项目根: `c:/doc/Code/rag/`
- 你的产出文件: `c:/doc/Code/rag/docs/audit/2026-06-28/d5-cva-audit.md`
- 本 brief 文件: `c:/doc/Code/rag/docs/audit/2026-06-28/scan-brief.md`

### Finding Schema (严格)

每条 finding 必须满足:

```yaml
- id: CVA-001                       # 必填, 3 位数字
  dimension: frontend               # 必填, 这次都填 frontend
  severity: high                    # 必填: critical|high|medium|low|info
  confidence: high                  # 必填: high|medium|low
  title: "组件用 if/else 拼 className, 可改 cva"  # ≤ 80 字符
  file: packages/web/components/... # 相对项目根
  line: 42                          # 整数
  description: |
    中文, ≥ 2 句, 解释问题本质 + 当前实现.
  evidence: |
    真实代码引用 ≥ 3 行 (用 Read 复制)
  impact: |
    中文, 解释影响: 维护性 / 类型安全 / 重复代码 / 不一致风险.
  fix_sketch: |
    中文, 改写思路 (不实施), 1-3 句 + cva 模板草稿.
  references: []                    # 可选
```

### 工具限制

- 最多 40 次工具调用
- 最多 ~60k tokens
- 超限自动 stop

### 网络限制

**禁止** WebSearch / WebFetch (纯本地静态扫描).

### 输出格式

主线程会用 `<DATE>/d5-cva-audit.md` 接收, 必须严格按上方 schema.

## 维度特定指令 (cva 专项)

### 角色

偏 React/Tailwind 视角: 找"组件 className 用 if/else / 字符串拼接 / 三元嵌套"模式, 这些都是 cva 该出手的信号.

### 必扫路径

按优先级扫 4 类文件:

1. **`packages/web/components/ui/*.tsx`** (除已用 cva 的 8 个)
   - input.tsx, textarea.tsx, checkbox.tsx, switch.tsx, radio-group.tsx, select.tsx, tabs.tsx, table.tsx, card.tsx, separator.tsx, scroll-area.tsx, popover.tsx, dropdown-menu.tsx, dialog.tsx, command.tsx, avatar.tsx, skeleton.tsx, sonner.tsx, calendar.tsx, pagination.tsx, collapsible.tsx, progress.tsx
2. **`packages/web/components/common/**`**
   - display/* (badge/icon/empty) — 已是 cva 还是 if/else?
   - table/* (data-table) — 是否有 size/variant 维度?
   - form/* (form/form-field) — error/success state 怎么管?
   - feedback/* (error-banner / app-tooltip / copy-button) — variant 维度?
3. **`packages/web/app/[locale]/**`**
   - 业务组件: avatar-uploader / deletion-section / change-password-dialog / etc.
   - 看 if/else className 模式
4. **`packages/web/components/{auth,chat,knowledge,layout,settings,evaluate}/**`**

### 检查项 (6 项, 按优先级)

1. **if/else 拼 className 模式** — `if (condition) cls += '...'` 或 `${cond ? 'a' : 'b'}` 字符串拼接
2. **size/variant/state 隐式散落** — 同一组件不同 size/color 是手写 className 而非变体
3. **重复 className 模式 ≥ 3 处** — `clsx(cn("rounded border bg-primary ..."))` 这种"基础 + variant"模板重复
4. **三元嵌套 ≥ 2 层** — `cond1 ? (cond2 ? 'a' : 'b') : 'c'` 可读性极差
5. **复合变体未抽 compoundVariants** — 多 prop 组合时手写 if, 应抽 cva compoundVariants
6. **状态色不一致** — 同一组件在不同文件里写 `bg-error-100` / `bg-destructive-100` / `bg-red-100`, 应该走 status-* 主题 token

### ID prefix

`CVA-`

### Dimension

`frontend`

### 优先级

必扫 components/ui → components/common → app/[locale] 业务组件 → 其他 components.

### 报告必须含 (主线程 check)

- 元信息 (扫了几个文件 / 找到几条)
- finding 列表 (YAML)
- "已扫但未发现 finding 的组件" 清单 (证明确实扫了)
- "已知跳过 / 不建议改 cva 的" 清单 (小到不值得)

## 重要提示

1. **不要写代码** — 这是 audit, 不是 fix
2. **不要 commit** — 主线程统一 commit
3. **找不到 finding 是合法的** — 在"未扫/已知缺口"段说明, 不要编
4. **evidence 必须真实** — 主线程会 `git show <file>` 验
5. **判断标准** — 不是所有 if/else 都该改 cva, 只标 ≥ 2 个变体维度 或 ≥ 3 处重复 的