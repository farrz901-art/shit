# 买家画像 → Dify 上下文集成设计

**日期**: 2026-06-23
**状态**: 设计稿
**作者**: 设计对话沉淀

## 背景

买家画像已存入 `buyer_profiles.profile_data`，但聊天时 Dify 工作流完全不知道买家画像信息。
当前 `inputs` 只有 `memory_context`（来自 mem0），缺少买家结构化画像。

## 决策记录

| 决策 | 选择 |
|------|------|
| 买家标识 | 直接使用 `account_id`（登录用户即买家），不用 `buyer_key` |
| 画像存储 key | `buyer_profiles.buyer_key = String(account_id)` |
| 画像传给 Dify 的格式 | 纯文本摘要（类似 memory_context），不改 Dify 工作流 |
| 前端存 account_id | zustand `auth-store`，从 `/permissions/me` 写入 |
| 取画像时机 | Pre-LLM，在 `memory-integration.ts` 里跟 `searchMemory` 并行 |

## 改动清单

### 1. 后端: `/api/permissions/me` 加 account_id

**文件**: `packages/service/src/permissions/router.py`

```python
# 当前响应: { role, allowed[], pages[] }
# 改为:
{
  "role": "admin",
  "account_id": 1,        # ← 新增
  "allowed": ["chat", ...],
  "pages": [...]
}
```

影响：前端 `lib/api/permissions.ts` 类型同步更新。

### 2. 后端: 新建 `GET /api/buyer-profiles/my-profile`

**文件**: `packages/service/src/buyer_profile/router.py`

新端点，`require_account` 守卫，`CurrentUser.account_id` 做唯一标识。

```python
@router.get("/my-profile", ...)
async def get_my_profile(current_user = Depends(require_account)):
    aid = current_user.account_id
    profile = ProfileService.get_profile(aid, str(aid))
    if not profile:
        ProfileService.create_or_get_profile(aid, str(aid))
        profile = ProfileService.get_profile(aid, str(aid))
    return profile
```

- 买家不存在时自动创建（懒加载）
- `buyer_key = String(account_id)`，避免新增 buyer_key 概念

### 3. 前端: zustand auth-store

**新建** `packages/web/lib/store/auth-store.ts`

```typescript
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

**写入时机**: 页面/布局调用 `getPermissions` / `getMyPermissions` 后，把返回的 `account_id` 写入 store。

### 4. 前端: 聊天 inputs 带 buyer_key

**文件**: `packages/web/lib/chat/chat-utils.ts`

```typescript
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

### 5. 前端: Pre-LLM 取画像 → 拼文本 → 注入 inputs

**文件**: `packages/web/lib/chat/memory-integration.ts`

```typescript
export const withMemoryHooks = (inner: ChatProvider): ChatProvider => ({
  async *sendMessage(req, signal) {
    // 1. Pre-LLM: 搜记忆 + 取画像 (并行)
    const [memoryContext, profileData] = await Promise.all([
      searchMemory(req.query),
      fetchBuyerProfile(req.inputs.buyer_key as string | undefined),
    ]);

    // 2. 画像文本化
    const profileText = formatProfile(profileData);

    const enhancedReq = {
      ...req,
      inputs: {
        ...req.inputs,
        [MEMORY_CONTEXT_KEY]: memoryContext,
        buyer_profile: profileText,
      },
    };

    // 3. 流中累积对话 (不变)
    const turns: MemoryTurn[] = [{ content: req.query, role: "user" }];
    for await (const ev of inner.sendMessage(enhancedReq, signal)) {
      if (ev.type === "message") appendAssistantDelta(turns, ev.delta);
      yield ev;
    }

    // 4. Post-LLM: addMemory 带 buyer_key → 触发后端 try_extract
    if (hasAssistant) {
      void addMemory(turns, req.conversationId, req.inputs.buyer_key as string | undefined);
    }
  },
});
```

**新增辅助函数**:

```typescript
const fetchBuyerProfile = async (buyerKey?: string) => {
  if (!buyerKey) return null;
  try {
    const headers = await serverAuthHeaders();
    const res = await fetch(
      `${BACKEND_URL}/api/buyer-profiles/my-profile`,
      { headers },
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data?.profile_data ?? null;
  } catch {
    return null;  // 降级: 拿不到画像不影响聊天
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

输出示例:
```
"buyer_profile": "买家信息: equipment_type=电机, budget=5000, decision_stage=比价, country=尼日利亚"
```

### 6. Dify inputs 最终结构

```json
{
  "memory_context": "用户之前提到过...",
  "buyer_profile": "买家信息: equipment_type=电机, budget=5000, decision_stage=比价, country=尼日利亚",
  "buyer_key": "1"
}
```

Dify 工作流可以不改（纯文本靠 LLM 理解），也可以在需要的地方引用 `{{buyer_profile}}`。

## 降级策略

任一步失败都不影响聊天:

- zustand 没 `accountId` → 空 buyer_key → 跳过取画像
- 后端 my-profile 挂了 → `fetchBuyerProfile` 返 null → 空 buyer_profile
- 画像提取失败 → `try_extract` 静默 warning，不阻断对话
- Post-LLM addMemory 失败 → warning log，不阻断

## 测试

| 测试 | 模式 |
|------|------|
| zustand auth-store 读写 | vitest 单元测试 |
| memory-integration fetch + format | mock fetch, 验 inputs 含 buyer_profile |
| `/my-profile` 端点 | 后端模式 1 (mock) |
| `/permissions/me` 加 account_id | 后端模式 1 (mock) |
