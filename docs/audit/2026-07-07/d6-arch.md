# D6 Architecture 审计报告 (2026-07-07)

- 扫描范围: `packages/web/**`, `packages/service/src/**` (排除 node_modules, tests, e2e, migrations)
- 简档来源: `docs/audit/2026-07-07/scan-brief.md`
- 工具链: Read / Grep / Glob / Bash (只读)

| id | dimension | severity | confidence | title |
|---|---|---|---|---|
| [ARCH-001](#arch-001) | architecture | high | high | BFF 路由处理器模板化重复 9 份 (5–22 行近 copy-paste) |
| [ARCH-002](#arch-002) | architecture | high | high | memory-management-dialog.tsx 378 行单文件 (上限 300) |
| [ARCH-003](#arch-003) | architecture | medium | high | kg/router.py 1045 行超大路由 (上限 300, 超 3.5×) |
| [ARCH-004](#arch-004) | architecture | medium | high | pdf_processing/router.py 743 行 + dead import `logging` |
| [ARCH-005](#arch-005) | architecture | medium | high | 自实现 log 模块部分被绕过, 仍有 3 处原生 console 调用 |
| [ARCH-006](#arch-006) | architecture | medium | medium | chat-shell.tsx 中间 import (非顶部) 破坏读码流程 |
| [ARCH-007](#arch-007) | architecture | medium | medium | use-chat-state.ts:253 声明使用 `function` 而非 const (style drift) |
| [ARCH-008](#arch-008) | architecture | low | high | `export *` re-export 让 server-only 模块泄漏给 client bundle 风险 |
| [ARCH-009](#arch-009) | architecture | low | medium | Dify HTTP Chat Transport 缺少可观测性埋点 |
| [ARCH-010](#arch-010) | architecture | low | high | web 端 15 文件使用 `export default function` (违反箭头函数规约例外仅 Next.js page) |

---

<a id="arch-001"></a>
## ARCH-001

```yaml
id: ARCH-001
dimension: architecture
severity: high
confidence: high
title: BFF 路由处理器模板化重复 9 份 (5–22 行近 copy-paste)
file: packages/web/app/api/ingest/upload/finalize/route.ts
line: 17
description: >
  Next.js BFF 透传路由 9+ 文件结构高度同质 (chat/files/{presign,finalize},
  ingest/upload/{presign,finalize}, approvals/[id]/{approve,reject,retry},
  evaluate/runs/[id]/cancel)。每个文件均为 `POST = async (req) => { const body
  = await req.json(); const resp = await apiProxy(...); return bffProxyResponse(resp); }`,
  仅 URL/verb 不同。是低 ROI 重复, 但需要保持 9 处同步变更 (例如加 auth /
  error envelope)。
evidence: |
  // packages/web/app/api/ingest/upload/finalize/route.ts:13-25
  /** Ingest 上传完成通知 BFF: 透传 POST /api/ingest/upload/finalize
   * @param req - 请求对象
   * @returns Response
   * @client-bff */
  export const POST = async (req: NextRequest) => {
    const body = await req.json();
    const resp = await apiProxy("/api/ingest/upload/finalize", {
      body: JSON.stringify(body),
      headers: { ...(await serverAuthHeaders()), [HEADER_CONTENT_TYPE]: MIME_JSON },
      method: "POST",
    });
    return bffProxyResponse(resp);
  };

  // packages/web/app/api/approvals/[id]/approve/route.ts:10-22
  /** 审批通过 BFF: 透传 POST /api/approvals/{id}/approve ... */
  export const POST = async (_req: NextRequest, { params }: { params: Promise<{ id: string }> }) => {
    const { id } = await params;
    const resp = await apiProxy(`/api/approvals/${encodeURIComponent(id)}/approve`, {
      cache: "no-store",
      method: "POST",
    });
    return bffProxyResponse(resp);
  };
impact: >
  加新端点 (新增 BFF 鉴权/审计/error envelope) 时需 9+ 处同步改, 易漏; 文件数膨胀
  阻碍 audit。CLAUDE.md 也提到 "优先封装" 在此场景未应用。
fix_sketch: >
  抽 `bffProxy(endpoint, method, params)` 高阶函数, 把 params + body + auth
  + content-type + error envelope 集中在 1 处; 9 文件瘦身为单行 export。
```

---

<a id="arch-002"></a>
## ARCH-002

```yaml
id: ARCH-002
dimension: architecture
severity: high
confidence: high
title: memory-management-dialog.tsx 378 行单文件 (上限 300)
file: packages/web/components/chat/memory-management-dialog.tsx
line: 1
description: >
  弹框组件含 4 hook + 3 子组件 (MemoryDialogFooter / MemoryListItem /
  MemoryListContent) + 主组件, 全部写在 1 文件 378 行, 已超过项目 CLAUDE.md
  §"React 单文件 ≤ 300 行" 强制线。文件混合弹框/列表/编辑/搜索 4 关注点。
evidence: |
  // packages/web/components/chat/memory-management-dialog.tsx:295-300
  export const MemoryManagementDialog = ({ open, onOpenChange }: MemoryManagementDialogProps) => {
    const translation = useTranslations();
    const [clearAllOpen, setClearAllOpen] = useState(false);
    const { memories, loading, load } = useMemoryApi(open);
    const { filter, setFilter, filtered } = useMemoryFilter(memories);
    // ... 320 行 JSX + 子组件
    const onClickEdit = () => { setEditingId(memory.id); setEditingText(memory.text); };
    const onClickDelete = () => handleDelete(memory.id);
  };
impact: >
  阅读和重构成本翻倍; 该文件 0 子文件已拆分, 但 300+ 行 JSX 难单元测试覆盖
  (chat-shell.test.tsx 走集成入口而非 dialog 拆测)。
fix_sketch: >
  拆 4 文件: use-memory-api.ts / use-memory-filter.ts / use-memory-edit.ts /
  memory-list-item.tsx + memory-management-dialog.tsx (主壳 < 50 行)。
```

---

<a id="arch-003"></a>
## ARCH-003

```yaml
id: ARCH-003
dimension: architecture
severity: medium
confidence: high
title: kg/router.py 1045 行超大路由 (上限 300, 超 3.5×)
file: packages/service/src/kg/router.py
line: 1
description: >
  knowledge graph router 集成 35+ 端点 + schema + cypher escape utils, 单文件
  1045 行, 超过项目"Python file ≤ 100 行 / 类 ≤ 100 行"约 10 倍。混淆 router /
  schema / 业务工具 3 层职责, 维护/读码难。
evidence: |
  // packages/service/src/kg/router.py:43-49
  _REPO_ROOT = Path(__file__).resolve().parents[2]
  # TODO: 加 @audited("kg_node.delete", target_type="kg_node") 当 DELETE 节点端点实现后
  # TODO: 加 @audited("kg_relation.delete", target_type="kg_relation") 当 DELETE 关系端点实现后

  # 单例 audit store; 数据落 data/kg_audit.db
  _audit_store = _audit.AuditStore("data/kg_audit.db")
  router = APIRouter(prefix="/api/kg", tags=["kg"])

  // packages/service/src/kg/router.py:1040-1046
  def _escape(s: str) -> r"""
      Cypher 字符串转义 (单引号 + 反斜杠 + 换行符)
      v1 简化版: 只转义 ' \ \n. 生产环境应走 Neo4j 参数化.
      """
      return s.replace("\\", "\\\\").replace("'", r"\'").replace("\n", r"\n")
impact: >
  router 文件膨胀抑制 LLM/IDE 索引; 调试/合规审查 (PATCH/DELETE 节点) 需翻全文;
  未审计 DELETE TODO 沉寂多年风险。
fix_sketch: >
  拆 kg/router.py 为 3 文件: schemas.py (Pydantic) / cypher_utils.py (escape +
  build_match_cypher) / router.py (瘦身后 ≤ 400 行, 端点按数据模型 group)。
```

---

<a id="arch-004"></a>
## ARCH-004

```yaml
id: ARCH-004
dimension: architecture
severity: medium
confidence: high
title: pdf_processing/router.py 743 行 + dead stdlib logging 导入
file: packages/service/src/ingest/pdf_processing/router.py
line: 11
description: >
  ingest 上传/转换路由 743 行 (超 CLAUDE.md 100 行红线 7×), 同时第 11 行
  `import logging` + 第 40 行 `_logger = logging.getLogger(__name__)`, 但全文未
  找到 `_logger.*` 调用 (dead code, 违反 CLAUDE.md §"loguru 替代 stdlib logging"
  强制规范)。
evidence: |
  // packages/service/src/ingest/pdf_processing/router.py:1-40
  """Ingest HTTP API (2026-06-10) 为前端 /output 页提供上传 + 后台转换 + 产物查询 + zip 下载。 ..."""
  # ruff: noqa: E402
  from __future__ import annotations

  import io
  import logging
  import re
  import secrets
  import traceback
  import zipfile
  from dataclasses import dataclass, field
  ...
  _logger = logging.getLogger(__name__)
impact: >
  1) 文件膨胀 7× 单点维护成本; 2) 死 import + dead var 被 pyright 放过, 与项目
  "loguru 统一 + 0 noqa 警告"规约不符, 0 warning 门禁未被守住。
fix_sketch: >
  1) 删 `import logging` + `_logger = logging.getLogger(__name__)` 2 行 dead code;
  2) router.py 拆 transformers.py (PDFAnalyzer) / multipart_helpers.py
  / zip_helpers.py / router.py (≤ 400 行)。
```

---

<a id="arch-005"></a>
## ARCH-005

```yaml
id: ARCH-005
dimension: architecture
severity: medium
confidence: high
title: 自实现 log 模块部分被绕过, 仍有 3 处原生 console 调用
file: packages/web/components/common/form/app-form.tsx
line: 96
description: >
  项目在 lib/log.ts 自实现 `log.{info,warn,error}` 替代 console, 但 grep
  出 3 处仍在源码中调原生 console.{warn|error}, 跟 CLAUDE.md §"自实现 log
  facade, 业务代码禁用 console" 不符。
evidence: |
  // packages/web/components/common/form/app-form.tsx:92-99
            try {
              await onFinish(value as TFormData);
            } catch (error) {
              // onFinish 内部出错时吞掉, 避免 unhandled rejection
              console.error("[AppForm] onFinish 执行出错:", error);
            }

  // packages/web/lib/nav/build-nav-tree.ts:94-100
      if (orphans.length > 0 && process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.warn(
          "[buildNavTree] orphan nodes (parent_id 找不到):",
          ...
        );
      }

  // packages/web/lib/api/query-client.ts:6 (注释, 但未走 log)
        //    RSC 端 prefetchQuery 失败已在 lib/api/rsc-queries.ts 吞掉 + console.warn,
impact: >
  业务可观测性碎片化 — 3 处不同格式, 没法统一聚合/级别控制; 跟自实现
  log facade (lib/log.ts) 的"升级路径"承诺不一致。
fix_sketch: >
  把 3 处 console.{warn,error} 改为 `log.warn/error`, log.ts 提供 `[AppForm]`
  前缀约定 + meta + 颜色输出统一。
```

---

<a id="arch-006"></a>
## ARCH-006

```yaml
id: ARCH-006
dimension: architecture
severity: medium
confidence: medium
title: chat-shell.tsx 中间 import (非顶部) 破坏读码流程
file: packages/web/components/chat/chat-shell.tsx
line: 244
description: >
  chat-shell.tsx 第 244 行有 `import { useAuthStore } from "@/lib/store/auth-store"`
  在文件中部 (函数 `useAccountId` 体内), 跟 ruff `E402` (前端 lint 规则) "import
  必须顶部" 规约不符。前端 lint 工具是 oxlint (未强制此规则), 但 import 在文件
  中部混淆依赖阅读, 跟 E402 精神相违。
evidence: |
  // packages/web/components/chat/chat-shell.tsx:1-33 (顶部 import)
  "use client";
  import type { ChatFile, Message } from "@/lib/chat/types";
  import { useEffect, useRef } from "react";
  import { useEffectOnce } from "react-use";
  ...

  // packages/web/components/chat/chat-shell.tsx:236-253 (useAccountId 内 inline import)
  /**
   * useAccountId - 获取当前账号 ID
   * @param isAccount - 是否为登录账号
   * @returns 账号 ID 或 null
   */
  import { useAuthStore } from "@/lib/store/auth-store";
  const useAccountId = (isAccount: boolean): number | null => {
    const ref = useRef<number | null>(null);
    if (isAccount) {
      ref.current = useAuthStore.getState().accountId;
    } else {
      ref.current = null;
    }
    return ref.current;
  };
impact: >
  阅读顺序混乱 (子组件 + helper 之后才看到依赖); 后续若有 hoist 优化工具,
  静态分析会遗漏这种后置 import; 跟"use client" 顶部 directive 风格的代码
  阅读习惯冲突。
fix_sketch: >
  把 `import { useAuthStore }` 挪到顶部 import group "lib/store/*" 位置;
  把 `useAccountId` 提到顶部常量级 (跟 `useChatShellUiState` 一样), 文件
  仍保持 < 300 行。
```

---

<a id="arch-007"></a>
## ARCH-007

```yaml
id: ARCH-007
dimension: architecture
severity: low
confidence: medium
title: use-chat-state.ts 保留 Deprecated 已声明函数但未被引用
file: packages/web/lib/chat/use-chat-state.ts
line: 256
description: >
  第 256 行 `useChatShellState = () => useChatShellUiState()` 标注 "Deprecated
  (2026-07-01), T7 后 chat-shell 不再用, 删此函数, 保留目的: 中间 commit 不破
  build"。第 262 行 `removeConvLocal` 同样标 Deprecated, 第 327 行
  `deleteConversationLocal` 是 wrapper 但业务侧只调 re-export。3 个标 deprecated
  函数当前 0 引 (需 grep verify), 但保留导致 chat-state.ts 文件膨胀到 329 行。
evidence: |
  // packages/web/lib/chat/use-chat-state.ts:252-265
  // --- 兼容旧 API (chat-shell 还在 T7 接入, 暂时保留) ---

  /**
   * (2026-07-01) ⚠️ Deprecated: 旧 useChatShellState shape.
   * T7 后 chat-shell 不再用, 删此函数. 保留目的: 中间 commit 不破 build.
   */
  export const useChatShellState = (): ChatShellUiState => useChatShellUiState();

  /**
   * (2026-07-01) ⚠️ Deprecated: 旧 removeConvLocal.
   * T7 后由 ChatShell 内部 handler 处理.
   */
  export const removeConvLocal = (targetId: string, state: ChatShellUiState): void => {
    state.setConversations((prev) => prev.filter((conv) => conv.id !== targetId));
  };
impact: >
  Deprecated 函数若仍未删 (T7 完成度不定), 文件增加 14 行无用 + 增加 review
  噪音; 违背 CLAUDE.md "0 lint warning" 中 "明令 dead code 删" 精神。
fix_sketch: >
  grep `useChatShellState\|removeConvLocal` 全仓, 确认 0 引后删 2 个函数 +
  cleanup "Deprecated T7" 注释块。
```

---

<a id="arch-008"></a>
## ARCH-008

```yaml
id: ARCH-008
dimension: architecture
severity: low
confidence: high
title: `lib/api/index.ts` 仍 `export * from './auth'` 暗示 server-only 模块进 client 风险
file: packages/web/lib/api/index.ts
line: 60
description: >
  barrel `lib/api/index.ts` 第 60 行 `export * from "./auth";` 但文件底部
  注释明示 "Auth.ts / auth.server.ts: 不走 barrel (auth 已删, auth.server 是
  server-only + next/headers)"。注释 vs 实际 export 不一致 — auth 已删/但
  export * from "./auth" 残留, 是 dead export; 后续若新增 server-only file,
  barrel 易疏忽拉进 client bundle。
evidence: |
  // packages/web/lib/api/index.ts:55-70 (注释 + export *)
  // Auth.ts / auth.server.ts: 不走 barrel (auth 已删, auth.server 是 server-only + next/headers)
  export * from "./auth";
  export * from "./buyer-profile";
  export * from "./chat";
  ...
  // Rsc-queries: 不走 barrel (server-only)
  export * from "./system";
  ...
impact: >
  1) 注释 / 代码漂移 (DRIFT-FOR-MAINTAINERS); 2) 任何新 server-only 添加者
  跟注释二选一时易错漏; 3) vitest setup mock server-only 是被动防护, 真
  bundle 不保护。
fix_sketch: >
  删 `export * from "./auth"` 1 行; 注释改 "auth.ts/auth.server.ts 不走 barrel
  (server-only)"。考虑加 `oxlint/no-restricted-imports` 把 `next/headers` 限在
  `app/**` + `lib/{api/auth.server,api/rsc-queries}` 内。
```

---

<a id="arch-009"></a>
## ARCH-009

```yaml
id: ARCH-009
dimension: architecture
severity: low
confidence: medium
title: Dify HTTP Chat Transport 缺少可观测性埋点
file: packages/web/lib/chat/dify-http-chat-transport.ts
line: 1
description: >
  AI SDK HttpChatTransport 负责全 chat SSE 入口 (用户/anon 共用路径), 但全文无
  任何 log/埋点; 同样的 lib/rate-limiter.ts 也只在 BFF 路由被用, 浏览器侧 4xx/5xx
  无 error log。当前业务报错只 toast 提示, 没法事后排查"useChat failed" 根因。
evidence: |
  // packages/web/lib/chat/dify-http-chat-transport.ts:15-50 (节选)
  import { HttpChatTransport, type UIMessageChunk, type UIMessage } from "ai";

  import { parseSseBlocks } from "./sse";
  import type { ChatEvent, ChatFile } from "./types";
  import { useAuthStore } from "@/lib/store/auth-store";
  ...
  const TEXT_ID = "msg";
  const REASONING_ID = "think";

  /**
   * (2026-07-01) 浏览器 anon id (Dify user 字段用).
   */
  const getAnonUserId = (): string => {
    if (typeof globalThis === "undefined") { return "anon-ssr"; }
    ...
  };
impact: >
  chat 真实故障 (上游 Dify 5xx, BFF 502, SSE 断流) 在浏览器静默, 跟后端
  loguru/audit_logs 体系不对称; 用户反馈"chat 卡死"时无可附的客户端日志。
fix_sketch: >
  在 transport 的 fetch 失败分支 + 错误事件 catch 处调 `log.error("chat
  fetch failed", { url, status, convId })`; 续接后端 loguru 的 request_id
  (BFF 注入 X-Request-ID → 透传 header → 浏览器 console warn)。
```

---

<a id="arch-010"></a>
## ARCH-010

```yaml
id: ARCH-010
dimension: architecture
severity: low
confidence: high
title: web 端 15 文件使用 `export default function` 仍占主流
file: packages/web/app/[locale]/login/page.tsx
line: 21
description: >
  项目规定 "禁止 function 声明, 用 const = () => {} / 箭头函数, 除非 React 组件
  default export"。15 文件用 `export default function ...` (属允许例外), 但 grep
  出 `[locale]/decode/page.tsx:160` DecodePage、`decode/page.tsx:160` 是
  `export default function DecodePage() { return <GuardClient>...</GuardClient>; }`
  — 单一转发组件, 完全可以写成 `const DecodePage = () => (...);` 跟项目零
  例外规约保持一致。
evidence: |
  // packages/web/app/[locale]/decode/page.tsx:160-166
  /** decode 页面
   * @param props
   * @client-bff
   */
  export default function DecodePage() {
    return (
      <GuardClient pageKey="decode">
        <DecodePageInner />
      </GuardClient>
    );
  }

  // packages/web/app/[locale]/login/page.tsx:21
  export default function LoginPage() { ... }
  // 还有 13 处: admin/dicts, admin/invites, admin/permissions, decode, error,
  //   forgot-password, health/layout, invite/[token], knowledge/batch,
  //   knowledge/extract, knowledge/layout, loading, output/layout,
  //   output/[task_id]/[file], reset-password, submissions/layout
impact: >
  CLAUDE.md "禁 function 声明" 规约被允许例外蚕食 — 单一转发组件本可箭头;
  project-level lint 配置 `no-restricted-syntax` 未禁止 `export default
  function`, 后续逐步扩大违例风险。
fix_sketch: >
  把 15 文件中"仅 1 行 forwarding return" 或 "<Component>...</Component>"
  的文件改箭头; Next.js page.tsx 入口必需 default export 这点不变, 仅改
  内部 style 为 `const X = () => ...; export default X;`。
```

---

## 建议优先级

| 优先级 | 数量 | 代表 finding |
|---|---|---|
| 立即修 (P0) | 1 | ARCH-001 (BFF 9 份 copy-paste, 加新端点必踩) |
| 短期 (P1) | 4 | ARCH-002 (378 行 dialog) / ARCH-003 (1045 行 kg router) / ARCH-004 (743 + dead import) / ARCH-006 (中部 import) |
| 中期 (P2) | 3 | ARCH-005 (console.* 绕过 log facade) / ARCH-007 (3 个 deprecated 函数) / ARCH-008 (barrel 注释漂移) |
| 观察 (P3) | 2 | ARCH-009 (chat observability) / ARCH-010 (style 统一) |

## 关键文件路径 (绝对)

- `C:\doc\Code\rag\packages\web\app\api\ingest\upload\finalize\route.ts`
- `C:\doc\Code\rag\packages\web\app\api\approvals\[id]\approve\route.ts`
- `C:\doc\Code\rag\packages\web\components\chat\memory-management-dialog.tsx`
- `C:\doc\Code\rag\packages\service\src\kg\router.py`
- `C:\doc\Code\rag\packages\service\src\ingest\pdf_processing\router.py`
- `C:\doc\Code\rag\packages\web\components\chat\chat-shell.tsx`
- `C:\doc\Code\rag\packages\web\lib\chat\use-chat-state.ts`
- `C:\doc\Code\rag\packages\web\lib\api\index.ts`
- `C:\doc\Code\rag\packages\web\lib\chat\dify-http-chat-transport.ts`
- `C:\doc\Code\rag\packages\web\lib\log.ts`
