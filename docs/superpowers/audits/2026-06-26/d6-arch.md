# D6: Architecture & Convention 扫描结果

> 扫描时间: 2026-06-26
> Agent 角色: D6 Architecture & Convention 维度扫描 agent — 偏架构视角, 检查规约遵守/代码重复/模块边界/测试规范等
> 工具调用次数: 24 / 30
> 找到 6 条 finding (verified: 6, refuted: 0, 待 verify: 0)

## 元信息

- 项目根: c:/doc/Code/rag
- 扫描路径:
  - packages/service/src/ (全量 — Grep 查 os.getenv / StrEnum / 函数大小 / 类大小)
  - packages/web/app/ (全量 — Grep 查 useRouter 错误 import / function 声明 / use() 使用)
  - packages/web/components/ (全量 — Grep 查函数声明)
  - packages/web/lib/ (全量 — Grep 查 process.env / useRouter / 函数声明)
  - packages/web/package.json (脚本一致性)
  - packages/service/pyproject.toml (工具链配置)
  - packages/service/CLAUDE.md + packages/web/CLAUDE.md + 项目根 CLAUDE.md (规约核对)
  - .husky/pre-commit (钩子检查)
  - docker/.env + packages/web/.env + packages/service/.env.local (env 泄露检查)
  - packages/service/src/config/settings.py + config_legacy.py (配置集中度)
- 已知跳过:
  - 重复代码扫描 (jscpd) 因工具未本地安装跳过, 仅做手动 grep 模式匹配
  - Python AST 函数大小分析仅覆盖 7 个最大文件 (共 30+ src 文件)
  - 前端 bundle 体积分析 (未接 webpack-bundle-analyzer)
  - 完整 4 模式测试覆盖分析 (仅检查 conftest 模式, 未逐 test 验证)
- 备注:
  - 跨层 import (service → web / web → service) 未发现违规, 模块边界良好
  - 前端 RSC/use(client/server) 边界使用正确, 未发现错用

## Findings (6 条)

- id: ARCH-001
  dimension: arch
  severity: medium
  confidence: high
  title: "CLAUDE.md 记载 typecheck 用 tsgo, 实际 package.json 用 tsc"
  file: packages/web/CLAUDE.md
  line: 50
  description: |
    packages/web/CLAUDE.md 第 50-52 行明确记载类型检查使用 `@typescript/native-preview` 的 `tsgo` 二进制
    ("10x 快于 tsc"), 并给出命令行 `bun run typecheck # = tsgo --noEmit`。但 packages/web/package.json
    第 15 行实际脚本是 `"typecheck": "tsc --noEmit"`, 且 .husky/pre-commit 钩子第 42 行也调用 `tsc`
    而非 tsgo。文档和代码之间存在明显脱节。
  evidence: |
    ```yaml
    # packages/web/CLAUDE.md:50-52
    - **类型检查**：`@typescript/native-preview` 的 `tsgo` 二进制 (10x 快于 tsc)
      ```bash
      bun run typecheck    # = tsgo --noEmit
      ```
    ```
    ```yaml
    # packages/web/package.json:15
    "typecheck": "tsc --noEmit",
    ```
    ```sh
    # .husky/pre-commit:42
    (cd packages/web && bun x tsc --noEmit)
    ```
  impact: |
    新人按 CLAUDE.md 文档理解工具链时会产生迷惑; tsgo 和 tsc 行为有差异 (tsgo 更快但可能
    规则集不同), 文档与实现不符会降低规约可信度。
  fix_sketch: |
    两种方案: (1) 更新 package.json 的 typecheck 脚本为 `tsgo --noEmit` 并同步 pre-commit
    钩子; (2) 更新 CLAUDE.md 第 50-52 行改为 `tsc`.
  references:
    - arch-005 (同属 scripts 一致性)

