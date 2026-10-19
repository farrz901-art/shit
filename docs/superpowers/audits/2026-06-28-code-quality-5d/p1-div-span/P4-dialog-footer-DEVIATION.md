# P1 Phase 4 DialogFooter 撤掉偏差报告 (2026-06-29)

> 触发: 用户在 P1 Phase 4 + Phase 6 完成、B/P2 即将开始时指出 "为什么不把 DialogFooter 做成 Dialog 组件的 footer 插槽, 直接把样式写进去, 这样引用的是否直接写 footer={<><Button></Button></>}就行了"
>
> 决策: 完全撤回 P1 Phase 4 (DialogFooter wrapper + 7 sites 替换), 改用 `<AppDialog footer={...}>` slot 写法 (AppDialog 已有 footer slot + 内部已包 `<DialogFooter className="border-t border-border/40 px-6 py-4">`)

## P1 Phase 4 原方案 (已撤回)

| 项目 | 内容 |
|------|------|
| 抽出的 wrapper | `components/common/dialog/dialog-footer.tsx` |
| Wrapper API | `<DialogFooter className?>` → `<div className="flex justify-end gap-2 pt-2">` |
| 替换的 7 处 | account/settings × 4 + admin/profile-fields × 2 + buyers/[id]/profile-card × 1 |
| 跳过的 4 处 | task-detail-client (Card 内) + output-card (DataTable 行 actions) + admin-users-table (表格 actions + pagination) + create-invite/reset-password-dialog (flex gap-2 无 justify-end) |
| Commits | `393b0ebc` (wrapper + test + barrel) + `d75780fd` (7 sites) |

## 用户质疑的核心

> "为什么不把 DialogFooter 做成 Dialog 组件的 footer 插槽, 直接把样式写进去, 这样引用的是否直接写 footer={<><Button></Button></>}就行了"

—— 用户正确指出: **`<AppDialog>` 已经有 `footer={...}` slot** ([app-dialog.tsx:86](packages/web/components/common/dialog/app-dialog.tsx#L86)), 内部已经包了 `<DialogFooter className="border-t border-border/40 px-6 py-4">` (shadcn 原生 DialogFooter 带 border-t/px-6/py-4)。

我抽的独立 `DialogFooter` 包装:

1. **走错方向**: 是裸 `<div className="flex justify-end gap-2 pt-2">` (无 border-t / 无 px-6 / 无 py-4), 跟 shadcn DialogFooter 的 "border-t border-border/40 px-6 py-4" 视觉完全不同
2. **被放在 AppDialog 内部当 children 用** (不是 footer slot), 相当于在 AppDialog 内容区手写一个按钮行, 失去了 AppDialog 已经提供的 footer slot
3. **多此一举**: AppDialog footer slot + shadcn DialogFooter 已经做了同样的事, 再抽独立包装是**重复造轮子**
4. **跟 P1 项目哲学矛盾**: P1 整体原则是 "优先用项目封装, 不手写重复模板" — 我自己造了一个新封装反而违反了这条原则

## 真实约束: AppForm + AppSubmit 不能抽到 footer slot

调研后发现 7 处 dialog 中 4 处 (account/settings) 走 `AppForm` + `AppSubmit` 模式:

```tsx
<AppDialog ...> {/* 没有 footer prop */}
  <AppForm defaultValues={...} action={action}>
    <AppField .../> {/* form 字段 */}
    <div className="flex justify-end gap-2">
      <Button onClick={() => onOpenChange(false)} type="button">取消</Button>
      <AppSubmit>提交</AppSubmit>  {/* 必须留在 form 内 */}
    </div>
  </AppForm>
</AppDialog>
```

**AppSubmit 必须在 `<form>` 内部** (HTMLButtonElement type="submit" 默认提交最近的 form, 离开 form 就变成哑按钮). 而 AppDialog 的 footer slot 在 AppForm 之外, 把 AppSubmit 抽出去就破了 form submit.

剩 3 处 (admin/profile-fields × 2 + buyers/[id]/profile-card × 1) 不走 AppForm, 理论上可以改 footer slot:

```tsx
<AppDialog
  ...
  footer={
    <>
      <Button onClick={onCancel} type="button" variant="outline">取消</Button>
      <Button onClick={onSubmit}>提交</Button>
    </>
  }
>
  {/* 表单字段 */}
</AppDialog>
```

但 7 处混用两种风格 (4 处 div + 3 处 footer slot) 本身就不一致, **不如统一保留 div 写法** (7 处都是 AppForm / 自定义 form 容器, footer slot 反而不自然)。

## 最终决策

| 行动 | 结果 |
|------|------|
| Revert `393b0ebc` (DialogFooter wrapper + test + barrel) | ✅ commit `b4329052` |
| Revert `d75780fd` (7 sites 替换) | ✅ commit `b6e09d9c` |
| 7 处 dialog 保留 `<div className="flex justify-end gap-2">` 原状 | ✅ 不动 |
| 不强行改用 `<AppDialog footer={...}>` slot (AppForm 约束) | ✅ 决策记录本文档 |
| 从 P1 handoff 移除 DialogFooter 相关进度条目 | ✅ 见 commit `f1589aee` 之后 handoff |

## 给后续 spec 的教训

1. **抽 wrapper 前先查现有封装是否已经支持**: `<AppDialog footer={...}>` 已存在, 不要再造 `DialogFooter` 这种半成品
2. **wrapper 必须比现有方案多一个真实价值**: 我那个 DialogFooter 比 shadcn DialogFooter 少 border-t / 少 px-6 / 少 py-4 — **负价值**, 应该立刻撤
3. **AppForm / AppSubmit 这类结构耦合组件不要硬塞 footer slot**: AppSubmit 必须 form 内, 强行抽 footer 反而破坏 form submit 语义
4. **撤掉负价值 wrapper 比留着 "统一" 更好**: spec 估算 -20 行不实现 ROI 更高 (不引入新组件, 后续 spec 不用维护 DialogFooter 拓展)

## 验证

- typecheck: **0 errors**
- format: **0 changes** (oxfmt 0 reformatted)
- 4 个 account/settings dialog tests: **4/4 PASS**
- 整体 vitest (P1 Phase 6 完成后): **1039 passed / 5 failed** (与 baseline 完全一致, 0 新 fail)
- 撤掉的 commits: `b4329052` + `b6e09d9c` (revert)