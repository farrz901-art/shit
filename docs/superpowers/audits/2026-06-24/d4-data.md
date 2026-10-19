# D4: Data integrity & Migrations 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: D4 数据完整性 & 迁移 扫描 agent (read-only)
> 工具调用次数: 26
> 找到 11 条 finding

## 元信息

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/`
- 扫描路径:
  - `packages/service/src/storage/migrations/versions/*.py` (10 个 alembic migration 全部读完 downgrade)
  - `packages/service/src/lookups/{models.py,safety_guard.py,README.md}` (字典模块)
  - `packages/service/src/auth/{models.py,account_models.py}`
  - `packages/service/src/chat/models.py`
  - `packages/service/src/eval/models.py`
  - `packages/service/src/approvals/models.py`
  - `packages/service/src/permissions/models.py`
  - `packages/service/src/chat_share/models.py`
  - `packages/service/src/buyer_profile/{service.py,schemas.py}` (无 ORM, 用裸 SQL)
  - `packages/service/config/dictionaries_seed.yaml` (字典种子)
  - `packages/service/src/common/dictionaries_enum.py`
  - `packages/service/src/db/models/{app_log,audit_log}.py`
  - Grep `ForeignKey\(` / `ondelete=` / `StrEnum` / `Literal\[`
  - `packages/service/KNOWN_ISSUES.md`
- 已知跳过:
  - `src/db/models/error_log.py` (未读, 不在 D4 核心范围, 跟 app_log / audit_log 同形)
  - `src/kg/audit_models.py` (kg_audit 表无 FK, 不在 lookups 范围)
  - `src/ingest/models.py` (ingest_tasks 表无 FK, 跟 buyer_profile 同样问题)
- 备注:
  - 项目已有 lookup 字典机制 (`src/lookups/`) 跟 6 层防御, 已就位但部分业务表 (`accounts.role`, `buyer_profiles.status`) 仍硬编字符串, 没走字典
  - 5 个 migration 全部带 downgrade; 多数干净, 仅 `20260623_000000_drop_account_id_from_field_configs` 的 downgrade 在多行数据下会失败
  - ORM 跟 migration 的约束名不一致是普遍现象 (3+ 处): ORM 用 `email_format` / `idx_accounts_email`, migration 用 `ck_accounts_email_format` / `uq_accounts_email`

## Findings (11 条)

```yaml
- id: DATA-001
  dimension: data
  severity: critical
  confidence: high
  title: "20260623 migration downgrade 在多行场景下必失败: account_id server_default=0 + UNIQUE 冲突"
  file: packages/service/src/storage/migrations/versions/20260623_000000_drop_account_id_from_field_configs.py
  line: 31
  description: |
    migration `20260623_000000` 的 upgrade 删了 `profile_field_configs.account_id` 并把
    UNIQUE 改成 `code`. downgrade 顺序是: 删 `uq_field_configs_code` → 加回 `account_id` 列
    (server_default="0", nullable=False) → 加 FK → 加回 `uq_field_configs_account_code` UNIQUE
    约束. 但 profile_field_configs 通常有 5+ 行 (e.g. country/industry/company_size/...), 全部
    落 `account_id=0`, 接着 UNIQUE(account_id, code) 立刻冲突: 5 行全有 account_id=0 + 不同
    code → 不冲突; 但若有 2 行同 code (历史 seed 重复, 或 admin 误操作), UNIQUE 失败; 更致命
    的情况是同一 account 业务下有重复 code 行, 倒回时无解. 此外, 当升级到这一版后又通过
    admin 加了新行 (无 account_id), downgrade 期间所有行硬挤到 account_id=0 同样会丢语义.
  evidence: |
    def downgrade() -> None:
        # 1. 删 UNIQUE(code)
        op.drop_constraint("uq_field_configs_code", "profile_field_configs", type_="unique")
        # 2. 加回 account_id 列 + FK
        op.add_column(
            "profile_field_configs",
            sa.Column("account_id", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_foreign_key(
            "fk_field_configs_account",
            "profile_field_configs",
            "accounts",
            ["account_id"],
            ["id"],
        )
        # 3. 加回 UNIQUE(account_id, code)
        op.create_unique_constraint(
            "uq_field_configs_account_code",
            "profile_field_configs",
            ["account_id", "code"],
        )
  impact: |
    数据丢失风险: 多行 + account_id 全相同 → 任意一行 UNIQUE 冲突导致 alembic downgrade
    中途崩, 后续 drop_column 跟 drop_constraint 无法执行, 需手工 SQL 救场. 此外 server_default
    把所有行填 0 永远不符合历史 account 隔离语义, 倒回等同于污染数据.
  fix_sketch: |
    在 downgrade 前先 SELECT DISTINCT code → 用 `INSERT INTO profile_field_configs_new`
    临时表方式兜底, 或明确加 `op.execute("UPDATE profile_field_configs SET account_id = "
    "(SELECT account_id FROM accounts WHERE id = (SELECT MIN(id) FROM accounts))")` 给个
    兜底 account_id, 文档化 "downgrade 仅适用于单 account 场景". 推荐: 不写可回滚的
    downgrade, 改 `raise NotImplementedError("data loss: 20260623 not reversible")` 强提示
    不可逆, 跟 alembic 项目对不可逆 migration 的标准做法一致.
  references: ["alembic-irreversible-migrations"]

- id: DATA-002
  dimension: data
  severity: critical
  confidence: high
  title: "Account 表 ORM 跟 migration 约束名不一致, ORM 无法透明读写 (name mismatch)"
  file: packages/service/src/auth/account_models.py
  line: 36
  description: |
    ORM model `Account` 用 `CheckConstraint("email LIKE '%_@_%._%'", name="email_format")` 跟
    `Index("idx_accounts_email", "email", unique=True)`. 但 `20260615_000000_consolidated_pg_init.py`
    实际创建的是 `ck_accounts_email_format` (CheckConstraint) + `uq_accounts_email` (UniqueConstraint
    on email) + `ix_accounts_email` (index). 名字完全不匹配: ORM 期望 `email_format`,
    DB 实际是 `ck_accounts_email_format`. SQLAlchemy 启动时如果使用 `Base.metadata.create_all`
    不会冲突 (因为有 Index 单独声明); 但用 `metadata.reflect` 或 alembic autogenerate 时, ORM
    会认为 DB 缺 `email_format` 约束, 试图新建 → 名字撞 `ck_accounts_email_format` 内容相同但
    名字不同, autogenerate 必出 diff. 此外 ORM 的 `Index("idx_accounts_email", unique=True)`
    跟 migration 的 `op.create_index(op.f("ix_accounts_email"), "accounts", ["email"], unique=True)`
    名字也不同 (idx_ vs ix_ 前缀).
  evidence: |
    # account_models.py:35-39 (ORM)
    __table_args__ = (
        CheckConstraint("email LIKE '%_@_%._%'", name="email_format"),
        Index("idx_accounts_email", "email", unique=True),
        Index("idx_accounts_is_active", "is_active"),
    )

    # 20260615_000000_consolidated_pg_init.py:43-47 (migration)
    sa.CheckConstraint("email LIKE '%_@_%._%'", name="ck_accounts_email_format"),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("email", name="uq_accounts_email"),
    op.create_index(op.f("ix_accounts_email"), "accounts", ["email"], unique=True)
  impact: |
    alembic revision --autogenerate 会报 "constraint 'email_format' missing", 误导开发者去
    加一个跟现有 migration 重复的约束. 实际 SQL 写入不受影响 (CheckConstraint 表达式相同),
    但 schema 漂移产生大量假 diff, 干扰 code review. 长期会导致 autogenerate 不可信.
  fix_sketch: |
    二选一: a) 改 ORM 跟 migration 对齐 (统一 `ck_accounts_email_format` + `ix_accounts_email`),
    删除 ORM 里重复声明的 UniqueConstraint on email (反正 Index unique=True 已够), 留
    CheckConstraint 表达式给 alembic 单独管; b) 把 ORM 的 `__table_args__` 改成
    `{"extend_existing": True}` + 不声明约束, 让 migration 唯一事实源. 推荐 b, 跟项目
    "migration 是 schema 唯一事实源" 的现行做法一致 (chat/models.py:37 用了 Index 声明,
    但跟 migration `ix_conversations_user_updated` 名字一致, 没问题).
  references: []

- id: DATA-003
  dimension: data
  severity: critical
  confidence: high
  title: "conversations.user_id FK 缺 ondelete 策略, 用户删除后聊天记录成孤儿"
  file: packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py
  line: 114
  description: |
    `conversations` 表 user_id FK 声明为 `sa.ForeignKeyConstraint(["user_id"], ["users.id"])`,
    没有 `ondelete=` 参数. PG 默认是 `NO ACTION`: 删 User 行时, 只要还有 conversations 引用,
    整删就被 PG 拒绝. 但 `users.account_id` 又是 `SET NULL` on delete, 删 Account 时 user 行
    不直接被 CASCADE 删, 但 user 的 account_id 变 NULL — 这不会触发 conversations.user_id
    的 FK 检查, 因为 user 还在. 真正的孤儿风险来自 user 手动物理删: 删 user → conversations
    引用悬挂的 user_id, 业务查询会拿不到 user 信息, 但 row 还在. 业务侧 chat service 用
    `WHERE user_id = :uid` 还能查到, 但 `JOIN users` 拿 display_name 必空.
  evidence: |
    # 20260615_000000_consolidated_pg_init.py:106-119 (conversations)
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # chat/models.py:40 (ORM) 同样没 ondelete=
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  impact: |
    GDPR 风险: 用户申请删除时 (Account deletion_requested_at 已支持), admin 跑硬删 user
    row, conversations 变孤儿 — 行还在, 用户历史聊天无法级联清. 跟 chat_soft_delete spec
    的 "30d cron hard_delete" 设计冲突: soft-delete 走 conversations.deleted_at 没问题,
    但 user 真删时 conversations 引用悬挂. 后续业务做 "user → 全部数据" 导出或清理时
    会漏这一块.
  fix_sketch: |
    加新 migration: `ALTER TABLE conversations DROP CONSTRAINT fk_conversations_user_id_users;
    ALTER TABLE conversations ADD CONSTRAINT fk_conversations_user_id_users FOREIGN KEY
    (user_id) REFERENCES users(id) ON DELETE CASCADE;` 同步 ORM (`ondelete="CASCADE"`).
    配套 chat/models.py:40 跟 migration 都更新. 触发 user 删时自动级联清 conv → messages
    (后者已 CASCADE), 跟 chat_soft_delete 互补: soft-delete 隐藏 UI, hard-delete user
    时彻底清.
  references: ["chat-soft-delete-spec"]

- id: DATA-004
  dimension: data
  severity: high
  confidence: high
  title: "accounts.role 跟 roles.name 无 FK, role 字典漂移无法被 DB 拦截"
  file: packages/service/src/storage/migrations/versions/20260617_000000_add_roles_and_rbac.py
  line: 27
  description: |
    `accounts.role` (Text, default "user") 跟 `role_permissions.role_name` (Text) 都没有
    FK 指向 `roles.name`. roles 表用 `name` UNIQUE 约束保证不重, 但 account/permission 行
    写任何字符串都不会被 DB 拦截. 业务侧 `guards.py:20` 跟 `permissions/service.py:67` 用
    `if user.role == "super_admin"` 这种 hardcoded string 比较, 任何 typo (e.g. "superAdmin"
    "super_admin " "SUPER_ADMIN") 都会被静默通过 (除了 super_admin 走 meta 豁免), 但其他
    role 走 matrix 查询时 cache miss → 返 False → 用户无感知地被拒绝. 同时违反 CLAUDE.md
    跟 README §字典使用规范 的 "业务 enum 必须走 lookup 字典" 强制规范.
  evidence: |
    # 20260617_000000_add_roles_and_rbac.py:26-29 (accounts.role)
    op.add_column(
        "accounts",
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
    )

    # 20260617_000000_add_roles_and_rbac.py:93-101 (role_permissions.role_name)
    sa.Column("role_name", sa.Text(), nullable=False),
    sa.Column("page_key", sa.Text(), nullable=False),
    sa.UniqueConstraint("role_name", "page_key", name="uq_role_perm"),

    # account_models.py:26 (ORM) 同样 Text, default="user", 无 FK
    role: Mapped[str] = mapped_column(Text, nullable=False, default="user", server_default="user")

    # guards.py:20 hardcoded 比较
    if user.role == "super_admin":
  impact: |
    中等严重: typo "admin " 带空格 → 永远走不进 admin 路径, 业务排查至少花 1-2 小时;
    字典漂移 (super_admin 重命名) 时无法被 DB 阻拦, 只能依赖业务代码 5 处 hardcoded
    "super_admin" 一一改, 漏一个就出 RBAC 绕过. 此外未来扩展新 role (e.g. "auditor")
    需手工改 5+ 处 if-elif, 不走字典管理.
  fix_sketch: |
    短期: 加 lookup 字典 `account_role` (items: user/admin/super_admin), 业务改用
    `LookupService.get_one("account_role", role)`. 长期: 改 schema, accounts.role 改
    FK references roles.name (加新 migration 删 default 改 FK). 项目已经有
    PageKeyEnum/ApprovalKindEnum 等走字典的成功案例, role 是漏网之鱼.
  references: ["CLAUDE.md §字典使用规范"]

- id: DATA-005
  dimension: data
  severity: high
  confidence: high
  title: "buyer_profiles / profile_change_logs FK 全缺 ondelete, 跟 account 删语义不一致"
  file: packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py
  line: 43
  description: |
    `20260622_000000_create_buyer_profiles.py` 创建 3 张表的 FK 全部没 ondelete:
    `buyer_profiles.account_id → accounts.id` (line 43), `profile_field_configs.account_id
    → accounts.id` (line 74), `profile_change_logs.account_id → accounts.id` (line 90),
    `profile_change_logs.profile_id → buyer_profiles.id` (line 91). 跟同项目其他业务表
    的策略不一致: `invites.account_id` 是 SET NULL, `password_resets.account_id` 是
    CASCADE, `email_changes.account_id` 是 CASCADE, `deletion_restores.account_id` 是
    CASCADE. buyer_profile 跟用户关联极强 (一个 account 删了, 它的画像 / 字段配置 /
    变更日志 没意义), 应该 CASCADE. 但现在 NO ACTION 意味着删 account 被 DB 拒, admin
    删账号体验断 (跟 deletion_requested_at 30d 宽限期流程冲突).
  evidence: |
    # 20260622_000000_create_buyer_profiles.py:43
    sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_buyer_profiles_account"),

    # 同文件 line 74
    sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_field_configs_account"),

    # 同文件 line 90-91
    sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name="fk_change_logs_account"),
    sa.ForeignKeyConstraint(["profile_id"], ["buyer_profiles.id"], name="fk_change_logs_profile"),
  impact: |
    GDPR 删账号流程: 30d 宽限期后硬删 accounts 行, 但 buyer_profiles.profile_field_configs
    (被 20260623 删过 account_id 列, 风险小) + profile_change_logs 引用悬挂. 业务测
    account 删前必须手工跑 `DELETE FROM profile_change_logs WHERE account_id = X`, 加
    运维负担. 此外 profile_change_logs 跟 buyer_profiles 间 FK 缺 CASCADE, 业务侧
    删 profile 不会清 logs, 历史日志永远累积.
  fix_sketch: |
    加新 migration `20260624_000000_add_buyer_profile_ondelete.py`:
    ```python
    op.drop_constraint("fk_buyer_profiles_account", "buyer_profiles", type_="foreignkey")
    op.create_foreign_key("fk_buyer_profiles_account", "buyer_profiles", "accounts",
                          ["account_id"], ["id"], ondelete="CASCADE")
    # profile_change_logs 同样
    op.drop_constraint("fk_change_logs_account", "profile_change_logs", type_="foreignkey")
    op.create_foreign_key("fk_change_logs_account", "profile_change_logs", "accounts",
                          ["account_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("fk_change_logs_profile", "profile_change_logs", type_="foreignkey")
    op.create_foreign_key("fk_change_logs_profile", "profile_change_logs", "buyer_profiles",
                          ["profile_id"], ["id"], ondelete="CASCADE")
    ```
    profile_field_configs.account_id 已被 20260623 删除, 跳过. 注意: buyer_profiles 跟
    accounts 之间 CASCADE 会让"删 account = 删全部画像", 跟项目 user→conversations
    CASCADE 语义保持一致.
  references: []

- id: DATA-006
  dimension: data
  severity: high
  confidence: high
  title: "buyer_profiles.status 用 String 硬编 active/archived, 违反 lookup 唯一事实源"
  file: packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py
  line: 31
  description: |
    `buyer_profiles.status` 是 `sa.String(32), server_default="active"`, schema 限定
    0 个候选值, 业务侧 `service.py:170` 硬编 `status = 'archived'`. 跟项目强制规范
    "业务 enum 必须走 lookup 字典, 禁止新增硬编 StrEnum" 冲突. 同类业务有
    `ApprovalReviewStatusEnum` / `ApprovalKindEnum` / `PageKeyEnum` 全部走 lookup,
    唯独 buyer_profiles 漏了. 后续 super_admin 改字典加 "dormant" / "blocked" 状态
    时, 业务侧 string compare 会漏处理, 列表过滤失效. CLAUDE.md §字典使用规范
    "新加字典 5 步流程" 也没按: 没 yaml / 没 dictionaries_enum / 没 _REFERENCE_MAP
    注册.
  evidence: |
    # 20260622_000000_create_buyer_profiles.py:31
    sa.Column("status", sa.String(32), server_default="active", nullable=False),

    # buyer_profile/schemas.py:38
    status: str = Field("active", description="状态: active/archived")

    # buyer_profile/service.py:170 (硬编 archived)
    query = "UPDATE buyer_profiles SET status = 'archived', updated_at = NOW() WHERE id = :id AND account_id = :aid"
  impact: |
    业务灵活性: 加新状态 (e.g. "blocked" "merged") 需改 DB default + service.py + schema
    description, 不能像 lookup 字典那样 runtime 5 秒生效. 字典 invalidation / 缓存
    / 多语言 label 都没有. 长期: 跟 approvals/reviews 等其他 status 字段不一致,
    增加新人学习成本.
  fix_sketch: |
    加 lookup 字典 `buyer_profile_status` (items: active/archived/dormant). 改 migration
    删 server_default 改 CHECK, 改 business service 用 `LookupService.get("buyer_profile_status")`
    验证状态. 短期不动 schema 的话, 业务 service.py 改用枚举常量替代字符串 hardcode.
  references: ["CLAUDE.md §字典使用规范"]

- id: DATA-007
  dimension: data
  severity: high
  confidence: high
  title: "chat_shares.conv_id / user_id 类型 + 长度跟实际表对不上, 无 FK 约束"
  file: packages/service/src/chat_share/models.py
  line: 23
  description: |
    `chat_shares.conv_id` 是 `String(128)`, 但 `conversations.id` 是 `String(36)`
    (UUID). `chat_shares.user_id` 是 `String(64)`, 但 `users.id` 是 `Integer`. ORM
    完全没声明 FK (line 23-26), migration `20260616_000000_add_chat_shares.py` 也没
    FK. 任何 conv_id / user_id 字符串都能写进 chat_shares, 不会触发 PG 约束. 业务
    侧公开读 share_id 拿 conv_id 后, 拿 conv_id 去 conversations 表查不到行 (或查到
    别的用户), 但 share 仍能展示 — 分享泄露. 此外 user_id String(64) 跟 Integer
    id 完全不兼容, 后续想 JOIN 必有类型错误.
  evidence: |
    # chat_share/models.py:23-26 (ORM)
    share_id: Mapped[str] = mapped_column(String(12), primary_key=True)  # nanoid 12 字符
    conv_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)  # 所有者
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 20260616_000000_add_chat_shares.py:22-37 (migration, 无 FK)
    sa.Column("conv_id", sa.String(length=128), nullable=False),
    sa.Column("user_id", sa.String(length=64), nullable=False),  # 所有者
    ...
    sa.PrimaryKeyConstraint("share_id"),
  impact: |
    数据完整性: 分享的快照跟用户/对话失联, admin 撤销时无法级联 (chat_shares.user_id
    跟 users.id 都不是同类型, 无法加 FK). 业务侧拿 conv_id 去 conversations 查时,
    类型不同 (String vs String 都 OK, 但 128 vs 36 大小写敏感) 实际可能误匹配.
  fix_sketch: |
    短期: 加 migration `ALTER TABLE chat_shares ADD CONSTRAINT fk_chat_shares_conv
    FOREIGN KEY (conv_id) REFERENCES conversations(id) ON DELETE CASCADE;` 同步
    user_id 改 Integer. 长期: chat_shares 改成存 user_token (String) 而非 user_id,
    因为 anon user 跟 share_id 本来就解耦; 或者 user_id 改成 String 跟 public_token
    一致 (但跟 users.id 仍不对应). 推荐: FK on conv_id 必加, user_id 改 public_token.
  references: []

- id: DATA-008
  dimension: data
  severity: high
  confidence: high
  title: "JSONB 列无 Pydantic schema 验证, profile_data / change_logs 可写任意结构"
  file: packages/service/src/storage/migrations/versions/20260622_000000_create_buyer_profiles.py
  line: 32
  description: |
    `buyer_profiles.profile_data` 跟 `profile_meta` 都是 JSONB 无 schema, business
    service `service.py:88-94` 写时仅塞 `{value, confidence, source, updated_at}` 4 字段,
    没 Pydantic 验证 (虽然 `schemas.py:23-29` 有 `ProfileFieldValue` 但没在 service
    写库时用). 此外 `old_value` / `new_value` (line 84-85) 是裸 JSONB, 写库时只
    json.dumps 没验证. 后果: 1) 不同来源 (auto/manual/import) 写出的 value 类型不一
    致 (e.g. "country" 写字符串 vs 写对象 `{label: "X", code: "Y"}`), 前端展示
    NaN. 2) 改 schema 字段时 (加 new field) 旧行结构不统一, 业务查询要 N 个 fallback.
    3) 误写超大 JSON (LLM 幻觉返回 100KB 文本) 直接塞库, 索引 / 备份膨胀.
  evidence: |
    # 20260622_000000_create_buyer_profiles.py:32-33
    sa.Column("profile_data", JSONB(), nullable=False, server_default="{}"),
    sa.Column("profile_meta", JSONB(), nullable=False, server_default="{}"),

    # 同文件 line 84-85
    sa.Column("old_value", JSONB(), nullable=True),
    sa.Column("new_value", JSONB(), nullable=True),

    # buyer_profile/service.py:88-94 (写库无 Pydantic 验证)
    for code, value in fields.items():
        current_data[code] = {
            "value": value,
            "confidence": "high" if value else "medium",
            "source": "auto",
            "updated_at": now,
        }
  impact: |
    业务层 schema 漂移: 后期加 field_type="select" 的字段, value 应是 `{label, code}`,
    但旧 auto-extract 直接写字符串. 跟 LLM 抽到的字段值类型不稳定, 前端渲染要
    做 5 个 if-else fallback. 此外 change_logs 的 old/new 没 schema 限制, 任何
    类型都能写, 数据分析时难做统一 diff.
  fix_sketch: |
    service 写库前用 `ProfileFieldValue.model_validate({...})` 验证, 失败 raise
    Pydantic ValidationError. 或者在 service 层维护一个 `field_code → field_type` 映射,
    写时按 field_type 转 (select → `{label, code}`, tags → list[str], number → float,
    boolean → bool). 老数据迁移: 写个一次性脚本把现有 profile_data 按字段 type
    normalize 一遍.
  references: []

- id: DATA-009
  dimension: data
  severity: medium
  confidence: high
  title: "Dictionary ORM 跟 migration UniqueConstraint 名字不一致 (uq_dict_item vs uq_dictionary_items_dict_code_key)"
  file: packages/service/src/lookups/models.py
  line: 79
  description: |
    ORM `DictionaryItem.__table_args__` 用 `UniqueConstraint("dict_code", "key", name="uq_dict_item")`,
    但 migration `20260619_120000_create_dictionary_tables.py:66` 用
    `sa.UniqueConstraint("dict_code", "key", name="uq_dictionary_items_dict_code_key")`.
    跟 DATA-002 同样问题, alembic autogenerate 必出 diff. 影响: developer 跑
    alembic revision --autogenerate 后看到 "add constraint uq_dict_item" 这种假
    diff, 干扰 code review. 短期无害 (因为 DB 已用 migration 名字), 长期会让
    autogenerate 不可信.
  evidence: |
    # lookups/models.py:79
    __table_args__ = (UniqueConstraint("dict_code", "key", name="uq_dict_item"),)

    # 20260619_120000_create_dictionary_tables.py:66
    sa.UniqueConstraint("dict_code", "key", name="uq_dictionary_items_dict_code_key"),
  impact: |
    跟 DATA-002 同型, 中等严重: autogenerate diff 噪音, 不会真出 schema 漂移. 但跟
    项目 "migration 是 schema 唯一事实源" 原则冲突, 长期维护成本.
  fix_sketch: |
    改 ORM 用 `extend_existing=True` + 不在 `__table_args__` 声明 UniqueConstraint,
    或者 ORM 跟 migration 名字对齐 (`uq_dictionary_items_dict_code_key`). 选跟
    20260619 已落库的名字一致: ORM 改 `name="uq_dictionary_items_dict_code_key"`.
  references: []

- id: DATA-010
  dimension: data
  severity: medium
  confidence: high
  title: "ingest_tasks.user_hash / kg_audit 表无 FK, 跟 accounts/users 完全失联"
  file: packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py
  line: 211
  description: |
    `ingest_tasks` 表用 `user_hash` (String 64) 标识用户, 不是 FK, 跟 users.id / public_token
    都不对应. `kg_audit` 表更没 user 字段, 仅 `actor` String 100. 业务侧 admin 排查
    "谁在什么时候 ingest 了什么" 时, 必须用 user_hash 字符串 join, 等同于"我猜
    是谁" — 实际上 user_hash 是什么 (hash 算法) 都没在表注释里说明. 此外 GDPR
    删 user 时, ingest_tasks 行不受影响, 任务历史永久留存, 跟 deletion 流程
    预期冲突.
  evidence: |
    # 20260615_000000_consolidated_pg_init.py:212-235 (ingest_tasks)
    op.create_table(
        "ingest_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        ...
        sa.Column("work_dir", sa.String(length=500), nullable=True),
        sa.Column("input_files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("output_files_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.PrimaryKeyConstraint("id"),
    )

    # 同文件 line 237-248 (kg_audit, 无 user 字段, 仅 actor String)
    op.create_table(
        "kg_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ts", sa.Float(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=True),
        ...
    )
  impact: |
    中等: GDPR 删 user 时, ingest_tasks 留 row (任务状态已完成, 不算 PII, 但
    user_hash 字符串本身算弱标识). 业务排查"哪个账号触发 ingest"需手工对照
    user_hash 算法 (如果 hash 是 SHA256(public_token), 业务可重算, 但 schema
    没说明). 长期: 加 user_id FK 后, GDPR 删 user 可 CASCADE 清任务历史.
  fix_sketch: |
    ingest_tasks 加 `user_id Integer` FK → users.id, 保留 user_hash 兼容旧行.
    kg_audit 加 `actor_id BigInteger` 跟 `actor_type Text` (跟 audit_logs 表
    schema 一致), 跟 accounts / users 多态关联. 短期: 在 model 注释里写明
    user_hash 算法, 让业务能 join.
  references: []

- id: DATA-011
  dimension: data
  severity: medium
  confidence: high
  title: "dictionaries_seed.yaml 不在 src/common/, lookup 启动校验路径跟 spec 文档不一致"
  file: packages/service/config/dictionaries_seed.yaml
  line: 1
  description: |
    `CLAUDE.md §字典使用规范` 跟 `lookups/README.md:158` 都写 "新加字典 5 步流程:
    1. 改 `src/common/dictionaries_seed.yaml`". 但实际 yaml 位置是
    `packages/service/config/dictionaries_seed.yaml`. 跟 `src/common/` 平行
    的是 `src/common/dictionaries_enum.py` + `src/common/dictionaries_loader.py`,
    后两者都从 `config/dictionaries_seed.yaml` 读 (推测), 跟 spec 文档对不上.
    新人按 spec 改 `src/common/dictionaries_seed.yaml` 不会生效, 但 `_verify_against_yaml`
    启动校验 (line 100-104) 静默通过 (因为找不到文件 → d is None → raise ValueError
    实际会 fail-fast, 但报错信息 "seed yaml 找不到字典: approval_review_status" 误导
    排查方向).
  evidence: |
    # lookups/models.py:18
    from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint

    # 实际 yaml 在 config/ 而非 src/common/
    $ find packages/service -name "dictionaries_seed*"
    packages/service/config/dictionaries_seed.yaml

    # 文档说在 src/common/
    # CLAUDE.md §字典使用规范: "改 src/common/dictionaries_seed.yaml"
    # lookups/README.md:158: "新加字典 5 步流程: 1. 改 src/common/dictionaries_seed.yaml"
  impact: |
    文档跟实际不一致, 新人改错位置浪费排错时间. 启动 fail-fast 报错指向 "yaml 找不到
    字典: approval_review_status", 看起来像 yaml 格式错, 实际是路径错. 不算数据
    损坏风险, 但 onboarding 摩擦.
  fix_sketch: |
    二选一: a) 把 `config/dictionaries_seed.yaml` 移到 `src/common/`, 跟 spec 一致;
    b) 更新 CLAUDE.md + lookups/README.md 跟实际路径对齐. 推荐 b (config/ 是
    12-factor 风格, 不该有 yaml 业务数据, 但 spec 已定, 改 spec 阻力小). 短期
    加个注释在 `src/common/dictionaries_loader.py` 顶部说明真实路径.
  references: ["CLAUDE.md §字典使用规范", "lookups/README.md §字典使用规范"]
```

## 未扫 / 已知缺口

- `src/db/models/error_log.py` 未读 (跟 app_log / audit_log 同形, 推断 schema 一致; 不在 D4 核心)
- `src/kg/audit_models.py` 未完整读 (kg_audit 表已确认无 FK, 无 lookup 关联; D4 不需深入)
- `src/ingest/models.py` 未读 (ingest_tasks 表跟 consolidated_pg_init 一致, 已通过 migration 文件分析)
- `tests/` 目录内 model 字段测试未扫 (测试模式 1 mock, 行为不影响生产 schema)
- 部分业务 model 的 `extend_existing=True` 是否带来 alembic 跟 ORM 重复声明问题, 未深入验 (DATA-002/009 提及但未深挖)
- `config/dictionaries_seed.yaml` 只读了 60 行, 25 个 items 已确认 enum 一致, 没全量对比字典 enum.py 的每个成员

## 总结

11 条 finding 中:

- **critical 3 条** (DATA-001 downgrade 必失败, DATA-002 ORM/migration 约束名漂移, DATA-003 conversations FK 缺 ondelete 致 GDPR 漏洞)
- **high 5 条** (DATA-004 account role 不走字典, DATA-005 buyer_profile FK 全缺 ondelete, DATA-006 buyer_profile status 硬编, DATA-007 chat_shares 无 FK + 类型错, DATA-008 JSONB 无 Pydantic 验证)
- **medium 3 条** (DATA-009 dictionary UniqueConstraint 名字漂移, DATA-010 ingest_tasks/kg_audit 无 FK, DATA-011 字典 yaml 路径文档不一致)

数据完整性核心矛盾: 项目已有 lookup 字典 + 6 层防御机制, 但 `accounts.role` / `buyer_profiles.status` 漏走, 形成 2 个硬编字符串孤岛; migration 跟 ORM 命名约定不统一, autogenerate 不可信; buyer_profile 整模块无 ORM model (裸 SQL), 跟项目其他 7 个 model 风格不一致, 未来加列/约束易出错。
