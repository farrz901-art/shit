# es-toolkit 教程

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

es-toolkit 是韩国 Toss 团队出品的现代化 JavaScript 工具库，是 lodash 的精神继承者，定位是"更小、更快、更类型安全、面向 ES6+"。它覆盖数组、对象、数学、函数式编程、Promise 等 200+ 工具函数。

**同类对比：**

| 库 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **es-toolkit** | 现代化工具库 | lodash 替身，体积小 2-3x，类型好 |
| **lodash** | 经典工具库 | 体积大（70KB+），老牌生态 |
| **ramda** | 函数式编程库 | 偏向 FP 风格，学习曲线高 |
| **原生 ES** | 内置方法 | map/filter/some 够用，但缺链式 |
| **date-fns** | 日期工具 | 专门处理日期，es-toolkit 不覆盖 |

**es-toolkit 解决的核心问题**：
- **数组链式**：`users.filter(...).map(...).uniqBy(...)`
- **深拷贝**：`cloneDeep(obj)` 不影响原对象
- **去抖节流**：`debounce(fn, 300)` / `throttle(fn, 1000)`
- **类型安全**：TypeScript 一等支持，泛型推断好
- **小体积**：Tree-shake 后只 import 用到的函数

---

## 二、安装 & 开发环境

### 2.1 安装

```bash
# 项目已装 (package.json: "es-toolkit": "^1.48.1")
cd packages/web
bun install
```

### 2.2 ESM 导入

```typescript
import { chunk, uniqBy, debounce } from "es-toolkit";
// 或
import { chunk } from "es-toolkit/array";
import { debounce } from "es-toolkit/function";
```

---

## 三、基础语法 & 类型系统

### 3.1 数组操作

```typescript
import { chunk, uniqBy, groupBy, sortBy, partition, difference } from "es-toolkit";

chunk([1, 2, 3, 4, 5], 2);
// [[1, 2], [3, 4], [5]]

uniqBy([{ id: 1 }, { id: 2 }, { id: 1 }], (x) => x.id);
// [{ id: 1 }, { id: 2 }]

groupBy([1, 2, 3, 4], (x) => x % 2 ? "odd" : "even");
// { odd: [1, 3], even: [2, 4] }

sortBy([{ name: "B" }, { name: "A" }], (x) => x.name);
// [{ name: "A" }, { name: "B" }]

partition([1, 2, 3, 4], (x) => x % 2 === 0);
// [[2, 4], [1, 3]]

difference([1, 2, 3], [2, 3, 4]);
// [1]
```

### 3.2 对象操作

```typescript
import { pick, omit, invert, mapValues } from "es-toolkit";

pick({ a: 1, b: 2, c: 3 }, ["a", "c"]);
// { a: 1, c: 3 }

omit({ a: 1, b: 2, c: 3 }, ["b"]);
// { a: 1, c: 3 }

invert({ a: "x", b: "y" });
// { x: "a", y: "b" }

mapValues({ a: 1, b: 2 }, (v) => v * 10);
// { a: 10, b: 20 }
```

### 3.3 函数式

```typescript
import { debounce, throttle, once, memoize, deburr } from "es-toolkit";

const debounced = debounce((text: string) => console.log(text), 300);
debounced("a"); debounced("b"); debounced("c");
// 300ms 后输出 1 次 "c"

const throttled = throttle(() => console.log("tick"), 1000);
// 1s 内最多 1 次

const init = once(() => console.log("init"));
init(); init();
// 只输出 1 次
```

### 3.4 数学

```typescript
import { sum, mean, max, min, range, clamp } from "es-toolkit";

sum([1, 2, 3]);          // 6
mean([1, 2, 3, 4]);      // 2.5
max([1, 2, 3]);          // 3
range(1, 5);             // [1, 2, 3, 4]
clamp(15, 0, 10);        // 10
```

### 3.5 链式

```typescript
import { pipe } from "es-toolkit";

const addOne = (x: number) => x + 1;
const double = (x: number) => x * 2;
const toString = (x: number) => `Result: ${x}`;

const compute = pipe(addOne, double, toString);
compute(3);  // "Result: 8"
```

---

## 四、核心概念

### 4.1 不可变

es-toolkit 始终返回新对象，**不修改入参**。这点跟 lodash 一致。

### 4.2 类型推断

```typescript
import { first, last } from "es-toolkit";

const arr: number[] = [1, 2, 3];
first(arr);     // type: number | undefined
last(arr);      // type: number | undefined

const empty: number[] = [];
first(empty);   // undefined（不报错）
```

