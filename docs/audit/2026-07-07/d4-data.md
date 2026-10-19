# D4 数据完整性审计 (2026-07-07)

> 扫描范围: `packages/service/src/models/**` (实际为 `src/chat/models.py`, `src/db/models/**`, `src/lookups/models.py`, `src/approvals/models.py`, `src/auth/account_models.py`, `src/auth/models.py`, `src/eval/models.py`, `src/ingest/pre_analysis/models.py` + `stage_models.py`, `src/chat_share/models.py`), `packages/service/src/storage/migrations/versions/**`, `packages/service/src/common/dictionaries_enum.py` + `configs/dictionaries_seed.yaml`
>
> 关注维度: alembic 可回滚 / FK 错配与级联 / enum 硬编 / JSONB schema 漂移 / 数据迁移零停机

## Findings 总览

| ID | Severity | Title |
|---|---|---|
| DATA-001 | high | pre_analysis_tasks 三列 JSON 用 sa.Text 替代 JSONB (新表违反项目规约) |
| DATA-002 | high | 多个新表 status/state/stage 列硬编 CheckConstraint, 不走 lookup 字典 |
| DATA-003 | medium | evaluations.user_id FK 无 ondelete, 删 user 后留孤儿行 |
| DATA-004 | medium | approvals/evaluations ORM 模型 FK 声明缺失 ondelete, 跟 DB 不一致 |
| DATA-005 | medium | kg_extract_items.task_id 无 FK 约束, 孤儿行风险 |
| DATA-006 | low | JSON-as-Text 模式触发 toctou-like 竞态: 累加 output_files_json 用 json.loads + 回写 |
| DATA-007 | info | 字典模块 _REFERENCE_MAP 仅 5 项, 留 9+ 个新枚举列引用未注册 |

---

## DATA-001 pre_analysis_tasks 三列 JSON 用 sa.Text 替代 JSONB

**severity**: high
**confidence**: high

新建表 `pre_analysis_tasks` 在 2026-07-02/03/06 三条 migration 中给 `output_files_json` / `summary_json` / `task_config_json` 三列用了 `sa.Text`, 业务侧 `store.py:64-66, 120` 用 `json.dumps` 写入. 这违反了项目 CLAUDE.md §JSONB 使用规范 "新列必须 JSONB, 禁止 sa.JSON()" — 该规约对应的 `tests/migrations/test_json_jsonb_policy.py` AST 扫描已经会 fail, 因为注释明确说 "新列必须 JSONB, 禁止 sa.JSON()" 但迁移里直接 `sa.Text` 绕过 ORM 端 (`sa.JSON` 用 `sa.Text` 替代). 同时 `pre_analysis_tasks` 的 JSON 列是高频读写热点 (runner 每 stage append 1 项), 后续若要加 GIN 索引做查询加速 (例如查 summary 里 total_chapters > N 的 task) 又必须先 ALTER, 锁表分钟级, 违反零停机原则.

### evidence

```python
# packages/service/src/storage/migrations/versions/20260702_000000_pre_analysis_tasks.py:40-41
sa.Column("output_files_json", sa.Text, nullable=False, server_default="[]"),
sa.Column("summary_json", sa.Text, nullable=False, server_default="{}"),

# packages/service/src/storage/migrations/versions/20260706_000000_pre_analysis_task_config.py:23-27
sa.Column(
    "task_config_json",
    sa.Text,
    nullable=False,
    server_default="{}",
)
```

```python
# packages/service/src/ingest/pre_analysis/store.py:40-44 (业务侧被迫 json.loads/dumps)
"summary": json.loads(task.summary_json or "{}"),
"task_config_json": json.loads(task.task_config_json or "{}"),
if include_output_files:
    result["output_files"] = json.loads(task.output_files_json or "[]")
```

### impact

