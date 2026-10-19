# D2: Concurrency & State 扫描结果

> 扫描时间: 2026-06-26
> Agent 角色: 偏并发视角 — 假设所有外部状态都可被并发改写
> 工具调用次数: ~39 / 30
> 找到 6 条 finding (verified: 6, refuted: 0, 待 verify: 0)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径:
  - packages/service/src/chat/service.py
  - packages/service/src/memory/* (service.py, mem0_client.py, router.py)
  - packages/service/src/ingest/api.py (tasks.py 不存在, 功能在 api.py 中)
  - packages/service/src/auth/account_service.py
  - packages/service/src/auth/account_settings_service.py
  - packages/service/src/auth/auth_invite_router.py
  - packages/service/src/auth/auth_account_router.py
  - packages/service/src/auth/auth_admin_router.py
  - packages/service/src/eval/* (router.py, runner.py, runner_registry.py, models.py)
  - packages/service/src/scheduler/* (__init__.py, deletion.py)
  - packages/service/src/core/lifespan.py
  - packages/service/src/core/permission_cache_redis.py
  - packages/service/src/permissions/service.py
  - packages/service/src/lookups/service.py, models.py
  - packages/service/src/buyer_profile/service.py
  - packages/service/src/middleware/auth.py
  - Grep session_scope 在所有 router (15+ 文件)
  - Grep OFFSET 所有使用点
  - Grep unique constraint 所有 models
- 已知跳过: packages/service/src/ingest/tasks.py 不存在 (功能在 api.py 中已覆盖); kg/tasks.py 含 threading.Lock 但不在必扫路径; 多 worker 部署场景未深入 (代码已注明不支持)
- 备注: 项目在 single-process (单 uvicorn worker) 下运行, 部分 findings 仅在 multi-worker 场景暴露, 但作为架构风险仍记录

## Findings (6 条)

- id: CONC-001
  dimension: concurrency
  severity: medium
  confidence: high
  title: "chat_hard_delete_30d cron job 缺分布式锁 / SKIP LOCKED"
  file: packages/service/src/scheduler/deletion.py
  line: 58
  description: |
    chat 30d hard-delete cron job (_run_chat_hard_delete) 通过 APScheduler 每日 03:05 执行, 但未使用分布式锁或 PG FOR UPDATE SKIP LOCKED 防止重入. 对比可发现 purge_pending_deletions (同文件 line 272) 已用 FOR UPDATE SKIP LOCKED 处理此问题, chat job 遗漏了同样的保护. 多 worker 部署下两个实例会同时执行 DELETE, 虽幂等不产生数据损坏, 但造成 DB 写放大 + 日志重复.
  evidence: |
    ```python
    # scheduler/deletion.py:58 — 无锁
    def _run_chat_hard_delete() -> None:
        # lazy import 避开 src.chat 顶层加载
        from ..chat.service import hard_delete_old_soft_deleted
        result = hard_delete_old_soft_deleted(days=30)

    # scheduler/deletion.py:47-54 — 注册 job, replace_existing=True 仅防同进程重复
    scheduler.add_job(
        _run_chat_hard_delete, "cron", hour=3, minute=5,
        id="chat_hard_delete_30d", replace_existing=True,
    )
    ```
  impact: |
    多 worker 部署下两个 cron 实例同时执行 DELETE, 虽行列级锁避免数据损坏, 但 rowcount 报告不准确, DB 连接数翻倍, 日志重复.
  fix_sketch: |
    在 hard_delete_old_soft_deleted 内加 FOR UPDATE SKIP LOCKED 保护 SELECT 待删行, 或引入 Redis 分布式锁 (SET NX EX) 确保同一时段只有一个 worker 执行.

- id: CONC-002
  dimension: concurrency
  severity: high
  confidence: high
  title: "dictionary_items 唯一约束与软删除冲突 — 软删后无法重建同 key 项"
  file: packages/service/src/lookups/models.py
  line: 84
  description: |
    dictionary_items 表定义 UNIQUE(dict_code, key), 但软删除仅设 is_active=False, 不删行. create_item 服务 (service.py:165-172) 查重时不区分 is_active, 导致软删后的 key 永远无法重建. 管理员在后台软删一条字典项后, 无法用相同 key 创建新项, 只能强行硬删或改 key 绕过.
  evidence: |
    ```python
    # models.py:84 — 唯一约束不含过滤
    __table_args__ = (UniqueConstraint("dict_code", "key", name="uq_dictionary_items_dict_code_key"),)

    # service.py:164-172 — 查重不区分 is_active
    existing = s.execute(
        select(DictionaryItem).where(
            DictionaryItem.dict_code == dict_code,
            DictionaryItem.key == payload["key"],
        )
    ).scalar_one_or_none()
    if existing:
        raise LookupSafetyError(409, f"item '{dict_code}:{payload['key']}' already exists")

    # models.py:95 — 软删仅设 is_active=False
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ```
  impact: |
    管理员无法"软删后重建同名枚举项", 必须强行硬删 (绕过安全护栏) 或改 key — 违反 lookup 字典的运维流程. 生产环境可能导致字典运维阻塞.
  fix_sketch: |
    方案 A: UNIQUE 改为 partial unique index WHERE is_active=true (PostgreSQL 支持). 方案 B: create_item 查重时加 AND is_active=true 过滤, 允许软删后重建. 需同步更新 SafetyGuard 和 seed 逻辑.

- id: CONC-003
  dimension: concurrency
  severity: medium
  confidence: medium
  title: "Eval 取消信号跨 worker 失效 — cancel_requested_at 只在启动时检查一次"
  file: packages/service/src/eval/runner.py
  line: 195
  description: |
    run_evaluation() 在启动时 (lines 195-199) 从 DB 读 cancel_requested_at 设置 asyncio.Event, 但启动后不再检查 DB 字段. 在单进程场景, 同进程内 request_cancel() 会设置 asyncio.Event 因此能正常取消. 在跨 worker 场景 (或多进程), Worker B 请求取消, 仅写入 DB cancel_requested_at, Worker A 的 asyncio.Event 未被触发, 且 Worker A 不会再读 DB, 因此取消不生效. 代码注释承认多 worker 不支持 (runner_registry.py:7), 但架构风险仍然存在.
  evidence: |
    ```python
    # runner.py:194-199 — 仅检查一次 DB
    if cancel_event is not None:
        with session_scope() as s:
            e = s.get_one(Evaluation, evaluation_id)
            if e.cancel_requested_at is not None:
                cancel_event.set()

    # runner.py:218-236 — 每题前只检查 asyncio.Event, 不再查 DB
    async def run_with_cancel_check(idx: int, item: dict) -> dict | None:
        if cancel_event is not None and cancel_event.is_set():
            return None

    # runner_registry.py:33-48 — request_cancel 写 DB + 设进程内 Event
    def request_cancel(evaluation_id: int) -> bool:
        event = _cancel_events.get(evaluation_id)
        if event is None:
            return False
        event.set()
        with session_scope() as s:
            ...

    # runner_registry.py:7 — 承认多 worker 不支持
    ⚠️ 多 worker 部署 (uvicorn --workers N) 不支持, 需换 Redis. 本 spec YAGNI 单进程.
    ```
  impact: |
    多 worker 部署下取消评估永远不生效, 评估跑完后才被发现. 单进程下仍有极短窗口 (cancel 在 running 状态设置后到达, 但样本级检查能捕获).
  fix_sketch: |
    每题前加一次 DB 轮询 cancel_requested_at (或利用 Redis pub/sub 广播取消信号). 至少应在 run_with_cancel_check 里再次读 DB, 防止长评估无法中途取消.

- id: CONC-004
  dimension: concurrency
  severity: low
  confidence: high
  title: "Evaluation.status 无 DB CHECK 约束 — 状态机靠应用层保证"
  file: packages/service/src/eval/models.py
  line: 44
  description: |
    Evaluation.status 字段定义仅为 String(20), 没有 CHECK 约束或 PG enum 限制合法值. 状态机 (pending / running / completed / failed / cancelled) 全靠应用层代码保证. 若代码 bug 写入非法值 (如 "runing"), DB 层不会拒绝. 同理, 从 running 直接跳到 pending 等非法转换 DB 也不拦截.
  evidence: |
    ```python
    # models.py:44 — 纯字符串, 无约束
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # runner.py 的状态转换
    e.status = "pending"    # line 182
    e.status = "running"    # lines 191, 213
    e.status = "cancelled"  # lines 205, 246
    e.status = "completed"  # line 267
    e.status = "failed"     # eval/router.py:247, runner_registry.py:62
    ```
  impact: |
    代码 bug 或数据迁移可能写入非法状态或执行非法状态转换, 造成前端显示异常 / 统计错误. 低严重度因为应用层实际已校验, 但数据完整性可加固.
  fix_sketch: |
    加 PostgreSQL CHECK 约束: status IN ('pending', 'running', 'completed', 'failed', 'cancelled'). 或新增 PG enum 类型.

- id: CONC-005
  dimension: concurrency
  severity: high
  confidence: high
  title: "账号注销/停用时未失效 Redis token cache — 脏缓存长达 6h"
  file: packages/service/src/auth/account_settings_service.py
  line: 167
  description: |
    request_deletion() 将 account.is_active 设为 False, 但不调用 invalidate_token() 清除 Redis 中的 token 缓存. resolve_user 在 cache hit 时 (6h sliding TTL) 直接返缓存中的 is_active=True, 已停用的账号仍可正常访问系统. 对比发现, 改邮箱 (verify_email_change) 和改密码 (change_password) 后都调用了 invalidate_token(), 唯独注销/停用没有. require_active_account 守卫依赖 resolve_user 注入的 CurrentUser.is_active, 该字段来自缓存, 因此失效.
  evidence: |
    ```python
    # account_settings_service.py:168 — 设 is_active=False, 但不失效缓存
    def request_deletion(session, account, current_password, confirm_text):
        ...
        account.is_active = False
        account.deletion_requested_at = now
        ...

    # account_settings_router.py:253-256 — 改邮箱后失效缓存 (正确做法)
    from src.core.token_cache import invalidate_token
    await invalidate_token(user.public_token)

    # account_settings_router.py:300-303 — 改密码后失效缓存 (正确做法)
    from src.core.token_cache import invalidate_token
    await invalidate_token(user.public_token)

    # middleware/auth.py:116-127 — cache hit 时不查 DB, 直接用缓存 is_active
    cached = await get_user_by_token(user_token)
    if cached is not None and cached.get("is_account"):
        if not cached.get("is_active", True):
            raise HTTPException(401, "account disabled")
        return CurrentUser(..., is_active=cached["is_active"])
    ```
  impact: |
    已注销/停用的账号最长可继续使用 6 小时 (token cache TTL). 用户预期"注销后立即失效"不满足. 安全性: 若账号被盗后 owner 申请注销, 攻击者仍可操作 6h.
  fix_sketch: |
    request_deletion() 和 set_active(False) 路径调用 invalidate_token(user_public_token) 清除 Redis 缓存. 同时确保 reset_password 和 seed-admin 路径也失效旧 token (已有的部分失效点保留).

- id: CONC-006
  dimension: concurrency
  severity: low
  confidence: medium
  title: "buyer_profile 分页用 OFFSET + updated_at DESC — 更新导致页码漂移"
  file: packages/service/src/buyer_profile/service.py
  line: 186
  description: |
    buyer_profile list 使用 OFFSET 分页, ORDER BY updated_at DESC. 当某条 buyer_profile 在分页查询期间被更新 (updated_at 刷新), 其排序位置会移动, 导致后续页码出现行跳过或重复. 这是典型的 OFFSET 漂移问题, 但 buyer_profile 是用户个人数据 (按 account_id 过滤), 并发更新概率低, 且前端通常一次性展示, 故低严重度.
  evidence: |
    ```python
    # service.py:186 — OFFSET + updated_at DESC
    data_q = f"SELECT * FROM buyer_profiles WHERE {where} ORDER BY updated_at DESC LIMIT :lim OFFSET :off"
    with session_scope() as sess:
        total = sess.execute(text(count_q), params).scalar() or 0
        rows = sess.execute(text(data_q), params).mappings().all()
    ```
  impact: |
    分页查看画像时, 如果某条被修改 (status/字段变更), 其 updated_at 跳到最新, 移动到下一页/上一页, 造成行重复或遗漏. 前端可能展示重复数据或漏项.
  fix_sketch: |
    改为游标分页 (cursor-based): 用 (updated_at, id) 做 WHERE 条件替代 OFFSET. 参考 chat/service.py:78-130 已实现的游标分页模式.

## 未扫 / 已知缺口

- **packages/service/src/ingest/** — tasks.py 不存在, 扫描了 api.py 中的 finalize_upload/add_task FOR UPDATE 模式. ingest pipeline (process_uri/process_path) 未深入 (非并发敏感).
- **packages/service/src/kg/tasks.py** — 含 threading.Lock 用于串行化知识图谱构建, 但不在必扫路径内, 未审计锁设计的正确性.
- **packages/service/src/approvals/** — 未扫描, 但 approval 提交流程是写操作并发敏感. 留给后续审计.
- **packages/service/src/product_decoders/** — config_loader 有进程内 _cache, 未审计并发安全.
- **Multi-worker/分布式部署** — 代码多处假设单进程 (asyncio.Event 作取消信号, 进程内 APScheduler, 进程内存 cache), 若后续扩展需整体审计.
- **测试代码中的 session_scope 使用** — 未扫描 tests/ 目录, 但模式 2 集成测试的 db_session fixture 可能在事务外暴露并发问题.
