先把结论放前面：
- **React 19 本身并不会“删掉” `memo` / `useCallback` / `useMemo`**，它们照样能用。
- 真正能“替代”它们的是 **React Compiler（自动记忆化）**，但这是 **编译器层面的新能力，不是新语法**，而且目前还是“可选 + 实验性/渐进采用”的状态，不是开箱即用默认全开。
- 对大多数项目：**可以先升级到 React 19，暂时不急着开 Compiler，等工具链成熟再逐步开启。**
下面分两块说：React 19 有哪些新特性，以及 Compiler 对 `memo` / `callback` 的影响。
---
## 一、React 19 的核心新特性（和性能/写法相关的）
官方博客的 React 19 新特性主要包括：Actions、`useActionState`、`useFormStatus`、`useOptimistic`、`use()`、`ref` 作为 prop、Context 简写、文档元数据、静态预渲染 API 等。
### 1. Actions：统一异步数据变更模式
核心：**在 `startTransition` 里跑异步函数，React 自动帮你管理 pending / 错误 / 乐观更新 / 表单重置**。
```js
// React 18：手动管 isPending / error
const [isPending, setIsPending] = useState(false);
const [error, setError] = useState(null);
const handleSubmit = async () => {
  setIsPending(true);
  const err = await updateName(name);
  setIsPending(false);
  if (err) setError(err);
};
// React 19：Actions（useTransition + 异步函数）
const [isPending, startTransition] = useTransition();
const handleSubmit = () => {
  startTransition(async () => {
    const err = await updateName(name);
    if (err) setError(err);
  });
};
```
配合 DOM 层的 `<form action={fn}>`，React 会自动处理表单提交、重置等。
### 2. `useActionState`：把 Action + 状态打包成一个 Hook
```js
const [error, submitAction, isPending] = useActionState(
  async (prevState, formData) => {
    const err = await updateName(formData.get('name'));
    if (err) return err;
    redirect('/path');
    return null;
  },
  null,
);
```
- `error`：最近一次 Action 的结果（这里只返回错误）
- `submitAction`：给你绑到 `<form action={submitAction}>` 的函数
- `isPending`：React 自动维护的提交状态
### 3. `useFormStatus`：子组件里读表单状态
```js
import { useFormStatus } from 'react-dom';
function SubmitButton() {
  const { pending } = useFormStatus();
  return <button disabled={pending}>{pending ? '提交中…' : '提交'}</button>;
}
```
不再需要把 `pending` 一层层传给按钮组件。
### 4. `useOptimistic`：官方乐观更新
```js
function ChangeName({ currentName, onUpdateName }) {
  const [optimisticName, setOptimisticName] = useOptimistic(currentName);
  const submitAction = async (formData) => {
    const newName = formData.get('name');
    setOptimisticName(newName); // 立刻显示“新名字”
    const updatedName = await updateName(newName);
    onUpdateName(updatedName); // 成功后再真正更新
  };
  return (
    <form action={submitAction}>
      <p>你的名字：{optimisticName}</p>
      <input name="name" />
      <button type="submit">更新</button>
    </form>
  );
}
```
请求失败时，React 会自动回滚到 `currentName`。
### 5. `use()`：在渲染里直接读 Promise / Context
```js
function Comments({ commentsPromise }) {
  const comments = use(commentsPromise); // 会在 Promise resolve 前挂起
  return comments.map(c => <p key={c.id}>{c.body}</p>);
}
function Page({ commentsPromise }) {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <Comments commentsPromise={commentsPromise} />
    </Suspense>
  );
}
```
- 可以读 **Promise**（配合 Suspense）
- 可以读 **Context**，而且 **支持条件调用**（比 `useContext` 更灵活）
### 6. `ref` 作为 prop：告别 `forwardRef`
```js
// React 19：函数组件可以直接接收 ref 作为 prop
function MyInput({ placeholder, ref }) {
  return <input placeholder={placeholder} ref={ref} />;
}
<MyInput ref={inputRef} />
```
- 新函数组件不再需要 `forwardRef`；
- 官方会提供 codemod 帮你自动迁移，未来版本会弃用 `forwardRef`。
### 7. Context 简写：`<Context value={...}>` 代替 `<Context.Provider>`
```js
const ThemeContext = createContext('');
function App({ children }) {
  // 以前：<ThemeContext.Provider value="dark">
  // 现在：
  return <ThemeContext value="dark">{children}</ThemeContext>;
}
```
更简洁，和原有 Provider 行为一致。
### 8. 文档元数据原生支持：`<title>` / `<meta>` / `<link>` 直接写在组件里
```js
function BlogPost({ post }) {
  return (
    <article>
      <title>{post.title}</title>
      <meta name="description" content={post.excerpt} />
      <h1>{post.title}</h1>
      ...
    </article>
  );
}
```
React 会自动把这些标签提升到 `<head>`，兼容 SSR / RSC / 流式渲染。
### 9. 新的静态预渲染 API：`prerender` / `prerenderToNodeStream`
```js
import { prerender } from 'react-dom/static';
async function handler(req) {
  const { prelude } = await prerender(<App />, { bootstrapScripts: ['/main.js'] });
  return new Response(prelude, { headers: { 'content-type': 'text/html' } });
}
```
比 `renderToString` 更适合静态站点生成，会等数据加载完再输出 HTML。
---
## 二、React Compiler：真正“替代 memo / useCallback / useMemo”的东西
### 1. Compiler 是什么，和 React 19 的关系？
- **React 19 = 新版本 React（核心库）**
- **React Compiler = 独立的编译器（Babel 插件），在构建时做自动优化**
官方文档明确说：Compiler 的目标是 **自动处理记忆化，减少手动使用 `useMemo`、`useCallback` 和 `React.memo` 的需求**。
> “Learn what React Compiler does and how it automatically optimizes your React application by handling memoization for you, eliminating the need for manual `useMemo`, `useCallback`, and `React.memo`.”
重要点：
- Compiler **不是** React 19 自带的默认行为，需要你安装 Babel 插件并配置；
- 截至 2025 年，官方文档仍把它当成 **实验性/渐进采用** 的能力，建议先在部分模块试，再逐步扩大范围；
- React 19 已经内置了 Compiler 的运行时 API（`react/compiler-runtime`），所以如果你在 19 上开 Compiler，不需要额外运行时包。
### 2. Compiler 对 `memo` / `useCallback` / `useMemo` 做了什么？
Compiler 在构建时对你的组件做静态分析，然后：
- **自动识别“昂贵的计算”**，插入类似 `useMemo` 的逻辑；
- **自动识别传给子组件的函数**，插入类似 `useCallback` 的稳定化处理；
- **自动识别“纯展示组件”**，插入类似 `React.memo` 的浅比较逻辑。
典型对比（来自社区示例）：
```js
// React 18：手动优化
function ExpensiveList({ items, filter }) {
  const filteredItems = useMemo(() => items.filter(i => i.category === filter), [items, filter]);
  const handleClick = useCallback((id) => { /* ... */ }, []);
  return (
    <ul>
      {filteredItems.map(item => (
        <ListItem key={item.id} item={item} onClick={handleClick} />
      ))}
    </ul>
  );
}
const ListItem = React.memo(({ item, onClick }) => {
  return <li onClick={() => onClick(item.id)}>{item.name}</li>;
});
// React 19 + Compiler：自动优化
function ExpensiveList({ items, filter }) {
  const filteredItems = items.filter(i => i.category === filter); // 编译器会自动记忆化
  const handleClick = (id) => { /* ... */ }; // 编译器会自动稳定化
  return (
    <ul>
      {filteredItems.map(item => (
        <ListItem key={item.id} item={item} onClick={handleClick} />
      ))}
    </ul>
  );
}
function ListItem({ item, onClick }) { // 不用手动 memo，编译器会处理
  return <li onClick={() => onClick(item.id)}>{item.name}</li>;
}
```
官方 `useCallback` 文档也明确提到：
> “React Compiler automatically memoizes values and functions, reducing the need for manual useCallback calls.”
### 3. Compiler 现在的状态：可以玩，但别全盘 All-in
- 2025 年 10 月，官方宣布 **React Compiler v1.0 稳定版** 发布；
- 但实际落地层面，社区普遍建议：
  - **新项目 / 新模块**：可以开 Compiler；
  - **老项目**：先局部开启（比如一个路由/一个模块），观察构建报错和运行行为，再逐步扩大；
  - 遇到编译器无法优化的“奇怪模式”，可以局部关掉（通过 `@react-compiler-disable` 指令）。
