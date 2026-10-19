# MinIO 教程

> 📅 创建日期：2026-06-25
> 📁 项目代码引用：本教程以 `c:/doc/Code/rag` 仓库当前代码为准，所有引用标注 `file_path:line_number`
> 🏷️ 类别：T-工具
> 🎯 读者：中高级 Python/TS 工程师

---

## 目录

- [一、是什么 & 解决什么问题](#一是什么--解决什么问题)
- [二、安装 & 启动](#二安装--启动)
- [三、核心概念](#三核心概念)
- [四、常用命令 & 用法速查](#四常用命令--用法速查)
- [五、项目集成点](#五项目集成点)
- [六、项目代码示例](#六项目代码示例)
- [七、项目没用到的能力](#七项目没用到的能力)
- [八、运维 & 最佳实践 + 常见坑](#八运维--最佳实践--常见坑)

---

## 一、是什么 & 解决什么问题

MinIO 是一款兼容 Amazon S3 API 的开源对象存储系统。它允许你自建一个完全可控的 S3 替代品，适合私有云、混合云、边缘计算等场景。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **MinIO** | 自建 S3 兼容对象存储 | 完全兼容 S3 API，本地开发友好 |
| **Amazon S3** | 云对象存储 | 需 AWS 账号 + 网络出云 |
| **Ceph** | 分布式存储系统 | 太重，单机项目用不上 |
| **SeaweedFS** | 轻量分布式对象存储 | 生态比 MinIO 小，文档少 |
| **本地文件系统** | 简单直接 | 无 S3 API，无法对接 S3 SDK / 浏览器直传 |

**MinIO 解决的核心问题**：
- **海量非结构化数据存储**：文档（PDF/Word）、图片、音视频
- **S3 兼容 API**：开发一次，应用可以无缝切换到 AWS S3
- **浏览器直传**：通过 presigned URL 让前端直接上传到 MinIO，不走后端
- **生命周期管理**：自动删除/归档老文件

---

## 二、安装 & 启动

### 2.1 Docker 启动

```bash
# 单机模式（开发用）
docker run -d \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  -v $PWD/minio_data:/data \
  --name minio \
  minio/minio server /data --console-address ":9001"

# 访问：
# S3 API: http://localhost:9000
# Web Console: http://localhost:9001 (admin / minioadmin)
```

### 2.2 项目集成启动

项目用 Docker Compose 启动，配置在 `docker/docker-compose.yml:54-73`：

```bash
cd docker/
docker compose up -d minio
# 等 healthcheck 通过后初始化 bucket
bash docker/scripts/minio_init.sh
```

### 2.3 健康检查

```bash
# Live（存活）
curl -f http://localhost:9000/minio/health/live
# Ready（就绪，包括磁盘）
curl -f http://localhost:9000/minio/health/ready
```

---

## 三、核心概念

1. **Bucket（桶）**：对象存储的顶层容器，类似文件系统根目录。本项目 `rag-ingest`（`docker/scripts/minio_init.sh:18`）。
2. **Object（对象）**：桶内的单个文件。Key 是对象的全路径（`inputs/abc/foo.pdf`）。
3. **Prefix（前缀）**：用 `/` 分隔的路径前缀，便于按目录管理（如 `inputs/`、`outputs/`、`chat/`）。
4. **Access Key / Secret Key**：S3 兼容的访问凭证，类比 AWS IAM access key。
5. **Presigned URL（预签名 URL）**：后端用 secret 签名的临时 URL，前端可直接 PUT/GET 文件，绕过服务器。
6. **CORS（跨域资源共享）**：MinIO 默认拒绝跨域请求，需要配置允许的 origin。
7. **Lifecycle Rule（生命周期规则）**：自动删除/迁移旧对象的规则（按 prefix 触发）。
8. **Bucket Policy（桶策略）**：控制 anonymous / authenticated 访问的策略 JSON。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Docker
docker start minio
docker stop minio
docker restart minio

# 二进制安装（Linux）
sudo systemctl start minio
sudo systemctl stop minio
```

### 4.2 查询

```bash
# 列出所有桶（用 mc 客户端）
mc alias set local http://localhost:9000 minioadmin minioadmin
mc ls local/

# 列出某桶的对象
mc ls local/rag-ingest/ --recursive

# 桶信息
mc stat local/rag-ingest

# 磁盘使用
mc du local/rag-ingest/
```

### 4.3 调试

```bash
# 上传文件
mc cp ./local.pdf local/rag-ingest/inputs/test.pdf

# 下载
mc cp local/rag-ingest/inputs/test.pdf ./downloaded.pdf

# 生成 presigned URL（15 分钟过期）
mc share download local/rag-ingest/inputs/test.pdf
mc share upload local/rag-ingest/inputs/new.pdf

# 查看对象元数据
mc stat local/rag-ingest/inputs/test.pdf
```

### 4.4 排错

```bash
# 端口冲突
netstat -ano | grep :9000
# 改：-p 9090:9000

# 初始化脚本失败
bash -x docker/scripts/minio_init.sh    # debug 模式
# 常见原因：MINIO_ROOT_USER / PASSWORD 跟 .env 不一致

# Bucket not found
# 跑过 docker compose down -v 吗？会删卷 → bucket 也删了
# 解决：重跑 docker/scripts/minio_init.sh

# CORS 错误（浏览器直传 403）
# 看 mc cors get local/rag-ingest 输出
# 缺 origin 就跑 minio_init.sh
```

---

## 五、项目集成点

### 5.1 项目当前使用 MinIO 做对象存储

`docker/docker-compose.yml:54-73` 定义 MinIO 服务；`docker/scripts/minio_init.sh` 负责 bucket + CORS + lifecycle 初始化。

### 5.2 Bucket 结构

项目用 5 个 prefix 区分用途（`docker/scripts/minio_init.sh:39-47`）：

| Prefix | 保留期 | 用途 |
|--------|--------|------|
| `inputs/` | 永久 | 用户上传的原始文档（PDF/Word/CAD） |
| `outputs/` | 90 天 | ingest 处理结果（Markdown / JSON） |
| `chat/` | 永久 | 聊天会话附件 |
| `eval/` | 永久 | 评估数据集 / 报告 |
| `temp/` | 1 天 | 临时文件（24h 自动删除） |

### 5.3 业务代码引用

```python
# packages/service/src/storage/object_store.py
from src.storage import get_object_store

store = get_object_store()  # env OBJECT_STORE_BACKEND 决定 impl
store.put_bytes("s3://rag-ingest/inputs/abc.pdf", b"...", mime="application/pdf")
store.get_bytes("s3://rag-ingest/inputs/abc.pdf")
store.presign_put("s3://rag-ingest/inputs/abc.pdf")  # 生成 presigned URL
```

### 5.4 URI 规范

- `local://inputs/abc/foo.pdf`（开发模式，文件存本地）
- `s3://rag-ingest/inputs/abc/foo.pdf`（生产模式，走 MinIO/S3）

DB 持久化用 URI 字符串，业务代码不区分 backend。

---

## 六、项目代码示例

### 6.1 MinIO 启动配置

`docker/docker-compose.yml:54-73`：

```yaml
minio:
  image: minio/minio:latest
  container_name: minio
  restart: unless-stopped
  ports:
    - "9000:9000"   # S3 API
    - "9001:9001"   # Web Console
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  volumes:
    - ./volumes/minio_data:/data
  command: server /data --console-address ":9001"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 10s
    timeout: 5s
    retries: 5
  networks:
    - app-network
```

### 6.2 初始化脚本

`docker/scripts/minio_init.sh:18-49` 创建 bucket + CORS + lifecycle：

```bash
# 1. 配 mc alias
mc alias set local "http://${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

# 2. 建 bucket（幂等）
mc mb --ignore-existing "local/${BUCKET}"

# 3. 配 CORS（允许前端直传）
cat > /tmp/cors.json <<EOF
{
  "CORSRules": [{
    "AllowedOrigins": ["${ALLOWED_ORIGIN}"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag", "Content-Length", "Content-Type"],
    "MaxAgeSeconds": 3000
  }]
}
EOF
mc cors set /tmp/cors.json "local/${BUCKET}"

# 4. Lifecycle: 5 prefix 规则
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
```

### 6.3 业务代码：上传文档

`src/ingest/api.py`（简化）演示了文件上传 → MinIO → ingest 处理流程：

```python
# 假设从 FastAPI 接收上传文件
@router.post("/ingest")
async def ingest_file(file: UploadFile, request: Request):
    # 1. 存到 MinIO
    key = f"inputs/{user_id}/{file.filename}"
    store = get_object_store()
    uri = f"s3://rag-ingest/{key}"
    store.put_bytes(uri, await file.read(), mime=file.content_type)

    # 2. 异步处理（pipeline）
    pipeline.process(uri)

    # 3. 返回 presigned URL 让前端预览
    presign = store.presign_get(uri, expires=3600)
    return {"uri": uri, "preview_url": presign}
```

---

## 七、项目没用到的能力

以下 MinIO 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **MinIO Server 多节点** | 分布式 / 高可用 | 单机够用，HA 部署时加 |
| **加密 (SSE-KMS)** | 服务器端加密 | 生产数据敏感时启用 |
| **Object Versioning** | 保留历史版本 | 防误删，但成本翻倍 |
| **事件通知 (Lambda/AMQP)** | 上传后触发处理 | 当前用同步 pipeline，未来异步化时考虑 |
| **Bucket Replication** | 跨 bucket 复制 | 单 bucket 不需要 |
| **Tiering（远程 tier）** | 冷数据存到 AWS S3 Glacier | 数据量小时不需要 |
| **Prometheus 指标导出** | MinIO metrics 接入 Grafana | 监控集成时启用 |

**建议关注**：Object Versioning 适合 `inputs/` prefix（防误删用户上传的源文档），但成本要接受 2x 存储。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **磁盘监控**：`mc du` 定期看增长，重要 prefix 设 quota
2. **备份**：MinIO `mc admin bucket remote add` 可配 cross-region 复制
3. **凭证轮转**：定期换 `MINIO_ROOT_PASSWORD`（重启服务，bucket 数据不丢）
4. **TLS**：生产必须启用 HTTPS（`--certs-dir` 或前置 Nginx / Caddy）
5. **时间同步**：NTP 必须准确，签名 URL 默认 15min 失效，时钟漂移会致 403

### 常见坑

1. **`docker compose down -v` 删数据**：v flag 会删 MinIO volume，所有 bucket 数据全丢。新手误操作。
2. **MINIO_ROOT_PASSWORD 没改**：默认 `minioadmin/minioadmin`，生产环境必须改，且不能跟 PG / Redis 密码共用
3. **CORS 403**：浏览器直传报 403，多半是 `minio_init.sh` 没跑过，或 origin 配置跟前端域名不一致
4. **Presigned URL 失效**：默认 7 天，签名生成时间跟 MinIO 服务器时钟差过大会被拒
5. **小文件过多**：单 bucket 1000 万个小文件性能差，按业务场景用 `tar.gz` 打包或改存数据库 BLOB

---

## 📚 参考

- [MinIO 官方文档](https://min.io/docs/minio/container/index.html)
- [MinIO mc 客户端](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [MinIO Lifecycle 配置](https://min.io/docs/minio/linux/administration/object-management/object-lifecycle-management.html)
- [S3 API 参考](https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html)（MinIO 兼容）
- [MinIO Python SDK (minio-py)](https://min.io/docs/minio/linux/developers/python/minio-py.html)
- [MinIO GitHub](https://github.com/minio/minio)

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
