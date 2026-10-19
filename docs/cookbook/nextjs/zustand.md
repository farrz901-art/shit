# Zustand 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：L-语言/框架
> 🎯 读者：中高级 TS 工程师

---

## 目录

- [一、是什么 & 适用场景](#一是什么--适用场景)
- [二、安装 & 开发环境](#二安装--开发环境)
- [三、基础语法 & 类型系统](#三基础语法--类型系统)
- [四、核心概念](#四核心概念)
- [五、常用命令 & 工具链](#五常用命令--工具链)
- [六、项目集成点](#六项目集成点)
- [七、项目代码示例](#七项目代码示例)
- [八、项目没用到的能力 / 进阶方向](#八项目没用到的能力--进阶方向)
- [九、最佳实践 & 常见坑](#九最佳实践--常见坑)

---

## 一、是什么 & 适用场景

Zustand 是德语"状态"的意思，是一个轻量级、无样板代码的 React 状态管理库。它用最简单的 API（`create` + hook）替代 Redux 的 reducer / action / dispatch 三件套，单文件 < 1KB。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Zustand** | 轻量状态管理 | 简单、无模板、性能好 |
| **Redux Toolkit** | 完整状态方案 | 太重，本项目不需要 |
| **Jotai** | 原子化状态 | 适合细粒度场景 |
| **Valtio** | 代理 + mutation | 学习曲线略陡 |
| **React Context** | 内置 | 频繁更新性能差 |

**Zustand 解决的核心问题**：
- **跨组件共享状态**：不用 Context 透传
- **持久化**：内置 `persist` middleware，状态存 localStorage
- **无样板代码**：不用 action types、reducers、dispatch

---

## 二、安装 & 开发环境

### 2.1 版本

`zustand: ^5.0.14`（`packages/web/package.json`）

### 2.2 安装

```bash
bun add zustand
```

---

## 三、基础语法 & 类型系统

### 3.1 最简 Store

```typescript
import { create } from "zustand";

type CounterState = {
  count: number;
  increment: () => void;
  decrement: () => void;
};

const useCounterStore = create<CounterState>((set) => ({
  count: 0,
  increment: () => set((s) => ({ count: s.count + 1 })),
  decrement: () => set((s) => ({ count: s.count - 1 })),
}));

// 组件使用
const Counter = () => {
  const count = useCounterStore((s) => s.count);
  const increment = useCounterStore((s) => s.increment);
  return <button onClick={increment}>{count}</button>;
};
```

### 3.2 派生数据

```typescript
type TodoState = {
  todos: Todo[];
  filter: "all" | "done" | "pending";
  setFilter: (f: TodoState["filter"]) => void;
};

const useTodoStore = create<TodoState>((set) => ({
  todos: [],
  filter: "all",
  setFilter: (filter) => set({ filter }),
}));

// 组件
const FilteredTodos = () => {
  const filtered = useTodoStore((s) =>
    s.filter === "all" ? s.todos :
    s.filter === "done" ? s.todos.filter(t => t.done) :
    s.todos.filter(t => !t.done)
  );
  return <ul>{filtered.map(t => <li key={t.id}>{t.name}</li>)}</ul>;
};
```

### 3.3 异步 actions

```typescript
type UserState = {
  user: User | null;
  loading: boolean;
  error: Error | null;
  fetchUser: (id: number) => Promise<void>;
};

const useUserStore = create<UserState>((set) => ({
  user: null,
  loading: false,
  error: null,
  fetchUser: async (id) => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`/api/users/${id}`);
      const user = await res.json();
      set({ user, loading: false });
    } catch (e) {
      set({ error: e as Error, loading: false });
    }
  },
}));
```

---

## 四、核心概念

### 4.1 Store（仓库）

全局状态容器，由 `create<T>((set, get) => ({...}))` 创建。返回 `useStore` hook。

### 4.2 set / get

- `set((s) => ({ key: newValue }))`：合并更新
- `set({ key: newValue })`：直接更新
- `get()`：读当前 state（在 action 内访问其他字段）

### 4.3 选择器（Selector）

`useStore((s) => s.field)` 通过选择器订阅单个字段，避免不必要重渲染。

### 4.4 Middleware

Zustand 用 middleware 扩展能力：
- `persist`：localStorage 持久化
- `devtools`：Redux DevTools 集成
- `immer`：可变写法（`set((s) => { s.count++ })`）
- `subscribeWithSelector`：跨组件订阅

### 4.5 Slice 模式

大型 store 拆 slice 组合：

```typescript
import { StateCreator } from "zustand";

type UserSlice = { user: User | null; setUser: (u: User) => void };
type CartSlice = { items: CartItem[]; addItem: (i: CartItem) => void };

const createUserSlice: StateCreator<UserSlice & CartSlice, [], [], UserSlice> = (set) => ({
  user: null,
  setUser: (user) => set({ user }),
});

const createCartSlice: StateCreator<UserSlice & CartSlice, [], [], CartSlice> = (set) => ({
  items: [],
  addItem: (item) => set((s) => ({ items: [...s.items, item] })),
});

const useStore = create<UserSlice & CartSlice>()((...a) => ({
  ...createUserSlice(...a),
  ...createCartSlice(...a),
}));
```

---

## 五、常用命令 & 工具链

```bash
# 项目无专属命令
bun run typecheck   # TS 检查
bun run lint        # oxlint

# 调试：Redux DevTools
# 启用 devtools middleware 后浏览器装 Redux DevTools 扩展可看
```

---

## 六、项目集成点

### 6.1 项目当前使用 Zustand ^5.0.14

`packages/web/package.json:36` 含 `zustand: ^5.0.14`。

### 6.2 典型场景

- **聊天草稿**：`DRAFT_KEY = "rag.chat.draft.v1"` 持久化到 localStorage
- **UI 状态**：侧边栏开关、主题偏好、模态框状态
- **购物车 / 临时选择**：列表多选 / 临时筛选

### 6.3 项目持久化约定

`web/CLAUDE.md` 提到禁止 magic number，应该用 `const/index.ts` 定义持久化 key：

```typescript
// packages/web/const/index.ts
export const DRAFT_KEY = "rag.chat.draft.v1";
export const THEME_KEY = "rag.theme";
```

### 6.4 与 TanStack Query 区分

| 状态类型 | 工具 | 原因 |
|---------|------|------|
| 服务端数据 | TanStack Query | 自动 fetch / 缓存 / 失效 |
| 客户端临时 UI | Zustand | 即时读写，无网络 |
| 跨路由持久 | Zustand persist | localStorage |
| 表单状态 | React Hook Form | 性能 + 验证 |

---

## 七、项目代码示例

### 7.1 聊天草稿持久化

`packages/web/lib/chat/store.ts`（推测项目风格）：

```typescript
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { DRAFT_KEY } from "@/const";

type DraftState = {
  draft: string;
  setDraft: (text: string) => void;
  clearDraft: () => void;
};

export const useDraftStore = create<DraftState>()(
  persist(
    (set) => ({
      draft: "",
      setDraft: (draft) => set({ draft }),
      clearDraft: () => set({ draft: "" }),
    }),
    {
      name: DRAFT_KEY,                // localStorage key
      storage: createJSONStorage(() => localStorage),
    }
  )
);
```

### 7.2 UI 状态（侧边栏 / 模态框）

```typescript
type UIState = {
  sidebarOpen: boolean;
  modalStack: string[];             // 嵌套模态框
  toggleSidebar: () => void;
  pushModal: (id: string) => void;
  popModal: () => void;
};

const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  modalStack: [],
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  pushModal: (id) => set((s) => ({ modalStack: [...s.modalStack, id] })),
  popModal: () => set((s) => ({ modalStack: s.modalStack.slice(0, -1) })),
}));
```

### 7.3 选择器性能优化

```typescript
// 错：每次 store 变化都重渲染
const Component = () => {
  const store = useStore();  // 不传选择器
  return <div>{store.user?.name}</div>;
};

// 对：只订阅 user 字段
const Component = () => {
  const userName = useStore((s) => s.user?.name);
  return <div>{userName}</div>;
};

// 多字段：用 shallow 比较
import { shallow } from "zustand/shallow";

const Component = () => {
  const { name, email } = useStore(
    (s) => ({ name: s.user?.name, email: s.user?.email }),
    shallow
  );
  return <div>{name} {email}</div>;
};
```

### 7.4 跨 store 通信

```typescript
const useUserStore = create<UserState>((set) => ({ /* ... */ }));
const useCartStore = create<CartState>((set) => ({ /* ... */ }));

// 组件内同时订阅两个 store
const Component = () => {
  const user = useUserStore((s) => s.user);
  const items = useCartStore((s) => s.items);
  // 各自独立更新
};
```

### 7.5 与 Next.js App Router 集成

Next.js Server Components 不能用 hooks，Zustand store 必须在 `"use client"` 组件内访问：

```typescript
"use client";
import { useStore } from "@/lib/store";

export const ClientComponent = () => {
  const count = useStore((s) => s.count);
  return <div>{count}</div>;
};
```

---

## 八、项目没用到的能力 / 进阶方向

以下 Zustand 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **`devtools` middleware** | Redux DevTools 集成 | 开发环境强烈推荐 |
| **`immer` middleware** | 可变写法 | 复杂嵌套 state 时简化 |
| **`subscribeWithSelector` middleware** | 跨组件订阅 | 组件外监听状态变化 |
| **Slice 模式** | 大 store 拆分 | 状态多时使用 |
| **`createStore` + 手动 Provider** | 多 store 实例 | SSR / 测试场景 |
| **Computed atoms（vanilla store）** | 无 hook 的纯 store | Node.js / Workers 用 |
| **`useShallow` hook** | 浅比较 + 多选择器 | 替代 `shallow` 第二个参数 |
| **Selectors with custom equality** | 自定义相等比较 | 派生数据场景 |

**建议关注**：`devtools` middleware 在 dev 模式启用能极大提升调试体验。

---

## 九、最佳实践 & 常见坑

### 项目风格指南

1. **禁止 magic number 持久化 key**：用 `const/index.ts` 定义（如 `DRAFT_KEY`）
2. **常量替代字符串**：`DRAFT_KEY = "rag.chat.draft.v1"` 而非内联
3. **优先使用已安装库**：Zustand / react-use / es-toolkit 等，不重复造轮子
4. **优先用项目封装**：UI 状态用 zustand，但业务状态优先 TanStack Query

### 最佳实践

1. **小粒度 store**：每个 store 关注一类状态（user / cart / ui），不要一个 store 装所有
2. **避免大对象 store**：`create({ user: { name, email, posts, comments } })` 会让所有消费者重渲染
3. **持久化版本控制**：persist 加 `version` 字段，schema 变化时 `migrate`
4. **selector 尽量简单**：复杂派生数据用 `useMemo` 包一层
5. **测试用 `createStore` + `act`**：避免 hook 测试的复杂性

### 常见坑

1. **不传选择器**：`useStore()` 订阅整个 store，频繁更新会让组件无效重渲染
2. **持久化 SSR 报错**：Next.js 14+ 用 `createJSONStorage(() => localStorage)`，在 Server 端不会执行
3. **persist 的 hydration 不一致**：服务端 / 客户端 localStorage 状态不同 → React hydration mismatch，需要用 `skipHydration: true` 或 `onRehydrateStorage`
4. **Zustand v4 → v5 变化**：`create<T>()` 写法变了，必须用 `create<T>()(...)` 双调用
5. **selector 返回新对象引用**：`useStore((s) => ({ a: s.a, b: s.b }))` 每次新对象 → 无限重渲染，必须用 `shallow` 或 `useShallow`
6. **异步 action 写错位置**：

```typescript
// 错：在 setState 内 await
fetchUser: async (id) => {
  set({ loading: true });
  set({ user: await fetchUser(id) });  // 多次 setState 不是原子的
}

// 对：用 try/catch 包一次
fetchUser: async (id) => {
  set({ loading: true, error: null });
  try {
    const user = await fetchUser(id);
    set({ user, loading: false });
  } catch (e) {
    set({ error: e as Error, loading: false });
  }
}
```

---

## 📚 参考

- [Zustand 官方文档](https://zustand.docs.pmnd.rs/)
- [Zustand v5 迁移指南](https://github.com/pmndrs/zustand/blob/main/docs/migrations/migrating-to-v5.md)
- [Zustand 实战模式](https://github.com/pmndrs/zustand/tree/main/docs/guides)
- [Zustand + Next.js App Router](https://zustand.docs.pmnd.rs/guides/nextjs)
- [Jotai vs Zustand 对比](https://jotai.org/docs/basics/comparison)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
