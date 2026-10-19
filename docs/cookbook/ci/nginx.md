# Nginx 教程

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

Nginx 是一款高性能的 HTTP 服务器、反向代理、负载均衡器。它在 Web 架构中通常承担"流量入口"的角色：接收外部请求，转发到后端应用服务器，并把响应返回给客户端。

**同类对比：**

| 工具 | 定位 | 本项目选择理由 |
|------|------|----------------|
| **Nginx** | 反向代理 + 静态资源 + 负载均衡 | 业界标准，文档和配置资源最丰富 |
| **Caddy** | 自动 HTTPS 反向代理（Go 写） | 配置简单，但生态比 Nginx 小 |
| **HAProxy** | 专门的负载均衡器 | 反代能力弱于 Nginx，HTTP 协议层功能少 |
| **Traefik** | K8s / Docker 场景的反向代理 | 适合动态服务发现，本项目用 Docker Compose 不太需要 |

**Nginx 解决的核心问题**：
- **反向代理**：把客户端请求转发到内部应用（FastAPI / Next.js），对外只暴露 80/443
- **HTTPS 终结**：处理 TLS 证书，应用层只关心 HTTP
- **负载均衡**：多个后端实例间轮询 / 权重分配
- **静态资源服务**：直接返回静态文件（图片、CSS、JS），不走应用层
- **限流 + 防爬**：高频请求拦截

---

## 二、安装 & 启动

### 2.1 Windows + WSL 2 启动

项目使用 Windows + WSL 2 环境，Nginx 推荐在 WSL 2 Ubuntu 里跑：

```bash
# WSL 2 Ubuntu
sudo apt update
sudo apt install -y nginx
sudo service nginx start
# 访问 http://localhost 验证（WSL 2 会自动转发 localhost）
```

### 2.2 Docker 启动（生产推荐）

```bash
# 临时跑
docker run -d -p 80:80 --name nginx nginx:1.27-alpine

# 持久化（挂载配置和日志）
mkdir -p $PWD/nginx/{conf,logs,certs,html}
docker run -d -p 80:80 -p 443:443 \
  -v $PWD/nginx/conf:/etc/nginx/conf.d \
  -v $PWD/nginx/certs:/etc/nginx/certs \
  -v $PWD/nginx/html:/usr/share/nginx/html \
  -v $PWD/nginx/logs:/var/log/nginx \
  --name nginx nginx:1.27-alpine
```

### 2.3 健康检查

```bash
# 检查进程
systemctl status nginx  # Linux
service nginx status      # WSL 2

# 测试配置语法
sudo nginx -t

# 健康端点（需在 nginx.conf 配置）
curl -f http://localhost/health
```

---

## 三、核心概念

1. **Worker Process（工作进程）**：Nginx 主进程 fork 出来的子进程，负责处理请求。默认 `worker_processes auto`（按 CPU 核心数）。
2. **Connection（连接）**：客户端到 Nginx 的 TCP 连接。一个连接可能承载多个 HTTP 请求（HTTP/1.1 keep-alive）。
3. **Server Block（虚拟主机）**：一个 `server { ... }` 块定义一个域名（或端口）的服务规则。一份 nginx.conf 可以有多个 server 块。
4. **Location Block（路由规则）**：在 server 块内，`location /path { ... }` 匹配特定 URL 前缀，决定请求如何处理。
5. **Upstream（上游）**：定义后端服务器列表，proxy_pass 引用 upstream 名做负载均衡。
6. **Proxy Headers**：转发到上游时设置 `X-Forwarded-For` / `X-Real-IP` 等头，让应用拿到真实客户端 IP。

---

## 四、常用命令 & 用法速查

### 4.1 启停

```bash
# Linux / WSL 2
sudo nginx              # 启动
sudo nginx -s stop      # 立即停止
sudo nginx -s quit      # 优雅停止（处理完当前请求）
sudo nginx -s reload    # 重新加载配置（不中断服务）
sudo nginx -s reopen    # 重新打开日志文件

# Docker
docker start nginx
docker stop nginx
docker restart nginx
```

### 4.2 查询

```bash
# 查看版本
nginx -v          # 版本号
nginx -V          # 版本号 + 编译选项

# 测试配置
sudo nginx -t

# 查看进程
ps aux | grep nginx

# 实时查看访问日志
tail -f /var/log/nginx/access.log
```

### 4.3 调试

```bash
# 启用 debug 日志（临时）
# 在 server 块加：error_log /var/log/nginx/error.log debug;

# 查看某条请求经过的 location
curl -v http://localhost/api/test
# 看响应头 X-Debug-Location 之类（需自加 add_header）

# 配置文件分块验证
# 把 http / server / location 块单独写文件，include 到主配置，便于排查
```

### 4.4 排错

```bash
# 配置语法错
sudo nginx -t
# 错误行号会直接打印

# 502 Bad Gateway
# 检查上游是否启动：curl http://localhost:8000/health
# 检查 nginx.conf 中 proxy_pass 地址是否对

# 504 Gateway Timeout
# 默认 60s 超时，调大：proxy_read_timeout 120s;

# 端口被占
netstat -ano | grep :80  # Windows
sudo ss -tlnp | grep :80  # Linux
```

---

## 五、项目集成点

### 5.1 项目当前不使用 Nginx

**项目当前未集成 Nginx**。架构是 FastAPI (`localhost:8000`) + Next.js (`localhost:3000`) 各自裸跑，CORS 配置在 FastAPI 侧（`src/core/app_factory.py:131-139`）做跨域。

