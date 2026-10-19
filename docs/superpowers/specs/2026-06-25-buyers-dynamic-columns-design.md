# Buyers 列表动态画像字段列 (2026-06-25)

> 起源: `app/[locale]/buyers/page.tsx` 表格信息量过空, 仅展示 `buyer_name` + `buyer_key` + 状态 + 最近联系, 真实有信息量的画像数据 (`profile_data`) 没渲染出来. 后台已经支持配置任意画像字段 (`ProfileFieldConfig`), 表格应该跟后台配的字段动态生成列.
> 范围: 1 个前端页面 (buyers/page.tsx) + 1 个测试文件. **0 后端改动, 0 schema 改动, 0 admin/profile-fields 改动**

## 1. 目标

| 目标 | 现状 | 验收 |
|---|---|---|
| 表格信息量增加 | 列: `# / 买家 / 标识(buyer_key) / 状态 / 最近联系 / 操作`, 6 列 | 列: `# / 买家 / [动态画像字段 N 列] / 状态 / 最近联系 / 操作`, 6+N 列, N = 后台激活字段数 |
| buyer_key 列删除 | 列 `buyer_key` 静态渲染 | 列删除, 移出 buildColumns |
| 动态画像字段列 | 无 | 来自 `useFieldConfigs()` 激活 (`is_active=true`) 且按 `sort_order` 排序的字段, 1 字段 = 1 列 |
| 按 field_type 差异化渲染 | 无 | `select` / `tags` 画 shadcn Badge (tags 多个 Badge), `number` 加 `num` CSS class 等宽数字, `boolean` 画 "是/否", 其他纯文本 |
| 0 后端改动 | - | ProfileFieldConfig / BuyerProfile schema 0 改动 |
| 0 调用方改动 | - | buyers/[id]/* 0 改动 |

## 2. 非目标 (YAGNI)

- ❌ 列拖拽 / 列排序 / 列固定 / 列宽用户偏好持久化 — 当前 spec 只做静态动态列
- ❌ 字段筛选 / 排序 / 全文搜索 — `filterProfiles` 当前只匹配 `buyer_name` + `buyer_key`, 未来再加
- ❌ 删除 `buyer_key` 后端字段 / 改 BuyerProfile schema
- ❌ 改 admin/profile-fields 页 (`is_active` / `sort_order` 的 UI 已在那边)
- ❌ 改 `useFieldConfigs()` / `useBuyerProfiles()` hook 实现
- ❌ 改 ProfileFieldConfig / BuyerProfile / ProfileFieldValue 类型
- ❌ 改后端 `/api/buyer-profile/fields` 或 `/api/buyer-profiles` 接口
- ❌ 加 row 虚拟化 / 列虚拟化 — 字段数有限 (≤ 20), 真实表格不卡

## 3. 设计

### 3.1 数据流

```
buyers/page.tsx
  ├── useBuyerProfiles(statusFilter?)          # 现有, 不动
  │     ↓ BuyerProfile[] (含 profile_data: Record<fieldCode, ProfileFieldValue>)
  ├── useFieldConfigs()                        # 新增调用
  │     ↓ ProfileFieldConfig[] (含 code, label, field_type, sort_order, is_active)
  │
  ├── 过滤: is_active=true 且 sort_order 升序
  ├── 列构建:
  │     静态列 (# / 买家 / 状态 / 最近联系 / 操作) + 动态列 (1 字段 = 1 列)
  │
  └── DataTable 渲染 (跟现状一致, 0 改动 DataTable 用法)
```

### 3.2 文件改动

**Files**:
- Modify: `packages/web/app/[locale]/buyers/page.tsx` (~195 行 → ~230 行)
- Create: `packages/web/app/[locale]/buyers/page.test.tsx` (新, ≥ 6 it)
- Modify: `packages/web/messages/zh.json` + `packages/web/messages/en.json` (少量新 i18n keys, 见 §3.6)

### 3.3 useFieldConfigs() + 加载态

```typescript
const { data: configs = [], isLoading: isLoadingFields, error: fieldsError } = useFieldConfigs();
const { data, isLoading: isLoadingProfiles, error: profilesError } = useBuyerProfiles(
  statusFilter ? { status: statusFilter } : undefined,
);

// 等两者都 ready 再 render (跟现状 isLoading 模式一致)
if (isLoadingProfiles || isLoadingFields) {
  return <LoadingSkeleton rows={5} />;
}

// 错误聚合
const error = profilesError ?? fieldsError;
```

字段配置失败时: 顶部 ErrorBanner 展示, **不阻塞表格**, 表格回退到基础 5 列 (无动态列). 买家列表本身仍可用.

### 3.4 动态列生成

新内部 helper `buildProfileColumn`:

```typescript
const buildProfileColumn = (cfg: ProfileFieldConfig): ColumnDef<BuyerProfile> => {
  const width: ColumnWidth = { max: 240, min: 120 };
  const baseColumn: ColumnDef<BuyerProfile> = {
    key: `profile_${cfg.code}`,  // 避免跟静态列冲突 (静态列 key: index/buyer_name/buyer_key/status/last_contact_at/actions)
    title: cfg.label,
    width,
  };
  switch (cfg.field_type) {
    case "select":
      return {
        ...baseColumn,
        render: (row) => {
          const field = row.profile_data[cfg.code];
          if (field === undefined || field.value === null || field.value === undefined) {
            return "—";
          }
          return <Badge variant="secondary">{String(field.value)}</Badge>;
        },
      };
    case "tags":
      return {
        ...baseColumn,
        render: (row) => {
          const field = row.profile_data[cfg.code];
          if (field === undefined || !Array.isArray(field.value)) {
            return "—";
          }
          const tags = field.value.filter((tag): tag is string => typeof tag === "string");
          if (tags.length === ZERO) {
            return "—";
          }
          return (
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <Badge key={tag} variant="secondary">{tag}</Badge>
              ))}
            </div>
          );
        },
      };
    case "number":
      return {
        ...baseColumn,
        render: (row) => {
          const field = row.profile_data[cfg.code];
          if (field === undefined || field.value === null || field.value === undefined) {
            return "—";
          }
          return <span className="num text-sm">{String(field.value)}</span>;
        },
      };
    case "boolean":
      return {
        ...baseColumn,
        render: (row) => {
          const field = row.profile_data[cfg.code];
          if (field === undefined || field.value === null || field.value === undefined) {
            return "—";
          }
          return String(field.value) === "true" || field.value === true
            ? translate("是")
            : translate("否");
        },
      };
    default:  // text / 未知 field_type
      return {
        ...baseColumn,
        render: (row) => {
          const field = row.profile_data[cfg.code];
          if (field === undefined || field.value === null || field.value === undefined) {
            return "—";
          }
          return <span className="text-sm">{String(field.value)}</span>;
        },
      };
  }
};
```

### 3.5 buildColumns 改造

```typescript
const activeFields = useMemo(
  () =>
    configs
      .filter((cfg) => cfg.is_active)
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order),
  [configs],
);

const profileColumns = useMemo(
  () => activeFields.map(buildProfileColumn),
  [activeFields],
);

const buildColumns = (
  translate: (key: string) => string,
): ColumnDef<BuyerProfile>[] => [
  // 静态列 (跟现状一致, 删 buyer_key)
  { key: "index", ... },
  { key: "buyer_name", ... },
  // 动态画像字段列 (插在 buyer_name 后面, 状态/最近联系前面)
  ...profileColumns,
  { key: "status", ... },
  { key: "last_contact_at", ... },
  { key: "actions", ... },
];
```

注: 动态列插在 "买家" 之后、"状态" 之前. 视觉顺序:
```
[#] [买家] [画像 1] [画像 2] ... [画像 N] [状态] [最近联系] [操作]
```

### 3.6 新增 i18n keys

zh.json + en.json 各加 1 个 key (Boolean 字段渲染):

| zh.json value | en.json value |
|---|---|
| `"是"` | `"Yes"` |
| `"否"` | `"No"` |

`"买家"` / `"标识"` / `"状态"` / `"最近联系"` / `"操作"` / `"全部"` / `"激活"` / `"已归档"` / `"搜索"` / `"暂无买家"` 等现有 key 直接复用, 不改.

但 `"标识"` 列被删了, 它从 buildColumns 移除后, **zh.json + en.json 里 `"标识"` 这个 key 仍保留** (虽然表格不再使用), 不删避免影响其他潜在引用.

注: 用户后续在 admin/profile-fields 配置字段时, `label` 是用户输入任意字符串 (中英文均可), **不走 i18n 系统** (配置数据, 不是文案). 字段列 `title` 直接用 `cfg.label`.

### 3.7 错误处理策略

| 情况 | 处理 |
|---|---|
| `useBuyerProfiles` 失败 | 顶部 ErrorBanner, 表格不渲染 (现状行为, 保留) |
| `useFieldConfigs` 失败 | 顶部 ErrorBanner, 表格回退基础 5 列 (无动态列), 买家列表仍可用 |
| 两者都失败 | 顶部 2 个 ErrorBanner (可堆叠), 仅基础 5 列 |
| `profile_data[code]` 缺失 | 单 cell 渲染 "—" (per-field_type 判空已处理) |
| `field_type` 未知值 (未来加新类型) | 走 default 分支, 纯文本, 不报错 |

### 3.8 filterProfiles 调整

现状 `filterProfiles` 匹配 `buyer_name` + `buyer_key`. 删 `buyer_key` 列后, 该匹配逻辑继续保留 (买家仍然可能有 buyer_key, 只是不展示了). 业务上 `buyer_key` 是机器标识, 搜索匹配它仍有意义.

不动.

### 3.9 测试策略

新增 `packages/web/app/[locale]/buyers/page.test.tsx`:

测试要点 (≥ 6 it):

1. **基础渲染** — 表格渲染列头 + 行数
2. **动态列从 useFieldConfigs 加载** — mock `useFieldConfigs` 返回 3 个字段, 验证表格多了 3 列
3. **按 sort_order 排序** — mock configs `sort_order` 顺序乱, 验证列顺序跟 sort_order 升序一致
4. **只显示 is_active=true 的字段** — mock configs 1 激活 + 1 停用, 验证只有 1 个动态列
5. **select 字段画 Badge** — mock select 字段 value="华东", 验证 cell 含 Badge 且 text=华东
6. **tags 字段画多个 Badge** — mock tags 字段 value=["云屏","数显"], 验证 cell 含 2 个 Badge
7. **boolean 字段画 是/否** — mock boolean 字段 value=true, 验证 cell text 是/否
8. **缺失 profile_data 渲染 —** — mock profile_data 没有某字段, 验证 cell 是 "—"
9. **useFieldConfigs 失败回退基础列** — mock useFieldConfigs 失败, 验证表格只有 5 列 + ErrorBanner

Test 工具:
- vitest + @testing-library/react
- mock `useBuyerProfiles` + `useFieldConfigs` (项目里 `lib/api/*` 都是独立函数, hook 实现细节可单独 mock)
- 不连真后端 (项目铁律: 测试 0 真实 DB/网络)

### 3.10 顺序约束 (项目铁律)

1. `bun run format` (0 报错)
2. `bun run lint:fix` (0 报错)
3. `bun run typecheck` (0 error)
4. `bun run test` (0 新 fail; baseline fail 不算)
5. `git add` + commit (prefix `feat:`)

中途 1 个 commit (跟 spec §5.3 验收一致), 拆太细没必要.

### 3.11 风险 + 缓解

| 风险 | 缓解 |
|---|---|
| 后台配的字段突然不激活 (is_active 改 false), 表格列数变化 → 用户视觉跳变 | 接受 (跟 spec "动态" 性质一致), 1 次刷新即稳定 |
| 不同买家 profile_data key 不全 → cell "—" 比例可能高 | 接受, 走字段提取覆盖率, UI 已用 "—" 占位 |
| 字段值类型变化 (后台 text → number) → 后端返的 value 类型跟 field_type 不一致 | 默认分支兜底 (`String(value)`), 不报错 |
| 字段标签 cfg.label 含特殊字符 (HTML / 引号) → 列 title 渲染问题 | shadcn DataTable title 是 string, React 转义安全; 接受 |
| useFieldConfigs 跟 useBuyerProfiles 速率不一致 → 表格闪烁 | 等两者都 ready 再 render (跟现状 `if (isLoading) return LoadingSkeleton` 模式一致) |
| 字段数过多 (e.g. 后台配 20 个) → 表格很宽需横向滚动 | 接受, 当前 spec 不限列数, 横滚是行业惯例 |

## 4. 关联文档

- 上游 spec: [2026-06-22-buyer-profile-design.md](./2026-06-22-buyer-profile-design.md) (客户画像系统 origin)
- 上游 spec: [2026-06-22-buyer-profile-to-dify-design.md](./2026-06-22-buyer-profile-to-dify-design.md) (Dify 集成)
- 项目铁律: [packages/web/CLAUDE.md §零 lint warning 规范](../../packages/web/CLAUDE.md)
- DataTable 封装: 刚拆分完成, 见 [2026-06-25-data-table-split-design.md](./2026-06-25-data-table-split-design.md)
- 类型参考: `packages/web/lib/buyer-profile/types.ts`
- Hook 参考: `packages/web/lib/buyer-profile/hooks.ts`

## 5. 验收

### 5.1 功能验收

- [ ] buyers/page.tsx 表格列顺序: `# / 买家 / [动态画像字段 N 列] / 状态 / 最近联系 / 操作`
- [ ] buyer_key 列从 buildColumns 删除 (commit diff 应显示这一行移除)
- [ ] 动态列数 = 后台 `useFieldConfigs()` 返回的 `is_active=true` 字段数
- [ ] 动态列按 `sort_order` 升序
- [ ] select 字段 cell 渲染 shadcn `Badge variant=secondary`
- [ ] tags 字段 cell 渲染 N 个 `Badge variant=secondary`
- [ ] number 字段 cell 渲染 `<span class="num text-sm">{value}</span>`
- [ ] boolean 字段 cell 渲染 "是" / "否" (i18n)
- [ ] text / 未知字段 cell 渲染纯文本
- [ ] profile_data 缺失 / value 是 null 渲染 "—"
- [ ] useFieldConfigs 失败: 顶部 ErrorBanner + 表格回退到 `# / 买家 / 状态 / 最近联系 / 操作` 5 列 (无动态画像字段列)
- [ ] useBuyerProfiles 失败: 顶部 ErrorBanner + 表格不渲染 (现状行为)

### 5.2 测试验收

- [ ] `page.test.tsx` 新建, ≥ 6 it (实际目标 9 it, 覆盖 §3.9 列出的 9 个测试点)
- [ ] `bun run test` 0 新 fail
- [ ] 测试 100% mock, 0 真后端连 (项目铁律)

### 5.3 质量验收

- [ ] `bun run format` 0 报错
- [ ] `bun run lint:fix` 0 报错
- [ ] `bun run typecheck` 0 error
- [ ] 0 `function` 声明 (全 `const = () =>`)
- [ ] 0 单字符变量名 (val / idx 等)
- [ ] 0 魔法数字 (顶层 const)
- [ ] 0 行内 `onClick` 复杂表达式
- [ ] import 字母排序
- [ ] 1 个 commit `feat(buyers): 表格动态列展示画像字段 + 删除 buyer_key 列`

### 5.4 行为验收

- [ ] 表格整体视觉仍走 DataTable 封装, 0 行为变化
- [ ] 状态筛选 / 搜索 / 行点击 行为不变
- [ ] 4 个买家详情页 (`buyers/[id]/*`) 0 改动
- [ ] admin/profile-fields 页 0 改动
- [ ] 后端 schema / API 0 改动

### 5.5 i18n 验收

- [ ] `messages/zh.json` 加 `"是"` / `"否"` (identity 模式: value=key)
- [ ] `messages/en.json` 加 `"Yes"` / `"No"` (翻译)
- [ ] `"标识"` key 在 zh/en.json 保留 (虽然表格不用, 避免影响其他引用)

## 6. 实施边界

### 6.1 In scope

- 1 个页面改 (`buyers/page.tsx`)
- 1 个新测试 (`buyers/page.test.tsx`)
- 2 个 i18n 文件加 4 行 (zh/en 各加 "是" / "否")

### 6.2 Out of scope

- 0 后端 / schema / API 改动
- 0 admin/profile-fields 改动
- 0 buyers/[id]/* 改动
- 0 ProfileFieldConfig / BuyerProfile 类型改动
- 0 useFieldConfigs / useBuyerProfiles hook 改动
- 0 DataTable 改动
- 列拖拽 / 排序 / 筛选 / 全文搜索 (未来 spec)

## 7. commit 信息模板

```
feat(buyers): 表格动态列展示画像字段 + 删除 buyer_key 列

- 表格列顺序: # / 买家 / [动态画像 N 列] / 状态 / 最近联系 / 操作
- 动态列来源: useFieldConfigs() 激活 (is_active=true) 且按 sort_order 升序
- 渲染按 field_type 差化: select/tags → Badge, number → 等宽字体,
  boolean → 是/否, 其他纯文本, null → —
- 删除 buyer_key 列 (业务上 buyer_key 是机器标识, 不展示给客户)
- 加 page.test.tsx (9 it), mock hook + 0 真后端连
- i18n zh/en.json 加 "是" / "否" / "Yes" / "No" (boolean 渲染)

0 后端 / schema / API 改动, 0 admin/profile-fields 改动,
4 个买家详情页 0 改动.
```