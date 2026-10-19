# 代码质量提升路线图 (2026-06-25)

> 来源: 4 维度并行扫描 (A1 Test / A2 Pyright / A3 Lint / A4 Pyright Strict)
> 原始报告:
> - [2026-06-25-test-failures.md](2026-06-25-test-failures.md) — 49 条测试失败
> - [2026-06-25-pyright-ignores.md](2026-06-25-pyright-ignores.md) — 78 处 type: ignore
> - [2026-06-25-lint-ignores.md](2026-06-25-lint-ignores.md) — 26 noqa + 172 oxlint ignore
> - [2026-06-25-pyright-strict-audit.md](2026-06-25-pyright-strict-audit.md) — 4 层级严格模式分析

---

## 汇总

| 优先级 | 数量 | 主要行动 | 复杂度 |
|---|---|---|---|
| **P0 测试修复** | 49 条 | 修 bug + 修回归 | 🔴 中 |
| **P5 重写 PG 测试** | 22 条 | 改为模式 1 mock，禁止连真 PG | 🔴 大 |
| **P1 清理 ignore** | 9 条 | 删 fixable type:ignore + dead noqa + fixable lint | 🟡 低 |
| **P2 配置优化** | ~35 条 | oxlintrc 加 `overrides` 消过半 lint ignore | 🟢 低 |
| **P3 pyright 升级** | L2 standard | 只多 5 error，建议升 | 🟡 低 |
| **P4 观察项** | — | 8,272 error L4 strict 暂不可行 | ⚪ 极高 |

---

## P0: 测试修复 — 真 bug (8 条) + 回归 (5 条) + flaky (14 条)

### 真 bug (8 条)
| ID | 类别 | 文件 | 根因 | 修复建议 |
|---|---|---|---|---|
| TF-01 | [bug] | tests/auth/test_config.py | `CONFIG_FILE` 从 `src.config` 移除 | 更新 import |
| TF-02 | [bug] | tests/memory/test_router.py:2 | MemoryService 异常处理方式变更 | 同步测试 mock |
| TF-03 | [bug] | tests/memory/test_service.py | 同上 | 同步测试 mock |
| TF-04 | [bug] | tests/auth/... | email token naive vs aware datetime | 统一 timezone |
| TF-05 | [bug] | 前端契约测试 | 后端新路由未同步前端期望 | 跑 `test_api_contract.py` |
| TF-06~08 | [bug] | 前端 3 条 | 见 test-failures.md | 待分析 |

### 回归 (5 条) — vitest
| ID | 文件 | 原因 |
|---|---|---|
| TF-09~13 | vitest 5 条 | `router.push`/`router.back` mock 未按预期调用，与 useRouter 实现变更可能有关 |

### Flaky (14 条) — Redis circuit breaker 状态污染
| ID | 文件 | 根因 |
|---|---|---|
| TF-14~27 | tests/core/test_redis_client.py 等 | `_circuit_open_until` 全局状态被破坏后未重置, 测试单独跑通过, 全量跑失败 |

---

## P5: PG 违规测试 (22 条) ⚠️ 最重

### 违规模式
`monkeypatch.setattr("src.storage.session_scope", ...)` 只 patch 了 `src.storage.session_scope`, 但 `src.middleware.auth.session_scope` / `src.eval.router.session_scope` 等别名路径没覆盖。

### 文件分布
| 文件组 | 数量 | 修复策略 |
|---|---|---|
| `tests/auth/` | 8 | mock 链路径不全 — 用 `tests/conftest.py` 的 `mock_all_db_connections` 覆盖所有 namespace 别名 |
| `tests/ingest/` | 8 | create_app + file path 问题 — 添加 `src.ingest.api.session_scope` patch |
| `tests/eval/` | 2 | 同上 |
| `tests/lookups/` | 2 | 需加 session_scope 路径全覆盖 |
| 其他 | 2 | — |

**关键**: 这些 PG 违规不是故意恶意，而是 `session_scope` 被 import 到各模块后用了全局 `monkeypatch.setattr`，但新路径没覆盖到。修复方式不是删依赖，而是 **加全路径 patch** 或改用 `unittest.patch` 在 import 前。

---

## P1: ignore 清理 (9 条，低风险)

