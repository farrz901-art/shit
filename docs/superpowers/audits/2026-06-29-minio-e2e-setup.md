# MinIO 6 项 e2e 跳过 — 需要你手动操作

## 现状

- MinIO container 已起 (12 天前 started, healthy)
- 0 个 bucket 存在
- pytest `tests/integration/test_minio_e2e.py` 6 项因 `OBJECT_STORE_BACKEND=local` 全部 skip

## 步骤

### 1. 创 bucket `rag-ingest`

任选一种:

**A. MinIO 控制台 (推荐, 图形化)**

浏览器打开: http://localhost:9001

- 账号: `minioadmin`
- 密码: `minioadmin` (`.env.local` 的 `OBJECT_STORE_S3_ACCESS_KEY` / `_SECRET_KEY`)
- 左侧 `Buckets` → 右上角 `Create Bucket` → 名字: `rag-ingest` → `Create Bucket`

**B. CLI (`mc` 在 minio container 内)**

```bash
docker exec minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker exec minio mc mb local/rag-ingest
```

### 2. 设环境变量

测试跑时需要:

```bash
export OBJECT_STORE_BACKEND=minio
export OBJECT_STORE_S3_ENDPOINT=http://localhost:9000
export OBJECT_STORE_S3_ACCESS_KEY=minioadmin
export OBJECT_STORE_S3_SECRET_KEY=minioadmin
export OBJECT_STORE_S3_BUCKET=rag-ingest
```

(这些都在 `.env.local` 已配, `OBJECT_STORE_BACKEND` 默认 `local`, 改成 `minio` 即生效)

### 3. 跑测试

```bash
cd packages/service
OBJECT_STORE_BACKEND=minio uv run pytest tests/integration/test_minio_e2e.py -v
```

6 项应全绿:
- `test_abc_put_get_roundtrip`
- `test_abc_list_prefix_returns_objects`
- `test_presign_put_url_works_with_real_put`
- `test_presign_get_url_returns_presigned_url`
- `test_5_prefix_isolation`
- `test_object_not_found_raises`

## 注意事项

- `OBJECT_STORE_BACKEND=minio` 跑完业务代码会**真连 MinIO**, 上传的文件落 `<bucket>/` 下
- 跑完可以 `OBJECT_STORE_BACKEND=local` 切回 dev 默认 (本地文件系统 `./ingest_uploads/`)
- bucket 内 prefix: inputs/ / outputs/ / chat/ / eval/ 是真路径, 业务跑会创建这些子目录
