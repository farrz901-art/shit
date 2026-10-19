---
name: feedback-cypher-merge-label-rel-type-not-parameterizable
description: "Neo4j Cypher 的 MERGE 节点 label 和关系 rel_type 不能参数化, UNWIND 批量写入多种 label/rel_type 时必须按 5 元组分组, 否则所有行被首行覆盖"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1f31d195-59f7-46d2-9621-643c2a513cbb
---

Neo4j Cypher 语法限制 (4.x/5.x 都适用):

```cypher
-- 合法: 属性可参数化
MERGE (n:Product {name: $name})

-- 非法: label 不能用 $param
MERGE (n:$label {name: $name})  -- ❌ ParserException

-- 非法: rel_type 也不能用 $param
MERGE (a)-[r:$rel_type]->(b)    -- ❌ ParserException
```

所以 label 和 rel_type 必须是 Cypher 字面量, 只能拼接到 query string 里. 一次 UNWIND 批量只能处理同一种 (from_label, from_key, to_label, to_key, rel_type) 组合的行 (5 元组同质).

**坑模式 (2026-06-12 在 [packages/service/src/kg/client.py](packages/service/src/kg/client.py) batch_upsert_triples 真实踩中)**:

```python
# ❌ bug 写法: 用 rows[0] 硬编码, 但 UNWIND 全部行
def _build_unwind_cypher(self, rows):
    first = rows[0]
    cypher = f"""
    UNWIND $rows AS row
    MERGE (a:{first.from_label} {{`{first.from_key}`: row.from_value}})
    MERGE (b:{first.to_label}   {{`{first.to_key}`:   row.to_value}})
    MERGE (a)-[r:{first.rel_type}]->(b)
    """
    params = {"rows": [{"from_value": r.from_value, "to_value": r.to_value} for r in rows]}
    # 后续行的 from_label/to_label/rel_type 全被首行覆盖, Neo4j 里:
    # - 所有节点都被打成 first.from_label / first.to_label
    # - 所有关系都成 first.rel_type
```

**真实灾难现场**: 前端录 4 行三元组 (产品系列+包含系列+产品系列 / 产品型号+符合标准+认证标准 / 产品系列+符合标准+认证标准 / 产品型号+具有参数+技术参数), Neo4j 里全成了 `:产品系列 -[包含系列]-> :产品系列` (4 节点 1 label, 4 关系 1 type).

**正确写法**:

```python
# ✅ 按 5 元组分组, 每组一次独立 UNWIND
groups = {}
for r in rows:
    key = (r.from_label, r.from_key, r.to_label, r.to_key, r.rel_type)
    groups.setdefault(key, []).append(r)

success = failed = 0
errors = []
for group_rows in groups.values():
    cypher, params = self._build_unwind_cypher(group_rows)  # 组内同质, first 取值跟所有行一致
    try:
        self._store.execute_and_fetch(cypher, params)
        success += len(group_rows)
    except Exception as e:
        failed += len(group_rows)
        errors.append(str(e))
```

**性能影响**: graph schema 里 label/rel_type 种类有限 (我们项目 7 节点 9 关系 ≤ 几十种组合), 分组数远小于行数, 仍然是批量优化 (组内 UNWIND), 不会退化到 1 行 1 query.

**测试盲点 (2026-06-12 这个 bug 漏掉的根因)**:
- 老测试只有 `test_single_row_runs_unwind_cypher` — 单行测出来 first==rows[0] 恒成立, 永远过
- 必须加 `test_heterogeneous_rows_grouped_by_label_and_rel_type` — 多行不同 label/rel_type, 断言 execute_and_fetch.call_count == 分组数 + 每次 Cypher 含正确 label/rel_type 字面量
- 同理加 `test_heterogeneous_partial_failure_isolated_per_group` — 一组失败不污染其他组

**How to apply**:
1. 任何 UNWIND MERGE 写多元批量数据时, 必须按所有"非属性"字段 (label/rel_type 等 Cypher 字面量) 分组
2. 单行测试通过 ≠ 多元批量也通过, **必须加多元测试** (label A+label B+rel R1+rel R2 至少各一条)
3. 单元测试要断言 `call_count == 预期分组数` 而非 `>= 1`, 否则单行/多元都过 (跟 [[feedback-tdd-test-real-behavior-not-just-no-crash]] 同源)
4. 测试 mock 时验证 cypher 字符串实际包含的 label/rel_type, 而不只是看 "UNWIND" 关键词

关联: [[feedback-tdd-test-real-behavior-not-just-no-crash]] (测真行为, 单行测过不代表多元过) · [[feedback-asyncio-sem-needs-peak-test]] (同理: 必须测多元/峰值) · [[feedback-must-test-both-ends]] (前端不报 422 不代表后端写对) · [[feedback-debug-distinguish-root-causes]] (前端看错觉得是 schema 设计问题, 真根因在后端 Cypher 拼接)
