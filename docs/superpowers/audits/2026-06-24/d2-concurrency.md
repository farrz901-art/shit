# D2: Concurrency & State 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: D2 Concurrency & State 扫描 agent
> 工具调用次数: 24
> 找到 9 条 finding

## 元信息

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/`
- 扫描路径:
  - `packages/service/src/chat/service.py` (主战场)
  - `packages/service/src/memory/` (全部)
  - `packages/service/src/ingest/api.py` (BackgroundTask)
  - `packages/service/src/scheduler/deletion.py`
  - `packages/service/src/auth/account_settings_service.py`
  - `packages/service/src/auth/auth_invite_router.py`
  - `packages/service/src/eval/runner.py` + `runner_registry.py`
  - `packages/service/src/middleware/auth.py` (token cache race)
  - `packages/service/src/buyer_profile/service.py` + `change_notifier.py` (JSONB RMW)
  - `packages/service/src/approvals/router.py` (BackgroundTask)
- 已知跳过:
  - 业务 enum/lookup 走字典的事实源正确, 不属于本维度
  - 单测试模式 1/2/4 不直接相关
  - 第三方 SDK 内部 race (mem0 / OpenAI) 不在管控内, 只关注我们的 wrapper

## Findings (9 条)

---

- id: CON-001
  dimension: concurrency
  severity: critical
  confidence: high
  title: "invite redeem 双重验证的 TOCTOU, 可创两个同 email Account"
  file: packages/service/src/auth/auth_invite_router.py
  line: 115
  description: |
    redeem_invite 流程是 `_validate_invite(token)` 单独 session (读) → 关闭 session → 第二个 session 创 Account + Invite.redeemed_at=NOW(). 
    两次 DB 操作之间存在窗口: 两个并发请求同时通过 `_validate_invite` 校验 (同一 session_scope() 各自干净读, 都没看到 redeemed_at 被改), 然后都进入第二个 session_scope(). 
    accounts.email 有 unique 约束, 但 PG 报错会以 IntegrityError 形式抛到客户端, 不会被业务翻译为"邀请已用".
  evidence: |
    ```python
    # auth_invite_router.py:115-148
    inv = _validate_invite(token)  # session 1 关闭, 只读校验
    ...
    with session_scope() as s:    # session 2 才是写
        if s.query(Account).filter_by(email=inv.email).first() is not None:
            raise HTTPException(status_code=409, detail="email already registered")
        account = Account(...)
        s.add(account)
        s.flush()
        s.refresh(account)
        user = User(...)
        s.add(user)
        s.flush()
        # 标 invite 已用
        inv_db = s.get(Invite, inv.id)
        inv_db.redeemed_at = datetime.now(HKT)
        inv_db.account_id = account.id
        s.flush()
    ```
  impact: |
    高概率 - 在网络抖动或多 tab 兑换同一邀请时, 第一个请求和第二个请求会同时通过 _validate_invite, 然后第二个 session 写入时撞 accounts.email unique 约束. 客户端会看到 500 (IntegrityError), 但同时第一个 session 的 transaction 已经成功 commit. 攻击者主动制造并发甚至可以: 让 invite 标记为"已用"两次 (虽然 s.refresh 之后写会被 PG 拒绝, 但 s.flush() 时不会, 业务层面没显式处理).
  fix_sketch: |
    把 redeem 整体放进单个 session_scope 内, 入口用 `SELECT ... FOR UPDATE` 锁 invite 行 (或 PG advisory lock on token hash), 然后在锁内做 email 重检 + Account 创 + User 创 + Invite 标 used. 单事务, 并发安全.
  references: []

---

- id: CON-002
  dimension: concurrency
  severity: critical
  confidence: high
  title: "cancel_deletion 标记所有 DeletionRestore.used_at 缺锁, 并发请求可能漏标"
  file: packages/service/src/auth/account_settings_service.py
  line: 188
  description: |
    cancel_deletion 在第二个 session 里把 account_id 下所有 used_at=None 的 DeletionRestore 标 used. 该查询 + UPDATE 序列没有任何行锁, 两个并发请求都查到 N 条未用 restore token, 都尝试 `dr.used_at = NOW()`, 后写覆盖前写, 但如果有第三个请求 (request_deletion) 在中间又新插了 token, 就会被漏掉 (committed 之后才 SELECT, 看不到).
  evidence: |
    ```python
    # account_settings_service.py:188-199
    def cancel_deletion(session, account: Account, current_password: str) -> None:
        if not account.is_pending_deletion:
            raise ValueError("account is not pending deletion")
        if not verify_password(current_password, account.password_hash):
            raise ValueError("invalid current password")
        account.is_active = True
        account.deletion_requested_at = None
        # 标所有未用的 DeletionRestore token 为 used (单选一次就行, 全部标)
        for dr in session.query(DeletionRestore).filter_by(account_id=account.id, used_at=None).all():
            dr.used_at = datetime.now(HKT)
        session.flush()
    ```
  impact: |
    中等 - 业务上 "取消" 本质是状态翻转 (is_active=True), 即便 token 漏标也只意味着"老的 restore token 仍可用". 但攻击者拿到旧 token 后能再次"还原", 制造出混乱. 真实风险: cron purge_pending_deletions 跟 cancel 并发时, 已翻转 is_active=True 的 account 仍可能被 cron 当成 victim (cron 查的是 deletion_requested_at < cutoff, 不查 is_active), 删除一个已经"撤销注销"的账号.
  fix_sketch: |
    1) cancel_deletion 走单 session 锁 Account 行 (SELECT ... FOR UPDATE) 后再读 DeletionRestore 列表. 
    2) cron purge_pending_deletions 加 `AND is_active = FALSE` 过滤, 防止撤销但 cron 误删. 
    3) request_deletion 跟 cancel_deletion 互斥 (同一 account_id 用 advisory lock).
  references: []

---

- id: CON-003
  dimension: concurrency
  severity: high
  confidence: high
  title: "verify_email_change 的 new_email 二次校验, 存在 TOCTOU 竞态"
  file: packages/service/src/auth/account_settings_service.py
  line: 121
  description: |
    verify_email_change 在事务内查 Account.email == change.new_email, 不存在时切换 account.email. 该 SELECT 跟 UPDATE 之间无行锁, 两个并发请求都通过"new_email 仍可用"校验, 都尝试写入, accounts.email unique 约束会拒绝第二个, 但抛出 IntegrityError 而非业务 409, 给用户看到的是 500.
  evidence: |
    ```python
    # account_settings_service.py:121-142
    def verify_email_change(session, token: str) -> dict:
        change = session.query(EmailChange).filter_by(token=token).first()
        if change is None or change.used_at is not None:
            raise ValueError("invalid or used token")
        ...
        if expires_aware < datetime.now(HKT):
            raise ValueError("token expired")
        # 二次校验 new_email 仍可用 (race)
        dup = session.query(Account).filter(Account.email == change.new_email, Account.id != change.account_id).first()
        if dup is not None:
            raise ValueError("email already in use")
        account = session.get(Account, change.account_id)
        assert account is not None
        account.email = change.new_email
        change.used_at = datetime.now(HKT)
        session.flush()
    ```
  impact: |
    中等 - 概率低 (同 email 邮箱在极短时间内被两个 token 验证), 但客户端会拿到 500 (IntegrityError), 不是 409 "email already in use". 改 1 行修复, 收益高.
  fix_sketch: |
    在事务开头 SELECT Account 旧行 FOR UPDATE 锁住 (防止别人改 account.email); 改完 release. 或者用 PG INSERT ... ON CONFLICT 模式在 application 层处理 IntegrityError → 409.
  references: []

---

- id: CON-004
  dimension: concurrency
  severity: high
  confidence: high
  title: "buyer_profile update_profile_fields 跨多 session 缺锁, JSONB 并发写入会丢字段"
  file: packages/service/src/buyer_profile/service.py
  line: 63
  description: |
    update_profile_fields 流程: get_profile (session 1, 读) → in-memory merge → 写回 (session 3, 写). 中间跨 session + 跨多 session 之间, 两个并发请求都读同一个 profile_data, 都 in-memory 各自加新字段, 后写覆盖前写, 丢字段. fire-and-forget (BackgroundTasks) 调用 try_extract 进一步加剧.
  evidence: |
    ```python
    # service.py:78-143
    existing = ProfileService.get_profile(account_id, buyer_key)  # session 1: SELECT
    ...
    current_data = dict(existing.get("profile_data") or {})
    for code, value in fields.items():
        current_data[code] = {  # 内存 merge
            "value": value,
            "confidence": "high" if value else "medium",
            "source": "auto",
            "updated_at": now,
        }
    changes = detect_changes(...)
    log_changes(...)  # session 2: 单独事务 INSERT 变更日志
    ...
    with session_scope() as sess:  # session 3: UPDATE
        r = sess.execute(text(query), params)
    ```
  impact: |
    高 - ProfileService.try_extract 是 fire-and-forget BackgroundTask (memory/router.py:114), 高频触发; 两个 chat 并发 (同一 user 同一 buyer_key) 同时抽到不同字段时, 一个的更新会覆盖另一个. 表现为"用户看到字段消失/回退". 同时 change_notifier.log_changes 是单条 INSERT 单事务, 不与 UPDATE 同事务, 异常时日志丢.
  fix_sketch: |
    1) 整个 update_profile_fields 走单 session. 2) 写回 profile_data 改 `profile_data = profile_data || :new_fields::jsonb` (PG JSONB concat operator, 原子). 3) detect_changes 移到 UPDATE 之前, 用 returning 拿旧值算 diff.
  references: []

---

- id: CON-005
  dimension: concurrency
  severity: high
  confidence: medium
  title: "run_evaluation 跑题期间 cancel_event 状态无持久化, 进程重启后无法恢复"
  file: packages/service/src/eval/runner.py
  line: 158
  description: |
    run_evaluation 用 asyncio.Semaphore + asyncio.gather 跑并发评估. 中途: (a) cancel_event 触发后, 任务标记 status='cancelled' 写入 DB; (b) 进程崩溃 / OOM / 重启 → runner_registry.recover_orphaned_running 把所有 status='running' 标 failed. 但已经写完的 EvaluationSample (单条 INSERT) 在崩溃前已 commit, Evaluation 状态却变 'failed', 出现 "samples 已落库 + 总表说失败" 的不一致. 前端轮询看到 failed 但 samples 列表不为空.
  evidence: |
    ```python
    # runner.py:230-243
    tasks = [run_with_cancel_check(i, item) for i, item in enumerate(dataset)]
    results = await asyncio.gather(*tasks)

    # 5. 取消 → 终止 (results 里 None 是被取消的)
    if cancel_event is not None and cancel_event.is_set():
        sample_results = [r for r in results if r is not None]
        with session_scope() as s:
            e = s.get_one(Evaluation, evaluation_id)
            e.status = "cancelled"
            e.successful = sum(1 for r in sample_results if r["error"] is None)
            e.failed = sum(1 for r in sample_results if r["error"] is not None)
            e.finished_at = datetime.now(HKT)
            e.duration_seconds = time.perf_counter() - start
        return evaluation_id
    ```
    配套的 recover_orphaned_running (runner_registry.py:47-61) 不统计 samples, 不知道完成到第几条.
  impact: |
    中 - 数据完整性问题, 不会丢数据, 但 evaluation 终态与 samples 数量不一致. 前端 / 报告展示时可能误导 (报告说失败, 但 samples 表里有部分结果).
  fix_sketch: |
    recover_orphaned_running 跑前先 `SELECT count(*) FROM evaluation_samples WHERE evaluation_id=X`, 算 successful/failed 后再标 failed + 写"中断恢复"备注. 或者引入 evaluation_samples 数量 == total_samples 才允许标 completed.
  references: []

---

- id: CON-006
  dimension: concurrency
  severity: high
  confidence: medium
  title: "_run_ingest 跟 finalize_upload 状态变更, 重入或重发会重复跑"
  file: packages/service/src/ingest/api.py
  line: 358
  description: |
    finalize_upload 校验 t.state == 'queued' 后, background.add_task(_run_ingest). _run_ingest 自己又 _save(t) 翻 running. 两个并发的 finalize_upload 请求 (用户连点 / 重试按钮), 都能过 state==queued 校验, 都 add_task, 跑两次 _run_ingest. 同时 _run_ingest 读 t = _load(task_id) 拿对象, 跟 finalize_upload 不在同 session, 状态机不在原子操作里.
  evidence: |
    ```python
    # api.py:358-372
    async def finalize_upload(
        req: FinalizeUploadRequest,
        current: CurrentUser = Depends(require_page("output")),
        background: BackgroundTasks = BackgroundTasks(),
    ) -> FinalizeUploadResponse:
        token = _check_token(current)
        uhash = user_hash_for(token)
        t = _resolve_task(req.task_id, uhash)
        if t.state != "queued":
            raise HTTPException(409, detail=f"task 状态错误: {t.state}")
        workdir_uri = t.work_dir
        assert workdir_uri is not None
        background.add_task(_run_ingest, t.id, workdir_uri)
        return FinalizeUploadResponse(task_id=t.id, state="running")

    # _run_ingest (api.py:480-488)
    t = _load(task_id)
    if t is None:
        return
    t.state = "running"
    _save(t)
    ```
  impact: |
    中 - 用户重复点"开始处理"按钮 → 同一 task 跑两次 pipeline, 写两遍 KG / embedding, 数据重复; 第一次跑完翻 'completed' 后, 第二次 _run_ingest 启动翻 'running' 把状态倒回去, UI 体验坏.
  fix_sketch: |
    finalize_upload 在 SELECT 后立刻 UPDATE state='running' (单 SQL, 原子), 影响行数 0 → 返回 409. 状态机变更和 add_task 都在事务内.
  references: []

---

- id: CON-007
  dimension: concurrency
  severity: medium
  confidence: high
  title: "chat list_conversations 期间 offset 漂移, 新建对话会跳号"
  file: packages/service/src/chat/service.py
  line: 73
  description: |
    list_conversations 用 LIMIT/OFFSET 分页, ORDER BY updated_at DESC. 用户在分页滚动期间新建一个 conv (会刷新所有已有 conv 的 updated_at 吗? 不会, 但新建的 conv updated_at=NOW() 排到第一). 用户拉第 2 页时, 第 1 页里"刚出现的最新 conv"挤到第 1 页第 1 位, 第 1 页第 20 位的 conv 移到第 2 页第 1 位, 用户看到的第 2 页第 1 条跟第 1 页第 20 条重复.
  evidence: |
    ```python
    # service.py:73-99
    def list_conversations(user_id: int, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = s.execute(
                text("""
                    SELECT id, title, message_count, created_at, updated_at
                    FROM conversations
                    WHERE user_id = :uid AND deleted_at IS NULL
                    ORDER BY updated_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"uid": user_id, "limit": limit, "offset": offset},
            ).fetchall()
    ```
  impact: |
    中 - 用户体验 bug, 不是数据损坏. 跟 ChatGPT 等产品同模式, 通常接受; 但无限滚动 + 新建对话组合必触发.
  fix_sketch: |
    用 cursor-based 分页 (keyset pagination): 传上一页最后一条的 updated_at + id, 走 `WHERE (updated_at, id) < (last_updated_at, last_id) ORDER BY updated_at DESC, id DESC LIMIT 20`. 性能更好且无漂移.
  references: []

---

- id: CON-008
  dimension: concurrency
  severity: medium
  confidence: medium
  title: "resolve_user token cache 写入 fire-and-forget, 短时窗口内 401 vs 200 闪烁"
  file: packages/service/src/middleware/auth.py
  line: 162
  description: |
    resolve_user 走 PG 拿到 account 之后, asyncio.create_task(cache_user_by_token(...)) 异步写 Redis. 紧接的第二次请求 (毫秒内) 拿不到 cache 还在走 PG, 但 cache 写入可能在 PG 查询跟第二次请求的 cache 读之间 race 完成. 表面看无 bug, 但若 cache 写失败 (Redis 挂), facade 静默吞, 用户第二次还走 PG, 永远不进 cache. 更严重的: is_active 字段刚变 False (用户被 disable) 时, 已 cache 的旧值 6h 内仍返 200, 跟 PG 不一致. 注释提到 6h sliding TTL, 但 disable 后没有 invalidate.
  evidence: |
    ```python
    # auth.py:158-174
    if not account.is_active:
        raise HTTPException(401, "account disabled")

    # 异步写 cache (fire-and-forget, 失败不影响响应, Redis 挂时 safe_set 返 False 不抛)
    asyncio.create_task(
        cache_user_by_token(
            user_token,
            {
                "id": user.id,
                "is_admin": account.role in ("admin", "super_admin"),
                "is_active": account.is_active,
                "email": account.email,
                "is_account": True,
                "role": account.role,
            },
        )
    )
    ```
    配套缺失: account_settings_service.request_deletion / cancel_deletion / change_password 写完没 invalid cache. 6h 内 token cache 仍用旧值.
  impact: |
    中 - 安全场景: admin 立刻 disable 一个用户, 该用户 6h 内仍能登; 改密码后, token cache 仍允许旧 session 走. 业务场景: 邮箱改完, 6h 内 cache 里仍是旧 email.
  fix_sketch: |
    1) 改 Account.is_active / password_hash / email / role 的写路径, 调 `await invalidate_user_token(user_token)`. 2) 关键路径 (is_active 变 False) 同步写 cache + PG, 不用 fire-and-forget.
  references: []

---

- id: CON-009
  dimension: concurrency
  severity: medium
  confidence: medium
  title: "MemoryService 单例 + mem0 Memory 实例缓存, 跨请求实例共享缺线程安全"
  file: packages/service/src/memory/service.py
  line: 75
  description: |
    MemoryService 单例, 内含 dict 缓存 (per-user_id Memory 实例). asyncio.create_task(self._mark_ready()) 异步 fire-and-forget. FastAPI 同步路由 (search/list_memories/update_memory/delete_memory/delete_all_memories) 在不同 worker thread 调同一个 MemoryService 单例 → 同一 _cache dict. CPython GIL 保护 dict 操作原子, 但 m.add / m.search 内部可能创建临时 session, 多线程并发调同一 Memory 实例的 search + add, mem0 内部 pgvector 连接是否线程安全未在代码中验证. 同时 _unavailable set 多个线程同时 add 没问题 (GIL), 但 add 之后 self._cache[user_id] 仍可能写入 (因为 add 在 _get_memory 内 try/except 后才 return None).
  evidence: |
    ```python
    # service.py:81-107
    def __init__(self, mem0_factory: Callable[[str], Memory] | None = None):
        self._factory = mem0_factory or _default_mem0_factory
        self._cache: dict[str, Memory] = {}
        # (2026-06-23) mem0 启动失败标记
        self._unavailable: set[str] = set()

    def _get_memory(self, user_id: str) -> Memory | None:
        if user_id in self._unavailable:
            return None
        if user_id not in self._cache:
            try:
                self._cache[user_id] = self._factory(user_id)
            except RuntimeError:
                self._unavailable.add(user_id)
                logger.error(...)
                return None
        return self._cache[user_id]
    ```
  impact: |
    低 - 大概率安全 (mem0 文档声明 Memory 线程安全 + CPython GIL 兜底), 但失败模式 (factory 抛 RuntimeError 同时另一线程 factory 成功) 会出现"用户标 unavailable 但其实有可用 instance" 的状态不一致, 需要重启服务才恢复. 单进程单 worker 部署影响小, 多 worker (uvicorn --workers N) 时 MemoryService 单例失效, 重复构造.
  fix_sketch: |
    1) 失败标记用 `asyncio.Lock` 保护 (async 路径). 2) 多 worker 部署时改用 Redis 持有 user_id → instance_id 映射, instance 用 weakref. 3) 修工厂失败后, 暴露 admin 接口清 _unavailable set 而不要求重启.
  references: []

## 未扫 / 已知缺口

- `packages/service/src/lookups/safety_guard.py` + `lookups/admin_router.py` (字典 admin 改 enum) — 部分走过, 但本维度重点是数据竞争, lookup 字典改的并发风险低 (admin 后台, 串行访问), 未列 finding
- `packages/service/src/permissions/router.py` (角色绑定) — 简单 session_scope 单写, 角色翻转的不一致窗口 < 100ms, 未列
- `packages/service/src/chat_share/` (公开 share) — anon 可读 + 创建/撤销 走单 session, 未发现关键 race
- `packages/service/src/kg/audit.py` — 单 session 写, 无状态机
- `packages/service/src/orchestration/`, `product_decoders/`, `retrieval/` — 任务路由型, 内部 race 不在 service 层控制, 未扫
- 测试 `tests/` 覆盖情况未在本维度核对 (属于 D6 范畴)
- ChatGPT-style LLM 调用并发 (openai_client streaming + DB write) 内部时序未深入, 不在 30 次工具调用预算内

## 重点关注文件 (主线程可优先修)

1. `auth_invite_router.py:115` (CON-001 critical) — 单事务 + FOR UPDATE 锁 invite 行
2. `account_settings_service.py:188` (CON-002 critical) — cancel_deletion 锁 Account 行 + cron 加 is_active=false
3. `auth_account_service.py` 整文件 + `auth_account_router.py` — email 改 / 密码改缺 token cache invalidation (CON-008 关联)
4. `buyer_profile/service.py:63` (CON-004 high) — JSONB RMW 改 `||` 原子操作
5. `chat/service.py:73` (CON-007 medium) — 分页改 cursor-based
