# P4 - 架构债务 spec 草稿 (2026-06-26)

> ⚠️ 草稿, 未实施.
> 来源: [AUDIT-REPORT.md](../AUDIT-REPORT.md) §Architecture (D6) + Concurrency (D2 非安全)
> 关联 checklist: [docs/audit/2026-06-26-findings.md](../../../../docs/audit/2026-06-26-findings.md)

## 范围

### 已验证 finding
- ARCH-002 (high) — os.getenv 分散在 31 个文件中, 未集中到 config/settings.py

### 未 verify
- ARCH-001 (medium) — CLAUDE.md 写 typecheck 用 tsgo, 实际 package.json 用 tsc --noEmit
- ARCH-003 (medium) — MinioObjectStore(283L) 和 EzdxfConverter(323L) 超过 100 行规约
- ARCH-004 (low) — config_legacy.py 冗余
- ARCH-005 (low) — package.json lint:check 与 lint 重复
- ARCH-006 (medium) — 前序 spec 阶段提交绕过 pre-commit
- CONC-001 (medium) — chat_hard_delete_30d 缺分布式锁
- CONC-004 (medium) — Eval 取消信号跨 worker 失效 (架构层面)

### Refuted (排除)
- (无 refuted 在架构维度)

## 修复策略

### 1. Config 集中管理
- 按模块分批迁移 31 个文件的 os.getenv → config/settings.py
- 第一阶段: auth (account_service, account_settings_service)
- 第二阶段: generation (llm.py), integration (dify_client.py)
- 第三阶段: 其余 ~18 个文件

### 2. CLAUDE.md 与 package.json 对齐
- package.json scripts: `typecheck` 统一为 `tsgo --noEmit`
- 更新 CLAUDE.md 对齐

### 3. 函数/类大小规约
- MinioObjectStore 拆分 (合理维度: 文件操作 / presign / health)
- EzdxfConverter 拆分 (解析 / 转换 / 输出)

### 4. 清理冗余
- 删除 config_legacy.py (确认无引用后)
- 删除/合并 lint:check 脚本

### 5. pre-commit 钩子
- --no-verify 记录到 commit message (强制规范)
- CI 加 pre-commit 检查绕过检测

### 6. 分布式锁
- chat_hard_delete_30d 加 Redis 分布式锁 (参考已有模式)
- Eval 取消用 Redis pub/sub

## 不在本文范围
- P0/P1/P2/P3 finding
