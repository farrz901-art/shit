# 导航子菜单 + 数据字典 (2026-07-02)

## 加一个新页面, 改 1 处

1. 改 [packages/service/config/dictionaries_seed.yaml](../../packages/service/config/dictionaries_seed.yaml) 中 `page_key` 字典:
   ```yaml
   - {
       key: my_page,
       label_zh: 我的页面,
       label_en: My Page,
       sort: 100,
       metadata_json: { path: "/my-page" },
     }
   ```
2. 跑 `cd packages/service && uv run python -m scripts.seed_dictionaries` 同步到 DB
3. 后端 cache 自动 warmup, 顶导航自动出现, 权限矩阵自动加入

## 子菜单 (hover dropdown)

把页面挂在某个顶级 page_key 下:
```yaml
- {
    key: admin_my_subpage,
    label_zh: 我的子页,
    label_en: My Sub Page,
    sort: 56,
    metadata_json: { path: "/admin/my-subpage", parent_id: "admin" },
  }
```

父级 (admin) 已标 `is_group: true`, 子项自动挂在下面.

## 父级不可点 (按 spec 决策)

父级 trigger 是 `<button>`, 不是 `<a>`, hover 弹 DropdownMenu 才进入子页.
直接点击父级 label 不会跳转.

## 权限矩阵

`/admin/permissions` 改成树形 UI:
- 父级 checkbox 永远 disabled (因为父级不入 role_permissions 表)
- 叶子单独 toggle, 进 pending
- indeterminate 状态自动从子项聚合

## 调试

- 子菜单不显示 → 检查 yaml 是否有 `parent_id` 指向存在的 key
- 父级 trigger 点了不弹菜单 → 看 Radix 控制台 + AppDropdownMenu 是否有错误
- 改了字典前端没刷新 → 看 PR7 cache invalidation, 编辑 dialog 的 onSuccess 是否触发 usePermissionsStore.reset()

## 相关文件

- Spec: [docs/superpowers/specs/2026-07-02-nav-submenu-design.md](../../superpowers/specs/2026-07-02-nav-submenu-design.md)
- Plan: [docs/superpowers/plans/2026-07-02-nav-submenu.md](../../superpowers/plans/2026-07-02-nav-submenu.md)
- 关键文件:
  - `packages/web/lib/nav/build-nav-tree.ts` — 纯函数, 树组装 + 权限过滤
  - `packages/web/components/layout/nav-dropdown.tsx` — 桌面端 hover dropdown
  - `packages/web/components/layout/mobile-nav-drawer.tsx` — 移动端 drawer
  - `packages/web/components/common/display/tree-checkbox.tsx` — 通用树形 checkbox
  - `packages/web/app/[locale]/admin/permissions/_components/permissions-table.tsx` — 权限矩阵 UI
  - `packages/service/src/permissions/cache.py` — 后端 metadata 透传