---
name: feedback-cypher-label-n-unknown-on-some-neo4j
description: "Cypher 统计节点 label 用 labels(n)[0] 别用 label(n), 后者在某些 Neo4j 实例 (driver/server 协议错位) 报 Unknown function"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eec4f205-4669-4734-b77f-77c2e0b18e11
---

Cypher 统计节点 label 数量时, 用 `labels(n)[0] AS label, count(n) AS cnt` 别用 `label(n) AS label, count(n) AS cnt`.

症状:
- `curl /api/kg/stats` → 500
- uvicorn 日志: `neo4j.exceptions.GqlError: Unknown function 'label' (line 1, column 8)`
- 同样的 Cypher 在 Neo4j Browser (Neo4j 5.x community edition) 里手敲能跑通 → 怀疑 driver/server 协议错位
- 进一步验证: 同一实例 `MATCH (n) RETURN count(n)` 正常, `RETURN labels(n)[0]` 正常, 只有 `label(n)` 不识别

**Why:** `label(n)` 是 Cypher 5.x+ 的"新"函数; 某些 driver 协议版本下 server 不识别. `labels(n)[0]` 是所有 Cypher 4.x/5.x 都支持的等价写法.

**How to apply:**
- 写 `count_by_label` / `count by node type` 类统计时永远用 `RETURN labels(n)[0] AS label, count(n) AS cnt` + 加 `WHERE size(labels(n)) > 0` 过滤无 label 节点
- 同样的规则适用 `type(r)` vs `type(r)` (关系 type 一直 OK, 只有节点 label 函数不统一)
- 测试要 verify cypher 字符串里不含 `label(n)`, 只含 `labels(n)[0]` —— 防止以后有人 "fix typo" 改回去
