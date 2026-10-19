# 全栈代码审计报告 (2026-07-07)

> **范围**: 6 维度并行扫描 + adversarial verify
> **关联**:
> - 扫描简档: [scan-brief.md](scan-brief.md)
> - 发现清单: [docs/audit/2026-07-07-findings.md](../../audit/2026-07-07-findings.md)
> - 5 份 spec 草稿: P0-P4
> **不修任何业务代码** — 仅报告 + 规约.

## 元信息

| 维度 | 总数 | critical | high | medium | low | info | verified | refuted |
|------|------|----------|------|--------|-----|------|----------|---------|
| D1 Security | 13 | 0 | 3 | 5 | 4 | 1 | 3 (high) | 0 |
| D2 Concurrency | 9 | 1 | 4 | 3 | 1 | 0 | 3 (1+2high) | 2 (high) |
| D3 Error | 10 | 0 | 3 | 4 | 3 | 0 | 4 (high) | 0 |
| D4 Data | 7 | 0 | 2 | 3 | 1 | 1 | 2 (high) | 0 |
| D5 Frontend | 13 | 1 | 4 | 5 | 2 | 1 | 3 (1critical+2high) | 1 (high) |
| D6 Architecture | 10 | 0 | 3 | 4 | 3 | 0 | 2 (high) | 1 (high) |
| **合计** | **62** | **2** | **19** | **24** | **14** | **3** | **17** | **4** |

误报率: 4/21 verified candidates = **19%** (Phase 3 反驳后).

## 关键 P0 (需立即修)

| ID | 维度 | 标题 | file:line | verified |
|----|------|------|-----------|----------|
| **CONC-001** | concurrency | DifyHttpChatTransport 5 段状态机 Set 是模块级全局共享 | lib/chat/dify-http-chat-transport.ts:52-53 | ✅ high |
| **FE-001** | frontend | submissions 4 文件用 useTranslations("namespace") + 英文 dotted key, 必然 MISSING_MESSAGE | app/[locale]/submissions/_components/*.tsx | ✅ high |

## 汇总表 — High (按维度)

### D1 Security (3 high, all verified)
- **SEC-002**: 4 BFF 路由漏注 x-user-token (apiProxy 不自动注入) — verified ✅
- **SEC-005**: catch-all `/api/[...path]` 无 origin/referrer 校验 — verified ✅
- **SEC-009**: chat_share create_share 无 @audited 装饰器 — verified ✅

### D2 Concurrency (4 high, 2 verified, 2 refuted)
- **CONC-001** [critical] — 状态机 Set 全局共享 — verified ✅
- **CONC-002** ❌ JS event loop 已保证原子 (refuted by verifier)
- **CONC-003** ❌ last-write-wins 同数据覆盖, 非并发竞态 (refuted)
- **CONC-004** ✅ APScheduler 无 jobstores, 多实例 cron 重复执行
- **CONC-005** ✅ append_message 无 client_msg_id 唯一约束, 网络重发会插入 N 条

### D3 Error (3 high, all verified)
- **ERR-001**: 后端 7+ 路由 `str(e)` 拼 HTTPException detail, 泄露内部错误 — verified ✅
- **ERR-002**: `/decode` 无鉴权 + 暴露 yaml 绝对路径 — verified ✅
- **ERR-003**: chat_share Dify 内部错误透给前端 — verified ✅
- **ERR-005**: chat BFF SSE error 事件原样转 provider message — verified ✅

### D4 Data (2 high, both verified)
- **DATA-001**: pre_analysis_tasks 3 JSON 列用 sa.Text, 应 JSONB — verified ✅
- **DATA-002**: 7 个新枚举硬编 CheckConstraint 不走 lookup (实为 3 个轴, finding 计数偏大) — verified ✅

### D5 Frontend (1 critical + 4 high, 3 verified, 1 refuted)
- **FE-001** [critical] — verified ✅
- **FE-002** ✅ 22 处从 next/navigation 直引 (应 @/i18n/navigation)
- **FE-003** ✅ AppField 缺 aria-invalid / aria-describedby
- **FE-004** ❌ 项目 CLAUDE.md 已声明默认 false (refuted)
- **FE-005** ✅ useBuyerProfiles queryKey inline object

### D6 Architecture (3 high, 2 verified, 1 refuted)
- **ARCH-001** ❌ 实际 21+ 个 BFF route.ts, 每个仅 11-31 行薄模板, 非"复制粘贴大块" (refuted)
- **ARCH-002** ✅ memory-management-dialog.tsx 378 行超 300 上限
- **ARCH-003** ✅ kg/router.py 1045 行 (3.48x), 5 职责混合

## Spec 草稿映射

- **P0-security.md**: SEC-002, SEC-005, SEC-009, CONC-001 + D1 全 13 条
- **P1-error-resilience.md**: ERR-001, ERR-002, ERR-003, ERR-005 (high) + D3 medium/low
- **P2-data-integrity.md**: DATA-001, DATA-002 + D4 其余
- **P3-frontend-quality.md**: FE-001, FE-002, FE-003, FE-005 + D5 medium
- **P4-architecture-debt.md**: CONC-004, CONC-005, ARCH-002, ARCH-003 + D6 medium/low

## 修复优先级建议 (P0 → P1 → P2)

1. **P0**: FE-001 (i18n 必报) → CONC-001 (状态机崩溃) → SEC-002 + SEC-005 (BFF 鉴权 / 端点守卫)
2. **P1**: D3 错误处理 4 条 (后端 / 前端) → ARCH-002 (文件大小)
3. **P2**: DATA-001 (JSONB 漂移) + FE-002 (22 处 import 路径) + ARCH-003 (kg/router 拆分)

总计约 9 人日修复工作量, 详见各 spec 草稿.

## 已证伪的 finding (4 条, 不需处理)

- **CONC-002**: JS event loop 已保证 checkAndIncrement 原子, pruneExpired 不会破坏 entry
- **CONC-003**: 双写 IDB 是 last-write-wins 同数据覆盖, 非并发竞态
- **FE-004**: 项目 CLAUDE.md 本身已规定 `refetchOnWindowFocus: false` 默认
- **ARCH-001**: BFF 实际有 21+ 个文件, 每个 11-31 行薄模板 (force-dynamic + apiProxy + bffProxyResponse), 是统一封装而非大块复制粘贴
