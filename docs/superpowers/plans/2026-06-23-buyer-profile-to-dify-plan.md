# 买家画像 → Dify 上下文集成 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 登录用户的买家画像在聊天时自动注入 Dify `inputs.buyer_profile` 纯文本上下文

**Architecture:** 后端 `/permissions/me` 加 `account_id` → 前端 zustand 存 `accountId` → `chat-utils` 传 `inputs.buyer_key` → `memory-integration` Pre-LLM 取画像拼文本 → Dify

**Tech Stack:** FastAPI + zustand + TanStack Query + Dify Chatflow

---

### Task 1: 后端 `/permissions/me` 加 account_id

**Files:**
- Modify: `packages/service/src/permissions/router.py:137-142`
- Test: `tests/permissions/test_permissions_router.py` (可能不存在, 需要新建或追加)

**Details:**

当前 `my_permissions` 端点返回 `{ role, allowed, pages }`。在响应中加 `account_id` 字段。`CurrentUser` 已有 `account_id` 属性（由 `resolve_user` 注入）。

- [ ] **Step 1: 写测试**

在 `tests/permissions/` 下找现有测试文件。

```bash
ls tests/permissions/
```

如果存在 test file，加一个 case:
```python
def test_my_permissions_returns_account_id(client, mock_resolve_user):
    """/permissions/me 返回 account_id"""
    resp = client.get("/api/permissions/me")
    assert resp.status_code == 200
    body = resp.json()
    assert "account_id" in body
    assert isinstance(body["account_id"], int)
```