### 可修 type:ignore (8 条)
| ID | file:line | 标签 | 改法 |
|---|---|---|---|
| PYR-005 | health/checks.py:243 | [fixable] | 改 `store._bucket` → getter 方法 |
| PYR-006 | health/checks.py:253 | [fixable] | 同上 |
| PYR-007 | health/checks.py:254 | [fixable] | 同上 |
| PYR-008 | embedder.py:79 | [fixable] | 改类型注解 |
| PYR-009 | embedder.py:90 | [fixable] | 同上 |
| PYR-010 | chat_share/service.py:172 | [fixable] | 改 file.read() 类型推断 |
| PYR-011 | ingest/converters/kreuzberg.py:11 | [fixable] | 改 try/import 模式 |
| PYR-012 | ingest/converters/kreuzberg.py:15 | [fixable] | 同上 |

### 已过期 / 可删 (1 条)
| ID | file:line | 类型 | 说明 |
|---|---|---|---|
| PYR-013 | eval/runner.py:255 | [dead] | pyright 已不报 `[misc]`, 直接删 |

### 可修 lint (1 条 noqa + ~6 条 oxlint)
| ID | 文件 | 类型 | 改法 |
|---|---|---|---|
| NOQA-024 | kg/client.py:92 | [fixable-code] | 收窄 `except Exception` -> `except (SpecificError, ...)` |
| LINT-xxx | 前端 6 处 | [fixable-code] | 改用 typed any / 改变量名 |

---

## P2: 配置优化 (~35 条，一次改完)

**核心建议**: 在 `.oxlintrc.json` 加 `overrides` 段，消掉 ~80-100 处 lint ignore

```json
{
  "rules": { ... 现有规则 ... },
  "overrides": [
    {
      "files": ["**/*.test.*", "**/*.spec.*", "**/e2e/**"],
      "rules": {
        "no-magic-numbers": "off",
        "max-statements": "off",
        "id-length": "off",
        "no-ternary": "off",
        "sort-imports": "off",
        "init-declarations": "off"
      }
    }
  ]
}
```

**效果**: 172 处 oxlint ignore 中 ~80-100 条测试文件专用 ignore 可删除, 仅保留 ~15 处核心逻辑 keep.

---

## P3: Pyright 升级

### 建议: 升到 L2 (standard) + 修 5 个新 error

```
typeCheckingMode: "standard"      # basic → standard
# 拿掉 5 个 reportUnknown*: "none"  # 改为默认 warning (6,758 个 warning, 0 new error)
```

5 个新 error 分布在:
- 测试文件 (3 处, 可加 `type: ignore[具体错误码]`)
- 源文件 (2 处: `multi_step_rag.py`, `kreuzberg.py`)

**L1 (reportUnknown* → warning)**: 6,758 个 warning, 不影响 CI 通过, 可按 module 逐文件修
**L3 (加 optional 规则)**: 0 额外 error, 可跟 L2 一起做

### 不推荐: L4 (full strict) — 8,272 error, 暂缓

---

## P4: 观察项 (不动)

| 项 | 说明 |
|---|---|
| noqa 24/26 条 [keep] | F401 import 副作用 / E402 import 顺序 / ARG001 守卫参数, 都有注释注明原因 |
| oxlint 15 条 [keep] | SSE 流解析 / e2e 全跳过 / framer-motion CSS 属性 / log facade |
| type:ignore 67 条 [stub] + [test] | SQLAlchemy ORM 推断 / boto3 TypedDict / 测试故意传非法值 |
| L4 pyright strict | 8,272 error, 项目无 Python 类型全套注解, 暂不推进 |

---

## 修复优先级建议

1. **🔴 P5: 修 PG 违规测试 (22 条)** — 先把 22 个 `[pg-violation]` 的 mock 路径加全, 这是强制规范
2. **🟡 P0: 修 13 个真 bug (8) + 回归 (5)** — CI 不红的必要前提
3. **🟡 P1: 清 9 个 fixable/ dead ignore** — 低风险, 几分钟
4. **🟢 P2: 改 oxlintrc overrides** — 一次配置消 ~80 lint ignore
5. **🟢 P3: 升 pyright standard** — 只多 5 error, 梯度推进
6. **⚪ P4: flaky 14 条** — 下一个 spec 专项处理 (Redis 全局状态隔离)

## 不实施

- L4 pyright strict (8,272 error, 暂缓)
- 24/26 noqa keep (合理理由)
- 15 oxlint keep (合理理由)
- 67 type:ignore stub/test (合理理由, 3rd party 库)
