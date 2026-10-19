# D4: Data integrity & Migrations 扫描结果

> 扫描时间: 2026-06-26
> Agent 角色: 偏数据视角 — 假设数据被破坏/迁移失败
> 工具调用次数: 15 / 30
> 找到 6 条 finding (verified: 6, refuted: 0, 待 verify: 0)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径:
  - packages/service/src/storage/migrations/versions/*.py (17 个 migration 文件)
  - 所有 models.py (auth, chat, eval, approvals, kg, lookups, db — 8 个文件)
  - packages/service/src/lookups/* (safety_guard, models, __init__)
  - Grep ForeignKey / relationship (12 个文件)
  - 每个 migration 的 upgrade() / downgrade() 对比
  - tests/conftest.py, tests/storage/conftest.py, tests/integration/conftest.py
- 已知跳过:
  - 不扫描 kg/neo4j.py (Neo4j 是图库, FK 语义不同, 不在检查范围)
  - 不检查前端 `tests/test_api_contract.py` (属 frontend D5 范围)
- 备注: 17 个 migration 的依赖链全部正确, 无循环依赖和顺序倒挂. 检查项 7 (软删+唯一约束) / 9 (已弃用列) / 10 (测试隔离) 未发现问题.

## Findings (6 条)

```yaml
- id: DATA-001
  dimension: data
  severity: high
  confidence: high
  title: "evaluations.user_id FK 无 ondelete, 删 user 后留孤儿行"
  file: packages/service/src/eval/models.py
  line: 36
  description: |
    evaluations.user_id 是 FK 到 users.id, 但 migration 和 ORM 模型都没有指定 ondelete
    行为 (默认 NO ACTION). 当用户被删除 (GDPR right to erasure) 时, PostgreSQL 会阻止
    删除, 或者需要先手动清理 evaluations 行. 这跟 conversations.user_id 已修复
    CASCADE (20260624_120000) 不一致, 形成不对称的 FK 策略.
  evidence: |
    ```python
    # eval/models.py line 36 — ORM 模型: 无 ondelete
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # 20260615_000000_consolidated_pg_init.py line 153 — migration: 无 ondelete
    sa.ForeignKeyConstraint(["user_id"], ["users.id"]),

    # 对比: chat/models.py line 42 — 已修复
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ```
  impact: |
    当匿名用户被 GDPR 清理或账号被删除时, evaluations 表出现孤儿行 (orphan records).
    或者删除操作直接被 FK 约束阻断, 导致数据清理流程失败. 目前已有一个专修 migration
    (20260624_120000) 解决了 conversations 但 evaluations 仍缺失.
  fix_sketch: |
    新建 migration: ALTER evaluations.user_id FK → ondelete=CASCADE.
    同步更新 eval/models.py: ForeignKey("users.id", ondelete="CASCADE").
    messages → conversations 已有 CASCADE 链, evaluations 也应加入这条链.
  references:
    - "相似问题: 20260624_120000 conversations.user_id CASCADE 修复"

- id: DATA-002
  dimension: data
  severity: medium
  confidence: high
  title: "approvals.models FK ondelete 行为未在 ORM 模型中表达"
  file: packages/service/src/approvals/models.py
  line: 61
  description: |
    DB 中 approvals.submitter_id 和 approvals.reviewer_id 的 FK 由 migration
    20260615_000000 定义了不同的 ondelete 行为 (submitter_id=CASCADE,
    reviewer_id=SET NULL). 但 ORM 模型没有显式指定这些策略, 使用 ForeignKey("users.id")
    而不带 ondelete. 这种 ORM 与迁移的不一致使开发者误以为 FK 是 NO ACTION 默认值,
    且 alembic autogenerate 可能产生虚假 diff.
  evidence: |
    ```python
    # approvals/models.py line 61-62 — ORM 模型: 无 ondelete
    submitter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), ...)
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), ...)

    # 20260615_000000_consolidated_pg_init.py line 197-198 — migration: 有 ondelete
    sa.ForeignKeyConstraint(["submitter_id"], ["users.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
    ```
  impact: |
    开发者按 ORM 模型理解会认为 FK 是 NO ACTION, 但实际 DB 是 CASCADE / SET NULL,
    导致在测试或手动操作时产生意外的级联行为. alembic autogenerate 可能误报需要迁移.
  fix_sketch: |
    同步 approvals/models.py 的 ForeignKey 定义: submitter_id 加 ondelete="CASCADE",
    reviewer_id 加 ondelete="SET NULL", 跟 migration 一致. 不需要新的 DB migration
    (DB 已正确, 仅模型需修正).

- id: DATA-003
  dimension: data
  severity: medium
  confidence: high
  title: "accounts.role 和 buyer_profiles.status 使用硬编码 CHECK 约束而非 lookups"
  file: packages/service/src/storage/migrations/versions/20260624_165000_add_role_and_status_check_constraints.py
  line: 21
  description: |
    accounts.role 和 buyer_profiles.status 通过 CHECK 约束写死枚举值
    ('super_admin','admin','user' / 'active','archived'). 根据项目规约 (CLAUDE.md
    §字典使用规范), 业务 enum 必须走 lookup 字典模块, 不允许新增硬编码 StrEnum 或
    CHECK 硬编码. 新增枚举值需要发版修改 migration, 违反运行时热更新策略.
    迁移本身注释也说明 "无 FK 到 dictionary_items (Phase 3 大重构范围外)".
  evidence: |
    ```python
    # 20260624_165000_add_role_and_status_check_constraints.py line 21-25
    op.execute("ALTER TABLE accounts ADD CONSTRAINT ck_accounts_role "
               "CHECK (role IN ('super_admin', 'admin', 'user'))")
    op.execute("ALTER TABLE buyer_profiles ADD CONSTRAINT ck_buyer_profiles_status "
               "CHECK (status IN ('active', 'archived'))")

    # account_models.py line 41 — 模型用硬编码 str 类型
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user", server_default="user")
    ```
  impact: |
    新增角色 (如 'editor') 或状态 (如 'suspended') 需要发版修改 migration + 重新
    ALTER TABLE ADD CONSTRAINT, 不是运行时修改的可插拔方式. lookup 字典模块已经就绪,
    accounts.role 和 buyer_profiles.status 应该引用字典项而非硬编码 CHECK.
  fix_sketch: |
    在 dictionaries_seed.yaml 注册 role_type 和 profile_status 两个字典; 替换
    CHECK 约束为 FK → dictionary_items; 迁移已有数据; 审计侧确认. 注意这是 Phase 3
    大重构内容, 本 finding 仅做记录.
  references:
    - "CLAUDE.md §字典使用规范"
    - "packages/service/src/lookups/README.md"

- id: DATA-004
  dimension: data
  severity: medium
  confidence: high
  title: "多个 JSONB 字段无 Pydantic schema 校验, 数据形状靠约定"
  file: packages/service/src/chat/models.py
  line: 88
  description: |
    项目 8 个 JSONB 字段 (messages.meta, evaluations.avg_metrics,
    evaluation_samples.contexts/sources/metrics, buyer_profiles.profile_data/
    profile_meta, dictionary_items.metadata_json) 均使用 Mapped[dict[str,Any] |
    None] 或类似泛型标注, 没有对应的 Pydantic 模型定义字段结构.
    这导致写入时可以接受任意形状的 JSON, 读取方只能靠逻辑防御
    (_parse_meta 兜底), 无法在边界做类型校验.
  evidence: |
    ```python
    # chat/models.py line 88 — 无 schema 约束
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # eval/models.py line 51 — 同样无 schema
    avg_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # eval/models.py line 95 — 同样是泛型
    contexts: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ```
  impact: |
    无 schema 校验的 JSONB 字段容易产生数据不一致. 例如 evaluation.contexts
    有的行是 list[str], 有的行是 list[dict]. 业务代码需要大量防御性判断
    (_parse_meta 等), 增加出错面和维护成本.
  fix_sketch: |
    为每个 JSONB 字段定义 Pydantic BaseModel (如 MessageMeta, EvalMetrics).
    在 service 层写入前做 model_validate, 读取时用 model_validate 保证形状.
    对历史数据做迁移脚本校验兼容.

- id: DATA-005
  dimension: data
  severity: low
  confidence: medium
  title: "profile_change_logs.account_id FK 列缺少 B-tree 索引"
  file: packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py
  line: 91
  description: |
    profile_change_logs 表有 FK (fk_change_logs_account) 引用 accounts.id,
    且 FK 定义了 ondelete=CASCADE. 但 account_id 列没有创建普通 B-tree 索引,
    仅在 (profile_id, created_at DESC) 上有复合索引. 在 PostgreSQL 中, FK 列
    缺少索引会导致 CASCADE 删除时锁全表扫描 (表级锁), 在大表场景下严重性能问题.
    虽然 buyer_profiles.account_id 和 profile_change_log 的 profile_id 列都有索引.
  evidence: |
    ```python
    # 20260622_000000_create_buyer_profiles.py line 78-92
    op.create_table("profile_change_logs", ...,
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ...),
        sa.ForeignKeyConstraint(["profile_id"], ["buyer_profiles.id"], ...),
    )
    # 只有 profile_id 复合索引, 没有 account_id 单列索引
    op.create_index("idx_change_logs_profile", "profile_change_logs",
                     ["profile_id", sa.text("created_at DESC")])
    ```
  impact: |
    当 account 被删除触发 CASCADE 到 profile_change_logs 时, PG 需要对
    profile_change_logs 全表扫描来定位需要级联删除的行. 在大量日志记录的
    生产环境中可能导致长时间锁表.
  fix_sketch: |
    创建索引 idx_change_logs_account 在 profile_change_logs.account_id 上.
    可以用 CREATE INDEX CONCURRENTLY 避免锁表. migration 同时建索引.

- id: DATA-006
  dimension: data
  severity: medium
  confidence: high
  title: "chat_shares 初始 migration 未定义 FK + 列类型不匹配, 存在孤立数据窗口期"
  file: packages/service/src/storage/migrations/versions/20260616_000000_add_chat_shares.py
  line: 23
  description: |
    20260616_000000 创建 chat_shares 表时没有为 conv_id 和 user_id 定义 FK 约束,
    且列类型跟被引用表不匹配: conv_id 用了 String(128) 而 conversations.id 是
    String(36); user_id 用了 String(64) 而 users.id 是 Integer. 这个状态持续到
    20260624_170000 修复, 期间 chat_shares 可以写入引用不存在或类型不匹配的 ID,
    产生语义孤立行. 修复 migration 也依赖现有数据全是合法数字字符串.
  evidence: |
    ```python
    # 20260616_000000_add_chat_shares.py line 23-26 — 无 FK, 类型跟被引用表不匹配
    sa.Column("conv_id", sa.String(length=128), nullable=False),
    sa.Column("user_id", sa.String(length=64), nullable=False),  # 所有者

    # 被引用表类型: conversations.id is String(36), users.id is Integer
    # 修复: 20260624_170000_fix_chat_shares_fk.py
    op.alter_column("chat_shares", "user_id", ..., type_=sa.Integer(),
                    postgresql_using="user_id::integer")
    op.create_foreign_key("fk_chat_shares_user_id", ...)
    ```
  impact: |
    在 20260616 到 20260624 之间, chat_shares 表可能包含指向不存在 conversation
    或 user 的行, 或不符合外键约束的数据. 修复 migration 用了
    postgresql_using="user_id::integer" 隐式转换, 如果存在非数字字符串会失败,
    需要手工清理数据.
  fix_sketch: |
    已由 20260624_170000 修复. 建议编写数据完整性检查脚本, 扫描现有 chat_shares
    数据确认没有孤立引用 (外键校验). 如果发现孤立行, 清理或添加关联.
```

## 未扫 / 已知缺口

- **KG (Neo4j)**: 不检查 kg/neo4j.py — 图数据库节点关系用 Cypher 表达, 不是 SQL FK 语义, 不在本维度范围.
- **查询性能**: FK 缺索引只对 CASCADE 场景做了浅层分析. 未跑 `EXPLAIN ANALYZE` 等查询计划分析.
- **数据迁移脚本**: 只检查了 alembic migration (DLM). 未检查 `scripts/seed_dictionaries.py` 等运行时数据迁移脚本的正确性.
- **生产数据校验**: 本扫描是静态代码分析. 未连接生产 DB 校验 FK 引用完整性或孤立数据. 建议在 staging 跑 `SELECT * FROM chat_shares WHERE conv_id NOT IN (SELECT id FROM conversations)` 等校验.
- **pgvector 表**: 检查了 retrieval/vector_store.py 的 raw SQL, 但 pgvector 扩展定义的 `vector` 类型不在标准 FK 检查范围内.
