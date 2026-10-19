---
name: ollama-default-binds-127-0-0-1-lan-needs-override
description: "Ollama 0.x 默认 bind 127.0.0.1:11434, LAN 访问必须显式 OLLAMA_HOST=0.0.0.0:11434 via systemd override, 不要靠 ssh tunnel 或 nginx 反代绕"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1b9fcc0d-8861-46a3-a981-3a0937775dd9
---

Ollama 0.x 默认 bind `127.0.0.1:11434`,LAN/外部客户端访问不到。任何访问 `http://<server-ip>:11434` 的请求都会被拒,表现可能是 connection refused,也可能是网关/反代层的 502 Bad Gateway(迷惑信号)。

**现象链** (2026-07-02):
- 用户报 `http://192.168.3.52:11434/api/*` 全 502
- 排查走了 4 步弯路:以为是反代挂了 → 查 nginx/caddy 全没装 → 查 ps 才发现 Ollama 进程健康
- `ss -tlnp | grep 11434` 显示 `LISTEN 127.0.0.1:11434` 才是真因

**Why:** Ollama 官方设计哲学是 local-first,默认绑本机防白嫖。0.x 系列无 switch 改默认行为,只能 override env。

**How to apply:**
- 排查 Ollama LAN 访问问题,第一步先 `ss -tlnp | grep 11434`,看 LISTEN 列是不是 `127.0.0.1` 还是 `0.0.0.0`
- 修法 (systemd override,永久):
  ```bash
  sudo systemctl edit ollama
  # [Service]
  # Environment="OLLAMA_HOST=0.0.0.0:11434"
  sudo systemctl daemon-reload && sudo systemctl restart ollama
  ```
- 临时修法: `OLLAMA_HOST=0.0.0.0:11434 ollama serve` (不推荐,重启失效)
- 子进程 `llama-server --port <随机>` 是 Ollama 多模型时的推理子进程端口,跟 11434 无关,不要被 ps 里的随机端口误导
- 不要用 ssh tunnel 绕(localhost 一样拒,问题在 bind 不是路由)
- 暴露前确认网络环境可信,Ollama 无认证,公网暴露 = 任何人可跑模型

**相关**:
- [[feedback-uvicorn-must-restart-after-route-add]] — 同样是"改了配置不重启/没生效"
- [[feedback-debug-distinguish-root-causes]] — 502 误诊为反代问题