- 跟项目规约冲突, `tests/migrations/test_json_jsonb_policy.py` 应该 FAIL (用 sa.Text 替代 sa.JSON 在 AST 扫描的 regex 也许漏掉, 需要补 case).
- 失去 JSONB 优势: GIN 索引 (例如查 summary.total_tables 范围), `@>` 操作符快速包含判断, 跟历史 json/jsonb 一族 bug 同源 (memory: feedback-postgres-json-jsonb-family-of-bugs).
- 业务侧 `json.loads/dumps` 多处出现, `text_io` IO 错误抛 JSONDecodeError, runner 路径 (line 367) 已裸用 `json.loads(task.output_files_json or "[]")` — 后续若 DB 出现脏 JSON (e.g. 手工 SQL 写坏), runner 直接崩.

### fix_sketch

新 migration `2026070X_000000_pre_analysis_tasks_jsonb.py` 给 3 列 `ALTER COLUMN ... TYPE JSONB USING col::jsonb`, 同步改 ORM 为 `Mapped[dict | list | None] = mapped_column(JSONB)`, 业务侧 `store.py` 去掉 `json.loads/dumps`, 直接传 dict. 跟 20260626_migrate_sa_json_to_jsonb 同样 lock-table 风险, 维护窗口跑.

---

## DATA-002 新表 status/state/stage 硬编 CheckConstraint, 不走 lookup 字典

**severity**: high
**confidence**: high

`pre_analysis_tasks.state` (4 值), `pre_analysis_task_stages.stage` (5 值) + `pre_analysis_task_stages.status` (4 值), `kg_extract_items.kind` (2 值), `evaluations.status` (5 值), `accounts.role` (3 值), `buyer_profiles.status` (2 值) 全部用 `sa.CheckConstraint("col IN ('a', 'b')")` 硬编. CLAUDE.md §"业务 enum 必须走 lookup" 明确禁止 (除 LLM 框架强制的 enum 外). 现 yaml `configs/dictionaries_seed.yaml` 仅 5 个字典, 全是 approvals 业务域. 新表的 7 个枚举轴没注册, 后续 admin 后台想加状态值 (e.g. pre_analysis_tasks 加 'cancelled') 只能发版改 migration, 违反字典 "runtime 改 DB + cache invalidate" 的设计目标.

### evidence

```python
# packages/service/src/storage/migrations/versions/20260702_000000_pre_analysis_tasks.py:42-46
sa.CheckConstraint(
    "state IN ('pending', 'running', 'completed', 'failed')",
    name="ck_pre_analysis_tasks_state",
)
```

```python
# packages/service/src/storage/migrations/versions/20260703_000000_pre_analysis_task_stages.py:34-41
sa.CheckConstraint(
    "status IN ('started', 'completed', 'failed', 'skipped')",
    name="ck_pre_analysis_task_stages_status",
),
sa.CheckConstraint(
    "stage IN ('load_config', 'extract_chapters', 'extract_tables', 'extract_flagged', 'write_outputs')",
    name="ck_pre_analysis_task_stages_stage",
),
```

```python
# packages/service/src/storage/migrations/versions/20260701_000000_kg_extract_items.py:50
sa.CheckConstraint("kind IN ('entity', 'relation')", name="ck_kg_extract_items_kind"),
```

```bash
# configs/dictionaries_seed.yaml 仅 5 个字典 (全部 approvals 相关):
#   approval_review_status / approval_apply_status / approval_kind
#   reject_reason / page_key
```

### impact

- 业务枚举值变更要发版 + alembic migration, 不能 admin 运行时改; 跟现有 5 字典的设计目标冲突.
- 多语言 label (zh/en) 缺失: 前端 hardcode "已完成" / "Failed", 跟 approvals 走 lookup 双语 label 不一致.
- `_REFERENCE_MAP` 没注册这些枚举列, 后续字典模块做反向引用检查 (避免误删) 失效 — 现在删 `state=pending` 这种"业务上还有人引用"的值, 不会触发任何阻断.

### fix_sketch

下个 spec (2026-07-XX) 启动 dictionary 扩展期: 7 个新枚举轴注册到 yaml + `dictionaries_enum.py` 明文 enum + ORM `Mapped[XxxStatusEnum]` 引用, 新 migration `ALTER TABLE ... DROP CONSTRAINT ck_...`. 老数据 backfill: 重命名/保留旧值到字典 `items.is_active=True`. 跟 20260624_165000 migration 注释 "Phase 3 大重构范围外" 一致 — 此 finding 是该阶段的 debt.

