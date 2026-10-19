# 导航栏配置化设计

**日期**: 2026-06-23
**状态**: 设计稿
**背景**: 每次加新页面都要改 header.tsx + permissions fallback 多处, 容易遗漏

---

## 问题

导航链接散落在 3 个地方, 全是硬编码:
- Header 导航栏: NAV_ITEMS 8 项
- UserMenu: 硬编码 isAdminLevel/isSuperAdmin 守卫
- SettingsDialog: 静态链接
加新页面 = 改 3 处 + 同步 fallback, 容易忘

## 方案: 现有 page_key 字典驱动

后端已有 page_key 字典 + /api/permissions/me 返 pages[]
让前端从 permissions.pages 渲染导航, 不再硬编码

### 数据流

字典 page_key (yaml) -> DB (seed_dictionaries) -> /api/permissions/me
  -> Header/frontend 从 permissions.pages 过滤 zones 渲染

## 改动清单

### 1. dictionaries_seed.yaml (后端)
- page_key items 加上新页面条目: buyers, 以后也在这加
- 每项有 key, label_zh, label_en, sort, metadata_json.path
- path 控制是否出现在导航栏 (有 path = 导航链接)

### 2. permissions/cache.py (后端)
- ALL_PAGE_KEYS_FALLBACK 和 _PAGE_METADATA_FALLBACK 同步加新 key

### 3. header.tsx (前端)
- 移除硬编码 NAV_ITEMS
- 从 permissions.pages 读, 过滤 path && allowed 渲染
- 用 translate(p.label_zh) 实现 i18n (已存在 en.json 翻译)

### 4. role_permissions 迁移 (后端)
- 新 migration 加 buyers 行: admin = true, user = false
- 以后加新页面同样需要 migration 配默认权限

## 加新页面的标准流程

1. dictionaries_seed.yaml page_key 加 item (含 path)
2. permissions/cache.py fallback 加 entry
3. alembic migration: role_permissions 插行 (默认权限)
4. (如果页面有 i18n 翻译: zh.json + en.json 加 key)
5. python -m scripts.seed_dictionaries 同步字典
6. uv run alembic upgrade head 跑权限迁移

以后加新页面不需要动 header.tsx 或任何前端组件 --
  dictionaries_seed.yaml + migration 就行

## 未来扩展 (Phase 2)

- zone 字段: 控制链接出现在 Header/UserMenu/SettingsDialog
- 导航配置管理页面 (admin UI) 让非开发者也可配置
- UserMenu + SettingsDialog 也从字典读 (当前先保持硬编码)

---
