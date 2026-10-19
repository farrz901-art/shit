# Lint Ignore 审计报告 (2026-06-25)

> 生成工具: A3 Lint Scanner (只读扫描)
> 范围: `packages/web` (oxlint/eslint-disable) + `packages/service/src` (noqa)

---

## 概要

| 类别 | 总数 | 文件数 | 深度分析 |
|------|------|--------|----------|
| **oxlint/eslint-disable** (TS/TSX) | **172** | 64 | 前 ~60 行深度 + 余下略 |
| **noqa** (Python) | **26** (实际 25 指令 + 1 注释文本) | 14 | 全部逐行分析 |

---

## 一、NOQA 分析 (Python, packages/service/src)

### 分类汇总

| 标签 | 计数 | 说明 |
|------|------|------|
| [keep] | 24 | 有意为之, 有充分注释 |
| [fixable-code] | 1 | bare `except Exception` 可收窄 |
| [dead/false-positive] | 1 | 注释内容含 "noqa" 文本, 非指令 |

### 详细清单

| ID | 文件:行 | 规则 | 标签 | 备注 |
|----|---------|------|------|------|
| NOQA-001 | `buyer_profile/service.py:279` | E402 | [keep] | 避免循环 import, 函数体内部 import |
| NOQA-002 | `config/__init__.py:8` | F401 | [keep] | 向后兼容, 暴露旧模块 getter |
| NOQA-003 | `chat_share/router.py:27` | F401 | [keep] | contract test (test_loguru_migration.py) 需要 |
| NOQA-004 | `core/logging.py:21` | F401 | [keep] | PII_FIELDS 集中定义 import |
| NOQA-005 | `kg/client.py:92` | BLE001 | **[fixable-code]** | bare `except Exception` — 可收窄为具体异常 |
| NOQA-006 | `ingest/__init__.py:12` | F401 | [keep] | 包级 re-export 接口 |
| NOQA-007 | `kg/audit.py:24` | ARG001 | [keep] | db_path 参数已废弃, 保留兼容调用方 |
| NOQA-008 | `storage/object_store.py:29` | F401 | [keep] | contract test 需要 |
| NOQA-009 | `permissions/cache.py:174` | ARG002 | [keep] | ttl_seconds 参数兼容旧签名 |
| NOQA-010 | `permissions/cache.py:184` | D401 | [keep] | 保留旧方法名 _refresh |
| NOQA-011 | `__init__.py:16` | E402 (file-level) | [keep] | register_routers() 定义在顶层 import 之前 |
| NOQA-012 | `ingest/api.py:7` | E402 (file-level) | [keep] | 变量定义在 from . import store 之前 |
| NOQA-013 | `ingest/api.py:25` | F401 | [keep] | resolve_user 留作依赖回退 |
| NOQA-014 | `ingest/api.py:26` | F401 | [keep] | require_page v2 RBAC 留用 |
| NOQA-015 | `storage/migrations/env.py:1` | E402 (file-level) | [keep] | alembic 子进程需要先 load_dotenv |
| NOQA-016 | `storage/migrations/env.py:12` | F401 | [keep] | model 注册给 Alembic autogenerate |
| NOQA-017 | `storage/migrations/env.py:16` | F401 | [keep] | model 注册 (同上) |
| NOQA-018 | `storage/migrations/env.py:17` | F401 | [keep] | model 注册 (同上) |
| NOQA-019 | `storage/migrations/env.py:19` | F401 | [keep] | model 注册 (同上) |
| NOQA-020 | `storage/migrations/env.py:20` | F401 | [keep] | model 注册 (同上) |
| NOQA-021 | `storage/migrations/env.py:21` | F401 | [keep] | model 注册 (同上) |
| NOQA-022 | `lookups/router.py:53` | ARG001 | [keep] | 鉴权守卫 Depends, 函数体未用 |
| NOQA-023 | `lookups/router.py:90` | ARG001 | [keep] | 鉴权守卫 Depends |
| NOQA-024 | `lookups/router.py:122` | ARG001 | [keep] | 鉴权守卫 Depends |
| NOQA-025 | `lookups/admin_router.py:510` | ARG001 | [keep] | 鉴权守卫 Depends |
| NOQA-026 | `storage/migrations/env.py:15` | — | [dead] | 注释文本含 "noqa" 字样, 非实际指令 |