如果不存在，直接在 `tests/buyer_profile/test_router.py` 风格一致的 mock 测试 (模式 1)。

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/permissions/ -v -x
```

Expected: FAIL — account_id not in response

- [ ] **Step 3: 修改路由**

```python
def my_permissions(user: CurrentUser = Depends(resolve_user)):
    return {
        "account_id": user.account_id,  # ← 新增
        "role": user.role,
        "allowed": get_my_permissions(user.role),
        "pages": get_all_page_metadata_sync(),
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/permissions/ -v -x
```

Expected: PASS

- [ ] **Step 5: 更新前端类型**

**File:** `packages/web/lib/api/permissions.ts`

```typescript
export const getMyPermissions = (headers?: Record<string, string>) =>
  apiFetch<{
    role: string;
    account_id: number;   // ← 新增
    allowed: string[];
    pages: any[];
  }>("/api/permissions/me", { headers });
```

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/permissions/router.py tests/permissions/ packages/web/lib/api/permissions.ts
git commit -m "feat: /permissions/me 加 account_id 字段"
```

---

### Task 2: 后端 GET /api/buyer-profiles/my-profile

**Files:**
- Add: `packages/service/src/buyer_profile/router.py` (追加新路由)
- Test: `tests/buyer_profile/test_router.py`

**Details:**

新端点返回当前账号的买家画像。`buyer_key = str(account_id)`，不存在时自动创建空画像。

- [ ] **Step 1: 写测试 (模式 1, mock ProfileService)**

在 `tests/buyer_profile/test_router.py` 末尾追加:

```python
def test_get_my_profile_creates_if_missing(client, mock_ProfileService):
    """画像不存在时自动创建并返回"""
    mock_ProfileService.get_profile.return_value = None
    mock_ProfileService.create_or_get_profile.return_value = {
        "id": "uuid-1",
        "account_id": 1,
        "buyer_key": "1",
        "profile_data": {},
    }
    mock_ProfileService.get_profile.side_effect = [
        None,
        {"id": "uuid-1", "account_id": 1, "buyer_key": "1", "profile_data": {}},
    ]

    resp = client.get("/api/buyer-profiles/my-profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["buyer_key"] == "1"
    assert mock_ProfileService.create_or_get_profile.called


def test_get_my_profile_exists(client, mock_ProfileService):
    """画像已存在时直接返回"""
    mock_ProfileService.get_profile.return_value = {
        "id": "uuid-1",
        "account_id": 1,
        "buyer_key": "1",
        "profile_data": {"equipment_type": {"value": "电机", "confidence": "high"}},
    }
    resp = client.get("/api/buyer-profiles/my-profile")
    assert resp.status_code == 200
    assert resp.json()["profile_data"]["equipment_type"]["value"] == "电机"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/buyer_profile/test_router.py -v -x -k "my_profile"
```

Expected: FAIL — 404 not found

- [ ] **Step 3: 实现端点**

在 `packages/service/src/buyer_profile/router.py` 的 `# ── 买家画像 CRUD ──` 节, 放在 `/fields` 之后 `/` 之前:

```python
@router.get(
    "/my-profile",
    response_model=BuyerProfileResponse,
    summary="当前账号画像",
    description="返回当前登录账号的买家画像, 不存在则自动创建空画像.",
)
async def get_my_profile(
    current_user: CurrentUser = Depends(require_account),
) -> dict:
    aid = current_user.account_id
    assert aid is not None
    buyer_key = str(aid)
    profile = ProfileService.get_profile(aid, buyer_key)
    if not profile:
        ProfileService.create_or_get_profile(aid, buyer_key)
        profile = ProfileService.get_profile(aid, buyer_key)
        if not profile:
            raise HTTPException(status_code=500, detail="failed to create profile")
    return profile
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/buyer_profile/test_router.py -v -x -k "my_profile"
```

Expected: PASS

- [ ] **Step 5: 运行全部 buyer_profile 测试确认无回归**

```bash
uv run pytest tests/buyer_profile/ -v
```

Expected: 74 passed

- [ ] **Step 6: Commit**

```bash
git add packages/service/src/buyer_profile/router.py tests/buyer_profile/test_router.py
git commit -m "feat: GET /api/buyer-profiles/my-profile 端点"
```

---

### Task 3: 前端 zustand auth-store

**Files:**
- Create: `packages/web/lib/store/auth-store.ts`
- Test: `packages/web/lib/store/auth-store.test.ts`

- [ ] **Step 1: 写测试**

```typescript
import { describe, expect, it } from "vitest";
import { useAuthStore } from "./auth-store";

describe("auth-store", () => {
  it("默认 accountId 为 null", () => {
    const { accountId } = useAuthStore.getState();
    expect(accountId).toBeNull();
  });

  it("setAccountId 写入后能读取", () => {
    useAuthStore.getState().setAccountId(42);
    expect(useAuthStore.getState().accountId).toBe(42);
  });

  it("重复 setAccountId 覆盖旧值", () => {
    useAuthStore.getState().setAccountId(1);
    useAuthStore.getState().setAccountId(99);
    expect(useAuthStore.getState().accountId).toBe(99);
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
bun run test -- auth-store.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 3: 创建 store**

```typescript
// (2026-06-23) 登录用户 auth 状态 (zustand)
// 存储 account_id 供聊天等场景使用
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  accountId: number | null;
  setAccountId: (id: number) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accountId: null,
      setAccountId: (accountId) => set({ accountId }),
    }),
    { name: "rag.auth-store.v1" },
  ),
);
```

- [ ] **Step 4: 运行测试确认通过**

```bash
bun run test -- auth-store.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/store/auth-store.ts packages/web/lib/store/auth-store.test.ts
git commit -m "feat: zustand auth-store 存 accountId"
```

---

### Task 4: 前端 use-permissions store 写入 accountId

**Files:**
- Modify: `packages/web/lib/hooks/use-permissions.ts`

- [ ] **Step 1: 在 store 接口加 accountId 字段**

在 `PermissionsStore` interface 加 `accountId: number | null`:

```typescript
interface PermissionsStore extends MyPermissions {
  accountId: number | null;  // ← 新增
  loaded: boolean;
  fetch: () => Promise<void>;
}
```

- [ ] **Step 2: fetch 成功后写入**

```typescript
fetch: async () => {
  try {
    const { getMyPermissions } = await import("@/lib/api/permissions");
    const data = await getMyPermissions();
    set({
      accountId: data.account_id,  // ← 新增
      allowed: data.allowed,
      loaded: true,
      pages: data.pages,
      role: data.role,
    });
  } catch {
    set({ loaded: true });
  }
},
```

- [ ] **Step 3: 同步更新 usePermissionsStore 初始值**

```typescript
export const usePermissionsStore = create<PermissionsStore>((set) => ({
  accountId: null,  // ← 新增初始值
  allowed: [],
  fetch: async () => { ... },
  loaded: false,
  pages: [],
  role: "user",
}));
```

- [ ] **Step 4: 运行 lint + typecheck**

```bash
cd packages/web && bun run lint && bun run typecheck
```

Expected: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/hooks/use-permissions.ts
git commit -m "feat: use-permissions store 同步存 accountId"
```

