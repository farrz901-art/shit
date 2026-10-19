#!/usr/bin/env bash
# Playwright webServer 脚本: 同时起 next dev 和后端 uvicorn
# 任意一方 ready 即返回, 失败 60s 退出
set -e
cd "$(dirname "$0")/../.."  # web/ → repo root

PORT_NEXT="${PLAYWRIGHT_PORT:-3000}"
PORT_BACKEND="${PLAYWRIGHT_BACKEND_PORT:-8000}"

# 日志目录
LOG_DIR="web/.e2e-logs"
mkdir -p "$LOG_DIR"

# 后端: 用 venv python 避开 uv 路径规范化问题
VENV_PY=".venv/Scripts/python.exe"
[ ! -x "$VENV_PY" ] && VENV_PY=".venv/bin/python"
("$VENV_PY" -m uvicorn src.product_decoders.app:app --host 127.0.0.1 --port "$PORT_BACKEND" \
   > "$LOG_DIR/backend.log" 2>&1) &
BACKEND_PID=$!
echo "backend pid=$BACKEND_PID"

# 前端
(cd web && PORT="$PORT_NEXT" bun run dev) > "$LOG_DIR/next.log" 2>&1 &
NEXT_PID=$!
echo "next pid=$NEXT_PID"

# 等就绪 (2026-06-24) 后端 /health 不存在 (404), 改用 /openapi.json 任意 2xx/4xx/5xx
# 视为服务在跑 (真正 4xx 仍说明 backend 进程活了, 只是该路由不存在)
for i in {1..60}; do
  sleep 1
  BACK_OK=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT_BACKEND/openapi.json" 2>/dev/null || echo 000)
  NEXT_OK=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT_NEXT/" 2>/dev/null || echo 000)
  if [ "$BACK_OK" != "000" ] && [ "$NEXT_OK" = "200" ]; then
    echo "both ready after ${i}s (backend=$BACK_OK next=$NEXT_OK)"
    exit 0
  fi
done

echo "TIMEOUT backend=$BACK_OK next=$NEXT_OK"
echo "--- next.log tail ---"
tail -30 "$LOG_DIR/next.log"
echo "--- backend.log tail ---"
tail -30 "$LOG_DIR/backend.log"
kill $BACKEND_PID $NEXT_PID 2>/dev/null
exit 1
