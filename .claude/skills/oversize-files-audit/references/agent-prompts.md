# Subagent Prompt Templates — oversize-files-audit v2

3 份 prompt，严格分语种。派发时把 `${FILE_COUNT}` / `${TOTAL_LINES}` / `${PY_COUNT}` / `${TS_COUNT}` / `${OUTPUT_DIR}` / `${FILE_LIST}` placeholder 替换成实际值。

**通用 frontmatter v2** (所有 3 份都加这一段):

```
你是 oversize-files-audit skill 的 subagent，只读扫描，不修任何业务代码。
项目根: c:/doc/Code/rag/
输出目录: ${OUTPUT_DIR} (必须写到 ${OUTPUT_DIR}/<你的文件名>.md)
文件清单 (从 .scan-cache.json 读): ${FILE_LIST}
文件总数: ${FILE_COUNT}, 总行数: ${TOTAL_LINES}

工具限制: 只读 (Read / Grep / Glob / Bash wc-l)，禁止 WebSearch / Write / Edit (但可以 Write 到输出文件)。
失败规则: agent 工具超限或挂掉 → 主线程会留 TODO 占位，你这边如果能跑就跑，跑不动就在文件顶部写 ## 失败原因 + TODO。

v2 启动步骤 (强制):
1. Read packages/web/package.json (确认 React/Next/zod/shadcn 等已装)
2. Read packages/web/components.json (确认 shadcn 组件已注册)  [A1 跳过]
3. Read packages/service/pyproject.toml (确认 Python 库已装)    [A2/A3 跳过]
4. Read 真文件后才写库替代段 + 第 7 段骨架伪代码

v2 输出格式: 6 段必填 + 第 7 段骨架伪代码 (可选，--no-pseudo 时跳过)。
```

---

## A1 Python agent 模板

**输出文件**: `${OUTPUT_DIR}/a1-python.md`

**库能力清单** (拆分时优先用) — 标"已装"必须引用 pyproject.toml 行号:
- `pydantic` (BaseModel / Field / validator) — 替 dataclass + 手动验证
- `dataclasses` (dataclass / field) — 替手写 __init__ + 大量 if isinstance
- `functools` (lru_cache / reduce / partial) — 替手写 memoize / 循环累计
- `itertools` (groupby / chain / starmap) — 替嵌套 for
- `pathlib` (Path / Path.read_text) — 替 os.path 字符串拼接 + if exists
- `pytest fixtures` (parametrize / fixture scope) — 替手写循环 setup

**v2 7 段输出格式** (每文件一节):

```markdown
### `<相对路径>` (N 行, M 个函数/类)

**1. 拆分点提议**:
- L1-72 `<干什么>` -> `<拆后文件名>.py` (pure function / class / module)
- L88-150 `<干什么>` -> `<拆后文件名>.py` (...)

**2. 纯函数/类化**: ✅ 可拆 (列出) / ❌ 不可拆 (原因)
**3. 库替代**: ✅ pydantic `<BaseModel>` 已装 (pyproject.toml:34) / ⚠️ 未装 (需 uv add pydantic) / ❌ 无
**4. 对象替 if**: ✅ L152-180 status validator -> `STATUS_VALIDATORS.get(s)` / ❌ 无
**5. 数组迭代替循环**: ✅ for 循环改 `next(filter(...))` / ❌ 无
**6. 预计减少**: N -> M (-X%)
**7. 骨架伪代码** (v2 新):
- `<filename>.py` (新文件):
```python
# imports: 只列需要的 import
from typing import Iterable

def function_name(arg1: str, arg2: int) -> bool:
    """函数签名 + docstring，**不写函数体**"""
```

**注意**: 7 段只骨架，不写实现逻辑。
```

**示例 (不要复制，自己读真文件)**:

```markdown
### packages/service/src/auth/handler.py (412 行, 8 函数)

**1. 拆分点提议**:
- L1-80 token 解析 + 验证 -> `token.py` (pure function `parse_token`)
- L88-160 用户权限检查 -> `permission.py` (class `PermissionChecker`)
- L170-280 路由 handler -> 拆 4 个 endpoint 文件
- L290-412 错误处理装饰器 -> `error_handler.py`

**2. 纯函数/类化**: ✅ parse_token / validate_scope 可拆 pure
**3. 库替代**: ✅ pydantic `TokenPayload` 已装 (pyproject.toml:34) 替手写 dict
**4. 对象替 if**: ✅ 8 个 `if status == ...` -> `STATUS_MAP[status]`
**5. 数组迭代替循环**: ❌ 循环里全是副作用, 不可替
**6. 预计减少**: 412 -> 260 (-37%)
**7. 骨架伪代码**:
- `auth/token.py`:
```python
from pydantic import BaseModel

class TokenPayload(BaseModel):
    user_id: str
    scope: list[str]
    exp: int

def parse_token(raw: str) -> TokenPayload:
    """解析 JWT token, 验证签名, 返回 pydantic model"""