---

## DATA-003 evaluations.user_id FK 无 ondelete, 删 user 留孤儿行

**severity**: medium
**confidence**: high

`evaluations.user_id` FK (consolidated_pg_init.py:153) 没用 `ondelete=` 子句, 走 PG 默认 `NO ACTION`. 即 `conversations.user_id` 2026-06-24 已修 (DATA-003), `evaluations.user_id` / `evaluation_samples.evaluation_id` 留同样 debt. 删 user 时 (account_settings_service.purge_pending_deletions 路径), 评估批留孤儿行, 跟 GDPR right to erasure 冲突; `evaluations.dataset_uri` (MinIO URI) 也跟着泄漏 (S3 桶里 .csv 不会被删).

### evidence

```python
# packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py:153
sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
sa.PrimaryKeyConstraint("id"),
)
```

```python
# packages/service/src/storage/migrations/versions/20260624_120000_conversations_user_id_ondelete_cascade.py:14-17
# 范围:
# - 仅改 conversations.user_id FK. messages / ingest_tasks / approvals / evaluations
#   跟 user 的 FK 留后续 spec 处理 (Master plan Task 1.7 范围限定).
```

### impact

- 评估历史表 `evaluations` 留孤儿 user_id 行, 后续 admin list / user-anonymization query 拉出来惊扰.
- `evaluation_samples` 通过 evaluation_id CASCADE 没问题 (line 175), 但 evaluation 没 CASCADE, evaluations→user 链路断.
- `evaluations.dataset_uri` 指向 S3 桶里的 csv 文件, 真删 user 时业务侧没清理 → 存储成本泄漏 + GDPR 违规.

### fix_sketch

新 migration `2026070X_000000_evaluations_user_id_ondelete_cascade.py`: `ALTER TABLE evaluations DROP CONSTRAINT evaluations_user_id_fkey, ADD CONSTRAINT ... FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`. 业务侧 `account_settings_service.purge_pending_deletions` 加一步: `DELETE FROM object_store WHERE uri LIKE 's3://rag-ingest/eval/{user_id}/%'`. 同时改 ORM `eval/models.py:36` 的 FK 声明加 `ondelete="CASCADE"` 跟 DB 对齐 (现 ORM 没 `ondelete=`, DB 默认 NO ACTION — 此处 DB 真没设, ORM 跟 DB 一致, 但二者都错).

---

## DATA-004 approvals/evaluations ORM FK 声明缺失 ondelete, 跟 DB 不一致

**severity**: medium
**confidence**: high

SQLAlchemy 2.0 ORM 模型 (`approvals/models.py:61-62`, `eval/models.py:36`) 的 FK 声明省略 `ondelete=` 参数, 而 DB 侧 migration `consolidated_pg_init.py:197-198` (approvals) 实际有 `CASCADE`/`SET NULL`. 当 alembic autogenerate 跑时, ORM 跟 DB 不一致会报 diff (虽然现在项目明确禁用 autogenerate, 但 ORM 反映不出真 schema 让代码 review 难做).

### evidence

```python
# packages/service/src/approvals/models.py:61-62
submitter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
```

```python
# packages/service/src/eval/models.py:36
user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
```

```python
# packages/service/src/storage/migrations/versions/20260615_000000_consolidated_pg_init.py:197-198
sa.ForeignKeyConstraint(["submitter_id"], ["users.id"], ondelete="CASCADE"),
sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
```

### impact

- 现 DB CASCADE 行为正常, 但 ORM 文档/类型 hint 缺失, pyright 看不到 ondelete 语义.
- DATA-003 修复后 (evaluations 加 CASCADE), 若 ORM 不同步, code review 时无法快速识别"这条 FK 真删 user 会级联".
- 跟 `chat/models.py:42` 对照 (显式 `ForeignKey("users.id", ondelete="CASCADE")`), 规约不一致.