### 4.3 Tree-shake 友好

```typescript
// 推荐：named import，esbuild/rollup 自动 tree-shake
import { chunk } from "es-toolkit";

// 避免：default import 全量引入
import _ from "es-toolkit";  // ❌ 引入全部
```

### 4.4 Predicate 函数（而非字符串）

```typescript
// es-toolkit 用函数谓词
uniqBy(arr, x => x.id);
sortBy(arr, x => x.name);

// 不像 lodash 早期用字符串属性
// lodash: _.uniqBy(arr, "id")
// lodash: _.sortBy(arr, "name")
```

### 4.5 跟 React 19 兼容

所有函数不依赖 React，纯函数。可以在 Server Component、Client Component、Node.js 任何环境用。

---

## 五、常用命令 & 工具链

es-toolkit 不需要单独命令。用 TypeScript 推断：

```bash
# 项目命令
bun run typecheck   # tsc --noEmit
bun run lint        # oxlint
```

---

## 六、项目集成点

### 6.1 项目风格指南（项目 CLAUDE.md 强制）

> 优先使用已安装的库和框架新特性
> 优先使用 TanStack Query, zustand, **react-use**, **es-toolkit**, date-fns 等已经装好的库来实现功能，而不是什么都自己实现

### 6.2 项目典型使用场景

- **数组去重 / 过滤 / 分组**：`uniqBy` / `groupBy` / `partition`
- **对象子集**：`pick` / `omit`（构造 Pydantic 兼容 dict）
- **防抖搜索**：`debounce` 搜索输入
- **深拷贝**：`cloneDeep` 状态复制
- **链式数据处理**：`pipe` 组合多个转换

### 6.3 跟 react-use 的关系

| 工具 | 定位 |
|------|------|
| `es-toolkit` | 纯函数工具（数组 / 对象 / 函数） |
| `react-use` | React Hook 工具（`useDebounce` / `useLocalStorage` / `useIntersection`） |

业务需要时：
- **纯函数逻辑**（不依赖 React）→ `es-toolkit`
- **React Hook**（订阅 state / 副作用）→ `react-use`

---

## 七、项目代码示例

### 7.1 数组去重（用户列表）

```typescript
import { uniqBy } from "es-toolkit";

const users = [
  { id: 1, name: "Alice" },
  { id: 2, name: "Bob" },
  { id: 1, name: "Alice (dup)" },  // 重复
];
const uniqueUsers = uniqBy(users, u => u.id);
// 3 → 2
```

### 7.2 表格列筛选

```typescript
import { groupBy, sortBy } from "es-toolkit";

// 按状态分组
const grouped = groupBy(rows, r => r.status);
// { pending: [...], approved: [...] }

// 按时间排序
const sorted = sortBy(rows, r => new Date(r.created_at).getTime());
```

### 7.3 搜索防抖

```typescript
import { useState } from "react";
import { debounce } from "es-toolkit";

const useSearch = () => {
  const [query, setQuery] = useState("");
  const debouncedSet = debounce((v: string) => setQuery(v), 300);
  return { query, debouncedSet };
};
```

### 7.4 对象子集

```typescript
import { pick, omit } from "es-toolkit";

const user = { id: 1, name: "Alice", password: "hash", email: "a@x.com" };

// 给前端返时不带 password
const safeUser = omit(user, ["password"]);

// 表单只展示部分字段
const formFields = pick(user, ["name", "email"]);
```

### 7.5 链式数据处理

```typescript
import { pipe } from "es-toolkit";

const processed = pipe(
  (arr: number[]) => arr.filter(x => x > 0),      // 过滤
  (arr: number[]) => arr.map(x => x * 2),         // 翻倍
  (arr: number[]) => arr.reduce((a, b) => a + b, 0),  // 求和
);
processed([-1, 2, 3, 4]);  // 14
```

### 7.6 深拷贝

```typescript
import { cloneDeep } from "es-toolkit";

// 不修改原对象
const original = { user: { name: "Alice", tags: ["vip"] } };
const copy = cloneDeep(original);
copy.user.tags.push("active");
console.log(original.user.tags);  // ["vip"]
console.log(copy.user.tags);      // ["vip", "active"]
```

### 7.7 Pydantic 兼容 payload 构造

```typescript
import { pick } from "es-toolkit";

const formData = { name: "Alice", email: "a@x.com", _csrf: "abc" };
// 发给后端前去掉无关字段
const payload = pick(formData, ["name", "email"]);
// { name: "Alice", email: "a@x.com" }
```

### 7.8 数值计算

