# 代码质量提升路线图 (2026-07-08)

> 来源: 4 维度并行扫描 (A1 测试 / A2 pyright ignore / A3 lint ignore / A4 pyright 严格模式)
> 原始报告:
> - [test-failures.md](2026-07-08-test-failures.md) — 70 条测试失败
> - [pyright-ignores.md](2026-07-08-pyright-ignores.md) — 116 处 type: ignore
> - [lint-ignores.md](2026-07-08-lint-ignores.md) — 136 noqa + 218 oxlint ignore
> - [pyright-strict-audit.md](2026-07-08-pyright-strict-audit.md) — 4 层级分析

## 汇总

| 优先级 | 数量 | 主要行动 | 复杂度 |
|---|---|---|---|
| **P0 测试修复** | 50 test | useTranslations provider + ingest 路径未跟迁 | 🟡 |
| **P1 ignore 清理** | ~60 条 | 删 pyright [dead] + 8 条 oxlint [fixable-code] | 🟢 |
| **P2 配置优化** | ~108 条 | oxlintrc 加 overrides + 调阈值 + sed 删 stale 12 | 🟢 |
| **P3 pyright 升级** | L2+L3 合并 | basic→standard + 6 optional 规则, 0 new error | 🟢 |
| **P4 观察项** | ~120 条 | keep / stub / test 类别, 不动 | ⚪ |
| **P5 PG 违规** | 0 条 | 无违规, 持续监控 | ⚪ |
| **环境依赖** | 3 test | ODA / mineru 镜像 / Docker 网络, 留给 CI 维护 | ⚪ |

> 整体趋势: 后端**越来越干净** (noqa 100% 合规, 0 裸 ignore), 前端 oxlint 有 ~67% 优化空间. pyright ignore 大多是"防御性残留" (被禁规则下不触发), 升 strict 模式前要先消 6 条 ORM [rule-up].

## P0: 测试修复 (50 条)