### 5.2 未来集成场景

如果加 Nginx，典型架构是：

```
:80 / :443
   ↓
┌──────────────────────┐
│      Nginx           │
│ /api/*  →  FastAPI   │
│ /      →  Next.js    │
│ /static → 静态资源   │
└──────────────────────┘
```

### 5.3 项目相关代理场景

- **容器间访问**：Docker 网络内 `app-network` 上服务名即 hostname（如 `pgvector`、`neo4j`），不需要 Nginx
- **静态资源**：`packages/web/.next/static/` 由 Next.js standalone 直接服务（`packages/web/Dockerfile:51`）
- **TLS / HTTPS**：当前 `localhost` 环境未启用 TLS，生产部署时由 Nginx / Caddy 终结

---

## 六、项目代码示例

### 6.1 反向代理 + 负载均衡（参考配置）

虽然项目未集成，但写一个本项目适用的示例配置（`nginx/conf.d/rag.conf`）：

```nginx
upstream rag_backend {
    least_conn;                          # 负载均衡算法
    server localhost:8000 max_fails=3 fail_timeout=30s;
    # 第二个实例（HA 部署时启用）
    # server localhost:8001 max_fails=3 fail_timeout=30s;
}

upstream rag_web {
    server localhost:3000;
}

server {
    listen 80;
    server_name rag.example.com;

    # 后端 API
    location /api/ {
        proxy_pass http://rag_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;          # LLM 调用慢，调大
        proxy_buffering off;              # 流式响应
    }

    # 前端
    location / {
        proxy_pass http://rag_web;
        proxy_set_header Host $host;
    }
}
```

### 6.2 项目 CORS 配置

`src/core/app_factory.py:125-139` 展示了项目的 CORS 处理。如果改用 Nginx 反代，跨域问题就消失了（Nginx 转发是同源），但生产环境仍可能需要：

```python
# src/core/app_factory.py:131-139
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["content-type"],
    max_age=600,
)
```

### 6.3 Next.js standalone 模式

`packages/web/Dockerfile:49-51` 用 Next.js `standalone` 模式构建，静态资源复制到 `.next/static`：

```dockerfile
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
```

如果用 Nginx 反向代理，`/static/*` 可以直接由 Nginx 服务（更快），不走 Node 进程：

```nginx
location /_next/static/ {
    alias /app/.next/static/;
    expires 1y;                          # 浏览器强缓存
    access_log off;
}
```

---

## 七、项目没用到的能力

以下 Nginx 能力项目当前未使用（**待评估**）：

| 能力 | 用途 | 集成建议 |
|------|------|----------|
| **HTTPS / TLS** | 证书终结 | 生产部署时再启用，dev 用 HTTP 即可 |
| **限流 (limit_req)** | 防止 API 被刷 | 项目用 Redis 限流（`src/core/rate_limiter.py`），Nginx 层冗余 |
| **Gzip 压缩** | 减少响应体积 | 启用收益大（CPU 换带宽），但 Next.js 已在构建时压缩 |
| **WebSocket 代理** | 实时双向通信 | 项目用 SSE / 短轮询，WebSocket 留待 LangGraph 时考虑 |
| **HTTP/2 / HTTP/3** | 提升并发性能 | 生产部署时配 TLS 自动启用 |
| **Caching 缓存** | 静态 / API 响应缓存 | 项目数据实时性高，缓存收益有限 |
| **ModSecurity WAF** | Web 应用防火墙 | 单机项目不需要，K8s 部署时再加 |

**建议关注**：TLS 是生产必需（certbot + Let's Encrypt 自动续签），其他高级能力按需引入。

---

## 八、运维 & 最佳实践 + 常见坑

### 运维检查清单

1. **配置版本管理**：`nginx.conf` 入 Git 仓库，禁止手工改生产环境配置
2. **日志轮转**：用 `logrotate` 或 Docker `--log-opt` 防止日志撑满磁盘
3. **worker 进程数**：`worker_processes auto`（按 CPU 数），IO 密集型可加 `worker_connections 1024`
4. **Keepalive**：`upstream { keepalive 32; }` 减少与上游建连次数
5. **监控指标**：用 Nginx Plus 或 stub_status + Prometheus 暴露指标

### 常见坑

1. **配置 reload 不生效**：`sudo nginx -s reload` 成功但行为没变？检查文件是否被 `include` 到主配置；用 `nginx -T` 看完整配置。
2. **502 误判上游崩溃**：Nginx 默认 1 次失败就标 down，配置 `max_fails=3 fail_timeout=30s` 更稳。
3. **proxy_set_header Host 丢失**：忘了设 `Host $host` 会让 FastAPI 收到错误的 host，影响 redirect URL 生成。
4. **大文件上传被截断**：`client_max_body_size 10m`（默认 1MB）不够，调大到 200MB+ 匹配本项目 `chat_share` 上传限制。
5. **WebSocket 反代路径写错**：WebSocket 升级需要 `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`

---

## 📚 参考

- [Nginx 官方文档](https://nginx.org/en/docs/)
- [Nginx 反向代理指南](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)
- [Nginx 负载均衡](https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/)
- [Nginx + WebSocket](https://www.nginx.com/blog/websocket-nginx/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)（生成 TLS 配置）

---

**状态：** ✅ 已完成

**最后更新：** 2026-06-25
