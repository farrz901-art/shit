---
title: RAG MinIO 集成交接
date: 2026-06-16
status: 完成
---

# RAG MinIO 集成交接 (2026-06-16)

## 核心目标

把 RAG Ingest / Chat 媒体 / Eval CSV / Product decoders 4 子系统从本地 FS 迁到 MinIO 对象存储, 通过 `ObjectStorage` ABC 双实现 (LocalFS + MinIO) 切后端, 不破坏现有契约.

## 实施方式 (5 phase)

1. **Bootstrap**: boto3 依赖 + .env.example + minio_init.sh
2. **ABC + LocalFS impl**: 14 抽象方法, URI parse/build
3. **Minio impl**: boto3 S3 兼容, lazy init, presign
4. **A 集成 (Ingest)**: presign_upload + finalize_upload + read/download 走 ABC
5. **B/C/D + Health + 前端 + 集成测**: 子系统接入 + 健康检查 + 前端 TDD

## Commits (16 个)

| # | Commit |
|---|--------|
| 1 | chore(deps): boto3 + boto3-stubs[s3] + minio_init.sh |
| 2 | feat(storage): ObjectStorage ABC + LocalFS impl + URI helper |
| 3 | feat(storage): MinioObjectStore 完整实现 (boto3 + lazy init + presign) |
| 4 | feat(ingest): IngestTask work_dir 注释 + InputFile/OutputFile uri 字段 |
| 5 | feat(ingest): presign_upload + finalize_upload 端点 (ABC 走通) |
| 6 | feat(ingest): read_task_file / download_zip / upload fallback 改 ABC + process_uri |
| 7 | feat(web): BFF ingest presign/finalize routes + upload v2 头检测 |
| 8 | feat(health): check_minio 集成 |
| 9 | feat(chat_share): B 集成 - presign/finalize 端点 + upload_to_dify 真接通 Dify |
| 10 | feat(web): BFF chat/files presign/finalize routes + multipart fallback |
| 11 | feat(product_decoders): D 集成 - list_files/read_file 走 ABC |
| 12 | feat(eval): C 集成 - Evaluation.dataset_uri 字段 + alembic migration |
| 13 | feat(eval): C 集成 - upload_run 走 ABC + runner 走 URI 模式 |
| 14 | feat(web): A + D 集成前端 - DocumentsImportForm + 3 output 页面 |
| 15 | test(contract + integration): FRONTEND_EXPECTS 同步 + 模式 4 集成测 |
| 16 | docs: handoff + ingest.md + CLAUDE.md + README.md |

## 全量测试结果

- 模式 1 mock 单测: 65+ 测试 (object_store / presign / chat / eval / output / health)
- 模式 4 集成: 6 测试 (test_minio_e2e, CI 跑, dev skip)
- 全绿 0 failed

## Plan / Spec 偏差

- runner.py dataset 参数变可选 (兼容旧调用方)
- Evaluation.id 保持 Integer autoincrement, dataset_uri 路径用 uuid4 hex 单独命名

## Follow-up

- P1: commit history 清理 (如有 squash 需求)
- P2: 输出加 OG meta (preview 卡片)
- P2: Multi-bucket 拆分 (chat/eval 独立 bucket)

## 关键决策记录

- **为什么 ABC**: 业务不感知 backend, env 切换无侵入
- **为什么 default local**: dev 无依赖, 测试无 MinIO server
- **为什么 E1 presign PUT**: 大文件不走 backend 内存, 直传 MinIO
- **为什么 default backend = local**: 现有 50MB+ 文件 OOM 风险, presign 模式消除

## 接手者速查

### ABC 位置
`packages/service/src/storage/object_store.py`

### 单例
```python
from src.storage import get_object_store
store = get_object_store()  # env OBJECT_STORE_BACKEND 决定 impl
```

### 4 端点
- `POST /api/ingest/upload/presign` → 签 PUT URL
- `POST /api/ingest/upload/finalize` → 启动后台 ingest
- `POST /api/chat/files/presign` → 签 PUT URL (chat media)
- `POST /api/chat/files/finalize` → 转发 Dify

### Env 切换
```bash
# Default (dev)
OBJECT_STORE_BACKEND=local
OBJECT_STORE_LOCAL_ROOT=./ingest_uploads

# Production (MinIO)
OBJECT_STORE_BACKEND=minio
OBJECT_STORE_S3_ENDPOINT=http://localhost:9000
OBJECT_STORE_S3_ACCESS_KEY=minioadmin
OBJECT_STORE_S3_SECRET_KEY=minioadmin
OBJECT_STORE_S3_BUCKET=rag-ingest
OBJECT_STORE_S3_REGION=us-east-1
OBJECT_STORE_S3_USE_SSL=false
OBJECT_STORE_PRESIGN_TTL_SECONDS=900
OBJECT_STORE_STAGE_ROOT=/tmp/minio_stage
```

### 关联文档
- Spec: `docs/superpowers/specs/2026-06-16-rag-minio-integration-design.md`
- Plan: `docs/superpowers/plans/2026-06-16-rag-minio-integration.md`