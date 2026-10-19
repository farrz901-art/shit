# Pyright 严格模式可行性分析 (2026-07-08)

> **审计员**: A4 Pyright Strict Analyzer
> **项目根**: `/home/deyuan/rag/rag/packages/service`
> **pyright 版本**: 1.1.410
> **Python**: 3.14
> **关键约束**: 每次修改 pyrightconfig.json 后必须 `git checkout packages/service/pyrightconfig.json` 恢复原状, 最终工作区已确认干净.

## Metadata

| 项 | 值 |
|---|---|
| 日期 | 2026-07-08 |
| pyright 版本 | 1.1.410 |
| 当前 typeCheckingMode | basic |
| 扫描 agent | A4 (Explore, run_in_background) |

## 当前 pyrightconfig.json (基线)

```json
{
  "include": ["src", "tests", "scripts"],
  "exclude": [
    "**/__pycache__",
    "**/.venv",
    "**/node_modules",
    "**/data",
    "**/ingest_uploads",
    "**/reports"
  ],
  "pythonVersion": "3.14",
  "typeCheckingMode": "basic",
  "reportMissingTypeStubs": "none",
  "reportUnknownMemberType": "none",
  "reportUnknownVariableType": "none",
  "reportUnknownArgumentType": "none",
  "reportUnknownParameterType": "none",
  "reportUnknownLambdaType": "none"
}
```

关闭了 6 类 `reportUnknown*` 规则, 这是 baseline 0 error 维持的代价.

## L0: 基线 (basic mode)

| 指标 | 值 |
|---|---|
| typeCheckingMode | basic |
| reportUnknown* 设为 none 数量 | 5 |
| 当前 error 总数 | **2** |
| 0 error 文件数 | **473 / 475** |
| 0 warning 文件数 | 475 / 475 |

**2 个 error 详情** (test 路径, 都是 pre-existing, 不在 src/):
1. `tests/ingest/test_mineru_container_cleanup.py:19:6` — `reportMissingImports`, 找不到 `src.ingest.converters` (跟 A1 [bug] 9 ingest 路径未跟迁是同一根因)
2. `tests/ingest/test_pipeline.py:8:24` — `reportAttributeAccessIssue`, `pipeline` 不是 `src.ingest` 的属性 (同上)

注: 这是 2026-06-19 code-quality spec 留下的 src/ 0 error 状态 (见 CLAUDE.md "pyright errors 91 errors → 0 errors"). 测试侧 2 个 import 错是 mock 路径下 converter 模块重构历史问题, 不在 src/.

## L1: reportUnknown* none → warning

| 规则 | warning 数 | 重灾区文件 |
|---|---|---|
| reportUnknownMemberType | **3083** | `src/ingest/pdf_processing/converters/cad.py` (179), `src/product_decoders/engine.py` (162), `tests/kg/test_kg_client.py` (113) |
| reportUnknownVariableType | **2019** | `tests/buyer_profile/test_router.py` (164), `tests/auth/test_admin_users_api.py` (143), `tests/chat/test_service_mock.py` (130) |
| reportUnknownParameterType | **1455** | `tests/auth/test_account_settings_router_mock.py` (148), `tests/buyer_profile/test_service.py` (113), `tests/kg/test_router_auth.py` (106) |
| reportUnknownArgumentType | **908** | (分散在 ORM Column 推断 + pytest fixture 边界) |
| reportUnknownLambdaType | **104** | (极少) |
| **总计** | **7569 warnings** | — |

**Top-10 命中文件** (按 warning 数):
1. `src/ingest/pdf_processing/converters/cad.py` (179)
2. `tests/buyer_profile/test_router.py` (164)
3. `src/product_decoders/engine.py` (162)
4. `tests/auth/test_account_settings_router_mock.py` (148)
5. `tests/auth/test_admin_users_api.py` (143)
6. `tests/chat/test_service_mock.py` (130)
7. `tests/kg/test_kg_client.py` (113)
8. `tests/buyer_profile/test_service.py` (113)
9. `tests/kg/test_router_auth.py` (106)
10. `tests/memory/test_router.py` (103)

**结论**: warning 不影响 CI (默认 exit 0), **7569 个 warning** 量级过大需按 module 逐文件修. 但因为是 warning 而非 error, 可以立即开启作为 type hint 缺口地图. 建议优先: src/ 强类型缺口 (cad.py, engine.py) → 再修 tests/ mock fixture 边界.

## L2: typeCheckingMode basic → standard

| 指标 | 值 |
|---|---|
| typeCheckingMode | standard |
| reportUnknown* 状态 | 保持 none |
| 总 error | **6** |
| Top 5 文件 | (见下) |
| vs L0 delta | **+4** |

**6 个 error 分布** (按文件):
| 文件 | error 数 | 错误类型 |
|---|---|---|
| `tests/auth/test_login.py` | 2 | reportPossiblyUnboundVariable (line 202, 出现 2 次) |
| `src/ingest/pdf_processing/converters/kreuzberg.py:40` | 1 | 方法签名不兼容替代 Converter 父类 |
| `src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:24` | 1 | 方法签名不兼容替代 TableExtractor 父类 |
| `tests/ingest/test_mineru_container_cleanup.py:19` | 1 | reportMissingImports (L0 已有) |
| `tests/ingest/test_pipeline.py:8` | 1 | reportAttributeAccessIssue (L0 已有) |