```

- `auth/permission.py`:
```python
class PermissionChecker:
    def __init__(self, token: TokenPayload): ...
    def can_access(self, resource: str) -> bool: ...
```
```

**Anti-pattern 防御**:
- ❌ 不要建议拆 FastAPI 路由到不同文件，如果只是装饰器一行 — 不算拆分点
- ❌ 不要建议把测试 fixture 拆出去 (默认排除)
- ❌ 不要用 emoji，跟项目规范一致
- ❌ **v2 新**: 库替代段必须引 pyproject.toml 行号 ("已装 (pyproject.toml:34)")，不允许"应该有"
- ❌ **v2 新**: 第 7 段骨架伪代码不许写函数体，5+ 行表达式 = 重新跑

---

## A2 TS Page/Component agent 模板

**输出文件**: `${OUTPUT_DIR}/a2-ts-page.md`

**库能力清单** — 标"已装"必须引用 package.json / components.json 行号:
- `shadcn/ui` (`<Table>` `<Pagination>` `<Dialog>` `<Form>` `<Tabs>`) — 替手写
- `zod` (schema / infer) — 替手写 type guard
- `tanstack-query` (useQuery / useMutation) — 替手写 fetch + loading 状态
- `lucide-react` (图标) — 替 emoji
- `@/i18n/navigation` useRouter — 替 next/navigation

**路径范围**: `packages/web/app/` + `packages/web/components/`

**v2 7 段输出格式** (跟 A1 同结构，库替代那行换 shadcn 关键词):

```markdown
### `<相对路径>` (N 行, M 个组件)

**1. 拆分点提议**:
- L1-72 `<干什么>` -> `<拆后文件名>.tsx` (component / hook)
- L88-150 `<干什么>` -> `<拆后文件名>.tsx` (...)

**2. 纯函数/hook 化**: ✅ 可拆 (列出) / ❌ 不可拆 (原因)
**3. 库替代**: ✅ shadcn `<Table>` 已装 (components.json:75) / ⚠️ 未装 (需 npx shadcn@latest add table) / ❌ 无
**4. 对象替 if**: ✅ L152-260 action variant switch -> `actionMap[variant]` / ❌ 无
**5. 数组替循环**: ✅ for 循环改 `.map()` / ❌ 无
**6. 预计减少**: N -> M (-X%)
**7. 骨架伪代码** (v2 新):
- `<filename>.tsx` (新文件):
```tsx
// imports: 只列需要的 import
import { Table } from "@/components/ui/table";

export function ComponentName(props: {
  rows: T[];
  columns: Column<T>[];
}): JSX.Element;
```

**注意**: 7 段只骨架，不写组件实现。
```

**Anti-pattern 防御**:
- ❌ 不要建议拆 `'use client'` directive 行 — 那是 1 行，不算拆分点
- ❌ 不要建议把 i18n key 拆出去 (那是 A3 范围)
- ❌ 不要建议拆 RSC 加载逻辑 (`async` server component) — 那不是"膨胀"
- ❌ 不要建议改路由路径 (那是 BFF 规则, 见 [CLAUDE.md §重构规则](../../../CLAUDE.md))
- ❌ **v2 新**: 库替代段不许用"应该用 shadcn" — 必须 Read components.json 确认
- ❌ **v2 新**: 第 7 段不许写完整 JSX body，只签名 + import

---

## A3 TS Hook/Util agent 模板

**输出文件**: `${OUTPUT_DIR}/a3-ts-hook.md`

**库能力清单** — 标"已装"必须引用 package.json 行号:
- `react-use` (`useDebounce` / `useLocalStorage` / `useMount` / `useEvent` / `useUpdate`) — 替手写 hook
- `ahooks` (`useRequest` / `useBoolean` / `useToggle`) — 替手写状态机
- `es-toolkit` (`pick` / `omit` / `groupBy` / `chunk` / `partition` / `keyBy`) — 替手写 utils
- `zod` (schema / `z.infer`) — 替手写 type guard + 运行时校验
- `dayjs` — 替手写日期格式化
- `nuqs` (useQueryState) — 替手写 URL state 同步

**路径范围**: `packages/web/hooks/` + `packages/web/lib/` + `packages/web/i18n/`

**v2 7 段输出格式** (跟 A2 同结构，库替代那行换 react-use 关键词):

**Anti-pattern 防御**:
- ❌ 不要建议拆 i18n message catalog (那是 flat-key 强制规范)
- ❌ 不要建议改 zod schema 结构 (那是 schema 主人负责)
- ❌ 不要建议用 `lodash` — 项目零依赖，用 es-toolkit 替代
- ❌ 不要建议用 `moment` — 项目已弃用，用 dayjs
- ❌ **v2 新**: react-use / ahooks / es-toolkit 库替代必须先 Read package.json 确认 dependency 行号
- ❌ **v2 新**: 第 7 段只写 hook 签名 + import，不许写 useEffect/useState body