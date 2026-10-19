# Handoff: 前端重构 (refactor/frontend-code-quality)

> **日期:** 2026-06-23
> **分支:** `refactor/frontend-code-quality`
> **状态:** Phase 1-4 完成 (P5-P7 待执行)

## 已完成

### Phase 1: react-use + es-toolkit + useMemo/useCallback 清理 ✅
- `useToggle` (react-use) 替换 10+ 处 `useState(false) + toggle`
- `groupBy` (es-toolkit) 替换手写 `reduce` 分组
- 清理 2 处无意义 `useCallback(fn, [])`

### Phase 2: 提取通用 Hooks ✅ — `lib/hooks/`
| Hook | 用途 |
|------|------|
| `useDialog` | Dialog open/close 状态管理 |
| `usePagination` | 分页计算 (page/totalPages/hasNext/hasPrev) |
| `useQueryParams` | URL query 参数读写 |
| `useConfirm` | AppConfirm + 确认状态组合 |

### Phase 3: 提取通用组件 ✅ — `components/common/`
| 组件 | 用途 |
|------|------|
| `PageHeader` | 返回按钮 + 标题 (12+ 处替换) |
| `LoadingSkeleton` | 加载骨架屏 (10+ 处替换) |
| `ConfirmDialog` | 确认弹窗 (基于 AlertDialog) |
| `SectionCard` | 带标题分组 Card |
| `SearchInput` | 带 react-use debounce 的搜索框 |
| `StatusBadge` | status→颜色 Badge |
| `DataEmpty` | 已有组件，替换手写空态 |

### Phase 4: 大组件拆分 ✅ — 6 个大文件拆分
| 文件 | 减行 | 产出 |
|------|------|------|
| `admin-users-table.tsx` | 539→331 (-208) | `useUserTable` + `UserFilters` |
| `triples-form.tsx` | 444→~200 | `useTripleForm` |
| `task-detail-client.tsx` | 437→~200 | `TaskInfo` + `TaskFiles` + `TaskDownload` |
| `permissions-table.tsx` | 400→~80 | `usePermissionsTable` + `PermissionRow` |
| `output-list-client.tsx` | 366→~150 | `useOutputList` + `OutputCard` |
| `chat-shell.tsx` (727) | **待执行** | 最复杂，需单独拆分 |

## 待执行

### Phase 5: RSC/RSF 拆分 ⏳
- 23 个无 `"use client"` 页面逐页分析
- 提取 RSF (Server Functions) 到 `lib/actions/`

### Phase 6: Zustand 状态收敛 ⏳
- 创建 `useUIStore` (sidebar 等跨组件 UI 状态)
- 创建 `useChatStore` (chat-shell 的 8 个 useState)

### Phase 7: 最终验证 ⏳
- `jscpd` 扫描结构重复率
- 全量 tsc + vitest + oxlint

## 关键提醒

1. **chat-shell(727行)** 是最大风险项 — 涉及流式消息/IDB 同步/录音/反馈，拆分前需要完整回归测试
2. **Phase 5 RSC 拆分**可能触发 `"use client"` → server component 迁移，需检查是否有浏览器 API 依赖
3. **Phase 6 Zustand** 需要 chat-shell 先拆分完 (Phase 4 完成) 才能做
4. 所有新组件在 `components/common/` 下，已通过 oxlint 规范