**与 L0 对比**: L0 的 2 个 error 全保留 + 4 个新 error:
- 2 个 ABC 子类方法签名不兼容 (`kreuzberg.py`, `pymupdf_extractor.py`) — Converter / TableExtractor 子类 override 时返回类型/参数类型与 ABC 不完全匹配
- 2 个 reportPossiblyUnboundVariable (test_login.py:202 — `r` 在 try/except 分支可能未绑定)

**结论**: 🟡 **强烈推荐升级到 standard**. 只多 4 个 error 且分布集中:
- 2 个 src/ ABC 兼容性 (子模块 spec 修)
- 2 个 tests/auth/ 局部变量绑定 (一个 PR 改完)
- L0 已有的 2 个 import 错保持

整体修复成本估算: **1-2 PR, 半天**.

## L3: standard + 逐个加 strict 规则

每条规则在 standard 基础上独立加, 其余 reportUnknown* 保持 none:

| 规则 | 总 error | vs L2 delta |
|---|---|---|
| reportOptionalMemberAccess | **6** | 0 |
| reportOptionalSubscript | **6** | 0 |
| reportOptionalCall | **6** | 0 |
| reportOptionalIterable | **6** | 0 |
| reportOptionalContains | **6** | 0 |
| reportOptionalChain | **6** | 0 |

**结论**: 6 条规则**全部命中数为 0**. 这表明项目代码风格偏防御性 (Optional[T] 用得少或已用 `assert x is not None` / `if x is None: raise` 保护). 这 6 条规则可以**白嫖**—全部开启, 不引入任何新 error.

**结论**: 🟢 **视规则全部加, 零成本**. 不需要分批.

## L4: typeCheckingMode strict

| 指标 | 值 |
|---|---|
| typeCheckingMode | strict |
| 总 error | **1836** |
| 阈值 | > 1000 → 仍记录, 不跳过 |
| vs L2 delta | **+1830** |

**严重程度**: 1,836 个 error 大幅超出 100 阈值. 分布在 src/ + tests/ 全栈, 主要是:
- strict 默认开 `reportUnknown*` (5 条) + `reportOptional*` (6 条) + `reportAttributeAccessIssue` + `reportArgumentType` 等
- 与 L1 的 7,569 warning 一致: 项目大量 ORM Column / third-party lib 无 stub / Any 推断
- 与 L0 的 2 error 相比 +1,834, 反映 strict 对隐式 Any 不容忍

**结论**: ❌ **暂不可行**. 项目无 Python 全套类型注解 (尤其 src/ingest/pdf_processing + tests/mock fixture 边界). 修复成本估算: 1-2 周 (分散到 5+ PR). 后续可以分两阶段推进:
1. 先把 L1 的 warning 当 backlog 按模块消 (尤其 src/ingest/ 与 src/product_decoders/)
2. 等 warning 数降到 <500, 再开 strict

## 结论与建议

| 层级 | 可行性 | 推荐度 | 工作量 |
|---|---|---|---|
| **L1** (reportUnknown* → warning) | ✅ 立即可做 | 🟢 **高** | 0 (改 1 行 JSON), warning 后续按 module 修 |
| **L2** (basic → standard) | ✅ 推荐 | 🟡 中 | 1-2 PR, 半天 |
| **L3** (standard + 6 optional rules) | ✅ 零成本 | 🟢 **高** | 0 (改 6 行 JSON), 可与 L2 合并提交 |
| **L4** (strict) | ❌ 1,836 error 暂不可行 | ⚪ 低 | 1-2 周, 后续 spec |

### 推荐 PR 序列

1. **PR-A (本周)**: L2 + L3 合并 — `typeCheckingMode: standard` + 6 个 reportOptional* 全 error. 共 6 error, 半天修.
2. **PR-B (后续 backlog)**: L1 — `reportUnknown*: warning`. 不改 type strictness, 但提供缺口地图, 按模块分批消 warning.
3. **PR-C (远期)**: L4 — 等 PR-B 把 src/ warning 消到 <500 后再开 strict.

### 关键修复点 (L2 立即可修)

- `src/ingest/pdf_processing/converters/kreuzberg.py:40` — Converter 子类签名匹配 ABC
- `src/ingest/pre_analysis/table_extractors/pymupdf_extractor.py:24` — TableExtractor 子类签名匹配 ABC
- `tests/auth/test_login.py:202` — `r = await ...` 在 try/except 后未绑定分支, 加 `r = None` 初始化或显式 raise
- `tests/ingest/test_mineru_container_cleanup.py:19` + `test_pipeline.py:8` — import 路径修复 (mock fixture 残留)

## 元数据

- **最终工作区状态**: 干净 (git status 显示 pyrightconfig.json 无未提交改动)
- **总工具调用**: 16 次 (含 L0-L4 + restoration 6 次 + verification 1 次)
- **pyright 版本**: 1.1.410 (有 1.1.411 可升, 不影响本审计)
- **审计员备注**: 测试侧 2 个 import 错是 mock fixture 跨包导入的固有特征, 与 type strictness 无关, 推荐单独立 spec 处理.