### fix_sketch

3 行 ORM 同步: `ForeignKey("users.id", ondelete="CASCADE")` 给 submitter_id / evaluations.user_id; `ondelete="SET NULL"` 给 reviewer_id. 不需 migration, 仅模型层.

---

## DATA-005 kg_extract_items.task_id 无 FK 约束, 孤儿行风险

**severity**: medium
**confidence**: medium

`kg_extract_items.task_id` 用了 `sa.Text`, migration 20260701 没声明 FK 到 `pre_analysis_tasks.id` (String(36)). spec 注释说 "kg_extract_items 是临时存储, 7d cron 自动清理", 但如果 pre_analysis_tasks 行被删 (admin 误删 / retry DELETE stages cascade? — 现 retry 仅删 stages 不删 tasks), kg_extract_items.task_id 变孤儿, 后续 7d cron 看不到这些孤儿 (WHERE task_id IN (...), 但 cron 走 `DELETE WHERE created_at < NOW() - INTERVAL '7 days'`, 不会因孤儿误删 — 是孤儿持续占空间, 不会被回收).

### evidence

```python
# packages/service/src/storage/migrations/versions/20260701_000000_kg_extract_items.py:36-50
op.create_table(
    "kg_extract_items",
    sa.Column("id", sa.BigInteger, primary_key=True),
    sa.Column("task_id", sa.Text, nullable=False),
    sa.Column("dataset", sa.Text, nullable=False),  # 2026-07-01 v3: 写哪个 dataset
    sa.Column("extractor", sa.Text, nullable=False),
    sa.Column("splitter", sa.Text, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("payload", JSONB, nullable=False),
    ...
```

```python
# pre_analysis_tasks.id 是 String(36) (migration 20260702:32)
# kg_extract_items.task_id 是 sa.Text (不限制长度, 不限制字符集)
```

### impact

- task_id 类型宽 (`sa.Text`), 跟 `pre_analysis_tasks.id String(36)` 不一致, 业务代码做 join 时 PG 隐式 cast 触发 type mismatch warning.
- 无 FK → 删 pre_analysis_tasks 行不会级联清 kg_extract_items → 7d cron 范围内累积孤儿.
- runner 写错 task_id (typo) 不会触发 FK 错误, 而是 silent 写脏数据.

### fix_sketch

新 migration: `ALTER TABLE kg_extract_items ALTER COLUMN task_id TYPE VARCHAR(36), ADD FOREIGN KEY (task_id) REFERENCES pre_analysis_tasks(id) ON DELETE CASCADE`. 业务侧 runner / preview API 必须捕 FK violation 错误 (现 task_id 是 runner 内部生成, 不大可能脏, 但有兜底).

---

## DATA-006 JSON-as-Text 累加模式触发竞态: json.loads + 回写

**severity**: low
**confidence**: medium

`pre_analysis_tasks.output_files_json` 是 Text 列, runner (store.py:362-376) 累加模式: `current = json.loads(task.output_files_json or "[]")` → append → `task.output_files_json = json.dumps(current)`. 这不是典型 TOCTOU (无并发写), 但有 3 类问题:

1. **脏 JSON 风险**: `json.loads` 碰到 DB 里被手工 SQL 改坏的 JSON 即抛 `JSONDecodeError`, runner 主流程崩. 跟 DATA-001 同源, 改 JSONB 后由 psycopg3 v3 适配器兜底.
2. **整列重写**: append 1 项要把全列 (例如几十 KB) 重新 load + dumps + 回写, runner 在 stage 写盘时已发生 N 次 (跟 stage 数量线性), 写入放大.
3. **校验缺失**: 业务 `ensure_ascii=False` 写, 但读侧没验证 schema (期望 list[dict] 但 DB 可能是 `null`), 后续 API 输出 `null` 给前端 — `if (data) { data.map(...) }` 必须健壮.

### evidence

