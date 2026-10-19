---
name: feedback-pytest-cwd-redirect-buffer
description: 跑 pytest 反复撞 3 个错 — CWD / 重定向 / 大输出超 buffer, 反复重试浪费时间
metadata:
  type: feedback
---

跑后端 `uv run pytest` 反复撞 3 个错, 误判"还在跑"重试浪费时间 (2026-07-08 inline 修 18 fail + 2 warnings + 1 filter config 期间多花 10-15 分钟):

1. **CWD 错**: `uv run` 读当前目录的 `pyproject.toml` + `.venv` 找 pytest. 仓库根跑立即报 `Failed to spawn: pytest (No such file or directory)` exit 0, 看起来"没结果".
   - ✅ 永远 `cd /home/deyuan/rag/rag/packages/service && uv run pytest ...`
   - ❌ 在仓库根跑 `uv run pytest` (没 cd)

2. **重定向必须配 cd**: `uv run pytest 2>/tmp/pw.txt 1>/tmp/po.txt` 单独写不 cd → 文件 0 字节 (命令立即报 uv 错, 没进 pytest). 拆成两步: 先 cd 在 background task, 后写 pytest, CWD 不持久, 也会 0 字节.
   - ✅ 整条命令同一行带 cd: `cd packages/service && uv run pytest ... 2>pw.txt`

3. **大输出会超 buffer**: 1k+ test 跑全量时 30k+ 行 (warning 路径 + traceback), Bash 截断后像"没结果". 看输出空就重跑 5 分钟全量, 实际命令早 exit.
   - ✅ 跑过的用 `Read` 读 /tmp/pytest-stdout.txt 找具体行
   - ✅ 验证性测试只跑单文件 (`uv run pytest tests/foo/test_x.py`), 1.x 秒
   - ❌ 重复跑全量

**Why**: 误判"pytest 还在跑"重试 3 次, 单次就够的验证被多花 10-15 分钟.
**How to apply**: 任何 `uv run pytest` / `bun run test` 跑前先确认 (a) CWD 是 `packages/service` 或 `packages/web` (b) 不写文件重定向除非整条命令同 cd (c) 验证只跑改过的文件, 不重跑全量. 沉淀在 [CLAUDE.md §测试运行避坑](../../../../../CLAUDE.md).
