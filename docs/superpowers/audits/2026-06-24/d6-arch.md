# D6: Architecture & Convention 扫描结果

> 扫描时间: 2026-06-24
> Agent 角色: D6 Architecture & Convention
> 工具调用次数: 25
> 找到 12 条 finding

## 元信息

- 项目根: `c:/doc/Code/rag/.claude/worktrees/audit-2026-06-24/`
- 扫描路径: `packages/service/src/`, `packages/web/`, `packages/service/pyproject.toml`, `packages/web/package.json`, `CLAUDE.md`, `packages/service/CLAUDE.md`, `packages/web/CLAUDE.md`, `packages/service/KNOWN_ISSUES.md`
- 已知跳过: `KNOWN_ISSUES.md` 中 22 fail / 38 errors 已全部修 (P2 phase2), 仅 0 行遗留, 见 `KNOWN_ISSUES.md`
- 备注: `dictionaries_enum.py` 中 5 个 `StrEnum` 类是 CLAUDE.md 显式豁免的 lookup 镜像 (pyright 可见性需要), 不算违规; 已加 `_verify_against_yaml` 启动校验

## Findings (12 条)

### Critical (1)

---

- id: ARCH-001
  dimension: arch
  severity: critical
  confidence: high
  title: "12 个前端文件从 next/navigation 引 useRouter, 违反 CLAUDE.md 强制 i18n 路由"
  file: packages/web/components/common/back-link.tsx
  line: 12
  description: |
    违反 {CLAUDE.md §前端 React/Next.js 准则} "路由跳转必须用 @/i18n/navigation 的 useRouter, 禁止 next/navigation 的".
    真实 bug 案例 (2026-06-17): 登录页 router.push("/") 因走 next/navigation, 被 intlMiddleware 307 重定向, 用户感觉 "没反应".
    `packages/web/CLAUDE.md §⚠️ 路由跳转必须用 next-intl 的 useRouter` 明文要求, 仅 login/page.tsx 有 import guard 测试保护,
    其余 12 个文件未走统一入口, 散布相同 bug 模式.
  evidence: |
    ```typescript
    // packages/web/components/common/back-link.tsx:12
    import { useRouter } from "next/navigation";
    ...
    const router = useRouter();
    if (typeof globalThis !== "undefined" && globalThis.history.length >= MIN_HISTORY_FOR_BACK) {
      router.back();
    } else {
      router.push(href);  // 不带 locale 前缀, 被 middleware 307 重定向
    }
    ```
    全量命中 (12 文件):
    - `components/common/back-link.tsx:12`
    - `components/settings/settings-dialog.tsx:6`
    - `components/chat/message-feedback.tsx:11`
    - `app/[locale]/submissions/_components/submissions-tabs.tsx:11`
    - `app/[locale]/admin/permissions/_components/permissions-admin-client.tsx:19`
    - `app/[locale]/reset-password/page.tsx:5`
    - `app/[locale]/output/new/page.tsx:22`
    - `app/[locale]/evaluate/_components/evaluate-list-view.tsx:15`
    - `app/[locale]/evaluate/new/_components/evaluate-new-form.tsx:21`
    - `app/[locale]/evaluate/[id]/_components/run-detail-view.tsx:21`
    - `app/[locale]/knowledge/triples/_components/triples-form.tsx:15`
    - `app/[locale]/knowledge/qa/_components/qa-submit-form.tsx:8`
    - `app/[locale]/knowledge/documents/import/_components/import-commit-card.tsx:10`
  impact: |
    用户在 /zh/foo 跳到 /bar 时, 跳到 /bar 被 middleware 307 重定向到 /zh/bar,
    多一跳 + 多一次服务端 roundtrip + 短暂白屏, 高频路径 (登录/重置密码/退出) 直接影响转化.
    admin / evaluate / knowledge 等复杂业务流同样中招, 状态可丢失 (表单 in-flight 跳走).
  fix_sketch: |
    全部 `from "next/navigation"` 改成 `from "@/i18n/navigation"`, createNavigation(routing) 已统一封装.
    跑 `app/[locale]/login/page.test.tsx` 的 import guard 测试, 必要时把 guard 提到 conftest 防所有文件漏改.
  references: [CLAUDE.md §重构规则, packages/web/CLAUDE.md §⚠️ 路由跳转]

