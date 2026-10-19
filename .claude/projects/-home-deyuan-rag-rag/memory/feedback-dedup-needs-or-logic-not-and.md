---
name: feedback-dedup-needs-or-logic-not-and
description: "Dedup 关系时用 \"至少一端新\" (OR), 不用 \"两端都新\" (AND); 否则丢 \"新型号→已存在 value\" 这种合法 rel"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2b43cdde-9008-4f4a-8f71-df2d2a112bb2
---

# Dedup 关系: OR 不用 AND

**Bug** (用户在真跑 Neo4j import 暴露):
- 1LE0001-1AA4-21-AA4 的 winding_protection = "A"
- "A" 已在 Neo4j (从其他系列的 poles 共享)
- 修复前 dedup: `r.srcName in new_node_names AND r.tgtName in new_node_names` (AND 逻辑)
  → (1LE0001→A) 两端不全在 new, **被丢弃** ❌
  → (A→绕组保护) 同上, 被丢弃 ❌
- 结果: 1LE0001 缺 4 个参数值 边 (3×A + 1×"NONE" 的 "A")

**正确逻辑** (OR):
- 端点在 known space (new ∪ existing) 即合法
- 至少一端 new 的 rel 都该保留 (例: 新型号→已存在的共享 value, 新参数→已存在的共享 value)
- 两端都 existing 的 rel 不必写 (apoc.merge 幂等, 写了也安全但浪费)

```python
# 错误 (AND)
new_rels = [r for r in rels if r.src in new_names and r.tgt in new_names]

# 正确 (OR) - 但要校验端点都 known
known_names = new_names | existing
new_rels = [r for r in rels if r.src in known_names and r.tgt in known_names]
```

**关键教训**:
- 共享资源 (相同 raw key 的 value 跨系列复用) 在 dedup 场景下要用 OR 逻辑
- 端点 known 检查很关键, 否则 dangling 端点的 rel 进 Neo4j 会失败
- "两端都 new" 看起来更"严格"和"安全", 实际是 over-filtering

**How to apply**:
- 写 dedup 过滤 rel 时, 先问: "一端 new + 一端 existing 的 rel 是不是想要的?"
  - 是 → 用 OR (或上面的 known space 模式)
  - 否 → 用 AND, 但说明为什么
- 测试要覆盖 "一端 new + 一端 existing" 的场景, 跟覆盖 "两端都 existing" 一样重要
- 共享节点 (e.g. 共享 enum value "A") 跨多个 owner 时, owner 之间是 N:N 关系, 共享节点是 N 的目标

**Related**: [[feedback-tdd-test-real-behavior-not-just-no-crash]] (TDD 漏了"一端 new 一端 existing" 的 rel 保留测试)
