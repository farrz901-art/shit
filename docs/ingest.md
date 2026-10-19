# Ingest 文档

## 端点列表

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | /api/ingest/upload/presign | 签 PUT URL, 前端直传 MinIO |
| POST | /api/ingest/upload/finalize | 通知后台启动 ingest |
| POST | /api/ingest/upload | (fallback) 后端 multipart 收文件 |
| GET | /api/ingest/tasks/{id}/files/{name} | 拿文件 presigned GET URL |
| GET | /api/ingest/tasks/{id}/download | 打包下载整个任务 (outputs + inputs) |

## Env 切换

```bash
# Local (default, dev)
OBJECT_STORE_BACKEND=local
OBJECT_STORE_LOCAL_ROOT=./ingest_uploads

# MinIO (生产 / 集成测)
OBJECT_STORE_BACKEND=minio
OBJECT_STORE_S3_ENDPOINT=http://localhost:9000
OBJECT_STORE_S3_BUCKET=rag-ingest
# ... 其他 S3 配置
```

## MinIO Bucket 布局

5 个 prefix (lifecycle 各异):

| Prefix | 用途 | Lifecycle |
|--------|------|-----------|
| inputs/ | 用户上传原始文件 | 永久保留 |
| outputs/ | 处理产物 | 90 天后过期 |
| chat/ | chat 媒体 (Dify Files) | 永久保留 |
| eval/ | Eval CSV | 永久保留 |
| temp/ | 临时文件 | 1 天后过期 |

## CORS 配置

浏览器直传需要 CORS. `docker/scripts/minio_init.sh` 一次性配置:
- AllowedOrigins: 走 env `ALLOWED_ORIGIN`
- AllowedMethods: GET / PUT / POST / DELETE / HEAD
- AllowedHeaders: *
- ExposeHeaders: ETag / Content-Length / Content-Type

## 故障排查

### CORS 错

浏览器控制台报 "Access to fetch has been blocked by CORS policy":
- 检查 `minio_init.sh` 跑过: `mc cors get local/rag-ingest`
- 检查 ALLOWED_ORIGIN 跟前端地址匹配

### Presign URL 过期

默认 900s (15 分钟) 过期:
- env `OBJECT_STORE_PRESIGN_TTL_SECONDS` 调
- 客户端应在过期前重新走 presign 流程

### Bucket 不存在

启动报 `NoSuchBucket`:
- 跑 `bash docker/scripts/minio_init.sh` 建 bucket
- 检查 `OBJECT_STORE_S3_BUCKET` 跟实际 bucket 一致

### Local 模式找不到文件

- 检查 `OBJECT_STORE_LOCAL_ROOT` 路径存在
- dev default: `./ingest_uploads` (已在 .gitignore)