### NOQA 行动项

1. **NOQA-005** (`kg/client.py:92`): 将 `except Exception` 收窄为特定 Neo4j 异常或 `except Exception as e: logger.error(...)` 再抛.
2. **NOQA-026**: 不是真正的 noqa 指令, 无需操作, 仅记录清洗.

---

## 二、oxlint/eslint-disable 分析 (TypeScript/TSX)

### 按目录分布

| 目录 | 出现数 | 文件数 |
|------|--------|--------|
| `packages/web/lib/` | 108 | 27 |
| `packages/web/components/` | 44 | 25 |
| `packages/web/app/` | 18 | 11 |
| `packages/web/e2e/` | 2 | 1 |
| **合计** | **172** | **64** |

### 规则分布 (前 10)

| 规则 | 估算次数 | 主要场景 |
|------|---------|---------|
| `no-magic-numbers` | ~50+ | 测试断言常数, 数学公式, 数组索引 |
| `max-statements` | ~30+ | 测试 describe/hook, 核心逻辑函数 |
| `init-declarations` | ~15 | if/else 代替三元模式 |
| `unicorn/prefer-ternary` | ~15 | 与 init-declarations 成对出现 |
| `id-length` | ~10 | framer-motion CSS 属性, 泛型 T, 表单 JSX |
| `no-ternary` | ~8 | 核心逻辑中故意用 if/else |
| `no-console` | ~5 | log facade 封装 |
| `sort-imports` | ~4 | oxlint 分组差异 |
| `@typescript-eslint/no-explicit-any` | ~3 | TanStack Query, vitest mock |
| `no-underscore-dangle` | ~3 | papaparse __parsed_extra, 测试重置函数 |

### 深度分析: 前 60 条分类

| 标签 | 计数 | 说明 |
|------|------|------|
| **[fixable-config]** | ~35 | test 文件 no-magic-numbers / max-statements — 可在 oxlintrc 加 test overrides |
| **[keep]** | ~15 | 核心流解析 (sse, dify), framer-motion CSS, log facade, e2e 全跳过 |
| **[fixable-code]** | ~6 | `@typescript-eslint/no-explicit-any` (3 处), `no-underscore-dangle` 可改名 (3 处) |
| **[dead/downgrade]** | ~4 | init-declarations + prefer-ternary 对 — 若 oxlintrc 已关则注释可删 |

### 关键发现

#### 1. [fixable-config] 测试文件豁免 (~35/172)

**最大优化点**: 大量 disable 集中在测试文件 (`.test.ts` / `.test.tsx`), 尤其是:

- `packages/web/lib/api/knowledge.test.ts` — 16 处 disable (主要是 no-magic-numbers)
- `packages/web/lib/api/approvals.test.ts` — 10 处 disable
- `packages/web/lib/api/evaluate.test.ts` — 7 处 disable
- `packages/web/lib/chat/memory-integration.test.ts` — 7 处 disable
- `packages/web/lib/api/memory.test.ts` — 6 处 disable

**建议**: 在 `packages/web/.oxlintrc.json` 添加 overrides 豁免测试文件:

```json
{
  "overrides": [
    {
      "files": ["**/*.test.*", "**/*.spec.*", "**/e2e/*"],
      "rules": {
        "no-magic-numbers": "off",
        "max-statements": "off",
        "no-ternary": "off",
        "id-length": "off",
        "max-params": "off",
        "init-declarations": "off",
        "sort-keys": "off",
        "sort-imports": "off"
      }
    }
  ]
}
```