---
## 三、回到你的问题：React 19 里，还要不要写 `memo` / `useCallback`？
可以分三层看：
### 1. 不开 Compiler：和以前一样
- **React 19 不会删掉这些 API**，你完全可以继续写：
  ```js
  const MemoChild = React.memo(Child);
  const memoizedValue = useMemo(() => compute(a, b), [a, b]);
  const stableHandler = useCallback(() => { /* ... */ }, [dep]);
  ```
- 行为、最佳实践和 React 18 基本一致。
### 2. 开 Compiler：可以少写，但不是“立刻删光”
- 在 Compiler 覆盖的组件里，你可以：
  - 不再手动写 `useMemo` / `useCallback`；
  - 不再手动 `React.memo` 组件；
- 但：
  - 项目里 **老代码** 还可以继续存在；
  - 一些 Compiler 暂时处理不了的边界情况，你仍然需要手动补。
**建议做法**：新代码按“不写 memo/callback”的风格写，让 Compiler 接管；老代码暂时别动，等后续统一迁移。
### 3. 实际迁移节奏建议
- **第一步：升级到 React 19**
  先享受 Actions、`use`、`ref` 作为 prop、Context 简写等，这些和 Compiler 无关。
- **第二步：选一个模块开启 Compiler**
  比如一个后台管理列表页，观察：
  - 构建是否报错；
  - DevTools 里重渲染是否明显减少；
  - 包体积是否变化（官方有说能删掉未使用的 JSX 分支，减小 15–30% 体积）。
- **第三步：逐步扩大 Compiler 范围**
  等你确实体会到“少写一堆 memo/callback，性能还更好”，再考虑全项目开启。
---
## 四、一句话总结
- **React 19 的新特性（Actions、`use`、`ref` 作为 prop 等）更多是“写法更爽”，不会直接干掉 `memo` / `useCallback`。**
- 真正能“替代”它们的是 **React Compiler**，它通过编译时自动插入记忆化逻辑，让你不需要手写 `useMemo` / `useCallback` / `React.memo`。
- 目前 Compiler 已经有 v1.0 稳定版，但生态和工具链还在成熟中，**建议先局部试用，不要一上来就全面 All-in**。
如果你愿意，我可以根据你现有项目的规模（组件数量 / 是否有大量列表或表单），给一份更具体的“React 19 + Compiler 渐进迁移步骤”。
