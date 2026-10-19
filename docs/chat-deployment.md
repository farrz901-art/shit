# 智能体聊天界面 部署指南

> 创建于 2026-06-09

## 概述

`/chat` 路由同时支持内网调试 + 公网暴露, 用单一 next 实例 + nginx 路径分流 + Next.js middleware 兜底。

## 架构

```
                  ┌──── 内网 (10.x.x.x) ────┐
nginx ──── /  ────►  next  ─── /decode
                  │          ─── /output
                  │          ─── /knowledge
                  │          ─── /api/knowledge/*
                  │          ─── /chat
                  │          ─── /api/chat/*
                  │
                  └──── 公网 (暴露 /chat) ─┐
                  │          ─── /chat
                  │          ─── /api/chat/*
```

## Nginx 片段

```nginx
server {
    listen 443 ssl;
    server_name your.domain;

    # SSE 必须关 buffer
    location /api/chat/ {
        proxy_pass http://127.0.0.1:3000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
    }

    location /chat {
        proxy_pass http://127.0.0.1:3000;
    }

    location / {
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://127.0.0.1:3000;
    }

    limit_req_zone $binary_remote_addr zone=chat:10m rate=10r/s;
    location /api/chat/ {
        limit_req zone=chat burst=20 nodelay;
    }
}
```

## 必配 env

| 变量 | 用途 | 出 bundle? |
|---|---|---|
| `DIFY_API_KEY` | Dify 后台 API 密钥 | ❌ server only |
| `DIFY_API_URL` | Dify 服务地址 | ❌ |
| `DIFY_CHATFLOW_APP_ID` | dify 应用 16 位 hash | ❌ |
| `CHAT_PROVIDER` | 工厂开关 (v1=`dify`) | ❌ |
| `CHAT_PUBLIC_TOKEN` | 公网 anti-abuse | ❌ |
| `NEXT_PUBLIC_CHAT_TOKEN` | 同上, 前端读 | ✅ |
| `CHAT_PUBLIC_MODE` | middleware 开关 | ❌ |

**安全约束:**
- `DIFY_API_KEY` 永远不加 `NEXT_PUBLIC_` 前缀
- `CHAT_PUBLIC_TOKEN` 不是私钥; nginx rate limit 是主防线
- 公网部署期 `CHAT_PUBLIC_MODE=true`

## Dify 后台配置

1. 创建 **Chatflow** 类型应用
2. 编排工作流 (知识检索 + LLM 节点)
3. 发布, 拿 API 密钥 (格式 `app-xxx`)
4. URL 末段 16 位 hash = `DIFY_CHATFLOW_APP_ID`

## 端到端验证清单

- [ ] `curl /api/chat/messages` 无 token → 401
- [ ] `curl -H "x-chat-token: ..." /api/chat/messages` → SSE 流
- [ ] 浏览器 `/chat` 输入消息 → 打字效果
- [ ] 引用块可展开
- [ ] 停止按钮真能停
- [ ] 刷新后历史还在 (localStorage)
- [ ] 公网模式 `/` → 404

## 已知限制

- v1 localStorage 持久化: 换浏览器 = 丢历史
- 无后端账号: 防滥用靠 nginx rate limit
- 不支持图片/文件上传 (v2)
