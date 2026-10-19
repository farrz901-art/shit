#!/usr/bin/env bash
# MinIO bucket + CORS + lifecycle 初始化 (2026-06-16 RAG 接入 MinIO spec)
# 跑法: bash docker/scripts/minio_init.sh
# 前提: MinIO 容器已起 (docker compose up -d minio)
# 幂等: 重复跑无副作用 (mc mb --ignore-existing)
set -euo pipefail

# 1. 读 env (允许 .env / .env.local 注入)
: "${MINIO_ROOT_USER:=minioadmin}"
: "${MINIO_ROOT_PASSWORD:=minioadmin}"
: "${MINIO_ENDPOINT:=localhost:9000}"
: "${BUCKET:=rag-ingest}"
: "${ALLOWED_ORIGIN:=http://localhost:3000}"

# 2. 配 mc alias (指向本地 minio)
mc alias set local "http://${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

# 3. 建 bucket (幂等)
mc mb --ignore-existing "local/${BUCKET}"

# 4. 配 CORS (允许浏览器直传, dev 跟前端地址对齐)
cat > /tmp/cors.json <<EOF
{
  "CORSRules": [
    {
      "AllowedOrigins": ["${ALLOWED_ORIGIN}"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag", "Content-Length", "Content-Type"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF
mc cors set /tmp/cors.json "local/${BUCKET}"

# 5. Lifecycle: 5 prefix 规则
cat > /tmp/lifecycle.json <<EOF
{
  "Rules": [
    {"ID": "expire-temp", "Status": "Enabled", "Filter": {"Prefix": "temp/"}, "Expiration": {"Days": 1}},
    {"ID": "expire-outputs", "Status": "Enabled", "Filter": {"Prefix": "outputs/"}, "Expiration": {"Days": 90}},
    {"ID": "keep-chat", "Status": "Enabled", "Filter": {"Prefix": "chat/"}, "Expiration": {"Days": 0}},
    {"ID": "keep-eval", "Status": "Enabled", "Filter": {"Prefix": "eval/"}, "Expiration": {"Days": 0}},
    {"ID": "keep-inputs", "Status": "Enabled", "Filter": {"Prefix": "inputs/"}, "Expiration": {"Days": 0}}
  ]
}
EOF
mc ilm import < /tmp/lifecycle.json "local/${BUCKET}"

# 6. 桶策略: 不设 anonymous read, 全部走 presigned
echo "✓ MinIO init done: bucket=${BUCKET}, CORS origin=${ALLOWED_ORIGIN}"
