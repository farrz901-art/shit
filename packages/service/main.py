"""RAG 项目统一入口

uv run python main.py            → 启动产品订货号解析服务 (默认, 端口 8000, 自动 kill 占端口进程)
uv run python main.py ingest     → 跑 PDF 离线流水线
uv run uvicorn main:app          → 同上, 用 uvicorn 直起 (开发/调试, 不走端口清理)
"""

# ruff: noqa: E402  # 故意: load_dotenv 必须在 src.* import 之前 (Neo4jStore 加载时读 env)
import argparse

# 必须在 import src.* 之前: Neo4jStore 在模块加载时读 os.getenv, 没 .env.local 就连不上
from dotenv import load_dotenv

load_dotenv(".env.local")

import logging
import socket
import subprocess
import sys
import time

import uvicorn

from src.core.app_factory import create_app
from src.kg.datasets import bootstrap as bootstrap_kg_datasets

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

# 启动时固化 KG_ALLOWED_DATASETS 白名单 (env KG_ALLOWED_DATASETS=motor,plc,sensor)
# 2026-07-01 markdown extract KG spec: dataset label 隔离 Neo4j
bootstrap_kg_datasets()

# 让 `uvicorn main:app` 能直接跑 (开发时常用, 比 python main.py serve 少一层 wrapper)
app = create_app()


# ============================================================
# 端口清理 (2026-06-18): 端口被占时自动 kill 旧进程, 避免 "address already in use"
# ============================================================


def _find_port_pids(port: int) -> list[int]:
    """跨平台找占用 port 的所有 PID. 返 [] 表示端口空闲.

    Windows: netstat -ano | findstr :PORT | LISTENING 行的最后一列
    Unix: lsof -ti :PORT (优先) / fuser PORT/tcp (fallback)
    """
    if sys.platform == "win32":
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids: set[int] = set()
        marker = f":{port} "
        for line in result.stdout.splitlines():
            if marker not in line or "LISTENING" not in line:
                continue
            parts = line.split()
            pid = parts[-1]
            if pid.isdigit() and pid != "0":
                pids.add(int(pid))
        return sorted(pids)
    # Unix / macOS
    for cmd in (
        ["lsof", "-ti", f":{port}"],
        ["fuser", f"{port}/tcp"],
    ):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            pids = {int(p) for p in result.stdout.split() if p.isdigit()}
            if pids:
                return sorted(pids)
    return []


def _kill_pids(pids: list[int], force: bool = False) -> None:
    """跨平台杀进程. force=True 用 SIGKILL / taskkill /F; 否则先软杀 (SIGTERM / taskkill) 等 1s 兜底 force."""
    for pid in pids:
        try:
            if sys.platform == "win32":
                # Windows 没 SIGTERM, taskkill 不带 /F 默认发 WM_CLOSE, 但 Python 进程不响应 → 直接 /F
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)
            elif force:
                subprocess.run(["kill", "-9", str(pid)], check=False)
            else:
                subprocess.run(["kill", str(pid)], check=False)
        except Exception as e:
            logging.getLogger(__name__).warning(f"failed to kill PID {pid}: {e}")


def _wait_port_free(port: int, timeout: float = 2.0) -> bool:
    """尝试 bind port 验证已释放. 返 True=空闲."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", port))
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _kill_port_holder(port: int) -> None:
    """端口被占时杀进程; 空闲时 no-op. 失败抛 RuntimeError."""
    pids = _find_port_pids(port)
    log = logging.getLogger(__name__)
    if not pids:
        log.info(f"port {port} 空闲, 直接启动")
        return
    log.warning(f"port {port} 被 {len(pids)} 个进程占用 (PID: {pids}), 正在清理...")
    # 第一轮软杀
    _kill_pids(pids, force=False)
    if not _wait_port_free(port, timeout=1.0):
        log.warning("软杀未释放, 用 SIGKILL / taskkill /F 重试")
        _kill_pids(pids, force=True)
    if _wait_port_free(port, timeout=2.0):
        log.info(f"port {port} 已释放, 继续启动")
    else:
        raise RuntimeError(f"无法释放 port {port} (占用 PID: {pids}), 请手动 kill")


def cmd_serve(host: str, port: int, reload: bool = True, no_kill_port: bool = False) -> None:
    """启动 FastAPI 产品解析服务

    Args:
        no_kill_port: True = 端口被占时不清理, 直接 uvicorn 报错 (默认 False = 自动清理)
    """
    if not no_kill_port:
        _kill_port_holder(port)
    app = create_app()
    # ws="none" 显式关闭 WebSocket 协议: uvicorn 0.49 在 import websockets 14+ 的 legacy 路径时会打
    # DeprecationWarning (websockets.legacy 2024-11-09 标记废弃), 项目 0 处用 WebSocket (src/ 无
    # @app.websocket), 关掉后 import 链不再触发 warnings.warn, 启动日志干净
    uvicorn.run(app, host=host, port=port, reload=reload, ws="none")


def cmd_ingest(path: str | None = None) -> None:
    """跑 PDF 离线流水线

    Args:
        path: 可选，单文件路径 / 目录路径 / None 走 config.toml 默认 input_dir
    """
    from src.ingest.pipeline import process_path

    process_path(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 入口")
    sub = parser.add_subparsers(dest="mode")

    p_ingest = sub.add_parser("ingest", help="跑 PDF 离线流水线")
    p_ingest.add_argument(
        "path",
        nargs="?",
        default=None,
        help="可选：单个文件路径 或 目录路径；不传走 config.toml 默认 input_dir",
    )
    p_ingest.set_defaults(_handler=cmd_ingest)

    p_serve = sub.add_parser("serve", help="启动产品订货号解析服务")
    p_serve.add_argument("--host", default=DEFAULT_HOST)
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.add_argument(
        "--no-kill-port",
        action="store_true",
        help="端口被占时不杀旧进程, 直接让 uvicorn 报错 (默认自动 kill 占用进程)",
    )
    p_serve.set_defaults(_handler=cmd_serve)

    args = parser.parse_args()
    if not getattr(args, "_handler", None):
        # 没指定子命令 → 默认走 serve
        args = parser.parse_args(["serve"])

    kwargs = {k: v for k, v in vars(args).items() if k not in ("mode", "_handler")}
    args._handler(**kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
