---
name: feedback-uv-only-no-pip
description: 安装 Python 依赖只能用 uv，禁止用 pip — 项目用 uv 管理虚拟环境和依赖
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 822e2447-09c4-4b8a-9808-d37453aff4b8
---

安装 Python 依赖只能用 `uv`，禁止用 `pip`.

**Why:** 项目用 uv 管理虚拟环境和依赖 (pyproject.toml + uv.lock). 用 pip 安装会绕过 uv 的依赖解析, 导致 lock 文件不同步.

**How to apply:**
- 安装: `uv pip install <package>` 或 `uv add <package>` (写入 pyproject.toml)
- 不要用: `pip install`, `python -m pip install`
