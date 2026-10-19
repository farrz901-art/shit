---
name: feedback-multi-tenant-isolation-required
description: "多租户项目 (B2B 邀请制 / 多 user 共享 DB) 必须显式设计 user 隔离, 不依赖 SDK 内部默认行为"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cdd2021a-1a31-4669-81ff-496a2134f22b
---

凡是 B2B / 邀请制 / 多 user 共享数据库的项目, 数据访问层必须显式设计 user 隔离.
不能假设"SDK 自己会过滤"或"前端不会乱传".

**Why**: 2026-06-16 实现记忆管理时发现 mem0 self-host 的 `Memory.delete(memory_id)` /
`Memory.update(memory_id, data)` 不传 user_id, 只按 ID 操作 → **跨租户漏洞**:
用户 A 拿到用户 B 的 memory_id 就能删/改 B 的记忆. mem0 自己的 `get_all(filters=)` /
`delete_all(user_id=)` 是隔离的, 但 update/delete 不是. 这是我之前没调研就默认
"mem0 自己会处理隔离" 的坑.

**How to apply**:

1. **数据访问前先做隔离审计**: `grep -rn 'user_id' <sdk_module>` 看每个方法签名,
   找出"按 ID 操作但不接 user_id"的方法. 这些方法不能直接用.
2. **3 层防御** (按从外到内):
   - 路由层: `Depends(resolve_user)` 拿 CurrentUser (从 cookie/header, 不接受请求体)
   - service 层: 用 `_resolve_user_id(current)` 解析, 绝不接受 user_id 参数
   - SDK 层: 优先用带 user_id/filters 的方法; 不带的方法包一层 `_assert_owned` 守卫
3. **写显式跨用户回归测试** (3 个必备):
   - 用户 A 调 list → mock SDK 返了别人数据也只看到自己的
   - 用户 A 调 delete_all → 必须传 user_id=A 给 SDK
   - **类型安全测试**: 用 `inspect.signature` 验证 service 方法不接受 `user_id` / `target_user_id` 参数
     (防 refactor 误加 = 攻击者伪造身份)
4. **PermissionError 翻译 HTTP 403**: 跨用户访问跟 not-found 统一返 403, 不区分
   (防 ID 探测泄漏)
5. **写 commit message 时**: 单独强调 "with cross-user isolation" / "PermissionError → 403"
   让 reviewer 重点看这块

**反模式 (禁用)**:
- ❌ "mem0 应该会自己处理" (没调研就假设)
- ❌ service 方法接 `user_id: str` 参数 (攻击面)
- ❌ "前端不会乱传" (前端是 JS, 可改)
- ❌ 只测 happy path, 不测跨用户 (漏洞测试盲区)

**参考**:
- `packages/service/src/memory/service.py` `_assert_owned` (2026-06-16 范本)
- `tests/memory/test_service.py` 三个 `test_user_a_cannot_*` (2026-06-16 范本)
- spec: `docs/superpowers/specs/2026-06-16-long-term-memory-design.md` "关键安全发现" 段