来源: [A1 test-failures.md §关键发现](2026-07-08-test-failures.md#关键发现--优先修复建议)

### P0.1: useTranslations 缺 NextIntlClientProvider (前端 41 条)

- **位置**: 跨 41 个 test 文件, 根因 `components/common/table/data-table-pagination.tsx:64` 调 `useTranslations()`
- **修法**: `packages/web/vitest.setup.ts` 全局 setupFiles 加 NextIntlClientProvider 包装, 或 `test-utils/render-with-intl.tsx` 加默认 wrapper
- **风险**: 低, 不动业务代码
- **影响**: 41 test 全绿

### P0.2: ingest 源码重组后测试路径未跟迁 (后端 9 条)

- **位置**:
  - `tests/ingest/test_mineru_container_cleanup.py:19` (collection error)
  - `tests/ingest/test_pipeline.py:8` (collection error)
  - `tests/ingest/test_converter_base.py` (4 test, FileNotFoundError)
  - `tests/ingest/test_pdf_analyzer.py` (5 test, FileNotFoundError)
- **实际源码位置**: `src/ingest/pdf_processing/converters/` / `src/ingest/pdf_processing/analyzers/`
- **修法**: 改 import / fixture path 字符串
- **风险**: 低, 只动测试

### P0.3: 单点修复 (4 条)

- `tests/chat_share/test_service.py:159` — mock session 缺 share 实体 owner=42
- `tests/core/test_audit_hooks.py:45` — EXPECTED_HOOKS 列表 ingest/api.py 跟迁
- `tests/lookups/test_seed.py:202` — 期望值 27 改 33 (含 6 个新 lookup)
- `tests/test_docs_structure.py:46` — README 链接修复 (或恢复 yaml)

## P1: ignore 清理 (~60 条)

### P1.1: pyright [dead] 批量删除 (~50 条)

来源: [A2 pyright-ignores.md §结论](2026-07-08-pyright-ignores.md#结论)

- **现状**: 66 SRC + 50 TEST = 116 条 type: ignore, 抽样 13 文件全部 pyright 0 errors
- **根因**: pyrightconfig 关掉 6 类 reportUnknown* 规则, 多数 ignore 错误码对应被禁规则
- **修法**: 全量删除实验 + pyright 验证 + 必要时加 cast 保险
  ```bash
  # 实验脚本
  for f in $(grep -rl "type: ignore" src tests --include="*.py"); do
    sed -i.bak '/type: ignore/d' "$f"
    uv run pyright "$f" || { git checkout "$f"; break; }
  done
  ```
- **风险**: 低 (高 ROI, 0 风险, 抽样已验证)
- **预计**: 116 → ~60 条, 净消 ~50 条

### P1.2: oxlint [fixable-code] 8 条

来源: [A3 lint-ignores.md §4.2](2026-07-08-lint-ignores.md#42-fixable-code-修复项-8-条)

| ID | 文件 | 规则 | 改法 |
|---|---|---|---|
| FC-01 | `lib/api/queries.ts:101` | @typescript-eslint/no-explicit-any | TanStack mutation 类型收窄 |
| FC-02 | `lib/chat/sse.ts:62` | max-statements | 加注释 (流式核心) |
| FC-03 | `lib/hooks/use-*.tsx:44` | max-statements | 拆 2-3 个 hook |
| FC-04 | `lib/api/admin-client.ts:1` | id-length, max-statements | 拆文件 |
| FC-05 | `lib/chat/memory-integration.test.ts:30` | new-cap | alias `_GET = GET` |
| FC-06 | `app/api/chat/.../route.ts:30` | max-statements | 加注释 |
| FC-07 | `lib/chat/parseSseStream.ts:50` | max-statements | 提取 `EVENT_DISPATCHERS` dict |
| FC-08 | `lib/chat/parseSseStream.ts:55` | unicorn/prefer-ternary | 改用三元 |

### P1.3: pyright [fixable] 1 条

- PYR-034 `src/kg/splitters/base.py:39` — `h.hexdigest()[:12]` 实测 dead, 删 ignore + 加 `cast(str, ...)`

## P2: 配置优化 (~108 条)

### P2.1: oxlintrc 加 overrides (消 108 条)

来源: [A3 lint-ignores.md §4.1](2026-07-08-lint-ignores.md#41-fixable-config-建议-overrides-一次改完可消-108-条)

加 overrides 段豁免 test / e2e / animations 目录:

```json
{
  "rules": { ... },
  "overrides": [
    {
      "files": ["**/*.test.*", "**/*.spec.*", "**/__tests__/**", "**/e2e/**"],
      "rules": {
        "no-magic-numbers": "off",
        "max-statements": "off",
        "id-length": "off",
        "no-ternary": "off",
        "init-declarations": "off",
        "sort-imports": "off",
        "new-cap": "off",
        "no-underscore-dangle": "off",
        "max-params": "off",
        "arrow-body-style": "off",
        "vitest/prefer-lowercase-title": "off"
      }
    },
    {
      "files": ["**/components/animations/**", "**/components/motion/**"],
      "rules": {
        "no-magic-numbers": "off",
        "id-length": "off"
      }
    }
  ]
}
```

- **风险**: 低 (只影响 test/e2e/animations 子目录)
- **预计**: 218 oxlint → ~110, 净消 ~108 条

### P2.2: id-length exceptions 扩展 + max-statements 阈值上调

- `id-length exceptions`: `["y", "x"]` → `["y", "x", "T", "e", "d", "s", "r", "c", ...]` (单字母白名单, 覆盖 TanStack + 回调短名)
- `max-statements: 15 → 25` (项目组件平均 18-22, 偏严)
- **风险**: 中 (max-statements 阈值变化需 lint diff 验证)

### P2.3: 批量删 stale 注释 (12 条)

- `no-ternary: off` + `sort-imports: off` 已设, 但残留 12 条 stale 注释
- `sed -i '/eslint-disable-next-line sort-imports\|no-ternary/d' packages/web/**/*.{ts,tsx}`
- **风险**: 低 (规则已 off, 删注释无影响)

## P3: Pyright 升级 (L2 + L3 合并)

来源: [A4 pyright-strict-audit.md §L2/L3](2026-07-08-pyright-strict-audit.md#l2-typecheckingmode-basic--standard)

### PR-A: pyrightconfig.json 一次改完

```json
{
  "typeCheckingMode": "standard",
  "reportOptionalMemberAccess": "error",
  "reportOptionalSubscript": "error",
  "reportOptionalCall": "error",
  "reportOptionalIterable": "error",
  "reportOptionalContains": "error",
  "reportOptionalChain": "error"
}
```

- **预期**: 6 个新 error (2 src ABC + 2 test_login try/except + 2 L0 已有)
- **修复**:
  - `src/ingest/pdf_processing/converters/kreuzberg.py:40` — Converter 子类签名匹配 ABC
  - `src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:24` — TableExtractor 子类签名匹配 ABC
  - `tests/auth/test_login.py:202` — `r = None` 初始化
  - `tests/ingest/test_mineru_container_cleanup.py:19` + `test_pipeline.py:8` — import 路径修复
- **工作量**: 1 PR, 半天
- **风险**: 低 (L3 6 条规则零命中, 已经是项目现状)
- **可选前置**: 6 条 [rule-up] ORM Column 加 `cast()` 防御 (PYR-007/008/012/013/041)

### PR-B: reportUnknown* → warning (L1, 后续 backlog)

- **现状**: baseline 0 error 是靠关 6 类 reportUnknown* 维持的
- **建议**: 改 warning 后, 7,569 个 warning 暴露真实类型盲区, 按 module 逐文件修
- **不影响 CI**: warning exit 0
- **工作量**: 改 1 行 JSON, warning backlog 长期消化

## P4: 观察项 (不动)

### 后端 noqa 100% 合规

136 条 noqa 全部 [keep]:
- 99 E402 (延迟 import 避免循环 / 重型依赖)
- 24 F401 (model 注册 / re-export)
- 5 ARG001 (FastAPI 鉴权守卫)
- 4 BLE001 (收口异常, 带注释)
- 其它 4 条 (兼容旧 API 签名)

**结论**: 0 修复项, 符合 CLAUDE.md §后端 Rust-like 严格准则.

### pyright [stub] / [rule-up] / [test-mock]

- [stub] 30 条 SRC: SQLAlchemy ORM / boto3 / pymupdf / kreuzberg / Pillow / httpx 等第三方库类型推断限制, **不可修**
- [rule-up] 6 条 SRC: ORM Column 推断, 升 strict 必爆, 需 `cast()` 防御
- [test-mock] 38 条 TEST: 故意传非法值 / 动态模块属性 / 协议绕开, 全部带具体错误码, 符合规范

### oxlint [keep] 102 条

- framer-motion 动画 (3 条): 贝塞尔曲线 / 透明度循环, 合理
- SSE 流解析核心 (~10 条): 拆分会破坏 reader/abort 闭包
- 测试 fixture + e2e: 已在 P2.1 overrides 覆盖范围
- 业务 guard + 上游库约束: 合理保留

### 测试 [env] 3 条

- `tests/ingest/test_cad_converter.py::test_convert_dwg_runs_with_real_oda_when_installed` — 沙箱缺 ODA
- `tests/ingest/test_cad_oda.py::test_dwg_does_not_raise_oda_not_installed_when_installed` — 同上
- `tests/integration/test_mineru_retry_e2e.py::test_mineru_retry_e2e_experiment_d` — 沙箱无 Docker Hub 网络

**建议**: 留给 CI 维护方处理 (装 ODA / 预 pull 镜像 / 镜像缓存), 不在代码质量修复范围.

## P5: PG 违规扫描 ✅ 0 违规

来源: [A1 test-failures.md §pg-violation](2026-07-08-test-failures.md#pg-violation-连真-pg-违规扫描)

- **方法**: Grep `db_session|session_scope|PG_*` (41 文件命中) + `pytest.mark.integration` (4 文件) + 实际 pytest 输出无 `psycopg` / `OperationalError` 报错
- **结论**: **0 个 pg-violation**. 所有 PG 接触 test 都走 `db_session` fixture (模式 2) 或 `@pytest.mark.integration` (合法模式 2 显式标)
- **保持现状**: 持续监控

## 修复优先级建议

1. 🟡 **P0.1**: 修 `useTranslations` provider (消 41 test) — 本周
2. 🟡 **P0.2**: ingest 测试路径跟迁 (消 9 test) — 本周
3. 🟡 **P0.3**: 4 个单点修复 — 本周
4. 🟢 **P1.1**: pyright [dead] 批量删除实验 (消 ~50 条) — 本周
5. 🟢 **P2.1**: oxlintrc 加 overrides (消 ~108 条) — 下周
6. 🟢 **P2.3**: 批量删 stale 注释 (消 12 条) — 下周
7. 🟢 **P3 PR-A**: pyright standard + 6 optional 规则 (0 new error) — 下周
8. 🟢 **P1.2**: 8 条 oxlint [fixable-code] — 月底
9. ⚪ **P3 PR-B**: reportUnknown* warning (backlog) — 长期
10. ⚪ **L4 strict**: 等 PR-B 消化后再说 — 远期

## 不实施

- **L4 pyright strict** (1,836 error, 1-2 周成本, 暂缓)
- **[keep] 类别** (业务合理 / 上游库约束)
- **[stub] / [test-mock] / [rule-up]** (第三方库限制 / 测试故意)
- **[env] 3 条** (沙箱缺外部依赖, 留给 CI 维护)

## 历史对比 (vs 2026-07-07)

| 维度 | 2026-07-07 | 2026-07-08 | 变化 |
|---|---|---|---|
| pytest fail | 22 fail + 38 errors (pre-existing) | 15 fail + 9 error + 2 collection | 改善 36 条 |
| vitest fail | (未单列) | 44 (主因 useTranslations 41) | 新增 useTranslations 维度 |
| pyright ignore | (未单列) | 66 SRC + 50 TEST | 116 总数 |
| noqa | (未单列) | 136 (100% 合规) | — |
| oxlint ignore | (未单列) | 218 (67% 优化空间) | — |
| pyright mode | basic | basic (L2 推荐升级) | 待执行 |