```typescript
import { clamp, range, sum } from "es-toolkit";

// 限制 pagination
const page = clamp(queryPage, 1, 100);
const offset = (page - 1) * pageSize;

// 总分
const totalScore = sum(exams.map(e => e.score));
```

---

## 八、项目没用到的能力 / 进阶方向

以下 es-toolkit 能力项目当前未充分使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **Async (`delay` / `retry`)** | Promise 工具 | 项目用 TanStack Query 替代 |
| **Date (`formatDate`)** | 日期格式化 | 项目用 `date-fns` |
| **Math (`sumBy` / `meanBy`)** | 聚合 | 大数据集用 sql 聚合 |
| **`range` / `rangeRight`** | 生成序列 | 测试数据生成 |
| **`zip` / `unzip`** | 数组转置 | 矩阵数据 |
| **`shuffle` / `sample`** | 随机抽样 | 测试数据 |
| **`deburr`** | 去重音符号 | i18n 搜索 |
| **Functional (`flow` / `flowRight`)** | 函数组合 | 跟 `pipe` 同义 |
| **Tree-shake subpath imports** | `es-toolkit/array` | 大项目分包优化 |

**建议关注**：`debounce` 在搜索 / window resize / scroll 事件都用得上。

---

## 九、最佳实践 & 常见坑

### 项目风格指南（项目 CLAUDE.md 强制）

1. **优先使用 es-toolkit**：数组 / 对象 / 函数操作不要自己手写循环
2. **优先使用 TypeScript 类型**：所有 es-toolkit 函数泛型推断好
3. **不要 import 默认对象**：`import { chunk } from "es-toolkit"` 而非 `import _`
4. **不修改入参**：es-toolkit 不可变，自己写代码也要遵守

### 最佳实践

1. **named import**：

```typescript
// ✅ 好：tree-shake
import { chunk, groupBy, sortBy } from "es-toolkit";

// ❌ 差：全量
import * as _ from "es-toolkit";
```

2. **链式 vs 函数组合**：

```typescript
// 简单：链式
const result = arr.filter(x => x > 0).map(x => x * 2).slice(0, 10);

// 复杂：pipe
const transform = pipe(
  filter(x => x > 0),
  map(x => x * 2),
  take(10),
);
```

3. **不可变**：es-toolkit 内部不修改，但自己写代码用 `const` + spread：

```typescript
// ✅ 不修改
const newUser = { ...user, name: "Bob" };

// ❌ 改了
user.name = "Bob";
```

4. **Predicate 函数**：不要传字符串属性名（`"name"`），传函数（`x => x.name`）

5. **Debounce + cleanup**：

```typescript
useEffect(() => {
  const debounced = debounce(handler, 300);
  debounced();
  return () => debounced.cancel();   // 组件卸载时清理
}, [handler]);
```

### 常见坑

1. **`debounce` 立刻执行**：

```typescript
const fn = debounce(handler, 300);
fn();  // 300ms 后才执行（不是立刻）
```

2. **`cloneDeep` 对 `Date` / `Map` / `Set` 行为**：es-toolkit 1.48+ 支持，但旧版本可能浅拷贝

3. **`groupBy` 返回对象是普通对象**，不是 `Map`：

```typescript
const grouped = groupBy(arr, x => x.id);
grouped.get?.(1);  // ❌ 报错
grouped[1];        // ✅
```

4. **大量数据时优先用 SQL 聚合**：客户端 `groupBy` 10000+ 条数据会卡，应该在 API 层 `GROUP BY`

5. **`partition` 返回 `[pass, fail]`，容易解构错**：

```typescript
const [adults, minors] = partition(people, p => p.age >= 18);
// adults: 是成年的，minors: 是未成年的
// 不要误读为 [true, false]
```

6. **`throttle` 首尾不触发**：`throttle(fn, 1000)` 第一次立即触发，最后一次可能被吞

7. **TypeScript 泛型**：

```typescript
// es-toolkit 自动推断
import { uniqBy } from "es-toolkit";
const result = uniqBy([{ id: 1 }], x => x.id);
// result: { id: number }[]，不需要手动标注
```

---

## 📚 参考

- [es-toolkit 官方文档](https://es-toolkit.dev/)
- [es-toolkit GitHub](https://github.com/toss/es-toolkit)
- [es-toolkit vs lodash 迁移指南](https://es-toolkit.dev/migration/from-lodash)
- [es-toolkit 性能基准](https://es-toolkit.dev/benchmarks)
- [项目 web/CLAUDE.md §优先使用已安装的库](../../packages/web/CLAUDE.md)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