- id: ARCH-002
  dimension: arch
  severity: high
  confidence: high
  title: "os.getenv 分散在 31 个文件中, 未按规约集中到 config/settings.py"
  file: packages/service/src/config/settings.py
  line: 3
  description: |
    项目已建立 config/settings.py 集中管理 env 变量, 但实际只有 6 个文件 import 自此模块
    (app_factory.py / settings.py 自身 / redis_client.py / checks.py / auth/router.py /
    object_store.py)。其余 31 个文件直接调用 os.getenv 获取环境变量, 包括 auth/account_service.py、
    auth/account_settings_service.py、auth/auth_account_router.py、generation/llm.py、
    chat_share/service.py、middleware/auth.py、integrations/dify_client.py 等核心模块。
    settings.py 注释写 "首次迁移: 5 个最常用模块的 env 变量, 其余 15+ 留给后续 PR", 但至今未完成。
  evidence: |
    ```python
    # packages/service/src/config/settings.py:3-4
    """项目配置集中管理 (ARCH-003 fix).
    所有 os.getenv 调用迁移至此, 避免散落 20+ 文件.
    首次迁移: 5 个最常用模块的 env 变量, 其余 15+ 留给后续 PR.
    """
    ```
    ```python
    # 散落示例: packages/service/src/chat_share/service.py:174
    api_key = os.getenv("DIFY_DATASET_API_KEY", "")
    dify_url = f"{os.getenv('DIFY_BASE_URL', '').rstrip('/')}/files/upload"
    # packages/service/src/auth/account_service.py:12
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    # packages/service/src/auth/account_settings_service.py:26-28
    DELETION_GRACE_DAYS = int(os.getenv("DELETION_GRACE_DAYS", "7"))
    EMAIL_CHANGE_EXPIRES_DAYS = int(os.getenv("EMAIL_CHANGE_EXPIRES_DAYS", "7"))
    DELETION_RESTORE_EXPIRES_DAYS = int(os.getenv("DELETION_RESTORE_EXPIRES_DAYS", "7"))
    ```
  impact: |
    配置项散落导致: (1) 修改 env 变量名需 grep 全项目确认引用点; (2) 新开发者难以发现
    所有可用配置项; (3) 默认值分散在各文件, 不易审计; (4) 部分变量含敏感 key (API_KEY),
    散落增加泄露风险。
  fix_sketch: |
    按 settings.py 已有模式, 将 30+ 个文件的 os.getenv 调用迁移到 config/settings.py 的 Settings
    dataclass, 逐步推进。高优迁移含敏感信息的变量 (API_KEY / SECRET / PASSWORD)。
  references: []

- id: ARCH-003
  dimension: arch
  severity: medium
  confidence: high
  title: "MinioObjectStore (283 行) 和 EzdxfConverter (323 行) 超过 100 行规约"
  file: packages/service/src/storage/object_store.py
  line: 267
  description: |
    项目 CLAUDE.md 规定 "每个函数或类的代码量不能超过 100 行"。MinioObjectStore 类从第 267 行
    到文件结束共 283 行, EzdxfConverter 类从第 193 行到第 515 行共 323 行, 均显著超过 100 行限制。
    MinioObjectStore 负责 MinIO S3 存储的 put/get/list/presign/delete 全套操作, EzdxfConverter
    处理 CAD 文件的 DWG/DXF 解析转换, 职责过重。
  evidence: |
    ```python
    # packages/service/src/storage/object_store.py:267
    class MinioObjectStore(ObjectStore):
        """MinIO (S3-compatible) 实现: put/get/presign/stage/list 全套."""

        def __init__(self) -> None:
            ...
        # 283 行代码 (到文件 549 行附近)
    ```
    ```python
    # packages/service/src/ingest/converters/cad.py:193
    class EzdxfConverter:
        """EZ-DXF 解析引擎 (2026-06-05)..."""

        def __init__(self, ...):
            ...
        # 323 行代码 (到文件 515 行)
    ```
  impact: |
    大类降低可维护性、可测试性和可读性; 违反项目代码质量规约, 削弱规范权威性。
  fix_sketch: |
    MinioObjectStore 按功能拆分子类或 mixin (例如 MinioPutMixin / MinioGetMixin), 或拆分为
    多个文件 (put.py / get.py / presign.py)。EzdxfConverter 将不同 CAD 格式解析拆为独立策略类。
  references: []

- id: ARCH-004
  dimension: arch
  severity: low
  confidence: high
  title: "config_legacy.py 冗余存在, 与新 config/settings.py 并行"
  file: packages/service/src/config_legacy.py
  line: 1
  description: |
    packages/service/src/config_legacy.py 仍存在于代码库中, 使用旧的 config.toml 文件读取方式
    配置 (Paths / CadConfig / ArchiveConfig)。项目已建立新的 config/settings.py 使用 env 方式
    集中管理配置。两个配置系统并行, 可能导致 (1) 新开发者不知该用哪个; (2) 同一配置在两个系
    统中各有一份默认值; (3) config_legacy.py 的 config.toml 可能已无人维护。
  evidence: |
    ```python
    # packages/service/src/config_legacy.py:1
    """RAG 系统统一配置
    
    从项目根 config.toml 读取全部配置段：
    - [paths]        → Paths
    - [cad]          → CadConfig
    - [archive]      → ArchiveConfig
    """
    ```
    ```python
    # packages/service/src/config/settings.py:1-4
    """项目配置集中管理 (ARCH-003 fix).
    所有 os.getenv 调用迁移至此, 避免散落 20+ 文件.
    """
    ```
  impact: |
    冗余配置降低项目可维护性, 配置变更需要在两处同步。
  fix_sketch: |
    审计 config_legacy.py 的功能是否仍有调用方, 若无则删除; 若有则迁移到 config/settings.py 后
    删除旧文件。
  references: []