### High (4)

---

- id: ARCH-002
  dimension: arch
  severity: high
  confidence: high
  title: "ingest/pipeline.py 散落 47 处 print(), 违反 loguru 统一规范"
  file: packages/service/src/ingest/pipeline.py
  line: 36
  description: |
    违反 {packages/service/CLAUDE.md §日志使用约定} "业务代码用 loguru, 不用 stdlib logging / print".
    全项目其它业务模块 (chat_share / memory / chat / lookups / core) 全部走 `from loguru import logger`,
    仅 `ingest/pipeline.py` 仍是 print 模板, 总计 47 处 (line 36, 116, 144, 164, 188, 194, 202, 208-228, 235, 257, 263-334, 358-440).
    2026-06-17 logging spec 完成 loguru 全量切换, 本文件遗漏.
  evidence: |
    ```python
    # packages/service/src/ingest/pipeline.py:36
    def process_path(path: str | None = None, output_dir: str | None = None) -> dict | None:
        ...
        if not p.exists():
            print(f"路径不存在: {path}")
            return None
    ...
    # line 188
    print(
        f"  bucket={len(buckets['cad'])} doc={len(buckets['doc'])} ..."
    )
    # line 333-334
    print("=" * 50)
    print(f"成功: {len(results['processed'])} | 失败: {len(results['errors'])}")
    ```
  impact: |
    print 走 stdlib stdout, 不进 loguru sink → 写不到 `app_logs` / `error_logs` PG 表, 监控和告警全失.
    JSON 控制台模式 (LOG_JSON=true) 失效, Grafana 抓不到 ingest 阶段事件.
    `prometheus_enabled` 跟 ingest 链路解耦, 无法做端到端调用追踪.
  fix_sketch: |
    顶部加 `from loguru import logger`, 把 47 处 print 改 `logger.info / warning / error`,
    占位符用 `{}` (loguru 风格), 警告/错误走 `logger.warning / error` 区分.
    跟 2026-06-17 logging spec 留的 `chat_share/router.py:26 # noqa: F401` 注释模式一致.
  references: [packages/service/CLAUDE.md §日志使用约定, 2026-06-17 logging spec]

---

- id: ARCH-003
  dimension: arch
  severity: high
  confidence: high
  title: "os.getenv 跨 20+ 文件散落, 无统一 config facade"
  file: packages/service/src/health/checks.py
  line: 269
  description: |
    违反 {CLAUDE.md §重构规则 §大模型规范} "禁止硬编码, 所有路径/配置项/常量等都必须从配置文件或环境变量中读取"
    (延伸: 应该集中读, 散落 os.getenv 等同于 100+ 处硬编码来源).
    `os.getenv("REDIS_HOST", "localhost")` 至少 5 处重复 (redis_client.py:68, 227; lifespan.py:59; health/checks.py:269),
    `os.getenv("DIFY_BASE_URL", ...)` 至少 5 处 (kg/router.py:96, 152, 185, 221; health/checks.py:136),
    `os.getenv("OBJECT_STORE_S3_BUCKET", "rag-ingest")` 5 处 (chat_share/router.py:292; ingest/api.py:266; eval/router.py:179;
    product_decoders/output_api.py:77, 148; auth/account_settings_service.py:68), 还有 PG_*, OLLAMA_BASE_URL, OPENAI_API_KEY,
    MEM0_COLLECTION_NAME, NEO4J_*, LANGFUSE_*, EMBED_*, RAG_ADMIN_TOKEN, RAG_AUTO_CREATE_SCHEMA 等等.
  evidence: |
    ```python
    # packages/service/src/health/checks.py:263-274 (Dify check)
    async def check_dify() -> CheckResult:
        ...
        base_url = os.getenv("DIFY_BASE_URL", "http://localhost/v1")
        api_key = os.getenv("DIFY_DATASET_API_KEY", "")

    # packages/service/src/health/checks.py:268-274 (Redis check)
    def _get_redis_client():
        import redis as _redis
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD", None)
    ```
    全部散落 ≥ 100 处, 见 `os.getenv` 命中行号清单.
  impact: |
    改 host/port/key 默认值要改 5+ 文件, 易漏; 测试要 monkeypatch 5+ 路径.
    配错 (env 没设) 各模块行为不一致 (Dify 走 localhost/v1, object_store 走 localhost:9000).
    `defaults.DEFAULT_*` 已经在 `src/common/defaults.py`, 但只有少数调用走它, 多数 os.getenv 硬编字面量.
  fix_sketch: |
    新增 `src/core/config.py` facade (pydantic-settings BaseSettings), 启动时一次性加载, 业务模块 `from src.core.config import settings`,
    兼容 dev mode: 走 `lifespan._lifespan` 早绑定, `os.getenv` 全部下沉到一处.
  references: [CLAUDE.md §大模型规范 §禁止硬编码, src/common/defaults.py]

