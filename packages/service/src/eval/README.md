# 评估子系统 (src/rag/eval)

异步跑 Dify + RAGAS, 落 SQLite `evaluations` + `evaluation_samples` 表.

## 公开 API

- `GET  /api/evaluate/runs`           列表 (admin 看全部, 普通看自己)
- `POST /api/evaluate/runs`           上传 CSV, 启动后台 task
- `GET  /api/evaluate/runs/{id}`      详情 + samples
- `POST /api/evaluate/runs/{id}/cancel` 取消 running
- `GET  /api/evaluate/template`       下载 CSV 模板

## 状态机

`pending` → `running` → (`completed` | `failed` | `cancelled`)

取消机制: 进程内 `dict[evaluation_id, asyncio.Event]`, 多 worker 不支持 (YAGNI).

## Admin 调试

后端 `.env` 配 `RAG_ADMIN_TOKEN=xxx` (生成: `python -c "import secrets; print(secrets.token_hex(16))"`),
浏览器 devtools 改 header `x-admin-token: xxx` 就能看所有用户数据.

⚠️ **生产部署务必留空**, 见 [docs/superpowers/specs/2026-06-09-evaluate-page-redesign-design.md](../../superpowers/specs/2026-06-09-evaluate-page-redesign-design.md).

## 重启恢复

启动时调 `recover_orphaned_running()`, 把 status='running' 的行标 failed + 写 "服务重启中断".

## 文件结构

```
src/rag/eval/
├── __init__.py            # 暴露 recover_orphaned_running
├── models.py              # Evaluation + EvaluationSample (storage spec 已有)
├── router.py              # FastAPI 路由 (5 endpoint)
├── runner.py              # 异步运行器 (Dify + RAGAS + DB 落库)
├── runner_registry.py     # 进程内取消 Event 表 + 重启恢复
├── csv_parser.py          # CSV 校验 + 清洗
├── template.py            # 模板生成
└── README.md              # 本文件

tests/rag/eval/
├── test_router.py
├── test_runner.py
├── test_runner_registry.py
├── test_csv_parser.py
└── test_template.py
```

## 测试

```bash
uv run --no-sync python -m pytest tests/rag/eval/ -v
```

## 后续工作 (不在本 spec)

- 客户端 token spec (BFF 中间件配套) - 独立 plan
- 聊天 spec (复用 CurrentUser) - 独立 plan
- 多 worker 部署时取消信号换 Redis
