# Code Quality Audit (代码体检归档)

> 本目录是 `/code-quality-scan` 4 维度并行扫描的归档.

## 命名约定

- `YYYY-MM-DD/` — 每次扫描的子目录
- `YYYY-MM-DD-test-failures.md` — A1 测试失败快照
- `YYYY-MM-DD-pyright-ignores.md` — A2 pyright type:ignore 审计
- `YYYY-MM-DD-lint-ignores.md` — A3 lint ignore (noqa + oxlint) 审计
- `YYYY-MM-DD-pyright-strict-audit.md` — A4 pyright 严格模式可行性 (L0-L4)
- `YYYY-MM-DD-code-quality-plan.md` — 6 级优先级合成路线图
- `YYYY-MM-DD-findings.md` — 顶层 checklist (跨多次扫描的历史)

## 维度固定标签

**A1 测试**: `[bug] [env] [regression] [flaky] [config] [pg-violation]`
**A2 pyright**: `[stub] [fixable] [dead] [rule-up] [test-mock]`
**A3 lint**: `[keep] [fixable-code] [fixable-config] [downgrade] [dead]`
**A4 strict**: `L0 (basic) / L1 (删 reportUnknown* none) / L2 (standard) / L3 (+optional rules) / L4 (strict)`

## 优先级映射

```
P0   = A1 [bug] + [regression]    → 立即修
P1   = A2 [fixable] + A2 [dead] + A3 [fixable-code]  → 逐个清
P2   = A3 [fixable-config] + A4 L1/L2/L3 → 调配置
P3   = A3 [downgrade]  → sed 批量删
P4   = [keep] / [stub] / [test]   → 不动
P-scan = A1 [pg-violation]        → 强制规范, 最高优先级
```

## 归档列表

| 日期 | 报告数 | finding 总数 | 备注 |
|---|---|---|---|
| 2026-07-10 | 1 | oversize-files v2: 42 文件 / 27 verified / 15 refuted | 详见 [2026-07-10-findings.md](2026-07-10-findings.md) |
| 2026-07-08 | 5 | 4 维度 / 6 级优先级 | 详见 [2026-07-08-findings.md](2026-07-08-findings.md) |
| 2026-07-07 | 6 | 6 维度 / 62 finding / 17 verified / 4 refuted | 详见 [2026-07-07-findings.md](2026-07-07-findings.md) |

## 使用方法

```bash
# 跑一次扫描 (自动派 4 个 subagent)
/code-quality-scan

# 只跑某个维度
/code-quality-scan --only tests
/code-quality-scan --only strict
```

**Hard rules** (主线程必须遵守):

- ❌ 永不修改 `packages/*/src/**` 或 `packages/service/tests/**`
- ❌ 永不修改 `pyrightconfig.json` / `oxlintrc.json` / `tsconfig.json` 持久状态 (A4 临时测试后必须 `git checkout` 恢复)
- ❌ 永不在 subagent prompt 里硬编码数字
- ✅ 报告输出严格按命名约定 (子目录 + 固定文件名)
