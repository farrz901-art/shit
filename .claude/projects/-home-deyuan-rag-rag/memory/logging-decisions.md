---
name: logging-decisions
description: "Logging system brainstorming decisions (2026-06-17) - scope, library, audit, Sentry"
metadata: 
  node_type: memory
  type: project
  originSessionId: 20df34db-3217-47b0-9511-2f09132e0f81
---

# 日志系统设计决策 (2026-06-17 brainstorming)

**Scope**: 完整方案 (P0+P1+P2+P3 全做)
- P0 账户安全: 账户删除 / 密码重置 / 邮箱变更 / API key 生成与撤销 / 角色变更 / 账户禁用启用
- P1 数据操作: 知识库删除 / 知识图谱节点删除 / dataset 删除 / 任务取消 / 文件批量删除
- P2 资源访问: 导出数据 / 下载 zip / admin 路由访问 / 跨用户读资源
- P3 业务: 评估运行 / 模型部署 / config 修改 / 用户邀请 / 权限调整

**Library**: 全量切 loguru (不并存 stdlib)
- 8 个模块逐个替换, 旧 stdlib logger 通过 InterceptHandler 桥接

**Sentry**: 暂不用, **记下来, 考虑以后升级** (用户原话)

**Why**: 用户 2026-06-17 主动要求"接入 loguru 和 postgres, 利用 backgroundtask 实现异步写入日志", "所有重要的功能不能静默不报错, 应该捕获错误, 打印在控制台, 并且写到数据库里", "危险操作 (删除账号) 应该写到日志里面", "我没有做过日志系统, 需要 2026 行业最佳实践".

**How to apply**: 写日志 spec / plan 时严格按这个 scope 实施. Sentry 不用, 但在 spec 留"未来升级"段.

**Related**: [[minio-plan-then-deepeval]] (项目执行队列)