---

### Task 5: 前端 chat-utils 传 buyer_key

**Files:**
- Modify: `packages/web/lib/chat/chat-utils.ts`
- Modify: `packages/web/lib/chat/chat-utils.test.ts` (如有)

- [ ] **Step 1: 在 sendRequest 里注入 buyer_key**

```typescript
import { useAuthStore } from "@/lib/store/auth-store";

export const sendRequest = async ({ conv, text, files }: SendRequestParams) => {
  const accountId = useAuthStore.getState().accountId;
  return apiSendMessage({
    conversationId: conv?.difyConversationId,
    files: streamFiles,
    inputs: { buyer_key: accountId ? String(accountId) : "" },
    query: text,
    user: conv?.id ?? "",
  });
};
```

- [ ] **Step 2: 更新测试**

找到 `chat-utils.test.ts` 中对 `sendRequest` 的测试，检查 `inputs` 断言加上 `buyer_key`。

如果现有测试 mock `useAuthStore`:
```typescript
vi.mock("@/lib/store/auth-store", () => ({
  useAuthStore: { getState: () => ({ accountId: 1 }) },
}));
```

- [ ] **Step 3: 运行测试**

```bash
bun run test -- chat-utils.test.ts
```

Expected: 现有 test 全部通过

- [ ] **Step 4: lint + typecheck**

```bash
bun run lint && bun run typecheck
```

Expected: 0 error

- [ ] **Step 5: Commit**

```bash
git add packages/web/lib/chat/chat-utils.ts packages/web/lib/chat/chat-utils.test.ts
git commit -m "feat: 聊天 inputs 带 buyer_key (accountId)"
```

---

### Task 6: 前端 memory-integration 取画像注入 Dify

**Files:**
- Modify: `packages/web/lib/chat/memory-integration.ts`
- Modify: `packages/web/lib/chat/memory-integration.test.ts`

- [ ] **Step 1: 新增 fetchBuyerProfile + formatProfile 函数**

在 `memory-integration.ts` 的 `addMemory` 函数附近添加:

```typescript
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const fetchBuyerProfile = async (buyerKey?: string): Promise<Record<string, { value: unknown }> | null> => {
  if (!buyerKey) return null;
  try {
    const headers = await serverAuthHeaders();
    const res = await fetch(`${BACKEND_URL}/api/buyer-profiles/my-profile`, { headers });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.profile_data ?? null;
  } catch {
    return null; // 降级: 拿不到画像不影响聊天
  }
};

const formatProfile = (profile: Record<string, { value: unknown }> | null): string => {
  if (!profile || Object.keys(profile).length === 0) return "";
  const pairs = Object.entries(profile)
    .filter(([, v]) => v?.value != null && v?.value !== "")
    .map(([k, v]) => `${k}=${v.value}`);
  return pairs.length ? `买家信息: ${pairs.join(", ")}` : "";
};
```

- [ ] **Step 2: 修改 withMemoryHooks 装饰器**

将 Pre-LLM 从 `searchMemory` 改为 `Promise.all([searchMemory, fetchBuyerProfile])`:

```typescript
export const withMemoryHooks = (inner: ChatProvider): ChatProvider => ({
  async *sendMessage(req: SendMessageRequest, signal: AbortSignal): AsyncIterable<ChatEvent> {
    // 1. Pre-LLM: 搜记忆 + 取画像 (并行, 任一失败降级)
    const [memoryContext, profileData] = await Promise.all([
      searchMemory(req.query),
      fetchBuyerProfile(req.inputs.buyer_key as string | undefined),
    ]);
    const profileText = formatProfile(profileData);
    const enhancedReq: SendMessageRequest = {
      ...req,
      inputs: { ...req.inputs, [MEMORY_CONTEXT_KEY]: memoryContext, buyer_profile: profileText },
    };

    // 2. 流中累积对话 (不变)
    const turns: MemoryTurn[] = [{ content: req.query, role: "user" }];
    for await (const ev of inner.sendMessage(enhancedReq, signal)) {
      if (ev.type === "message") appendAssistantDelta(turns, ev.delta);
      yield ev;
    }

    // 3. Post-LLM (不变)
    const hasAssistant = turns.some((turn) => turn.role === "assistant");
    if (hasAssistant) {
      void addMemory(turns, req.conversationId, req.inputs.buyer_key as string | undefined);
    }
  },
});
```