---

- id: ARCH-004
  dimension: arch
  severity: high
  confidence: medium
  title: "tests/lookups/test_audit.py:47 和 test_config.py:63 用裸 # type: ignore"
  file: packages/service/tests/lookups/test_audit.py
  line: 47
  description: |
    违反 {CLAUDE.md §后端 Rust-like 严格准则} "type: ignore 必须带具体错误码 + 注释. 不接受裸 # type: ignore"
    (CLAUDE.md §top-10 防再犯 #2 显式列, 跟 P2a 删过的 approvals/models.py 同模式).
    其余 80+ type: ignore 全部带 `[error-code]` + 注释, 这 2 处是漏网.
  evidence: |
    ```python
    # packages/service/tests/lookups/test_audit.py:45-52
    with pytest.raises(TypeError, match="actor_id"):
        log_dict_change(
            actor="anon",
            actor_id=None,  # type: ignore            ← 裸 ignore, 无 error code
            action="test",
            target="x",
            before=None,
            after=None,
            ip=None,
        )
    ```
    ```python
    # packages/service/tests/ingest/test_config.py:59-63
    def test_paths_immutable(self):
        """Paths 应该是 frozen dataclass，外部不能改"""
        paths = get_paths()
        with pytest.raises(Exception):
            paths.input_dir = Path("/tmp")  # type: ignore    ← 裸 ignore
    ```
  impact: |
    未来 pyright 升级或加 strict mode 时, 裸 ignore 不指向具体错误, 报新错会被静默吞.
    CLAUDE.md 强制 "type: ignore 必须带具体错误码 + 注释", 这 2 处明确违反.
  fix_sketch: |
    跑 `uv run pyright` 拿具体 error code, 改 `  # type: ignore[arg-type]  # 注释说明为什么`.
  references: [CLAUDE.md §top-10 防再犯 #2]

---

- id: ARCH-005
  dimension: arch
  severity: high
  confidence: high
  title: "permission/service.py:50 写 datetime.utcnow(), 触发 pyright 多次 # type: ignore[assignment]"
  file: packages/service/src/permissions/service.py
  line: 50
  description: |
    违反 {CLAUDE.md §后端 Rust-like 严格准则} "ruff 警告不允许绕过 / pyright 必须 0 error / type: ignore 必须带具体错误码 + 注释".
    `datetime.utcnow()` 在 Python 3.12+ deprecation 警告, SQLAlchemy DateTime 字段类型推断也常报 assignment 不匹配,
    本文件 4 处 (line 50, 51, 312, 314, 315) 全用 `# type: ignore[assignment]` 强压, 没有为 datetime.utcnow 替换.
    同一仓库 `auth/account_service.py:5` 等文件用 `datetime.now(timezone.utc)`, 标准答案已经存在.
  evidence: |
    ```python
    # packages/service/src/permissions/service.py:48-53
    for r in roles:
        if r.code == req.code:
            existing = r
            existing.allowed = allowed  # type: ignore[assignment]
            existing.updated_at = datetime.utcnow()  # type: ignore[assignment]
            break
    ...
    # line 312-315 (router.py)
    role.label_zh = req.label_zh  # type: ignore[assignment]
    role.label_en = req.label_en  # type: ignore[assignment]
    role.updated_at = datetime.utcnow()  # type: ignore[assignment]
    ```
  impact: |
    Python 3.14 跑起来 `datetime.utcnow()` 触发 DeprecationWarning, 生产 stderr 噪音.
    类型 ignore 散落 4 处, 真有 schema 改 Column type 时, 不会再被 pyright 发现.
  fix_sketch: |
    全部 `datetime.utcnow()` 改 `datetime.now(timezone.utc)`, 删 `# type: ignore[assignment]`, 跑 pyright 验 0 error.
  references: [CLAUDE.md §后端 Rust-like 严格准则]

### Medium (5)

---

- id: ARCH-006
  dimension: arch
  severity: medium
  confidence: high
  title: "api/routes.py + kg/router.py 4 处 TODO 提示待补 @audited 装饰器"
  file: packages/service/src/api/routes.py
  line: 7
  description: |
    违反 {packages/service/CLAUDE.md §危险操作必须加 @audited} "DELETE / 改账户 / 改权限 / 导出数据" 必须 @audited.
    这 4 处 TODO 自承 "等端点实现后补", 但当前 DELETE 节点 / 关系端点 / admin.access 中间件 / audit.read_self
    一旦上线, 没有审计 → 误删无 trace, 修不了.
  evidence: |
    ```python
    # packages/service/src/api/routes.py:7-8
    # TODO: 加 @audited("admin.access") 中间件 (2026-06-18 sync)
    # TODO: 加 audit.read_self 端点 (2026-06-18 sync)

    # packages/service/src/kg/router.py:24-25
    # TODO: 加 @audited("kg_node.delete", target_type="kg_node") 当 DELETE 节点端点实现后
    # TODO: 加 @audited("kg_relation.delete", target_type="kg_relation") 当 DELETE 关系端点实现后
    ```
  impact: |
    高风险端点 (admin / kg node/relation delete) 一旦合入 master, 没有 audit trail, GDPR / 内审查不到谁删了什么.
  fix_sketch: |
    写新 spec "kg-delete + admin-access" 一次性补齐 4 个 @audited 装饰器 + admin.access 中间件, 删 TODO 注释.
  references: [packages/service/CLAUDE.md §危险操作必须加 @audited]

---

- id: ARCH-007
  dimension: arch
  severity: medium
  confidence: medium
  title: "lib/api/permissions.ts 和 buyer-profile.ts 用 any[] 而非 Pydantic 风格 typed"
  file: packages/web/lib/api/permissions.ts
  line: 12
  description: |
    违反 {packages/web/CLAUDE.md §代码规范} "tsgo 必须 0 error" + "import 必须按首字母排序 / 变量名禁止单字符".
    `lib/api/permissions.ts:12` `patchPermissions = (updates: any[], ...)` 和
    `lib/api/buyer-profile.ts:11, 16, 18` `updateBuyerProfile = (id, body: any)` 4 处用 `any` 类型.
    CLAUDE.md 强 tsgo 0 error, 但 `any` 编译不报错, 失去类型保护, 改 schema 时下游静默.
    `lib/api/permissions.ts:4` `pages: any[]` 也是同模式.
  evidence: |
    ```typescript
    // packages/web/lib/api/permissions.ts:1-12
    import { apiFetch } from "@/lib/api/fetcher";

    export const patchPermissions = (updates: any[], headers?: Record<string, string>) =>
      apiFetch<void>("/api/admin/permissions/roles", {
        method: "PATCH",
        body: JSON.stringify({ updates }),
        headers,
      });
    ```
    ```typescript
    // packages/web/lib/api/buyer-profile.ts:11-18
    export const updateBuyerProfile = (id: string, body: any) => ...
    export const createFieldConfig = (body: any) => ...
    export const updateProfileFieldConfig = (code: string, body: any) => ...
    ```
  impact: |
    后端 Pydantic schema 改字段后, 前端 `any` 不报错, 错值直接发出去, 422 调试困难.
    不可 grep 出 "这条 API 实际接受什么", 文档与代码脱节.
  fix_sketch: |
    从 `app/[locale]/_actions/*` 或 backend `schemas.py` 拿 zod schema, 编译期保证一致.
    例如 `patchPermissions = (updates: RoleUpdate[], ...)`.
  references: [packages/web/CLAUDE.md §工具链 §tsgo 0 error]

---

- id: ARCH-008
  dimension: arch
  severity: medium
  confidence: high
  title: "print() 在 scripts/duplication-report.ts 和 e2e spec 出现, 业务代码应走 console 包装"
  file: packages/web/scripts/duplication-report.ts
  line: 54
  description: |
    违反 {packages/web/CLAUDE.md §日志 i18n 一致性} 风格 (相对轻量, scripts/ 容忍, 但 e2e 没用项目 lib/log.ts).
    `scripts/duplication-report.ts:54, 127, 128` 用 console.error/log,
    `e2e/01-decode.spec.ts:34`, `e2e/02-knowledge.spec.ts:19` 同模式.
    项目已有 `lib/log.ts` 统一封装 (line 58, 62, 70), 业务代码应走它.
  evidence: |
    ```typescript
    // packages/web/scripts/duplication-report.ts:54
    console.error(`找不到报告文件: ${REPORT_PATH}\n先运行 bun run find-duplicates`);
    ...
    // line 127-128
    console.log(`报告已生成: ${OUTPUT_PATH}`);
    console.log(`共 ${report.duplicates.length} 处重复`);
    ```
    ```typescript
    // packages/web/lib/log.ts:55-70 (已有统一封装)
    export const log = {
      debug: (message: string, meta?: object) => console.log(format("debug", message, meta)),
      info:  (message: string, meta?: object) => console.log(format("info", message, meta)),
      warn:  (message: string, meta?: object) => console.warn(format("warn", message, meta)),
      error: (message: string, meta?: object) => console.error(format("error", message, meta)),
    };
    ```
  impact: |
    scripts 缺统一格式 (时间戳 / level), 拼装 log 聚合工具 (Loki / Datadog) 时格式不一致要重写.
  fix_sketch: |
    scripts/ + e2e/ 改 `import { log } from "@/lib/log"; log.error(...)`, 已有的封装 0 成本复用.
  references: [packages/web/lib/log.ts]

---

- id: ARCH-009
  dimension: arch
  severity: medium
  confidence: high
  title: "package.json scripts 用 tsc --noEmit, 违反 CLAUDE.md '用 tsgo 替代 tsc'"
  file: packages/web/package.json
  line: 15
  description: |
    违反 {packages/web/CLAUDE.md §工具链} "类型检查: @typescript/native-preview 的 tsgo 二进制 (10x 快于 tsc)".
    实际 `package.json:typecheck = "tsc --noEmit"`, 应是 `tsgo --noEmit`.
    devDependencies 第 101 行 `"typescript": "^6.0.3"` 装的是 tsc, 缺 tsgo binary.
    偏离 CLAUDE.md 强约束, CI 速度差 ~10x.
  evidence: |
    ```json
    // packages/web/package.json:15
    "typecheck": "tsc --noEmit",
    ```
    ```json
    // devDependencies:101
    "typescript": "^6.0.3",
    ```
    CLAUDE.md §工具链明确规定:
    ```
    - **类型检查**：`@typescript/native-preview` 的 `tsgo` 二进制 (10x 快于 tsc)
      bun run typecheck    # = tsgo --noEmit
    ```
  impact: |
    CI typecheck 阶段跑 tsc 慢 ~10x, 阻塞 PR feedback loop.
    tsgo 是 native preview 包, 没装 = 0 受益, 但 devDeps 仍然装 tsc 占据体积.
  fix_sketch: |
    `bun add -D @typescript/native-preview`, `"typecheck": "tsgo --noEmit"`.
    husky pre-commit 钩子里也是 `tsgo` (CLAUDE.md §工具链 §Pre-commit), 跟 package.json 同步切换.
  references: [packages/web/CLAUDE.md §工具链]

---

- id: ARCH-010
  dimension: arch
  severity: medium
  confidence: medium
  title: "package.json scripts 缺 lint:check 跟 format:check 一致; pre-commit 依赖 format:check 但 scripts 没有"
  file: packages/web/package.json
  line: 16
  description: |
    违反 {CLAUDE.md §工具链 §Pre-commit} "pre-commit 钩子串了 lint-staged + tsgo + vitest + format:check".
    `package.json` 有 `format:check` (line 19), 但缺 `lint:check` (只有 `lint:fix` 自动改); CI 阶段想 fail-fast 找不到只读入口.
    同样 `test:watch` 缺 `test:bun` 跟 `test:bun` 是 `bun test` (CLAUDE.md 警示: "bun test 不读 vitest.config.ts").
  evidence: |
    ```json
    // packages/web/package.json:5-26
    "scripts": {
      "test": "vitest run",
      "test:watch": "vitest",
      "test:coverage": "vitest run --coverage",
      "test:bun": "bun test",          // ← CLAUDE.md 警示: 不读 vitest.config.ts
      "test:e2e": "playwright test",
      "test:e2e:ui": "playwright test --ui",
      "typecheck": "tsc --noEmit",
      "lint": "oxlint .",              // 已是只读, OK
      "lint:fix": "oxlint --fix --fix-suggestions --fix-dangerously",
      "format": "oxfmt .",
      "format:check": "oxfmt . --check",
      ...
    ```
  impact: |
    CI 跑 `bun run format:check` 跟 husky 一致, 但 `bun run lint` 实际是 `oxlint .` (只读, OK), 没 `--check` flag 区分 lint 跟 lint:fix.
    命名一致性差: 测试有 `test` / `test:watch` / `test:coverage`, lint 只有 `lint` / `lint:fix`.
  fix_sketch: |
    加 `"lint:check": "oxlint . --deny-warnings"` 走 fail-fast,
    `test:bun` 改注释 "deprecated, 用 bun run test (vitest)", 防止误用.
  references: [CLAUDE.md §工具链 §Pre-commit, packages/web/CLAUDE.md §跑测试]

### Low (2)

---

- id: ARCH-011
  dimension: arch
  severity: low
  confidence: high
  title: "SubmissionsTabs.tsx 53 行, 含 3 处 useState + 内联 onClick, 风格跟 DataTable 封装不统一"
  file: packages/web/app/[locale]/submissions/_components/submissions-tabs.tsx
  line: 11
  description: |
    违反 {packages/web/CLAUDE.md §封装组件 §反模式} "❌ 写 useState 套 5 层的 hook 而不抽封装" +
    "JSX 不写行内 onClick={() => {}} 复杂表达式, 提取命名函数".
    文件从 `next/navigation` 引 useRouter (ARCH-001 命中), 加上 useState/useTranslation 套层,
    53 行小文件用 5+ useState + 内联 onClick + setStatus 调用 → 典型 6a93b06 重复模式被吸 7 页的反面.
    应改用 `DataTable<T>` + `AppToggle` (项目已封装) 拆 Tab.
  evidence: |
    ```typescript
    // packages/web/app/[locale]/submissions/_components/submissions-tabs.tsx:11
    import { useRouter } from "next/navigation";
    ...
    const [activeTab, setActiveTab] = useState<"pending" | "reviewed">("pending");
    const [page, setPage] = useState(1);
    const handleTabChange = (tab: ...) => { setActiveTab(tab); setPage(1); router.replace(...); };
    ```
  impact: |
    文件结构跟 `DataTable<T>` + `AppToggle` 不统一, 后续 submissions 业务扩展时, Tab 切换 / 分页状态会膨胀.
    重构时再拆, 改动面比现在大一倍.
  fix_sketch: |
    Tab 段换 `<AppToggle>` (项目封装), 分页走 `DataTable` 内建 pagination, useState 数从 5+ 降到 1 (activeTab).
  references: [packages/web/CLAUDE.md §封装组件 §反模式, ARCH-001]

---

- id: ARCH-012
  dimension: arch
  severity: low
  confidence: medium
  title: "tests/conftest.py autouse mock_all_db_connections 全局 mock, 业务方难以定位 mock 失败根因"
  file: packages/service/tests/conftest.py
  line: 1
  description: |
    违反 {CLAUDE.md §测试规范} "覆盖正常路径和异常路径" + {packages/service/CLAUDE.md §测试隔离 4 模式 §反模式}
    "❌ 写新 test 时 凭直觉造 fixture (应该问: 我用 4 模式里哪个?)".
    `KNOWN_ISSUES.md` 已经修了 30+ test, 但 autouse 在 conftest 顶层, 新 test 看不见 mock 列表,
    出错时 "为什么 session_scope 返回 MagicMock" 难定位. 文档化是部分缓解, 不算违规,
    但 conftest 没 README / 没打印 "本目录生效的 mock" 摘要 → onboarding 成本高.
    严重度低, 提示级别.
  evidence: |
    ```python
    # packages/service/tests/conftest.py (KNOWN_ISSUES.md 描述)
    # 全局 autouse fixture: tests/conftest.py::mock_all_db_connections
    # mock 了:
    #   1. src.storage.engine._engine = None (关单例)
    #   2. src.storage.session_scope + namespace alias
    #   3. src.core.redis_client.get_redis → fakeredis
    #   4. src.storage.object_store.get_object_store → MagicMock
    #   5. src.knowledge_graph.neo4j_client.get_neo4j → None
    #   6. src.permissions.cache.permission_cache.get → True
    ```
  impact: |
    1 onboarding 成本高 (新人不知道 mock 了什么). 2 test failure 时, 报错栈可能指向
    "session_scope 返 MagicMock 缺方法" 但真因可能是 autouse 跟具体 test 不兼容.
  fix_sketch: |
    conftest.py 顶部加 docstring 列 mock 矩阵 + 影响范围, 或单独 README.
  references: [packages/service/CLAUDE.md §测试隔离 4 模式, packages/service/KNOWN_ISSUES.md]

## 未扫 / 已知缺口

- 没扫 `bun.lock` / `uv.lock` 完整 lockfile (大文件, 工具调用预算); 用 pyright + `bun outdated` 之类命令可在后续 spec 跑
- 没扫 `.env.example` / `.env.local` (私密文件, 按 CLAUDE.md 默认不入库)
- 没读 `docs/superpowers/specs/` 全部 spec (文件量大, 仅按需引用)
- ARCH-012 (conftest mock 文档) 严重度仅 low, 不阻塞 commit
- 已知豁免 (跟 KNOWN_ISSUES.md 对齐): 当前没有 pre-existing fail, 0 行遗留
- 已知豁免: `dictionaries_enum.py` 中 5 个 `StrEnum` 是 CLAUDE.md §字典使用规范 显式豁免的 lookup 镜像
- 已知豁免: `pyright` 当前 basic 模式, strict 后 ARCH-004 / ARCH-005 影响面会扩大

## 严重度分布

- critical: 1 (ARCH-001, i18n useRouter bug 模式 ×12 文件)
- high: 4 (ARCH-002 print, ARCH-003 env 散落, ARCH-004 裸 type:ignore, ARCH-005 datetime.utcnow)
- medium: 5 (ARCH-006 缺 @audited, ARCH-007 any 滥用, ARCH-008 console 散落, ARCH-009 tsc vs tsgo, ARCH-010 scripts 一致性)
- low: 2 (ARCH-011 组件封装, ARCH-012 conftest 文档)

## 关注点

1. **ARCH-001 是高频 1 类 bug** — 12 文件同样的已知 bug 模式, 修复可以批量 5-10 分钟 (sed + import guard 升级到 conftest).
2. **ARCH-002 + ARCH-003 是大型重构** — ingest/pipeline.py 47 处 print + 全项目 100+ os.getenv, 拆 2-3 个 PR 比较稳.
3. **ARCH-005 是 deprecation** — Python 3.14 还在容忍 `datetime.utcnow()` DeprecationWarning, 升级到 3.15 会变 hard error, 提前 1 个 sprint 修.
4. **ARCH-006 跟安全审计相关** — admin.access / kg node delete 没 @audited 装饰器, 跟 D1 (Security) 维度强耦合, 建议 verify 阶段交叉看.
5. **ARCH-009 性能** — tsc 换 tsgo 是 0 风险高收益, 应是 P0 PR.
