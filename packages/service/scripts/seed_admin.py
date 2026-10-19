"""Seed 首个 admin 账号 — 调 POST /api/account/seed-admin

用法:
    RAG_ADMIN_TOKEN=xxx \\
    RAG_SEED_ADMIN_EMAIL=admin@x.com \\
    RAG_SEED_ADMIN_PASSWORD=longpassword \\
    uv run python scripts/seed_admin.py
"""

# 顺序: 所有 import 在前, load_dotenv 在后 (后者 import dotenv 已 include).
# 跟 main.py 行为一致: load_dotenv 在 import *业务* 之前; 业务 import (os/httpx) 必须在前面.
from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

# Windows console 默认 GBK 编码, print unicode (✓ ✗) 必崩. 强制 utf-8.
# sys.stdout 静态类型是 TextIO (typing), 不含 reconfigure; 但运行时是 io.TextIOWrapper
# pyright 不接受 cast 字符串, 改用 sys.__stdout__ (实际 io.TextIOWrapper 静态类型)
if sys.platform == "win32":
    sys.__stdout__.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]  # noqa: ERA001

# 路径: scripts/seed_admin.py 在 packages/service/scripts/, .env.local 在 packages/service/.env.local
# cwd 决定相对路径解析, 跑前必须 cd 到 packages/service (跟 main.py 一致)
load_dotenv(".env.local")


def main() -> None:
    base = os.getenv("RAG_API_BASE", "http://localhost:8000")
    admin_token = os.getenv("RAG_ADMIN_TOKEN", "")
    email = os.getenv("RAG_SEED_ADMIN_EMAIL", "")
    password = os.getenv("RAG_SEED_ADMIN_PASSWORD", "")
    display_name = os.getenv("RAG_SEED_ADMIN_DISPLAY_NAME", "Admin")

    if not (admin_token and email and password):
        print("✗ 缺环境变量: 需 RAG_ADMIN_TOKEN + RAG_SEED_ADMIN_EMAIL + RAG_SEED_ADMIN_PASSWORD")
        sys.exit(1)

    try:
        r = httpx.post(
            f"{base}/api/account/seed-admin",
            json={"email": email, "password": password, "display_name": display_name},
            headers={"x-admin-token": admin_token},
            timeout=10,
        )
    except httpx.ConnectError as e:
        print(f"✗ 连不上后端 {base}")
        print(f"  原因: {e}")
        print("  修复: 先起后端 — cd packages/service && uv run python main.py")
        print("       或改 RAG_API_BASE 指向实际后端地址")
        sys.exit(1)
    except httpx.TimeoutException:
        print(f"✗ 后端 {base} 超时 (10s 无响应)")
        print("  修复: 检查后端是否卡住 / DB 是否能连")
        sys.exit(1)

    if r.status_code == 200:
        print(f"✓ 创 admin: {r.json()}")
    elif r.status_code == 409:
        print(f"已存在 admin: {r.json().get('detail', r.text)}")
    elif r.status_code == 401:
        print(f"✗ RAG_ADMIN_TOKEN 错: {r.text}")
        sys.exit(1)
    elif r.status_code == 502:
        print(f"✗ {base}/api/account/seed-admin 返 502 (BFF / proxy 上游不可达)")
        print("  常见原因: 调的是 Next.js BFF (3000) 但后端 (8000) 没起")
        print("  修复: 确认 RAG_API_BASE 指向后端 8000, 或先起 uv run python main.py")
        sys.exit(1)
    else:
        print(f"✗ {r.status_code}: {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