- [ ] **Step 3: 更新测试**

在 `memory-integration.test.ts` 追加:

```typescript
describe("buyer profile injection", () => {
  it("buyer_key 存在时 fetch 画像并注入 inputs.buyer_profile", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        profile_data: {
          equipment_type: { value: "电机", confidence: "high" },
          budget: { value: "5000", confidence: "medium" },
        },
      }),
    });
    const events: ChatEvent[] = [];
    for await (const ev of provider.sendMessage(
      { ...REQ, inputs: { buyer_key: "1" } },
      new AbortController().signal,
    )) {
      events.push(ev);
    }
    // 内层 provider 应收到 enhancedReq.inputs.buyer_profile 非空
    const received = (inner.provider as FakeProvider).receivedReq;
    const profile = received?.inputs?.buyer_profile as string;
    expect(profile).toContain("电机");
    expect(profile).toContain("5000");
    expect(profile).toContain("买家信息");
  });

  it("buyer_key 为空时不调 fetch, buyer_profile 为空", async () => {
    const events: ChatEvent[] = [];
    for await (const ev of provider.sendMessage(
      { ...REQ, inputs: {} },
      new AbortController().signal,
    )) {
      events.push(ev);
    }
    const received = (inner.provider as FakeProvider).receivedReq;
    expect(received?.inputs?.buyer_profile).toBe("");
  });

  it("fetch 失败时 buyer_profile 为空字符串 (降级)", async () => {
    fetchMock.mockRejectedValueOnce(new Error("network error"));
    const events: ChatEvent[] = [];
    for await (const ev of provider.sendMessage(
      { ...REQ, inputs: { buyer_key: "1" } },
      new AbortController().signal,
    )) {
      events.push(ev);
    }
    const received = (inner.provider as FakeProvider).receivedReq;
    expect(received?.inputs?.buyer_profile).toBe("");
  });
});
```

- [ ] **Step 4: 运行测试**

```bash
bun run test -- memory-integration.test.ts
```

Expected: ALL PASS

- [ ] **Step 5: lint + typecheck**

```bash
bun run lint && bun run typecheck
```

Expected: 0 error

- [ ] **Step 6: Commit**

```bash
git add packages/web/lib/chat/memory-integration.ts packages/web/lib/chat/memory-integration.test.ts
git commit -m "feat: 聊天 Pre-LLM 取买家画像注入 Dify inputs.buyer_profile"
```

---

### Task 7: 全量验证

- [ ] **Step 1: 跑全量后端测试**

```bash
cd packages/service && uv run pytest tests/buyer_profile/ -v
```

Expected: 74 passed (含新加 2 个 my-profile 测试)

- [ ] **Step 2: 跑全量前端 vitest**

```bash
bun run test
```

Expected: 0 new failures

- [ ] **Step 3: 跑 lint + typecheck**

```bash
bun run lint && bun run typecheck
```

Expected: 0 error

- [ ] **Step 4: 端到端验证 (手动)**

重启后端 + 前端:

```bash
# Term 1: 后端
cd packages/service && uv run python main.py

# Term 2: 前端
cd packages/web && bun run dev
```

测试步骤:
1. 登录系统 (确保 account_id 非空)
2. 打开聊天页
3. 发一条消息
4. 检查服务端日志: `POST /api/buyer-profiles/my-profile` 被调用
5. 检查 Dify 请求: `inputs.buyer_profile` 包含 "买家信息: ..."
6. 检查 memory add: 带 `buyer_key` 参数

- [ ] **Step 5: Commit (如无额外修复)**

```bash
git add -A && git commit -m "chore: buyer-profile-to-dify 集成完成"
```