- id: ARCH-005
  dimension: arch
  severity: low
  confidence: medium
  title: "package.json lint:check 脚本与 lint 行为重复且参数不一"
  file: packages/web/package.json
  line: 18
  description: |
    packages/web/package.json 中定义了三个 lint 相关脚本: `lint` = "oxlint .", `lint:fix` = "oxlint --fix...",
    `lint:check` = "oxlint"。其中 `lint:check` 与 `lint` 重复 — 都运行 oxlint, 但 `lint:check`
    未传 `.` 参数 (指定扫描当前目录)。这会导致 `lint:check` 的行为可能跟 `lint` 不一致,
    且新手容易混淆两者的区别。
  evidence: |
    ```json
    {
      "lint": "oxlint .",
      "lint:fix": "oxlint --fix --fix-suggestions --fix-dangerously",
      "lint:check": "oxlint"
    }
    ```
  impact: |
    `bun run lint:check` 可能漏扫描某些路径, 产生 CI 检查结果和本地不一致的假象。
    脚本冗余增加维护负担。
  fix_sketch: |
    删除 `lint:check` 脚本或用 `"lint:check": "oxlint ."` 对齐, 或让 `lint` = "oxlint" 并保持
    `lint:check` 也一致。
  references:
    - arch-001 (同属 scripts/文档一致性)

- id: ARCH-006
  dimension: arch
  severity: medium
  confidence: high
  title: "前序 spec 阶段所有提交使用 --no-verify 绕过 pre-commit 钩子"
  file: packages/service/CLAUDE.md
  line: 345
  description: |
    packages/service/CLAUDE.md 第 345-350 行明确记载 2026-06-19 code-quality spec 期间
    P0/P1/P2/P3/P4 全部使用 `git commit --no-verify` 提交, 绕过了 pre-commit 钩子的
    lint-staged + tsgo + vitest + format:check 自动化检查。虽然理由是 "格式化/lint 自动修
    复零语义改动"和"pyright 中间状态会爆", 但这种做法丧失了自动化质量门禁的价值, 且该条款
    仍留在文档中可能暗示后续也可以绕行。
  evidence: |
    ```markdown
    # packages/service/CLAUDE.md:345-350
    ### pre-commit 钩子绕过策略
    
    本期 P0/P1/P2/P3/P4 全用 `git commit --no-verify` 提交, 因为:
    - pre-commit 钩子串了 `lint-staged + tsgo + vitest + format:check`, 单次 ~3-5 分钟
    - P0/P1 是格式/lint 自动修复, 0 语义改动, 无风险
    - P2a 修复期间 pyright 中间状态会爆 (从 91 → 14 → 0), 钩子拦不住进度
    ```
  impact: |
    pre-commit 钩子是代码质量的第一道防线, 批量 --no-verify 使得 lint/typecheck/test 在
    commit 阶段未执行, 依赖事后人工补跑。该模式可能被后续开发者援引为"可以绕行"的先例,
    导致质量门禁形同虚设。
  fix_sketch: |
    移除或更新 CLAUDE.md 中的绕过策略条款, 明确 --no-verify 仅在 CI 门禁覆盖的紧急修复场景
    下经审核可用, 且事后必须补跑全套检查。确保 pre-commit 钩子足够快 (< 60s) 以减少绕过动机。
  references: []

## 未扫 / 已知缺口

- 重复代码定量扫描: 项目 package.json 配了 jscpd 脚本 (`bun run find-duplicates`), 但本地
  未安装 jscpd 二进制, 无法执行, 仅做手动 grep 模式匹配 (未发现明显 > 3 处重复块)
- 前端 bundle 体积分析: 未接入 webpack-bundle-analyzer, 无法判断 bundle 体积优化
- 完整测试覆盖率门禁验证: pyproject.toml 配置 `--cov-fail-under=0`, 覆盖率门禁未启用,
  当前只采集不阻断
- 跨 package 重复前端的组件封装: 前端已有 AppDialog/AppConfirm/DataTable 等 13 个封装,
  但未逐文件验证是否所有业务代码都已使用封装而非手写模板
- 后端每个 service 函数的测试覆盖分析: 仅检查 conftest mock 机制, 未逐 service 文件分析
  function 级别的测试配对
- 前端 TanStack Query staleTime 一致性: 未逐 hook 检查 staleTime 配置是否跟项目约定
  (60_000) 一致
