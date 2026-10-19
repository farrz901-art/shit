# RAG 日志系统 Handoff (2026-06-17)

> Spec: `docs/superpowers/specs/2026-06-17-logging-system-design.md`
> Plan: `docs/superpowers/plans/2026-06-17-logging-system.md`
> 实施: 10 task, 7-8 commit, ~40 测试新增

## 完成清单

- [x] T1 Bootstrap: loguru 装包 + .env + contextvars
- [x] T2 PII Scrubber + InterceptHandler
- [x] T3 configure_logging + 控制台 / PG sinks
- [x] T4 9 模块 stdlib → loguru
- [x] T5 RequestIDMiddleware + main.py 切 configure_logging
- [x] T6 DB schema 3 表 + 月分区 + 不可变 trigger
- [x] T7 @audited decorator + AuditContext
- [x] T8 ~20 端点加 hook (按实际代码)
- [x] T9 全局异常 handler 4xx warn / 5xx error
- [x] T10 文档 + handoff (本文件)

## 接手 checklist

- [ ] 跑全测试: `cd packages/service && uv run pytest -v`
- [ ] alembic upgrade: `uv run alembic upgrade head`
- [ ] 启服务: `uv run python main.py` (LOG_TO_DB=true 默认)
- [ ] 触发危险操作 → 验 audit_logs 落表
- [ ] 跑运维 SQL (docs/operations/observability.md)
- [ ] 检查控制台: dev 彩色 / prod JSON

## 已知限制

1. **后台线程崩 → 后续日志全丢**: loguru `enqueue=True` 用一个 worker 线程. 崩了不重启.
   缓解: shutdown 钩子调 `logger.complete()` 排空.
2. **5xx error_logs 同步写 PG → 阻塞 ~5-50ms**: 异常本来就慢, 后期换 enqueue.
3. **audit_logs 不可变 trigger 在 superuser 也生效**: 合规 OK, 但 dev 误操作可能要 DROP TRIGGER 处理.
4. **分区维护未实现**: 当前 migration 只建当月 + 下月分区. 后期写 `scripts/log_partition_cron.py`.
5. **Grafana / Sentry 未接**: spec §13 留路线图. 用户决策 "暂不用".

## 下一步 / 后期工作

1. **分区维护 cron**: 每天续建 + 过期分区 drop
2. **Grafana 仪表盘 JSON**: app_logs / error_logs / audit_logs 仪表盘
3. **Sentry 接入** (env SENTRY_ENABLED + 装包 + 2 行代码)
4. **Loki 接入** (K8s / 多服务时)
5. **审计冷归档** (audit_logs 1 年后导 Parquet 到 MinIO)

## 关键决策记录

- ✅ 全量切 loguru (用户 2026-06-17)
- ✅ Audit ~20 hook (P0+P1+P2+P3, 按实际代码重对齐)
- ✅ 不接 Sentry / Grafana / Loki (留 hook + 路线图)
- ✅ 不做日志查看 UI (后期 Grafana)
- ✅ 3 表分离 (app/error/audit, 不同 retention)
- ✅ 月分区 + audit 不可变 trigger
- ✅ 2026-06-18 sync: 按实际代码调整 hook 落点, 9 模块迁移

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-17-logging-system-design.md`
- Plan: `docs/superpowers/plans/2026-06-17-logging-system.md`
- 运维 SQL: `docs/operations/observability.md`
- 项目约定: `packages/service/CLAUDE.md` (增补日志约定)