这单一改动预计可消除 **~80-100 处** disable 注释.

#### 2. [keep] 核心逻辑豁免 (~15/172)

- `lib/chat/sse.ts:12,53` — max-statements: SSE 流解析紧密循环, 拆分会破坏 reader/abort 生命周期
- `lib/chat/use-chat-state.ts` — 6 处 max-statements: hooks + handler 分组, 逻辑紧凑
- `lib/chat/dify.ts` — 4 处 max-statements: 流式消息处理 + dispatch 查表
- `components/common/motion/*` — id-length: framer-motion CSS 属性名 `y`/`x`
- `lib/log.ts` — 4 处 no-console: log facade 故意包装
- `e2e/chat-full-flow.spec.ts:13` — file-level oxlint-disable: Playwright 串行场景复杂

#### 3. [fixable-code] 可改代码消除 (~6/172)

- `app/[locale]/buyers/[id]/page.tsx:97` — `@typescript-eslint/no-explicit-any`: TanStack Query mutation 类型, 可用 `UseMutateAsyncFunction` 代替
- `lib/chat/use-chat-state.ts:266` — `@typescript-eslint/no-explicit-any`: 同上
- `components/common/submit-button.test.tsx:54` — `@typescript-eslint/no-explicit-any`
- `lib/parse/parse-eval-csv.ts:30` — `no-underscore-dangle`: `__parsed_extra` papaparse 约定字段
- `lib/api/rsc-queries.test.ts:26/33/69` — `no-underscore-dangle`: 测试重置函数名, 可改为 `reset_*`

#### 4. [dead/downgrade] 可清理 (~4/172)

多对 `init-declarations` + `unicorn/prefer-ternary` 同时出现:
- `components/ui/button.tsx:40/42` — no-ternary 已 off, 应校验当前 oxlint 是否仍触发
- `components/ui/form.tsx:147/149` — 同上
- `components/ui/calendar.tsx:49/51` — 同上
- `components/common/motion/pressable.tsx` — 同上

**若 oxlintrc 已关 `no-ternary` + `prefer-ternary`, 这些注释是 dead code.** 需要确认 oxlint 版本行为.

---

## 三、oxlintrc.json 现状

```json
{
  "categories": {
    "correctness": "error",
    "suspicious": "warn",
    "style": "warn"
  },
  "rules": {
    "id-length": ["warn", { "exceptions": ["y", "x"] }],
    "no-unused-vars": "error",
    "no-console": "off",
    "complexity": ["error", { "max": 20 }],
    "unicorn/no-null": "off",
    "prefer-ternary": "off",
    "no-ternary": "off",
    "sort-keys": "off",
    "sort-imports": "off",
    "capitalized-comments": "off"
  },
  "ignorePatterns": ["node_modules", ".next", "out"]
}
```

**缺失项**:
1. 无 `overrides` 段 — 测试文件豁免缺失 (最大痛点)
2. `init-declarations` 未配置 — 默认走 style warn, 导致大量 if/else 模式触发
3. `no-magic-numbers` 未配置 — 测试文件中大面积触发

---

## 四、行动建议 (按优先级)

| 优先级 | 改动 | 预计减少 | 难度 |
|--------|------|---------|------|
| **P0** | oxlintrc 添加 test file overrides | **-80~100** | 低 (纯配置) |
| **P1** | kangaroo `kg/client.py:92` BLE001 收窄异常 | -1 | 低 |
| **P2** | 验证 4 组 `init-declarations+prefer-ternary` 是否仍触发 | -0~8 | 低 (需本地运行 lint) |
| **P3** | 消除 3 处 `@typescript-eslint/no-explicit-any` | -3 | 中 |
| **P4** | `no-underscore-dangle` 改名 3 处测试函数 | -3 | 中 |

**配置改动后剩余预计**: ~60-70 处 (核心逻辑 keep)
