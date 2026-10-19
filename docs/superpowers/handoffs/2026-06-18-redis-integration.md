# RAG Redis 接入 Handoff (2026-06-18)

> Spec: `docs/superpowers/specs/2026-06-18-redis-integration-design.md`
> Plan: `docs/superpowers/plans/2026-06-18-redis-integration.md`
> 实施: 7 task + 1 docs, 8 commit, 38 测试新增

## 完成清单

- [x] T1 core/redis_client.py facade + 6 测试
- [x] T2 PermissionCache 改 Redis 共享, 60s TTL + 4 测试
- [x] T3 TokenCache 6h sliding + auth.resolve_user 改 async + 7 测试
- [x] T4 RateLimiter IP 限流 + login/reset 端点接入 + 7 测试
- [x] T5 Mem0Ready 跨 worker 标记 + 4 测试
- [x] T6 DifyQueryCache 10min TTL + 5 测试
- [x] T7 EmbedCache 7d TTL base64 + 6 测试
- [x] T8 docs/operations/redis.md + handoff + CLAUDE.md

## 接手 checklist

- [ ] 跑全测试: `cd packages/service && uv run pytest -v`
- [ ] docker compose up + alembic upgrade (0 改动)
- [ ] 启服务: `uv run python main.py`
- [ ] 触发登录 / 重置密码 → 验 rate_limiter 计数
- [ ] 触发同 query 检索 2 次 → 验 DifyQueryCache 命中
- [ ] 触发同 chunk embedding 2 次 → 验 EmbedCache 命中
- [ ] 多 worker 启动 (`uvicorn --workers 4`) → 验 PermissionCache 跨 worker 一致
- [ ] 模拟 Redis 挂 (`docker compose stop redis`) → 验 fail-open 服务不挂

## 已知限制

1. **单 Redis 实例, 无 HA**: docker stop redis = 服务降级 (走原路径), 但 0 数据丢失 (AOF 每 1s 刷)
2. **resolve_user 改 async 可能影响其他 sync 依赖链**: 实施时验证了全测试 0 break, 接手者改新业务时注意
3. **PermissionCache invalidate 跨 worker 生效, 但本地 _local 不同步**: 下次 get 走 Redis miss → 读 PG → 写本地, 期间 0-60s 各 worker 看到旧值 (可接受)
4. **Embedding cache 撞 key 概率极低**: sha256[:16] = 2^64 空间, 撞概率 ~1/2^64
5. **Dify query 不主动失效**: 10min 纯 TTL, ingest 后最多 10min 旧结果, 业务可接受 (spec §5.5 决策)

## 下一步 / 后期工作

1. **Redis Sentinel / Cluster**: 单点故障, 后期 K8s 多 pod 加 Sentinel (spec §10 YAGNI)
2. **arq 任务队列**: spec §9 YAGNI, 单独 spec
3. **按 user_id 限流**: 本期仅 IP, 业务用户配额后期 spec
4. **主动 cache invalidation on ingest**: 10min TTL 够用, 后期如要 0 延迟失效加 spec
5. **Redis 监控接入 Prometheus**: 命中率 / 内存 / 连接数 暴露给 Grafana (本期只 INFO 命令查)

## 关键决策记录

- ✅ Phase 1+2 全做 (7 任务 7 天)
- ✅ Auth token 6h sliding TTL (安全 + 性能平衡)
- ✅ 限流仅 IP (login 5/15min, reset 3/1h)
- ✅ Mem0 Redis ready 标记 (实例进程内存, 不可序列化)
- ✅ Dify query 10min 纯 TTL (业务可接受)
- ✅ 全 fail-open (Redis 挂 = 走原路径)
- ✅ Key 统一 `rag:` 前缀
- ✅ 测试 模式 1 mock + fakeredis

## 相关文档

- Spec: `docs/superpowers/specs/2026-06-18-redis-integration-design.md`
- Plan: `docs/superpowers/plans/2026-06-18-redis-integration.md`
- 运维 SQL: `docs/operations/redis.md`
- 项目约定: `packages/service/CLAUDE.md` (增补 "Redis 使用约定" 章节)