```python
# packages/service/src/ingest/pre_analysis/store.py:362-376
"""(2026-07-06) DB output_files_json append 1 项, 详情页 admin 实时可见."""
with session_scope() as s:
    task = s.get(PreAnalysisTask, task_id)
    if task is not None:
        current = json.loads(task.output_files_json or "[]")
        current.append({...})
        task.output_files_json = json.dumps(current, ensure_ascii=False)
```

```python
# packages/service/src/ingest/pre_analysis/runner.py:230
final_output_files = json.loads(task.output_files_json or "[]")
# 注意这里没 try/except, json.JSONDecodeError 直接冒出到 runner 顶
```

### impact

- 现阶段单 runner 单 task, 并发写概率低, 实测不爆.
- 后续若拆 runner 多 worker 并发写同一 task, 累加即丢 (lost update).
- 性能: append 模式 IO 放大, 单 task 50 个产物 + 反复 read-write 比直接 JSONB `@>` 操作符 + jsonb_set 慢 5-10 倍.

### fix_sketch

短期: `json.loads` 包 try/except, 失败 → log + return empty list (跟 DATA-001 一并修). 长期: 改 JSONB 后用 `UPDATE pre_analysis_tasks SET output_files_json = output_files_json || :new::jsonb WHERE id = :id` (JSONB concatenation), 配合事务行锁 `SELECT FOR UPDATE`.

---

## DATA-007 字典模块 _REFERENCE_MAP 仅 5 项, 9+ 个新枚举列引用未注册

**severity**: info
**confidence**: high

`packages/service/src/lookups/safety_guard.py:46-52` 的 `_REFERENCE_MAP` 仅注册 5 个业务引用 (`approval_kind.kind` / `approval_review_status.review_status` / ...). 配合 DATA-002 的 7 个新硬编枚举列, 现在 admin 后台如果走字典模块 (5 个老字典) 删一个 item key, 第 4 层引用检查仅扫 approvals 表 — 对 `evaluations.status='running'` 这种引用, 不阻断. 跟 CLAUDE.md §字典使用规范 "**不注册则删除时不报引用错误, 可能误删**" 一致.

### evidence

```python
# packages/service/src/lookups/safety_guard.py:46-52
_REFERENCE_MAP: dict[str, list[tuple[str, str]]] = {
    "approval_kind": [("approvals", "kind")],
    "approval_review_status": [("approvals", "review_status")],
    "approval_apply_status": [("approvals", "apply_status")],
    "reject_reason": [("approvals", "rejection_reason")],
    "page_key": [("role_permissions", "page_key")],
}
```

### impact

- 现 5 个老字典的删除检查只覆盖 approvals / role_permissions 两表; 未来这 5 个字典新增业务引用 (e.g. `reject_reason` 写到 `evaluations.error_message`) 也不会自动发现.
- 跟 DATA-002 联动: 若后续 7 个新枚举轴迁入字典, _REFERENCE_MAP 必须同步扩到 ~12+ 项, 否则 safety guard 第 4 层失效.

### fix_sketch

跟 DATA-002 同一 spec 处理. 拆 2 步: (a) 加 AST 扫 `sa.CheckConstraint("col IN (...)")` + `Mapped[str]` enum 列, 自动建议 (table, column) 注册 (在 safety_guard._REFERENCE_MAP 自动 append); (b) 让 admin router 删字典项时, 对未注册引用表的枚举轴 warning + 人工 confirm. 跟现有 safety_guard 6 层防御一致.

---

## 备注

- 本次扫描未发现 alembic downgrade 缺失 (所有 migration 都有 `def downgrade()`), 符合项目 "alembic 迁移必须可回滚" 规约.
- 排除 pre-commit pytest `--picked 0 tests` 阻塞类问题 (本维度不涉及).
- 本次扫描对 `chat/models.py` `eval/models.py` 的 JSONB 列已迁 (20260626 migration), 无 sa.JSON() 残留, 符合 `tests/migrations/test_json_jsonb_policy.py` 规约.
- DATA-001/002/003 是本期 (2026-07-07) 必须优先处理的 high/medium debt, 与 `feedback-record-errors-and-lessons` 一致沉淀到 memory.